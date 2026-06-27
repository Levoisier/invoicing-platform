"""Proves BACKLOG B4: a calculator registers under a jurisdiction and is resolved
from the registry with no direct import by the consumer.

The whole thesis lives here. ``compute_line_tax`` is the *consumer* — it stands in
for ``module-invoicing``. Read its body: it imports no calculator, names no
concrete class. It is handed a registry and a jurisdiction string and resolves the
implementation at runtime. That is dependency inversion, and removing the only
registered calculator turns a ``ZX`` request into a clear, specific error — the
seed of B9's "remove the plugin, CO fails cleanly" property.
"""

from __future__ import annotations

import pytest
from _fake_tax_plugin import RegionXTaxCalculator

from nucleus.contracts import TaxCalculator
from nucleus.primitives import Money
from nucleus.registry import Registry, RegistryError
from nucleus.registry import tax as tax_registry


def compute_line_tax(
    registry: Registry[str, TaxCalculator], jurisdiction: str, net: Money, code: str
) -> Money:
    """The consumer. Note what it does NOT do: import a plugin or mention any
    concrete calculator. It only knows the contract and the registry."""
    return registry.get(jurisdiction).tax_for(net, code)


def _fresh_registry() -> Registry[str, TaxCalculator]:
    return Registry(label="TaxCalculator", key_name="jurisdiction")


def test_resolved_from_registry_without_importing_the_implementation() -> None:
    registry = _fresh_registry()
    calc = RegionXTaxCalculator()
    registry.register(calc.jurisdiction, calc)  # the plugin self-describes its key

    tax = compute_line_tax(registry, "ZX", Money("1000", "COP"), "vat_10")

    assert tax == Money("100", "COP")


def test_registered_calculator_satisfies_the_contract() -> None:
    # runtime_checkable Protocol: the stub never inherits TaxCalculator, yet it
    # *is* one structurally. Structural typing is what lets an external plugin
    # satisfy the contract without importing the core's class.
    assert isinstance(RegionXTaxCalculator(), TaxCalculator)


def test_missing_jurisdiction_raises_a_clear_error() -> None:
    registry = _fresh_registry()
    with pytest.raises(RegistryError, match="no TaxCalculator registered for jurisdiction 'CO'"):
        compute_line_tax(registry, "CO", Money("1000", "COP"), "iva_19")


def test_duplicate_registration_is_refused() -> None:
    registry = _fresh_registry()
    registry.register("ZX", RegionXTaxCalculator())
    with pytest.raises(RegistryError, match="already registered for jurisdiction 'ZX'"):
        registry.register("ZX", RegionXTaxCalculator())


def test_replace_is_the_explicit_escape_hatch() -> None:
    registry = _fresh_registry()
    first, second = RegionXTaxCalculator(), RegionXTaxCalculator()
    registry.register("ZX", first)
    registry.register("ZX", second, replace=True)
    assert registry.get("ZX") is second


def test_contains_and_keys_reflect_registrations() -> None:
    registry = _fresh_registry()
    assert "ZX" not in registry
    registry.register("ZX", RegionXTaxCalculator())
    assert "ZX" in registry
    assert registry.keys() == ("ZX",)


def test_module_level_tax_singleton_is_the_real_seam() -> None:
    # The shared `nucleus.registry.tax` is what the host/plugins actually use.
    # Clear after so we don't leak state into other tests (the cost of a singleton).
    try:
        tax_registry.register("ZX", RegionXTaxCalculator())
        assert compute_line_tax(tax_registry, "ZX", Money("500", "COP"), "vat_10") == Money(
            "50", "COP"
        )
    finally:
        tax_registry.clear()
