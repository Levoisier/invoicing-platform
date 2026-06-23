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

### 2026-06-23 — Initial architecture recorded
Captured the two load-bearing decisions (plugin inversion, transactional intimacy) and the
supporting choices straight from the README, before any code exists. **Why now:** so the
first implementation agent builds against a written rationale, not a guess. **Cost:** these
are intentions until code and tests prove them — update this log as reality pushes back.
