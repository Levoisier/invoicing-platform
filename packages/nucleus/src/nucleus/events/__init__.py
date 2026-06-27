"""In-process event bus: publish/subscribe within the shared transaction, so
side-effects participate in the same commit/rollback as their trigger (BACKLOG B6).
"""

from nucleus.events.bus import EventBus, bus

__all__ = ["EventBus", "bus"]
