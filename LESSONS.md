# LESSONS.md — what we learned the hard way

An **append-only** log of non-obvious things discovered while building this project.
This is the project's memory. When you hit a surprise — a library that didn't behave, a
tax rule that wasn't what the README assumed, an architectural choice that turned out
wrong — you write it down here so the next agent (and the owner) doesn't pay for it twice.

This pairs with the learning mandate in `CLAUDE.md` §0: the **How & Why** in your reply
explains *this* change; `LESSONS.md` captures the *transferable* insight that outlives it.

## When to add an entry

Add one when:

- A library/API behaved differently than the README or your assumption expected.
- A tax rate, format, or rule needed correcting against a real source.
- You chose an approach, hit a wall, and backtracked — record the wall.
- A test caught something subtle, or a property was harder to prove than it looked.
- You discovered a constraint that isn't written down anywhere else yet.

Don't log routine successes. Log the things that would make someone say *"oh, good to
know."*

## Format

Newest entries on top. Keep each one tight — a paragraph, not an essay. Link the commit
or file when useful.

```
## YYYY-MM-DD — short title
**Context:** what you were doing.
**Surprise:** what you expected vs. what actually happened.
**Resolution:** what you did about it.
**Takeaway:** the durable lesson for next time.
```

---

<!-- Add new lessons below this line, newest first. -->

## 2026-06-28 — FastAPI's `Depends` trips ruff B008; PyJWT warns on short secrets (B7)
**Context:** Wiring JWT auth into a FastAPI dependency and linting/testing it.
**Surprise:** Two small ones. (1) ruff's bugbear `B008` ("don't call functions in argument
defaults") fires on the FastAPI idiom `def route(x = Depends(...))` — but that *is* the
framework contract, not a bug. The fix is config, not `# noqa`: add `fastapi.Depends`
(and `Security`) to `[lint.flake8-bugbear] extend-immutable-calls`. A *nested* call like
`Depends(require_principal(auth))` still trips it, so build the dependency once at module
level (`dep = require_principal(auth)`) — which is also how a host should wire it. (2) PyJWT
2.13 emits `InsecureKeyLengthWarning` for HMAC secrets under 32 bytes; tests with a short
secret spew warnings. Use a ≥32-byte secret (and we bumped `.env.example` accordingly).
**Resolution:** Whitelisted `Depends`/`Security` in ruff, built the auth dependency once,
used 32-byte test secrets.
**Takeaway:** When a linter fights a framework's required idiom, prefer a scoped config
allowance over per-line suppressions — it documents the exception once and keeps the diff
clean.

## 2026-06-27 — Atomic boot depends on Postgres transactional DDL (B5)
**Context:** The module loader runs every module's `migrate` inside one unit of work so a
failed boot rolls back with no half-installed schema, and a test asserts the
`installed_modules` ledger is empty after a mid-load failure.
**Surprise:** This property is *not* portable. It works because Postgres wraps DDL
(`CREATE TABLE`, etc.) in the transaction and rolls it back like any other statement. MySQL
(and others) **auto-commit DDL**, which would leave the first module's tables behind even
after the unit of work "rolls back" — the atomic-boot guarantee silently evaporates there.
**Resolution:** Kept the one-transaction boot (we're Postgres-only, same call as the gapless
row lock in B2) and recorded the dependency. Also: `metadata.create_all(engine, ...)` for
the ledger table runs on its *own* connection and commits independently of the session's
transaction — which is what we want (the ledger table should exist regardless), but it's a
trap if you ever assume create_all participates in the surrounding transaction.
**Takeaway:** "Migrations are atomic" is a Postgres property, not a SQL one. Any future
second-database support has to re-prove it, not assume it.

## 2026-06-27 — Sharing a helper module between tests: absolute import, not relative (B4)
**Context:** The B4 registry test needs a fake plugin in its *own* module (so the consumer
provably never imports the implementation). Put it in `packages/nucleus/tests/_fake_tax_plugin.py`.
**Surprise:** `from ._fake_tax_plugin import …` fails — `packages/nucleus/tests` has no
`__init__.py`, so pytest's default `prepend` import mode loads the test as a *top-level*
module with no parent package, and the relative import has nothing to resolve against.
`apps/api/tests` *is* a package (it has `__init__.py`), which masks the asymmetry.
**Resolution:** Use a plain absolute import (`from _fake_tax_plugin import …`); prepend mode
puts the test's own directory on `sys.path`, so a sibling module imports directly. Keep
shared-fixture module names unique across test dirs to avoid collisions.
**Takeaway:** In a src-layout repo where test dirs aren't packages, import sibling test
helpers absolutely, not relatively — relative imports need an `__init__.py` that isn't there.

