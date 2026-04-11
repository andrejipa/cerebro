"""Schema definitions for the minimal checkpoint state."""

from __future__ import annotations

from core.schema_policy import CURRENT_SCHEMA_VERSION

SCHEMA_VERSION = CURRENT_SCHEMA_VERSION

ROOT_KEYS = {
    "version",
    "revision",
    "sources",
    "checkpoint",
    "last_validation",
}

SOURCE_KEYS = {
    "path",
    "sha256",
    "role",
}

CHECKPOINT_KEYS = {
    "goal",
    "summary",
    "next_step",
    "constraints",
    "updated_at",
}

LAST_VALIDATION_KEYS = {
    "validated_at",
    "result",
    "details",
}

DETAIL_KEYS = {
    "code",
    "message",
}

VALID_RESULTS = {"ok", "fail"}
VALID_SOURCE_ROLES = {"primary", "reference"}
SESSION_KEYS = {
    "opened_at",
    "actor",
    "based_on_revision",
}

MAX_SOURCES = 32
MAX_VALIDATION_DETAILS = 32
MAX_GOAL_LENGTH = 200
MAX_SUMMARY_LENGTH = 1000
MAX_NEXT_STEP_LENGTH = 300
MAX_CONSTRAINTS = 8
MAX_CONSTRAINT_LENGTH = 160


def build_initial_state() -> dict:
    """Return the minimal valid initial state for a new instance."""
    return {
        "version": SCHEMA_VERSION,
        "revision": 0,
        "sources": [],
        "checkpoint": {
            "goal": "",
            "summary": "",
            "next_step": "",
            "constraints": [],
            "updated_at": "",
        },
        "last_validation": {
            "validated_at": "",
            "result": "fail",
            "details": [
                {
                    "code": "uninitialized",
                    "message": "context sources have not been validated yet",
                }
            ],
        },
    }
