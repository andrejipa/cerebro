"""Strongly ordered transition journal primitives."""

from __future__ import annotations

import hashlib
import json
import os
import secrets
import string
from pathlib import Path


class TransitionJournalError(Exception):
    """Raised when the transition journal cannot prove its ordering."""


REQUIRED_EVENT_FIELDS = {
    "event_type",
    "event_version",
    "schema_version",
    "operation_id",
    "pre_state_digest",
    "post_state_digest",
    "deterministic_fields",
    "observational_fields",
}


def canonical_json_bytes(value: object) -> bytes:
    """Return the stable JSON byte representation used by event ids."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def compute_event_id(event: dict) -> str:
    """Compute the canonical event id, excluding only any existing event id."""
    if not isinstance(event, dict):
        raise TransitionJournalError("transition event must be an object")
    payload = {key: value for key, value in event.items() if key != "event_id"}
    try:
        digest = hashlib.sha256(canonical_json_bytes(payload)).hexdigest()
    except (TypeError, ValueError) as exc:
        raise TransitionJournalError("transition event must be JSON-serializable") from exc
    return f"sha256:{digest}"


class TransitionJournal:
    """Append and verify immutable transition events under one directory."""

    def __init__(self, journal_dir: str | Path):
        self.journal_dir = Path(journal_dir)
        self.head_path = self.journal_dir / "HEAD"

    def append_event(self, event: dict) -> dict:
        """Append one event after proving the existing chain is contiguous."""
        self._validate_new_event_input(event)
        committed_events = self.read_events()
        sequence_number = len(committed_events) + 1
        previous_event_id = committed_events[-1]["event_id"] if committed_events else ""
        committed = dict(event)
        committed["sequence_number"] = sequence_number
        committed["previous_event_id"] = previous_event_id
        committed["event_id"] = compute_event_id(committed)

        self.journal_dir.mkdir(parents=True, exist_ok=True)
        target = self._event_path(sequence_number)
        self._write_event_file_once(target, committed)
        self._write_head_cache({"sequence_number": sequence_number, "event_id": committed["event_id"]})
        return dict(committed)

    def read_events(self) -> tuple[dict, ...]:
        """Read all committed events and fail closed on any ordering defect."""
        events: list[dict] = []
        previous_event_id = ""

        for expected_sequence, path in enumerate(self._committed_event_paths(), start=1):
            sequence_number = self._parse_sequence_number(path)
            if sequence_number != expected_sequence:
                raise TransitionJournalError(
                    f"transition journal sequence gap: expected {expected_sequence}, found {sequence_number}"
                )
            event = self._read_event_file(path)
            if event.get("sequence_number") != sequence_number:
                raise TransitionJournalError(f"transition event sequence mismatch: {path.name}")
            if event.get("previous_event_id") != previous_event_id:
                raise TransitionJournalError(f"transition event previous_event_id mismatch: {path.name}")
            expected_event_id = compute_event_id(event)
            if event.get("event_id") != expected_event_id:
                raise TransitionJournalError(f"transition event_id mismatch: {path.name}")
            self._validate_committed_event_shape(event)
            events.append(event)
            previous_event_id = event["event_id"]

        return tuple(events)

    def read_head(self) -> dict:
        """Return a verified head derived from committed events, not from HEAD."""
        events = self.read_events()
        if not events:
            return {"sequence_number": 0, "event_id": ""}
        latest = events[-1]
        return {"sequence_number": latest["sequence_number"], "event_id": latest["event_id"]}

    def _validate_new_event_input(self, event: dict) -> None:
        if not isinstance(event, dict):
            raise TransitionJournalError("transition event must be an object")
        forbidden = {"sequence_number", "previous_event_id", "event_id"}
        present_forbidden = sorted(forbidden.intersection(event))
        if present_forbidden:
            raise TransitionJournalError(
                "transition event input must not predeclare ordering fields: " + ", ".join(present_forbidden)
            )
        self._validate_event_payload_fields(event)

    def _validate_committed_event_shape(self, event: dict) -> None:
        if not isinstance(event.get("sequence_number"), int) or event["sequence_number"] < 1:
            raise TransitionJournalError("transition event sequence_number must be a positive integer")
        if not isinstance(event.get("previous_event_id"), str):
            raise TransitionJournalError("transition event previous_event_id must be a string")
        event_id = event.get("event_id")
        if not isinstance(event_id, str) or not event_id.startswith("sha256:"):
            raise TransitionJournalError("transition event event_id must be a sha256 digest")
        self._validate_event_payload_fields(event)

    def _validate_event_payload_fields(self, event: dict) -> None:
        missing = sorted(field for field in REQUIRED_EVENT_FIELDS if field not in event)
        if missing:
            raise TransitionJournalError("transition event missing required fields: " + ", ".join(missing))
        for field in ("event_type", "operation_id", "pre_state_digest", "post_state_digest"):
            if not isinstance(event.get(field), str) or not event[field]:
                raise TransitionJournalError(f"transition event {field} must be a non-empty string")
        for field in ("pre_state_digest", "post_state_digest"):
            if not _is_sha256_digest(event[field]):
                raise TransitionJournalError(f"transition event {field} must be a sha256 digest")
        for field in ("event_version", "schema_version"):
            if not isinstance(event.get(field), int) or event[field] < 1:
                raise TransitionJournalError(f"transition event {field} must be a positive integer")
        for field in ("deterministic_fields", "observational_fields"):
            if not isinstance(event.get(field), dict):
                raise TransitionJournalError(f"transition event {field} must be an object")

    def _committed_event_paths(self) -> tuple[Path, ...]:
        if not self.journal_dir.exists():
            return ()
        paths = []
        for path in self.journal_dir.iterdir():
            if not path.is_file() or path.name == "HEAD":
                continue
            if path.suffix != ".json":
                continue
            stem = path.stem
            if len(stem) != 18 or not stem.isdigit():
                raise TransitionJournalError(f"invalid transition journal file name: {path.name}")
            paths.append(path)
        return tuple(sorted(paths, key=self._parse_sequence_number))

    def _event_path(self, sequence_number: int) -> Path:
        return self.journal_dir / f"{sequence_number:018d}.json"

    def _parse_sequence_number(self, path: Path) -> int:
        try:
            return int(path.stem)
        except ValueError as exc:
            raise TransitionJournalError(f"invalid transition sequence file name: {path.name}") from exc

    def _read_event_file(self, path: Path) -> dict:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise TransitionJournalError(f"invalid JSON in transition event: {path.name}") from exc
        except OSError as exc:
            raise TransitionJournalError(f"failed to read transition event: {path}") from exc
        if not isinstance(payload, dict):
            raise TransitionJournalError(f"transition event file must contain an object: {path.name}")
        return payload

    def _write_event_file_once(self, path: Path, payload: dict) -> None:
        data = canonical_json_bytes(payload) + b"\n"
        try:
            with path.open("xb") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            self._cleanup_abandoned_temps(path, keep=path)
        except FileExistsError as exc:
            raise TransitionJournalError(f"transition sequence already exists: {self._parse_sequence_number(path)}") from exc
        except OSError as exc:
            raise TransitionJournalError(f"failed to persist transition journal file: {path}") from exc

    def _write_json_replace(self, path: Path, payload: dict) -> None:
        tmp_path = path.with_name(f"{path.name}.{secrets.token_hex(8)}.tmp")
        data = canonical_json_bytes(payload) + b"\n"
        try:
            with tmp_path.open("xb") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp_path, path)
            self._cleanup_abandoned_temps(path, keep=tmp_path)
        except OSError as exc:
            raise TransitionJournalError(f"failed to persist transition journal file: {path}") from exc
        finally:
            if tmp_path.exists():
                try:
                    tmp_path.unlink()
                except OSError:
                    pass

    def _write_head_cache(self, payload: dict) -> None:
        try:
            self._write_json_replace(self.head_path, payload)
        except TransitionJournalError:
            return

    def _cleanup_abandoned_temps(self, path: Path, *, keep: Path) -> None:
        if not path.parent.exists():
            return
        patterns = (f"{path.name}.tmp", f"{path.name}.*.tmp")
        for pattern in patterns:
            for candidate in path.parent.glob(pattern):
                if candidate == keep or not candidate.is_file():
                    continue
                try:
                    candidate.unlink()
                except OSError:
                    pass


def _is_sha256_digest(value: object) -> bool:
    if not isinstance(value, str):
        return False
    prefix = "sha256:"
    if not value.startswith(prefix):
        return False
    digest = value[len(prefix) :]
    return len(digest) == 64 and all(character in string.hexdigits for character in digest)
