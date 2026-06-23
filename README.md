# Invoicing Platform

> Self-hostable invoicing where **the tax engine is a plugin**. Ship a core; add the module a client's country needs. v1.0.0 ships the core plus one plugin: **Colombia (CO / IVA)**.

This README is the **single source of context** for the project. Agents and contributors should read it before generating a backlog or writing code. Deeper architecture lives in [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md); the plugin SDK in [`docs/plugin-sdk.md`](docs/plugin-sdk.md).

---

## 1. What this is (and why it's built this way)

A working, self-hostable invoicing app for freelancers and small agencies. But its **architecture is a reusable nucleus**: a thin transactional core that domain *modules* and pluggable *providers* attach to at runtime. The headline capability — and the thing that makes it more than a CRUD app — is that **tax rules for a jurisdiction are a self-registering plugin**, not core code.

Two goals, one codebase:
1. **Product:** something real people would run to issue invoices.
2. **Platform:** demonstrates extensible-platform design — core + modules + plugin SDK — the pattern behind ERP-style systems.

### Vocabulary (use these terms consistently)
- **Nucleus** — the reusable core. Owns domain primitives, the DB/transaction layer, registries, the module loader, the event bus, and the API gateway. Built once. (`packages/nucleus`)
- **Module** — an in-process domain unit that attaches to the nucleus and **shares its database transaction** (e.g. `invoicing`, `payments`). (`packages/module-*`)
- **Plugin / Provider** — a swappable implementation of a nucleus *contract* (e.g. a `TaxCalculator` for a jurisdiction). Self-registers via entry points; the core never imports it directly. (`packages/plugin-*`)
- **Host** — the deployable that *composes* a chosen set of modules + plugins. Different editions = different host dependencies. (`apps/api`)

### The two ideas everything rests on
1. **Plugin contract (inversion).** The nucleus defines an interface (`TaxCalculator`); a plugin implements and registers it; consumers ask the **registry**, never import the plugin. Adding a country = installing a package, with **zero core changes**.
2. **Transactional intimacy.** Modules run in-process and share one DB session, so an invoice's status and its ledger entries **commit or roll back as a unit**. This atomicity is the reason modules are same-language/in-process — and the property v1 must prove with a test.

---

## 2. Tech stack

| Layer | Choice |
|---|---|
| API | FastAPI |
| ORM / transactions | SQLAlchemy 2.0 (Core + ORM) |
| Migrations | Alembic (per-module) |
| Validation / schemas | Pydantic v2 |
| Database | PostgreSQL |
| PDF generation | WeasyPrint (HTML/CSS → PDF) |
| Frontend | Next.js + TypeScript |
| API contract | OpenAPI emitted by FastAPI → `openapi-typescript` generates `apps/web/lib/types.ts` |
| Python tooling | **uv workspace** (one repo, many packages) |
| Auth | JWT |
| Deploy | docker-compose (db + api + web) |

> **Verify current majors before coding** — SQLAlchemy 2.x, Pydantic v2, FastAPI, WeasyPrint, openapi-typescript all move. WeasyPrint has native deps (Pango/cairo); if the Docker image fights you, fall back to headless-Chromium print or ReportLab.

---

## 3. Repository structure

One monorepo, two toolchains: **uv** owns the Python packages, **npm/pnpm** owns the frontend. They live side by side; the root `Makefile` and `docker-compose.yml` tie them together.

