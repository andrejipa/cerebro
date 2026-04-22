"""Schema policy for the minimal checkpoint system."""

from __future__ import annotations

CURRENT_SCHEMA_VERSION = "2"
SUPPORTED_SCHEMA_VERSIONS = frozenset({CURRENT_SCHEMA_VERSION})


def is_supported_schema_version(version: object) -> bool:
    """Return whether the given schema version is supported by this runtime."""
    return isinstance(version, str) and version in SUPPORTED_SCHEMA_VERSIONS
