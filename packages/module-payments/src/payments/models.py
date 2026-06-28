"""Payments entities: Payment and its double-entry LedgerEntry rows.

Both inherit the nucleus ``Base``, so they live in the same metadata and the same
transaction as the invoice they settle — that shared transaction is what makes a
payment's ledger entries and the invoice's status move as one unit (the property
B12 exists to prove). The FK from ``Payment`` to ``invoicing_invoice`` is a
cross-module reference made safe by the loader's toposort: invoicing's tables are
created before payments'.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from nucleus.db import Base


class Payment(Base):
    __tablename__ = "payments_payment"

    id: Mapped[int] = mapped_column(primary_key=True)
    invoice_id: Mapped[int] = mapped_column(ForeignKey("invoicing_invoice.id"))
    amount: Mapped[Decimal] = mapped_column(Numeric)
    currency: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    ledger_entries: Mapped[list[LedgerEntry]] = relationship(
        back_populates="payment", cascade="all, delete-orphan"
    )


class LedgerEntry(Base):
    __tablename__ = "payments_ledger_entry"

    id: Mapped[int] = mapped_column(primary_key=True)
    payment_id: Mapped[int] = mapped_column(ForeignKey("payments_payment.id"))
    account: Mapped[str] = mapped_column(String)
    # Signed amount: + is a debit, - is a credit. Storing the sign (rather than
    # separate debit/credit columns) makes the double-entry invariant a one-line
    # check: the entries for a payment must sum to zero.
    amount: Mapped[Decimal] = mapped_column(Numeric)

    payment: Mapped[Payment] = relationship(back_populates="ledger_entries")
