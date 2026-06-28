"""Dependency seams a module's routes declare but the host fills.

A module defines its routes against these placeholders — ``Depends(get_session)``,
``Depends(get_principal)`` — without holding the host's engine or auth config. At
boot the host overrides them via ``app.dependency_overrides`` with the real
session-per-request and the configured authenticator. It's the registry pattern
applied to HTTP: the module asks for "a session" / "the caller" by name, the host
supplies the concrete thing. Calling these unoverridden is a wiring bug, so they
fail loudly rather than silently returning nothing.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from nucleus.api.auth import Principal


def get_session() -> Session:
    raise RuntimeError("get_session must be overridden by the host (app.dependency_overrides)")


def get_principal() -> Principal:
    raise RuntimeError("get_principal must be overridden by the host (app.dependency_overrides)")