```
invoicing-platform/
├── pyproject.toml              # uv workspace root: members = apps/api + packages/*
├── uv.lock
├── ruff.toml
├── docker-compose.yml          # db + api + web
├── Makefile                    # dev, gen-types, migrate, test, up
├── .env.example
│
├── apps/
│   ├── api/                    # HOST — thin composition root (deps decide the edition)
│   │   ├── pyproject.toml        # deps: nucleus + module-* + plugin-tax-co
│   │   ├── src/app/
│   │   │   ├── main.py           # FastAPI entry
│   │   │   ├── bootstrap.py      # discover modules → toposort → migrate → mount routers/plugins
│   │   │   └── settings.py
│   │   └── tests/
│   │
│   └── web/                    # Next.js + TypeScript (same repo, standalone package)
│       ├── package.json
│       ├── next.config.ts
│       ├── tsconfig.json
│       ├── app/                  # routes: clients, invoices, invoice/[id]
│       ├── components/
│       ├── lib/
│       │   ├── api.ts            # typed client
│       │   └── types.ts          # GENERATED from OpenAPI — do not hand-edit
│       └── public/
│
├── packages/
│   ├── nucleus/                # ★ the reusable core
│   │   └── src/nucleus/
│   │       ├── primitives/       # money.py, sequence.py, party.py
│   │       ├── db/               # engine.py, session.py, base.py, unit_of_work.py
│   │       ├── contracts/        # Protocols: TaxCalculator, PaymentProvider, Exporter
│   │       ├── registry/         # model / route / event / tax / payment registries
│   │       ├── modules/          # loader.py, manifest.py, toposort.py, lifecycle.py
│   │       ├── events/           # bus.py
│   │       └── api/              # gateway helpers, auth (JWT)
│   │
│   ├── module-invoicing/       # Invoice, InvoiceLine, numbering, PDF
│   │   └── src/invoicing/        # manifest.py, models.py, api.py, service.py, migrations/
│   │
│   ├── module-payments/        # Payment, LedgerEntry — the atomic crux
│   │   └── src/payments/
│   │
│   └── plugin-tax-co/          # ★ the only plugin in v1.0.0: Colombia / IVA
│       ├── pyproject.toml        # entry point registers the CO calculator
│       └── src/tax_co/__init__.py
│
├── infra/
│   ├── docker/                 # Dockerfile.api, Dockerfile.web
│   └── alembic/                # alembic.ini + env.py aggregating module migrations
│
└── docs/
    ├── ARCHITECTURE.md         # deep architecture + decision record
    └── plugin-sdk.md           # "write a tax plugin in ~50 lines"
```

Distribution dir names are prefixed (`module-`, `plugin-`) so the tree reads at a glance; **import names stay clean** (`import invoicing`, `import tax_co`).

---

## 4. The Colombia (CO) tax plugin

The one plugin v1.0.0 ships. It implements the nucleus `TaxCalculator` contract for `jurisdiction = "CO"` and self-registers via entry point:

```toml
# packages/plugin-tax-co/pyproject.toml
[project.entry-points."nucleus.plugins"]
tax_co = "tax_co:ColombiaTaxCalculator"
```

**Scope of the CO plugin (IVA — Impuesto sobre las Ventas):**

| Tax code | Meaning | Rate |
|---|---|---|
| `iva_19` | Standard IVA | 19% |
| `iva_5`  | Reduced IVA | 5% |
| `excluded` | Excluded / exempt | 0% |

- Currency: **COP (Colombian Peso)**. Note COP is conventionally used **without decimal places** — the `Money` primitive must support **per-currency precision** (COP → 0 decimals), not a hardcoded 2. Get this right or totals will look wrong to Colombian users.
- Clients carry a Colombian tax id (**NIT / Cédula**); store it on the `Party`, render it on the PDF. Format validation can be minimal in v1.

**Explicitly OUT of scope for the CO plugin in v1** (these are future plugins, and listing them is intentional — it proves the architecture extends):
- DIAN **electronic invoicing** (facturación electrónica): CUFE, UBL 2.1 XML, DIAN authorization/`resolución`, numbering ranges. Large, separate effort.
- Withholdings: **retención en la fuente, ReteIVA, ReteICA**.

> **Verify the rates and rules** against current DIAN regulations before relying on output for real accounting — tax law changes, and this README's knowledge may be dated. v1 targets a *correct architecture with plausible rates*, not certified compliance.

---

## 5. v1.0.0 scope

### In scope
- **Auth:** single-user (or minimal multi-user) login via JWT.
- **Clients (Party):** create / list / edit; name, NIT/Cédula, address, `jurisdiction = "CO"`.
- **Invoicing module:** create invoice with line items (description, qty, unit price, tax code); per-line net + IVA via the CO plugin; totals in `Money` (COP); **gapless sequential invoice number**.
- **PDF:** generate a downloadable invoice PDF with line items, IVA breakdown, totals, client NIT.
- **Payments module:** record a (manual) payment; invoice status transitions (`draft → issued → partial → paid`); ledger entries posted **atomically** with the status change.
- **CO tax plugin:** discovered via entry point, not hardcoded.
- **Frontend (Next.js):** client list/create, invoice create/list/detail, mark-paid, PDF download — consuming **generated** types from the OpenAPI contract.
- **Self-host:** `docker compose up` brings up db + api + web.

