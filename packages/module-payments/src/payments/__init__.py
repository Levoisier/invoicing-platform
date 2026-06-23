"""Payments module: Payment + LedgerEntry, and invoice-status transitions posted
atomically with ledger entries in the *same* transaction. The module that proves
transactional intimacy (BACKLOG B12).
"""
