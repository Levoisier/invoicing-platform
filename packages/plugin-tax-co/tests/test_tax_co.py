"""Proves the CO plugin computes correct IVA and self-registers via its entry point.

Rates are checked against DIAN (general 19%, reduced 5%, excluded 0%). The
discovery test is the load-bearing one: it runs the *real* entry-point mechanism
and shows the calculator lands in a registry under "CO" — no manual wiring, no core
edit. (The "remove the plugin → CO fails" half lives in module-invoicing's totals
test, where the consumer is.)
"""

from __future__ import annotations

import pytest

from nucleus.contracts import TaxCalculator
from nucleus.plugins import discover_plugins
from nucleus.primitives import Money
from nucleus.registry import Registry
from tax_co import ColombiaTaxCalculator


@pytest.mark.parametrize(
    ("code", "expected"),
    [("iva_19", "190000"), ("iva_5", "50000"), ("excluded", "0")],
)
def test_iva_rate_per_code(code: str, expected: str) -> None:
    tax = ColombiaTaxCalculator().tax_for(Money("1000000", "COP"), code)
    assert tax == Money(expected, "COP")


def test_unknown_code_raises_rather_than_taxing_zero() -> None:
    with pytest.raises(ValueError, match="unknown CO tax code 'iva_99'"):
        ColombiaTaxCalculator().tax_for(Money("1000", "COP"), "iva_99")


def test_calculator_satisfies_the_contract() -> None:
    # Structural: it never inherits TaxCalculator, yet it is one.
    assert isinstance(ColombiaTaxCalculator(), TaxCalculator)


def test_self_registers_via_entry_point() -> None:
    # The real mechanism: discovery reads the installed `nucleus.plugins` entry
    # points and registers CO with zero manual wiring.
    registry: Registry[str, TaxCalculator] = Registry(
        label="TaxCalculator", key_name="jurisdiction"
    )
    registered = discover_plugins(tax=registry)

    assert "CO" in registered
    assert isinstance(registry.get("CO"), ColombiaTaxCalculator)
