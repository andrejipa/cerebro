"""Minimal output helpers for the CLI surface."""

from __future__ import annotations


def user_error(code: str, message: str) -> dict:
    """Create a stable user-facing CLI error payload."""
    return {"code": code, "message": message}


def print_ok(lines: list[str] | None = None) -> None:
    """Print a successful command result."""
    print("OK")
    for line in lines or []:
        print(line)


def print_fail(errors: list[dict]) -> None:
    """Print a failed command result with stable error formatting."""
    print("FAIL")
    for item in errors:
        print(f"- {item['code']}: {item['message']}")
