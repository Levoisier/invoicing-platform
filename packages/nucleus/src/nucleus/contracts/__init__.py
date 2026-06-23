"""Nucleus contracts: the Protocols plugins implement (TaxCalculator,
PaymentProvider, Exporter). The core depends on these abstractions; concrete
implementations live in plugins and are resolved via the registry, never imported
(BACKLOG B4).
"""