### Out of scope (v1.1+ / future plugins)
- DIAN electronic invoicing, withholdings (see §4).
- Real payment-gateway integration (v1 records payments manually; a `plugin-payment-*` comes later).
- Recurring invoices, credit notes, multi-currency FX, email delivery, dashboards/reports, organizations/teams/roles beyond minimal auth.
- A second jurisdiction (the architecture supports it; v1 just doesn't build one).

---

## 6. Build order (use this to generate the backlog)

The natural dependency spine. Each item is a self-contained work unit; later items depend on earlier ones. Agents should decompose the backlog along this order.

1. **Workspace + tooling** — uv workspace, ruff, docker-compose (Postgres), Makefile, `.env`.
2. **`nucleus.primitives.money`** — `Money` with per-currency precision (COP = 0 decimals) + tests.
3. **`nucleus.primitives.sequence`** — gapless sequential generator (DB row lock) + concurrency test.
4. **`nucleus.db`** — engine, session-per-request, declarative base, unit-of-work; atomic commit + rollback tests.
5. **`nucleus.registry` + `nucleus.contracts`** — model/route/event/tax/payment registries; `TaxCalculator`/`PaymentProvider` Protocols.
6. **`nucleus.modules` loader** — manifest format, dependency toposort, per-module migration runner, install/upgrade lifecycle.
7. **`nucleus.events.bus`** — in-process event bus.
8. **`nucleus.api`** — gateway helpers + JWT auth.
9. **`module-invoicing` (entities)** — `Party` (in nucleus primitives or core), `Invoice`, `InvoiceLine`; numbering via `Sequence`.
10. **`plugin-tax-co`** — `ColombiaTaxCalculator`, entry-point registration; wire into invoice totals via the **registry**.
11. **`apps/api` host** — `bootstrap.py`: discover → toposort → migrate → mount; first end-to-end vertical slice.
12. **PDF generation** — invoice → HTML template → PDF.
13. **`module-payments`** — payment + ledger, **atomic** with invoice status; plus the "break it out-of-process" demonstration test.
14. **Contract generation** — OpenAPI → `openapi-typescript` → `apps/web/lib/types.ts`, wired into the Makefile.
15. **`apps/web`** — client + invoice screens, mark-paid, PDF download, against generated types.
16. **Packaging** — Dockerfiles, compose, README run instructions, `docs/ARCHITECTURE.md`, `docs/plugin-sdk.md`.

---

## 7. Definition of success — what a shippable v1.0.0 is

v1.0.0 is **done** when all of the following are true. This is the acceptance checklist.

### A. The user flow works end to end
A user can, from a clean `docker compose up`:
1. Log in.
2. Create a **client** with a NIT and `jurisdiction = CO`.
3. Create an **invoice**: pick the client, add line items with tax codes (`iva_19`, `iva_5`, `excluded`).
4. See the invoice total computed correctly: per-line net, IVA applied by the **CO plugin**, grand total in COP (no decimals).
5. The invoice gets a **gapless sequential number**.
6. **Download a PDF** of the invoice showing line items, an IVA breakdown, totals, and the client NIT.
7. **Record a payment**; the invoice status updates (`partial`/`paid`) **and** ledger entries are posted in the same transaction.
8. List invoices and see correct statuses; re-download any PDF.

### B. The architecture properties hold (proven by tests, not by claims)
- [ ] **Atomicity:** a test shows invoice-status + ledger entries commit together, and roll back together on failure.
- [ ] **Gapless numbering:** a concurrency test shows no gaps and no duplicates under parallel invoice creation.
- [ ] **Plugin inversion:** the CO calculator is resolved from the registry; the invoicing module does **not** import `tax_co` directly. Removing `plugin-tax-co` from the host's dependencies removes CO support cleanly (a request for `CO` then fails with a clear "no tax plugin" error) — demonstrating a new jurisdiction would be add-a-package, zero core change.
- [ ] **Money correctness:** COP totals render with 0 decimals; mixing currencies raises rather than silently coercing.
- [ ] **Contract honesty:** `apps/web/lib/types.ts` is generated from the live OpenAPI schema; a backend change regenerates it via one Make target.

### C. The output is real
- A **valid PDF invoice** for a Colombian client with correct IVA — the tangible artifact you can show.
- A running, self-hostable app (db + api + web) reachable in a browser.
- `docs/ARCHITECTURE.md` (the decision record) and `docs/plugin-sdk.md` (how to write the next tax plugin).

### What "success" deliberately does NOT require
Polished UI, real payment gateways, DIAN compliance, multi-tenancy, or a second jurisdiction. The bar is: **a correct, extensible, transactional core that issues a real Colombian invoice end to end, with the plugin seam demonstrably working.** Polish the core, not the buttons.

---

## 8. Running it (target state)

```bash
cp .env.example .env
make up            # docker compose: db + api + web
make migrate       # run module migrations in dependency order
make gen-types     # OpenAPI -> apps/web/lib/types.ts
# web: http://localhost:3000   api docs: http://localhost:8000/docs
```

For local dev without full Docker: `make dev` runs Postgres in a container, the API with reload, and the Next.js dev server together.
