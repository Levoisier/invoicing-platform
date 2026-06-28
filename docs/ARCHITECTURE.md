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
- **Event bus is synchronous and in-transaction, not a queue.** `publish(event, session)`
  calls each subscriber immediately, in the publisher's call stack, on the publisher's
  session. So a subscriber's DB writes are in the **same transaction** as the trigger and
  commit or roll back with it; a subscriber that raises propagates and aborts the whole
  unit of work (trigger + every handler). This is deliberately *not* a message queue: no
  async, no retries, no eventual consistency, and handlers observe the trigger's still-
  uncommitted state (correct — same txn). The cost: subscribers are on the publisher's
  critical path (keep them fast) and anything that must run **only after commit** (email,
  webhooks, DIAN submission) is explicitly out of scope for this bus — that's a future
  out-of-process concern. Dispatch is by **exact** event type, handlers fire in
  subscription order; those are the only delivery guarantees made.
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
  a fallback to headless-Chromium print or ReportLab. **Resolved (B11):** the deps
  (libpango, libcairo, libharfbuzz) are present in our image and WeasyPrint renders cleanly,
  so we kept WeasyPrint and took **no fallback**. The packaging Dockerfile (B15) must keep
  those system libs installed; if a future base image drops them and they can't be re-added,
  that's when the sanctioned fallback comes into play (record it here then).
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

### 2026-06-28 — PDF via WeasyPrint (HTML/CSS), no fallback needed (B11)
**Decision:** invoices render as HTML/CSS (a Jinja2 template) → PDF via WeasyPrint, in
`invoicing.pdf`; `GET /invoices/{id}/pdf` serves it. The IVA breakdown comes from a new
`tax_breakdown` service function that groups lines by tax code into (base, tax) buckets,
resolved through the registry like `compute_totals`. **Why HTML/CSS→PDF:** an invoice is a
styled page; authoring it in HTML/CSS is far more maintainable than drawing primitives in
code (the ReportLab style), and it's the README's pick. **Why no fallback:** the README
sanctioned ReportLab/headless-Chromium if WeasyPrint's native deps fought the image — they
don't; libpango/cairo/harfbuzz are present and it renders, so adding a fallback would be
complexity with no cause. **Why an inline template string, not a file:** one document doesn't
justify wheel package-data wiring; the template lives in `pdf.py` with autoescape on (line
descriptions/names are user data). **Money on the artifact** goes through `Money.__str__`, so
COP shows 0 decimals — the visible proof of the per-currency primitive. **Cost / watch:** (1)
WeasyPrint pulls system libs, so the B15 Dockerfile must install them (noted in §4); (2)
tests assert PDF *text* via pypdf (a dev dep) — robust here, but text extraction can be
brittle if the template moves to exotic fonts; (3) no issuer/branding entity yet — the
template shows the client and totals, not a sender letterhead (v1 scope).

### 2026-06-28 — `module-payments`: atomicity proven, via a downward import not the bus (B12)
**Decision:** `record_payment` writes the payment, its balanced double-entry ledger, and the
invoice's new status all on the *caller's session*, so they commit or roll back as one unit.
payments **imports invoicing** (`Invoice`, `InvoiceStatus`, `compute_totals`) — a downward
dependency, declared in the manifest so the loader migrates invoicing first. **Why an import,
not the event bus:** the stub aspired to "cooperate via the event bus, not a hard import",
but an event-driven version forces a *wrong-direction* dependency — the subscriber is
invoicing (it owns status), so invoicing would have to import a payments event, yet invoicing
is the earlier, lower module. Putting the event in invoicing instead is conceptually
backwards (a "payment recorded" event owned by invoicing). The build spine explicitly places
payments after invoicing, so a same-process downward import is the honest model and keeps the
atomic action obviously in one transaction. CLAUDE.md §2 forbids core→plugin imports, not
module→module ones. **Why signed-amount ledger:** storing +debit/−credit makes the
double-entry invariant a one-line "sums to zero" check. **The demonstration:** a test posts
the ledger in a separate committed transaction and then fails the status update in another —
the ledger persists while the invoice stays ISSUED, the exact corruption same-transaction
prevents. That is the concrete argument for why modules are in-process sharing one session
(README §1, the second core idea). **Cost:** payments↔invoicing are now compile-time coupled
(can't deploy independently) — accepted, because that coupling is *what buys* atomicity;
splitting them would require distributed transactions, which the project rejects on purpose.

### 2026-06-28 — `apps/api` bootstrap: compose the edition at runtime (B10)
**Decision:** `create_app()` is the composition root: clear the shared registries, discover
tax plugins from entry points, load modules (toposort + migrate) in one unit of work, then
mount the routers modules published to the route registry. Module routes declare the nucleus
seams `get_session`/`get_principal`; the host fills them with `app.dependency_overrides`
(session-per-request, and the configured `JWTAuth`). **Why dependency_overrides:** it's the
registry inversion at the HTTP layer — a module's route asks for "a session"/"the caller" by
name and the host supplies the concrete dependency, so a module holds no engine or secret and
stays host-agnostic. **Why clear registries at boot:** bootstrap builds a composition from
scratch, so re-composing (a second app in one test process) is idempotent rather than
tripping duplicate-registration guards. **Why migrate inside create_app:** the first
end-to-end slice needs the schema present; one unit of work keeps the boot atomic (B5).
**Cost / sharp edges:** (1) `create_app` touches the DB (runs migrations), so importing
`app.main` requires a reachable database — tests build their own app against a test DB rather
than importing `app.main`; (2) migrating on app construction means every worker would migrate
on startup — fine for single-process dev, but production wants a dedicated migrate step
(`make migrate`) run once before scaling out (the B5 concurrency note); (3) login compares a
plaintext credential from settings — adequate for v1 single-user dev, flagged for hashing
later.

### 2026-06-28 — `plugin-tax-co` + discovery: the inversion, proven end to end (B9)
**Decision:** `ColombiaTaxCalculator` lives in its own package and self-registers via the
`nucleus.plugins` entry point; `nucleus.plugins.discover_plugins()` loads that group,
instantiates each class, and routes it into a registry **by the contract it structurally
satisfies** (isinstance against the runtime_checkable `TaxCalculator`). `invoicing.compute_totals`
resolves the calculator from the tax registry by `party.jurisdiction` and never imports the
plugin. **Why route by contract, not entry-point name:** a plugin is whatever contract it
matches, so adding a `PaymentProvider` plugin later needs no change to discovery's interface.
**Why the consumer holds the "remove" test:** the guarantee that matters is the *consumer's*
failure mode — an absent plugin yields the registry's clear "no TaxCalculator registered for
jurisdiction 'CO'", with zero core change to add or drop a jurisdiction. **Rates:** verified
against DIAN (June 2026) — general 19%, reduced 5%, excluded/exempt 0% (Estatuto Tributario
arts. 420–513). **Cost / sharp edges:** (1) codes are rate *buckets*, not product
classifications — choosing 5% vs 19% per line is the user's responsibility; (2) v1 folds
"excluded" and "exempt" into one 0% code (they differ on input-tax credit, out of scope);
(3) discovery instantiates every advertised plugin at boot — fine at this scale, but a
misbehaving third-party plugin's constructor could break startup (a sandboxing concern for a
real marketplace, not v1).

