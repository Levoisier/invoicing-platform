# Root task runner. Ties the two toolchains (uv for Python, npm for web) and
# docker-compose together (README §3, §8). Targets are intentionally thin
# wrappers so the real commands stay visible and copy-pasteable.

.PHONY: up down dev migrate gen-types test lint sync

# Bring up Postgres (the only service that builds today; api/web are behind the
# `full` profile until their Dockerfiles land in B10/B14).
up:
	docker compose up -d db

down:
	docker compose down

# Install/refresh the workspace virtualenv from uv.lock.
sync:
	uv sync

# Local dev without full Docker: Postgres in a container, API with reload. The
# web dev server is added in B14; kept here as the documented single entrypoint.
dev: up
	uv run uvicorn app.main:app --reload --app-dir apps/api/src

# Run all module migrations in dependency (toposort) order. The host's bootstrap
# (create_app, B10) already migrates on startup; building the app applies them. A
# dedicated single-shot migrate entrypoint (so workers don't each migrate at scale)
# is a later refinement.
migrate:
	uv run python -c "from app.bootstrap import create_app; create_app()" && echo "migrate: modules migrated via bootstrap"

# Emit OpenAPI from FastAPI and regenerate the frontend's typed client. The one
# Make target that owns apps/web/lib/types.ts (README §7.B: contract honesty) —
# never hand-edit that file. Needs no DB: the schema is built with migrations off.
# Assumes web deps are installed (`cd apps/web && npm install`).
gen-types:
	uv run python -m app.export_openapi > openapi.json
	cd apps/web && npx openapi-typescript ../../openapi.json -o lib/types.ts
	rm -f openapi.json
	@echo "gen-types: regenerated apps/web/lib/types.ts"

# Run the Python test suite. Empty today, but the target must exist and exit 0
# (BACKLOG B0 done-criterion: `make test` runs even if empty).
test:
	uv run pytest

lint:
	uvx ruff check .
