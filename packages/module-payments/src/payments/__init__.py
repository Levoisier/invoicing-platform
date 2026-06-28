"""Payments module: Payment + LedgerEntry, and invoice-status transitions posted
atomically with ledger entries in the *same* transaction. The module that proves
transactional intimacy (BACKLOG B12).
"""

from payments.manifest import manifest
from payments.models import LedgerEntry, Payment
from payments.service import record_payment

__all__ = ["LedgerEntry", "Payment", "manifest", "record_payment"]
