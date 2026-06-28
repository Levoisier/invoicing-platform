"""JWT auth, framework-agnostic.

This layer knows nothing about FastAPI: it just issues and verifies signed tokens.
Keeping it pure means the token rules (signing, expiry, the "must have a subject"
invariant) are testable without spinning up an HTTP app, and a different transport
could reuse them. The FastAPI binding that turns a request into a verified
principal lives next door in ``gateway.py``.

Config is *passed in*, never read from the environment — same rule as the rest of
the nucleus (the host owns configuration). ``JWTAuth`` is constructed by the host
with its secret; the core stays a library.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt


class InvalidTokenError(Exception):
    """A token was missing, malformed, expired, or signed with the wrong key."""


@dataclass(frozen=True)
class Principal:
    """Who the request is acting as. ``subject`` is the JWT ``sub``; ``claims`` is
    the full validated payload, so routes can read roles/scopes later without
    re-decoding."""

    subject: str
    claims: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class JWTAuth:
    """Issues and verifies HS256 tokens against a single secret."""

    secret: str
    algorithm: str = "HS256"
    expire_minutes: int = 60

    def issue(self, subject: str, *, claims: dict[str, Any] | None = None) -> str:
        """Mint a signed token for ``subject``, expiring after ``expire_minutes``."""
        now = datetime.now(tz=UTC)
        payload: dict[str, Any] = {
            "sub": subject,
            "iat": now,
            # exp is the security-critical claim: PyJWT enforces it on decode, so an
            # expired token is rejected by the library, not by code we must remember
            # to write.
            "exp": now + timedelta(minutes=self.expire_minutes),
        }
        if claims:
            payload.update(claims)
        return jwt.encode(payload, self.secret, algorithm=self.algorithm)

    def verify(self, token: str) -> Principal:
        """Validate signature + expiry and return the principal, or raise."""
        try:
            payload = jwt.decode(token, self.secret, algorithms=[self.algorithm])
        except jwt.PyJWTError as exc:
            # Collapse PyJWT's many failure types into one auth error — callers only
            # care that the token is unacceptable, not which check tripped.
            raise InvalidTokenError(str(exc)) from exc
        subject = payload.get("sub")
        if not subject:
            raise InvalidTokenError("token missing subject")
        return Principal(subject=subject, claims=payload)
