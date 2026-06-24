from decimal import Decimal

import pytest

from nucleus.primitives import CurrencyMismatchError, Money


def test_cop_rounds_and_renders_with_zero_decimals() -> None:
    money = Money("1234.50", "cop")

    assert money.amount == Decimal("1235")
    assert money.currency == "COP"
    assert str(money) == "COP 1,235"


def test_two_decimal_currency_rounds_and_renders_with_cents() -> None:
    money = Money("10.235", "USD")

    assert money.amount == Decimal("10.24")
    assert str(money) == "USD 10.24"


def test_same_currency_arithmetic_preserves_currency_precision() -> None:
    total = Money("1000.20", "COP") + Money("10.20", "COP")

    assert total == Money("1010", "COP")


def test_cross_currency_arithmetic_raises() -> None:
    with pytest.raises(CurrencyMismatchError, match="cannot operate on COP and USD"):
        Money("1000", "COP") + Money("1.00", "USD")
