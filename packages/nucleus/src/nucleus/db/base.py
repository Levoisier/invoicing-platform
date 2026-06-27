"""The one declarative base every nucleus and module model inherits.

One ``Base`` means one ``MetaData``, which means one coherent schema the host can
create and Alembic can diff in a single pass. The naming convention is here on
purpose: left to itself, SQLAlchemy lets the database auto-name constraints and
indexes, and those names vary by engine and shift between autogenerate runs —
which makes Alembic migrations noisy and downgrades (which drop constraints *by
name*) unreliable. Pinning the convention makes every constraint name
deterministic, so migrations diff cleanly. (SQLAlchemy: "Configuring Constraint
Naming Conventions".)
"""

from __future__ import annotations

from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

_NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=_NAMING_CONVENTION)
