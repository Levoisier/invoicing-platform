"""Proves BACKLOG B3: the unit of work commits as one unit and rolls back as one.

Atomicity is the project's headline property (it's what B12's invoice+ledger leans
on), so it has to be shown against a real transaction, not asserted. We use a
throwaway model on the real declarative ``Base`` and a real Postgres session: a
clean block persists; a block that raises leaves *nothing* behind.
"""

from __future__ import annotations

import pytest
from sqlalchemy import String, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Mapped, Session, mapped_column, sessionmaker

from nucleus.db import Base, make_session_factory, unit_of_work


class _Widget(Base):
    # First real consumer of the declarative base — doubles as proof Base works.
    __tablename__ = "uow_test_widget"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String)


class _Boom(Exception):
    """A deliberate failure raised mid-unit to trigger rollback."""


@pytest.fixture
def session_factory(pg_engine: Engine) -> sessionmaker[Session]:
    Base.metadata.create_all(pg_engine, tables=[_Widget.__table__])
    try:
        yield make_session_factory(pg_engine)
    finally:
        Base.metadata.drop_all(pg_engine, tables=[_Widget.__table__])


def _count(session_factory: sessionmaker[Session]) -> int:
    # A fresh session each time, so we read what's actually committed to the DB,
    # not what's lingering in some session's identity map.
    with session_factory() as session:
        return len(session.execute(select(_Widget)).scalars().all())


def test_unit_of_work_commits_on_success(session_factory: sessionmaker[Session]) -> None:
    with unit_of_work(session_factory) as session:
        session.add(_Widget(name="kept"))

    assert _count(session_factory) == 1


def test_unit_of_work_rolls_back_on_error(session_factory: sessionmaker[Session]) -> None:
    with pytest.raises(_Boom):  # the error must propagate, not be swallowed
        with unit_of_work(session_factory) as session:
            session.add(_Widget(name="doomed"))
            raise _Boom

    assert _count(session_factory) == 0


def test_rollback_undoes_every_write_in_the_unit(
    session_factory: sessionmaker[Session],
) -> None:
    # The "as one unit" claim: a later failure must un-persist earlier writes in
    # the same block, even ones already flushed to the DB.
    with pytest.raises(_Boom):
        with unit_of_work(session_factory) as session:
            session.add(_Widget(name="first"))
            session.flush()  # sent to the DB, but inside the open transaction
            session.add(_Widget(name="second"))
            raise _Boom

    assert _count(session_factory) == 0
