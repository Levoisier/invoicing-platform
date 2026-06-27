"""Proves BACKLOG B6: a published event reaches its subscriber, and a subscriber's
work shares the publisher's transaction — commits with it, rolls back with it.

Delivery and dispatch are pure (no DB). The headline property — that the bus is a
seam atomicity crosses, not a queue that breaks it — is shown against Postgres: a
subscriber writes through the publisher's session, and a failing subscriber takes
the trigger down with it.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest
from sqlalchemy import String, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Mapped, Session, mapped_column, sessionmaker

from nucleus.db import Base, make_session_factory, unit_of_work
from nucleus.events import EventBus


@dataclass
class Pinged:
    n: int


@dataclass
class Ponged:
    n: int


# --- pure: delivery and dispatch (no database) ------------------------------


def test_subscriber_receives_published_event() -> None:
    bus = EventBus()
    seen: list[int] = []
    bus.subscribe(Pinged, lambda e, _session: seen.append(e.n))

    bus.publish(Pinged(1), session=None)  # this handler ignores the session

    assert seen == [1]


def test_handlers_fire_in_subscription_order() -> None:
    bus = EventBus()
    order: list[str] = []
    bus.subscribe(Pinged, lambda e, _s: order.append("first"))
    bus.subscribe(Pinged, lambda e, _s: order.append("second"))

    bus.publish(Pinged(1), session=None)

    assert order == ["first", "second"]


def test_dispatch_is_by_exact_type() -> None:
    bus = EventBus()
    seen: list[str] = []
    bus.subscribe(Pinged, lambda e, _s: seen.append("ping"))

    bus.publish(Ponged(1), session=None)  # different type, no subscriber

    assert seen == []


def test_publish_with_no_subscribers_is_a_noop() -> None:
    EventBus().publish(Pinged(1), session=None)  # must not raise


def test_handler_exception_propagates() -> None:
    # The bus must not swallow: propagation is what lets a unit of work roll back.
    def _boom(event: Pinged, _session: object) -> None:
        raise RuntimeError("boom")

    bus = EventBus()
    bus.subscribe(Pinged, _boom)
    with pytest.raises(RuntimeError, match="boom"):
        bus.publish(Pinged(1), session=None)


# --- DB-backed: the subscriber shares the publisher's transaction -----------


class _Note(Base):
    __tablename__ = "event_test_note"

    id: Mapped[int] = mapped_column(primary_key=True)
    text: Mapped[str] = mapped_column(String)


@dataclass
class ThingHappened:
    label: str


def _write_note(event: ThingHappened, session: Session) -> None:
    session.add(_Note(text=event.label))


@pytest.fixture
def session_factory(pg_engine: Engine) -> sessionmaker[Session]:
    Base.metadata.create_all(pg_engine, tables=[_Note.__table__])
    try:
        yield make_session_factory(pg_engine)
    finally:
        Base.metadata.drop_all(pg_engine, tables=[_Note.__table__])


def _notes(session_factory: sessionmaker[Session]) -> list[str]:
    with session_factory() as session:
        return sorted(session.execute(select(_Note.text)).scalars().all())


def test_subscriber_writes_commit_with_the_trigger(
    session_factory: sessionmaker[Session],
) -> None:
    bus = EventBus()
    bus.subscribe(ThingHappened, _write_note)

    with unit_of_work(session_factory) as session:
        session.add(_Note(text="trigger"))
        bus.publish(ThingHappened("reaction"), session)  # same session, same txn

    # Both the trigger's row and the subscriber's row are there: one commit.
    assert _notes(session_factory) == ["reaction", "trigger"]


def test_failing_subscriber_rolls_back_the_trigger(
    session_factory: sessionmaker[Session],
) -> None:
    bus = EventBus()

    def _boom(event: ThingHappened, session: Session) -> None:
        raise RuntimeError("subscriber failed")

    bus.subscribe(ThingHappened, _boom)

    with pytest.raises(RuntimeError, match="subscriber failed"):
        with unit_of_work(session_factory) as session:
            session.add(_Note(text="trigger"))  # written before the event
            bus.publish(ThingHappened("x"), session)

    # The subscriber's failure rolled back the publisher's own write too: the seam
    # is atomic, not a fire-and-forget queue.
    assert _notes(session_factory) == []