### 2026-06-28 — `module-invoicing` entities: first domain module on the shared Base (B8)
**Decision:** `Party`, `Invoice`, `InvoiceLine` inherit the nucleus declarative `Base` (one
metadata, shared transactions); `issue_invoice` allocates the gapless number from
`Sequence("invoice")` on the *caller's* session; the module ships a `ModuleManifest` whose
`migrate` creates its tables with `create_all` on the loader's session connection. A line
stores an opaque `tax_code`; one currency lives on the invoice and every line's Money derives
from it. **Why number-on-caller's-session:** allocation must be in the same transaction as
the insert, so a rolled-back request reuses the number instead of skipping it — gaplessness
holds per request, not just under concurrency (B2). **Why `create_all`, not Alembic yet:**
honest for a schema with no history; per-module Alembic is the production path once tables
evolve (README §2) — deferred to avoid migration scaffolding before there's anything to
migrate. **Why currency on the invoice, not the line:** mixing currencies on one invoice
becomes impossible by construction rather than by validation. **Cost / watch:** (1)
`create_all` can't express schema *changes* — the first real migration forces the Alembic
switch, and that cutover must import the existing tables as the baseline; (2) tax is
deliberately absent — totals here are pre-tax `subtotal()` only; the grand total waits on the
registry-resolved calculator (B9).

### 2026-06-28 — `nucleus.api`: FastAPI in the core, auth split pure/bound (B7)
**Decision:** the API gateway lives in the nucleus, so `fastapi` is now a nucleus dependency.
Auth is two layers: `JWTAuth` (pure pyjwt — issue/verify, enforces signature, expiry, and a
non-empty subject) and `gateway.require_principal(auth)` (the FastAPI dependency that reads
the bearer token and answers 401). **Why FastAPI in the core:** README §1 says the nucleus
*owns the API gateway*; "framework-light" (CLAUDE.md §2) means no dependency on a *module or
plugin*, not "no web framework". Putting the gateway here is what lets modules expose
protected routes uniformly without each re-implementing auth. **Why split pure vs bound:**
token rules are security-critical and must be testable without HTTP; the thin FastAPI adapter
then has almost no logic to get wrong. **Why config is passed in:** same rule as nucleus.db —
the host owns secrets, the core stays a library, so `JWTAuth` is constructed with the secret
rather than reading `os.environ`. **Cost / sharp edges:** (1) the core now pulls FastAPI, a
heavier dep — acceptable since every edition ships an HTTP API; (2) HS256 (shared secret)
only — fine for single-tenant self-host; asymmetric keys (RS256) would be a later change if
multiple services must verify tokens; (3) `require_principal` is a factory (needs the host's
`auth`), so the host builds the dependency once and reuses it (router mounting itself lands
in B10).

### 2026-06-27 — `nucleus.events.bus`: synchronous, in-transaction delivery (B6)
**Decision:** the event bus delivers synchronously, in-process, on the publisher's session
(`publish(event, session)`); exact-type dispatch, handlers in subscription order, exceptions
**not** caught. **Why:** the project's thesis is cross-module atomicity. If a subscriber's
writes weren't in the trigger's transaction, "invoice status + ledger commit together"
(B12) would be a lie — payments will subscribe to an invoicing event and post ledger
entries in the *same* unit of work. Synchronous same-session delivery is the only thing that
makes that true. Not catching handler errors is part of the contract: propagation is what
lets the unit of work roll the whole reaction back. **Cost / boundary (see §3):** subscribers
are on the critical path; there is no async, retry, or after-commit hook — post-commit side
effects (email, DIAN) are a future out-of-process mechanism, not this bus. Exact-type
dispatch (no subclass matching) keeps delivery predictable but means a base-type subscription
won't catch subtypes — revisit only if a real need appears.

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
