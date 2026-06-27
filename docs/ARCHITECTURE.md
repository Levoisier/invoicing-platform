# Architecture & Decision Record

The deep architecture for the invoicing platform, plus the **decision record** where we
write down *why* a structural choice was made. [`README.md`](../README.md) is product
truth (what we're building); [`CLAUDE.md`](../CLAUDE.md) is process truth (how we work);
**this file is design truth** (why the code is shaped this way).

> Learning-project note: this file exists so the owner can reopen it later and reconstruct
> the reasoning. Keep entries concise and *why*-focused (per `CLAUDE.md` §0.2). When a
> decision is too big for an inline code comment, it belongs here.

---

## 1. The shape: Nucleus + Modules + Plugins + Host

```
        ┌──────────────────────────────────────────────┐
        │                  Host (apps/api)              │  composes an "edition"
        │   discover → toposort → migrate → mount       │  by its dependencies
        └───────────────┬──────────────────────────────┘
                        │ depends on
        ┌───────────────▼──────────────────────────────┐
        │                  Nucleus                      │  the reusable core
        │  primitives · db/UoW · contracts · registry   │  built once, owns nothing
        │  · module loader · event bus · api/auth       │  domain-specific
        └───┬───────────────────────────────────┬───────┘
            │ attach (in-process, shared txn)    │ implement contracts (resolved
            ▼                                    ▼  via registry, never imported)
   ┌──────────────────┐  ┌──────────────────┐   ┌─────────────────────────┐
   │ module-invoicing │  │ module-payments  │   │ plugin-tax-co           │
   │ Invoice, lines,  │  │ Payment, Ledger  │   │ ColombiaTaxCalculator   │
   │ numbering, PDF   │  │ (atomic crux)    │   │ (entry point, CO/IVA)   │
   └──────────────────┘  └──────────────────┘   └─────────────────────────┘
```

- **Nucleus** — domain primitives (`Money`, `Sequence`, `Party`), the DB/transaction
  layer, the registries, the module loader, the event bus, and API/auth. It defines
  *contracts* and never imports a concrete plugin.
- **Module** — an in-process domain unit (`invoicing`, `payments`) that attaches to the
  nucleus and **shares its DB transaction**.
- **Plugin/Provider** — a swappable implementation of a nucleus contract (e.g. a
  `TaxCalculator`). Self-registers via entry points; the core asks the **registry** for it.
- **Host** — the deployable (`apps/api`) that *composes* a chosen set of modules + plugins.
  The edition is decided by its dependency list, nothing more.

---

## 2. The two load-bearing decisions

Everything else is detail. These two are the project.

### 2.1 Plugin contract (inversion of control)

**Decision:** the nucleus defines an interface (`TaxCalculator`); a plugin implements and
**registers** it via an entry point; consumers ask the **registry**, never `import`.

**Why:** adding a jurisdiction must be *install a package, zero core change*. The moment
`module-invoicing` imports `tax_co`, that property dies and the project is just a CRUD app
with a tax function. The registry seam is the whole thesis.

**Consequence / cost:** indirection. Resolving a calculator by jurisdiction string is less
obvious than a direct call, and a missing plugin is a runtime failure, not a compile error.
We accept that and make the failure *loud and clear* ("no tax plugin for CO"). The payoff —
demonstrable extensibility — is the point.

**Proven by:** removing `plugin-tax-co` from the host's deps makes a `CO` request fail
cleanly, with no core edit required (README §7.B, BACKLOG B9).

### 2.2 Transactional intimacy (shared DB session)

**Decision:** modules run **in-process, same language, sharing one DB session**. An
invoice's status change and its ledger entries commit or roll back as a **single unit**.

**Why:** financial correctness. A payment that updates invoice status but fails to post the
ledger entry (or vice versa) is a corrupt book. Atomicity here is non-negotiable, and the
cheapest reliable way to get it is one transaction in one process — not a distributed saga.

**Consequence / cost:** modules can't be separate services; they must be same-runtime.
That's a deliberate trade — we give up service independence to *buy* atomicity. v1 includes
a "break it out-of-process" demonstration test precisely to show *why* this constraint
exists, not just that it's followed.

**Proven by:** a test showing status + ledger commit together and roll back together
(README §7.B, BACKLOG B12).

---

## 3. Supporting decisions

- **`Money` with per-currency precision.** COP uses **0 decimals**; a hardcoded 2 would
  render every Colombian total wrong. Precision is a property of the currency, not a global
  constant. Cross-currency arithmetic **raises** rather than silently coercing — silent
  coercion is how money bugs hide.
- **Gapless numbering via DB row lock.** Invoice numbers must be sequential with no gaps,
  and must hold under **multiple API workers**. An app-level counter can't guarantee that
  across processes; a row lock in the same transaction as the insert can. The lock is the
  reason, and it's worth the contention cost on the numbering row.
- **Per-module Alembic migrations, aggregated at the host.** Each module owns its schema;
  `infra/alembic/env.py` aggregates them and the loader runs them in **toposort** order so
  a module's tables exist before a dependent module's. Keeps modules self-contained while
  giving the host one coherent migration run.
- **Generated API types (`apps/web/lib/types.ts`).** The frontend's types are **emitted
  from the live OpenAPI schema** via `openapi-typescript`. Hand-editing them would let the
  contract and the client drift silently; generation makes drift a build step, not a bug.
  Hence: never hand-edit that file.
- **Dir names prefixed, import names clean.** Distribution dirs are `module-*` / `plugin-*`
  so the tree reads at a glance; import names stay clean (`import invoicing`, `import
  tax_co`). Cosmetic-but-deliberate: legibility of the repo vs. ergonomics of the code,
  and we get both.

---

## 4. Known risks & sanctioned fallbacks

- **WeasyPrint native deps (Pango/cairo)** can fight the Docker image. The README sanctions
  a fallback to headless-Chromium print or ReportLab. If you take it, **record why here**
  and in `LESSONS.md` — a future reader needs to know the PDF path changed and what forced
  it.
- **CO/IVA rates drift.** v1 targets *correct architecture with plausible rates*, not
  certified DIAN compliance. Verify rates against current regulation before presenting
  output as accounting-grade.
- **Library majors move** (SQLAlchemy 2.x, Pydantic v2, FastAPI, openapi-typescript).
  Verify current majors before coding; note any version-specific workaround here.

---

## 5. Decision log

Append a dated entry whenever you make or revise a structural decision. Keep it tight:
**decision · why · cost.** Newest on top.

<!-- Add decisions below, newest first. -->

### 2026-06-27 — `nucleus.modules` loader: two-phase lifecycle, atomic boot (B5)
**Decision:** a module is a `ModuleManifest` (name, version, `depends`, and two hooks);
`load_modules` toposorts the set, then for each module runs a **schema phase** (`migrate`,
gated by a DB `installed_modules` ledger so it runs once per version) and a **runtime
phase** (`register`, every boot). The whole load runs inside the caller's unit of work.
**Why two phases:** migrations are persistent and must run once per version; router/registry
wiring lives in process memory and must re-run every start. Collapsing them re-migrates on
every boot or drops wiring after a restart. **Why a DB ledger, not a file/memory:** the
truth about what schema exists is in the database, and multiple API workers must agree on
it. **Why depend by *name*, not import:** a module never imports a peer — the loader
resolves order from the set it's given, preserving the one-directional dependency rule.
**Why one transaction for the whole boot:** a module failing mid-load rolls back every
prior migration and ledger row, so there's no half-installed state to hand-repair. **Cost:**
(1) the version gate treats *any* version difference as "run migrate" — it doesn't reason
about up/down, so the hook owns reaching its version; (2) running all migrations in one
transaction means a huge migration set is one big lock — fine at this scale, revisit if
boots get heavy; (3) concurrent workers booting at once could race the ledger — the host
runs the loader once at startup (the `make migrate` seam), which sidesteps it for v1.

### 2026-06-27 — `nucleus.registry` + `nucleus.contracts`: the inversion seam (B4)
**Decision:** contracts are `runtime_checkable` `Protocol`s (`TaxCalculator`,
`PaymentProvider`) in the core; implementations register into a generic `Registry` keyed by
a string (jurisdiction, provider key) and are resolved by key, never imported. Registries
are **module-level singletons** (`tax`, `payment`, `model`, `route`). **Why Protocols, not
ABCs:** structural typing lets an external plugin satisfy the contract without importing the
core's base class — the dependency only ever points plugin→core, never core→plugin.
**Why singletons:** registration is global, one-time boot wiring (entry-point discovery,
B9) and every consumer must see one shared table. **Why no `event` registry:** pub/sub is
one-event-to-many-subscribers — a different shape the B6 bus owns; faking it as a key→value
registry now would mislead. **Cost:** (1) a missing implementation is a *runtime* miss, so
we invest in loud, specific errors ("no TaxCalculator registered for jurisdiction 'CO'");
(2) singletons hold global state, so tests must `clear()` them — the price of the shared
table.

### 2026-06-27 — `nucleus.db`: unit-of-work as the single transaction boundary (B3)
**Decision:** atomicity is expressed once, as a `unit_of_work` context manager that commits
a block on clean exit and rolls the whole block back on any exception; the FastAPI
`session_per_request` dependency wraps each request in one. Models share one declarative
`Base`/`MetaData` carrying a pinned constraint **naming convention**. **Why:** every module
inheriting one transaction policy is what makes "invoice status + ledger commit or roll
back together" (B12) a property of the platform rather than something each module
re-implements (and gets subtly wrong). The naming convention keeps Alembic autogenerate
deterministic and downgrades (which drop constraints by name) safe. `expire_on_commit=False`
on the sessionmaker lets routes serialize just-written objects after commit without a
post-transaction reload. **Cost:** one-transaction-per-request couples a request's work into
a single rollback unit (a deliberate trade — see §2.2); and the nucleus takes a DSN rather
than reading env, so the host must wire config (it does, in B10).

### 2026-06-27 — Gapless `Sequence`: counter row + `SELECT FOR UPDATE`, not a native sequence (B2)
**Decision:** numbering is a `sequences(key, value)` row bumped under a `SELECT … FOR
UPDATE` row lock inside the caller's transaction — explicitly **not** a Postgres
`SEQUENCE`. **Why:** native sequences cache and never roll back, so they leave gaps; DIAN
(and most invoice law) forbids gaps. The lock lives in the DB, so it serializes across API
workers, which an app-level counter cannot. **Cost:** issuing a number is serialized
per-key (contention on the hot row) and the primitive is Postgres-specific (`FOR UPDATE`).
Both are accepted: gaplessness is a legal requirement, and the platform already targets
Postgres. The counter table uses a private `MetaData`, not the (not-yet-existing) nucleus
declarative base; B3/B8 fold it into the unified metadata without changing the API.

### 2026-06-23 — Initial architecture recorded
Captured the two load-bearing decisions (plugin inversion, transactional intimacy) and the
supporting choices straight from the README, before any code exists. **Why now:** so the
first implementation agent builds against a written rationale, not a guess. **Cost:** these
are intentions until code and tests prove them — update this log as reality pushes back.
