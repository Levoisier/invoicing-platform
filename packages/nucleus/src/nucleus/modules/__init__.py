"""Module loader: manifest format, dependency toposort, per-module migration
runner, install/upgrade lifecycle. Loads domain modules in correct order and
rejects dependency cycles (BACKLOG B5).
"""
