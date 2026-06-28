"""Invoicing domain entities: Party, Invoice, InvoiceLine.

These inherit the nucleus declarative ``Base``, so they share the one metadata and
participate in the same transactions as every other module — the structural basis
for "invoice status + ledger commit together" (B12). Money is reconstructed from
stored ``Numeric`` amounts plus the invoice's currency, so the value object's
rounding rules apply wherever totals are computed, not just at the edges.

Tax is intentionally absent here: a line carries a ``tax_code`` string, but what
19% *means* is the CO plugin's job, resolved via the registry in B9. This module
never knows a jurisdiction's rates.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import Enum, ForeignKey, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from nucleus.db import Base
from nucleus.primitives import Money


class InvoiceStatus(StrEnum):
    """The lifecycle states from README §5. Transitions past ISSUED are posted
    atomically with ledger entries by the payments module (B12)."""

    DRAFT = "draft"
    ISSUED = "issued"
    PARTIAL = "partial"
    PAID = "paid"


class Party(Base):
    """A client. In v1 single-user, parties are the people you invoice."""

    __tablename__ = "invoicing_party"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String)
    # NIT / Cédula. Free text — format validation is minimal in v1 (README §4).
    tax_id: Mapped[str] = mapped_column(String)
    # The jurisdiction that selects the tax plugin (e.g. "CO"). This string is the
    # key the invoicing service hands the registry to resolve a TaxCalculator (B9).
    jurisdiction: Mapped[str] = mapped_column(String)
    address: Mapped[str | None] = mapped_column(String, default=None)


class Invoice(Base):
    __tablename__ = "invoicing_invoice"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Gapless sequential number from the Sequence primitive, assigned at issue.
    # UNIQUE is the belt to the row-lock's braces: even a numbering bug can't land
    # two invoices on the same number.
    number: Mapped[int] = mapped_column(unique=True)
    party_id: Mapped[int] = mapped_column(ForeignKey("invoicing_party.id"))
    # One currency per invoice; every line's Money is denominated in it. Mixing is
    # impossible by construction, not by checking.
    currency: Mapped[str] = mapped_column(String)
    # native_enum=False → a VARCHAR + CHECK, so the constraint lives with the table
    # (no separate PG enum type to migrate or drop).
    status: Mapped[InvoiceStatus] = mapped_column(
        Enum(InvoiceStatus, native_enum=False, length=16), default=InvoiceStatus.ISSUED
    )
    issued_at: Mapped[datetime] = mapped_column(server_default=func.now())

    party: Mapped[Party] = relationship()
    lines: Mapped[list[InvoiceLine]] = relationship(
        back_populates="invoice", cascade="all, delete-orphan"
    )

    def subtotal(self) -> Money:
        """Net of tax: the sum of line nets. IVA and grand total arrive in B9 once
        the tax calculator is resolved from the registry."""
        total = Money(0, self.currency)
        for line in self.lines:
            total = total + line.net()
        return total


class InvoiceLine(Base):
    __tablename__ = "invoicing_invoice_line"

    id: Mapped[int] = mapped_column(primary_key=True)
    invoice_id: Mapped[int] = mapped_column(ForeignKey("invoicing_invoice.id"))
    description: Mapped[str] = mapped_column(String)
    quantity: Mapped[Decimal] = mapped_column(Numeric)
    unit_price: Mapped[Decimal] = mapped_column(Numeric)
    # e.g. "iva_19" — opaque here, interpreted by the jurisdiction's plugin (B9).
    tax_code: Mapped[str] = mapped_column(String)

    invoice: Mapped[Invoice] = relationship(back_populates="lines")

    def net(self) -> Money:
        """Line amount before tax. Money rounds to the currency's precision."""
        return Money(self.quantity * self.unit_price, self.invoice.currency)