## 2026-06-27 — Two non-obvious DB-layer defaults: constraint naming + expire_on_commit (B3)
**Context:** Building `nucleus.db` (declarative `Base`, session factory, unit of work).
**Surprise:** Two defaults that bite later, not now. (1) Without a `MetaData`
**naming convention**, SQLAlchemy lets the database auto-name constraints/indexes; those
names differ across engines and shift between Alembic autogenerate runs, so migrations get
noisy and downgrades — which `DROP CONSTRAINT` *by name* — become unreliable. Set the
convention on the `Base` metadata once, up front. (2) `sessionmaker`'s default
`expire_on_commit=True` expires every loaded attribute on commit; a route that serializes
the just-committed object into its response then triggers a reload *after* the request's
transaction is gone. `expire_on_commit=False` avoids it.
**Resolution:** Pinned a naming convention on `Base.metadata`; built the session factory
with `expire_on_commit=False`. Neither changes behaviour today; both prevent a confusing
failure in B10/B13.
**Takeaway:** Decide constraint naming and commit-expiry at the moment you create the
declarative base — retrofitting either after migrations and routes exist is the painful
path.

## 2026-06-27 — Postgres native `SEQUENCE` can't do gapless; proving the lock needs real Postgres (B2)
**Context:** Building `nucleus.primitives.sequence` and proving "no gaps, no duplicates
under parallel workers."
**Surprise:** Two things. (1) A Postgres `SEQUENCE`/`SERIAL` is the obvious tool and the
wrong one — it *caches* values and deliberately does **not** roll back on a failed
transaction, so it leaves gaps. Gapless numbering must be a counter *row* taken under
`SELECT … FOR UPDATE`, tied to the caller's transaction. (2) The property can't be proven
on SQLite: it serializes writes at the database level and treats `FOR UPDATE` as a no-op,
so a green SQLite test would prove nothing about the row lock. You need real Postgres with
real threads/connections. The build sandbox has no Docker daemon (see B0 lesson), but the
`postgresql-16` binaries are installed — you can `initdb` + `pg_ctl start` a throwaway
cluster **as the `postgres` user** (Postgres refuses to run as root) on a high port and
point `DATABASE_URL` at it.
**Resolution:** Row + `FOR UPDATE`; threaded test asserts the issued set equals `1..N`
exactly; a Barrier-coordinated lock-less variant proves duplicates appear without the lock,
so we know the lock is load-bearing. The `pg_engine` fixture skips when no Postgres is
reachable, so `make test` stays green on a laptop without a DB and only proves the property
when one is up (`make up`).
**Takeaway:** Don't reach for `SERIAL` when the requirement is *gapless* — it's the wrong
guarantee. And when a property only holds under real DB locking, test it against real
Postgres or don't claim it; a local `initdb` cluster (run as `postgres`) is enough when
Docker isn't.

## 2026-06-23 — uv virtual workspace root + cross-package sources (B0)
**Context:** Standing up the uv workspace so `apps/api` can depend on the in-repo
`nucleus`/`invoicing`/`payments`/`tax_co` packages by clean import name.
**Surprise:** Two things worth remembering. (1) The workspace root needs no
`[project]` table — a "virtual" root with just `[tool.uv.workspace]` works and keeps
the root a coordinator, not a deployable. (2) `[tool.uv.sources]` declared at the
root (`{ workspace = true }`) is *inherited* by all members, so each member can list
`nucleus` as a dep without re-declaring the source. Dir names are prefixed
(`module-invoicing`) but the wheel package is the clean name via
`[tool.hatch.build.targets.wheel] packages = ["src/<name>"]`.
**Resolution:** Virtual root + inherited sources + hatchling src-layout. `uv sync`
installs all four packages editable; `make test` passes a host smoke test.
**Takeaway:** Prefix-dir / clean-import (README §3) is a ~3-line hatchling setting,
not a fight. Keep the workspace root package-less.

## 2026-06-23 — No Docker daemon in the build sandbox; Starlette wants httpx2
**Context:** Verifying B0's `make up` (Postgres) and the host smoke test.
**Surprise:** (1) The remote build sandbox has no Docker daemon, so `make up`
can't be exercised live here; `docker compose config` validates the file
statically, which is the most we can prove in-sandbox. (2) Starlette 1.3's
TestClient emits a deprecation: it wants `httpx2` instead of `httpx`. Harmless
today (tests pass on httpx 0.28) but it will bite when we pin versions.
**Resolution:** Rely on `docker compose config` for compose correctness in CI/sandbox;
left the httpx warning alone for B0.
**Takeaway:** Don't assume Docker is runnable in every environment — validate compose
statically and gate live `make up` on a machine with the daemon. Revisit the
httpx2 migration when we lock the test deps.

## 2026-06-23 — Foundation docs created; no code lessons yet
**Context:** Bootstrapping the repo's agent-facing documentation before any code exists.
**Surprise:** None — this is the seed entry.
**Takeaway:** Every future agent: when something bites you, the lesson goes here, not just
in a commit message. The owner reads this file to learn what the codebase taught us.
