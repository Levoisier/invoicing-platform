"""Compose the running edition: discover → load (toposort + migrate) → mount.

This is where the project's pieces become an app. The *edition* is decided by this
host's dependency list (README §1): which modules it imports, which plugins are
installed. Bootstrap reads that reality at runtime — it discovers tax plugins from
entry points, loads modules in dependency order (migrating each), and mounts their
routers — without naming any jurisdiction. Swap `tax_co` for another country's
package in pyproject and this file does not change.
"""

from __future__ import annotations

from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel

from app.settings import Settings, settings

# The edition's module set. Importing the manifests is the host's choice of modules;
# plugins arrive separately, via entry-point discovery, so they need no mention here.
# Order in this list doesn't matter — the loader toposorts by declared dependencies
# (payments depends on invoicing), so invoicing always migrates first.
from invoicing import manifest as invoicing_manifest
from nucleus.api import JWTAuth, get_principal, get_session, require_principal
from nucleus.db import make_engine, make_session_factory, session_per_request, unit_of_work
from nucleus.modules import load_modules, register_modules
from nucleus.plugins import discover_plugins
from nucleus.registry import route, tax
from payments import manifest as payments_manifest


class TokenIn(BaseModel):
    username: str
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


def create_app(config: Settings = settings, *, run_migrations: bool = True) -> FastAPI:
    engine = make_engine(config.database_url)
    session_factory = make_session_factory(engine)
    auth = JWTAuth(
        secret=config.jwt_secret,
        algorithm=config.jwt_algorithm,
        expire_minutes=config.jwt_expire_minutes,
    )

    modules = [invoicing_manifest, payments_manifest]

    # Build the composition from scratch. Clearing the shared registries makes
    # bootstrap idempotent — a second app in the same process (tests) re-composes
    # cleanly instead of tripping duplicate-registration guards.
    tax.clear()
    route.clear()

    discover_plugins()  # populate the tax registry from installed entry points
    if run_migrations:
        # One unit of work for the whole boot: every module's migration commits
        # together or not at all (B5). Register hooks also publish routers here.
        with unit_of_work(session_factory) as session:
            load_modules(modules, session)
    else:
        # Schema-only build (e.g. OpenAPI export for gen-types): mount routers
        # without touching the DB, so the contract can be generated with no Postgres.
        register_modules(modules)

    app = FastAPI(title="Invoicing Platform API")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/auth/token", response_model=TokenOut, tags=["auth"])
    def login(body: TokenIn) -> TokenOut:
        if body.username != config.auth_username or body.password != config.auth_password:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid credentials")
        return TokenOut(access_token=auth.issue(body.username))

    # Fill the seams the module routes declared: a request-scoped session (one
    # transaction per request) and the authenticator. This is the inversion at the
    # HTTP layer — modules asked by name, the host supplies the concrete deps.
    app.dependency_overrides[get_session] = session_per_request(session_factory)
    app.dependency_overrides[get_principal] = require_principal(auth)

    # Mount every router modules published during load.
    for name in route.keys():
        app.include_router(route.get(name))

    return app
