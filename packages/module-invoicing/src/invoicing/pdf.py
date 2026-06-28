"""Render an invoice to a PDF: the project's tangible artifact (B11).

The path is invoice → HTML/CSS → PDF via WeasyPrint, chosen because the README's
stack picks it and the document is fundamentally a styled page — HTML/CSS is the
right authoring language for it, far more maintainable than drawing boxes in code.
WeasyPrint's native deps (Pango/cairo) are present in our image, so no fallback is
needed (the README sanctioned ReportLab/headless-Chromium if they fought us).

Money is rendered through ``Money.__str__``, so COP shows with 0 decimals — getting
that right on the visible artifact is the whole point of the per-currency primitive.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from jinja2 import Template
from weasyprint import HTML

from invoicing.service import compute_totals, tax_breakdown

if TYPE_CHECKING:
    from invoicing.models import Invoice
    from nucleus.contracts import TaxCalculator
    from nucleus.registry import Registry

# Inline template (not a packaged file) to avoid wheel-data packaging concerns for a
# single document. autoescape on: line descriptions and client names are user data.
_TEMPLATE = Template(
    """
<!doctype html>
<html><head><meta charset="utf-8"><style>
  @page { size: A4; margin: 2cm; }
  body { font-family: sans-serif; color: #222; font-size: 11px; }
  h1 { font-size: 22px; margin: 0; }
  .muted { color: #666; }
  table { width: 100%; border-collapse: collapse; margin-top: 12px; }
  th, td { text-align: left; padding: 6px 8px; border-bottom: 1px solid #ddd; }
  td.num, th.num { text-align: right; }
  .totals { margin-top: 16px; width: 50%; margin-left: auto; }
  .totals td { border: none; padding: 3px 8px; }
  .grand { font-weight: bold; font-size: 13px; border-top: 2px solid #333; }
</style></head><body>
  <h1>Invoice #{{ invoice.number }}</h1>
  <p class="muted">Status: {{ invoice.status.value }} &middot; Currency: {{ invoice.currency }}</p>

  <p><strong>Bill to:</strong> {{ party.name }}<br>
     NIT/C&eacute;dula: {{ party.tax_id }}<br>
     {% if party.address %}{{ party.address }}<br>{% endif %}
     Jurisdiction: {{ party.jurisdiction }}</p>

  <table>
    <thead><tr>
      <th>Description</th><th class="num">Qty</th><th class="num">Unit price</th>
      <th>Tax</th><th class="num">Net</th>
    </tr></thead>
    <tbody>
      {% for line in invoice.lines %}
      <tr>
        <td>{{ line.description }}</td>
        <td class="num">{{ line.quantity }}</td>
        <td class="num">{{ line.unit_price }}</td>
        <td>{{ line.tax_code }}</td>
        <td class="num">{{ line.net() }}</td>
      </tr>
      {% endfor %}
    </tbody>
  </table>

  <table class="totals">
    <tr><td>Subtotal</td><td class="num">{{ totals.subtotal }}</td></tr>
    {% for bucket in breakdown %}
    <tr><td>IVA ({{ bucket.code }}) on {{ bucket.base }}</td>
        <td class="num">{{ bucket.tax }}</td></tr>
    {% endfor %}
    <tr class="grand"><td>Total</td><td class="num">{{ totals.total }}</td></tr>
  </table>
</body></html>
"""
)


def render_invoice_pdf(
    invoice: Invoice, *, tax_registry: Registry[str, TaxCalculator] | None = None
) -> bytes:
    """Render ``invoice`` to PDF bytes, with line items, the IVA breakdown, totals,
    and the client NIT. Tax is resolved via the registry (default: the shared one)."""
    kwargs = {} if tax_registry is None else {"tax_registry": tax_registry}
    html = _TEMPLATE.render(
        invoice=invoice,
        party=invoice.party,
        totals=compute_totals(invoice, **kwargs),
        breakdown=tax_breakdown(invoice, **kwargs),
    )
    return HTML(string=html).write_pdf()
