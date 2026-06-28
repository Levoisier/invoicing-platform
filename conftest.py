"""Workspace-wide pytest fixtures, loaded from the repo root so every package's
tests share them (nucleus, module-invoicing, …).

The DB-backed properties (gapless numbering, atomicity, persistence) can only be
proven against real Postgres — the row-lock semantics that make them true don't
exist in SQLite. So these fixtures point at a live Postgres and *skip* cleanly
when one isn't reachable, rather than silently testing weaker semantics.

Point the suite at a database with ``DATABASE_URL``; the default matches the
docker-compose Postgres (``make up``).
"""

from __future__ import annotations

import os

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError

_DEFAULT_DSN = "postgresql+psycopg://invoicing:invoicing@localhost:5432/invoicing"


@pytest.fixture(scope="session")
def pg_engine() -> Engine:
    """A live Postgres engine, or skip the whole DB-backed test if none is up."""
    engine = create_engine(os.environ.get("DATABASE_URL", _DEFAULT_DSN))
    try:
        with engine.connect() as conn:
            conn.execute(text("select 1"))
    except OperationalError as exc:
        pytest.skip(f"Postgres not reachable ({exc.__class__.__name__}); set DATABASE_URL")
    return engine
