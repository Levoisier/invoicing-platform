"""The tax contract: what every jurisdiction plugin must implement.

This Protocol is the nucleus side of the project's headline seam. The core (and
``module-invoicing``) depend on *this abstraction*; a plugin like ``tax_co``
implements it and registers under its jurisdiction, and consumers resolve it from
the tax registry — never `import tax_co`. Keeping the contract here, in the core,
is what lets "add a country = install a package" hold with zero core changes.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from nucleus.primitives import Money


@runtime_checkable
class TaxCalculator(Protocol):
    """Computes the tax owed on one invoice line in a single jurisdiction."""

    # Self-describing: the calculator declares the jurisdiction it serves, so the
    # registry can index it under its own key during entry-point discovery (B9).
    jurisdiction: str

    def tax_for(self, net: Money, code: str) -> Money:
        """Tax owed on ``net`` for tax ``code`` (e.g. ``"iva_19"``), in net's
        currency. Unknown codes are the implementation's to reject."""
        ...
