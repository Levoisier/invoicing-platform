"""Gapless sequential numbering, backed by a Postgres row lock.

Invoice numbers (and, by law in many jurisdictions including Colombia's DIAN)
must be **gapless**: 1, 2, 3, … with no holes and no duplicates, even when
several API workers issue invoices at the same instant. A Postgres native
``SEQUENCE`` is the obvious tool and the wrong one here — it caches values and
deliberately does *not* roll back on a failed transaction, so it leaves gaps.

So we keep a counter *row* per named sequence and hand out the next value under a
``SELECT … FOR UPDATE`` row lock. The lock lives in the database, not in any one
process, which is what lets it serialize callers across multiple workers. We pay
in throughput (issuing a number is serialized per key) and buy gaplessness — the
right trade for a legal numbering requirement.

This primitive owns only its counter table; it takes a SQLAlchemy ``Session``
and never opens its own. The transaction boundary belongs to the caller, which is
exactly what makes gaplessness real: if the caller's transaction rolls back, the
increment rolls back with it and the number is reused, never skipped.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Column, MetaData, String, Table, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

if TYPE_CHECKING:
    from sqlalchemy import Connection, Engine
    from sqlalchemy.orm import Session

# A private MetaData, not the nucleus declarative base (that arrives in B3). Keeping
# the counter table self-contained lets B2 stand alone; B3/B8 can later fold this
# into the unified metadata and Alembic migrations without changing the contract.
metadata = MetaData()

sequences = Table(
    "sequences",
    metadata,
    Column("key", String, primary_key=True),
    # BigInteger: invoice counters are cheap to bump and expensive to overflow;
    # a 32-bit ceiling is a foot-gun a long-lived tenant could actually hit.
    Column("value", BigInteger, nullable=False),
)


def ensure_schema(bind: Engine | Connection) -> None:
    """Create the counter table if absent. Idempotent; safe to call on boot."""
    metadata.create_all(bind, tables=[sequences], checkfirst=True)


@dataclass(frozen=True, slots=True)
class Sequence:
    """A named gapless counter. State lives in the DB, so instances are cheap and
    interchangeable — two ``Sequence("invoice")`` objects address the same row."""

    key: str
    start: int = 1

    def next_value(self, session: Session) -> int:
        """Issue the next number for this key, holding a row lock for the caller's
        transaction. Caller owns the commit: the number is only final once they
        commit, and is reused (not skipped) if they roll back."""
        # Lazily create the counter so callers need not pre-register every key.
        # ON CONFLICT DO NOTHING makes concurrent first-use idempotent: the second
        # writer blocks on the in-flight insert, then sees the row and moves on.
        session.execute(
            pg_insert(sequences)
            .values(key=self.key, value=self.start - 1)
            .on_conflict_do_nothing(index_elements=["key"])
        )
        # The load-bearing line: FOR UPDATE locks *this key's row* so a concurrent
        # caller cannot read the same value before we commit our increment. Drop
        # the lock and parallel callers read-modify-write the same number → dupes.
        current = session.execute(
            select(sequences.c.value).where(sequences.c.key == self.key).with_for_update()
        ).scalar_one()
        nxt = current + 1
        session.execute(
            update(sequences).where(sequences.c.key == self.key).values(value=nxt)
        )
        return nxt
