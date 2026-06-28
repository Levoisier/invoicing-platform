"""HTTP surface for payments: record a payment against an invoice.

Mounted by the host (manifest register hook → route registry → bootstrap). Like the
invoicing router, it declares the nucleus seams and holds no host config. Recording
a payment returns the resulting invoice status alongside the posted ledger, so a
client sees the atomic outcome in one response.
"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from invoicing import Invoice
from nucleus.api import get_principal, get_session
from nucleus.primitives import Money
from payments.service import record_payment

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

router = APIRouter(tags=["payments"])


class PaymentIn(BaseModel):
    amount: Decimal
    currency: str


class LedgerEntryOut(BaseModel):
    account: str
    amount: Decimal


class PaymentOut(BaseModel):
    id: int
    invoice_id: int
    amount: Decimal
    currency: str
    invoice_status: str
    ledger: list[LedgerEntryOut]


@router.post(
    "/invoices/{invoice_id}/payments",
    response_model=PaymentOut,
    status_code=status.HTTP_201_CREATED,
)
def create_payment(
    invoice_id: int,
    body: PaymentIn,
    session: Session = Depends(get_session),
    _principal: object = Depends(get_principal),
) -> PaymentOut:
    invoice = session.get(Invoice, invoice_id)
    if invoice is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"invoice {invoice_id} not found")
    try:
        payment = record_payment(session, invoice=invoice, amount=Money(body.amount, body.currency))
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    return PaymentOut(
        id=payment.id,
        invoice_id=payment.invoice_id,
        amount=payment.amount,
        currency=payment.currency,
        invoice_status=invoice.status.value,
        ledger=[LedgerEntryOut(account=e.account, amount=e.amount) for e in payment.ledger_entries],
    )
