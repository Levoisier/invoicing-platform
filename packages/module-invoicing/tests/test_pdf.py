"""Proves BACKLOG B11: a valid PDF renders for a CO invoice, showing line items, the
IVA breakdown, totals, the client NIT, and COP at 0 decimals.

No database needed: the renderer works on an in-memory invoice. We read the PDF
back with pypdf and assert the required facts appear in the extracted text, so the
test proves the *content* is real, not just that some bytes came out.
"""

from __future__ import annotations

from decimal import Decimal
from io import BytesIO

from pypdf import PdfReader

from invoicing import Invoice, InvoiceLine, Party
from invoicing.pdf import render_invoice_pdf
from nucleus.plugins import discover_plugins
from nucleus.registry import Registry


def _co_registry() -> Registry:
    registry: Registry = Registry(label="TaxCalculator", key_name="jurisdiction")
    discover_plugins(tax=registry)
    return registry


def _co_invoice() -> Invoice:
    party = Party(
        name="Acme S.A.S.", tax_id="900.123.456-7", jurisdiction="CO", address="Calle 1 # 2-3"
    )
    return Invoice(
        party=party,
        currency="COP",
        number=7,
        lines=[
            InvoiceLine(description="Consulting", quantity=Decimal("10"),
                        unit_price=Decimal("100000"), tax_code="iva_19"),
            InvoiceLine(description="Excluded item", quantity=Decimal("1"),
                        unit_price=Decimal("50000"), tax_code="excluded"),
        ],
    )


def _text(pdf: bytes) -> str:
    return "\n".join(page.extract_text() for page in PdfReader(BytesIO(pdf)).pages)


def test_renders_a_valid_pdf() -> None:
    pdf = render_invoice_pdf(_co_invoice(), tax_registry=_co_registry())
    assert pdf[:5] == b"%PDF-"  # a real PDF, not an error page
    assert len(pdf) > 1000


def test_pdf_shows_the_required_invoice_facts() -> None:
    text = _text(render_invoice_pdf(_co_invoice(), tax_registry=_co_registry()))

    assert "Invoice #7" in text
    assert "900.123.456-7" in text  # client NIT
    assert "Consulting" in text  # a line item
    assert "iva_19" in text and "excluded" in text  # IVA breakdown by code
    # COP at 0 decimals (no cents): subtotal 1,050,000, IVA 190,000, total 1,240,000.
    assert "COP 1,050,000" in text
    assert "COP 190,000" in text
    assert "COP 1,240,000" in text
    assert ".00" not in text  # never any 2-decimal money on a COP invoice
