"""Proves BACKLOG B10: the host boots and the create-client → create-invoice slice
works over HTTP.

This is the first true end-to-end test: it builds the real app with
``create_app`` (discover plugins → load+migrate modules → mount routers), then
drives it through the HTTP API — log in, create a client, create a CO invoice, and
read it back — asserting the IVA totals the registered plugin produced. It also
confirms ``/docs`` is live and that the domain routes require auth.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.engine import Engine

# Tables the boot (modules + numbering + loader ledger) creates; dropped for a clean
# bootstrap each test.
_TABLES = (
    "payments_ledger_entry",
    "payments_payment",
    "invoicing_invoice_line",
    "invoicing_invoice",
    "invoicing_party",
    "sequences",
    "installed_modules",
)


def _reset(engine: Engine) -> None:
    with engine.begin() as conn:
        for table in _TABLES:
            conn.execute(text(f'DROP TABLE IF EXISTS "{table}" CASCADE'))


@pytest.fixture
def client(pg_engine: Engine) -> TestClient:
    _reset(pg_engine)
    from app.bootstrap import create_app  # imported here so collection needs no DB

    app = create_app()
    yield TestClient(app)
    _reset(pg_engine)


def _token(client: TestClient) -> str:
    resp = client.post("/auth/token", json={"username": "admin", "password": "admin"})
    assert resp.status_code == 200
    return resp.json()["access_token"]


def test_docs_and_health_are_live(client: TestClient) -> None:
    assert client.get("/health").json() == {"status": "ok"}
    assert client.get("/docs").status_code == 200  # interactive API docs mounted


def test_domain_routes_require_auth(client: TestClient) -> None:
    resp = client.post("/clients", json={"name": "X", "tax_id": "1", "jurisdiction": "CO"})
    assert resp.status_code == 401


def test_create_client_then_invoice_over_http(client: TestClient) -> None:
    auth = {"Authorization": f"Bearer {_token(client)}"}

    created = client.post(
        "/clients",
        json={"name": "Acme S.A.S.", "tax_id": "900.123.456-7", "jurisdiction": "CO"},
        headers=auth,
    )
    assert created.status_code == 201
    client_id = created.json()["id"]

    issued = client.post(
        "/invoices",
        json={
            "client_id": client_id,
            "currency": "COP",
            "lines": [
                {"description": "Consulting", "quantity": "10", "unit_price": "100000",
                 "tax_code": "iva_19"},
                {"description": "Excluded item", "quantity": "1", "unit_price": "50000",
                 "tax_code": "excluded"},
            ],
        },
        headers=auth,
    )
    assert issued.status_code == 201
    body = issued.json()
    assert body["number"] == 1  # gapless number assigned
    assert body["status"] == "issued"
    # net 1,000,000 + 50,000; IVA = 190,000 (19% on the consulting line) + 0
    assert body["subtotal"] == {"amount": "1050000", "currency": "COP"}
    assert body["tax"] == {"amount": "190000", "currency": "COP"}
    assert body["total"] == {"amount": "1240000", "currency": "COP"}

    # Read it back: persisted and re-totalled identically.
    fetched = client.get(f"/invoices/{body['id']}", headers=auth)
    assert fetched.status_code == 200
    assert fetched.json()["total"] == {"amount": "1240000", "currency": "COP"}


def test_record_payment_marks_invoice_paid_over_http(client: TestClient) -> None:
    auth = {"Authorization": f"Bearer {_token(client)}"}
    client_id = client.post(
        "/clients",
        json={"name": "Acme", "tax_id": "900.1", "jurisdiction": "CO"},
        headers=auth,
    ).json()["id"]
    invoice = client.post(
        "/invoices",
        json={
            "client_id": client_id,
            "currency": "COP",
            "lines": [{"description": "Item", "quantity": "1", "unit_price": "1000000",
                       "tax_code": "iva_19"}],
        },
        headers=auth,
    ).json()
    assert invoice["total"] == {"amount": "1190000", "currency": "COP"}

    # Pay it in full: the payments module posts the ledger and flips status, atomically.
    paid = client.post(
        f"/invoices/{invoice['id']}/payments",
        json={"amount": "1190000", "currency": "COP"},
        headers=auth,
    )
    assert paid.status_code == 201
    assert paid.json()["invoice_status"] == "paid"
    assert len(paid.json()["ledger"]) == 2

    fetched = client.get(f"/invoices/{invoice['id']}", headers=auth)
    assert fetched.json()["status"] == "paid"
