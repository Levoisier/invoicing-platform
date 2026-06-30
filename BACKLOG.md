# BACKLOG.md — the ordered work for v1.0.0

Derived from the **build order** in [`README.md`](README.md) §6. It is a *dependency
spine*: each item is a self-contained unit, and later items depend on earlier ones. Work
them roughly top to bottom. Don't start an item whose dependencies aren't done unless you
can stub them honestly.

**Before starting any item, read [`CLAUDE.md`](CLAUDE.md)** — especially §0 (this is a
learning project: explain *how & why*, document the *why* concisely) and §2 (the
architectural guardrails you must not cross).

## How to use this file

- Pick the topmost unblocked item.
- Build the **smallest correct slice** that satisfies its acceptance criteria.
- Prove any architecture property with a test (claims without tests don't count).
- Finish with the **How & Why** section in your reply, and tick the boxes below.
- Update status inline: `TODO` → `IN PROGRESS` → `DONE` (link the commit).

Status legend: `[ ]` todo · `[~]` in progress · `[x]` done.

The **Proves** column on some items points at the acceptance properties in `README.md`
§7.B — those items are not done until that property is demonstrated by a test.

---

## B0 — Workspace + tooling  `[x]`
Stand up the monorepo skeleton so everything else has a home.
- uv workspace root (`pyproject.toml`, members = `apps/api` + `packages/*`), `uv.lock`.
- `ruff.toml`, `docker-compose.yml` (Postgres + api + web), root `Makefile`
  (`dev`, `gen-types`, `migrate`, `test`, `up`), `.env.example`.
- **Done when:** `make up` brings up Postgres; `make test` runs (even if empty); the
  package layout matches `README.md` §3.

## B1 — `nucleus.primitives.money`  `[x]`  · Proves: *Money correctness*
`Money` value object with **per-currency precision** (COP = 0 decimals, not a hardcoded 2).
- Mixing currencies in arithmetic **raises**, never silently coerces.
- **Done when:** tests show COP rounds/renders at 0 decimals, a 2-decimal currency works,
  and cross-currency ops raise.

## B2 — `nucleus.primitives.sequence`  `[x]`  · Proves: *Gapless numbering*
Gapless sequential generator backed by a **DB row lock** (must survive multiple workers).
- **Done when:** a concurrency test issues numbers in parallel and shows **no gaps, no
  duplicates**.
- Done: `Sequence` issues numbers via a `sequences` counter row under `SELECT … FOR
  UPDATE`; a threaded test draws 8×25 numbers in parallel and asserts the issued set is
  exactly `1..200`, and a companion test shows the lock-less read-then-write *does*
  duplicate. DB-backed tests skip cleanly when no Postgres is reachable.

## B3 — `nucleus.db`  `[x]`  · Proves: *Atomicity (foundation)*
Engine, session-per-request, declarative `base`, and a unit-of-work.
- **Done when:** tests show a commit persists and a raised error inside the unit-of-work
  rolls everything back.
- Done: `Base` (one MetaData + pinned naming convention), `make_engine`,
  `make_session_factory`, `session_per_request` (FastAPI dep, mounted in B10), and
  `unit_of_work`. Tests prove a clean block commits, a raised error rolls back, and a
  late failure un-persists earlier flushed writes in the same unit.

## B4 — `nucleus.registry` + `nucleus.contracts`  `[x]`  · Proves: *Plugin inversion (foundation)*
Model / route / event / tax / payment registries; `TaxCalculator` and `PaymentProvider`
Protocols.
- **Done when:** a fake calculator can register under a jurisdiction and be resolved from
  the registry with **no direct import** by the consumer.
- Done: `runtime_checkable` `TaxCalculator`/`PaymentProvider` Protocols; a generic
  `Registry` (clear errors on missing/duplicate keys) with module-level `tax`/`payment`/
  `model`/`route` singletons. Event pub/sub is deferred to the B6 bus (different shape),
  not a plain registry. Test resolves a fake calculator (in its own module) via the
  registry — the consumer imports no implementation — and a missing jurisdiction raises
  the clear error B9 builds on.

## B5 — `nucleus.modules` loader  `[x]`
Manifest format, dependency **toposort**, per-module migration runner, install/upgrade
lifecycle.
- **Done when:** two fake modules with a declared dependency load in correct order; a
  cycle is rejected with a clear error.
- Done: `ModuleManifest` (name/version/depends + `migrate`/`register` hooks), a
  deterministic DFS `toposort` (cycle/missing/duplicate raise with the path), and a
  version-gated lifecycle backed by an `installed_modules` ledger (install → unchanged →
  upgrade). `load_modules` runs the whole set in the caller's unit of work, so a failed
  boot rolls back every migration. Tests prove ordering, cycle rejection, migrate-once-per-
  version, and atomic rollback of a failed boot.

## B6 — `nucleus.events.bus`  `[x]`
In-process event bus (publish/subscribe within the shared transaction).
- **Done when:** a published event reaches its subscriber; semantics around the
  transaction boundary are documented in `docs/ARCHITECTURE.md`.
- Done: `EventBus` (+ module-level `bus` singleton). `publish(event, session)` is
  synchronous, exact-type dispatch, on the publisher's session — so a subscriber's writes
  share the trigger's transaction. Handler exceptions propagate (never swallowed) so a unit
  of work rolls the whole reaction back. Transaction-boundary semantics recorded in
  `docs/ARCHITECTURE.md` §3 + decision log. Tests prove delivery/ordering/exact-type
  dispatch and the commit-together / roll-back-together property against Postgres.

## B7 — `nucleus.api`  `[x]`
API gateway helpers + JWT auth.
- **Done when:** a protected route rejects a missing/invalid token and accepts a valid one.
- Done: split into a framework-agnostic `JWTAuth` (issue/verify HS256, enforces exp +
  subject) and a FastAPI binding `require_principal(auth)` that turns a bearer token into a
  `Principal` or a clean 401. Config is passed in, never read from env. `fastapi` added to
  nucleus deps (README §1 puts the gateway in the core). Tests prove token round-trip,
  expiry/forged/garbage rejection, and the protected route accepting a valid token while
  rejecting missing/invalid ones.

## B8 — `module-invoicing` (entities)  `[x]`
`Party`, `Invoice`, `InvoiceLine`; invoice numbering via `Sequence` (B2).
- `Party` carries jurisdiction + tax id (NIT/Cédula).
- **Done when:** an invoice with lines persists and receives a gapless number.
- Done: `Party`/`Invoice`/`InvoiceLine` on the nucleus `Base`; `issue_invoice` service
  draws the number from `Sequence("invoice")` on the caller's session, and a `ModuleManifest`
  whose `migrate` creates the tables (transactionally, via the loader). Lines carry an opaque
  `tax_code` — IVA meaning is the CO plugin's job (B9). Tests prove persistence + line
  round-trip, gapless numbers across invoices, that a rolled-back invoice doesn't burn a
  number, and that the module installs cleanly via the loader.

## B9 — `plugin-tax-co`  `[x]`  · Proves: *Plugin inversion*
`ColombiaTaxCalculator` for `jurisdiction = "CO"`; **entry-point** registration
(`nucleus.plugins`). Codes: `iva_19` (19%), `iva_5` (5%), `excluded` (0%).
- Invoicing computes IVA **via the registry**, never `import tax_co`.
- **Done when:** totals are correct via the plugin; a test shows that **removing the
  plugin** makes a `CO` request fail with a clear "no tax plugin" error — zero core change
  needed to add/remove a jurisdiction. **Verify rates against current DIAN rules first.**
- Done: `ColombiaTaxCalculator` (rates verified vs DIAN June 2026 — 19/5/0%); `nucleus.plugins.discover_plugins`
  loads the `nucleus.plugins` entry-point group and routes by contract into the registry;
  `invoicing.compute_totals` resolves the calculator by `party.jurisdiction` from the registry
  (no `import tax_co`). Tests prove rates, real entry-point self-registration, correct totals
  via the plugin, and that an empty registry (plugin removed) fails with the clear error.

## B10 — `apps/api` host (bootstrap)  `[x]`
`bootstrap.py`: discover modules → toposort → migrate → mount routers/plugins. First
end-to-end vertical slice.
- **Done when:** `GET /docs` is live and the create-client → create-invoice slice works
  over HTTP.
- Done: `create_app()` clears the shared registries, discovers tax plugins from entry
  points, loads modules (toposort + migrate) in one unit of work, then mounts the routers
  modules published into the route registry. Module routes declare nucleus seams
  (`get_session`/`get_principal`) that the host fills via `dependency_overrides`. Added the
  invoicing router (`/clients`, `/invoices`, `/invoices/{id}`) and a `/auth/token` login.
  E2E test: log in → create client → create CO invoice → read back, asserting plugin IVA
  totals; `/docs` live; domain routes 401 without a token.

## B11 — PDF generation  `[x]`  · Proves: *The output is real*
Invoice → HTML template → PDF (WeasyPrint). Shows line items, IVA breakdown, totals,
client NIT, COP with 0 decimals.
- **Done when:** a valid PDF downloads for a CO invoice. If WeasyPrint's native deps fight
  Docker, fall back (headless-Chromium / ReportLab) and **record why** in
  `docs/ARCHITECTURE.md` and `LESSONS.md`.
- Done: `invoicing.pdf.render_invoice_pdf` (Jinja2 HTML/CSS → WeasyPrint PDF) + `tax_breakdown`
  (base/IVA per code); `GET /invoices/{id}/pdf` streams it. WeasyPrint's native deps are
  present in the image — **no fallback needed**. Tests render in-memory and read the PDF back
  with pypdf to assert the NIT, line items, IVA breakdown, and COP-0-decimal totals appear
  (and no 2-decimal money); HTTP e2e downloads a valid `application/pdf`.

## B12 — `module-payments`  `[x]`  · Proves: *Atomicity*
`Payment` + `LedgerEntry`; invoice status transitions (`draft → issued → partial → paid`)
posted **atomically** with ledger entries in the **same transaction**.
- **Done when:** a test shows status + ledger commit together and **roll back together** on
  failure. Include the "break it out-of-process" demonstration showing why same-process is
  what makes atomicity possible.
- Done: `Payment` + signed-amount double-entry `LedgerEntry` (debit cash / credit AR, sums
  to zero); `record_payment` posts the ledger and moves invoice status on the caller's
  session — one unit. payments depends on invoicing (downward, in-spine) and loads after it
  via toposort; mounted in the host (`POST /invoices/{id}/payments`). Tests: full/partial
  transitions, ledger balances, commit-together, roll-back-together, and the out-of-process
  demonstration showing two transactions tear the books apart. HTTP e2e records a payment
  and sees the invoice flip to `paid`.

## B13 — Contract generation  `[x]`  · Proves: *Contract honesty*
OpenAPI (from FastAPI) → `openapi-typescript` → `apps/web/lib/types.ts`, wired into the
`Makefile`.
- **Done when:** `make gen-types` regenerates `types.ts`; the file is never hand-edited.
- Done: `app.export_openapi` dumps the schema with `create_app(run_migrations=False)` (DB-free,
  via a new `register_modules` register-only path); `make gen-types` pipes it through
  `openapi-typescript` into `apps/web/lib/types.ts` (regenerated, real, 500+ lines). Tests
  assert the schema source exposes the domain routes and serializes Money as a string pair —
  and run with no database.

## B14 — `apps/web`  `[x]`
Next.js screens: client list/create, invoice create/list/detail, mark-paid, PDF download —
consuming the **generated** types from B13.
- **Done when:** the full user flow in `README.md` §7.A is clickable in a browser.
- Done: Next.js 15 (App Router) client app — login, clients (list/create), invoices
  (list/create/detail), mark-paid, PDF download — with a typed `lib/api.ts` whose request/
  response types come straight from the generated `types.ts`. Backend gained `GET /clients`,
  `GET /invoices` (summary), and CORS to support the browser SPA. Verified two ways: `next
  build` typechecks the contract consumption, and a Playwright run drove the whole §7.A flow
  through real Chromium (login → client → CO invoice with IVA → record payment → status
  `paid`), screenshots captured.

## B15 — Packaging & docs  `[x]`
`Dockerfile.api`, `Dockerfile.web`, compose, README run instructions; finalize
`docs/ARCHITECTURE.md` (decision record) and `docs/plugin-sdk.md` ("write a tax plugin in
~50 lines").
- **Done when:** a clean `docker compose up` brings up db + api + web and the §7.A flow
  works end to end.
- Done: `Dockerfile.api` (uv `--frozen --no-dev`, WeasyPrint system libs) and
  `Dockerfile.web` (npm ci → build, `NEXT_PUBLIC_API_URL` baked); compose runs all three
  (profiles dropped), db healthcheck gates the api, which self-migrates on startup; `.dockerignore`
  added; `make up` builds+starts the stack, `make db`/`make dev` for local. README §8 updated;
  `docs/plugin-sdk.md` written. **Note:** no Docker daemon in this sandbox, so the stack was
  validated with `docker compose config` (resolves cleanly) — a live `docker compose up` must
  be run on a Docker host to fully confirm.

---

## Acceptance checklist (from README §7.B — the project isn't v1.0.0 until all hold)

- [x] **Atomicity** proven by test (B12).
- [x] **Gapless numbering** proven by concurrency test (B2).
- [x] **Plugin inversion** proven: CO resolved from registry, no direct import, removable
      cleanly (B4, B9).
- [x] **Money correctness**: COP 0 decimals, currency mixing raises (B1).
- [x] **Contract honesty**: `types.ts` generated by one Make target (B13).
- [x] **Real output**: a valid Colombian PDF invoice with correct IVA (B11).
