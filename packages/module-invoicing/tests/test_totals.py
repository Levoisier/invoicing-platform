"""Proves BACKLOG B9 from the consumer's side: invoicing computes IVA through the
registry, and removing the plugin makes a CO invoice fail with a clear error.

These run in memory — no database needed — because the property is purely about
*resolution*: `compute_totals` reads the calculator from a registry by the client's
jurisdiction. The CO calculator is put there by real entry-point discovery, so
invoicing never imports `tax_co`. Hand it an empty registry (the plugin "removed")
and the same call fails cleanly — that's the zero-core-change add/remove guarantee.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from invoicing import Invoice, InvoiceLine, Party, compute_totals
from nucleus.plugins import discover_plugins
from nucleus.primitives import Money
from nucleus.registry import Registry, RegistryError


def _co_registry() -> Registry:
    registry: Registry = Registry(label="TaxCalculator", key_name="jurisdiction")
    discover_plugins(tax=registry)  # find and register the real CO plugin
    return registry


def _co_invoice() -> Invoice:
    party = Party(name="Acme S.A.S.", tax_id="900.123.456-7", jurisdiction="CO")
    # Transient objects: compute_totals only reads them, so no session is involved.
    return Invoice(
        party=party,
        currency="COP",
        number=1,
        lines=[
            InvoiceLine(description="Consulting", quantity=Decimal("10"),
                        unit_price=Decimal("100000"), tax_code="iva_19"),
            InvoiceLine(description="Reduced item", quantity=Decimal("1"),
                        unit_price=Decimal("200000"), tax_code="iva_5"),
            InvoiceLine(description="Excluded item", quantity=Decimal("1"),
                        unit_price=Decimal("50000"), tax_code="excluded"),
        ],
    )


def test_totals_computed_via_the_registry_plugin() -> None:
    totals = compute_totals(_co_invoice(), tax_registry=_co_registry())

    # net 1,000,000 + 200,000 + 50,000 = 1,250,000
    assert totals.subtotal == Money("1250000", "COP")
    # IVA 190,000 (19%) + 10,000 (5%) + 0 (excluded) = 200,000
    assert totals.tax == Money("200000", "COP")
    assert totals.total == Money("1450000", "COP")


def test_removing_the_plugin_fails_with_a_clear_error() -> None:
    empty: Registry = Registry(label="TaxCalculator", key_name="jurisdiction")
    with pytest.raises(
        RegistryError, match="no TaxCalculator registered for jurisdiction 'CO'"
    ):
        compute_totals(_co_invoice(), tax_registry=empty)
