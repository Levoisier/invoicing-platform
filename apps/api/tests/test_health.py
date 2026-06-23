"""Smoke test for the host. Proves the workspace is wired: the `app` package
imports, FastAPI mounts, and a request round-trips. If this fails, B0's skeleton is
broken — everything downstream sits on top of it.
"""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_ok():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
