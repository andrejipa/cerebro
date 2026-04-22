"""Minimal output helpers for the CLI surface."""

from __future__ import annotations

from pathlib import Path

from core.state_store import StateStore


def user_error(code: str, message: str) -> dict:
    """Create a stable user-facing CLI error payload."""
    return {"code": code, "message": message}


def state_store_user_errors(root: Path, errors: list[dict]) -> list[dict]:
    """Rewrite state-store-facing errors into clearer CLI guidance when needed."""
    return [_friendly_user_error(root, item) for item in errors]


def state_store_user_error(root: Path, code: str, message: str) -> dict:
    """Create a stable user-facing error payload for state-store failures."""
    return user_error(code, _friendly_state_store_message(root, message))


def _friendly_user_error(root: Path, item: dict) -> dict:
    code = item.get("code")
    message = item.get("message", "")
    if code == "state_missing" and isinstance(message, str):
        return {**item, "message": _friendly_state_store_message(root, message)}
    if code == "sources_unregistered":
        return {**item, "message": _friendly_sources_unregistered_message(root)}
    return item


def _friendly_state_store_message(root: Path, message: str) -> str:
    if not message.startswith("state file not found:"):
        return message

    runtime_root = _find_runtime_root(root)
    if runtime_root is not None:
        return (
            f"no Cerebro state found in current directory: {root}. "
            "You may be running this command outside the project directory. "
            f"Change into the project root and run the command again: cd \"{runtime_root}\""
        )

    return (
        f"no Cerebro state found in current directory: {root}. "
        "You may be running this command outside the project directory. "
        "Change into the target project root that was initialized for Cerebro, "
        "or run `cerebro init` first if this project has not been initialized yet."
    )


def _find_runtime_root(root: Path) -> Path | None:
    for candidate in (root, *root.parents):
        if StateStore(candidate).state_path.exists():
            return candidate
    return None


def _friendly_sources_unregistered_message(root: Path) -> str:
    return (
        f"no context sources are registered for this project yet: {root}. "
        "Next step: run `cerebro import-context --files ...` from this project root "
        "with a small explicit set of human-maintained files such as `README.md`, "
        "a project-definition file, and one current-work note."
    )


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


def print_ambiguity(lines: list[str]) -> None:
    """Print an ambiguity block that requires explicit external resolution."""
    print("AMBIGUITY DETECTED")
    for line in lines:
        print(line)
