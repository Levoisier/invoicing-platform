"""Proves BACKLOG B5: modules load in dependency order, cycles are rejected, and
migrations run once per version (install → unchanged → upgrade), atomically.

Ordering and cycle detection are pure graph logic, tested without a database. The
lifecycle (the version-gated migration ledger) only means something against a real
transaction, so those tests use Postgres and run each boot inside a unit of work —
which also lets the last test show a failed boot rolls back as a whole.
"""

from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from nucleus.db import make_session_factory, unit_of_work
from nucleus.modules import (
    Action,
    DependencyCycleError,
    MissingDependencyError,
    ModuleContext,
    ModuleManifest,
    ensure_schema,
    installed_modules,
    load_modules,
    toposort,
)
from nucleus.modules.toposort import DependencyError


def _names(manifests: list[ModuleManifest]) -> list[str]:
    return [m.name for m in manifests]


# --- pure: ordering and graph validation (no database) ----------------------


def test_orders_dependencies_before_dependents() -> None:
    # payments depends on invoicing; invoicing depends on nothing → invoicing first.
    invoicing = ModuleManifest(name="invoicing", version="1")
    payments = ModuleManifest(name="payments", version="1", depends=("invoicing",))

    assert _names(toposort([payments, invoicing])) == ["invoicing", "payments"]


def test_order_is_deterministic_for_independent_modules() -> None:
    # No edges between them → tie broken by name, so output is reproducible.
    mods = [ModuleManifest(name=n, version="1") for n in ("c", "a", "b")]
    assert _names(toposort(mods)) == ["a", "b", "c"]


def test_cycle_is_rejected_with_the_path() -> None:
    a = ModuleManifest(name="a", version="1", depends=("b",))
    b = ModuleManifest(name="b", version="1", depends=("a",))
    with pytest.raises(DependencyCycleError, match="dependency cycle: a -> b -> a"):
        toposort([a, b])


def test_unknown_dependency_is_rejected() -> None:
    a = ModuleManifest(name="a", version="1", depends=("ghost",))
    with pytest.raises(MissingDependencyError, match="depends on unknown module 'ghost'"):
        toposort([a])


def test_duplicate_module_name_is_rejected() -> None:
    with pytest.raises(DependencyError, match="duplicate module name: 'a'"):
        toposort([ModuleManifest(name="a", version="1"), ModuleManifest(name="a", version="2")])


# --- DB-backed: the install/upgrade lifecycle -------------------------------


@pytest.fixture
def session_factory(pg_engine: Engine) -> sessionmaker[Session]:
    ensure_schema(pg_engine)
    with pg_engine.begin() as conn:
        conn.execute(installed_modules.delete())
        # Drop any leftover module tables a previous run's migrate hook created.
        for name in ("mod_a", "mod_b"):
            conn.execute(text(f'DROP TABLE IF EXISTS "{name}"'))
    return make_session_factory(pg_engine)


def _record_module(
    name: str, version: str, *, depends: tuple[str, ...] = (), log: list[str] | None = None
) -> ModuleManifest:
    """A fake module whose hooks append to `log`, so a test can read off exactly
    when (and in what order) migrate/register fired."""

    def migrate(ctx: ModuleContext, _n: str = name, _log: list[str] | None = log) -> None:
        if _log is not None:
            _log.append(f"migrate:{_n}")
        # Real DDL inside the boot transaction — proves migrations share the txn.
        ctx.session.execute(text(f'CREATE TABLE IF NOT EXISTS "mod_{_n}" (id int)'))

    def register(ctx: ModuleContext, _n: str = name, _log: list[str] | None = log) -> None:
        if _log is not None:
            _log.append(f"register:{_n}")

    return ModuleManifest(
        name=name, version=version, depends=depends, migrate=migrate, register=register
    )


def _installed_version(session_factory: sessionmaker[Session], name: str) -> str | None:
    with session_factory() as session:
        return session.execute(
            installed_modules.select()
            .with_only_columns(installed_modules.c.version)
            .where(installed_modules.c.name == name)
        ).scalar_one_or_none()


def test_two_modules_load_in_dependency_order(session_factory: sessionmaker[Session]) -> None:
    log: list[str] = []
    invoicing = _record_module("a", "1", log=log)
    payments = _record_module("b", "1", depends=("a",), log=log)

    with unit_of_work(session_factory) as session:
        results = load_modules([payments, invoicing], session)  # deliberately out of order

    # Dependency first, in both the schema phase and the runtime phase.
    assert log == ["migrate:a", "register:a", "migrate:b", "register:b"]
    assert [(r.name, r.action) for r in results] == [
        ("a", Action.INSTALLED),
        ("b", Action.INSTALLED),
    ]


def test_migration_runs_once_per_version(session_factory: sessionmaker[Session]) -> None:
    log: list[str] = []

    # First boot: install, migrate runs.
    with unit_of_work(session_factory) as session:
        (r1,) = load_modules([_record_module("a", "1", log=log)], session)
    # Second boot at the same version: ledger says current, migrate is skipped.
    with unit_of_work(session_factory) as session:
        (r2,) = load_modules([_record_module("a", "1", log=log)], session)
    # Third boot at a new version: upgrade, migrate runs again.
    with unit_of_work(session_factory) as session:
        (r3,) = load_modules([_record_module("a", "2", log=log)], session)

    assert (r1.action, r2.action, r3.action) == (
        Action.INSTALLED,
        Action.UNCHANGED,
        Action.UPGRADED,
    )
    # migrate fired only on install and upgrade — never on the unchanged boot.
    assert [e for e in log if e.startswith("migrate")] == ["migrate:a", "migrate:a"]
    assert _installed_version(session_factory, "a") == "2"


def test_failed_boot_rolls_back_every_module(session_factory: sessionmaker[Session]) -> None:
    good = _record_module("a", "1")

    def _boom(ctx: ModuleContext) -> None:
        raise RuntimeError("migration blew up")

    bad = ModuleManifest(name="b", version="1", depends=("a",), migrate=_boom)

    with pytest.raises(RuntimeError, match="migration blew up"):
        with unit_of_work(session_factory) as session:
            load_modules([good, bad], session)

    # 'a' migrated and recorded *before* 'b' failed — but the unit of work rolls
    # the whole boot back, so the ledger is empty: no half-installed state.
    with session_factory() as session:
        rows = session.execute(installed_modules.select()).all()
    assert rows == []
