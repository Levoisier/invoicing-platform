"""Module loader: manifest format, dependency toposort, per-module migration
runner, install/upgrade lifecycle. Loads domain modules in correct order and
rejects dependency cycles (BACKLOG B5).
"""

from nucleus.modules.lifecycle import Action, ensure_schema, installed_modules
from nucleus.modules.loader import LoadResult, load_modules
from nucleus.modules.manifest import ModuleContext, ModuleManifest
from nucleus.modules.toposort import (
    DependencyCycleError,
    DependencyError,
    MissingDependencyError,
    toposort,
)

__all__ = [
    "Action",
    "DependencyCycleError",
    "DependencyError",
    "LoadResult",
    "MissingDependencyError",
    "ModuleContext",
    "ModuleManifest",
    "ensure_schema",
    "installed_modules",
    "load_modules",
    "toposort",
]
