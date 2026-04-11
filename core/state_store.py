"""Persistent state access for the minimal checkpoint system."""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from core.read_models import (
    CheckpointRecord,
    SourceRecord,
    StateSnapshot,
    ValidationDetail,
    ValidationRecord,
)
from core.schema import build_initial_state
from core.validation import error, validate_session_data, validate_state_data


class StateStoreError(Exception):
    """Base exception for state store failures."""


class StateValidationError(StateStoreError):
    """Raised when state data is structurally invalid."""

    def __init__(self, errors: list[dict]):
        super().__init__("state validation failed")
        self.errors = errors


class StateStore:
    """Read and write the only persistent state file for the system."""

    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()
        self.cerebro_dir = self.root / ".cerebro"
        self.state_path = self.cerebro_dir / "state.json"
        self.session_path = self.cerebro_dir / "session.local.json"
        self.logs_dir = self.cerebro_dir / "logs"
        self.events_path = self.logs_dir / "events.jsonl"

    def initialize(self) -> dict:
        """Create the minimal instance layout and initial state."""
        if self.state_path.exists():
            raise StateStoreError(f"instance already exists at {self.state_path}")

        self.cerebro_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self.events_path.touch(exist_ok=True)

        initial_state = build_initial_state()
        self.save_state(initial_state)
        return initial_state

    def compute_sha256(self, path: str | Path) -> str:
        """Compute the SHA-256 digest for a file inside the current project root."""
        candidate = Path(path)
        if candidate.is_absolute():
            resolved_path = candidate.resolve()
            try:
                resolved_path.relative_to(self.root)
            except ValueError as exc:
                raise StateStoreError(f"path resolves outside root: {candidate}") from exc
            if not resolved_path.exists() or not resolved_path.is_file():
                raise StateStoreError(f"source file does not exist: {candidate}")
        else:
            resolved_path, _ = self._resolve_registered_path(candidate)
        digest = hashlib.sha256()
        try:
            with resolved_path.open("rb") as handle:
                for chunk in iter(lambda: handle.read(65536), b""):
                    digest.update(chunk)
        except OSError as exc:
            raise StateStoreError(f"failed to read source file: {resolved_path}") from exc
        return digest.hexdigest()

    def load_state(self) -> dict:
        """Load and validate the persisted state."""
        if not self.state_path.exists():
            raise StateStoreError(f"state file not found: {self.state_path}")

        try:
            with self.state_path.open(encoding="utf-8") as handle:
                data = json.load(handle)
        except json.JSONDecodeError as exc:
            raise StateStoreError(f"invalid JSON in state file: {exc.msg}") from exc
        except OSError as exc:
            raise StateStoreError(f"failed to read state file: {self.state_path}") from exc

        errors = validate_state_data(data)
        if errors:
            raise StateValidationError(errors)
        return data

    def read_snapshot(self) -> StateSnapshot:
        """Return a stable read-only snapshot of the current state."""
        state = self.load_state()
        return self._to_snapshot(state)

    def read_checkpoint(self) -> CheckpointRecord:
        """Return the current checkpoint via the stable read interface."""
        return self.read_snapshot().checkpoint

    def read_sources(self) -> tuple[SourceRecord, ...]:
        """Return the current sources via the stable read interface."""
        return self.read_snapshot().sources

    def save_state(self, state: dict) -> None:
        """Validate and atomically persist the state."""
        errors = validate_state_data(state)
        if errors:
            raise StateValidationError(errors)

        self.cerebro_dir.mkdir(parents=True, exist_ok=True)
        self._write_json_atomic(self.state_path, state)

    def prepare_sources(self, paths: list[str]) -> list[dict]:
        """Validate explicit file paths and build the persisted sources list."""
        if not isinstance(paths, list) or not paths:
            raise StateStoreError("paths must be a non-empty list")

        prepared: dict[str, dict] = {}
        for raw_path in paths:
            resolved_path, stored_path = self._resolve_registered_path(raw_path)
            prepared[stored_path] = {
                "path": stored_path,
                "sha256": self.compute_sha256(resolved_path),
                "role": "primary",
            }

        return [prepared[path] for path in sorted(prepared)]

    def register_sources(self, paths: list[str]) -> dict:
        """Replace the full sources list with a new validated set."""
        state = self.load_state()
        sources = self.prepare_sources(paths)
        state["sources"] = sources
        self._bump_revision(state)
        state["last_validation"] = {
            "validated_at": "",
            "result": "fail",
            "details": [
                {
                    "code": "sources_not_validated",
                    "message": "sources changed and must be validated again",
                }
            ],
        }
        self.save_state(state)
        return state

    def update_checkpoint(self, data: dict) -> dict:
        """Replace the checkpoint block with a short explicit checkpoint."""
        checkpoint = self._build_checkpoint_update(data)
        state = self.load_state()
        previous_sources = list(state["sources"])
        state["checkpoint"] = checkpoint
        self._bump_revision(state)
        self.save_state(state)
        if state["sources"] != previous_sources:
            raise StateStoreError("checkpoint update must not change sources")
        return state

    def open_session(self, actor: str) -> dict:
        """Create or overwrite the local session file for the current operator."""
        state = self.load_state()
        if not isinstance(actor, str) or not actor.strip():
            raise StateStoreError("actor must be a non-empty string")

        session = {
            "opened_at": self._timestamp_now(),
            "actor": actor.strip(),
            "based_on_revision": state["revision"],
        }
        errors = validate_session_data(session)
        if errors:
            raise StateValidationError(errors)

        self.cerebro_dir.mkdir(parents=True, exist_ok=True)
        self._write_json_atomic(self.session_path, session)
        return session

    def close_session(self) -> bool:
        """Remove the local session file when present."""
        if self.session_path.exists():
            self.session_path.unlink()
            return True
        return False

    def validate_state(self) -> dict:
        """Validate the persisted state file without raising on user-data failures."""
        if not self.state_path.exists():
            return {
                "ok": False,
                "errors": [error("state_missing", f"state file not found: {self.state_path}")],
            }

        try:
            with self.state_path.open(encoding="utf-8") as handle:
                data = json.load(handle)
        except json.JSONDecodeError as exc:
            return {
                "ok": False,
                "errors": [error("state_invalid_json", f"invalid JSON in state file: {exc.msg}")],
            }
        except OSError:
            return {
                "ok": False,
                "errors": [error("state_unreadable", f"failed to read state file: {self.state_path}")],
            }

        errors = validate_state_data(data)
        if errors:
            return {
                "ok": False,
                "errors": [error("state_invalid_schema", "state file does not match the required schema"), *errors],
            }

        source_errors: list[dict] = []
        for item in data["sources"]:
            try:
                resolved_path, _ = self._resolve_registered_path(item["path"])
            except StateStoreError as exc:
                source_errors.append(self._map_source_resolution_error(str(exc)))
                continue

            current_hash = self.compute_sha256(resolved_path)
            if current_hash != item["sha256"]:
                source_errors.append(
                    error(
                        "source_hash_mismatch",
                        f"registered hash does not match current file content: {item['path']}",
                    )
                )

        session_errors: list[dict] = []
        if self.session_path.exists():
            try:
                with self.session_path.open(encoding="utf-8") as handle:
                    session_data = json.load(handle)
            except json.JSONDecodeError as exc:
                session_errors.append(error("session_invalid_json", f"invalid JSON in session file: {exc.msg}"))
            except OSError:
                session_errors.append(error("session_unreadable", f"failed to read session file: {self.session_path}"))
            else:
                validation_errors = validate_session_data(session_data)
                if validation_errors:
                    session_errors = [
                        error("session_invalid_schema", "session file does not match the required schema"),
                        *validation_errors,
                    ]
                elif session_data["based_on_revision"] > data["revision"]:
                    session_errors.append(
                        error(
                            "session_revision_invalid",
                            "session.based_on_revision cannot be greater than state.revision",
                        )
                    )

        validation_errors = [*source_errors, *session_errors]
        result = {"ok": not validation_errors, "errors": validation_errors}
        revision_before = data["revision"]
        data["last_validation"] = {
            "validated_at": self._timestamp_now(),
            "result": "ok" if result["ok"] else "fail",
            "details": validation_errors,
        }
        self.save_state(data)
        if data["revision"] != revision_before:
            raise StateStoreError("validate_state must not change revision")
        return result

    def _resolve_registered_path(self, path: str | Path) -> tuple[Path, str]:
        """Validate and resolve a stored source path against the project root."""
        if not isinstance(path, (str, Path)):
            raise StateStoreError("source path must be a string")

        raw = str(path).strip()
        if not raw:
            raise StateStoreError("source path must be a non-empty string")

        candidate = Path(raw)
        if candidate.is_absolute():
            raise StateStoreError(f"path must be relative: {raw}")

        if any(part == ".." for part in candidate.parts):
            raise StateStoreError(f"path cannot contain '..': {raw}")

        resolved_path = (self.root / candidate).resolve()
        try:
            relative_path = resolved_path.relative_to(self.root)
        except ValueError as exc:
            raise StateStoreError(f"path resolves outside root: {raw}") from exc

        if not resolved_path.exists() or not resolved_path.is_file():
            raise StateStoreError(f"source file does not exist: {raw}")

        stored_path = relative_path.as_posix()
        return resolved_path, stored_path

    def _map_source_resolution_error(self, message: str) -> dict:
        """Map internal path failures to stable validation codes."""
        if "does not exist" in message:
            return error("source_missing", message)
        if "outside root" in message:
            return error("source_outside_root", message)
        return error("state_invalid_schema", message)

    def _timestamp_now(self) -> str:
        """Return a stable ISO 8601 timestamp in UTC."""
        return datetime.now(timezone.utc).isoformat(timespec="seconds")

    def _bump_revision(self, state: dict) -> None:
        """Increment revision while preserving monotonic integer semantics."""
        revision = state.get("revision")
        if not isinstance(revision, int) or isinstance(revision, bool) or revision < 0:
            raise StateStoreError("revision must be a non-negative integer")
        state["revision"] = revision + 1

    def _build_checkpoint_update(self, data: object) -> dict:
        """Normalize explicit checkpoint input before persistence."""
        if not isinstance(data, dict):
            raise StateStoreError("checkpoint data must be an object")

        expected_keys = {"goal", "summary", "next_step", "constraints"}
        actual_keys = set(data.keys())
        missing = sorted(expected_keys - actual_keys)
        extra = sorted(actual_keys - expected_keys)
        if missing:
            raise StateStoreError(f"checkpoint data missing required keys: {', '.join(missing)}")
        if extra:
            raise StateStoreError(f"checkpoint data contains unexpected keys: {', '.join(extra)}")

        checkpoint = {
            "goal": data["goal"],
            "summary": data["summary"],
            "next_step": data["next_step"],
            "constraints": data["constraints"],
            "updated_at": self._timestamp_now(),
        }
        return checkpoint

    def _write_json_atomic(self, path: Path, data: dict) -> None:
        """Persist a JSON document via write-then-replace."""
        tmp_path = path.with_suffix(f"{path.suffix}.tmp")

        try:
            with tmp_path.open("w", encoding="utf-8", newline="\n") as handle:
                json.dump(data, handle, indent=2, ensure_ascii=False)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp_path, path)
        except OSError as exc:
            raise StateStoreError(f"failed to write file: {path}") from exc
        finally:
            if tmp_path.exists():
                tmp_path.unlink()

    def _to_snapshot(self, state: dict) -> StateSnapshot:
        """Convert the internal JSON representation into the stable read model."""
        return StateSnapshot(
            version=state["version"],
            revision=state["revision"],
            sources=tuple(
                SourceRecord(
                    path=item["path"],
                    sha256=item["sha256"],
                    role=item["role"],
                )
                for item in state["sources"]
            ),
            checkpoint=CheckpointRecord(
                goal=state["checkpoint"]["goal"],
                summary=state["checkpoint"]["summary"],
                next_step=state["checkpoint"]["next_step"],
                constraints=tuple(state["checkpoint"]["constraints"]),
                updated_at=state["checkpoint"]["updated_at"],
            ),
            last_validation=ValidationRecord(
                validated_at=state["last_validation"]["validated_at"],
                result=state["last_validation"]["result"],
                details=tuple(
                    ValidationDetail(code=item["code"], message=item["message"])
                    for item in state["last_validation"]["details"]
                ),
            ),
        )
