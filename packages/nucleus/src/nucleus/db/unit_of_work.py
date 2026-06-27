"""The unit of work: the transaction boundary that makes module operations atomic.

A block runs and either *every* write inside it commits or none of them do. This
is the mechanism behind the project's headline property — an invoice's status
change and its ledger entries commit or roll back together (B12) — written once,
here, so every module inherits the same guarantee instead of hand-rolling
try/commit/rollback and getting it subtly wrong.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy.orm import Session, sessionmaker


@contextmanager
def unit_of_work(session_factory: sessionmaker[Session]) -> Iterator[Session]:
    """Yield a session whose work commits as one unit, or rolls back entirely."""
    session = session_factory()
    try:
        yield session
        session.commit()  # reached only if the block completed without raising
    except Exception:
        # Any error rolls back the *whole* unit — partial writes must never
        # persist, or the books are corrupt. Re-raise: the rollback is a side
        # effect; the error is still the caller's to see and handle.
        session.rollback()
        raise
    finally:
        session.close()
