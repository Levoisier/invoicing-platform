"""A stand-in tax plugin, living in its *own* module on purpose.

It plays the role ``plugin-tax-co`` plays in production: a separate package that
implements the ``TaxCalculator`` contract and gets registered under a
jurisdiction. The registry test imports this only to *register* it — the
"consumer" code path under test never imports it, which is exactly the inversion
B4 must demonstrate.
"""

from __future__ import annotations

from decimal import Decimal

from nucleus.primitives import Money

_RATES = {"vat_10": Decimal("0.10"), "exempt": Decimal("0")}


class RegionXTaxCalculator:
    """Made-up jurisdiction "ZX" — deliberately not CO, to keep this a generic
    stand-in and avoid implying it's the real Colombia plugin."""

    jurisdiction = "ZX"

    def tax_for(self, net: Money, code: str) -> Money:
        try:
            rate = _RATES[code]
        except KeyError as exc:
            raise ValueError(f"unknown tax code: {code}") from exc
        return net * rate
