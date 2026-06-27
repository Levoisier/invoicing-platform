"""The payment-provider contract: the seam for how a payment is captured.

v1 records payments manually (README §5), so this contract has no concrete
implementation yet — it exists to mark the inversion point so a real gateway
(`plugin-payment-*`, a future item) can drop in the same way `tax_co` does for
tax: implement the Protocol, register under a key, get resolved from the payment
registry. Defined alongside ``TaxCalculator`` so both seams live in one place.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from nucleus.primitives import Money


@runtime_checkable
class PaymentProvider(Protocol):
    """Captures a payment through some provider and returns its reference."""

    # The key this provider registers under (e.g. "manual", "stripe").
    key: str

    def charge(self, amount: Money, reference: str) -> str:
        """Capture ``amount`` against ``reference``; return the provider's
        payment id. v1's manual provider just echoes a reference back."""
        ...
