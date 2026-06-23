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

# Run all module migrations in dependency (toposort) order. Wired in B10 once the
# host's bootstrap exists; today it's a no-op placeholder so the contract is named.
migrate:
	@echo "migrate: no migrations yet (wired in B10)"

# Emit OpenAPI from FastAPI and regenerate the frontend's typed client. The one
# Make target that owns apps/web/lib/types.ts (README §7.B: contract honesty).
# Implemented in B13; placeholder until then.
gen-types:
	@echo "gen-types: implemented in B13"

# Run the Python test suite. Empty today, but the target must exist and exit 0
# (BACKLOG B0 done-criterion: `make test` runs even if empty).
test:
	uv run pytest

lint:
	uvx ruff check .
