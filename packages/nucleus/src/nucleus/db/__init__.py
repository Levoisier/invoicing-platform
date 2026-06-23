"""DB & transaction layer: engine, session-per-request, declarative base, and the
unit-of-work that makes module operations atomic. The "transactional intimacy" that
lets invoice status and ledger entries commit or roll back as one (BACKLOG B3).
"""
