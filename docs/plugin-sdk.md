# Plugin SDK — write a tax plugin in ~50 lines

This is the payoff of the whole architecture: **a new jurisdiction is a package you
install, not a change to the core.** This guide shows how to write one. The shipped
`plugin-tax-co` (Colombia / IVA) is the reference implementation — read it alongside
this.

> The rule that makes it work: the core depends on a *contract*, resolves
> implementations from a *registry*, and never imports a plugin. So your plugin
> depends on the nucleus; the nucleus never depends on you. (See
> `docs/ARCHITECTURE.md` §2.1.)

---

## 1. The contract you implement

The nucleus defines `TaxCalculator` (`nucleus.contracts.tax`):

```python
@runtime_checkable
class TaxCalculator(Protocol):
    jurisdiction: str
    def tax_for(self, net: Money, code: str) -> Money: ...
```

Two things to satisfy:

- a **`jurisdiction`** attribute — the key your calculator registers under (e.g.
  `"CO"`, `"MX"`), matched against a client's `Party.jurisdiction`;
- a **`tax_for(net, code)`** method — given a line's net amount (a `Money`) and its
  tax code, return the tax owed (also `Money`, same currency).

It's a `Protocol`, so **you do not inherit it** — you just match its shape. Your
plugin's only import from the core is `Money`.

---

## 2. A complete plugin

Say we want Mexico (`MX`), IVA at 16% standard and a 0% "frontier"/exempt code.
Two files.

`packages/plugin-tax-mx/src/tax_mx/__init__.py`:

```python
"""Mexico (MX / IVA) tax plugin."""
from decimal import Decimal

from nucleus.primitives import Money

# Verify rates against current SAT rules before trusting output (README §4 spirit).
_RATES = {"iva_16": Decimal("0.16"), "exempt": Decimal("0")}


class MexicoTaxCalculator:
    jurisdiction = "MX"

    def tax_for(self, net: Money, code: str) -> Money:
        try:
            rate = _RATES[code]
        except KeyError as exc:
            raise ValueError(f"unknown MX tax code {code!r}") from exc
        return net * rate  # Money carries the currency and rounds to its precision
```

`packages/plugin-tax-mx/pyproject.toml`:

```toml
[project]
name = "tax_mx"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = ["nucleus"]            # depend on the core, nothing else

# The self-registration seam. The host discovers this at boot via the
# "nucleus.plugins" entry-point group — no import of tax_mx anywhere in the core.
[project.entry-points."nucleus.plugins"]
tax_mx = "tax_mx:MexicoTaxCalculator"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/tax_mx"]
```

That's the whole plugin.

---

## 3. How it gets wired in

You never call a register function. At boot the host runs
`nucleus.plugins.discover_plugins()`, which:

1. reads the `nucleus.plugins` entry-point group from installed packages,
2. instantiates each advertised class,
3. routes it into a registry **by the contract it structurally satisfies**
   (`isinstance(obj, TaxCalculator)` → the tax registry, keyed by `obj.jurisdiction`).

`module-invoicing` then computes tax with `tax_registry.get(party.jurisdiction)` —
it has no idea `tax_mx` exists.

To ship an edition that includes Mexico, add the package to the host's deps
(`apps/api/pyproject.toml`) and rebuild. **Zero core changes.**

---

## 4. The property you get for free

Because resolution goes through the registry:

- **Add a jurisdiction** = install a package that advertises the entry point.
- **Remove one** = drop the package. A request for that jurisdiction then fails with
  a clear `RegistryError`: *"no TaxCalculator registered for jurisdiction 'MX'"* —
  not a crash, not a silent zero-tax. (This exact behaviour is tested for CO in
  `module-invoicing/tests/test_totals.py` and `plugin-tax-co/tests/test_tax_co.py`.)

---

## 5. Conventions & gotchas

- **Distribution dir is prefixed (`plugin-tax-mx`), import name is clean (`tax_mx`).**
  Map them in `[tool.hatch.build.targets.wheel] packages = ["src/tax_mx"]`.
- **Codes are rate buckets, not product classifications.** Deciding *which* code a
  line uses is the user's job; your plugin only maps a code → a rate.
- **Return `Money`, let it round.** `net * rate` yields a `Money` quantized to the
  currency's precision — don't pre-round to 2 decimals (COP is 0).
- **Reject unknown codes loudly** (`raise`), never tax them at 0 — a silent 0
  under-bills and corrupts the books.
- **Register tests as a package** with a `tests/` dir; the workspace runner picks
  them up. Prove your rates and that the calculator satisfies the contract
  (`isinstance(MexicoTaxCalculator(), TaxCalculator)`).
