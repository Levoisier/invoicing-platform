"""Recording a payment: post the ledger AND move the invoice status, as one unit.

This is the crux of "transactional intimacy". ``record_payment`` writes the
payment, its balanced double-entry ledger rows, and the invoice's new status all on
the *caller's* session — so the caller's unit of work commits them together or rolls
them all back together. There is no point at which the books say "paid" but the
ledger is missing, or vice versa.

The function depends on invoicing (a downward dependency: payments is the later
module in the build spine). That's deliberate — the atomic action genuinely spans
both domains, and a same-process import is what keeps it in one transaction. An
out-of-process call here is exactly what would break atomicity (see the test).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import func, select

from invoicing import Invoice, InvoiceStatus, compute_totals
from nucleus.primitives import Money
from nucleus.registry import tax as _tax_registry
from payments.models import LedgerEntry, Payment

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from nucleus.contracts import TaxCalculator
    from nucleus.registry import Registry

# A customer payment moves value out of what they owe us (accounts receivable) and
# into cash. Debit cash, credit AR — equal and opposite, so the entry balances.
_CASH = "cash"
_ACCOUNTS_RECEIVABLE = "accounts_receivable"


def record_payment(
    session: Session,
    *,
    invoice: Invoice,
    amount: Money,
    tax_registry: Registry[str, TaxCalculator] = _tax_registry,
) -> Payment:
    """Post `amount` against `invoice`: ledger entries + status transition, atomic."""
    if amount.currency != invoice.currency:
        # Mixing currencies on a payment is a bug, not something to coerce.
        raise ValueError(
            f"payment currency {amount.currency} != invoice currency {invoice.currency}"
        )

    payment = Payment(
        invoice_id=invoice.id,
        amount=amount.amount,
        currency=amount.currency,
        ledger_entries=[
            LedgerEntry(account=_CASH, amount=amount.amount),  # debit
            LedgerEntry(account=_ACCOUNTS_RECEIVABLE, amount=-amount.amount),  # credit
        ],
    )
    session.add(payment)
    session.flush()  # the new payment counts toward "total paid" below

    # Recompute status from total-paid vs invoice total. Reads and the write are on
    # the same session, so the status change rides the same transaction as the ledger.
    invoice.status = _status_for(session, invoice, tax_registry)
    session.flush()
    return payment


def _status_for(
    session: Session, invoice: Invoice, tax_registry: Registry[str, TaxCalculator]
) -> InvoiceStatus:
    total = compute_totals(invoice, tax_registry=tax_registry).total
    paid = session.execute(
        select(func.coalesce(func.sum(Payment.amount), 0)).where(
            Payment.invoice_id == invoice.id
        )
    ).scalar_one()
    # Same currency throughout (guarded above), so comparing amounts is safe.
    if Money(paid, invoice.currency).amount >= total.amount:
        return InvoiceStatus.PAID
    return InvoiceStatus.PARTIAL
