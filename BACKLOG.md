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

## B0 — Workspace + tooling  `[ ]`
Stand up the monorepo skeleton so everything else has a home.
- uv workspace root (`pyproject.toml`, members = `apps/api` + `packages/*`), `uv.lock`.
- `ruff.toml`, `docker-compose.yml` (Postgres + api + web), root `Makefile`
  (`dev`, `gen-types`, `migrate`, `test`, `up`), `.env.example`.
- **Done when:** `make up` brings up Postgres; `make test` runs (even if empty); the
  package layout matches `README.md` §3.

## B1 — `nucleus.primitives.money`  `[ ]`  · Proves: *Money correctness*
`Money` value object with **per-currency precision** (COP = 0 decimals, not a hardcoded 2).
- Mixing currencies in arithmetic **raises**, never silently coerces.
- **Done when:** tests show COP rounds/renders at 0 decimals, a 2-decimal currency works,
  and cross-currency ops raise.

## B2 — `nucleus.primitives.sequence`  `[ ]`  · Proves: *Gapless numbering*
Gapless sequential generator backed by a **DB row lock** (must survive multiple workers).
- **Done when:** a concurrency test issues numbers in parallel and shows **no gaps, no
  duplicates**.

## B3 — `nucleus.db`  `[ ]`  · Proves: *Atomicity (foundation)*
Engine, session-per-request, declarative `base`, and a unit-of-work.
- **Done when:** tests show a commit persists and a raised error inside the unit-of-work
  rolls everything back.

## B4 — `nucleus.registry` + `nucleus.contracts`  `[ ]`  · Proves: *Plugin inversion (foundation)*
Model / route / event / tax / payment registries; `TaxCalculator` and `PaymentProvider`
Protocols.
- **Done when:** a fake calculator can register under a jurisdiction and be resolved from
  the registry with **no direct import** by the consumer.

## B5 — `nucleus.modules` loader  `[ ]`
Manifest format, dependency **toposort**, per-module migration runner, install/upgrade
lifecycle.
- **Done when:** two fake modules with a declared dependency load in correct order; a
  cycle is rejected with a clear error.

## B6 — `nucleus.events.bus`  `[ ]`
In-process event bus (publish/subscribe within the shared transaction).
- **Done when:** a published event reaches its subscriber; semantics around the
  transaction boundary are documented in `docs/ARCHITECTURE.md`.

## B7 — `nucleus.api`  `[ ]`
API gateway helpers + JWT auth.
- **Done when:** a protected route rejects a missing/invalid token and accepts a valid one.

## B8 — `module-invoicing` (entities)  `[ ]`
`Party`, `Invoice`, `InvoiceLine`; invoice numbering via `Sequence` (B2).
- `Party` carries jurisdiction + tax id (NIT/Cédula).
- **Done when:** an invoice with lines persists and receives a gapless number.

## B9 — `plugin-tax-co`  `[ ]`  · Proves: *Plugin inversion*
`ColombiaTaxCalculator` for `jurisdiction = "CO"`; **entry-point** registration
(`nucleus.plugins`). Codes: `iva_19` (19%), `iva_5` (5%), `excluded` (0%).
- Invoicing computes IVA **via the registry**, never `import tax_co`.
- **Done when:** totals are correct via the plugin; a test shows that **removing the
  plugin** makes a `CO` request fail with a clear "no tax plugin" error — zero core change
  needed to add/remove a jurisdiction. **Verify rates against current DIAN rules first.**

## B10 — `apps/api` host (bootstrap)  `[ ]`
`bootstrap.py`: discover modules → toposort → migrate → mount routers/plugins. First
end-to-end vertical slice.
- **Done when:** `GET /docs` is live and the create-client → create-invoice slice works
  over HTTP.

## B11 — PDF generation  `[ ]`  · Proves: *The output is real*
Invoice → HTML template → PDF (WeasyPrint). Shows line items, IVA breakdown, totals,
client NIT, COP with 0 decimals.
- **Done when:** a valid PDF downloads for a CO invoice. If WeasyPrint's native deps fight
  Docker, fall back (headless-Chromium / ReportLab) and **record why** in
  `docs/ARCHITECTURE.md` and `LESSONS.md`.

## B12 — `module-payments`  `[ ]`  · Proves: *Atomicity*
`Payment` + `LedgerEntry`; invoice status transitions (`draft → issued → partial → paid`)
posted **atomically** with ledger entries in the **same transaction**.
- **Done when:** a test shows status + ledger commit together and **roll back together** on
  failure. Include the "break it out-of-process" demonstration showing why same-process is
  what makes atomicity possible.

## B13 — Contract generation  `[ ]`  · Proves: *Contract honesty*
OpenAPI (from FastAPI) → `openapi-typescript` → `apps/web/lib/types.ts`, wired into the
`Makefile`.
- **Done when:** `make gen-types` regenerates `types.ts`; the file is never hand-edited.

## B14 — `apps/web`  `[ ]`
Next.js screens: client list/create, invoice create/list/detail, mark-paid, PDF download —
consuming the **generated** types from B13.
- **Done when:** the full user flow in `README.md` §7.A is clickable in a browser.

## B15 — Packaging & docs  `[ ]`
`Dockerfile.api`, `Dockerfile.web`, compose, README run instructions; finalize
`docs/ARCHITECTURE.md` (decision record) and `docs/plugin-sdk.md` ("write a tax plugin in
~50 lines").
- **Done when:** a clean `docker compose up` brings up db + api + web and the §7.A flow
  works end to end.

---

## Acceptance checklist (from README §7.B — the project isn't v1.0.0 until all hold)

- [ ] **Atomicity** proven by test (B12).
- [ ] **Gapless numbering** proven by concurrency test (B2).
- [ ] **Plugin inversion** proven: CO resolved from registry, no direct import, removable
      cleanly (B4, B9).
- [ ] **Money correctness**: COP 0 decimals, currency mixing raises (B1).
- [ ] **Contract honesty**: `types.ts` generated by one Make target (B13).
- [ ] **Real output**: a valid Colombian PDF invoice with correct IVA (B11).
