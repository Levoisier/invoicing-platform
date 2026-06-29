"""Emit the app's OpenAPI schema as JSON on stdout — the source of truth for the
frontend's generated types (B13).

The schema is a pure function of the routes and Pydantic models, so we build the
app with ``run_migrations=False``: routers are mounted (register hooks don't touch
the DB) but nothing migrates. That lets ``make gen-types`` run in CI with no
Postgres — contract generation must never depend on a live database.

Usage: ``python -m app.export_openapi > openapi.json``
"""

from __future__ import annotations

import json
import sys

from app.bootstrap import create_app


def main() -> None:
    schema = create_app(run_migrations=False).openapi()
    json.dump(schema, sys.stdout, indent=2)


if __name__ == "__main__":
    main()
