"""What a module declares to the loader.

A module is just data plus two hooks. The split between them is the important
idea: ``migrate`` is the *schema* phase — persistent, run once per version when a
module is installed or upgraded — while ``register`` is the *runtime* phase —
in-process wiring (routers, models, plugins) that must happen on every boot
because it lives in process memory, not the database. Conflating the two is how
you end up re-running migrations every start, or forgetting to re-wire routers
after a restart.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


@dataclass
class ModuleContext:
    """Handed to a module's hooks. Carries the loader's session so a module's
    migration participates in the *same* transaction as the rest of the boot —
    bootstrap is then all-or-nothing, like everything else on this platform."""

    session: Session


# Hooks are plain callables, not subclasses: a module supplies behaviour, it does
# not inherit a framework base. Keeps the module→core dependency one-directional.
Hook = Callable[[ModuleContext], None]


@dataclass(frozen=True)
class ModuleManifest:
    """A module's identity, its dependencies, and its lifecycle hooks."""

    name: str
    version: str
    # Names of modules that must load first. Names, not imports — the loader
    # resolves order from the set it's given, so a module never imports a peer.
    depends: tuple[str, ...] = ()
    migrate: Hook | None = None
    register: Hook | None = None
