"""Stable read-only models exposed by the core."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SourceRecord:
    """Read-only representation of a registered source."""

    path: str
    sha256: str
    role: str


@dataclass(frozen=True)
class CheckpointRecord:
    """Read-only representation of the current checkpoint."""

    goal: str
    summary: str
    next_step: str
    constraints: tuple[str, ...]
    updated_at: str


@dataclass(frozen=True)
class ValidationDetail:
    """Read-only representation of a validation detail."""

    code: str
    message: str


@dataclass(frozen=True)
class ValidationRecord:
    """Read-only representation of the last validation result."""

    validated_at: str
    result: str
    details: tuple[ValidationDetail, ...]


@dataclass(frozen=True)
class StateSnapshot:
    """Stable read-only snapshot of the canonical state."""

    version: str
    revision: int
    sources: tuple[SourceRecord, ...]
    checkpoint: CheckpointRecord
    last_validation: ValidationRecord
