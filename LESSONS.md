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

## 2026-06-28 — WeasyPrint just worked here; verify deps before assuming the fallback (B11)
**Context:** B11's PDF step. The README and CLAUDE.md §3 both pre-warn that WeasyPrint's
native deps (Pango/cairo) often fight the image, and sanction a ReportLab/headless-Chromium
fallback.
**Surprise:** No fight at all — `ldconfig -p` already listed libpango/libcairo/libharfbuzz,
and `uv run --with weasyprint python -c "import weasyprint"` imported and rendered a PDF
first try. The pre-warned hazard wasn't present in this environment.
**Resolution:** Kept WeasyPrint, took no fallback, and recorded that the B15 Dockerfile must
keep those system libs so the assumption holds in the shipped image. Also: tests assert PDF
*content* (NIT, totals, "no .00") by extracting text with pypdf — much stronger than checking
the `%PDF-` magic bytes alone.
**Takeaway:** A documented hazard is a prompt to *probe*, not to pre-emptively detour. A
two-minute `ldconfig`/import check settled it; reaching for the fallback first would have
added ReportLab complexity for a problem we didn't have. Verify before you trust — including
trusting the warning.

## 2026-06-28 — Event-bus decoupling can't beat the dependency direction (B12)
**Context:** The payments stub said it should "cooperate with invoicing through the event
bus, not a hard import." Tried to honor that for recording a payment (which must move invoice
status).
**Surprise:** It doesn't work cleanly. The thing that reacts to a payment is *invoicing* (it
owns status), so an event-driven design makes invoicing the subscriber — which means
invoicing must import the event type. If payments owns the event (the natural concept),
invoicing→payments is a *wrong-direction* dependency (invoicing is the earlier/lower module
and must not depend on the later one). Putting the event in invoicing fixes the direction but
is conceptually backwards. The event bus only decouples cleanly when the *publisher* is the
lower module and the *subscriber* is higher — here it's the reverse.
**Resolution:** Used a plain downward import (payments → invoicing), which the build spine
already sanctions, and kept the whole action in one transaction. The bus stays the right tool
for lower-publishes/higher-subscribes flows; it's not a universal decoupler.
**Takeaway:** "Use events to decouple" has a precondition: the dependency must run the same
way as the event flow. When the reactor is the lower-level module, an import is honest and an
event is a contortion. Don't add a bus hop to dodge a dependency the architecture already
permits.

## 2026-06-28 — Mounting module routes the host hasn't configured: dependency_overrides (B10)
**Context:** Modules define FastAPI routes, but the engine and auth secret live in the host.
The route can't import the host's session factory without inverting the dependency.
**Surprise/technique:** FastAPI's `app.dependency_overrides` is the clean seam. The module
declares `Depends(get_session)` / `Depends(get_principal)` against *placeholder* functions
exported by the nucleus (which just raise "not configured"); the host swaps them for the real
session-per-request and authenticator at boot. The module stays host-agnostic, and an
unconfigured placeholder fails loudly instead of silently. Second gotcha: once `create_app`
runs migrations, `app.main:app` touches the DB *at import* — so tests must build the app via
`create_app` against a test DB, not `from app.main import app` (which would need a DB just to
collect). Third: registry/route singletons persist across `create_app` calls in one process,
so bootstrap must `clear()` them to stay idempotent (or register hooks must use `replace`).
**Resolution:** placeholder deps + overrides; tests call `create_app`; bootstrap clears
registries before composing.
**Takeaway:** Inversion at the HTTP layer is `dependency_overrides`, the same shape as the
registry for plugins — module asks by name, host supplies. And watch what runs at *import*
time once the app does real work at construction.

## 2026-06-28 — CO IVA rates verified; "excluded" ≠ "exempt" but we fold them (B9)
**Context:** Building the CO tax plugin; CLAUDE.md §3 requires verifying rates against current
DIAN rules, not memory.
**Surprise/confirmation:** Rates hold as the README assumed — general **19%**, reduced
**5%**, and 0% — but the 0% bucket hides a real distinction Colombian tax law makes:
*excluido* (excluded, art. 424) vs *exento* (exempt, art. 477). Both charge 0% output IVA,
but **exempt** sellers can still credit *input* IVA while **excluded** ones cannot. v1 models
only output tax, so it collapses both into one `excluded` (0%) code. Also: the tax codes are
rate *buckets*, not product classifications — the app does not decide whether a given good is
5% or 19%; the user picks the code per line.
**Resolution:** Implemented 19/5/0; documented the excluded/exempt simplification in code and
ARCHITECTURE; recorded the source (Estatuto Tributario arts. 420–513, DIAN, June 2026).
**Takeaway:** When a tax rate looks trivially right, the trap is usually in the *0% cases* —
"zero-rated" splits into legally distinct kinds. Fine to simplify for v1, but say so out loud
so the next person knows it's a deliberate scope cut, not an oversight.

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
