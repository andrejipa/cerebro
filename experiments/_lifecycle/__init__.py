"""Lifecycle governance for folders under `experiments/`.

This package provides a derived, read-only view over
`experiments/lifecycle.toml`. It loads and validates the ledger, and
cross-checks it against the directories actually present under
`experiments/`.

It is infrastructure, not an experiment itself. It must not be imported
by `core/` or `cli/`, must not write inside `.cerebro/`, and must never
be treated as canonical runtime state.
"""

from __future__ import annotations

SCHEMA_VERSION = "1"
AUTHORITY = "derived-governance-only"
