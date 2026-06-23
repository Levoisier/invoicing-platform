"""Registries (model / route / event / tax / payment): the lookup tables that
invert dependencies. A consumer asks the registry for a TaxCalculator by
jurisdiction instead of importing a plugin — the seam that makes "add a country =
install a package" true (BACKLOG B4).
"""
