"""Experimental operational insufficiency signals.

This package is derived, non-authoritative, opt-in, and observability-only.
It must never be treated as canonical runtime state or as a decision gate.
"""

from .logger import default_registry_path, load_registry, record_unmet_use_case
from .report import build_report, write_report

__all__ = [
    "build_report",
    "default_registry_path",
    "load_registry",
    "record_unmet_use_case",
    "write_report",
]
