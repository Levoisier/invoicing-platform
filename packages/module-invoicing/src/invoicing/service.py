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
from nucleus.primitives import Sequence

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

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
