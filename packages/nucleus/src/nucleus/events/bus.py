"""In-process, synchronous event bus.

Publish is a *function call*, not a message send: subscribers run immediately, in
the publisher's call stack, on the publisher's database session. That is the whole
point. Because a subscriber's writes land in the same transaction as the event
that triggered them, they commit or roll back together — the transactional
intimacy that lets invoice status and ledger entries move as one (B12).

This is deliberately the opposite of a message queue: no async, no retries, no
eventual consistency. The trade — subscribers sit on the publisher's critical path
and must be in-process — is exactly what buys cross-module atomicity. Transaction-
boundary semantics are recorded in docs/ARCHITECTURE.md §3.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from typing import TYPE_CHECKING, TypeVar

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

E = TypeVar("E")


class EventBus:
    """Maps event types to ordered lists of synchronous handlers."""

    def __init__(self) -> None:
        self._subscribers: dict[type, list[Callable[..., None]]] = defaultdict(list)

    def subscribe(self, event_type: type[E], handler: Callable[[E, Session], None]) -> None:
        """Register `handler` for exactly `event_type`. Handlers fire in
        subscription order — the only ordering guarantee the bus makes."""
        self._subscribers[event_type].append(handler)

    def publish(self, event: object, session: Session) -> None:
        """Deliver `event` to its subscribers, now, on `session`.

        Dispatch is by *exact* type, not subclass — a handler gets only the type it
        asked for, keeping delivery predictable. We pass the publisher's own
        session so handlers write inside the same transaction, and we do NOT catch:
        a handler raising must propagate, so a unit of work rolls the whole reaction
        (trigger + every handler) back as one. Swallowing here would quietly break
        the atomicity this bus exists to provide.
        """
        for handler in self._subscribers.get(type(event), ()):
            handler(event, session)

    def clear(self) -> None:
        """Drop all subscriptions. For tests — the module-level `bus` is shared."""
        self._subscribers.clear()


# Module-level singleton: modules subscribe at load time (their `register` hook)
# and publishers look up the same shared bus, the same wiring pattern as the
# registries. Tests that touch it must `clear()` to avoid leaking subscriptions.
bus = EventBus()
