"""Invoicing module: Party, Invoice, InvoiceLine, gapless numbering, and PDF
output. Attaches to the nucleus and shares its DB transaction. Computes tax through
the registry-resolved TaxCalculator — never by importing a jurisdiction plugin
(BACKLOG B8).
"""

from invoicing.manifest import manifest
from invoicing.models import Invoice, InvoiceLine, InvoiceStatus, Party
from invoicing.service import LineInput, issue_invoice

__all__ = [
    "Invoice",
    "InvoiceLine",
    "InvoiceStatus",
    "LineInput",
    "Party",
    "issue_invoice",
    "manifest",
]
