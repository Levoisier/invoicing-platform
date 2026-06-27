"""Engine factory.

The nucleus builds the engine from a DSN it is *handed*; it never reads the
environment itself — config is the host's job (apps/api settings), so the core
stays a library, not an app. One engine per process: it owns the connection pool
every session draws from.
"""

from __future__ import annotations

from sqlalchemy import Engine
from sqlalchemy import create_engine as _sa_create_engine


def make_engine(url: str, *, echo: bool = False) -> Engine:
    # pool_pre_ping: a pooled connection can be silently killed by the DB or a
    # network blip while idle. Pre-ping validates it on checkout, so a request
    # gets a fresh connection instead of a "server closed the connection"
    # error — cheap insurance for a long-lived API process.
    return _sa_create_engine(url, echo=echo, pool_pre_ping=True)
