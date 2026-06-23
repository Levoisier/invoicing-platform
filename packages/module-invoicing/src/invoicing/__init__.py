"""Invoicing module: Party, Invoice, InvoiceLine, gapless numbering, and PDF
output. Attaches to the nucleus and shares its DB transaction. Computes tax through
the registry-resolved TaxCalculator — never by importing a jurisdiction plugin
(BACKLOG B8).
"""
