"""The generic registry: a keyed lookup table that inverts dependencies.

A consumer asks a registry for an implementation by key (a jurisdiction, a
provider name) instead of importing the implementing module. That one
indirection is the whole project: adding a country becomes "install a package
that registers itself", with no edit to the consumer. The cost is honest — a
missing implementation is a *runtime* miss, not a compile error — so the miss is
made loud and specific rather than a bare ``KeyError``.
"""

from __future__ import annotations

from typing import Generic, TypeVar

K = TypeVar("K")
V = TypeVar("V")


class RegistryError(LookupError):
    """A registry registration or lookup failed: duplicate key, or missing key."""


class Registry(Generic[K, V]):
    """A small dict with guard rails and human-readable misses."""

    def __init__(self, *, label: str, key_name: str = "key") -> None:
        # `label`/`key_name` exist only to shape error text, so a missing CO tax
        # plugin reads "no TaxCalculator registered for jurisdiction 'CO'".
        self._label = label
        self._key_name = key_name
        self._items: dict[K, V] = {}

    def register(self, key: K, value: V, *, replace: bool = False) -> None:
        # Refuse silent overwrites: two plugins claiming one jurisdiction is a
        # conflict to surface, not to settle by load order. `replace=True` is the
        # explicit escape hatch (a test swapping an implementation, say).
        if key in self._items and not replace:
            msg = f"{self._label} already registered for {self._key_name} {key!r}"
            raise RegistryError(msg)
        self._items[key] = value

    def get(self, key: K) -> V:
        try:
            return self._items[key]
        except KeyError:
            # `from None`: the dict KeyError is noise; ours is the actionable line.
            msg = f"no {self._label} registered for {self._key_name} {key!r}"
            raise RegistryError(msg) from None

    def __contains__(self, key: object) -> bool:
        return key in self._items

    def keys(self) -> tuple[K, ...]:
        return tuple(self._items)

    def clear(self) -> None:
        """Drop all registrations. Mainly for tests — they must not leak state
        through the module-level registry singletons."""
        self._items.clear()
