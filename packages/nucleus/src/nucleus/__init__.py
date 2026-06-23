"""The reusable nucleus: the transactional core that modules attach to and plugins
extend.

It owns domain primitives, the DB/transaction layer, the registries, the module
loader, the event bus, and the API gateway. It defines *contracts* and resolves
implementations from a registry — it never imports a concrete module or plugin.
That inversion is the architecture's thesis (see docs/ARCHITECTURE.md §2).
"""
