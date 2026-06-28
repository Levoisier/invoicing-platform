"""The invoicing module's manifest: what the loader needs to install and wire it.

The ``migrate`` hook creates this module's tables (and ensures the Sequence
primitive's counter table, since numbering depends on it). v1 migrates with
``create_all`` — honest for a schema with no history yet; per-module Alembic is the
production path once tables start evolving (README §2). Migration runs on the
loader's *session connection*, so it's part of the same atomic boot as every other
module (B5).

The ``register`` hook publishes this module's router into the route registry; the
host mounts everything in the registry at boot (B10). It runs on every boot
(routers live in process memory), so it registers with ``replace=True`` to be
idempotent across re-composition (e.g. a second app in the same test process).
"""

from __future__ import annotations

from invoicing.models import Invoice, InvoiceLine, Party
from nucleus.db import Base
from nucleus.modules import ModuleContext, ModuleManifest
from nucleus.primitives import ensure_schema as ensure_sequence_schema
from nucleus.registry import route


def _migrate(ctx: ModuleContext) -> None:
    # The session's connection, not the engine: keeps DDL inside the boot
    # transaction so a failed load rolls these tables back too (B5).
    bind = ctx.session.connection()
    ensure_sequence_schema(bind)
    Base.metadata.create_all(
        bind,
        tables=[Party.__table__, Invoice.__table__, InvoiceLine.__table__],
        checkfirst=True,
    )


def _register(ctx: ModuleContext) -> None:
    # Imported here, not at module top: the router pulls in FastAPI/Pydantic, which
    # only the running host needs — keeps `import invoicing.manifest` light.
    from invoicing.api import router

    route.register("invoicing", router, replace=True)


manifest = ModuleManifest(name="invoicing", version="1", migrate=_migrate, register=_register)
