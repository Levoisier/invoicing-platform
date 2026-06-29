"""Proves BACKLOG B13's source half: the OpenAPI schema is emitted from the live app
with no database, and carries the routes and models the frontend types are generated
from.

The TS generation itself is a Make/Node step (`make gen-types`), but the *contract*
is this schema. Building it with run_migrations=False is what lets gen-types run in
CI without Postgres — so we assert exactly that build works and is complete.
"""

from __future__ import annotations

from app.bootstrap import create_app


def _schema() -> dict:
    # No DB: schema is a pure function of routes + Pydantic models.
    return create_app(run_migrations=False).openapi()


def test_schema_exposes_the_domain_routes() -> None:
    paths = _schema()["paths"]
    for path in ("/clients", "/invoices", "/invoices/{invoice_id}", "/auth/token"):
        assert path in paths


def test_schema_carries_money_as_string_pair() -> None:
    # The contract must reflect our deliberate Money serialization (string amount,
    # not a float) — this is the shape the frontend will consume.
    money = _schema()["components"]["schemas"]["MoneyOut"]["properties"]
    assert money["amount"]["type"] == "string"
    assert money["currency"]["type"] == "string"
