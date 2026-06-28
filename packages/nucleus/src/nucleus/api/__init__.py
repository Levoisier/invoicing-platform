"""API gateway helpers + JWT auth. The thin FastAPI-facing layer the host uses to
mount module routers and protect them (BACKLOG B7).
"""

from nucleus.api.auth import InvalidTokenError, JWTAuth, Principal
from nucleus.api.deps import get_principal, get_session
from nucleus.api.gateway import require_principal

__all__ = [
    "InvalidTokenError",
    "JWTAuth",
    "Principal",
    "get_principal",
    "get_session",
    "require_principal",
]
