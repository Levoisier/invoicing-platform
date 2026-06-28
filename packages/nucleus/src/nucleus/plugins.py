"""Plugin discovery: load self-registering plugins and place them in registries.

This is the *only* code in the system that knows plugins exist as installed
packages. It reads the ``nucleus.plugins`` entry-point group, instantiates each
advertised class, and routes it into the right registry by the contract it
satisfies. Everything else asks the registry by key and never imports a plugin.

That's the inversion the whole project is built to demonstrate: adding a
jurisdiction is "pip install a package that advertises this entry point"; the host
calls ``discover_plugins()`` once at boot (B10) and not one line of core code
changes. Removing the package removes the jurisdiction just as cleanly — a request
for it then fails with the registry's clear "no TaxCalculator registered" error.
"""

from __future__ import annotations

from importlib.metadata import entry_points

from nucleus.contracts import TaxCalculator
from nucleus.registry import Registry
from nucleus.registry import tax as _tax_registry

PLUGIN_GROUP = "nucleus.plugins"


def discover_plugins(
    *,
    group: str = PLUGIN_GROUP,
    tax: Registry[str, TaxCalculator] = _tax_registry,
    replace: bool = False,
) -> list[str]:
    """Discover and register every plugin in ``group``. Returns the keys
    registered, for the boot log. Registries default to the shared singletons; a
    test can pass fresh ones to discover in isolation."""
    registered: list[str] = []
    for ep in entry_points(group=group):
        # The entry point names a class; instantiate it to get the plugin object.
        plugin = ep.load()()
        # Route by contract, not by entry-point name: a plugin is whatever contract
        # it structurally satisfies. (runtime_checkable Protocols make this work
        # without the plugin importing or inheriting the contract.)
        if isinstance(plugin, TaxCalculator):
            tax.register(plugin.jurisdiction, plugin, replace=replace)
            registered.append(plugin.jurisdiction)
    return registered
