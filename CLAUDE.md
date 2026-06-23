# CLAUDE.md — Working agreement for agents in this repo

This file is the **operating contract** for any AI agent (Claude Code or otherwise)
working in this repository. Read it before doing anything. The product context lives
in [`README.md`](README.md); the deep architecture lives in
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md). This file governs **how you work**, not
what the product is.

`AGENTS.md` exists only to redirect other tools here. This is the single source of truth.

---

## 0. The one rule that overrides convenience: this is a learning project

The owner of this repo is building it **to learn how an extensible, transactional
platform is designed and constructed.** Shipping the feature is necessary but **not
sufficient**. The real deliverable is that the owner understands *why* the code looks
the way it does after you touch it.

Two non-negotiable obligations follow from this:

### 0.1 Always explain *how* and *why* — every time

After completing **any** backlog item, bugfix, refactor, or one-off user request, your
final reply MUST include a short **"How & Why"** section. It is not optional and not a
nicety. It covers:

- **What** you changed (the files/behavior, briefly).
- **How** it works — the mechanism, in plain language.
- **Why this way** — the reasoning. What alternatives existed, and what made you reject
  them? What trade-off did you accept? If the README or a contract forced your hand,
  say so.
- **What it costs / what to watch** — the limitation, the sharp edge, or the thing that
  will need revisiting later.

Write it for someone learning the craft, not for someone signing off a ticket. If a
decision was obvious, one line is fine. If it was a real fork in the road, spend the
words. **A change without its reasoning is an incomplete change here.**

### 0.2 Code documentation is concise and explains *why*, not *what*

The owner should be able to open any file later and learn the reasoning from the
comments alone. So:

- **Comment the *why*, never the *what*.** The code already says what it does. A comment
  that restates the line is noise. A comment that explains *why this approach* is the
  asset. Good: `# row lock here, not app lock — gapless numbering must survive multiple API workers`.
  Bad: `# increment the counter`.
- **Keep it short.** A sentence or two at a decision point beats a paragraph. Density of
  insight, not volume.
- **Put rationale where the decision lives.** Comment the surprising line, the chosen
  constant, the contract boundary — not the boilerplate.
- **Module/package docstrings** state the *purpose and its place in the architecture*
  (e.g. "Nucleus contract for tax calculation; plugins implement this, the core never
  imports them"), not a feature list.
- When a decision is bigger than a comment, record it in `docs/ARCHITECTURE.md` (the
  decision record) and reference it.

If you find yourself writing a comment that narrates the code, delete it. If you find a
clever line with no comment, add the *why*.

---

## 1. The workflow loop

For each unit of work:

1. **Orient.** Read `README.md` §1–§7 for product truth, this file for process, and the
   relevant backlog item in `BACKLOG.md`. Check `LESSONS.md` for traps already hit.
2. **Plan, briefly.** State what you're about to do and the acceptance criteria you're
   targeting. For anything ambiguous or architecturally significant, ask before building.
3. **Build the smallest correct thing.** Prefer a thin vertical slice that proves a
   property over a broad horizontal layer that proves nothing. The README's §7 "success"
   is about *properties holding*, not surface area.
4. **Prove it with a test.** The architecture properties (atomicity, gapless numbering,
   plugin inversion, money precision) are only real if a test demonstrates them. No claim
   of correctness without a test that would fail if it were false.
5. **Document as you go** per §0.2.
6. **Report with "How & Why"** per §0.1, and update `LESSONS.md` if you learned something
   non-obvious.
7. **Commit** with a clear message (see §4).

Do not batch ten items and a giant commit. One coherent unit, explained, then the next.

---

## 2. Architectural guardrails (do not cross without asking)

These come straight from the README's two core ideas. Violating them defeats the point
of the project.

- **The core never imports a plugin.** `module-invoicing` must resolve the tax calculator
  from the **registry**, never `import tax_co`. If you're reaching for that import, stop —
  you're breaking the seam the whole project exists to demonstrate.
- **Modules share one DB transaction.** Invoice status + ledger entries commit or roll
  back as a unit. Don't introduce a second session or an out-of-process call on that path.
- **`Money` has per-currency precision.** COP is 0 decimals. Never hardcode 2. Mixing
  currencies raises, it does not silently coerce.
- **Numbering is gapless.** Use a DB row lock, not an app-level counter. It must survive
  multiple API workers.
- **`apps/web/lib/types.ts` is generated.** Never hand-edit it. A backend contract change
  is finished only when `make gen-types` regenerates it.
- **Distribution dir names are prefixed (`module-`, `plugin-`); import names stay clean**
  (`import invoicing`, `import tax_co`).

If a task seems to require crossing one of these lines, that's a signal to ask the owner,
not to quietly cross it.

---

## 3. Verify before you trust

The README says it plainly and so do we: **library majors and tax rules drift.**

- Verify current majors before coding against them (SQLAlchemy 2.x, Pydantic v2, FastAPI,
  WeasyPrint, openapi-typescript).
- Verify CO/IVA rates against current DIAN regulation before presenting output as
  accounting-correct. v1 targets *correct architecture with plausible rates*.
- If WeasyPrint's native deps (Pango/cairo) fight the Docker image, the README sanctions a
  fallback (headless-Chromium print or ReportLab) — take it and record why in
  `docs/ARCHITECTURE.md`.

---

## 4. Commits & branches

- Develop on the branch you were assigned. Create it locally if needed. Never push to a
  different branch without explicit permission.
- One logical change per commit. Message: imperative subject line, then a body that says
  **why** when the why isn't obvious from the diff. (Same principle as code comments.)
- Do **not** open a pull request unless explicitly asked.
- Keep generated artifacts (`types.ts`, lockfiles) consistent with their sources in the
  same commit.

---

## 5. Definition of done (per item)

An item is done when:

- [ ] It meets the acceptance criteria in its `BACKLOG.md` entry.
- [ ] A test proves any architecture property it claims to establish.
- [ ] Code carries concise *why*-comments at the decision points (§0.2).
- [ ] Your reply includes the **How & Why** section (§0.1).
- [ ] `LESSONS.md` is updated if anything non-obvious was learned.
- [ ] It's committed with a clear message.

"It runs" is not done. "It runs, it's proven, and the owner can learn from it" is done.
