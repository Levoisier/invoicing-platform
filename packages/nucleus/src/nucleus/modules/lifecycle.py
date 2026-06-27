"""Install/upgrade lifecycle: run a module's migration exactly when its version
changes, and remember what's installed.

The loader keeps a tiny ledger — ``installed_modules(name, version)`` — so it can
tell, per module, whether this boot is a first install, a version upgrade, or a
no-op. Migrations are expensive and must not re-run every start; the version gate
is what makes "migrate once per version" true. The ledger lives in the database
(not a file or memory) because the truth about what schema exists is in the
database, and several API workers must agree on it.
"""

from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import Column, MetaData, String, Table, select

from nucleus.modules.manifest import ModuleContext

if TYPE_CHECKING:
    from sqlalchemy import Connection, Engine
    from sqlalchemy.orm import Session

    from nucleus.modules.manifest import ModuleManifest

# Own MetaData, not the declarative Base: the ledger is loader infrastructure, not
# a domain model, and it must exist before any module's own tables are migrated.
metadata = MetaData()

installed_modules = Table(
    "installed_modules",
    metadata,
    Column("name", String, primary_key=True),
    Column("version", String, nullable=False),
)


class Action(StrEnum):
    """What the loader did with a module on this boot."""

    INSTALLED = "installed"
    UPGRADED = "upgraded"
    UNCHANGED = "unchanged"


def ensure_schema(bind: Engine | Connection) -> None:
    """Create the loader's ledger table if absent. Idempotent; called before load."""
    metadata.create_all(bind, tables=[installed_modules], checkfirst=True)


def install_or_upgrade(session: Session, manifest: ModuleManifest) -> Action:
    """Run ``manifest.migrate`` iff the installed version differs (or is absent),
    then record the new version. Returns what happened, for the boot log."""
    installed = session.execute(
        select(installed_modules.c.version).where(installed_modules.c.name == manifest.name)
    ).scalar_one_or_none()

    if installed == manifest.version:
        # Already current: skipping the migration is the whole point of the ledger.
        return Action.UNCHANGED

    if manifest.migrate is not None:
        # Any version difference triggers a migrate. We don't compare order
        # (up vs down): the migrate hook owns bringing schema to its version, and
        # treating "different" as "run it" keeps the gate dumb and predictable.
        manifest.migrate(ModuleContext(session=session))

    if installed is None:
        session.execute(
            installed_modules.insert().values(name=manifest.name, version=manifest.version)
        )
        return Action.INSTALLED

    session.execute(
        installed_modules.update()
        .where(installed_modules.c.name == manifest.name)
        .values(version=manifest.version)
    )
    return Action.UPGRADED
