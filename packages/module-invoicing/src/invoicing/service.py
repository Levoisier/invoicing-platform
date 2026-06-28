"""Invoicing operations. Today: issue an invoice with lines and a gapless number.

The service is where the nucleus primitives meet the domain: it draws the next
number from a ``Sequence`` (row-locked, gapless) on the caller's session, so the
number is allocated in the same transaction that persists the invoice. If the
caller's unit of work rolls back, the number rolls back with it — never skipped,
never reused for a different invoice.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING

from invoicing.models import Invoice, InvoiceLine, InvoiceStatus, Party
from nucleus.primitives import Money, Sequence
from nucleus.registry import tax as _tax_registry

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from nucleus.contracts import TaxCalculator
    from nucleus.registry import Registry

# One shared counter for invoice numbers. Stateless (the state is the DB row), so a
# module-level instance is fine and every worker addresses the same "invoice" row.
_INVOICE_NUMBERS = Sequence("invoice")


@dataclass(frozen=True)
class LineInput:
    """A line to put on an invoice. Plain data so callers (routes, tests) don't
    construct ORM objects directly."""

    description: str
    quantity: Decimal
    unit_price: Decimal
    tax_code: str


def issue_invoice(
    session: Session, *, party: Party, currency: str, lines: list[LineInput]
) -> Invoice:
    """Create and persist an issued invoice with `lines`, assigning the next
    gapless number. Returns the flushed invoice (its id and number populated)."""
    invoice = Invoice(
        party=party,
        currency=currency,
        status=InvoiceStatus.ISSUED,
        # Allocate the number on this session → same transaction as the insert.
        number=_INVOICE_NUMBERS.next_value(session),
        lines=[
            InvoiceLine(
                description=line.description,
                quantity=line.quantity,
                unit_price=line.unit_price,
                tax_code=line.tax_code,
            )
            for line in lines
        ],
    )
    session.add(invoice)
    # Flush now so the PK/number are assigned and any constraint violation surfaces
    # here, inside the caller's transaction, rather than at a surprising later point.
    session.flush()
    return invoice


@dataclass(frozen=True)
class InvoiceTotals:
    """An invoice's money, broken out so a PDF/UI can show the IVA line (B11)."""

    subtotal: Money  # net of tax
    tax: Money  # total IVA
    total: Money  # subtotal + tax


def compute_totals(
    invoice: Invoice, *, tax_registry: Registry[str, TaxCalculator] = _tax_registry
) -> InvoiceTotals:
    """Total an invoice, applying tax via the calculator registered for the
    client's jurisdiction.

    This is the inversion in action: invoicing resolves the calculator from the
    registry by ``party.jurisdiction`` and never imports a plugin. If no plugin is
    registered for that jurisdiction, ``registry.get`` raises a clear "no
    TaxCalculator registered" error — which is exactly how removing a jurisdiction
    fails: cleanly, with no core change."""
    calculator = tax_registry.get(invoice.party.jurisdiction)
    subtotal = Money(0, invoice.currency)
    tax = Money(0, invoice.currency)
    for line in invoice.lines:
        net = line.net()
        subtotal = subtotal + net
        tax = tax + calculator.tax_for(net, line.tax_code)
    return InvoiceTotals(subtotal=subtotal, tax=tax, total=subtotal + tax)
