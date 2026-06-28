"""Proves BACKLOG B8: an invoice with lines persists and receives a gapless number.

Also pins the properties that matter downstream: numbers are sequential across
invoices and — because the number is drawn on the caller's session — a rolled-back
invoice does *not* burn a number. The module is exercised the way the host will
use it: installed through the loader, then issuing invoices.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from invoicing import Invoice, InvoiceStatus, LineInput, Party, issue_invoice, manifest
from nucleus.db import make_session_factory, unit_of_work
from nucleus.modules import Action, ModuleContext, load_modules
from nucleus.primitives import Money

# Tables this module (and its numbering/loader deps) touch, dropped for isolation.
_TABLES = (
    "invoicing_invoice_line",
    "invoicing_invoice",
    "invoicing_party",
    "sequences",
    "installed_modules",
)


def _reset(engine: Engine) -> None:
    with engine.begin() as conn:
        for table in _TABLES:
            conn.execute(text(f'DROP TABLE IF EXISTS "{table}" CASCADE'))


@pytest.fixture
def session_factory(pg_engine: Engine) -> sessionmaker[Session]:
    _reset(pg_engine)
    factory = make_session_factory(pg_engine)
    with factory() as session:  # install the schema via the module's own migrate hook
        manifest.migrate(ModuleContext(session=session))
        session.commit()
    yield factory
    _reset(pg_engine)


def _party() -> Party:
    return Party(name="Acme S.A.S.", tax_id="900.123.456-7", jurisdiction="CO")


def _lines() -> list[LineInput]:
    return [
        LineInput("Consulting", Decimal("10"), Decimal("100000"), "iva_19"),
        LineInput("Hosting", Decimal("1"), Decimal("50000"), "iva_19"),
    ]


def test_invoice_persists_with_lines_and_a_number(
    session_factory: sessionmaker[Session],
) -> None:
    with unit_of_work(session_factory) as session:
        invoice = issue_invoice(session, party=_party(), currency="COP", lines=_lines())
        invoice_id = invoice.id

    # Reload from a fresh session: prove it's really in the database, not just in
    # the identity map of the session that wrote it.
    with session_factory() as session:
        loaded = session.get(Invoice, invoice_id)
        assert loaded is not None
        assert loaded.number == 1
        assert loaded.status == InvoiceStatus.ISSUED
        assert len(loaded.lines) == 2
        assert loaded.party.tax_id == "900.123.456-7"
        # COP renders with no decimals; subtotal = 10*100000 + 1*50000.
        assert loaded.subtotal() == Money("1050000", "COP")


def test_numbers_are_gapless_across_invoices(
    session_factory: sessionmaker[Session],
) -> None:
    numbers = []
    for _ in range(3):
        with unit_of_work(session_factory) as session:
            invoice = issue_invoice(session, party=_party(), currency="COP", lines=_lines())
            numbers.append(invoice.number)

    assert numbers == [1, 2, 3]


def test_rolled_back_invoice_does_not_burn_a_number(
    session_factory: sessionmaker[Session],
) -> None:
    # Allocate a number, then blow up the unit of work: the number must roll back
    # with everything else, or numbering would gap on every failed request.
    with pytest.raises(RuntimeError, match="abort"):
        with unit_of_work(session_factory) as session:
            issue_invoice(session, party=_party(), currency="COP", lines=_lines())
            raise RuntimeError("abort")

    with unit_of_work(session_factory) as session:
        invoice = issue_invoice(session, party=_party(), currency="COP", lines=_lines())
        assert invoice.number == 1  # not 2 — the aborted number was reused, not skipped


def test_module_installs_via_loader(pg_engine: Engine) -> None:
    # The real path: the loader installs invoicing, then invoices can be issued.
    _reset(pg_engine)
    factory = make_session_factory(pg_engine)
    try:
        with unit_of_work(factory) as session:
            results = load_modules([manifest], session)
        assert [(r.name, r.action) for r in results] == [("invoicing", Action.INSTALLED)]

        with unit_of_work(factory) as session:
            invoice = issue_invoice(
                session,
                party=_party(),
                currency="COP",
                lines=[LineInput("Item", Decimal("1"), Decimal("1000"), "iva_19")],
            )
            assert invoice.number == 1
    finally:
        _reset(pg_engine)
