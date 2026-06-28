"""The payments module manifest. Declares its dependency on invoicing so the loader
toposorts invoicing's tables before payments' (the cross-module FK needs them first),
creates its own tables, and publishes its router for the host to mount.
"""

from __future__ import annotations

from nucleus.db import Base
from nucleus.modules import ModuleContext, ModuleManifest
from nucleus.registry import route
from payments.models import LedgerEntry, Payment


def _migrate(ctx: ModuleContext) -> None:
    bind = ctx.session.connection()  # in the boot transaction (B5)
    Base.metadata.create_all(
        bind, tables=[Payment.__table__, LedgerEntry.__table__], checkfirst=True
    )


def _register(ctx: ModuleContext) -> None:
    from payments.api import router

    route.register("payments", router, replace=True)


# depends on invoicing: payments references invoicing_invoice and reads invoice
# totals, so it must load second. The toposort enforces the order.
manifest = ModuleManifest(
    name="payments", version="1", depends=("invoicing",), migrate=_migrate, register=_register
)
