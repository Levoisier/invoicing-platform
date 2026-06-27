"""Registries (model / route / event / tax / payment): the lookup tables that
invert dependencies. A consumer asks the registry for a TaxCalculator by
jurisdiction instead of importing a plugin — the seam that makes "add a country =
install a package" true (BACKLOG B4).
"""

from nucleus.contracts import PaymentProvider, TaxCalculator
from nucleus.registry.registry import Registry, RegistryError

# Module-level registries: the shared lookup tables the host and plugins write
# into once, at boot. Singletons because registration is global, one-time wiring
# (entry-point discovery in B9) and every consumer must read the same table.
tax: Registry[str, TaxCalculator] = Registry(label="TaxCalculator", key_name="jurisdiction")
payment: Registry[str, PaymentProvider] = Registry(label="PaymentProvider", key_name="key")

# Filled by later items: the module loader/host register models and routers
# (B5/B10). There is deliberately no plain `event` registry — event pub/sub is the
# event bus's job (B6), which is a different shape (one event → many subscribers).
model: Registry[str, object] = Registry(label="model", key_name="name")
route: Registry[str, object] = Registry(label="router", key_name="name")

__all__ = [
    "PaymentProvider",
    "Registry",
    "RegistryError",
    "TaxCalculator",
    "model",
    "payment",
    "route",
    "tax",
]
