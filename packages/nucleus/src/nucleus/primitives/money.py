"""Money value object with currency-specific precision.

The primitive lives in the nucleus because every module that handles prices,
taxes, invoices, or payments needs the same rounding and currency-mixing rules.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Self

MoneyInput = Decimal | int | str


class CurrencyMismatchError(ValueError):
    """Raised when arithmetic would silently mix two different currencies."""


_CURRENCY_DECIMALS: dict[str, int] = {
    "COP": 0,
    "USD": 2,
    "EUR": 2,
}


@dataclass(frozen=True, slots=True)
class Money:
    """A rounded amount in one currency."""

    amount: Decimal | int | str
    currency: str

    def __post_init__(self) -> None:
        currency = self.currency.upper()
        object.__setattr__(self, "currency", currency)
        object.__setattr__(self, "amount", _quantize(_to_decimal(self.amount), currency))

    def __add__(self, other: Self) -> Self:
        self._require_same_currency(other)
        return type(self)(self.amount + other.amount, self.currency)

    def __sub__(self, other: Self) -> Self:
        self._require_same_currency(other)
        return type(self)(self.amount - other.amount, self.currency)

    def __mul__(self, multiplier: Decimal | int | str) -> Self:
        return type(self)(self.amount * _to_decimal(multiplier), self.currency)

    def __rmul__(self, multiplier: Decimal | int | str) -> Self:
        return self * multiplier

    def __str__(self) -> str:
        decimals = _currency_decimals(self.currency)
        return f"{self.currency} {self.amount:,.{decimals}f}"

    def _require_same_currency(self, other: Self) -> None:
        # Raising at the arithmetic boundary makes currency bugs loud before they
        # can leak into totals, ledger entries, or PDFs.
        if self.currency != other.currency:
            msg = f"cannot operate on {self.currency} and {other.currency}"
            raise CurrencyMismatchError(msg)


def _to_decimal(value: MoneyInput) -> Decimal:
    return value if isinstance(value, Decimal) else Decimal(str(value))


def _quantize(amount: Decimal, currency: str) -> Decimal:
    decimals = _currency_decimals(currency)
    quantum = Decimal(1).scaleb(-decimals)
    # HALF_UP matches invoice-style rounding better than Decimal's default
    # half-even, which is useful for statistics but surprising on receipts.
    return amount.quantize(quantum, rounding=ROUND_HALF_UP)


def _currency_decimals(currency: str) -> int:
    try:
        return _CURRENCY_DECIMALS[currency]
    except KeyError as exc:
        msg = f"unsupported currency: {currency}"
        raise ValueError(msg) from exc
