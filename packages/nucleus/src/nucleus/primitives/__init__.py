"""Domain primitives with no infrastructure: Money (per-currency precision),
Sequence (gapless numbering), Party. Pure value/behaviour the rest of the core and
every module build on. Implemented across BACKLOG B1–B2.
"""

from nucleus.primitives.money import CurrencyMismatchError, Money

__all__ = ["CurrencyMismatchError", "Money"]
