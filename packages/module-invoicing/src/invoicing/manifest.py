"""The invoicing module's manifest: what the loader needs to install and wire it.

The ``migrate`` hook creates this module's tables (and ensures the Sequence
primitive's counter table, since numbering depends on it). v1 migrates with
``create_all`` — honest for a schema with no history yet; per-module Alembic is the
production path once tables start evolving (README §2). Migration runs on the
loader's *session connection*, so it's part of the same atomic boot as every other
module (B5).

No ``register`` hook yet: routes are mounted by the host in B10.
"""

from __future__ import annotations

from invoicing.models import Invoice, InvoiceLine, Party
from nucleus.db import Base
from nucleus.modules import ModuleContext, ModuleManifest
from nucleus.primitives import ensure_schema as ensure_sequence_schema


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


manifest = ModuleManifest(name="invoicing", version="1", migrate=_migrate)
