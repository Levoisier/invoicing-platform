"""Session factory and the session-per-request seam.

A ``sessionmaker`` is the process-wide factory; each request (or unit of work)
gets its *own* ``Session``, because Sessions are not thread-safe and hold
identity/transaction state that must not be shared. The FastAPI dependency wraps
each request's session in a ``unit_of_work`` so one request == one transaction:
commit on a clean response, rollback on a raised error.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator

from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from nucleus.db.unit_of_work import unit_of_work


def make_session_factory(engine: Engine) -> sessionmaker[Session]:
    # expire_on_commit=False: a route typically serializes the just-written
    # objects into its response *after* commit. The default expires every
    # attribute on commit, forcing a reload — which then fails or re-queries once
    # the request's transaction is gone. Keeping attributes live avoids that.
    return sessionmaker(bind=engine, expire_on_commit=False)


def session_per_request(
    session_factory: sessionmaker[Session],
) -> Callable[[], Iterator[Session]]:
    """Build a FastAPI dependency that yields a request-scoped session inside a
    unit of work. The host mounts it in B10; it lives here so the request's
    transaction policy sits next to the session it governs."""

    def _dependency() -> Iterator[Session]:
        # FastAPI re-raises a route's exception back through this `yield`, so the
        # unit_of_work's except-branch sees it and rolls the request back.
        with unit_of_work(session_factory) as session:
            yield session

    return _dependency
