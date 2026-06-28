"""Proves BACKLOG B12: invoice status + ledger entries commit together and roll back
together — and demonstrates *why* same-process/same-transaction is what makes that
possible, by breaking it out-of-process.

Atomicity is the project's second core idea. These tests issue a real CO invoice,
record payments against it, and check that the status transition and the ledger move
as one unit. The final test deliberately posts the ledger in a *separate*
transaction (simulating an out-of-process ledger service) and shows the books go
inconsistent — the exact failure same-transaction `record_payment` prevents.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from invoicing import Invoice, InvoiceStatus, LineInput, Party, issue_invoice
from invoicing import manifest as invoicing_manifest
from nucleus.db import make_session_factory, unit_of_work
from nucleus.modules import load_modules
from nucleus.plugins import discover_plugins
from nucleus.primitives import Money
from nucleus.registry import Registry
from payments import LedgerEntry, Payment, record_payment
from payments import manifest as payments_manifest

_TABLES = (
    "payments_ledger_entry",
    "payments_payment",
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
def env(pg_engine: Engine) -> tuple[sessionmaker[Session], Registry]:
    _reset(pg_engine)
    factory = make_session_factory(pg_engine)
    # Load both modules via the loader → proves toposort orders invoicing before
    # payments (the cross-module FK needs invoicing's table first).
    with unit_of_work(factory) as session:
        results = load_modules([payments_manifest, invoicing_manifest], session)
    assert [r.name for r in results] == ["invoicing", "payments"]

    registry: Registry = Registry(label="TaxCalculator", key_name="jurisdiction")
    discover_plugins(tax=registry)  # the real CO plugin, for compute_totals
    yield factory, registry
    _reset(pg_engine)


def _issue_co_invoice(factory: sessionmaker[Session]) -> int:
    # One iva_19 line: net 1,000,000, IVA 190,000, total 1,190,000 COP.
    with unit_of_work(factory) as session:
        invoice = issue_invoice(
            session,
            party=Party(name="Acme", tax_id="900.1", jurisdiction="CO"),
            currency="COP",
            lines=[LineInput("Consulting", Decimal("1"), Decimal("1000000"), "iva_19")],
        )
        return invoice.id


def _counts(factory: sessionmaker[Session], invoice_id: int) -> tuple[InvoiceStatus, int, int]:
    with factory() as session:
        status = session.get(Invoice, invoice_id).status
        payments = session.execute(
            select(func.count()).select_from(Payment).where(Payment.invoice_id == invoice_id)
        ).scalar_one()
        ledger = session.execute(select(func.count()).select_from(LedgerEntry)).scalar_one()
    return status, payments, ledger


def test_full_payment_commits_status_and_ledger_together(
    env: tuple[sessionmaker[Session], Registry],
) -> None:
    factory, registry = env
    invoice_id = _issue_co_invoice(factory)

    with unit_of_work(factory) as session:
        invoice = session.get(Invoice, invoice_id)
        record_payment(
            session, invoice=invoice, amount=Money("1190000", "COP"), tax_registry=registry
        )

    status, payments, ledger = _counts(factory, invoice_id)
    assert status == InvoiceStatus.PAID
    assert payments == 1
    assert ledger == 2  # debit cash + credit AR


def test_partial_then_full_payment_transitions_status(
    env: tuple[sessionmaker[Session], Registry],
) -> None:
    factory, registry = env
    invoice_id = _issue_co_invoice(factory)

    with unit_of_work(factory) as session:
        invoice = session.get(Invoice, invoice_id)
        record_payment(
            session, invoice=invoice, amount=Money("500000", "COP"), tax_registry=registry
        )
    assert _counts(factory, invoice_id)[0] == InvoiceStatus.PARTIAL

    with unit_of_work(factory) as session:
        invoice = session.get(Invoice, invoice_id)
        record_payment(
            session, invoice=invoice, amount=Money("690000", "COP"), tax_registry=registry
        )
    assert _counts(factory, invoice_id)[0] == InvoiceStatus.PAID


def test_ledger_for_a_payment_balances_to_zero(
    env: tuple[sessionmaker[Session], Registry],
) -> None:
    factory, registry = env
    invoice_id = _issue_co_invoice(factory)
    with unit_of_work(factory) as session:
        invoice = session.get(Invoice, invoice_id)
        record_payment(
            session, invoice=invoice, amount=Money("1190000", "COP"), tax_registry=registry
        )

    with factory() as session:
        total = session.execute(select(func.coalesce(func.sum(LedgerEntry.amount), 0))).scalar_one()
    assert total == Decimal("0")  # double-entry: debits + credits net to zero


def test_failure_rolls_back_status_and_ledger_together(
    env: tuple[sessionmaker[Session], Registry],
) -> None:
    factory, registry = env
    invoice_id = _issue_co_invoice(factory)

    # Record the payment, then blow up *before* the unit of work commits.
    with pytest.raises(RuntimeError, match="boom"):
        with unit_of_work(factory) as session:
            invoice = session.get(Invoice, invoice_id)
            record_payment(
                session, invoice=invoice, amount=Money("1190000", "COP"), tax_registry=registry
            )
            raise RuntimeError("boom after recording payment")

    # Everything rolled back as a unit: status untouched, no payment, no ledger.
    status, payments, ledger = _counts(factory, invoice_id)
    assert status == InvoiceStatus.ISSUED
    assert payments == 0
    assert ledger == 0


def test_out_of_process_ledger_breaks_atomicity(
    env: tuple[sessionmaker[Session], Registry],
) -> None:
    """The demonstration: do it the wrong way and watch the books tear.

    A separate, already-committed transaction posts the payment+ledger (as a remote
    ledger service would), and then the status update fails in its own transaction.
    The ledger is now durable but the invoice never moved — precisely the corruption
    that same-transaction `record_payment` makes impossible.
    """
    factory, _ = env
    invoice_id = _issue_co_invoice(factory)

    # "Out-of-process" ledger service: its own transaction, commits independently.
    with unit_of_work(factory) as ledger_session:
        ledger_session.add(
            Payment(
                invoice_id=invoice_id,
                amount=Decimal("1190000"),
                currency="COP",
                ledger_entries=[
                    LedgerEntry(account="cash", amount=Decimal("1190000")),
                    LedgerEntry(account="accounts_receivable", amount=Decimal("-1190000")),
                ],
            )
        )

    # The caller then updates status in a *different* transaction, which fails.
    with pytest.raises(RuntimeError, match="status update failed"):
        with unit_of_work(factory) as session:
            session.get(Invoice, invoice_id).status = InvoiceStatus.PAID
            raise RuntimeError("status update failed")

    # The damage: payment+ledger committed, but the invoice is still ISSUED. Two
    # transactions cannot roll back together — which is the whole argument for
    # keeping modules in one process sharing one session.
    status, payments, ledger = _counts(factory, invoice_id)
    assert status == InvoiceStatus.ISSUED
    assert payments == 1
    assert ledger == 2
