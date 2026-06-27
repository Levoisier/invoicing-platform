"""Proves BACKLOG B2: gapless sequential numbering under parallel issuance.

The headline test runs real threads, each on its own connection, racing to draw
numbers — and asserts the issued set is exactly ``1..N`` with no gaps and no
duplicates. The companion test removes the row lock and shows the same race
*does* produce duplicates, so we know the lock is what's carrying the property,
not luck.
"""

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from nucleus.primitives import Sequence, ensure_schema, sequences


@pytest.fixture(autouse=True)
def _clean_table(pg_engine: Engine):
    """Each test starts from an empty counter table so ranges are predictable."""
    ensure_schema(pg_engine)
    with pg_engine.begin() as conn:
        conn.execute(sequences.delete())
    yield


def test_sequential_next_value_increments_from_one(pg_engine: Engine) -> None:
    seq = Sequence("invoice")
    with Session(pg_engine) as session:
        issued = [seq.next_value(session) for _ in range(5)]
        session.commit()

    assert issued == [1, 2, 3, 4, 5]


def test_sequences_are_independent_per_key(pg_engine: Engine) -> None:
    invoices, credits = Sequence("invoice"), Sequence("credit_note")
    with Session(pg_engine) as session:
        assert invoices.next_value(session) == 1
        assert credits.next_value(session) == 1
        assert invoices.next_value(session) == 2
        session.commit()


def test_start_offset_is_honored(pg_engine: Engine) -> None:
    # A tenant may need invoice numbers to begin at a DIAN-authorized range start,
    # so the first issued value must be `start`, not always 1.
    seq = Sequence("ranged", start=1000)
    with Session(pg_engine) as session:
        assert seq.next_value(session) == 1000
        assert seq.next_value(session) == 1001
        session.commit()


def test_parallel_issue_is_gapless_and_unique(pg_engine: Engine) -> None:
    workers, per_worker = 8, 25
    total = workers * per_worker

    def draw_numbers() -> list[int]:
        # A fresh Session per thread == a separate DB connection, the way separate
        # API workers would each hold their own. Commit per number so each draw is
        # its own transaction, exactly mirroring "one invoice, one commit".
        got: list[int] = []
        seq = Sequence("invoice")
        with Session(pg_engine) as session:
            for _ in range(per_worker):
                got.append(seq.next_value(session))
                session.commit()
        return got

    with ThreadPoolExecutor(max_workers=workers) as pool:
        issued = [n for chunk in pool.map(lambda _: draw_numbers(), range(workers)) for n in chunk]

    # No gaps and no duplicates == the issued set is exactly the contiguous range.
    assert sorted(issued) == list(range(1, total + 1))


def test_without_row_lock_a_naive_counter_duplicates(pg_engine: Engine) -> None:
    """The lock is load-bearing: prove the naive read-then-write loses numbers.

    A ``Barrier`` forces every worker to read the counter *before* anyone writes,
    which is the exact interleaving the row lock prevents. Without ``FOR UPDATE``
    they all read the same value and write back the same number — duplicates —
    which is precisely the bug gapless numbering must not have.
    """
    workers = 8
    with pg_engine.begin() as conn:
        conn.execute(sequences.insert().values(key="naive", value=0))

    barrier = threading.Barrier(workers)

    def draw_without_lock() -> int:
        with Session(pg_engine) as session:
            current = session.execute(
                text("SELECT value FROM sequences WHERE key = 'naive'")  # no FOR UPDATE
            ).scalar_one()
            barrier.wait()  # hold until every worker has read the same value
            nxt = current + 1
            session.execute(text("UPDATE sequences SET value = :v WHERE key = 'naive'"), {"v": nxt})
            session.commit()
            return nxt

    with ThreadPoolExecutor(max_workers=workers) as pool:
        issued = list(pool.map(lambda _: draw_without_lock(), range(workers)))

    # The whole point: without the lock the numbers collide instead of being 1..N.
    assert len(set(issued)) < workers
