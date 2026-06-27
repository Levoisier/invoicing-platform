"""Order modules so every module loads after the ones it depends on.

Dependency order is what makes "a module's tables exist before a dependent
module's" hold (README §3). We compute it once, up front, and refuse to proceed
on a cycle or a dangling dependency — a bad module graph should fail loudly at
boot, not corrupt a half-migrated database.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from nucleus.modules.manifest import ModuleManifest


class DependencyError(ValueError):
    """The module dependency graph is invalid (duplicate, missing dep, or cycle)."""


class MissingDependencyError(DependencyError):
    """A module declares a dependency on a module that wasn't provided."""


class DependencyCycleError(DependencyError):
    """The dependency graph contains a cycle, so no valid load order exists."""


def toposort(manifests: list[ModuleManifest]) -> list[ModuleManifest]:
    """Return manifests ordered dependencies-first. Deterministic: ties broken by
    name, so the same graph always yields the same order (reproducible migrations)."""
    by_name: dict[str, ModuleManifest] = {}
    for m in manifests:
        if m.name in by_name:
            raise DependencyError(f"duplicate module name: {m.name!r}")
        by_name[m.name] = m

    for m in manifests:
        for dep in m.depends:
            if dep not in by_name:
                raise MissingDependencyError(
                    f"module {m.name!r} depends on unknown module {dep!r}"
                )

    # DFS post-order: append a node only after all its dependencies are emitted,
    # which yields dependencies-before-dependents. A grey node found again on the
    # current path is a back edge — i.e. a cycle — and we surface the actual path.
    _WHITE, _GREY, _BLACK = 0, 1, 2
    color = dict.fromkeys(by_name, _WHITE)
    order: list[ModuleManifest] = []
    path: list[str] = []

    def visit(name: str) -> None:
        color[name] = _GREY
        path.append(name)
        for dep in sorted(by_name[name].depends):  # sorted == deterministic order
            if color[dep] == _GREY:
                cycle = path[path.index(dep) :] + [dep]
                raise DependencyCycleError("dependency cycle: " + " -> ".join(cycle))
            if color[dep] == _WHITE:
                visit(dep)
        path.pop()
        color[name] = _BLACK
        order.append(by_name[name])

    for name in sorted(by_name):  # sorted roots == deterministic output
        if color[name] == _WHITE:
            visit(name)
    return order
