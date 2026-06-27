"""DB & transaction layer: engine, session-per-request, declarative base, and the
unit-of-work that makes module operations atomic. The "transactional intimacy" that
lets invoice status and ledger entries commit or roll back as one (BACKLOG B3).
"""

from nucleus.db.base import Base
from nucleus.db.engine import make_engine
from nucleus.db.session import make_session_factory, session_per_request
from nucleus.db.unit_of_work import unit_of_work

__all__ = [
    "Base",
    "make_engine",
    "make_session_factory",
    "session_per_request",
    "unit_of_work",
]
