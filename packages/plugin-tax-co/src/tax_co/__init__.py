"""Colombia tax plugin (CO / IVA). Implements the nucleus TaxCalculator contract
for jurisdiction "CO" and self-registers via the `nucleus.plugins` entry point.

The core resolves it from the registry; removing this package removes CO support
with zero core change — the demonstration the whole architecture exists to make
(BACKLOG B9).

This is also the reference plugin for `docs/plugin-sdk.md`: a whole jurisdiction in
a few lines. Note the only nucleus import is `Money` — the calculator satisfies the
`TaxCalculator` contract *structurally*, so it never imports the core's interface,
and the core never imports this. The dependency points one way only.
"""

from __future__ import annotations

from decimal import Decimal

from nucleus.primitives import Money

# IVA rates verified against current DIAN rules (June 2026): general 19%, reduced
# 5%, and exempt/excluded at 0% — Estatuto Tributario arts. 420–513. The codes are
# rate *buckets*, not product classifications: deciding which good is 5% vs 19% is
# the user's call when they pick a line's tax_code. v1 also folds "excluded" and
# "exempt" together (both 0% output tax; they differ on input-tax credit, which is
# out of scope here).
_RATES: dict[str, Decimal] = {
    "iva_19": Decimal("0.19"),
    "iva_5": Decimal("0.05"),
    "excluded": Decimal("0"),
}


class ColombiaTaxCalculator:
    """Computes Colombian IVA for an invoice line."""

    jurisdiction = "CO"

    def tax_for(self, net: Money, code: str) -> Money:
        try:
            rate = _RATES[code]
        except KeyError as exc:
            # A bad code is a caller error, surfaced clearly rather than silently
            # taxed at 0 — a silent 0 would under-bill and corrupt the books.
            raise ValueError(
                f"unknown CO tax code {code!r}; expected one of {sorted(_RATES)}"
            ) from exc
        # Money carries the currency and rounds to its precision (COP → 0 decimals).
        return net * rate
