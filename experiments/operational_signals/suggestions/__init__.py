"""Derived advisory layer for operational insufficiency suggestions.

This package is experimental, derived, read-only, non-authoritative,
opt-in, and advisory-only. It does not register insufficiency signals
on its own; every emitted suggestion requires explicit human review
before being accepted into the human registry defined in
`experiments/operational_signals/unmet_use_cases.toml`.

Nothing in this package may be imported by `core/` or `cli/`, must not
write inside `.cerebro/`, and must never act as canonical runtime state.
"""

from __future__ import annotations

AUTHORITY = "derived-advisory-only"
SCHEMA_VERSION = "1"
