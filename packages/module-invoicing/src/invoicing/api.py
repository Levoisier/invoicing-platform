"""HTTP surface for the invoicing module: create clients and invoices.

The router is defined here but *mounted by the host* (the manifest's register hook
puts it in the route registry; bootstrap includes it). It depends on the nucleus
seams ``get_session``/``get_principal``, which the host overrides — so this module
holds no engine, no auth secret, and no knowledge of the host. Tax is applied via
``compute_totals``, which resolves the calculator from the registry: this file
never imports ``tax_co``.
"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from invoicing.models import Invoice, Party
from invoicing.service import LineInput, compute_totals, issue_invoice
from nucleus.api import get_principal, get_session
from nucleus.registry import RegistryError

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from invoicing.service import InvoiceTotals
    from nucleus.primitives import Money

router = APIRouter(tags=["invoicing"])


class ClientIn(BaseModel):
    name: str
    tax_id: str
    jurisdiction: str
    address: str | None = None


class ClientOut(BaseModel):
    id: int
    name: str
    tax_id: str
    jurisdiction: str
    address: str | None


class LineIn(BaseModel):
    description: str
    quantity: Decimal
    unit_price: Decimal
    tax_code: str


class InvoiceIn(BaseModel):
    client_id: int
    currency: str
    lines: list[LineIn]


class MoneyOut(BaseModel):
    # amount as a string: preserves Decimal precision and the currency's decimal
    # places (COP → "1450000") without JSON float rounding.
    amount: str
    currency: str


class LineOut(BaseModel):
    description: str
    quantity: Decimal
    unit_price: Decimal
    tax_code: str
    net: MoneyOut


class InvoiceOut(BaseModel):
    id: int
    number: int
    status: str
    client_id: int
    currency: str
    lines: list[LineOut]
    subtotal: MoneyOut
    tax: MoneyOut
    total: MoneyOut


def _money_out(money: Money) -> MoneyOut:
    return MoneyOut(amount=str(money.amount), currency=money.currency)


def _invoice_out(invoice: Invoice, totals: InvoiceTotals) -> InvoiceOut:
    return InvoiceOut(
        id=invoice.id,
        number=invoice.number,
        status=invoice.status.value,
        client_id=invoice.party_id,
        currency=invoice.currency,
        lines=[
            LineOut(
                description=line.description,
                quantity=line.quantity,
                unit_price=line.unit_price,
                tax_code=line.tax_code,
                net=_money_out(line.net()),
            )
            for line in invoice.lines
        ],
        subtotal=_money_out(totals.subtotal),
        tax=_money_out(totals.tax),
        total=_money_out(totals.total),
    )


@router.post("/clients", response_model=ClientOut, status_code=status.HTTP_201_CREATED)
def create_client(
    body: ClientIn,
    session: Session = Depends(get_session),
    _principal: object = Depends(get_principal),
) -> ClientOut:
    party = Party(
        name=body.name, tax_id=body.tax_id, jurisdiction=body.jurisdiction, address=body.address
    )
    session.add(party)
    session.flush()  # assign the id within the request's transaction
    return ClientOut(
        id=party.id,
        name=party.name,
        tax_id=party.tax_id,
        jurisdiction=party.jurisdiction,
        address=party.address,
    )


@router.post("/invoices", response_model=InvoiceOut, status_code=status.HTTP_201_CREATED)
def create_invoice(
    body: InvoiceIn,
    session: Session = Depends(get_session),
    _principal: object = Depends(get_principal),
) -> InvoiceOut:
    party = session.get(Party, body.client_id)
    if party is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"client {body.client_id} not found")
    invoice = issue_invoice(
        session,
        party=party,
        currency=body.currency,
        lines=[
            LineInput(li.description, li.quantity, li.unit_price, li.tax_code) for li in body.lines
        ],
    )
    try:
        totals = compute_totals(invoice)
    except RegistryError as exc:
        # No tax plugin for this jurisdiction: a 400 with the registry's clear
        # message, not an opaque 500 — the request is unserviceable as composed.
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    return _invoice_out(invoice, totals)


@router.get("/invoices/{invoice_id}", response_model=InvoiceOut)
def get_invoice(
    invoice_id: int,
    session: Session = Depends(get_session),
    _principal: object = Depends(get_principal),
) -> InvoiceOut:
    invoice = session.get(Invoice, invoice_id)
    if invoice is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"invoice {invoice_id} not found")
    return _invoice_out(invoice, compute_totals(invoice))
