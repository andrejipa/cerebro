"""Runtime identifier policy for ids that become filesystem path segments."""

from __future__ import annotations

import re


_RUNTIME_PATH_SEGMENT_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")


def is_runtime_path_segment_id(value: object) -> bool:
    """Return whether value is safe as a single filesystem path segment."""
    return isinstance(value, str) and bool(_RUNTIME_PATH_SEGMENT_ID_RE.fullmatch(value))


def require_runtime_path_segment_id(value: str, label: str) -> str:
    """Validate an identifier that will be used as one path segment."""
    if not is_runtime_path_segment_id(value):
        raise ValueError(
            f"{label} must contain only letters, digits, underscore, dash, or dot "
            "and must start with a letter or digit"
        )
    return value
