"""The FastAPI side of the gateway: turn a request into a verified principal.

This is the thin adapter from HTTP to the pure auth layer. It reads the bearer
token off the request, hands it to ``JWTAuth.verify``, and translates an auth
failure into a clean ``401``. Modules protect a route by depending on the callable
``require_principal(auth)`` returns — they never parse headers or touch JWT
themselves, which keeps auth uniform across every module.
"""

from __future__ import annotations

from collections.abc import Callable

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from nucleus.api.auth import InvalidTokenError, JWTAuth, Principal

# auto_error=False: let a *missing* credential fall through to us as None, so we
# answer 401 (with WWW-Authenticate) consistently for both "no token" and "bad
# token". FastAPI's default would raise a bare 403 for the missing case.
_bearer = HTTPBearer(auto_error=False)


def require_principal(auth: JWTAuth) -> Callable[..., Principal]:
    """Build a FastAPI dependency that authenticates the request or raises 401.

    A factory (not a plain dependency) because the dependency needs the host's
    configured ``auth`` — the same inject-by-construction pattern as
    ``session_per_request`` in nucleus.db."""

    def _dependency(
        credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    ) -> Principal:
        if credentials is None:
            raise _unauthorized("missing bearer token")
        try:
            return auth.verify(credentials.credentials)
        except InvalidTokenError as exc:
            raise _unauthorized(str(exc)) from exc

    return _dependency


def _unauthorized(detail: str) -> HTTPException:
    # WWW-Authenticate is part of a correct 401 — it tells the client the scheme.
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )
