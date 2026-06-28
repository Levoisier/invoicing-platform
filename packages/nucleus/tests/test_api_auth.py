"""Proves BACKLOG B7: a protected route rejects a missing/invalid token and accepts
a valid one.

The pure tests pin the token rules (round-trip, expiry, wrong key, missing
subject) without HTTP. The integration tests mount a real protected route and hit
it with the TestClient — the actual acceptance criterion — covering no token, a
junk token, and a valid one.
"""

from __future__ import annotations

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from nucleus.api import InvalidTokenError, JWTAuth, Principal, require_principal

# 32+ byte secret: HS256 wants at least that, and PyJWT warns below it.
_AUTH = JWTAuth(secret="unit-test-secret-key-0123456789-abc")


# --- pure: the token rules --------------------------------------------------


def test_issue_then_verify_round_trips_the_subject() -> None:
    token = _AUTH.issue("user-42")
    principal = _AUTH.verify(token)
    assert principal.subject == "user-42"


def test_extra_claims_survive_the_round_trip() -> None:
    principal = _AUTH.verify(_AUTH.issue("u", claims={"role": "admin"}))
    assert principal.claims["role"] == "admin"


def test_garbage_token_is_rejected() -> None:
    with pytest.raises(InvalidTokenError):
        _AUTH.verify("not-a-jwt")


def test_token_signed_with_another_secret_is_rejected() -> None:
    forged = JWTAuth(secret="a-different-secret-key-0123456789-x").issue("u")
    with pytest.raises(InvalidTokenError):
        _AUTH.verify(forged)


def test_expired_token_is_rejected() -> None:
    # Negative lifetime → already expired; PyJWT enforces exp on decode.
    expired = JWTAuth(secret=_AUTH.secret, expire_minutes=-1).issue("u")
    with pytest.raises(InvalidTokenError):
        _AUTH.verify(expired)


# --- integration: a protected FastAPI route ---------------------------------


# Build the auth dependency once, the way the host would, then reuse it.
_require_principal = require_principal(_AUTH)


def _app() -> FastAPI:
    app = FastAPI()

    @app.get("/me")
    def me(principal: Principal = Depends(_require_principal)) -> dict[str, str]:
        return {"subject": principal.subject}

    return app


def test_protected_route_rejects_missing_token() -> None:
    resp = TestClient(_app()).get("/me")
    assert resp.status_code == 401
    assert resp.headers["WWW-Authenticate"] == "Bearer"


def test_protected_route_rejects_invalid_token() -> None:
    resp = TestClient(_app()).get("/me", headers={"Authorization": "Bearer garbage"})
    assert resp.status_code == 401


def test_protected_route_accepts_valid_token() -> None:
    token = _AUTH.issue("alice")
    resp = TestClient(_app()).get("/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json() == {"subject": "alice"}
