"""The loader: order modules, bring each to its version, then wire it in.

This is the host's bootstrap engine (mounted in B10). It runs the whole module
set inside the caller's transaction, so a failure partway through rolls back
*every* migration and ledger update from this boot — there is no half-installed
state to recover from. Ordering comes from toposort; the per-module version gate
comes from lifecycle; this module just sequences them.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from nucleus.modules.lifecycle import Action, ensure_schema, install_or_upgrade
from nucleus.modules.manifest import ModuleContext
from nucleus.modules.toposort import toposort

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from nucleus.modules.manifest import ModuleManifest


@dataclass(frozen=True)
class LoadResult:
    """One module's outcome, in load order — the boot record the host logs."""

    name: str
    version: str
    action: Action


def load_modules(manifests: list[ModuleManifest], session: Session) -> list[LoadResult]:
    """Load all modules in dependency order. For each: migrate if its version
    changed, record it, then run its runtime ``register`` hook. Returns results in
    the order modules were loaded."""
    ordered = toposort(manifests)  # raises on cycle/missing/duplicate before any write
    ensure_schema(session.get_bind())

    results: list[LoadResult] = []
    for manifest in ordered:
        action = install_or_upgrade(session, manifest)
        if manifest.register is not None:
            # Runtime wiring runs on *every* boot, regardless of the schema action —
            # routers and registry entries live in process memory and vanish on
            # restart, unlike migrations which persist in the DB.
            manifest.register(ModuleContext(session=session))
        results.append(LoadResult(manifest.name, manifest.version, action))
    return results


def register_modules(manifests: list[ModuleManifest]) -> None:
    """Run only the `register` hooks (mount routers etc.), in dependency order,
    touching no database. For assembling the app's HTTP surface without migrating —
    e.g. emitting the OpenAPI schema in CI, where no Postgres is available."""
    context = ModuleContext(session=None)
    for manifest in toposort(manifests):
        if manifest.register is not None:
            manifest.register(context)
