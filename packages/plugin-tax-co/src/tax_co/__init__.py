"""Colombia tax plugin (CO / IVA). Implements the nucleus TaxCalculator contract
for jurisdiction "CO" and self-registers via the `nucleus.plugins` entry point.

The core resolves it from the registry; removing this package removes CO support
with zero core change — the demonstration the whole architecture exists to make
(BACKLOG B9). ColombiaTaxCalculator lands in B9.
"""
