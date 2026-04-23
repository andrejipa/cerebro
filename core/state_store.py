"""Persistent state access for the minimal checkpoint system."""

from __future__ import annotations

from copy import deepcopy
import errno
import hashlib
import hmac
import json
import os
import secrets
import shutil
import threading
import time
from contextlib import contextmanager
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4
from typing import Callable, TypeVar

from core.agent_runtime import (
    MAX_ACTION_HISTORY,
    MAX_APPROVAL_ITEMS,
    MAX_ROLLBACK_POINTS,
    MAX_USED_BATCH_IDS,
    canonicalize_state_data,
    iter_command_checks,
)
from core.decision_runtime import choose_next_task
from core.memory_runtime import (
    sync_approval_memory_notes,
    sync_success_memory_notes,
    sync_verification_memory_notes,
)
from core.read_models import (
    CheckpointRecord,
    SourceRecord,
    StateSnapshot,
    ValidationDetail,
    ValidationRecord,
)
from core.state_read_model_service import StateReadModelService
from core.state_session_artifacts_service import (
    SESSION_CLAIMS_DIR_ENV_VAR,
    SESSION_CLAIM_BACKEND_FILE,
    SESSION_CLAIM_BACKEND_WINCRED,
    SESSION_LIVE_PROOFS_DIR_ENV_VAR,
    SESSION_LIVE_PROOF_BACKEND_FILE,
    SESSION_LIVE_PROOF_BACKEND_WINCRED,
    WINCRED_COMPRESSED_PAYLOAD_PREFIX,
    WINCRED_PACKED_SESSION_CLAIM_PREFIX,
    WINCRED_PACKED_SESSION_LIVE_PROOF_PREFIX,
    WINCRED_SESSION_CLAIM_FIELDS,
    WINCRED_SESSION_LIVE_PROOF_FIELDS,
    StateSessionArtifactsService,
    WindowsCredentialStoreError,
    delete_generic_credential,
    read_generic_credential,
    write_generic_credential,
)
from core.schema import build_initial_state
from core.validation import error, validate_session_data, validate_state_data

VALIDATION_RETRY_LIMIT = 3
RUNTIME_LOCK_TIMEOUT_SECONDS = 5.0
RUNTIME_LOCK_POLL_SECONDS = 0.01
RUNTIME_LOCK_RELEASE_RETRY_LIMIT = 3
TRACE_DURABILITY_ENV_VAR = "CEREBRO_TRACE_DURABILITY"
TRACE_DURABILITY_BALANCED = "balanced"
TRACE_DURABILITY_STRICT = "strict"
TRACE_DURABILITY_MODES = {TRACE_DURABILITY_BALANCED, TRACE_DURABILITY_STRICT}
RETENTION_NON_CONSOLIDATION_EVENT_LIMIT = 20_000
RETENTION_VERIFICATION_GROUP_LIMIT = 20
RETENTION_ACTION_GROUP_LIMIT = 64
_T = TypeVar("_T")


class StateStoreError(Exception):
    """Base exception for state store failures."""


class StateValidationError(StateStoreError):
    """Raised when state data is structurally invalid."""

    def __init__(self, errors: list[dict]):
        super().__init__("state validation failed")
        self.errors = errors


class StateStore:
    """Read and write the only persistent state file for the system."""

    _process_runtime_lock_counts: dict[str, int] = {}
    _process_runtime_lock_guard = threading.Lock()

    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()
        self.cerebro_dir = self.root / ".cerebro"
        self.state_path = self.cerebro_dir / "state.json"
        self.session_path = self.cerebro_dir / "session.local.json"
        self.session_refresh_pending_path = self.cerebro_dir / "session.refresh.pending.json"
        self._session_artifacts = StateSessionArtifactsService(
            root=self.root,
            session_path=self.session_path,
            read_optional_file_bytes=self._read_optional_file_bytes,
            write_bytes_atomic=self._write_bytes_atomic,
            error_cls=StateStoreError,
            read_generic_credential_func=lambda target_name: read_generic_credential(target_name),
            write_generic_credential_func=lambda target_name, payload: write_generic_credential(target_name, payload),
            delete_generic_credential_func=lambda target_name: delete_generic_credential(target_name),
            windows_credential_store_error_cls=WindowsCredentialStoreError,
        )
        self.claims_dir = self._session_artifacts.claims_dir
        self.live_proofs_dir = self._session_artifacts.live_proofs_dir
        self.lock_path = self.cerebro_dir / "runtime.lock"
        self.logs_dir = self.cerebro_dir / "logs"
        self.events_path = self.logs_dir / "events.jsonl"
        self.artifacts_dir = self.cerebro_dir / "artifacts"
        self.trash_dir = self.cerebro_dir / "trash"
        self._lock_fd: int | None = None
        self._lock_depth = 0
        self._read_models = StateReadModelService(
            load_agent_runtime=lambda: self.read_agent_runtime(),
            load_task_assessments=lambda **kwargs: self.read_task_assessments(**kwargs),
        )

    def initialize(self) -> dict:
        """Create the minimal instance layout and initial state."""
        with self.runtime_lock():
            if self.state_path.exists():
                raise StateStoreError(f"instance already exists at {self.state_path}")

            self.cerebro_dir.mkdir(parents=True, exist_ok=True)
            self.logs_dir.mkdir(parents=True, exist_ok=True)
            self.artifacts_dir.mkdir(parents=True, exist_ok=True)
            self.trash_dir.mkdir(parents=True, exist_ok=True)
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
        signature_before = self._file_signature(resolved_path)
        try:
            with resolved_path.open("rb") as handle:
                for chunk in iter(lambda: handle.read(65536), b""):
                    digest.update(chunk)
        except OSError as exc:
            raise StateStoreError(f"failed to read source file: {resolved_path}") from exc
        signature_after = self._file_signature(resolved_path)
        if signature_after != signature_before:
            raise StateStoreError(f"source file changed during read: {resolved_path}")
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

        data = canonicalize_state_data(data)
        errors = validate_state_data(data)
        if errors:
            raise StateValidationError(errors)
        return data

    def read_snapshot(self) -> StateSnapshot:
        """Return a stable read-only snapshot of the current state."""
        state = self.load_state()
        return self._to_snapshot(state)

    def read_snapshot_and_runtime(self) -> tuple[StateSnapshot, dict]:
        """Return one coherent snapshot plus a detached runtime copy from a single state load."""
        state = self.load_state()
        return self._to_snapshot(state), deepcopy(state["agent_runtime"])

    def read_checkpoint(self) -> CheckpointRecord:
        """Return the current checkpoint via the stable read interface."""
        return self.read_snapshot().checkpoint

    def read_sources(self) -> tuple[SourceRecord, ...]:
        """Return the current sources via the stable read interface."""
        return self.read_snapshot().sources

    def read_agent_runtime(self) -> dict:
        """Return a copy of the alpha-runtime block from the canonical state."""
        state = self.load_state()
        return deepcopy(state["agent_runtime"])

    def read_trace_observability(self, *, agent_runtime: dict | None = None) -> dict:
        """Return the current trace-plane health and analytical integrity."""
        agent_runtime = deepcopy(agent_runtime) if agent_runtime is not None else self.read_agent_runtime()
        audit = agent_runtime["audit"]
        status = audit.get("trace_status", "healthy")
        integrity = audit.get("trace_integrity", "reliable")
        thread_id = audit.get("trace_thread_id", "bootstrap")
        next_event_id = audit.get("next_event_id", 1)
        expected_last_event_number = next_event_id - 1 if isinstance(next_event_id, int) and next_event_id >= 1 else 0
        reasons: list[str] = []
        latest_event_id = ""
        latest_event_number = 0

        try:
            recent_events = self.read_recent_events(limit=50)
        except StateStoreError as exc:
            return {
                "trace_status": "degraded",
                "trace_integrity": "partial",
                "trace_thread_id": thread_id,
                "next_event_id": next_event_id,
                "expected_last_event_number": expected_last_event_number,
                "latest_event_id": "",
                "latest_event_number": 0,
                "diagnostics": ("trace_read_failed", str(exc)),
                "durability_mode": self._trace_durability_mode(),
            }

        if any(isinstance(event, dict) and event.get("event") == "unreadable_event_log_record" for event in recent_events):
            integrity = "partial"
            reasons.append("unreadable_event_log_record")

        for event in reversed(recent_events):
            if not isinstance(event, dict):
                continue
            if event.get("trace_thread_id") != thread_id:
                continue
            candidate_event_id = event.get("event_id", "")
            candidate_number = self._parse_trace_event_number(candidate_event_id, thread_id)
            if candidate_number is not None:
                latest_event_id = candidate_event_id
                latest_event_number = candidate_number
                break

        if latest_event_number < expected_last_event_number:
            integrity = "partial"
            reasons.append("state_event_gap")

        return {
            "trace_status": status,
            "trace_integrity": integrity,
            "trace_thread_id": thread_id,
            "next_event_id": next_event_id,
            "expected_last_event_number": expected_last_event_number,
            "latest_event_id": latest_event_id,
            "latest_event_number": latest_event_number,
            "diagnostics": tuple(reasons),
            "durability_mode": self._trace_durability_mode(),
        }

    def read_recent_events(self, limit: int = 10) -> tuple[dict, ...]:
        """Return the most recent audit events from the append-only runtime log."""
        if limit <= 0:
            return ()
        if not self.events_path.exists():
            return ()

        try:
            recent_lines = self._read_recent_event_lines(limit)
        except OSError as exc:
            raise StateStoreError(f"failed to read event log: {self.events_path}") from exc

        events: list[dict] = []
        for raw_line in recent_lines:
            try:
                parsed = json.loads(raw_line)
            except json.JSONDecodeError:
                parsed = {
                    "recorded_at": "",
                    "event": "unreadable_event_log_record",
                }
            if isinstance(parsed, dict):
                events.append(parsed)
            else:
                events.append(
                    {
                        "recorded_at": "",
                        "event": "unreadable_event_log_record",
                    }
                )
        return tuple(events)

    def read_recent_consolidations(self, limit: int = 5) -> tuple[dict, ...]:
        """Return the most recent parallel-approach consolidation records."""
        if limit <= 0:
            return ()
        if not self.events_path.exists():
            return ()
        try:
            recent, _ = self._read_parallel_approach_consolidation_view(limit=limit, subjects=())
            return recent
        except OSError as exc:
            raise StateStoreError(f"failed to read event log: {self.events_path}") from exc

    def read_parallel_approach_consolidation_view(
        self,
        limit: int = 5,
        subjects: tuple[tuple[str, str], ...] | list[tuple[str, str]] = (),
    ) -> tuple[tuple[dict, ...], dict[tuple[str, str], dict]]:
        """Return recent consolidation heads plus current heads for requested subjects."""
        if limit <= 0 and not subjects:
            return (), {}
        if not self.events_path.exists():
            return (), {}
        try:
            return self._read_parallel_approach_consolidation_view(limit=limit, subjects=subjects)
        except OSError as exc:
            raise StateStoreError(f"failed to read event log: {self.events_path}") from exc

    def read_parallel_approach_consolidation_head(self, subject_kind: str, subject_id: str) -> dict | None:
        """Return the current valid consolidation head for one subject, if it exists."""
        if not self.events_path.exists():
            return None
        try:
            return self._read_parallel_approach_consolidation_head(subject_kind, subject_id)
        except OSError as exc:
            raise StateStoreError(f"failed to read event log: {self.events_path}") from exc

    def read_parallel_approach_consolidation_heads(
        self,
        subjects: tuple[tuple[str, str], ...] | list[tuple[str, str]],
    ) -> dict[tuple[str, str], dict]:
        """Return current valid consolidation heads for the requested subjects."""
        if not self.events_path.exists():
            return {}
        normalized_subjects: set[tuple[str, str]] = set()
        for subject_kind, subject_id in subjects:
            subject_key = self._parallel_approach_subject_key(subject_kind, subject_id)
            if subject_key is not None:
                normalized_subjects.add(subject_key)
        if not normalized_subjects:
            return {}
        try:
            histories = self._read_parallel_approach_consolidation_histories(normalized_subjects)
        except OSError as exc:
            raise StateStoreError(f"failed to read event log: {self.events_path}") from exc

        heads: dict[tuple[str, str], dict] = {}
        for subject_key, records_by_id in histories.items():
            head = self._select_parallel_approach_consolidation_head(records_by_id)
            if head is not None:
                heads[subject_key] = self._strip_parallel_approach_consolidation_internal_fields(head)
        return heads

    def record_parallel_approach_consolidation(self, consolidation: dict) -> None:
        """Append one explicit consolidation record to the audit trail."""
        if not isinstance(consolidation, dict):
            raise StateStoreError("parallel approach consolidation must be an object")
        with self.runtime_lock():
            state = self.load_state()
            normalized = dict(consolidation)
            subject_kind = normalized.get("subject_kind", "")
            subject_id = normalized.get("subject_id", "")
            current_head = self._read_parallel_approach_consolidation_head(subject_kind, subject_id)
            current_head_id = current_head["consolidation_id"] if isinstance(current_head, dict) else ""
            if not isinstance(normalized.get("consolidation_id"), str) or not normalized.get("consolidation_id", "").strip():
                normalized["consolidation_id"] = self._generate_parallel_approach_consolidation_id(
                    subject_kind,
                    subject_id,
                )
            raw_supersedes = normalized.get("supersedes_consolidation_id", "")
            if not isinstance(raw_supersedes, str):
                raise StateStoreError("parallel approach consolidation supersedes_consolidation_id must be a string")
            normalized_supersedes = raw_supersedes.strip()
            if not normalized_supersedes:
                normalized["supersedes_consolidation_id"] = current_head_id
            elif normalized_supersedes != current_head_id:
                if current_head_id:
                    raise StateStoreError(
                        "parallel approach consolidation must supersede the current head for the same subject"
                    )
                raise StateStoreError(
                    "parallel approach consolidation cannot supersede a previous record when no current head exists"
                )
            payload = self._build_parallel_approach_consolidation_event(normalized)
            self._record_trace_only_events(
                state,
                [
                    {
                        "event_type": "parallel_approach_consolidated",
                        "phase": "record",
                        "step": "parallel_approach_consolidated",
                        "payload": payload,
                    }
                ],
            )

    def parse_parallel_approach_consolidation_event(self, event: object) -> dict | None:
        """Expose the shared consolidation parser for read-only consumers."""
        return self._parse_parallel_approach_consolidation(event)

    def _read_recent_event_lines(self, limit: int) -> tuple[str, ...]:
        """Return up to ``limit`` recent non-empty event-log lines in chronological order."""
        lines: deque[str] = deque(maxlen=limit)
        with self.events_path.open("rb") as handle:
            handle.seek(0, os.SEEK_END)
            position = handle.tell()
            buffer = b""

            while position > 0 and len(lines) < limit:
                read_size = min(8192, position)
                position -= read_size
                handle.seek(position)
                buffer = handle.read(read_size) + buffer
                segments = buffer.split(b"\n")
                buffer = segments[0]

                for raw_line in reversed(segments[1:]):
                    stripped = raw_line.strip()
                    if not stripped:
                        continue
                    lines.appendleft(stripped.decode("utf-8", errors="replace"))
                    if len(lines) >= limit:
                        break

            if position == 0:
                stripped = buffer.strip()
                if stripped and len(lines) < limit:
                    lines.appendleft(stripped.decode("utf-8", errors="replace"))

        return tuple(lines)

    def _read_recent_consolidations(self, limit: int) -> tuple[dict, ...]:
        """Return recent subject heads after validating each subject's consolidation chain."""
        recent, _ = self._read_parallel_approach_consolidation_view(limit=limit, subjects=())
        return recent

    def _read_parallel_approach_consolidation_view(
        self,
        limit: int,
        subjects: tuple[tuple[str, str], ...] | list[tuple[str, str]],
    ) -> tuple[tuple[dict, ...], dict[tuple[str, str], dict]]:
        """Build one shared consolidation read-model from a single history scan."""
        histories = self._read_parallel_approach_consolidation_histories()
        heads: list[dict] = []
        head_map: dict[tuple[str, str], dict] = {}
        requested_subjects = {
            subject_key
            for subject_key in (
                self._parallel_approach_subject_key(subject_kind, subject_id)
                for subject_kind, subject_id in subjects
            )
            if subject_key is not None
        }
        for records_by_id in histories.values():
            head = self._select_parallel_approach_consolidation_head(records_by_id)
            if head is not None:
                heads.append(head)
                subject_key = (head["subject_kind"], head["subject_id"])
                if subject_key in requested_subjects:
                    head_map[subject_key] = self._strip_parallel_approach_consolidation_internal_fields(head)

        heads.sort(
            key=lambda item: (
                -int(item.get("_tail_rank", 0)),
                item["subject_kind"],
                item["subject_id"],
            )
        )
        recent = tuple(self._strip_parallel_approach_consolidation_internal_fields(item) for item in heads[-limit:]) if limit > 0 else ()
        return recent, head_map

    def _read_parallel_approach_consolidation_head(self, subject_kind: object, subject_id: object) -> dict | None:
        """Return the current head for one subject after validating the full append-only chain."""
        subject_key = self._parallel_approach_subject_key(subject_kind, subject_id)
        if subject_key is None:
            return None
        histories = self._read_parallel_approach_consolidation_histories({subject_key})
        records_by_id = histories.get(subject_key)
        if not records_by_id:
            return None
        head = self._select_parallel_approach_consolidation_head(records_by_id)
        if head is None:
            return None
        return self._strip_parallel_approach_consolidation_internal_fields(head)

    def _parse_parallel_approach_consolidation_line(self, raw_line: bytes) -> dict | None:
        """Parse one raw event-log line into a valid consolidation record when possible."""
        stripped = raw_line.strip()
        if not stripped:
            return None
        if b"parallel_approach_consolidated" not in stripped:
            return None
        if b"\"event\"" not in stripped:
            return None
        try:
            parsed = json.loads(stripped.decode("utf-8", errors="replace"))
        except json.JSONDecodeError:
            return None
        return self._parse_parallel_approach_consolidation(parsed)

    def _parse_event_log_event_type(self, raw_line: bytes) -> str | None:
        """Return one event-log event_type when the raw line decodes cleanly."""
        stripped = raw_line.strip()
        if not stripped or b"\"event_type\"" not in stripped:
            return None
        try:
            parsed = json.loads(stripped.decode("utf-8", errors="replace"))
        except json.JSONDecodeError:
            return None
        event_type = parsed.get("event_type")
        if not isinstance(event_type, str) or not event_type:
            return None
        return event_type

    def _build_parallel_approach_consolidation_event(self, consolidation: dict) -> dict:
        """Normalize one explicit consolidation record before appending it."""
        expected_keys = {
            "consolidation_id",
            "supersedes_consolidation_id",
            "subject_kind",
            "subject_id",
            "compared_approach_ids",
            "winner_id",
            "winner_label",
            "rejected_approach_ids",
            "comparison_basis",
            "decision",
            "comparison_event_ids",
        }
        actual_keys = set(consolidation.keys())
        missing = sorted(expected_keys - actual_keys)
        extra = sorted(actual_keys - expected_keys)
        if missing:
            raise StateStoreError(f"parallel approach consolidation missing required keys: {', '.join(missing)}")
        if extra:
            raise StateStoreError(f"parallel approach consolidation contains unexpected keys: {', '.join(extra)}")

        consolidation_id = consolidation["consolidation_id"]
        supersedes_consolidation_id = consolidation["supersedes_consolidation_id"]
        subject_kind = consolidation["subject_kind"]
        subject_id = consolidation["subject_id"]
        compared_approach_ids = self._normalize_unique_strings(consolidation["compared_approach_ids"])
        winner_id = consolidation["winner_id"]
        winner_label = consolidation["winner_label"]
        decision = consolidation["decision"]
        rejected_approach_ids = self._normalize_unique_strings(consolidation["rejected_approach_ids"])
        comparison_basis = self._normalize_unique_strings(consolidation["comparison_basis"])
        comparison_event_ids = self._normalize_unique_strings(consolidation["comparison_event_ids"])

        if not isinstance(subject_kind, str) or not subject_kind.strip():
            raise StateStoreError("parallel approach consolidation subject_kind must be a non-empty string")
        if not isinstance(subject_id, str) or not subject_id.strip():
            raise StateStoreError("parallel approach consolidation subject_id must be a non-empty string")
        if not isinstance(consolidation_id, str) or not consolidation_id.strip():
            raise StateStoreError("parallel approach consolidation consolidation_id must be a non-empty string")
        if not isinstance(supersedes_consolidation_id, str):
            raise StateStoreError("parallel approach consolidation supersedes_consolidation_id must be a string")
        if len(compared_approach_ids) < 2:
            raise StateStoreError("parallel approach consolidation must compare at least two approach ids")
        if not isinstance(winner_id, str) or not winner_id.strip():
            raise StateStoreError("parallel approach consolidation winner_id must be a non-empty string")
        if not isinstance(winner_label, str) or not winner_label.strip():
            raise StateStoreError("parallel approach consolidation winner_label must be a non-empty string")
        if not isinstance(decision, str) or not decision.strip():
            raise StateStoreError("parallel approach consolidation decision must be a non-empty string")
        if not rejected_approach_ids:
            raise StateStoreError("parallel approach consolidation must reject at least one competing approach")
        if not comparison_basis:
            raise StateStoreError("parallel approach consolidation must include at least one comparison basis item")
        if not comparison_event_ids:
            raise StateStoreError("parallel approach consolidation must include at least one comparison_event_id")
        normalized_winner_id = winner_id.strip()
        if normalized_winner_id not in compared_approach_ids:
            raise StateStoreError("parallel approach consolidation winner_id must be part of compared_approach_ids")
        if set(compared_approach_ids) != {normalized_winner_id, *rejected_approach_ids}:
            raise StateStoreError(
                "parallel approach consolidation must cover the full compared set with exactly one winner and the remaining rejected approaches"
            )

        if normalized_winner_id in rejected_approach_ids:
            raise StateStoreError("winner_id cannot also appear in rejected_approach_ids")
        if supersedes_consolidation_id.strip() == consolidation_id.strip():
            raise StateStoreError("consolidation cannot supersede itself")

        event = {
            "consolidation_id": consolidation_id.strip(),
            "supersedes_consolidation_id": supersedes_consolidation_id.strip(),
            "subject_kind": subject_kind.strip(),
            "subject_id": subject_id.strip(),
            "compared_approach_ids": compared_approach_ids,
            "winner_id": normalized_winner_id,
            "winner_label": winner_label.strip(),
            "rejected_approach_ids": rejected_approach_ids,
            "comparison_basis": comparison_basis,
            "decision": decision.strip(),
            "comparison_event_ids": comparison_event_ids,
        }
        return event

    def _parse_parallel_approach_consolidation(self, event: object) -> dict | None:
        """Return a normalized consolidation record when the event matches the expected shape."""
        if not isinstance(event, dict) or event.get("event") != "parallel_approach_consolidated":
            return None

        subject_kind = event.get("subject_kind")
        subject_id = event.get("subject_id")
        consolidation_id = event.get("consolidation_id")
        supersedes_consolidation_id = event.get("supersedes_consolidation_id", "")
        compared_approach_ids = self._normalize_unique_strings(event.get("compared_approach_ids", []))
        winner_id = event.get("winner_id")
        winner_label = event.get("winner_label", "")
        decision = event.get("decision")
        rejected_approach_ids = self._normalize_unique_strings(event.get("rejected_approach_ids", []))
        comparison_basis = self._normalize_unique_strings(event.get("comparison_basis", []))
        comparison_event_ids = self._normalize_unique_strings(event.get("comparison_event_ids", []))
        recorded_at = event.get("recorded_at", "")

        if not isinstance(subject_kind, str) or not subject_kind.strip():
            return None
        if not isinstance(subject_id, str) or not subject_id.strip():
            return None
        if isinstance(consolidation_id, str) and consolidation_id.strip():
            normalized_consolidation_id = consolidation_id.strip()
        else:
            normalized_consolidation_id = self._synthesize_parallel_approach_consolidation_id(
                event,
                subject_kind,
                subject_id,
            )
        if not isinstance(supersedes_consolidation_id, str):
            return None
        if not isinstance(winner_id, str) or not winner_id.strip():
            return None
        if not isinstance(winner_label, str) or not winner_label.strip():
            return None
        if not isinstance(decision, str) or not decision.strip():
            return None
        if (
            len(compared_approach_ids) < 2
            or not rejected_approach_ids
            or not comparison_basis
            or not comparison_event_ids
        ):
            return None
        if not isinstance(recorded_at, str):
            recorded_at = ""
        normalized_winner_id = winner_id.strip()
        if normalized_winner_id not in compared_approach_ids:
            return None
        if set(compared_approach_ids) != {normalized_winner_id, *rejected_approach_ids}:
            return None

        return {
            "recorded_at": recorded_at,
            "consolidation_id": normalized_consolidation_id,
            "supersedes_consolidation_id": supersedes_consolidation_id.strip(),
            "subject_kind": subject_kind.strip(),
            "subject_id": subject_id.strip(),
            "compared_approach_ids": tuple(compared_approach_ids),
            "winner_id": normalized_winner_id,
            "winner_label": winner_label.strip(),
            "rejected_approach_ids": tuple(rejected_approach_ids),
            "comparison_basis": tuple(comparison_basis),
            "decision": decision.strip(),
            "comparison_event_ids": tuple(comparison_event_ids),
        }

    def _generate_parallel_approach_consolidation_id(self, subject_kind: object, subject_id: object) -> str:
        """Create a short opaque id for one consolidation record."""
        kind = subject_kind if isinstance(subject_kind, str) else "subject"
        subject = subject_id if isinstance(subject_id, str) else "unknown"
        return f"cons-{kind.strip() or 'subject'}-{subject.strip() or 'unknown'}-{uuid4().hex[:10]}"

    def _find_latest_parallel_approach_consolidation_id(self, subject_kind: object, subject_id: object) -> str:
        """Return the latest consolidation id recorded for one subject, if any."""
        head = self._read_parallel_approach_consolidation_head(subject_kind, subject_id)
        if head is None:
            return ""
        return head["consolidation_id"]

    def _parallel_approach_subject_key(self, subject_kind: object, subject_id: object) -> tuple[str, str] | None:
        """Return a normalized subject key when both parts are non-empty strings."""
        if not isinstance(subject_kind, str) or not isinstance(subject_id, str):
            return None
        normalized_kind = subject_kind.strip()
        normalized_subject = subject_id.strip()
        if not normalized_kind or not normalized_subject:
            return None
        return normalized_kind, normalized_subject

    def _read_parallel_approach_consolidation_histories(
        self,
        subject_filter: set[tuple[str, str]] | None = None,
    ) -> dict[tuple[str, str], dict[str, dict]]:
        """Collect valid consolidation records grouped by subject and deduplicated by id."""
        if not self.events_path.exists():
            return {}
        histories: dict[tuple[str, str], dict[str, dict]] = {}
        invalid_subjects: set[tuple[str, str]] = set()
        tail_rank = 0
        with self.events_path.open("rb") as handle:
            handle.seek(0, os.SEEK_END)
            position = handle.tell()
            buffer = b""

            while position > 0:
                read_size = min(8192, position)
                position -= read_size
                handle.seek(position)
                buffer = handle.read(read_size) + buffer
                segments = buffer.split(b"\n")
                buffer = segments[0]

                for raw_line in reversed(segments[1:]):
                    tail_rank += self._collect_parallel_approach_consolidation_history_entry(
                        raw_line,
                        histories,
                        invalid_subjects,
                        subject_filter,
                        tail_rank + 1,
                    )

            if position == 0:
                tail_rank += self._collect_parallel_approach_consolidation_history_entry(
                    buffer,
                    histories,
                    invalid_subjects,
                    subject_filter,
                    tail_rank + 1,
                )

        for subject_key in invalid_subjects:
            histories.pop(subject_key, None)
        return histories

    def _collect_parallel_approach_consolidation_history_entry(
        self,
        raw_line: bytes,
        histories: dict[tuple[str, str], dict[str, dict]],
        invalid_subjects: set[tuple[str, str]],
        subject_filter: set[tuple[str, str]] | None,
        tail_rank: int,
    ) -> int:
        """Collect one consolidation record into the per-subject history index."""
        consolidation = self._parse_parallel_approach_consolidation_line(raw_line)
        if consolidation is None:
            return 0
        subject_key = (consolidation["subject_kind"], consolidation["subject_id"])
        if subject_filter is not None and subject_key not in subject_filter:
            return 0
        if subject_key in invalid_subjects:
            return 0

        records_by_id = histories.setdefault(subject_key, {})
        existing = records_by_id.get(consolidation["consolidation_id"])
        if existing is None:
            records_by_id[consolidation["consolidation_id"]] = {
                **consolidation,
                "_tail_rank": tail_rank,
            }
            return 1
        if not self._parallel_approach_consolidation_records_equivalent(existing, consolidation):
            invalid_subjects.add(subject_key)
            histories.pop(subject_key, None)
        return 0

    def _parallel_approach_consolidation_records_equivalent(self, left: dict, right: dict) -> bool:
        """Compare consolidation payloads while ignoring read-model-only metadata."""
        comparable_fields = (
            "consolidation_id",
            "supersedes_consolidation_id",
            "subject_kind",
            "subject_id",
            "compared_approach_ids",
            "winner_id",
            "winner_label",
            "rejected_approach_ids",
            "comparison_basis",
            "decision",
            "comparison_event_ids",
        )
        return all(left.get(field) == right.get(field) for field in comparable_fields)

    def _select_parallel_approach_consolidation_head(self, records_by_id: dict[str, dict]) -> dict | None:
        """Return the unique linear-chain head for a subject, or None when the chain is ambiguous."""
        if not records_by_id:
            return None

        child_by_parent: dict[str, str] = {}
        root_id = ""
        for record in records_by_id.values():
            consolidation_id = record["consolidation_id"]
            supersedes_consolidation_id = record["supersedes_consolidation_id"]
            if not supersedes_consolidation_id:
                if root_id and root_id != consolidation_id:
                    return None
                root_id = consolidation_id
                continue
            if supersedes_consolidation_id not in records_by_id:
                return None
            existing_child = child_by_parent.get(supersedes_consolidation_id)
            if existing_child and existing_child != consolidation_id:
                return None
            child_by_parent[supersedes_consolidation_id] = consolidation_id

        if not root_id:
            return None

        visited: set[str] = set()
        current_id = root_id
        while True:
            if current_id in visited:
                return None
            visited.add(current_id)
            next_id = child_by_parent.get(current_id)
            if not next_id:
                break
            current_id = next_id

        if len(visited) != len(records_by_id):
            return None
        return records_by_id[current_id]

    def _strip_parallel_approach_consolidation_internal_fields(self, consolidation: dict) -> dict:
        """Drop read-model-only metadata before exposing a consolidation record."""
        return {
            key: value
            for key, value in consolidation.items()
            if not key.startswith("_")
        }

    def _synthesize_parallel_approach_consolidation_id(
        self,
        event: object,
        subject_kind: object,
        subject_id: object,
    ) -> str:
        """Create a deterministic legacy id for consolidation events that predate explicit ids."""
        comparable = {
            "subject_kind": subject_kind.strip() if isinstance(subject_kind, str) else "",
            "subject_id": subject_id.strip() if isinstance(subject_id, str) else "",
            "compared_approach_ids": self._normalize_unique_strings(event.get("compared_approach_ids", []))
            if isinstance(event, dict)
            else [],
            "winner_id": event.get("winner_id", "").strip()
            if isinstance(event, dict) and isinstance(event.get("winner_id"), str)
            else "",
            "winner_label": event.get("winner_label", "").strip()
            if isinstance(event, dict) and isinstance(event.get("winner_label"), str)
            else "",
            "rejected_approach_ids": self._normalize_unique_strings(event.get("rejected_approach_ids", []))
            if isinstance(event, dict)
            else [],
            "comparison_basis": self._normalize_unique_strings(event.get("comparison_basis", []))
            if isinstance(event, dict)
            else [],
            "decision": event.get("decision", "").strip()
            if isinstance(event, dict) and isinstance(event.get("decision"), str)
            else "",
            "comparison_event_ids": self._normalize_unique_strings(event.get("comparison_event_ids", []))
            if isinstance(event, dict)
            else [],
        }
        digest = hashlib.sha256(json.dumps(comparable, sort_keys=True).encode("utf-8")).hexdigest()[:12]
        return f"legacy-cons-{digest}"

    def _normalize_unique_strings(self, values: object) -> list[str]:
        """Return string items in first-seen order without blanks or duplicates."""
        if not isinstance(values, list):
            return []
        normalized: list[str] = []
        for item in values:
            if not isinstance(item, str):
                continue
            cleaned = item.strip()
            if not cleaned or cleaned in normalized:
                continue
            normalized.append(cleaned)
        return normalized

    def read_task_assessments(
        self,
        event_limit: int = 20,
        *,
        agent_runtime: dict | None = None,
        recent_events: tuple[dict, ...] | None = None,
    ) -> tuple[dict, ...]:
        """Return evidence-backed task assessments derived from canonical runtime state."""
        return self._read_models.read_task_assessments(
            event_limit=event_limit,
            agent_runtime=agent_runtime,
            recent_events=recent_events,
        )

    def read_task_selection_consistency(
        self,
        *,
        agent_runtime: dict | None = None,
        recent_events: tuple[dict, ...] | None = None,
        task_assessments: tuple[dict, ...] | list[dict] | None = None,
    ) -> dict:
        """Replay task selection from read-only state and report whether it still matches current_task_id."""
        return self._read_models.read_task_selection_consistency(
            agent_runtime=agent_runtime,
            recent_events=recent_events,
            task_assessments=task_assessments,
        )

    def read_task_work_profiles(
        self,
        *,
        agent_runtime: dict | None = None,
    ) -> tuple[dict, ...]:
        """Return derived work profiles for the current canonical tasks."""
        return self._read_models.read_task_work_profiles(agent_runtime=agent_runtime)

    def record_runtime_event(self, event: dict) -> None:
        """Persist one runtime event and project any decision-critical signal into canonical state."""
        if not isinstance(event, dict):
            raise StateStoreError("runtime event must be an object")
        with self.runtime_lock():
            state = self.load_state()
            normalized = self._normalize_runtime_event_input(event)
            expected_revision = state["revision"]
            if self._apply_runtime_signal(state, normalized):
                self._bump_revision(state)
            self._record_trace_only_events(state, [normalized], expected_revision=expected_revision)

    def has_active_session(self) -> bool:
        """Return whether a local session file is currently present."""
        return self.session_path.exists()

    def is_runtime_path(self, path: str | Path) -> bool:
        """Return whether a path falls under the runtime-owned directory."""
        candidate = Path(path)
        if not candidate.is_absolute():
            candidate = self.root / candidate

        resolved_path = candidate.resolve()
        try:
            resolved_path.relative_to(self.cerebro_dir)
        except ValueError:
            return False
        return True

    def save_state(self, state: dict, expected_revision: int | None = None) -> None:
        """Validate and atomically persist the state."""
        with self.runtime_lock():
            state = canonicalize_state_data(state)
            if not isinstance(state, dict):
                raise StateStoreError("state must be a JSON object")
            errors = validate_state_data(state)
            if errors:
                raise StateValidationError(errors)

            if self.state_path.exists():
                current_state = self.load_state()
                if state["revision"] < current_state["revision"]:
                    raise StateStoreError("state revision must not go backwards")
                if expected_revision is not None and current_state["revision"] != expected_revision:
                    raise StateStoreError("state revision changed during operation")

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

    def register_sources(self, paths: list[str], *, expected_session_token: str | None = None) -> dict:
        """Replace the full sources list with a new validated set."""
        with self.runtime_lock():
            state = self.load_state()
            self._assert_active_session_token(state, expected_session_token)
            sources = self.prepare_sources(paths)
            self._assert_sources_match_prepared(sources)

            def persist() -> dict:
                state["sources"] = sources
                self._bump_revision(state)
                self._clear_active_session_registry(state)
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
                self.save_state(state, expected_revision=state["revision"] - 1)
                return state

            updated, _ = self._run_after_temporary_session_close(persist)
            return updated

    def update_checkpoint(
        self,
        data: dict,
        validated_revision: int | None = None,
        *,
        close_session_on_success: bool = False,
        expected_session_id: str | None = None,
        expected_session_token: str | None = None,
    ) -> dict:
        """Replace the checkpoint block with a short explicit checkpoint."""
        with self.runtime_lock():
            checkpoint = self._build_checkpoint_update(data)
            state = self.load_state()
            candidate = dict(state)
            candidate["checkpoint"] = checkpoint
            checkpoint_errors = validate_state_data(candidate)
            if checkpoint_errors:
                raise StateValidationError(checkpoint_errors)

            if validated_revision is None:
                validation = self.validate_state()
                if not validation["ok"]:
                    raise StateValidationError(validation["errors"])
                validated_revision = validation["revision"]

            state = self.load_state()
            self._assert_state_matches_validated_revision(state, validated_revision)
            runtime_errors = self._runtime_validation_errors(state)
            if runtime_errors:
                raise StateValidationError(runtime_errors)
            active_session = self.read_owned_active_session(state, expected_session_token)

            def persist() -> dict:
                previous_sources = list(state["sources"])
                state["checkpoint"] = checkpoint
                self._bump_revision(state)
                if state["sources"] != previous_sources:
                    raise StateStoreError("checkpoint update must not change sources")
                if close_session_on_success:
                    self._clear_active_session_registry(state)
                    self.save_state(state, expected_revision=validated_revision)
                else:
                    self._save_state_with_refreshed_session(
                        state,
                        expected_revision=validated_revision,
                        active_session=active_session,
                    )
                return state

            if close_session_on_success:
                self._assert_expected_session_id(state, expected_session_id)
                updated, _ = self._run_after_temporary_session_close(persist)
                return updated

            return persist()

    def open_session(self, actor: str, validated_revision: int | None = None) -> dict:
        """Create one local session file for the current operator."""
        with self.runtime_lock():
            if not isinstance(actor, str) or not actor.strip():
                raise StateStoreError("actor must be a non-empty string")

            if validated_revision is None:
                validation = self.validate_state()
                if not validation["ok"]:
                    raise StateValidationError(validation["errors"])
                validated_revision = validation["revision"]

            state = self.load_state()
            self._assert_state_matches_validated_revision(state, validated_revision)
            runtime_errors = self._runtime_validation_errors(state)
            if runtime_errors:
                raise StateValidationError(runtime_errors)

            existing_session, session_errors = self._read_validated_session_for_state(state)
            if session_errors:
                raise StateValidationError(session_errors)
            if existing_session is not None:
                raise StateValidationError(
                    [
                        error(
                            "session_open_conflict",
                            "a local continuity session is already active; run `cerebro session-discard` before opening a new one",
                        )
                    ]
                )

            session_token = secrets.token_urlsafe(32)
            owner_claim_id = f"claim-{uuid4().hex}"
            owner_binding_sha256 = self._hash_session_owner_binding(self._current_session_owner_binding())
            live_proof_id = f"proof-{uuid4().hex}"
            session_live_proof = secrets.token_urlsafe(32)
            session = {
                "session_id": f"session-{uuid4().hex}",
                "opened_at": self._timestamp_now(),
                "actor": actor.strip(),
                "based_on_revision": state["revision"],
                "owner_claim_id": owner_claim_id,
            }
            claim_data = {
                "claim_id": owner_claim_id,
                "session_id": session["session_id"],
                "root_sha256": self._hash_root_identity(),
                "session_token_sha256": self._hash_session_token(session_token),
                "live_proof_id": live_proof_id,
                "session_live_proof_sha256": self._hash_session_live_proof(session_live_proof),
                "owner_binding_sha256": owner_binding_sha256,
            }
            live_proof_data = {
                "proof_id": live_proof_id,
                "session_id": session["session_id"],
                "root_sha256": self._hash_root_identity(),
                "session_live_proof": session_live_proof,
            }
            errors = validate_session_data(session)
            if errors:
                raise StateValidationError(errors)

            pre_open_state = deepcopy(state)
            self.cerebro_dir.mkdir(parents=True, exist_ok=True)
            registry_persisted = False
            cleaned_registry_residue = False
            try:
                self._write_session_claim(claim_data)
                self._write_session_live_proof(live_proof_data)
                self._set_active_session_registry(
                    state,
                    session_id=session["session_id"],
                    claim_id=owner_claim_id,
                )
                self.save_state(state, expected_revision=validated_revision)
                registry_persisted = True
                self._write_json_atomic(self.session_path, session)
            except Exception as open_session_exc:
                if registry_persisted:
                    try:
                        self.save_state(pre_open_state, expected_revision=pre_open_state["revision"])
                    except Exception as exc:
                        try:
                            cleaned_registry_residue = self._recover_failed_open_session_registry_residue(
                                session_id=session["session_id"],
                                claim_id=owner_claim_id,
                            )
                        except Exception as cleanup_exc:
                            raise StateStoreError("failed to restore state after session file write failure") from cleanup_exc
                        if not cleaned_registry_residue:
                            raise StateStoreError("failed to restore state after session file write failure") from exc
                if not cleaned_registry_residue:
                    self._remove_session_live_proof(live_proof_id)
                    self._remove_session_claim(owner_claim_id)
                raise open_session_exc
            return {**session, "session_token": session_token}

    def close_session(self) -> bool:
        """Remove the local session file when present, failing closed if the session cannot be read safely."""
        with self.runtime_lock():
            if self.session_path.exists():
                state = self.load_state()
                previous_state = deepcopy(state)
                session_data = None
                session_errors: list[dict] = []
                if self.session_path.is_file():
                    try:
                        session_data, session_errors = self._read_session_file()
                    except Exception as exc:
                        self._record_trace_only_events(
                            state,
                            [
                                {
                                    "event_type": "session_close_failed",
                                    "phase": "analysis",
                                    "step": "session_close_failed",
                                    "payload": {
                                        "reason_code": "session_unreadable",
                                        "session_path": str(self.session_path),
                                    },
                                }
                            ],
                            expected_revision=state["revision"],
                        )
                        raise StateStoreError(
                            f"failed to read session file before closing session: {self.session_path} (session_unreadable)"
                        ) from exc
                    if session_errors:
                        reason_code = str(session_errors[0].get("code", "session_unreadable"))
                        self._record_trace_only_events(
                            state,
                            [
                                {
                                    "event_type": "session_close_failed",
                                    "phase": "analysis",
                                    "step": "session_close_failed",
                                    "payload": {
                                        "reason_code": reason_code,
                                        "session_path": str(self.session_path),
                                    },
                                }
                            ],
                            expected_revision=state["revision"],
                        )
                        raise StateStoreError(
                            f"failed to read session file before closing session: {self.session_path} ({reason_code})"
                        )
                claim_snapshot = None
                live_proof_snapshot = None
                if session_data is not None:
                    claim_snapshot = self._capture_session_claim_snapshot(
                        session_data.get("owner_claim_id", ""),
                        label="external session claim",
                    )
                    live_proof_id = self._active_session_live_proof_id(session_data)
                    if live_proof_id is not None:
                        live_proof_snapshot = self._capture_session_live_proof_snapshot(
                            live_proof_id,
                            label="external session live proof",
                        )
                self._clear_active_session_registry(state)
                self.save_state(state, expected_revision=state["revision"])
                if session_data is not None:
                    if live_proof_snapshot is not None:
                        self._remove_session_live_proof(live_proof_snapshot["proof_id"])
                    self._remove_session_claim(session_data.get("owner_claim_id"))
                try:
                    self.session_path.unlink()
                except Exception as exc:
                    self.save_state(previous_state, expected_revision=previous_state["revision"])
                    if claim_snapshot is not None:
                        self._restore_session_claim_snapshot(claim_snapshot)
                    if live_proof_snapshot is not None:
                        self._restore_session_live_proof_snapshot(live_proof_snapshot)
                    raise StateStoreError(f"failed to remove session file: {self.session_path}") from exc
                return True
            return False

    def discard_session(self, *, expected_session_token: str | None = None) -> dict:
        """Explicitly remove the local session without claiming uninterrupted continuity."""
        with self.runtime_lock():
            session_exists = self.has_active_session()
            validation = self.validate_state()
            session_errors = [item for item in validation["errors"] if str(item.get("code", "")).startswith("session_")]
            non_session_errors = [
                item for item in validation["errors"] if not str(item.get("code", "")).startswith("session_")
            ]
            if not session_exists:
                if (
                    not validation["ok"]
                    and not non_session_errors
                    and self._session_errors_allow_registry_only_discard(session_errors)
                ):
                    state = self.load_state()
                    active_session_id, active_claim_id = self._active_session_registry(state)
                    if active_session_id and active_claim_id:
                        self._discard_registry_only_session_residue(state, claim_id=active_claim_id)
                        after = self.validate_state()
                        if not after["ok"]:
                            return {
                                "ok": False,
                                "status": "incomplete",
                                "errors": after["errors"],
                            }

                        state = self.load_state()
                        self._record_trace_only_events(
                            state,
                            [
                                {
                                    "event_type": "session_discarded",
                                    "phase": "analysis",
                                    "step": "session_discarded",
                                    "payload": {
                                        "mode": "stale_session_recovery",
                                        "had_session_error": True,
                                    },
                                }
                            ],
                            expected_revision=state["revision"],
                        )
                        return {
                            "ok": True,
                            "status": "discarded",
                            "revision": after["revision"],
                            "recovered_stale_session": True,
                        }
                if validation["ok"]:
                    return {
                        "ok": True,
                        "status": "absent",
                        "revision": validation["revision"],
                    }
                return {
                    "ok": False,
                    "status": "blocked",
                    "reason": "session_absent",
                    "errors": validation["errors"],
                }
            if not validation["ok"] and non_session_errors:
                return {
                    "ok": False,
                    "status": "blocked",
                    "reason": "non_session_errors",
                    "errors": validation["errors"],
                }

            session_data = validation.get("session")
            if session_data is None:
                session_data, session_read_errors = self._read_session_file()
                if session_read_errors:
                    return {
                        "ok": False,
                        "status": "blocked",
                        "reason": "session_validation",
                        "errors": session_read_errors,
                    }

            if session_data is not None:
                if not self._session_errors_allow_unowned_discard(session_errors):
                    try:
                        self._assert_expected_session_token_for_session(session_data, expected_session_token)
                        self._assert_current_session_owner_binding_for_session(session_data)
                    except StateValidationError as exc:
                        return {
                            "ok": False,
                            "status": "blocked",
                            "reason": "session_token",
                            "errors": exc.errors,
                        }

            closed = self.close_session()
            if not closed:
                return {
                    "ok": False,
                    "status": "race",
                    "errors": [
                        error(
                            "session_discard_race",
                            "local session file disappeared before discard completed",
                        )
                    ],
                }

            after = self.validate_state()
            if not after["ok"]:
                return {
                    "ok": False,
                    "status": "incomplete",
                    "errors": after["errors"],
                }

            state = self.load_state()
            self._record_trace_only_events(
                state,
                [
                    {
                        "event_type": "session_discarded",
                        "phase": "analysis",
                        "step": "session_discarded",
                        "payload": {
                            "mode": "stale_session_recovery" if session_errors else "explicit_close",
                            "had_session_error": bool(session_errors),
                        },
                    }
                ],
                expected_revision=state["revision"],
            )
            return {
                "ok": True,
                "status": "discarded",
                "revision": after["revision"],
                "recovered_stale_session": bool(session_errors),
            }

    def _discard_registry_only_session_residue(self, state: dict, *, claim_id: str) -> None:
        """Clear one crash residue where the canonical registry survived but the local session file did not."""
        previous_state = deepcopy(state)
        claim_snapshot = self._capture_session_claim_snapshot(claim_id, label="external session claim")
        claim_data, claim_errors = self._read_session_claim_file(claim_id)
        live_proof_snapshot = None
        live_proof_id = None
        if not claim_errors and claim_data is not None:
            live_proof_candidate = claim_data.get("live_proof_id")
            if isinstance(live_proof_candidate, str) and live_proof_candidate:
                live_proof_id = live_proof_candidate
                live_proof_snapshot = self._capture_session_live_proof_snapshot(
                    live_proof_id,
                    label="external session live proof",
                )

        self._clear_active_session_registry(state)
        self.save_state(state, expected_revision=state["revision"])
        try:
            if live_proof_id is not None:
                self._remove_session_live_proof(live_proof_id)
            self._remove_session_claim(claim_id)
        except Exception as exc:
            try:
                self.save_state(previous_state, expected_revision=previous_state["revision"])
            except Exception as restore_exc:
                raise StateStoreError("failed to restore state after registry-only session discard failure") from restore_exc
            if claim_snapshot is not None:
                self._restore_session_claim_snapshot(claim_snapshot)
            if live_proof_snapshot is not None:
                self._restore_session_live_proof_snapshot(live_proof_snapshot)
            raise StateStoreError("failed to discard registry-only session residue") from exc

    def _recover_failed_open_session_registry_residue(self, *, session_id: str, claim_id: str) -> bool:
        """Clear one narrow residue left when session.local.json fails and the registry rollback also fails."""
        state = self.load_state()
        active_session_id, active_claim_id = self._active_session_registry(state)
        if active_session_id != session_id or active_claim_id != claim_id:
            return False
        self._discard_registry_only_session_residue(state, claim_id=claim_id)
        return True

    def update_agent_plan(
        self,
        data: dict,
        validated_revision: int | None = None,
        *,
        expected_session_token: str | None = None,
    ) -> dict:
        """Persist the alpha-runtime plan, command registry, and execution policy."""
        with self.runtime_lock():
            plan_block, command_registry, verification_block, execution_policy = self._build_agent_plan_update(data)
            if validated_revision is None:
                validation = self.validate_state()
                if not validation["ok"]:
                    raise StateValidationError(validation["errors"])
                validated_revision = validation["revision"]

            state = self.load_state()
            self._assert_state_matches_validated_revision(state, validated_revision)
            runtime_errors = self._runtime_validation_errors(state)
            if runtime_errors:
                raise StateValidationError(runtime_errors)
            active_session = self.read_owned_active_session(state, expected_session_token)

            previous_task_id = state["agent_runtime"]["plan"].get("current_task_id", "")
            state["agent_runtime"]["plan"] = plan_block
            state["agent_runtime"]["command_registry"] = command_registry
            state["agent_runtime"]["verification"] = verification_block
            state["agent_runtime"]["execution_policy"] = execution_policy
            state["agent_runtime"]["approvals"]["items"] = []
            state["agent_runtime"]["batch_registry"]["used_ids"] = []
            selection = self._refresh_agent_runtime_progress(state["agent_runtime"])
            self._update_agent_audit(state, "plan_updated", "")
            self._reset_trace_thread(state["agent_runtime"]["audit"], prefix="plan")
            event_specs = [
                {
                    "event_type": "plan_updated",
                    "phase": "plan",
                    "step": "plan_updated",
                    "payload": {
                        "plan_goal": plan_block["goal"],
                        "tasks": [item["id"] for item in plan_block["tasks"]],
                    },
                }
            ]
            selection_event = self._build_task_selection_event_spec(
                previous_task_id,
                selection,
                parent_event_index=len(event_specs) - 1 if event_specs else None,
            )
            if selection_event is not None:
                event_specs.append(selection_event)
            self._bump_revision(state)
            prepared_events = self._prepare_trace_events(state, event_specs)
            self._save_state_with_refreshed_session(
                state,
                expected_revision=validated_revision,
                active_session=active_session,
            )
            self._commit_trace_events(state, prepared_events)
            return state

    def record_agent_actions(
        self,
        action_records: list[dict],
        validated_revision: int | None = None,
        *,
        expected_session_token: str | None = None,
    ) -> dict:
        """Append one or more executed action records to the canonical alpha-runtime state."""
        with self.runtime_lock():
            if not isinstance(action_records, list) or not action_records:
                raise StateStoreError("action_records must contain at least one action record")
            if validated_revision is None:
                validation = self.validate_state()
                if not validation["ok"]:
                    raise StateValidationError(validation["errors"])
                validated_revision = validation["revision"]

            state = self.load_state()
            self._assert_state_matches_validated_revision(state, validated_revision)
            runtime_errors = self._runtime_validation_errors(state)
            if runtime_errors:
                raise StateValidationError(runtime_errors)
            active_session = self.read_owned_active_session(state, expected_session_token)

            previous_task_id = state["agent_runtime"]["plan"].get("current_task_id", "")
            actions = list(state["agent_runtime"]["actions"])
            event_specs: list[dict] = []
            for action_record in action_records:
                actions = [item for item in actions if item["id"] != action_record["id"]]
                actions.append(action_record)
                if len(actions) > MAX_ACTION_HISTORY:
                    actions = actions[-MAX_ACTION_HISTORY:]
                state["agent_runtime"]["actions"] = actions
                self._sync_task_with_action(state["agent_runtime"]["plan"], action_record)
                self._sync_pending_action_ids(state["agent_runtime"]["verification"], action_record)
                self._update_agent_audit(state, "action_recorded", action_record["id"])
                if action_record["status"] == "applied" and action_record["rollback_ref"]:
                    self._append_rollback_point(state, action_record)
                event_specs.append(
                    {
                        "event_type": "action_recorded",
                        "phase": "apply",
                        "step": "action_recorded",
                        "payload": {
                            "action_id": action_record["id"],
                            "kind": action_record["kind"],
                            "status": action_record["status"],
                            "target": action_record["target"],
                            "task_id": action_record["task_id"],
                        },
                    }
                )

            self._record_used_batch_ids(state["agent_runtime"], action_records)
            self._prune_retained_action_refs(state["agent_runtime"])
            recent_events = self._safe_recent_events(limit=20)
            selection = self._refresh_agent_runtime_progress(
                state["agent_runtime"],
                recent_events=recent_events,
            )
            selection_event = self._build_task_selection_event_spec(previous_task_id, selection, parent_event_index=0)
            if selection_event is not None:
                event_specs.append(selection_event)
            self._bump_revision(state)
            prepared_events = self._prepare_trace_events(state, event_specs)
            self._save_state_with_refreshed_session(
                state,
                expected_revision=validated_revision,
                active_session=active_session,
            )
            self._commit_trace_events(state, prepared_events)
            return state

    def record_agent_action(
        self,
        action_record: dict,
        validated_revision: int | None = None,
        *,
        expected_session_token: str | None = None,
    ) -> dict:
        """Append one executed action record to the canonical alpha-runtime state."""
        return self.record_agent_actions(
            [action_record],
            validated_revision=validated_revision,
            expected_session_token=expected_session_token,
        )

    def update_agent_approval(
        self,
        approval_record: dict,
        validated_revision: int | None = None,
        *,
        expected_session_token: str | None = None,
    ) -> dict:
        """Persist one approval request or resolution in canonical runtime state."""
        with self.runtime_lock():
            if validated_revision is None:
                validation = self.validate_state()
                if not validation["ok"]:
                    raise StateValidationError(validation["errors"])
                validated_revision = validation["revision"]

            state = self.load_state()
            self._assert_state_matches_validated_revision(state, validated_revision)
            runtime_errors = self._runtime_validation_errors(state)
            if runtime_errors:
                raise StateValidationError(runtime_errors)
            active_session = self.read_owned_active_session(state, expected_session_token)

            approvals = list(state["agent_runtime"]["approvals"]["items"])
            approvals = [item for item in approvals if item["id"] != approval_record["id"]]
            approvals.append(approval_record)
            if len(approvals) > MAX_APPROVAL_ITEMS:
                approvals = approvals[-MAX_APPROVAL_ITEMS:]
            state["agent_runtime"]["approvals"]["items"] = approvals
            state["agent_runtime"]["memory"]["notes"] = sync_approval_memory_notes(
                state["agent_runtime"]["memory"]["notes"],
                approval_record,
            )
            self._update_agent_audit(state, "approval_updated", "")
            previous_task_id = state["agent_runtime"]["plan"].get("current_task_id", "")
            recent_events = self._safe_recent_events(limit=20)
            selection = self._refresh_agent_runtime_progress(
                state["agent_runtime"],
                recent_events=recent_events,
            )
            event_specs = [
                {
                    "event_type": "approval_updated",
                    "phase": "approve",
                    "step": "approval_updated",
                    "payload": {
                        "approval_id": approval_record["id"],
                        "status": approval_record["status"],
                        "action_kind": approval_record["action_kind"],
                        "task_id": approval_record["task_id"],
                        "target": approval_record["target"],
                    },
                }
            ]
            selection_event = self._build_task_selection_event_spec(previous_task_id, selection, parent_event_index=0)
            if selection_event is not None:
                event_specs.append(selection_event)
            self._bump_revision(state)
            prepared_events = self._prepare_trace_events(state, event_specs)
            self._save_state_with_refreshed_session(
                state,
                expected_revision=validated_revision,
                active_session=active_session,
            )
            self._commit_trace_events(state, prepared_events)
            return state

    def update_agent_verification(
        self,
        verification_record: dict,
        validated_revision: int | None = None,
        *,
        expected_session_token: str | None = None,
    ) -> dict:
        """Persist the latest verification run for the alpha runtime."""
        with self.runtime_lock():
            if validated_revision is None:
                validation = self.validate_state()
                if not validation["ok"]:
                    raise StateValidationError(validation["errors"])
                validated_revision = validation["revision"]

            state = self.load_state()
            self._assert_state_matches_validated_revision(state, validated_revision)
            runtime_errors = self._runtime_validation_errors(state)
            if runtime_errors:
                raise StateValidationError(runtime_errors)
            active_session = self.read_owned_active_session(state, expected_session_token)

            previous_plan = deepcopy(state["agent_runtime"]["plan"])
            verification_record = self._merge_verification_result(
                state["agent_runtime"]["verification"],
                verification_record,
                state["agent_runtime"]["plan"],
                state["agent_runtime"]["actions"],
            )
            state["agent_runtime"]["verification"] = verification_record
            state["agent_runtime"]["memory"]["notes"] = sync_verification_memory_notes(
                state["agent_runtime"]["memory"]["notes"],
                verification_record,
            )
            success_records = self._derive_success_records(
                previous_plan,
                state["agent_runtime"]["plan"],
                verification_record,
                state["agent_runtime"]["actions"],
            )
            state["agent_runtime"]["memory"]["notes"] = sync_success_memory_notes(
                state["agent_runtime"]["memory"]["notes"],
                success_records,
            )
            self._update_agent_audit(state, "verification_completed", "")
            previous_task_id = state["agent_runtime"]["plan"].get("current_task_id", "")
            recent_events = self._safe_recent_events(limit=20)
            selection = self._refresh_agent_runtime_progress(
                state["agent_runtime"],
                recent_events=recent_events,
            )
            event_specs = [
                {
                    "event_type": "verification_completed",
                    "phase": "verify",
                    "step": "verification_completed",
                    "payload": {
                        "status": verification_record["status"],
                        "checks": [item["command_id"] for item in iter_command_checks(verification_record)],
                    },
                }
            ]
            for success_record in success_records:
                event_specs.append(
                    {
                        "event_type": "decision_success",
                        "phase": "verify",
                        "step": "decision_success",
                        "parent_event_index": 0,
                        "payload": {
                            "task_id": success_record["task_id"],
                            "context": success_record["context"],
                            "action_kinds": success_record["action_kinds"],
                            "result": success_record["result"],
                            "cost": success_record["cost"],
                            "reason": success_record["reason"],
                            "pattern_signature": success_record["pattern_signature"],
                        },
                    }
                )
            selection_event = self._build_task_selection_event_spec(previous_task_id, selection, parent_event_index=0)
            if selection_event is not None:
                event_specs.append(selection_event)
            self._bump_revision(state)
            prepared_events = self._prepare_trace_events(state, event_specs)
            self._save_state_with_refreshed_session(
                state,
                expected_revision=validated_revision,
                active_session=active_session,
            )
            self._commit_trace_events(state, prepared_events)
            return state

    def validate_state(self) -> dict:
        """Validate the persisted state file without raising on user-data failures."""
        with self.runtime_lock():
            result, _ = self.validate_state_locked()
            return result

    def validate_state_locked(self) -> tuple[dict, dict | None]:
        """Return the validation result plus the canonical state while the runtime lock is held."""
        if not self.state_path.exists():
            return {
                "ok": False,
                "errors": [error("state_missing", f"state file not found: {self.state_path}")],
            }, None

        try:
            with self.state_path.open(encoding="utf-8") as handle:
                data = json.load(handle)
        except json.JSONDecodeError as exc:
            return {
                "ok": False,
                "errors": [error("state_invalid_json", f"invalid JSON in state file: {exc.msg}")],
            }, None
        except OSError:
            return {
                "ok": False,
                "errors": [error("state_unreadable", f"failed to read state file: {self.state_path}")],
            }, None

        data = canonicalize_state_data(data)
        if not isinstance(data, dict):
            return {
                "ok": False,
                "errors": [error("state_invalid_schema", "state file does not match the required schema")],
            }, None
        errors = validate_state_data(data)
        if errors:
            return {
                "ok": False,
                "errors": [error("state_invalid_schema", "state file does not match the required schema"), *errors],
            }, None

        for _ in range(VALIDATION_RETRY_LIMIT):
            revision_before = data["revision"]
            validation_errors, session_data = self._runtime_validation_context(data)
            result = {"ok": not validation_errors, "errors": validation_errors}
            data["last_validation"] = {
                "validated_at": self._timestamp_now(),
                "result": "ok" if result["ok"] else "fail",
                "details": validation_errors,
            }

            try:
                self.save_state(data, expected_revision=revision_before)
            except StateStoreError as exc:
                if str(exc) != "state revision changed during operation":
                    raise
                data = self.load_state()
                continue

            if data["revision"] != revision_before:
                raise StateStoreError("validate_state must not change revision")

            result["revision"] = revision_before
            result["snapshot"] = self._to_snapshot(data)
            if session_data is not None:
                result["session"] = deepcopy(session_data)
            return result, deepcopy(data)

        return {
            "ok": False,
            "errors": [
                error(
                    "state_changed_during_validation",
                    "state changed during validation; rerun the operation",
                )
            ],
        }, None

    def describe_retention_policy(self) -> dict:
        """Return the current governed retention policy for runtime artifacts and logs."""
        return {
            "event_log": {
                "retain_all_consolidations": True,
                "retain_latest_non_consolidation_events": RETENTION_NON_CONSOLIDATION_EVENT_LIMIT,
            },
            "artifacts": {
                "retain_live_refs": True,
                "retain_latest_unreferenced_verification_groups": RETENTION_VERIFICATION_GROUP_LIMIT,
                "retain_latest_unreferenced_action_groups": RETENTION_ACTION_GROUP_LIMIT,
                "unknown_surfaces": "blocked",
            },
            "mode": "manual_validate_gated",
            "archive_root": "trash/retention/",
        }

    def inspect_retention(self, *, expected_revision: int | None = None) -> dict:
        """Return one dry-run retention report without mutating runtime files."""
        with self.runtime_lock():
            state = self.load_state()
            if expected_revision is not None and state["revision"] != expected_revision:
                raise StateStoreError("state revision changed during operation")
            return self._build_retention_report(state)

    def apply_retention(self, *, expected_revision: int | None = None) -> dict:
        """Apply the governed retention policy and archive discarded runtime data."""
        with self.runtime_lock():
            state = self.load_state()
            if expected_revision is not None and state["revision"] != expected_revision:
                raise StateStoreError("state revision changed during operation")

            pending = self._load_pending_retention_archive()
            if pending is not None:
                archive_root, pending_manifest = pending
                return self._finalize_pending_retention_archive(state, archive_root, pending_manifest)

            report = self._build_retention_report(state)
            if not report["has_candidates"]:
                return {**report, "applied": False, "archive_root_ref": "", "retention_event_id": ""}

            archive_id = f"retention-{self._timestamp_now().replace(':', '-').replace('+00:00', 'Z')}"
            archive_root = self.trash_dir / "retention" / archive_id
            archive_root.mkdir(parents=True, exist_ok=False)
            archive_root_ref = archive_root.relative_to(self.cerebro_dir).as_posix()
            pending_path = archive_root / "manifest.pending.json"
            pending_manifest = self._build_retention_pending_manifest(
                archive_root_ref=archive_root_ref,
                created_at=self._timestamp_now(),
                policy=report["policy"],
                archived_event_lines=report["events"]["archived_line_count"],
                archived_event_bytes=report["events"]["archived_bytes"],
                archived_group_paths=report["artifacts"]["archive_group_paths"],
                archived_group_count=report["artifacts"]["archive_group_count"],
                archived_file_count=report["artifacts"]["archive_file_count"],
                archived_artifact_bytes=report["artifacts"]["archive_bytes"],
                blocked_unknown_group_count=report["artifacts"]["blocked_unknown_group_count"],
            )
            self._write_json_atomic(pending_path, pending_manifest)

            moved_groups: list[str] = []
            if report["artifacts"]["archive_group_paths"]:
                artifacts_archive_root = archive_root / "artifacts"
                for relative_group in report["artifacts"]["archive_group_paths"]:
                    source = self.artifacts_dir / Path(relative_group)
                    if not source.exists():
                        continue
                    destination = artifacts_archive_root / Path(relative_group)
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(source), str(destination))
                    moved_groups.append(relative_group)
                    self._remove_empty_artifact_parents(source.parent)

            archived_event_lines = report["events"]["archived_line_count"]
            archived_event_bytes = report["events"]["archived_bytes"]
            if report["events"]["archived_line_count"]:
                logs_archive_root = archive_root / "logs"
                logs_archive_root.mkdir(parents=True, exist_ok=True)
                self._write_bytes_atomic(
                    logs_archive_root / "events.archived.jsonl",
                    b"".join(line.rstrip(b"\r\n") + b"\n" for line in report["events"]["_archived_lines"]),
                )
                self._write_bytes_atomic(
                    self.events_path,
                    b"".join(line.rstrip(b"\r\n") + b"\n" for line in report["events"]["_retained_lines"]),
                )

            manifest = self._build_retention_archive_manifest(
                created_at=pending_manifest["created_at"],
                policy=report["policy"],
                archived_event_lines=archived_event_lines,
                archived_event_bytes=archived_event_bytes,
                archived_group_paths=moved_groups,
                archived_file_count=report["artifacts"]["archive_file_count"],
                archived_artifact_bytes=report["artifacts"]["archive_bytes"],
            )

            event_payload = {
                "archive_root_ref": archive_root_ref,
                "archived_event_lines": archived_event_lines,
                "archived_event_bytes": archived_event_bytes,
                "archived_artifact_groups": len(moved_groups),
                "archived_artifact_files": report["artifacts"]["archive_file_count"],
                "archived_artifact_bytes": report["artifacts"]["archive_bytes"],
                "blocked_unknown_artifact_surfaces": report["artifacts"]["blocked_unknown_group_count"],
            }
            prepared = self._prepare_trace_events(
                state,
                [
                    {
                        "event_type": "retention_applied",
                        "phase": "record",
                        "step": "retention_applied",
                        "payload": event_payload,
                    }
                ],
            )
            pending_manifest = self._build_retention_pending_manifest(
                archive_root_ref=archive_root_ref,
                created_at=manifest["created_at"],
                policy=report["policy"],
                archived_event_lines=archived_event_lines,
                archived_event_bytes=archived_event_bytes,
                archived_group_paths=moved_groups,
                archived_group_count=len(moved_groups),
                archived_file_count=report["artifacts"]["archive_file_count"],
                archived_artifact_bytes=report["artifacts"]["archive_bytes"],
                blocked_unknown_group_count=report["artifacts"]["blocked_unknown_group_count"],
                retention_event=prepared[0],
            )
            self._write_json_atomic(pending_path, pending_manifest)
            self.save_state(
                state,
                expected_revision=state["revision"] if expected_revision is None else expected_revision,
            )
            self._commit_trace_events(state, prepared)
            retention_event_id = prepared[0]["event_id"]
            trace_error = state["agent_runtime"]["audit"].get("last_trace_error", "")
            if trace_error.startswith(f"{retention_event_id}:"):
                raise StateStoreError(f"failed to append retention_applied trace event: {trace_error}")
            self._write_json_atomic(
                archive_root / "manifest.json",
                {
                    **manifest,
                    "retention_event_id": retention_event_id,
                },
            )
            try:
                pending_path.unlink()
            except FileNotFoundError:
                pass
            except OSError as exc:
                raise StateStoreError(f"failed to remove pending retention manifest: {pending_path}") from exc

            return self._build_retention_apply_result(
                policy=report["policy"],
                archived_event_lines=archived_event_lines,
                archived_event_bytes=archived_event_bytes,
                archived_group_count=len(moved_groups),
                archived_file_count=report["artifacts"]["archive_file_count"],
                archived_artifact_bytes=report["artifacts"]["archive_bytes"],
                blocked_unknown_group_count=report["artifacts"]["blocked_unknown_group_count"],
                archive_root_ref=archive_root_ref,
                retention_event_id=retention_event_id,
            )

    def _load_pending_retention_archive(self) -> tuple[Path, dict] | None:
        """Return one pending retention archive journal if the previous apply did not finish."""
        retention_root = self.trash_dir / "retention"
        if not retention_root.exists():
            return None
        pending_paths = sorted(retention_root.glob("retention-*/manifest.pending.json"))
        if not pending_paths:
            return None
        if len(pending_paths) > 1:
            raise StateStoreError("multiple pending retention journals require manual inspection")
        pending_path = pending_paths[0]
        try:
            pending_manifest = json.loads(pending_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise StateStoreError(f"failed to read pending retention manifest: {pending_path}") from exc
        if not isinstance(pending_manifest, dict):
            raise StateStoreError(f"pending retention manifest must be an object: {pending_path}")
        return pending_path.parent, pending_manifest

    def _build_retention_pending_manifest(
        self,
        *,
        archive_root_ref: str,
        created_at: str,
        policy: dict,
        archived_event_lines: int,
        archived_event_bytes: int,
        archived_group_paths: list[str] | tuple[str, ...],
        archived_group_count: int,
        archived_file_count: int,
        archived_artifact_bytes: int,
        blocked_unknown_group_count: int,
        retention_event: dict | None = None,
    ) -> dict:
        """Build the local-only retention journal for one in-flight archive."""
        pending_manifest = {
            "archive_root_ref": archive_root_ref,
            "created_at": created_at,
            "policy": deepcopy(policy),
            "events": {
                "archived_line_count": archived_event_lines,
                "archived_bytes": archived_event_bytes,
            },
            "artifacts": {
                "archived_group_paths": list(archived_group_paths),
                "archived_group_count": archived_group_count,
                "archived_file_count": archived_file_count,
                "archived_bytes": archived_artifact_bytes,
                "blocked_unknown_group_count": blocked_unknown_group_count,
            },
        }
        if retention_event is not None:
            pending_manifest["retention_event"] = deepcopy(retention_event)
        return pending_manifest

    def _build_retention_archive_manifest(
        self,
        *,
        created_at: str,
        policy: dict,
        archived_event_lines: int,
        archived_event_bytes: int,
        archived_group_paths: list[str] | tuple[str, ...],
        archived_file_count: int,
        archived_artifact_bytes: int,
        retention_event_id: str = "",
    ) -> dict:
        """Build the final retention manifest stored next to archived runtime data."""
        manifest = {
            "created_at": created_at,
            "policy": deepcopy(policy),
            "events": {
                "archived_line_count": archived_event_lines,
                "archived_bytes": archived_event_bytes,
            },
            "artifacts": {
                "archived_group_paths": list(archived_group_paths),
                "archived_group_count": len(archived_group_paths),
                "archived_file_count": archived_file_count,
                "archived_bytes": archived_artifact_bytes,
            },
        }
        if retention_event_id:
            manifest["retention_event_id"] = retention_event_id
        return manifest

    def _build_retention_apply_result(
        self,
        *,
        policy: dict,
        archived_event_lines: int,
        archived_event_bytes: int,
        archived_group_count: int,
        archived_file_count: int,
        archived_artifact_bytes: int,
        blocked_unknown_group_count: int,
        archive_root_ref: str,
        retention_event_id: str,
    ) -> dict:
        """Build the public retention result shape consumed by validate/apply callers."""
        return {
            "policy": deepcopy(policy),
            "events": {
                "archived_line_count": archived_event_lines,
                "archived_bytes": archived_event_bytes,
            },
            "artifacts": {
                "archive_group_count": archived_group_count,
                "archive_file_count": archived_file_count,
                "archive_bytes": archived_artifact_bytes,
                "blocked_unknown_group_count": blocked_unknown_group_count,
            },
            "has_candidates": bool(archived_event_lines or archived_group_count),
            "applied": True,
            "archive_root_ref": archive_root_ref,
            "retention_event_id": retention_event_id,
        }

    def _event_log_contains_retention_event(self, event_id: str) -> bool:
        """Return whether the active event log already contains the finalized retention event."""
        if not isinstance(event_id, str) or not event_id or not self.events_path.exists():
            return False
        try:
            with self.events_path.open("rb") as handle:
                for raw_line in handle:
                    stripped = raw_line.strip()
                    if not stripped:
                        continue
                    try:
                        parsed = json.loads(stripped)
                    except json.JSONDecodeError:
                        continue
                    if (
                        isinstance(parsed, dict)
                        and parsed.get("event_id") == event_id
                        and parsed.get("event_type") == "retention_applied"
                    ):
                        return True
        except OSError as exc:
            raise StateStoreError(f"failed to read event log: {self.events_path}") from exc
        return False

    def _finalize_pending_retention_archive(self, state: dict, archive_root: Path, pending_manifest: dict) -> dict:
        """Finish one already-applied retention archive without recalculating eligibility."""
        archive_root_ref = pending_manifest.get("archive_root_ref", archive_root.relative_to(self.cerebro_dir).as_posix())
        if not isinstance(archive_root_ref, str) or not archive_root_ref:
            raise StateStoreError(f"pending retention manifest is missing archive_root_ref: {archive_root}")
        created_at = pending_manifest.get("created_at", "")
        if not isinstance(created_at, str) or not created_at:
            raise StateStoreError(f"pending retention manifest is missing created_at: {archive_root}")
        policy = pending_manifest.get("policy")
        events = pending_manifest.get("events")
        artifacts = pending_manifest.get("artifacts")
        if not isinstance(policy, dict) or not isinstance(events, dict) or not isinstance(artifacts, dict):
            raise StateStoreError(f"pending retention manifest is incomplete: {archive_root}")
        archived_group_paths = artifacts.get("archived_group_paths", [])
        if not isinstance(archived_group_paths, list) or not all(isinstance(item, str) for item in archived_group_paths):
            raise StateStoreError(f"pending retention manifest archived_group_paths must be a string list: {archive_root}")
        archived_event_lines = events.get("archived_line_count", 0)
        archived_event_bytes = events.get("archived_bytes", 0)
        archived_file_count = artifacts.get("archived_file_count", 0)
        archived_artifact_bytes = artifacts.get("archived_bytes", 0)
        blocked_unknown_group_count = artifacts.get("blocked_unknown_group_count", 0)
        if not all(
            isinstance(value, int) and value >= 0
            for value in (
                archived_event_lines,
                archived_event_bytes,
                archived_file_count,
                archived_artifact_bytes,
                blocked_unknown_group_count,
            )
        ):
            raise StateStoreError(f"pending retention manifest counts must be non-negative integers: {archive_root}")
        retention_event = pending_manifest.get("retention_event")
        if not isinstance(retention_event, dict):
            raise StateStoreError(f"pending retention manifest is missing retention_event: {archive_root}")
        retention_event_id = retention_event.get("event_id", "")
        if not isinstance(retention_event_id, str) or not retention_event_id:
            raise StateStoreError(f"pending retention manifest retention_event is missing event_id: {archive_root}")

        if not self._event_log_contains_retention_event(retention_event_id):
            self._commit_trace_events(state, [retention_event])
            trace_error = state["agent_runtime"]["audit"].get("last_trace_error", "")
            if trace_error.startswith(f"{retention_event_id}:"):
                raise StateStoreError(f"failed to append retention_applied trace event: {trace_error}")

        manifest = self._build_retention_archive_manifest(
            created_at=created_at,
            policy=policy,
            archived_event_lines=archived_event_lines,
            archived_event_bytes=archived_event_bytes,
            archived_group_paths=archived_group_paths,
            archived_file_count=archived_file_count,
            archived_artifact_bytes=archived_artifact_bytes,
            retention_event_id=retention_event_id,
        )
        self._write_json_atomic(archive_root / "manifest.json", manifest)
        pending_path = archive_root / "manifest.pending.json"
        try:
            pending_path.unlink()
        except FileNotFoundError:
            pass
        except OSError as exc:
            raise StateStoreError(f"failed to remove pending retention manifest: {pending_path}") from exc

        return self._build_retention_apply_result(
            policy=policy,
            archived_event_lines=archived_event_lines,
            archived_event_bytes=archived_event_bytes,
            archived_group_count=len(archived_group_paths),
            archived_file_count=archived_file_count,
            archived_artifact_bytes=archived_artifact_bytes,
            blocked_unknown_group_count=blocked_unknown_group_count,
            archive_root_ref=archive_root_ref,
            retention_event_id=retention_event_id,
        )

    def _build_retention_report(self, state: dict) -> dict:
        """Build one dry-run retention report from the current canonical state."""
        event_plan = self._build_event_log_retention_plan()
        artifact_plan = self._build_artifact_retention_plan(state)
        return {
            "policy": self.describe_retention_policy(),
            "events": event_plan,
            "artifacts": artifact_plan,
            "has_candidates": bool(event_plan["archived_line_count"] or artifact_plan["archive_group_count"]),
        }

    def _build_event_log_retention_plan(self) -> dict:
        """Return one retention plan for the append-only runtime log."""
        if not self.events_path.exists():
            return {
                "archived_line_count": 0,
                "archived_bytes": 0,
                "retained_line_count": 0,
                "retained_consolidation_count": 0,
                "retained_non_consolidation_count": 0,
                "_archived_lines": (),
                "_retained_lines": (),
            }

        try:
            with self.events_path.open("rb") as handle:
                raw_lines = [line.rstrip(b"\r\n") for line in handle if line.strip()]
        except OSError as exc:
            raise StateStoreError(f"failed to read event log: {self.events_path}") from exc

        consolidation_indexes: list[int] = []
        protected_non_consolidation_indexes: list[int] = []
        non_consolidation_indexes: list[int] = []
        for index, raw_line in enumerate(raw_lines):
            if self._parse_parallel_approach_consolidation_line(raw_line) is not None:
                consolidation_indexes.append(index)
                continue
            if self._parse_event_log_event_type(raw_line) == "retention_applied":
                protected_non_consolidation_indexes.append(index)
                continue
            non_consolidation_indexes.append(index)

        retained_non_consolidation = set(non_consolidation_indexes[-RETENTION_NON_CONSOLIDATION_EVENT_LIMIT:])
        protected_indexes = set(consolidation_indexes) | set(protected_non_consolidation_indexes)
        archived_lines: list[bytes] = []
        retained_lines: list[bytes] = []
        for index, raw_line in enumerate(raw_lines):
            if index in retained_non_consolidation or index in protected_indexes:
                retained_lines.append(raw_line)
            else:
                archived_lines.append(raw_line)

        return {
            "archived_line_count": len(archived_lines),
            "archived_bytes": sum(len(line) + 1 for line in archived_lines),
            "retained_line_count": len(retained_lines),
            "retained_consolidation_count": len(consolidation_indexes),
            "retained_non_consolidation_count": len(retained_non_consolidation) + len(protected_non_consolidation_indexes),
            "_archived_lines": tuple(archived_lines),
            "_retained_lines": tuple(retained_lines),
        }

    def _build_artifact_retention_plan(self, state: dict) -> dict:
        """Return one retention plan for grouped runtime artifacts."""
        groups: dict[str, dict] = {}
        blocked_unknown_groups: set[str] = set()
        live_groups = self._live_artifact_group_paths(state)
        if self.artifacts_dir.exists():
            for path in self.artifacts_dir.rglob("*"):
                if not path.is_file():
                    continue
                relative_path = path.relative_to(self.artifacts_dir).as_posix()
                group_path = self._artifact_retention_group_path(relative_path)
                if group_path is None:
                    blocked_unknown_groups.add(relative_path)
                    continue
                group = groups.setdefault(
                    group_path,
                    {
                        "path": group_path,
                        "kind": group_path.split("/", 1)[0],
                        "file_count": 0,
                        "bytes": 0,
                        "latest_mtime_ns": 0,
                    },
                )
                stats = path.stat()
                group["file_count"] += 1
                group["bytes"] += stats.st_size
                group["latest_mtime_ns"] = max(group["latest_mtime_ns"], stats.st_mtime_ns)

        verification_candidates = sorted(
            [group for group in groups.values() if group["kind"] == "verification" and group["path"] not in live_groups],
            key=lambda item: item["latest_mtime_ns"],
            reverse=True,
        )
        action_candidates = sorted(
            [group for group in groups.values() if group["kind"] == "actions" and group["path"] not in live_groups],
            key=lambda item: item["latest_mtime_ns"],
            reverse=True,
        )
        archive_groups = verification_candidates[RETENTION_VERIFICATION_GROUP_LIMIT:] + action_candidates[RETENTION_ACTION_GROUP_LIMIT:]
        archive_groups.sort(key=lambda item: (item["kind"], item["path"]))

        return {
            "archive_group_paths": tuple(group["path"] for group in archive_groups),
            "archive_group_count": len(archive_groups),
            "archive_file_count": sum(group["file_count"] for group in archive_groups),
            "archive_bytes": sum(group["bytes"] for group in archive_groups),
            "blocked_unknown_group_count": len(blocked_unknown_groups),
            "blocked_unknown_examples": tuple(sorted(blocked_unknown_groups)[:5]),
            "live_group_count": len(live_groups),
        }

    def _live_artifact_group_paths(self, state: dict) -> set[str]:
        """Return grouped artifact paths that remain operationally live."""
        live_groups: set[str] = set()
        for ref, _label, _sha256 in self._iter_live_runtime_artifact_refs(state):
            try:
                resolved = self._resolve_runtime_artifact_ref(ref)
            except StateStoreError:
                continue
            try:
                relative = resolved.relative_to(self.artifacts_dir).as_posix()
            except ValueError:
                continue
            group_path = self._artifact_retention_group_path(relative)
            if group_path is not None:
                live_groups.add(group_path)
        return live_groups

    def _artifact_retention_group_path(self, relative_artifact_path: str) -> str | None:
        """Map one artifact file path to the retention group that owns it."""
        candidate = Path(relative_artifact_path)
        if len(candidate.parts) < 2:
            return None
        if candidate.parts[0] not in {"verification", "actions"}:
            return None
        return Path(candidate.parts[0], candidate.parts[1]).as_posix()

    def _remove_empty_artifact_parents(self, start: Path) -> None:
        """Collapse empty artifact parents after archiving one group."""
        current = start
        artifacts_root = self.artifacts_dir.resolve()
        while True:
            try:
                current.relative_to(artifacts_root)
            except ValueError:
                return
            if current == artifacts_root:
                return
            try:
                current.rmdir()
            except OSError:
                return
            current = current.parent

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
        if "changed during read" in message:
            return error("source_changed_during_validation", message)
        return error("state_invalid_schema", message)

    def _resolve_runtime_artifact_ref(self, ref: str) -> Path:
        """Resolve one persisted runtime artifact reference inside `.cerebro`."""
        raw = ref.strip()
        if not raw:
            raise StateStoreError("runtime artifact ref must be a non-empty string")

        candidate = Path(raw)
        if candidate.is_absolute():
            raise StateStoreError(f"runtime artifact ref must be relative: {raw}")

        resolved_path = (self.cerebro_dir / candidate).resolve()
        try:
            resolved_path.relative_to(self.cerebro_dir.resolve())
        except ValueError as exc:
            raise StateStoreError(f"runtime artifact ref resolves outside .cerebro: {raw}") from exc
        return resolved_path

    def _action_runtime_artifact_hashes(self, action: dict) -> dict[str, str]:
        """Return expected digest metadata for rollback-critical action artifacts when present."""
        details = action.get("details", {})
        if not isinstance(details, dict):
            return {}

        hashes: dict[str, str] = {}
        rollback_ref = action.get("rollback_ref", "")
        if isinstance(rollback_ref, str) and rollback_ref:
            rollback_sha256 = details.get("rollback_artifact_sha256", "")
            if isinstance(rollback_sha256, str) and rollback_sha256:
                hashes[rollback_ref] = rollback_sha256

        target_preimage_ref = details.get("target_preimage_ref", "")
        target_preimage_sha256 = details.get("target_preimage_sha256", "")
        if (
            isinstance(target_preimage_ref, str)
            and target_preimage_ref
            and isinstance(target_preimage_sha256, str)
            and target_preimage_sha256
        ):
            hashes[target_preimage_ref] = target_preimage_sha256

        trash_ref = details.get("trash_ref", "")
        trash_sha256 = details.get("trash_sha256", "")
        if isinstance(trash_ref, str) and trash_ref and isinstance(trash_sha256, str) and trash_sha256:
            hashes[trash_ref] = trash_sha256

        return hashes

    def _is_valid_runtime_artifact_sha256(self, value: object) -> bool:
        """Return whether one persisted runtime-artifact digest is a lowercase SHA-256 hex string."""
        return isinstance(value, str) and len(value) == 64 and all(char in "0123456789abcdef" for char in value)

    def _iter_live_runtime_artifact_refs(self, state: dict):
        """Yield operational artifact refs that must remain readable before runtime use."""
        agent_runtime = state.get("agent_runtime", {})
        if not isinstance(agent_runtime, dict):
            return

        actions = agent_runtime.get("actions", [])
        if isinstance(actions, list):
            for index, action in enumerate(actions):
                if not isinstance(action, dict) or action.get("status") != "applied":
                    continue
                artifact_hashes = self._action_runtime_artifact_hashes(action)
                rollback_ref = action.get("rollback_ref")
                if isinstance(rollback_ref, str) and rollback_ref:
                    yield rollback_ref, f"agent_runtime.actions[{index}].rollback_ref", artifact_hashes.get(rollback_ref, "")
                artifact_refs = action.get("artifact_refs", [])
                if isinstance(artifact_refs, list):
                    for artifact_index, artifact_ref in enumerate(artifact_refs):
                        if isinstance(artifact_ref, str) and artifact_ref:
                            yield (
                                artifact_ref,
                                f"agent_runtime.actions[{index}].artifact_refs[{artifact_index}]",
                                artifact_hashes.get(artifact_ref, ""),
                            )

        verification = agent_runtime.get("verification", {})
        if not isinstance(verification, dict):
            return
        checks = verification.get("checks", [])
        if not isinstance(checks, list):
            return
        for index, check in enumerate(checks):
            if not isinstance(check, dict):
                continue
            artifact_ref = check.get("artifact_ref")
            if isinstance(artifact_ref, str) and artifact_ref:
                artifact_sha256 = check.get("artifact_sha256", "")
                yield artifact_ref, f"agent_runtime.verification.checks[{index}].artifact_ref", artifact_sha256

    def _runtime_artifact_validation_errors(self, state: dict) -> list[dict]:
        """Return missing or invalid live runtime artifact refs."""
        errors: list[dict] = []
        seen_refs: set[str] = set()
        for ref, label, expected_sha256 in self._iter_live_runtime_artifact_refs(state):
            if ref in seen_refs:
                continue
            seen_refs.add(ref)
            try:
                resolved_path = self._resolve_runtime_artifact_ref(ref)
            except StateStoreError as exc:
                errors.append(error("runtime_artifact_invalid", f"{label} is invalid: {exc}"))
                continue
            if not resolved_path.exists():
                errors.append(error("runtime_artifact_missing", f"{label} points to a missing runtime file: {ref}"))
                continue
            if not resolved_path.is_file():
                errors.append(
                    error(
                        "runtime_artifact_invalid",
                        f"{label} must resolve to a file inside .cerebro: {ref}",
                    )
                )
                continue
            if expected_sha256:
                if not self._is_valid_runtime_artifact_sha256(expected_sha256):
                    errors.append(
                        error(
                            "runtime_artifact_invalid",
                            f"{label} has invalid artifact hash metadata: {ref}",
                        )
                    )
                    continue
                try:
                    current_sha256 = self.compute_sha256(resolved_path)
                except StateStoreError as exc:
                    errors.append(error("runtime_artifact_invalid", f"{label} could not be hashed: {exc}"))
                    continue
                if current_sha256 != expected_sha256:
                    errors.append(
                        error(
                            "runtime_artifact_hash_mismatch",
                            f"{label} content no longer matches the persisted runtime artifact digest: {ref}",
                        )
                    )
        return errors

    def _timestamp_now(self) -> str:
        """Return a stable ISO 8601 timestamp in UTC."""
        return datetime.now(timezone.utc).isoformat(timespec="seconds")

    def _bump_revision(self, state: dict) -> None:
        """Increment revision while preserving monotonic integer semantics."""
        revision = state.get("revision")
        if not isinstance(revision, int) or isinstance(revision, bool) or revision < 0:
            raise StateStoreError("revision must be a non-negative integer")
        state["revision"] = revision + 1

    def _require_valid_runtime_context(self) -> None:
        """Block mutating continuity operations when the current context is invalid."""
        result = self.validate_state()
        if not result["ok"]:
            raise StateValidationError(result["errors"])

    def _assert_state_matches_validated_revision(self, state: dict, validated_revision: int) -> None:
        """Reject work that moved away from the revision that was just validated."""
        if state["revision"] != validated_revision:
            raise StateStoreError("state changed after validation")

    def _runtime_validation_context(self, state: dict) -> tuple[list[dict], dict | None]:
        """Validate runtime usability for a single in-memory state snapshot."""
        source_errors: list[dict] = []
        if not state["sources"]:
            source_errors.append(
                error(
                    "sources_unregistered",
                    "at least one source must be registered before runtime use",
                )
            )
        else:
            for item in state["sources"]:
                try:
                    resolved_path, _ = self._resolve_registered_path(item["path"])
                    current_hash = self.compute_sha256(resolved_path)
                except StateStoreError as exc:
                    source_errors.append(self._map_source_resolution_error(str(exc)))
                    continue

                if current_hash != item["sha256"]:
                    source_errors.append(
                        error(
                            "source_hash_mismatch",
                            f"registered hash does not match current file content: {item['path']}",
                        )
                    )

        session_data, session_errors = self._read_validated_session_for_state(state)
        artifact_errors = self._runtime_artifact_validation_errors(state)
        return [*source_errors, *session_errors, *artifact_errors], session_data

    def _runtime_validation_errors(self, state: dict) -> list[dict]:
        """Validate runtime usability for a single in-memory state snapshot."""
        return self._runtime_validation_context(state)[0]

    def _hash_session_token(self, token: str) -> str:
        """Hash one session capability token before persistence or comparison."""
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    def _hash_session_live_proof(self, proof: str) -> str:
        """Hash one live session proof before persistence or comparison."""
        return hashlib.sha256(proof.encode("utf-8")).hexdigest()

    def _resolve_session_claims_dir(self) -> Path:
        """Resolve the external per-user claim directory for live session authority."""
        override = os.environ.get(SESSION_CLAIMS_DIR_ENV_VAR, "").strip()
        if override:
            return Path(override).expanduser().resolve()

        if os.name == "nt":
            local_app_data = os.environ.get("LOCALAPPDATA", "").strip()
            if local_app_data:
                return Path(local_app_data).resolve() / "Cerebro" / "session_claims"

        xdg_state_home = os.environ.get("XDG_STATE_HOME", "").strip()
        if xdg_state_home:
            return Path(xdg_state_home).expanduser().resolve() / "cerebro" / "session_claims"

        return Path.home().resolve() / ".local" / "state" / "cerebro" / "session_claims"

    def _resolve_session_live_proofs_dir(self) -> Path:
        """Resolve the external per-user live-proof directory for active session freshness."""
        override = os.environ.get(SESSION_LIVE_PROOFS_DIR_ENV_VAR, "").strip()
        if override:
            return Path(override).expanduser().resolve()

        claims_override = os.environ.get(SESSION_CLAIMS_DIR_ENV_VAR, "").strip()
        if claims_override:
            return Path(claims_override).expanduser().resolve().parent / "session_live_proofs"

        if os.name == "nt":
            local_app_data = os.environ.get("LOCALAPPDATA", "").strip()
            if local_app_data:
                return Path(local_app_data).resolve() / "Cerebro" / "session_live_proofs"

        xdg_state_home = os.environ.get("XDG_STATE_HOME", "").strip()
        if xdg_state_home:
            return Path(xdg_state_home).expanduser().resolve() / "cerebro" / "session_live_proofs"

        return Path.home().resolve() / ".local" / "state" / "cerebro" / "session_live_proofs"

    def _session_claim_path(self, claim_id: str) -> Path:
        """Return the external claim path for one claim id."""
        return self.claims_dir / f"{claim_id}.json"

    def _session_live_proof_path(self, proof_id: str) -> Path:
        """Return the external live-proof path for one proof id."""
        return self.live_proofs_dir / f"{proof_id}.json"

    def _session_claim_backend(self) -> str:
        """Return the active backend for session claim storage."""
        if os.environ.get(SESSION_CLAIMS_DIR_ENV_VAR, "").strip():
            return SESSION_CLAIM_BACKEND_FILE
        return SESSION_CLAIM_BACKEND_FILE

    def _session_claim_target_name(self, claim_id: str) -> str:
        """Return one deterministic external target name for a session claim."""
        digest = hashlib.sha256(f"{self._hash_root_identity()}:claim:{claim_id}".encode("utf-8")).hexdigest()[:32]
        return f"Cerebro.SC.{digest}"

    def _legacy_session_claim_target_name(self, claim_id: str) -> str:
        """Return the previous WinCred target name for compatibility reads and cleanup."""
        return f"Cerebro.SessionClaim.{self._hash_root_identity()}.{claim_id}"

    def _session_claim_location(self, claim_id: str, *, backend: str | None = None) -> str:
        """Return one human-readable location descriptor for a claim."""
        resolved_backend = backend or self._session_claim_backend()
        if resolved_backend == SESSION_CLAIM_BACKEND_WINCRED:
            return self._session_claim_target_name(claim_id)
        return f"session_claims/{claim_id}.json"

    def _session_live_proof_backend(self) -> str:
        """Return the active backend for session live-proof storage."""
        if os.environ.get(SESSION_LIVE_PROOFS_DIR_ENV_VAR, "").strip():
            return SESSION_LIVE_PROOF_BACKEND_FILE
        return SESSION_LIVE_PROOF_BACKEND_FILE

    def _session_live_proof_target_name(self, proof_id: str) -> str:
        """Return one deterministic external target name for a live proof."""
        digest = hashlib.sha256(f"{self._hash_root_identity()}:proof:{proof_id}".encode("utf-8")).hexdigest()[:32]
        return f"Cerebro.SL.{digest}"

    def _legacy_session_live_proof_target_name(self, proof_id: str) -> str:
        """Return the previous WinCred target name for compatibility reads and cleanup."""
        return f"Cerebro.SessionLiveProof.{self._hash_root_identity()}.{proof_id}"

    def _session_live_proof_location(self, proof_id: str, *, backend: str | None = None) -> str:
        """Return one human-readable location descriptor for a live proof."""
        resolved_backend = backend or self._session_live_proof_backend()
        if resolved_backend == SESSION_LIVE_PROOF_BACKEND_WINCRED:
            return self._session_live_proof_target_name(proof_id)
        return f"session_live_proofs/{proof_id}.json"

    def _hash_root_identity(self) -> str:
        """Hash the resolved project root for claim-to-root binding."""
        return hashlib.sha256(str(self.root).encode("utf-8")).hexdigest()

    def _hash_session_owner_binding(self, binding: str) -> str:
        """Hash one local owner-context binding before persistence or comparison."""
        return hashlib.sha256(binding.encode("utf-8")).hexdigest()

    def _current_session_owner_binding(self) -> str:
        """Return one best-effort fingerprint for the current live holder context."""
        parent_pid = os.getppid()
        if not isinstance(parent_pid, int) or parent_pid <= 0:
            return f"{os.name}:parent:0"

        parent_identity = self._process_binding_identity(parent_pid)
        return f"{os.name}:parent:{parent_pid}:{parent_identity}"

    def _process_binding_identity(self, pid: int) -> str:
        """Return one stable-enough per-process identity marker for holder binding."""
        if os.name == "nt":
            identity = self._windows_process_binding_identity(pid)
            if identity:
                return identity
        else:
            identity = self._proc_process_binding_identity(pid)
            if identity:
                return identity
        return f"pid:{pid}"

    def _proc_process_binding_identity(self, pid: int) -> str:
        """Return a Linux-style process identity when `/proc` is available."""
        proc_dir = Path("/proc") / str(pid)
        stat_path = proc_dir / "stat"
        if not stat_path.exists():
            return ""

        try:
            stat_text = stat_path.read_text(encoding="utf-8")
        except OSError:
            return ""

        right_paren = stat_text.rfind(")")
        if right_paren == -1:
            return ""
        fields = stat_text[right_paren + 2 :].split()
        if len(fields) <= 19:
            return ""

        start_ticks = fields[19]
        exe_path = ""
        exe_link = proc_dir / "exe"
        try:
            exe_path = os.readlink(exe_link)
        except OSError:
            exe_path = ""
        return f"start:{start_ticks};exe:{exe_path}"

    def _windows_process_binding_identity(self, pid: int) -> str:
        """Return a Windows process identity from creation time plus executable path."""
        try:
            import ctypes
            from ctypes import wintypes
        except ImportError:
            return ""

        process_query_limited_information = 0x1000
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel32.OpenProcess.restype = wintypes.HANDLE
        kernel32.GetProcessTimes.argtypes = [
            wintypes.HANDLE,
            ctypes.POINTER(wintypes.FILETIME),
            ctypes.POINTER(wintypes.FILETIME),
            ctypes.POINTER(wintypes.FILETIME),
            ctypes.POINTER(wintypes.FILETIME),
        ]
        kernel32.GetProcessTimes.restype = wintypes.BOOL
        kernel32.QueryFullProcessImageNameW.argtypes = [
            wintypes.HANDLE,
            wintypes.DWORD,
            wintypes.LPWSTR,
            ctypes.POINTER(wintypes.DWORD),
        ]
        kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel32.CloseHandle.restype = wintypes.BOOL

        handle = kernel32.OpenProcess(process_query_limited_information, False, pid)
        if not handle:
            return ""

        try:
            created_at = wintypes.FILETIME()
            exited_at = wintypes.FILETIME()
            kernel_time = wintypes.FILETIME()
            user_time = wintypes.FILETIME()
            if not kernel32.GetProcessTimes(
                handle,
                ctypes.byref(created_at),
                ctypes.byref(exited_at),
                ctypes.byref(kernel_time),
                ctypes.byref(user_time),
            ):
                return ""

            created_ticks = (int(created_at.dwHighDateTime) << 32) | int(created_at.dwLowDateTime)
            buffer_length = wintypes.DWORD(32768)
            buffer = ctypes.create_unicode_buffer(buffer_length.value)
            if kernel32.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(buffer_length)):
                executable_path = buffer.value[: buffer_length.value]
            else:
                executable_path = ""
            return f"created:{created_ticks};exe:{executable_path}"
        finally:
            kernel32.CloseHandle(handle)

    def _write_session_claim(self, claim_data: dict) -> None:
        """Persist one external session claim outside the project root."""
        backend = self._session_claim_backend()
        if backend == SESSION_CLAIM_BACKEND_WINCRED:
            payload = (json.dumps(claim_data, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
        else:
            payload = (json.dumps(claim_data, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
        self._write_session_claim_bytes(claim_data["claim_id"], payload, backend=backend)

    def _write_session_live_proof(self, proof_data: dict) -> None:
        """Persist one external live session proof outside the project root."""
        backend = self._session_live_proof_backend()
        if backend == SESSION_LIVE_PROOF_BACKEND_WINCRED:
            payload = (json.dumps(proof_data, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
        else:
            payload = (json.dumps(proof_data, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
        self._write_session_live_proof_bytes(proof_data["proof_id"], payload, backend=backend)

    def _encode_wincred_payload(self, payload: bytes) -> bytes:
        """Compress WinCred payloads to stay below the host's effective blob limits."""
        return WINCRED_COMPRESSED_PAYLOAD_PREFIX + zlib.compress(payload, level=6)

    def _decode_wincred_payload(self, payload: bytes, *, label: str) -> bytes:
        """Decode one WinCred payload while preserving compatibility with legacy plain JSON bytes."""
        if not payload.startswith(WINCRED_COMPRESSED_PAYLOAD_PREFIX):
            return payload
        try:
            return zlib.decompress(payload[len(WINCRED_COMPRESSED_PAYLOAD_PREFIX) :])
        except zlib.error as exc:
            raise StateStoreError(f"failed to decode {label} from WinCred storage") from exc

    def _encode_wincred_structured_payload(
        self,
        payload: bytes,
        *,
        prefix: bytes,
        fields: tuple[str, ...],
    ) -> bytes:
        """Pack one known JSON object into a smaller WinCred-specific envelope."""
        try:
            data = json.loads(payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return self._encode_wincred_payload(payload)
        if not isinstance(data, dict):
            return self._encode_wincred_payload(payload)
        if set(data.keys()) != set(fields):
            return self._encode_wincred_payload(payload)
        values: list[str] = []
        for field in fields:
            value = data.get(field)
            if not isinstance(value, str) or "\n" in value:
                return self._encode_wincred_payload(payload)
            values.append(value)
        packed = ("\n".join(values) + "\n").encode("utf-8")
        return prefix + zlib.compress(packed, level=6)

    def _decode_wincred_structured_payload(
        self,
        payload: bytes,
        *,
        prefix: bytes,
        fields: tuple[str, ...],
        label: str,
    ) -> bytes:
        """Decode one smaller WinCred-specific envelope back into canonical compact JSON bytes."""
        if not payload.startswith(prefix):
            return self._decode_wincred_payload(payload, label=label)
        try:
            packed = zlib.decompress(payload[len(prefix) :])
        except zlib.error as exc:
            raise StateStoreError(f"failed to decode {label} from WinCred storage") from exc
        try:
            values = packed.decode("utf-8").splitlines()
        except UnicodeDecodeError as exc:
            raise StateStoreError(f"failed to decode {label} from WinCred storage") from exc
        if len(values) != len(fields):
            raise StateStoreError(f"failed to decode {label} from WinCred storage")
        data = {field: value for field, value in zip(fields, values)}
        return (json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")

    def _encode_wincred_session_claim_payload(self, payload: bytes) -> bytes:
        """Encode one session claim into a compact WinCred envelope when the schema is known."""
        try:
            data = json.loads(payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return self._encode_wincred_payload(payload)
        if not isinstance(data, dict) or set(data.keys()) != set(WINCRED_SESSION_CLAIM_FIELDS):
            return self._encode_wincred_payload(payload)
        try:
            packed = b"".join(
                (
                    self._pack_prefixed_hex_identifier(data["claim_id"], prefix="claim-", label="session claim claim_id"),
                    self._pack_prefixed_hex_identifier(data["session_id"], prefix="session-", label="session claim session_id"),
                    self._pack_sha256_hex(data["root_sha256"], label="session claim root_sha256"),
                    self._pack_sha256_hex(data["session_token_sha256"], label="session claim session_token_sha256"),
                    self._pack_prefixed_hex_identifier(data["live_proof_id"], prefix="proof-", label="session claim live_proof_id"),
                    self._pack_sha256_hex(
                        data["session_live_proof_sha256"],
                        label="session claim session_live_proof_sha256",
                    ),
                    self._pack_sha256_hex(data["owner_binding_sha256"], label="session claim owner_binding_sha256"),
                )
            )
        except ValueError:
            return self._encode_wincred_payload(payload)
        return WINCRED_PACKED_SESSION_CLAIM_PREFIX + packed

    def _decode_wincred_session_claim_payload(self, payload: bytes) -> bytes:
        """Decode one WinCred session claim payload back into canonical compact JSON bytes."""
        if payload.startswith(WINCRED_PACKED_SESSION_CLAIM_PREFIX):
            packed = payload[len(WINCRED_PACKED_SESSION_CLAIM_PREFIX) :]
            if len(packed) == 176:
                data = {
                    "claim_id": self._unpack_prefixed_hex_identifier(
                        packed[0:16],
                        prefix="claim-",
                    ),
                    "session_id": self._unpack_prefixed_hex_identifier(
                        packed[16:32],
                        prefix="session-",
                    ),
                    "root_sha256": packed[32:64].hex(),
                    "session_token_sha256": packed[64:96].hex(),
                    "live_proof_id": self._unpack_prefixed_hex_identifier(
                        packed[96:112],
                        prefix="proof-",
                    ),
                    "session_live_proof_sha256": packed[112:144].hex(),
                    "owner_binding_sha256": packed[144:176].hex(),
                }
                return (json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
            return self._decode_wincred_structured_payload(
                payload,
                prefix=WINCRED_PACKED_SESSION_CLAIM_PREFIX,
                fields=WINCRED_SESSION_CLAIM_FIELDS,
                label="external session claim",
            )
        return self._decode_wincred_payload(payload, label="external session claim")

    def _encode_wincred_session_live_proof_payload(self, payload: bytes) -> bytes:
        """Encode one session live proof into a compact WinCred envelope when the schema is known."""
        try:
            data = json.loads(payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return self._encode_wincred_payload(payload)
        if not isinstance(data, dict) or set(data.keys()) != set(WINCRED_SESSION_LIVE_PROOF_FIELDS):
            return self._encode_wincred_payload(payload)
        try:
            packed = b"".join(
                (
                    self._pack_prefixed_hex_identifier(data["proof_id"], prefix="proof-", label="session live proof proof_id"),
                    self._pack_prefixed_hex_identifier(
                        data["session_id"],
                        prefix="session-",
                        label="session live proof session_id",
                    ),
                    self._pack_sha256_hex(data["root_sha256"], label="session live proof root_sha256"),
                    self._pack_base64url_token(
                        data["session_live_proof"],
                        expected_bytes=32,
                        label="session live proof session_live_proof",
                    ),
                )
            )
        except ValueError:
            return self._encode_wincred_payload(payload)
        return WINCRED_PACKED_SESSION_LIVE_PROOF_PREFIX + packed

    def _decode_wincred_session_live_proof_payload(self, payload: bytes) -> bytes:
        """Decode one WinCred session live proof payload back into canonical compact JSON bytes."""
        if payload.startswith(WINCRED_PACKED_SESSION_LIVE_PROOF_PREFIX):
            packed = payload[len(WINCRED_PACKED_SESSION_LIVE_PROOF_PREFIX) :]
            if len(packed) == 96:
                data = {
                    "proof_id": self._unpack_prefixed_hex_identifier(packed[0:16], prefix="proof-"),
                    "session_id": self._unpack_prefixed_hex_identifier(packed[16:32], prefix="session-"),
                    "root_sha256": packed[32:64].hex(),
                    "session_live_proof": self._unpack_base64url_token(packed[64:96]),
                }
                return (json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
            return self._decode_wincred_structured_payload(
                payload,
                prefix=WINCRED_PACKED_SESSION_LIVE_PROOF_PREFIX,
                fields=WINCRED_SESSION_LIVE_PROOF_FIELDS,
                label="external session live proof",
            )
        return self._decode_wincred_payload(payload, label="external session live proof")

    def _pack_prefixed_hex_identifier(self, value: object, *, prefix: str, label: str) -> bytes:
        """Pack one `prefix + 32hex` identifier into 16 raw bytes."""
        if not isinstance(value, str) or not value.startswith(prefix):
            raise ValueError(label)
        suffix = value[len(prefix) :]
        if len(suffix) != 32:
            raise ValueError(label)
        try:
            return bytes.fromhex(suffix)
        except ValueError as exc:
            raise ValueError(label) from exc

    def _unpack_prefixed_hex_identifier(self, value: bytes, *, prefix: str) -> str:
        """Unpack one 16-byte identifier into its canonical prefixed hex form."""
        if len(value) != 16:
            raise StateStoreError("failed to decode WinCred identifier payload")
        return prefix + value.hex()

    def _pack_sha256_hex(self, value: object, *, label: str) -> bytes:
        """Pack one sha256 hex string into 32 raw bytes."""
        if not isinstance(value, str) or len(value) != 64:
            raise ValueError(label)
        try:
            return bytes.fromhex(value)
        except ValueError as exc:
            raise ValueError(label) from exc

    def _pack_base64url_token(self, value: object, *, expected_bytes: int, label: str) -> bytes:
        """Pack one URL-safe base64 token into its raw byte form."""
        if not isinstance(value, str) or not value:
            raise ValueError(label)
        padding = "=" * (-len(value) % 4)
        try:
            decoded = base64.urlsafe_b64decode((value + padding).encode("ascii"))
        except (ValueError, UnicodeEncodeError) as exc:
            raise ValueError(label) from exc
        if len(decoded) != expected_bytes or self._unpack_base64url_token(decoded) != value:
            raise ValueError(label)
        return decoded

    def _unpack_base64url_token(self, value: bytes) -> str:
        """Unpack one raw token into URL-safe base64 without padding."""
        return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")

    def _read_optional_session_claim_bytes(self, claim_id: object, *, backend: str | None = None) -> bytes | None:
        """Return raw claim bytes from the active backend when present."""
        if not isinstance(claim_id, str) or not claim_id.strip():
            return None
        normalized_claim_id = claim_id.strip()
        resolved_backend = backend or self._session_claim_backend()
        if resolved_backend == SESSION_CLAIM_BACKEND_WINCRED:
            for target_name in (
                self._session_claim_target_name(normalized_claim_id),
                self._legacy_session_claim_target_name(normalized_claim_id),
            ):
                try:
                    payload = read_generic_credential(target_name)
                except WindowsCredentialStoreError as exc:
                    raise StateStoreError(f"failed to read external session claim: {target_name}") from exc
                if payload is None:
                    continue
                return self._decode_wincred_session_claim_payload(payload)
            return None
        return self._read_optional_file_bytes(self._session_claim_path(normalized_claim_id))

    def _write_session_claim_bytes(self, claim_id: object, payload: bytes, *, backend: str | None = None) -> None:
        """Persist raw claim bytes to the active backend."""
        if not isinstance(claim_id, str) or not claim_id.strip():
            raise StateStoreError("external session claim id must be a non-empty string")
        normalized_claim_id = claim_id.strip()
        resolved_backend = backend or self._session_claim_backend()
        if resolved_backend == SESSION_CLAIM_BACKEND_WINCRED:
            target_name = self._session_claim_target_name(normalized_claim_id)
            try:
                write_generic_credential(
                    target_name,
                    self._encode_wincred_session_claim_payload(payload),
                )
            except WindowsCredentialStoreError as exc:
                raise StateStoreError(f"failed to write external session claim: {target_name}") from exc
            legacy_target_name = self._legacy_session_claim_target_name(normalized_claim_id)
            if legacy_target_name != target_name:
                try:
                    delete_generic_credential(legacy_target_name)
                except WindowsCredentialStoreError as exc:
                    raise StateStoreError(f"failed to remove external session claim: {legacy_target_name}") from exc
            return
        self.claims_dir.mkdir(parents=True, exist_ok=True)
        self._write_bytes_atomic(self._session_claim_path(normalized_claim_id), payload)

    def _read_optional_session_live_proof_bytes(self, proof_id: object, *, backend: str | None = None) -> bytes | None:
        """Return raw live-proof bytes from the active backend when present."""
        if not isinstance(proof_id, str) or not proof_id.strip():
            return None
        normalized_proof_id = proof_id.strip()
        resolved_backend = backend or self._session_live_proof_backend()
        if resolved_backend == SESSION_LIVE_PROOF_BACKEND_WINCRED:
            for target_name in (
                self._session_live_proof_target_name(normalized_proof_id),
                self._legacy_session_live_proof_target_name(normalized_proof_id),
            ):
                try:
                    payload = read_generic_credential(target_name)
                except WindowsCredentialStoreError as exc:
                    raise StateStoreError(f"failed to read external session live proof: {target_name}") from exc
                if payload is None:
                    continue
                return self._decode_wincred_session_live_proof_payload(payload)
            return None
        return self._read_optional_file_bytes(self._session_live_proof_path(normalized_proof_id))

    def _write_session_live_proof_bytes(self, proof_id: object, payload: bytes, *, backend: str | None = None) -> None:
        """Persist raw live-proof bytes to the active backend."""
        if not isinstance(proof_id, str) or not proof_id.strip():
            raise StateStoreError("external session live proof id must be a non-empty string")
        normalized_proof_id = proof_id.strip()
        resolved_backend = backend or self._session_live_proof_backend()
        if resolved_backend == SESSION_LIVE_PROOF_BACKEND_WINCRED:
            target_name = self._session_live_proof_target_name(normalized_proof_id)
            try:
                write_generic_credential(
                    target_name,
                    self._encode_wincred_session_live_proof_payload(payload),
                )
            except WindowsCredentialStoreError as exc:
                raise StateStoreError(f"failed to write external session live proof: {target_name}") from exc
            legacy_target_name = self._legacy_session_live_proof_target_name(normalized_proof_id)
            if legacy_target_name != target_name:
                try:
                    delete_generic_credential(legacy_target_name)
                except WindowsCredentialStoreError as exc:
                    raise StateStoreError(f"failed to remove external session live proof: {legacy_target_name}") from exc
            return
        self.live_proofs_dir.mkdir(parents=True, exist_ok=True)
        self._write_bytes_atomic(self._session_live_proof_path(normalized_proof_id), payload)

    def _read_session_claim_file(self, claim_id: object) -> tuple[dict | None, list[dict]]:
        """Return the raw external claim file when it is structurally valid."""
        if not isinstance(claim_id, str) or not claim_id.strip():
            return None, [error("session_claim_invalid", "session.owner_claim_id must reference one external claim id")]
        normalized_claim_id = claim_id.strip()
        location = self._session_claim_location(normalized_claim_id)
        try:
            raw_claim = self._read_optional_session_claim_bytes(normalized_claim_id)
        except StateStoreError:
            return None, [error("session_claim_unreadable", f"failed to read external session claim: {location}")]
        if raw_claim is None:
            return None, [error("session_claim_missing", f"external session claim not found: {location}")]
        try:
            claim_data = json.loads(raw_claim.decode("utf-8"))
        except json.JSONDecodeError as exc:
            return None, [error("session_claim_invalid_json", f"invalid JSON in external session claim: {exc.msg}")]

        expected_keys = {
            "claim_id",
            "session_id",
            "root_sha256",
            "session_token_sha256",
            "live_proof_id",
            "session_live_proof_sha256",
            "owner_binding_sha256",
        }
        if not isinstance(claim_data, dict):
            return None, [error("session_claim_invalid_schema", "external session claim must be a JSON object")]
        actual_keys = set(claim_data.keys())
        if actual_keys != expected_keys:
            return None, [error("session_claim_invalid_schema", "external session claim does not match the required schema")]
        if not isinstance(claim_data.get("claim_id"), str) or not claim_data["claim_id"]:
            return None, [error("session_claim_invalid_schema", "external session claim claim_id must be a non-empty string")]
        if not isinstance(claim_data.get("session_id"), str) or not claim_data["session_id"]:
            return None, [error("session_claim_invalid_schema", "external session claim session_id must be a non-empty string")]
        root_sha256 = claim_data.get("root_sha256", "")
        if not isinstance(root_sha256, str) or not self._is_valid_sha256_string(root_sha256):
            return None, [error("session_claim_invalid_schema", "external session claim root_sha256 must be a sha256 hex string")]
        session_token_sha256 = claim_data.get("session_token_sha256", "")
        if not isinstance(session_token_sha256, str) or not self._is_valid_sha256_string(session_token_sha256):
            return None, [error("session_claim_invalid_schema", "external session claim session_token_sha256 must be a sha256 hex string")]
        live_proof_id = claim_data.get("live_proof_id", "")
        if not isinstance(live_proof_id, str) or not live_proof_id:
            return None, [error("session_claim_invalid_schema", "external session claim live_proof_id must be a non-empty string")]
        session_live_proof_sha256 = claim_data.get("session_live_proof_sha256", "")
        if not isinstance(session_live_proof_sha256, str) or not self._is_valid_sha256_string(session_live_proof_sha256):
            return None, [
                error(
                    "session_claim_invalid_schema",
                    "external session claim session_live_proof_sha256 must be a sha256 hex string",
                )
            ]
        owner_binding_sha256 = claim_data.get("owner_binding_sha256", "")
        if not isinstance(owner_binding_sha256, str) or not self._is_valid_sha256_string(owner_binding_sha256):
            return None, [error("session_claim_invalid_schema", "external session claim owner_binding_sha256 must be a sha256 hex string")]
        return claim_data, []

    def _read_validated_session_claim(self, session_data: dict) -> tuple[dict | None, list[dict]]:
        """Return one validated external session claim for the current local session artifact."""
        claim_data, claim_errors = self._read_session_claim_file(session_data.get("owner_claim_id"))
        if claim_errors or claim_data is None:
            return claim_data, claim_errors
        if claim_data["session_id"] != session_data["session_id"]:
            return None, [error("session_claim_mismatch", "external session claim does not match the active local session id")]
        if claim_data["root_sha256"] != self._hash_root_identity():
            return None, [error("session_claim_mismatch", "external session claim does not belong to this project root")]
        return claim_data, []

    def _remove_session_claim(self, claim_id: object, *, backend: str | None = None) -> None:
        """Remove one external session claim when present."""
        if not isinstance(claim_id, str) or not claim_id.strip():
            return
        normalized_claim_id = claim_id.strip()
        resolved_backend = backend or self._session_claim_backend()
        if resolved_backend == SESSION_CLAIM_BACKEND_WINCRED:
            for target_name in (
                self._session_claim_target_name(normalized_claim_id),
                self._legacy_session_claim_target_name(normalized_claim_id),
            ):
                try:
                    delete_generic_credential(target_name)
                except WindowsCredentialStoreError as exc:
                    raise StateStoreError(f"failed to remove external session claim: {target_name}") from exc
            return
        claim_path = self._session_claim_path(normalized_claim_id)
        if not claim_path.exists():
            return
        try:
            claim_path.unlink()
        except OSError as exc:
            raise StateStoreError(f"failed to remove external session claim: {claim_path}") from exc

    def _capture_session_claim_snapshot(self, claim_id: object, *, label: str) -> dict | None:
        """Capture one provider-neutral claim snapshot for later comparison or restore."""
        if not isinstance(claim_id, str) or not claim_id.strip():
            return None
        normalized_claim_id = claim_id.strip()
        return {
            "label": label,
            "claim_id": normalized_claim_id,
            "backend": self._session_claim_backend(),
            "bytes": self._read_optional_session_claim_bytes(normalized_claim_id),
        }

    def _restore_session_claim_snapshot(self, snapshot: dict) -> None:
        """Restore one provider-neutral claim snapshot."""
        claim_id = snapshot.get("claim_id")
        if not isinstance(claim_id, str) or not claim_id:
            raise StateStoreError("session claim snapshot is missing claim_id")
        backend = snapshot.get("backend")
        if not isinstance(backend, str) or not backend:
            raise StateStoreError("session claim snapshot is missing backend")
        before_bytes = snapshot.get("bytes")
        if before_bytes is None:
            self._remove_session_claim(claim_id, backend=backend)
            return
        if not isinstance(before_bytes, bytes):
            raise StateStoreError("session claim snapshot must contain raw bytes or None")
        self._write_session_claim_bytes(claim_id, before_bytes, backend=backend)

    def _read_session_live_proof_file(self, proof_id: object) -> tuple[dict | None, list[dict]]:
        """Return the raw external live proof when it is structurally valid."""
        if not isinstance(proof_id, str) or not proof_id.strip():
            return None, [error("session_live_proof_invalid", "external session live proof id must be a non-empty string")]
        normalized_proof_id = proof_id.strip()
        location = self._session_live_proof_location(normalized_proof_id)
        try:
            raw_proof = self._read_optional_session_live_proof_bytes(normalized_proof_id)
        except StateStoreError:
            return None, [error("session_live_proof_unreadable", f"failed to read external session live proof: {location}")]
        if raw_proof is None:
            return None, [error("session_live_proof_missing", f"external session live proof not found: {location}")]
        try:
            proof_data = json.loads(raw_proof.decode("utf-8"))
        except json.JSONDecodeError as exc:
            return None, [error("session_live_proof_invalid_json", f"invalid JSON in external session live proof: {exc.msg}")]

        expected_keys = {"proof_id", "session_id", "root_sha256", "session_live_proof"}
        if not isinstance(proof_data, dict):
            return None, [error("session_live_proof_invalid_schema", "external session live proof must be a JSON object")]
        actual_keys = set(proof_data.keys())
        if actual_keys != expected_keys:
            return None, [error("session_live_proof_invalid_schema", "external session live proof does not match the required schema")]
        if not isinstance(proof_data.get("proof_id"), str) or not proof_data["proof_id"]:
            return None, [error("session_live_proof_invalid_schema", "external session live proof proof_id must be a non-empty string")]
        if not isinstance(proof_data.get("session_id"), str) or not proof_data["session_id"]:
            return None, [error("session_live_proof_invalid_schema", "external session live proof session_id must be a non-empty string")]
        root_sha256 = proof_data.get("root_sha256", "")
        if not isinstance(root_sha256, str) or not self._is_valid_sha256_string(root_sha256):
            return None, [error("session_live_proof_invalid_schema", "external session live proof root_sha256 must be a sha256 hex string")]
        live_proof = proof_data.get("session_live_proof", "")
        if not isinstance(live_proof, str) or not live_proof:
            return None, [error("session_live_proof_invalid_schema", "external session live proof session_live_proof must be a non-empty string")]
        return proof_data, []

    def _read_validated_session_live_proof(self, session_data: dict, claim_data: dict) -> tuple[dict | None, list[dict]]:
        """Return one validated external live proof for the current local session artifact."""
        proof_data, proof_errors = self._read_session_live_proof_file(claim_data.get("live_proof_id"))
        if proof_errors or proof_data is None:
            return proof_data, proof_errors
        if proof_data["proof_id"] != claim_data["live_proof_id"]:
            return None, [error("session_live_proof_mismatch", "external session live proof does not match the active live proof id")]
        if proof_data["session_id"] != session_data["session_id"]:
            return None, [error("session_live_proof_mismatch", "external session live proof does not match the active local session id")]
        if proof_data["root_sha256"] != self._hash_root_identity():
            return None, [error("session_live_proof_mismatch", "external session live proof does not belong to this project root")]
        if not hmac.compare_digest(
            claim_data["session_live_proof_sha256"],
            self._hash_session_live_proof(proof_data["session_live_proof"]),
        ):
            return None, [
                error(
                    "session_live_proof_mismatch",
                    "external session live proof does not match the active local session claim",
                )
            ]
        return proof_data, []

    def _remove_session_live_proof(self, proof_id: object, *, backend: str | None = None) -> None:
        """Remove one external live proof when present."""
        if not isinstance(proof_id, str) or not proof_id.strip():
            return
        normalized_proof_id = proof_id.strip()
        resolved_backend = backend or self._session_live_proof_backend()
        if resolved_backend == SESSION_LIVE_PROOF_BACKEND_WINCRED:
            for target_name in (
                self._session_live_proof_target_name(normalized_proof_id),
                self._legacy_session_live_proof_target_name(normalized_proof_id),
            ):
                try:
                    delete_generic_credential(target_name)
                except WindowsCredentialStoreError as exc:
                    raise StateStoreError(f"failed to remove external session live proof: {target_name}") from exc
            return
        self._remove_session_live_proof_by_path(self._session_live_proof_path(normalized_proof_id))

    def _remove_session_live_proof_by_path(self, proof_path: Path) -> None:
        """Remove one external live proof by path when present."""
        if not proof_path.exists():
            return
        try:
            proof_path.unlink()
        except OSError as exc:
            raise StateStoreError(f"failed to remove external session live proof: {proof_path}") from exc

    def _is_valid_sha256_string(self, value: str) -> bool:
        """Return whether one string is a lowercase SHA-256 hex digest."""
        return len(value) == 64 and all(character in "0123456789abcdef" for character in value)

    def _read_session_file(self) -> tuple[dict | None, list[dict]]:
        """Return the raw local session file when it is schema-valid independent of one state revision."""
        if not self.session_path.exists():
            return None, []

        try:
            with self.session_path.open(encoding="utf-8") as handle:
                session_data = json.load(handle)
        except json.JSONDecodeError as exc:
            return None, [error("session_invalid_json", f"invalid JSON in session file: {exc.msg}")]
        except OSError:
            return None, [error("session_unreadable", f"failed to read session file: {self.session_path}")]

        validation_errors = validate_session_data(session_data)
        if validation_errors:
            return None, [
                error("session_invalid_schema", "session file does not match the required schema"),
                *validation_errors,
            ]
        return session_data, []

    def _read_validated_session_for_state(self, state: dict) -> tuple[dict | None, list[dict]]:
        """Return the current local session only when it is schema-valid for this revision."""
        pending_errors = self._recover_pending_session_refresh_for_state(state)
        if pending_errors:
            return None, pending_errors
        session_data, session_errors = self._read_session_file()
        active_session_id, active_claim_id = self._active_session_registry(state)
        registry_active = bool(active_session_id) or bool(active_claim_id)
        if session_errors or session_data is None:
            if registry_active:
                return None, [
                    error(
                        "session_registry_mismatch",
                        "canonical state expects one active local session but session artifacts are missing or invalid",
                    ),
                    *session_errors,
                ]
            return session_data, session_errors
        if not registry_active:
            return None, [
                error(
                    "session_not_registered",
                    "local session artifacts exist but no canonical active session is registered",
                )
            ]
        if session_data["session_id"] != active_session_id or session_data["owner_claim_id"] != active_claim_id:
            return None, [
                error(
                    "session_registry_mismatch",
                    "local session artifacts do not match the canonical active session registry",
                )
            ]
        if session_data["based_on_revision"] != state["revision"]:
            return None, [
                error(
                    "session_revision_invalid",
                    "session.based_on_revision must equal state.revision",
                )
            ]
        claim_data, claim_errors = self._read_validated_session_claim(session_data)
        if claim_errors or claim_data is None:
            return None, claim_errors
        live_proof_data, live_proof_errors = self._read_validated_session_live_proof(session_data, claim_data)
        if live_proof_errors or live_proof_data is None:
            return None, live_proof_errors
        return session_data, []

    def _active_session_registry(self, state: dict) -> tuple[str, str]:
        """Return the canonical active local session identifiers from runtime audit metadata."""
        agent_runtime = state.get("agent_runtime", {})
        if not isinstance(agent_runtime, dict):
            return "", ""
        audit = agent_runtime.get("audit", {})
        if not isinstance(audit, dict):
            return "", ""
        active_session_id = audit.get("active_session_id", "")
        active_claim_id = audit.get("active_session_claim_id", "")
        if not isinstance(active_session_id, str):
            active_session_id = ""
        if not isinstance(active_claim_id, str):
            active_claim_id = ""
        return active_session_id, active_claim_id

    def _set_active_session_registry(self, state: dict, *, session_id: str, claim_id: str) -> None:
        """Persist the canonical ids for the one active local session."""
        audit = state["agent_runtime"]["audit"]
        audit["active_session_id"] = session_id
        audit["active_session_claim_id"] = claim_id

    def _clear_active_session_registry(self, state: dict) -> None:
        """Clear the canonical ids for the active local session."""
        self._set_active_session_registry(state, session_id="", claim_id="")

    def _assert_expected_session_token_for_session(
        self,
        session_data: dict,
        expected_session_token: str | None,
    ) -> None:
        """Fail closed when the caller cannot prove possession of the active session capability."""
        claim_data, claim_errors = self._read_validated_session_claim(session_data)
        if claim_errors or claim_data is None:
            raise StateValidationError(claim_errors)

        if not isinstance(expected_session_token, str) or not expected_session_token.strip():
            raise StateValidationError(
                [
                    error(
                        "session_token_required",
                        "explicit session token is required; the runtime never falls back to persisted session claims",
                    )
                ]
            )
        provided_token = expected_session_token.strip()
        if not hmac.compare_digest(claim_data["session_token_sha256"], self._hash_session_token(provided_token)):
            raise StateValidationError(
                [
                    error(
                        "session_token_mismatch",
                        "provided session token does not match the active local session",
                    )
                ]
            )

    def _assert_current_session_owner_binding_for_session(self, session_data: dict) -> None:
        """Fail closed when the caller is not running from the same holder context."""
        claim_data, claim_errors = self._read_validated_session_claim(session_data)
        if claim_errors or claim_data is None:
            raise StateValidationError(claim_errors)
        stored_hash = claim_data.get("owner_binding_sha256", "")
        current_hash = self._hash_session_owner_binding(self._current_session_owner_binding())
        if not isinstance(stored_hash, str) or not hmac.compare_digest(stored_hash, current_hash):
            raise StateValidationError(
                [
                    error(
                        "session_owner_binding_mismatch",
                        "active local session belongs to a different terminal or process holder context",
                    )
                ]
            )

    def read_owned_active_session(self, state: dict, expected_session_token: str | None) -> dict | None:
        """Return the one active local session after proving capability ownership when present."""
        session_data, session_errors = self._read_validated_session_for_state(state)
        if session_errors:
            raise StateValidationError(session_errors)
        if session_data is None:
            return None
        self._assert_expected_session_token_for_session(session_data, expected_session_token)
        self._assert_current_session_owner_binding_for_session(session_data)
        return session_data

    def _session_errors_allow_unowned_discard(self, session_errors: list[dict]) -> bool:
        """Return whether one broken session already lacks enough live proof to require a tokened discard."""
        if not session_errors:
            return False
        allowed_codes = {
            "session_live_proof_missing",
            "session_live_proof_invalid_json",
            "session_live_proof_unreadable",
            "session_live_proof_invalid_schema",
            "session_live_proof_mismatch",
        }
        codes = {str(item.get("code", "")) for item in session_errors if isinstance(item, dict)}
        return bool(codes) and codes.issubset(allowed_codes)

    def _session_errors_allow_registry_only_discard(self, session_errors: list[dict]) -> bool:
        """Return whether one registry-only residue is narrow enough for unowned explicit cleanup."""
        codes = {str(item.get("code", "")) for item in session_errors if isinstance(item, dict)}
        return codes == {"session_registry_mismatch"}

    def _active_session_live_proof_id(self, session_data: dict) -> str | None:
        """Return the current active live-proof id when the claim is readable enough to locate it."""
        claim_data, claim_errors = self._read_validated_session_claim(session_data)
        if claim_errors or claim_data is None:
            return None
        proof_id = claim_data.get("live_proof_id", "")
        if not isinstance(proof_id, str) or not proof_id:
            return None
        return proof_id

    def _capture_session_live_proof_snapshot(self, proof_id: object, *, label: str) -> dict | None:
        """Capture one provider-neutral live-proof snapshot for later comparison or restore."""
        if not isinstance(proof_id, str) or not proof_id.strip():
            return None
        normalized_proof_id = proof_id.strip()
        return {
            "label": label,
            "proof_id": normalized_proof_id,
            "backend": self._session_live_proof_backend(),
            "bytes": self._read_optional_session_live_proof_bytes(normalized_proof_id),
        }

    def _restore_session_live_proof_snapshot(self, snapshot: dict) -> None:
        """Restore one provider-neutral live-proof snapshot."""
        proof_id = snapshot.get("proof_id")
        if not isinstance(proof_id, str) or not proof_id:
            raise StateStoreError("session live-proof snapshot is missing proof_id")
        backend = snapshot.get("backend")
        if not isinstance(backend, str) or not backend:
            raise StateStoreError("session live-proof snapshot is missing backend")
        before_bytes = snapshot.get("bytes")
        if before_bytes is None:
            self._remove_session_live_proof(proof_id, backend=backend)
            return
        if not isinstance(before_bytes, bytes):
            raise StateStoreError("session live-proof snapshot must contain raw bytes or None")
        self._write_session_live_proof_bytes(proof_id, before_bytes, backend=backend)

    def _refresh_session_for_revision(self, session_data: dict, revision: int) -> dict:
        """Advance the active session revision after one successful owner-authenticated mutation."""
        refreshed_session = dict(session_data)
        refreshed_session["based_on_revision"] = revision
        errors = validate_session_data(refreshed_session)
        if errors:
            raise StateValidationError(errors)
        return refreshed_session

    def _build_pending_session_refresh_manifest(self, previous_session: dict, *, target_revision: int) -> dict:
        """Build one local journal that makes a session refresh recoverable across crashes."""
        return {
            "created_at": self._timestamp_now(),
            "session_id": previous_session["session_id"],
            "owner_claim_id": previous_session["owner_claim_id"],
            "previous_session": deepcopy(previous_session),
            "target_revision": target_revision,
        }

    def _load_pending_session_refresh(self) -> dict | None:
        """Return one pending session-refresh journal when the previous mutation did not finish."""
        if not self.session_refresh_pending_path.exists():
            return None
        try:
            pending = json.loads(self.session_refresh_pending_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise StateStoreError(
                f"failed to read pending session refresh journal: {self.session_refresh_pending_path}"
            ) from exc
        if not isinstance(pending, dict):
            raise StateStoreError(
                f"pending session refresh journal must be an object: {self.session_refresh_pending_path}"
            )
        return pending

    def _clear_pending_session_refresh(self) -> None:
        """Remove the local session-refresh journal on a best-effort basis."""
        try:
            self.session_refresh_pending_path.unlink()
        except FileNotFoundError:
            pass
        except OSError:
            pass

    def _recover_pending_session_refresh_for_state(self, state: dict) -> list[dict]:
        """Recover or finalize one interrupted session refresh before session validation proceeds."""
        try:
            pending = self._load_pending_session_refresh()
        except StateStoreError as exc:
            return [error("session_refresh_pending_invalid", str(exc))]
        if pending is None:
            return []

        session_id = pending.get("session_id", "")
        owner_claim_id = pending.get("owner_claim_id", "")
        previous_session = pending.get("previous_session")
        target_revision = pending.get("target_revision")
        if not isinstance(session_id, str) or not session_id:
            return [error("session_refresh_pending_invalid", "pending session refresh journal is missing session_id")]
        if not isinstance(owner_claim_id, str) or not owner_claim_id:
            return [
                error(
                    "session_refresh_pending_invalid",
                    "pending session refresh journal is missing owner_claim_id",
                )
            ]
        if not isinstance(previous_session, dict):
            return [
                error(
                    "session_refresh_pending_invalid",
                    "pending session refresh journal is missing previous_session",
                )
            ]
        previous_session_errors = validate_session_data(previous_session)
        if previous_session_errors:
            return [
                error(
                    "session_refresh_pending_invalid",
                    "pending session refresh journal contains an invalid previous_session snapshot",
                ),
                *previous_session_errors,
            ]
        if previous_session["session_id"] != session_id or previous_session["owner_claim_id"] != owner_claim_id:
            return [
                error(
                    "session_refresh_pending_invalid",
                    "pending session refresh journal does not match the previous_session identity",
                )
            ]
        if not isinstance(target_revision, int) or target_revision < 0:
            return [
                error(
                    "session_refresh_pending_invalid",
                    "pending session refresh journal must declare one non-negative target_revision",
                )
            ]
        previous_revision = previous_session["based_on_revision"]
        if target_revision != previous_revision + 1:
            return [
                error(
                    "session_refresh_pending_invalid",
                    "pending session refresh journal target_revision must advance exactly one revision",
                )
            ]

        active_session_id, active_claim_id = self._active_session_registry(state)
        if active_session_id != session_id or active_claim_id != owner_claim_id:
            return [
                error(
                    "session_refresh_pending_inconsistent",
                    "pending session refresh journal does not match the canonical active session registry",
                )
            ]

        session_data, session_errors = self._read_session_file()
        if session_errors or session_data is None:
            return [
                error(
                    "session_refresh_pending_inconsistent",
                    "pending session refresh journal requires readable session artifacts",
                ),
                *session_errors,
            ]
        if session_data["session_id"] != session_id or session_data["owner_claim_id"] != owner_claim_id:
            return [
                error(
                    "session_refresh_pending_inconsistent",
                    "pending session refresh journal does not match session.local.json",
                )
            ]

        state_revision = state["revision"]
        session_revision = session_data["based_on_revision"]
        if state_revision == previous_revision:
            if session_revision == target_revision:
                self._write_json_atomic(self.session_path, previous_session)
                self._clear_pending_session_refresh()
                return []
            if session_revision == previous_revision:
                self._clear_pending_session_refresh()
                return []
            return [
                error(
                    "session_refresh_pending_inconsistent",
                    "pending session refresh journal found an unexpected session revision before state commit",
                )
            ]

        if state_revision == target_revision:
            if session_revision != target_revision:
                return [
                    error(
                        "session_refresh_pending_inconsistent",
                        "pending session refresh journal found an unexpected session revision after state commit",
                    )
                ]
            self._clear_pending_session_refresh()
            return []

        return [
            error(
                "session_refresh_pending_inconsistent",
                "pending session refresh journal does not match the committed state revision",
            )
        ]

    def _save_state_with_refreshed_session(
        self,
        state: dict,
        *,
        expected_revision: int | None,
        active_session: dict | None,
    ) -> None:
        """Persist state and keep one owned session aligned to the resulting revision."""
        if active_session is None:
            self.save_state(state, expected_revision=expected_revision)
            return

        refreshed_session = self._refresh_session_for_revision(active_session, state["revision"])
        pending_manifest = self._build_pending_session_refresh_manifest(
            active_session,
            target_revision=state["revision"],
        )
        self._write_json_atomic(self.session_refresh_pending_path, pending_manifest)
        session_written = False
        try:
            self._write_json_atomic(self.session_path, refreshed_session)
            session_written = True
            self.save_state(state, expected_revision=expected_revision)
        except Exception:
            if session_written:
                try:
                    self._write_json_atomic(self.session_path, active_session)
                except Exception as restore_exc:  # pragma: no cover - defensive recovery path
                    raise StateStoreError("failed to restore session file after state write failure") from restore_exc
            self._clear_pending_session_refresh()
            raise
        self._clear_pending_session_refresh()

    def _assert_active_session_token(self, state: dict, expected_session_token: str | None) -> None:
        """Require a matching session capability before mutating state under one live local session."""
        self.read_owned_active_session(state, expected_session_token)

    def _assert_expected_session_id(self, state: dict, expected_session_id: str | None) -> None:
        """Fail closed when a session-bound operation no longer owns the same session."""
        if expected_session_id is None:
            return

        session_data, session_errors = self._read_validated_session_for_state(state)
        if session_errors or session_data is None:
            raise StateValidationError(
                [
                    error(
                        "session_changed_during_operation",
                        "local session changed after validation; reopen continuity before retrying",
                    ),
                    *session_errors,
                ]
            )
        if session_data["session_id"] != expected_session_id:
            raise StateValidationError(
                [
                    error(
                        "session_changed_during_operation",
                        "local session changed after validation; reopen continuity before retrying",
                    )
                ]
            )

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

    def _build_agent_plan_update(self, data: object) -> tuple[dict, dict, dict, dict]:
        """Normalize explicit alpha-runtime planning input before persistence."""
        if not isinstance(data, dict):
            raise StateStoreError("agent plan data must be an object")

        expected_keys = {
            "goal",
            "summary",
            "tasks",
            "command_registry",
            "required_command_ids",
            "autonomy_level",
            "protected_paths",
            "blocked_command_prefixes",
            "approval_required_kinds",
        }
        actual_keys = set(data.keys())
        missing = sorted(expected_keys - actual_keys)
        extra = sorted(actual_keys - expected_keys)
        if missing:
            raise StateStoreError(f"agent plan data missing required keys: {', '.join(missing)}")
        if extra:
            raise StateStoreError(f"agent plan data contains unexpected keys: {', '.join(extra)}")

        now = self._timestamp_now()
        plan = {
            "goal": data["goal"],
            "summary": data["summary"],
            "status": "ready" if data["tasks"] else "idle",
            "current_task_id": "",
            "tasks": data["tasks"],
            "generation_id": f"plan-{uuid4().hex[:8]}",
            "updated_at": now,
        }
        for task in plan["tasks"]:
            if not isinstance(task, dict):
                continue
            task.setdefault("retry_blocked_count", 0)
            task.setdefault("verify_blocked_count", 0)
            task.setdefault("apply_blocked_count", 0)
        self._refresh_plan_progress(plan)
        command_registry = {
            "commands": data["command_registry"],
        }
        verification = {
            "required_command_ids": data["required_command_ids"],
            "pending_action_ids": [],
            "last_run_at": "",
            "status": "idle",
            "checks": [],
            "failed_attempt_count": 0,
        }
        execution_policy = {
            "autonomy_level": data["autonomy_level"],
            "protected_paths": data["protected_paths"],
            "blocked_command_prefixes": data["blocked_command_prefixes"],
            "approval_required_kinds": data["approval_required_kinds"],
        }
        candidate = self.load_state()
        candidate["agent_runtime"]["plan"] = plan
        candidate["agent_runtime"]["command_registry"] = command_registry
        candidate["agent_runtime"]["verification"] = verification
        candidate["agent_runtime"]["execution_policy"] = execution_policy
        plan_errors = validate_state_data(candidate)
        if plan_errors:
            raise StateValidationError(plan_errors)
        return plan, command_registry, verification, execution_policy

    def _append_rollback_point(self, state: dict, action_record: dict) -> None:
        """Store one rollback reference in compact audit metadata."""
        rollback_points = list(state["agent_runtime"]["audit"]["rollback_points"])
        rollback_points = [item for item in rollback_points if item["id"] != action_record["id"]]
        rollback_points.append(
            {
                "id": action_record["id"],
                "kind": "soft_delete" if action_record["kind"] == "fs.delete_soft" else "preimage",
                "artifact_ref": action_record["rollback_ref"],
                "created_at": action_record["updated_at"],
            }
        )
        if len(rollback_points) > MAX_ROLLBACK_POINTS:
            rollback_points = rollback_points[-MAX_ROLLBACK_POINTS:]
        state["agent_runtime"]["audit"]["rollback_points"] = rollback_points

    def _action_record_targets_current_plan(self, plan: dict, action_record: dict) -> bool:
        """Return whether one in-flight action record belongs to the current plan generation."""
        details = action_record.get("details", {})
        if isinstance(details, dict):
            plan_generation_id = details.get("plan_generation_id", "")
            current_plan_generation_id = plan.get("generation_id", "")
            if isinstance(plan_generation_id, str) and plan_generation_id:
                return isinstance(current_plan_generation_id, str) and plan_generation_id == current_plan_generation_id

        task_id = action_record.get("task_id", "")
        if isinstance(task_id, str) and task_id:
            tasks = plan.get("tasks", [])
            if isinstance(tasks, list):
                return any(isinstance(task, dict) and task.get("id") == task_id for task in tasks)
        return True

    def _record_used_batch_ids(self, agent_runtime: dict, action_records: list[dict]) -> None:
        """Persist a bounded registry of non-empty batch ids already consumed by apply."""
        batch_registry = agent_runtime.get("batch_registry", {})
        if not isinstance(batch_registry, dict):
            return
        used_batch_ids = batch_registry.get("used_ids", [])
        if not isinstance(used_batch_ids, list):
            used_batch_ids = []
        for action_record in action_records:
            if not self._action_record_targets_current_plan(agent_runtime.get("plan", {}), action_record):
                continue
            batch_id = action_record.get("batch_id", "")
            if not isinstance(batch_id, str) or not batch_id:
                continue
            used_batch_ids = [item for item in used_batch_ids if item != batch_id]
            used_batch_ids.append(batch_id)
        if len(used_batch_ids) > MAX_USED_BATCH_IDS:
            used_batch_ids = used_batch_ids[-MAX_USED_BATCH_IDS:]
        batch_registry["used_ids"] = used_batch_ids

    def _sync_task_with_action(self, plan: dict, action_record: dict) -> None:
        """Attach actions to tasks and move task state into the correct pre-verify posture."""
        if not self._action_record_targets_current_plan(plan, action_record):
            return
        task_id = action_record.get("task_id")
        if not isinstance(task_id, str) or not task_id:
            return
        tasks = plan.get("tasks", [])
        if not isinstance(tasks, list):
            return

        for task in tasks:
            if not isinstance(task, dict) or task.get("id") != task_id:
                continue
            action_ids = task.get("action_ids")
            if isinstance(action_ids, list) and action_record["id"] not in action_ids:
                action_ids.append(action_record["id"])
            status = action_record.get("status")
            if status == "applied":
                task["status"] = "running"
            elif status in {"failed", "blocked"}:
                task["status"] = "failed"
            elif status == "rolled_back":
                task["status"] = "ready"
            break

    def _increment_task_counter(self, plan: dict, task_id: str, counter_field: str) -> bool:
        """Increment one plan-local task counter when runtime discipline records a blocked path."""
        tasks = plan.get("tasks", [])
        if not isinstance(tasks, list):
            return False
        for task in tasks:
            if not isinstance(task, dict) or task.get("id") != task_id:
                continue
            current = task.get(counter_field, 0)
            if not isinstance(current, int) or current < 0:
                current = 0
            task[counter_field] = current + 1
            return True
        return False

    def _apply_runtime_signal(self, state: dict, event_spec: dict) -> bool:
        """Persist decision-critical runtime signals into canonical state."""
        event_type = event_spec.get("event_type", "")
        payload = event_spec.get("payload", {})
        if not isinstance(payload, dict):
            return False
        task_id = payload.get("task_id", "")
        if not isinstance(task_id, str) or not task_id:
            return False
        counter_field_by_event = {
            "retry_blocked": "retry_blocked_count",
            "verify_blocked": "verify_blocked_count",
            "apply_blocked": "apply_blocked_count",
        }
        counter_field = counter_field_by_event.get(event_type)
        if counter_field is None:
            return False
        return self._increment_task_counter(state["agent_runtime"]["plan"], task_id, counter_field)

    def _sync_pending_action_ids(self, verification: dict, action_record: dict) -> None:
        """Reset verification posture after runtime actions mutate the workspace."""
        pending_action_ids = verification.get("pending_action_ids", [])
        if not isinstance(pending_action_ids, list):
            pending_action_ids = []
        pending_action_ids = [item for item in pending_action_ids if item != action_record["id"]]

        mutating_action = action_record["kind"].startswith("fs.")
        if action_record["kind"] == "exec.command":
            mutating_action = action_record.get("details", {}).get("side_effect") != "read_only"

        if action_record["status"] == "applied" and mutating_action:
            pending_action_ids.append(action_record["id"])
            verification["status"] = "idle"
            verification["checks"] = []
            verification["last_run_at"] = ""
        elif action_record["status"] == "rolled_back":
            if mutating_action and verification.get("status") == "passed":
                verification["status"] = "idle"
                verification["checks"] = []
                verification["last_run_at"] = ""
            elif verification.get("status") != "failed":
                verification["status"] = "idle" if pending_action_ids else verification.get("status", "idle")

        verification["pending_action_ids"] = pending_action_ids

    def _prune_retained_action_refs(self, agent_runtime: dict) -> None:
        """Drop derived action references that no longer exist in retained canonical history."""
        actions = agent_runtime.get("actions", [])
        live_action_ids = {
            action["id"]
            for action in actions
            if isinstance(action, dict) and isinstance(action.get("id"), str) and action["id"]
        }

        plan = agent_runtime.get("plan", {})
        if isinstance(plan, dict):
            tasks = plan.get("tasks", [])
            if isinstance(tasks, list):
                for task in tasks:
                    if not isinstance(task, dict):
                        continue
                    action_ids = task.get("action_ids")
                    if isinstance(action_ids, list):
                        task["action_ids"] = [
                            action_id
                            for action_id in action_ids
                            if isinstance(action_id, str) and action_id in live_action_ids
                        ]

        verification = agent_runtime.get("verification", {})
        if isinstance(verification, dict):
            pending_action_ids = verification.get("pending_action_ids")
            if isinstance(pending_action_ids, list):
                verification["pending_action_ids"] = [
                    action_id
                    for action_id in pending_action_ids
                    if isinstance(action_id, str) and action_id in live_action_ids
                ]
            checks = verification.get("checks", [])
            if isinstance(checks, list):
                for check in checks:
                    if not isinstance(check, dict):
                        continue
                    covered_action_ids = check.get("covered_action_ids")
                    if isinstance(covered_action_ids, list):
                        check["covered_action_ids"] = [
                            action_id
                            for action_id in covered_action_ids
                            if isinstance(action_id, str) and action_id in live_action_ids
                        ]

        audit = agent_runtime.get("audit", {})
        if isinstance(audit, dict):
            last_action_id = audit.get("last_action_id", "")
            if isinstance(last_action_id, str) and last_action_id and last_action_id not in live_action_ids:
                audit["last_action_id"] = ""

    def _mark_verified_tasks_done(self, plan: dict, actions: list[dict], pending_action_ids: set[str]) -> None:
        """Promote running tasks to done only after all attached actions verify successfully."""
        action_status_by_id = {
            action["id"]: action["status"]
            for action in actions
            if isinstance(action, dict) and isinstance(action.get("id"), str)
        }
        task_statuses = {
            task["id"]: task["status"]
            for task in plan.get("tasks", [])
            if isinstance(task, dict) and isinstance(task.get("id"), str)
        }

        for task in plan.get("tasks", []):
            if not isinstance(task, dict):
                continue
            action_ids = task.get("action_ids")
            depends_on = task.get("depends_on")
            if not isinstance(action_ids, list) or not isinstance(depends_on, list):
                continue
            if not action_ids:
                continue
            if any(task_statuses.get(dep) != "done" for dep in depends_on if isinstance(dep, str)):
                continue
            if any(action_id in pending_action_ids for action_id in action_ids if isinstance(action_id, str)):
                continue
            if any(action_status_by_id.get(action_id) != "applied" for action_id in action_ids if isinstance(action_id, str)):
                continue
            if task.get("status") not in {"failed", "done"}:
                task["status"] = "done"

    def _working_set_bucket(self, working_set: list[str]) -> str:
        """Return a coarse scope bucket for learning successful task patterns."""
        size = len([path for path in working_set if isinstance(path, str) and path])
        if size <= 0:
            return "undefined"
        if size == 1:
            return "single"
        if size <= 3:
            return "small"
        return "wide"

    def _derive_success_records(
        self,
        previous_plan: dict,
        current_plan: dict,
        verification_record: dict,
        actions: list[dict],
    ) -> list[dict]:
        """Return verified task successes safe enough to reinforce later decisions."""
        if verification_record.get("status") != "passed":
            return []

        covered_action_ids: set[str] = set()
        for check in verification_record.get("checks", []):
            if not isinstance(check, dict):
                continue
            for action_id in check.get("covered_action_ids", []):
                if isinstance(action_id, str) and action_id:
                    covered_action_ids.add(action_id)
        if not covered_action_ids:
            return []

        previous_status_by_id = {
            task["id"]: task.get("status", "")
            for task in previous_plan.get("tasks", [])
            if isinstance(task, dict) and isinstance(task.get("id"), str)
        }
        action_by_id = {
            action["id"]: action
            for action in actions
            if isinstance(action, dict) and isinstance(action.get("id"), str)
        }
        success_records: list[dict] = []
        for task in current_plan.get("tasks", []):
            if not isinstance(task, dict):
                continue
            task_id = task.get("id", "")
            if not isinstance(task_id, str) or not task_id:
                continue
            if task.get("status") != "done" or previous_status_by_id.get(task_id) == "done":
                continue

            action_ids = [
                action_id
                for action_id in task.get("action_ids", [])
                if isinstance(action_id, str) and action_id
            ]
            if not action_ids or not covered_action_ids.intersection(action_ids):
                continue

            task_actions = [action_by_id[action_id] for action_id in action_ids if action_id in action_by_id]
            if not task_actions:
                continue
            if any(action.get("status") != "applied" for action in task_actions):
                continue

            if any(
                isinstance(task.get(field), int) and task.get(field, 0) > 0
                for field in ("retry_blocked_count", "apply_blocked_count", "verify_blocked_count")
            ):
                continue

            action_kinds: list[str] = []
            for action in task_actions:
                action_kind = action.get("kind")
                if isinstance(action_kind, str) and action_kind and action_kind not in action_kinds:
                    action_kinds.append(action_kind)

            acceptance_defined = bool(
                [
                    criterion
                    for criterion in task.get("acceptance_criteria", [])
                    if isinstance(criterion, str) and criterion
                ]
            )
            working_set = [
                path
                for path in task.get("working_set", [])
                if isinstance(path, str) and path
            ]
            working_set_bucket = self._working_set_bucket(working_set)
            has_sensitive_actions = any(
                action_kind in {"exec.command", "fs.delete_soft", "fs.move", "fs.write_patch"}
                for action_kind in action_kinds
            )
            approval_count = len([action for action in task_actions if action.get("approval_id")])
            cost = (
                len(task_actions) * 10
                + approval_count * 6
                + (6 if has_sensitive_actions else 0)
            )

            reason_parts = ["verify passed on pending workspace delta"]
            if acceptance_defined:
                reason_parts.append("explicit acceptance criteria")
            if working_set_bucket in {"single", "small"}:
                reason_parts.append("bounded working set")
            if len(task_actions) <= 2:
                reason_parts.append("low action count")
            if approval_count == 0:
                reason_parts.append("no approval friction")
            if not has_sensitive_actions:
                reason_parts.append("low-risk action mix")
            reason = "; ".join(reason_parts[:4])
            result = (
                f"task {task_id} promoted to done after verification consumed "
                f"{len(covered_action_ids.intersection(action_ids))} action(s)"
            )
            context = (
                f"title={task.get('title') or task_id}; "
                f"working_set={working_set_bucket}; "
                f"acceptance={'defined' if acceptance_defined else 'missing'}"
            )
            pattern_signature = (
                f"ws={working_set_bucket}"
                f"|acceptance={'defined' if acceptance_defined else 'missing'}"
                f"|actions={'+'.join(action_kinds) or 'none'}"
                f"|sensitive={'yes' if has_sensitive_actions else 'no'}"
            )
            success_records.append(
                {
                    "task_id": task_id,
                    "context": context,
                    "action_kinds": action_kinds,
                    "result": result,
                    "cost": cost,
                    "reason": reason,
                    "working_set_bucket": working_set_bucket,
                    "acceptance_defined": acceptance_defined,
                    "has_sensitive_actions": has_sensitive_actions,
                    "pattern_signature": pattern_signature,
                    "recorded_at": verification_record.get("last_run_at", ""),
                }
            )

        return success_records

    def _verification_covers_required_scope(self, verification_record: dict) -> bool:
        """Return whether a verification record executed the full required command set successfully."""
        required_command_ids = {
            command_id
            for command_id in verification_record.get("required_command_ids", [])
            if isinstance(command_id, str) and command_id
        }
        if not required_command_ids:
            return True
        executed_command_ids = {
            check["command_id"]
            for check in iter_command_checks(verification_record)
            if check.get("status") == "passed"
            and isinstance(check.get("command_id"), str)
            and check["command_id"]
        }
        return required_command_ids.issubset(executed_command_ids)

    def _merge_verification_result(
        self,
        current_verification: dict,
        verification_record: dict,
        plan: dict,
        actions: list[dict],
    ) -> dict:
        """Merge a verification run with pending-action bookkeeping and task promotion."""
        merged = deepcopy(current_verification)
        merged.update(verification_record)
        pending_action_ids = merged.get("pending_action_ids", current_verification.get("pending_action_ids", []))
        if not isinstance(pending_action_ids, list):
            pending_action_ids = []
        covered_action_ids: set[str] = set()
        for check in merged.get("checks", []):
            if not isinstance(check, dict):
                continue
            for action_id in check.get("covered_action_ids", []):
                if isinstance(action_id, str):
                    covered_action_ids.add(action_id)
        failed_attempt_count = merged.get("failed_attempt_count", current_verification.get("failed_attempt_count", 0))
        if not isinstance(failed_attempt_count, int) or failed_attempt_count < 0:
            failed_attempt_count = 0
        if merged.get("status") == "failed":
            failed_attempt_count += 1
        full_required_coverage = self._verification_covers_required_scope(merged)
        if merged.get("status") == "passed" and full_required_coverage:
            pending_action_ids = [action_id for action_id in pending_action_ids if action_id not in covered_action_ids]
            self._mark_verified_tasks_done(plan, actions, set(pending_action_ids))
        elif merged.get("status") == "passed":
            current_status = current_verification.get("status", "idle")
            merged["status"] = "failed" if current_status == "failed" else "idle"
        merged["failed_attempt_count"] = failed_attempt_count
        merged["pending_action_ids"] = pending_action_ids
        return merged

    def _refresh_plan_progress(self, plan: dict) -> None:
        """Recompute task readiness and overall plan status from current task states."""
        tasks = plan.get("tasks", [])
        if not isinstance(tasks, list) or not tasks:
            plan["status"] = "idle"
            plan["current_task_id"] = ""
            return

        task_statuses = {
            task["id"]: task["status"]
            for task in tasks
            if isinstance(task, dict) and isinstance(task.get("id"), str)
        }
        for task in tasks:
            if not isinstance(task, dict):
                continue
            depends_on = task.get("depends_on")
            if not isinstance(depends_on, list):
                continue
            if task.get("status") in {"done", "failed", "running"}:
                continue
            dependencies_complete = all(task_statuses.get(dep) == "done" for dep in depends_on if isinstance(dep, str))
            task["status"] = "ready" if dependencies_complete else "blocked"

        running = [
            task["id"]
            for task in tasks
            if isinstance(task, dict) and task.get("status") == "running" and isinstance(task.get("id"), str)
        ]
        ready = [
            task["id"]
            for task in tasks
            if isinstance(task, dict) and task.get("status") == "ready" and isinstance(task.get("id"), str)
        ]
        blocked = [
            task["id"]
            for task in tasks
            if isinstance(task, dict) and task.get("status") == "blocked" and isinstance(task.get("id"), str)
        ]
        done = [
            task["id"]
            for task in tasks
            if isinstance(task, dict) and task.get("status") == "done" and isinstance(task.get("id"), str)
        ]

        if running:
            plan["status"] = "running"
            plan["current_task_id"] = running[0]
        elif len(done) == len([task for task in tasks if isinstance(task, dict)]):
            plan["status"] = "completed"
            plan["current_task_id"] = ""
        elif ready:
            plan["status"] = "ready"
            plan["current_task_id"] = ready[0]
        elif blocked:
            plan["status"] = "blocked"
            plan["current_task_id"] = ""
        else:
            plan["status"] = "blocked"
            plan["current_task_id"] = ""

    def _refresh_agent_runtime_progress(
        self,
        agent_runtime: dict,
        *,
        recent_events: tuple[dict, ...] = (),
    ) -> dict:
        """Refresh plan progress and select the best executable task from current evidence."""
        plan = agent_runtime["plan"]
        self._refresh_plan_progress(plan)
        selection = choose_next_task(agent_runtime, recent_events)
        if plan["status"] in {"ready", "running"}:
            plan["current_task_id"] = selection["task_id"]
        else:
            plan["current_task_id"] = ""
        return selection

    def _build_task_selection_event_spec(
        self,
        previous_task_id: str,
        selection: dict,
        *,
        parent_event_index: int | None = None,
    ) -> dict | None:
        """Build the task-selection trace event when the selected task changed."""
        selected_task_id = selection.get("task_id", "")
        if not isinstance(selected_task_id, str):
            return None
        if selected_task_id == previous_task_id:
            return None
        evidence_event_ids = self._normalize_unique_strings(selection.get("evidence_event_ids", []))[:6]
        return {
            "event_type": "task_selected",
            "phase": "decision",
            "step": "task_selected",
            "parent_event_index": parent_event_index,
            "payload": {
                "selected_task_id": selected_task_id,
                "priority": selection.get("priority", 0),
                "impact": selection.get("impact", 0),
                "cost": selection.get("cost", 0),
                "risk": selection.get("risk", 0),
                "real_cost": selection.get("real_cost", 0),
                "reason": selection.get("reason", ""),
                "evidence": selection.get("evidence", []),
                "evidence_event_ids": evidence_event_ids,
                "rejected_alternatives": selection.get("rejected_alternatives", []),
            },
        }

    def _safe_recent_events(self, limit: int = 20) -> tuple[dict, ...]:
        """Read recent events without failing mutating state transitions."""
        try:
            return self.read_recent_events(limit=limit)
        except StateStoreError:
            return ()

    def _assert_sources_match_prepared(self, sources: list[dict]) -> None:
        """Reject registration when a source changed between hashing and persistence."""
        for item in sources:
            resolved_path, _ = self._resolve_registered_path(item["path"])
            current_hash = self.compute_sha256(resolved_path)
            if current_hash != item["sha256"]:
                raise StateStoreError(f"source changed during registration: {item['path']}")

    def _run_after_temporary_session_close(self, operation: Callable[[], _T]) -> tuple[_T, bool]:
        """Close the local session for a mutating operation and restore it if persistence fails."""
        preserved_state = self.load_state()
        preserved_session = self._read_optional_file_bytes(self.session_path)
        preserved_claim = None
        preserved_live_proof = None
        session_data, session_errors = self._read_session_file()
        if not session_errors and session_data is not None:
            claim_id = session_data.get("owner_claim_id", "")
            if isinstance(claim_id, str) and claim_id:
                preserved_claim = self._capture_session_claim_snapshot(
                    claim_id,
                    label="external session claim",
                )
            preserved_live_proof_id = self._active_session_live_proof_id(session_data)
            if preserved_live_proof_id is not None:
                preserved_live_proof = self._capture_session_live_proof_snapshot(
                    preserved_live_proof_id,
                    label="external session live proof",
                )
        session_closed = self.close_session()
        try:
            result = operation()
        except Exception as exc:
            if session_closed:
                try:
                    self.save_state(preserved_state, expected_revision=preserved_state["revision"])
                    if preserved_claim is not None:
                        self._restore_session_claim_snapshot(preserved_claim)
                    if preserved_live_proof is not None:
                        self._restore_session_live_proof_snapshot(preserved_live_proof)
                    if preserved_session is not None:
                        self._write_bytes_atomic(self.session_path, preserved_session)
                except StateStoreError as restore_exc:
                    raise StateStoreError(
                        f"operation failed and session restore also failed: {self.session_path}"
                    ) from restore_exc
            raise
        return result, session_closed

    def _read_optional_file_bytes(self, path: Path) -> bytes | None:
        """Return the exact file bytes when the file exists, otherwise `None`."""
        if not path.exists():
            return None

        try:
            return path.read_bytes()
        except OSError as exc:
            raise StateStoreError(f"failed to read file: {path}") from exc

    def _write_bytes_atomic(self, path: Path, payload: bytes) -> None:
        """Persist raw bytes via write-then-replace."""
        tmp_path = path.with_suffix(f"{path.suffix}.tmp")

        try:
            with tmp_path.open("wb") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp_path, path)
        except OSError as exc:
            raise StateStoreError(f"failed to write file: {path}") from exc
        finally:
            if tmp_path.exists():
                tmp_path.unlink()

    def capture_verify_authority_guard(self) -> list[dict]:
        """Capture live runtime authority files that one verify command must preserve."""
        snapshots = [
            {"label": "runtime.lock", "path": self.lock_path, "bytes": self._read_optional_file_bytes(self.lock_path)},
            {"label": "state.json", "path": self.state_path, "bytes": self._read_optional_file_bytes(self.state_path)},
            {"label": "events.jsonl", "path": self.events_path, "bytes": self._read_optional_file_bytes(self.events_path)},
            {"label": "session.local.json", "path": self.session_path, "bytes": self._read_optional_file_bytes(self.session_path)},
        ]

        session_data, session_errors = self._read_session_file()
        if not session_errors and session_data is not None:
            claim_id = session_data.get("owner_claim_id", "")
            if isinstance(claim_id, str) and claim_id:
                snapshot = self._capture_session_claim_snapshot(
                    claim_id,
                    label="external session claim",
                )
                if snapshot is not None:
                    snapshots.append(snapshot)
            live_proof_id = self._active_session_live_proof_id(session_data)
            if live_proof_id is not None:
                snapshot = self._capture_session_live_proof_snapshot(
                    live_proof_id,
                    label="external session live proof",
                )
                if snapshot is not None:
                    snapshots.append(snapshot)
        return snapshots

    def restore_verify_authority_guard_if_changed(self, snapshots: list[dict]) -> str:
        """Restore guarded live runtime authority files if verify tampered with them persistently."""
        changed_labels: list[str] = []
        for snapshot in snapshots:
            if not isinstance(snapshot, dict):
                continue
            claim_id = snapshot.get("claim_id")
            if isinstance(claim_id, str) and claim_id:
                before_bytes = snapshot.get("bytes")
                backend = snapshot.get("backend")
                if not isinstance(backend, str) or not backend:
                    raise StateStoreError("session claim guard snapshot is missing backend")
                current_bytes = self._read_optional_session_claim_bytes(claim_id, backend=backend)
                if current_bytes == before_bytes:
                    continue
                changed_labels.append(str(snapshot.get("label", "external session claim")))
                self._restore_session_claim_snapshot(snapshot)
                continue
            proof_id = snapshot.get("proof_id")
            if isinstance(proof_id, str) and proof_id:
                before_bytes = snapshot.get("bytes")
                backend = snapshot.get("backend")
                if not isinstance(backend, str) or not backend:
                    raise StateStoreError("session live-proof guard snapshot is missing backend")
                current_bytes = self._read_optional_session_live_proof_bytes(proof_id, backend=backend)
                if current_bytes == before_bytes:
                    continue
                changed_labels.append(str(snapshot.get("label", "external session live proof")))
                self._restore_session_live_proof_snapshot(snapshot)
                continue
            path = snapshot.get("path")
            if not isinstance(path, Path):
                continue
            before_bytes = snapshot.get("bytes")
            current_bytes = self._read_optional_file_bytes(path)
            if current_bytes == before_bytes:
                continue
            changed_labels.append(str(snapshot.get("label", path.name)))
            if before_bytes is None:
                if path.exists():
                    try:
                        path.unlink()
                    except OSError as exc:
                        raise StateStoreError(f"failed to remove guarded runtime file: {path}") from exc
                continue
            if not isinstance(before_bytes, bytes):
                raise StateStoreError(f"guarded runtime snapshot for {path} must contain raw bytes or None")
            self._write_bytes_atomic(path, before_bytes)
        if not changed_labels:
            return ""
        return "verify command mutated live runtime authority: " + ", ".join(changed_labels)

    def _write_json_atomic(self, path: Path, data: dict) -> None:
        """Persist a JSON document via write-then-replace."""
        payload = (json.dumps(data, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
        self._write_bytes_atomic(path, payload)

    def _trace_durability_mode(self) -> str:
        """Return the configured trace durability mode."""
        raw = os.environ.get(TRACE_DURABILITY_ENV_VAR, TRACE_DURABILITY_BALANCED)
        normalized = raw.strip().lower() if isinstance(raw, str) else TRACE_DURABILITY_BALANCED
        if normalized in TRACE_DURABILITY_MODES:
            return normalized
        return TRACE_DURABILITY_BALANCED

    def _reset_trace_thread(self, audit: dict, *, prefix: str) -> None:
        """Start a fresh monotonic event sequence for a new logical trace thread."""
        audit["trace_thread_id"] = self._next_trace_thread_id(prefix)
        audit["next_event_id"] = 1
        audit["trace_status"] = "healthy"
        audit["trace_integrity"] = "reliable"
        audit["last_trace_error_at"] = ""
        audit["last_trace_error"] = ""

    def _next_trace_thread_id(self, prefix: str) -> str:
        """Build one compact trace-thread id."""
        cleaned_prefix = prefix.strip() if isinstance(prefix, str) and prefix.strip() else "trace"
        return f"{cleaned_prefix}-{uuid4().hex[:8]}"

    def _normalize_runtime_event_input(self, event: dict) -> dict:
        """Normalize one public runtime-event request into the shared event spec shape."""
        event_type = event.get("event_type", event.get("event", ""))
        phase = event.get("phase", "")
        step = event.get("step", "")
        if not isinstance(event_type, str) or not event_type.strip():
            raise StateStoreError("runtime event must include event_type")
        if not isinstance(phase, str) or not phase.strip():
            raise StateStoreError("runtime event must include phase")
        if not isinstance(step, str) or not step.strip():
            raise StateStoreError("runtime event must include step")
        parent_event_id = event.get("parent_event_id", "")
        if not isinstance(parent_event_id, str):
            raise StateStoreError("runtime event parent_event_id must be a string")
        payload = {}
        for key, value in event.items():
            if key in {"event", "event_type", "phase", "step", "parent_event_id"}:
                continue
            payload[key] = value
        return {
            "event_type": event_type.strip(),
            "phase": phase.strip(),
            "step": step.strip(),
            "parent_event_id": parent_event_id.strip(),
            "payload": payload,
        }

    def _record_trace_only_events(
        self,
        state: dict,
        event_specs: list[dict],
        *,
        expected_revision: int | None = None,
    ) -> None:
        """Reserve ids, persist observability metadata, and append read-only trace events."""
        if not event_specs:
            return
        prepared_events = self._prepare_trace_events(state, event_specs)
        self.save_state(
            state,
            expected_revision=state["revision"] if expected_revision is None else expected_revision,
        )
        self._commit_trace_events(state, prepared_events)

    def _prepare_trace_events(self, state: dict, event_specs: list[dict]) -> list[dict]:
        """Validate one batch of events and reserve monotonic ids in canonical audit metadata."""
        prepared: list[dict] = []
        audit = state["agent_runtime"]["audit"]
        if not isinstance(audit.get("trace_thread_id"), str) or not audit.get("trace_thread_id", "").strip():
            self._reset_trace_thread(audit, prefix="trace")
        next_event_id = audit.get("next_event_id", 1)
        if not isinstance(next_event_id, int) or next_event_id < 1:
            next_event_id = 1
            audit["next_event_id"] = 1

        for spec in event_specs:
            if not isinstance(spec, dict):
                raise StateStoreError("trace event spec must be an object")
            event_type = spec.get("event_type", "")
            phase = spec.get("phase", "")
            step = spec.get("step", "")
            payload = spec.get("payload", {})
            parent_event_id = spec.get("parent_event_id", "")
            parent_event_index = spec.get("parent_event_index")
            if not isinstance(event_type, str) or not event_type.strip():
                raise StateStoreError("trace event spec must include event_type")
            if not isinstance(phase, str) or not phase.strip():
                raise StateStoreError("trace event spec must include phase")
            if not isinstance(step, str) or not step.strip():
                raise StateStoreError("trace event spec must include step")
            if not isinstance(payload, dict):
                raise StateStoreError("trace event payload must be an object")
            if not isinstance(parent_event_id, str):
                raise StateStoreError("trace event parent_event_id must be a string")
            if parent_event_index is not None:
                if not isinstance(parent_event_index, int) or parent_event_index < 0 or parent_event_index >= len(prepared):
                    raise StateStoreError("trace event parent_event_index must reference an earlier event in the same batch")
                parent_event_id = prepared[parent_event_index]["event_id"]
            prepared.append(
                self._build_trace_event(
                    state,
                    event_type=event_type.strip(),
                    phase=phase.strip(),
                    step=step.strip(),
                    payload=payload,
                    parent_event_id=parent_event_id.strip(),
                    event_number=next_event_id,
                )
            )
            next_event_id += 1
        audit["next_event_id"] = next_event_id
        return prepared

    def _build_trace_event(
        self,
        state: dict,
        *,
        event_type: str,
        phase: str,
        step: str,
        payload: dict,
        parent_event_id: str,
        event_number: int,
    ) -> dict:
        """Build one validated persisted event envelope."""
        reserved_keys = {
            "event_id",
            "event",
            "event_type",
            "phase",
            "step",
            "parent_event_id",
            "recorded_at",
            "revision",
            "trace_thread_id",
        }
        overlap = sorted(key for key in payload if key in reserved_keys)
        if overlap:
            raise StateStoreError(f"trace event payload cannot override reserved keys: {', '.join(overlap)}")
        thread_id = state["agent_runtime"]["audit"]["trace_thread_id"]
        return {
            "event_id": f"{thread_id}:{event_number:06d}",
            "trace_thread_id": thread_id,
            "recorded_at": self._timestamp_now(),
            "revision": state["revision"],
            "event": event_type,
            "event_type": event_type,
            "phase": phase,
            "step": step,
            "parent_event_id": parent_event_id,
            **payload,
        }

    def _commit_trace_events(self, state: dict, events: list[dict]) -> None:
        """Append one prepared event batch and persist trace-plane health if needed."""
        audit = state["agent_runtime"]["audit"]
        append_error: OSError | None = None
        failed_event_id = ""
        for event in events:
            try:
                self._write_trace_event_line(event)
            except OSError as exc:
                append_error = exc
                failed_event_id = event["event_id"]
                break

        if append_error is not None:
            self._mark_trace_degraded(state, failed_event_id, append_error)
            self._persist_trace_audit(state)
            return

        if audit.get("trace_status") == "degraded":
            audit["trace_status"] = "healthy"
            audit["last_trace_error_at"] = ""
            audit["last_trace_error"] = ""
            self._persist_trace_audit(state)

    def _mark_trace_degraded(self, state: dict, failed_event_id: str, exc: OSError) -> None:
        """Mark the trace plane degraded without changing authoritative runtime facts."""
        audit = state["agent_runtime"]["audit"]
        audit["trace_status"] = "degraded"
        audit["trace_integrity"] = "partial"
        audit["last_trace_error_at"] = self._timestamp_now()
        audit["last_trace_error"] = f"{failed_event_id}: {exc}"

    def _persist_trace_audit(self, state: dict) -> None:
        """Persist observability-only audit metadata without changing runtime revision."""
        self.save_state(state, expected_revision=state["revision"])

    def _write_trace_event_line(self, event: dict) -> None:
        """Append one validated trace event using the configured durability policy."""
        self._validate_trace_event_record(event)
        payload = json.dumps(event, ensure_ascii=False)
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        with self.events_path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(payload)
            handle.write("\n")
            handle.flush()
            if self._trace_durability_mode() == TRACE_DURABILITY_STRICT:
                os.fsync(handle.fileno())

    def _validate_trace_event_record(self, event: object) -> None:
        """Validate the final persisted trace envelope before it reaches the log."""
        if not isinstance(event, dict):
            raise StateStoreError("trace event must be an object")
        required_string_fields = (
            "event_id",
            "trace_thread_id",
            "recorded_at",
            "event",
            "event_type",
            "phase",
            "step",
            "parent_event_id",
        )
        for field in required_string_fields:
            value = event.get(field)
            if not isinstance(value, str):
                raise StateStoreError(f"trace event {field} must be a string")
            if field != "parent_event_id" and not value.strip():
                raise StateStoreError(f"trace event {field} must be a non-empty string")
        if event["event"] != event["event_type"]:
            raise StateStoreError("trace event event and event_type must match")
        revision = event.get("revision")
        if not isinstance(revision, int) or revision < 0:
            raise StateStoreError("trace event revision must be a non-negative integer")
        if self._parse_trace_event_number(event["event_id"], event["trace_thread_id"]) is None:
            raise StateStoreError("trace event_id must be monotonic within the trace thread namespace")

    def _parse_trace_event_number(self, event_id: object, thread_id: str) -> int | None:
        """Parse one event number from a namespaced trace event id."""
        if not isinstance(event_id, str) or not event_id.startswith(f"{thread_id}:"):
            return None
        suffix = event_id.split(":", 1)[1]
        if not suffix.isdigit():
            return None
        return int(suffix)

    def _update_agent_audit(self, state: dict, event_type: str, action_id: str) -> None:
        """Refresh compact audit metadata alongside canonical state mutations."""
        state["agent_runtime"]["audit"]["last_event_at"] = self._timestamp_now()
        state["agent_runtime"]["audit"]["last_event_type"] = event_type
        state["agent_runtime"]["audit"]["last_action_id"] = action_id

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

    def _file_signature(self, path: Path) -> tuple[int, int]:
        """Capture a cheap signature used to detect in-place file changes during reads."""
        try:
            stat_result = path.stat()
        except OSError as exc:
            raise StateStoreError(f"failed to read source file: {path}") from exc
        return stat_result.st_size, stat_result.st_mtime_ns

    def _register_process_runtime_lock(self) -> None:
        """Mark the runtime lock as held somewhere in the current process."""
        key = str(self.lock_path)
        with StateStore._process_runtime_lock_guard:
            StateStore._process_runtime_lock_counts[key] = StateStore._process_runtime_lock_counts.get(key, 0) + 1

    def _unregister_process_runtime_lock(self) -> None:
        """Clear the current-process marker for this runtime lock."""
        key = str(self.lock_path)
        with StateStore._process_runtime_lock_guard:
            count = StateStore._process_runtime_lock_counts.get(key, 0)
            if count <= 1:
                StateStore._process_runtime_lock_counts.pop(key, None)
            else:
                StateStore._process_runtime_lock_counts[key] = count - 1

    def _process_runtime_lock_is_held(self) -> bool:
        """Return whether any StateStore in this process still owns the lock."""
        key = str(self.lock_path)
        with StateStore._process_runtime_lock_guard:
            return StateStore._process_runtime_lock_counts.get(key, 0) > 0

    def _read_runtime_lock_owner_pid(self) -> int | None:
        """Return the lock-owner pid when the lock file is readable and valid."""
        try:
            raw = self.lock_path.read_text(encoding="ascii").strip()
        except OSError:
            return None

        if not raw.isdigit():
            return None

        owner_pid = int(raw)
        return owner_pid if owner_pid > 0 else None

    def _pid_is_running(self, pid: int) -> bool:
        """Return whether the runtime-lock owner still appears to be active."""
        if pid <= 0:
            return False

        if pid == os.getpid():
            return self._process_runtime_lock_is_held()

        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        except OSError as exc:
            if exc.errno == errno.ESRCH:
                return False
            if getattr(exc, "winerror", None) == 87:
                return False
            return True
        return True

    def _try_remove_runtime_lock_file(self) -> bool:
        """Best-effort removal for the lock file after work already completed."""
        for attempt in range(RUNTIME_LOCK_RELEASE_RETRY_LIMIT):
            try:
                if self.lock_path.exists():
                    self.lock_path.unlink()
                return True
            except FileNotFoundError:
                return True
            except OSError:
                if attempt == RUNTIME_LOCK_RELEASE_RETRY_LIMIT - 1:
                    return False
                time.sleep(RUNTIME_LOCK_POLL_SECONDS)
        return False

    def _try_recover_stale_runtime_lock(self) -> bool:
        """Remove a stale runtime lock left behind by an inactive owner."""
        owner_pid = self._read_runtime_lock_owner_pid()
        if owner_pid is None:
            return False

        if self._pid_is_running(owner_pid):
            return False

        return self._try_remove_runtime_lock_file()

    def _release_runtime_lock(self) -> None:
        """Release lock ownership without reclassifying completed work as failure."""
        fd = self._lock_fd
        self._lock_depth = 0
        self._lock_fd = None

        if fd is not None:
            try:
                os.close(fd)
            except OSError:
                pass

        self._unregister_process_runtime_lock()
        self._try_remove_runtime_lock_file()

    @contextmanager
    def runtime_lock(self):
        """Serialize runtime mutations across instances to avoid lost updates."""
        if self._lock_depth > 0:
            self._lock_depth += 1
            try:
                yield
            finally:
                self._lock_depth -= 1
            return

        self.cerebro_dir.mkdir(parents=True, exist_ok=True)
        start = time.monotonic()
        while True:
            try:
                fd = os.open(self.lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.write(fd, str(os.getpid()).encode("ascii"))
                self._lock_fd = fd
                self._lock_depth = 1
                self._register_process_runtime_lock()
                break
            except FileExistsError:
                if self._try_recover_stale_runtime_lock():
                    continue
                if time.monotonic() - start >= RUNTIME_LOCK_TIMEOUT_SECONDS:
                    raise StateStoreError(
                        "timed out waiting for runtime lock: "
                        f"{self.lock_path}; another Cerebro process may still be running or a previous run may have left a stale lock"
                    )
                time.sleep(RUNTIME_LOCK_POLL_SECONDS)

        try:
            yield
        finally:
            self._release_runtime_lock()

    # Session artifact extraction wrappers.
    # These late-bound method redefinitions keep the existing StateStore
    # surface stable while delegating the session artifact/authority cluster to
    # StateSessionArtifactsService.

    def _hash_session_token(self, token: str) -> str:
        return self._session_artifacts.hash_session_token(token)

    def _hash_session_live_proof(self, proof: str) -> str:
        return self._session_artifacts.hash_session_live_proof(proof)

    def _resolve_session_claims_dir(self) -> Path:
        return self._session_artifacts.resolve_session_claims_dir()

    def _resolve_session_live_proofs_dir(self) -> Path:
        return self._session_artifacts.resolve_session_live_proofs_dir()

    def _session_claim_path(self, claim_id: str) -> Path:
        return self._session_artifacts.session_claim_path(claim_id)

    def _session_live_proof_path(self, proof_id: str) -> Path:
        return self._session_artifacts.session_live_proof_path(proof_id)

    def _session_claim_backend(self) -> str:
        return self._session_artifacts.session_claim_backend()

    def _session_claim_target_name(self, claim_id: str) -> str:
        return self._session_artifacts.session_claim_target_name(claim_id)

    def _legacy_session_claim_target_name(self, claim_id: str) -> str:
        return self._session_artifacts.legacy_session_claim_target_name(claim_id)

    def _session_claim_location(self, claim_id: str, *, backend: str | None = None) -> str:
        return self._session_artifacts.session_claim_location(claim_id, backend=backend)

    def _session_live_proof_backend(self) -> str:
        return self._session_artifacts.session_live_proof_backend()

    def _session_live_proof_target_name(self, proof_id: str) -> str:
        return self._session_artifacts.session_live_proof_target_name(proof_id)

    def _legacy_session_live_proof_target_name(self, proof_id: str) -> str:
        return self._session_artifacts.legacy_session_live_proof_target_name(proof_id)

    def _session_live_proof_location(self, proof_id: str, *, backend: str | None = None) -> str:
        return self._session_artifacts.session_live_proof_location(proof_id, backend=backend)

    def _hash_root_identity(self) -> str:
        return self._session_artifacts.hash_root_identity()

    def _hash_session_owner_binding(self, binding: str) -> str:
        return self._session_artifacts.hash_session_owner_binding(binding)

    def _current_session_owner_binding(self) -> str:
        return self._session_artifacts.current_session_owner_binding()

    def _process_binding_identity(self, pid: int) -> str:
        return self._session_artifacts.process_binding_identity(pid)

    def _proc_process_binding_identity(self, pid: int) -> str:
        return self._session_artifacts.proc_process_binding_identity(pid)

    def _windows_process_binding_identity(self, pid: int) -> str:
        return self._session_artifacts.windows_process_binding_identity(pid)

    def _write_session_claim(self, claim_data: dict) -> None:
        self._session_artifacts.write_session_claim(claim_data)

    def _write_session_live_proof(self, proof_data: dict) -> None:
        self._session_artifacts.write_session_live_proof(proof_data)

    def _read_optional_session_claim_bytes(self, claim_id: object, *, backend: str | None = None) -> bytes | None:
        return self._session_artifacts.read_optional_session_claim_bytes(claim_id, backend=backend)

    def _write_session_claim_bytes(self, claim_id: object, payload: bytes, *, backend: str | None = None) -> None:
        self._session_artifacts.write_session_claim_bytes(claim_id, payload, backend=backend)

    def _read_optional_session_live_proof_bytes(self, proof_id: object, *, backend: str | None = None) -> bytes | None:
        return self._session_artifacts.read_optional_session_live_proof_bytes(proof_id, backend=backend)

    def _write_session_live_proof_bytes(self, proof_id: object, payload: bytes, *, backend: str | None = None) -> None:
        self._session_artifacts.write_session_live_proof_bytes(proof_id, payload, backend=backend)

    def _read_session_claim_file(self, claim_id: object) -> tuple[dict | None, list[dict]]:
        return self._session_artifacts.read_session_claim_file(claim_id)

    def _read_validated_session_claim(self, session_data: dict) -> tuple[dict | None, list[dict]]:
        return self._session_artifacts.read_validated_session_claim(session_data)

    def _remove_session_claim(self, claim_id: object, *, backend: str | None = None) -> None:
        self._session_artifacts.remove_session_claim(claim_id, backend=backend)

    def _capture_session_claim_snapshot(self, claim_id: object, *, label: str) -> dict | None:
        return self._session_artifacts.capture_session_claim_snapshot(claim_id, label=label)

    def _restore_session_claim_snapshot(self, snapshot: dict) -> None:
        self._session_artifacts.restore_session_claim_snapshot(snapshot)

    def _read_session_live_proof_file(self, proof_id: object) -> tuple[dict | None, list[dict]]:
        return self._session_artifacts.read_session_live_proof_file(proof_id)

    def _read_validated_session_live_proof(self, session_data: dict, claim_data: dict) -> tuple[dict | None, list[dict]]:
        return self._session_artifacts.read_validated_session_live_proof(session_data, claim_data)

    def _remove_session_live_proof(self, proof_id: object, *, backend: str | None = None) -> None:
        self._session_artifacts.remove_session_live_proof(proof_id, backend=backend)

    def _remove_session_live_proof_by_path(self, proof_path: Path) -> None:
        self._session_artifacts.remove_session_live_proof_by_path(proof_path)

    def _is_valid_sha256_string(self, value: str) -> bool:
        return self._session_artifacts.is_valid_sha256_string(value)

    def _read_session_file(self) -> tuple[dict | None, list[dict]]:
        return self._session_artifacts.read_session_file()

    def _active_session_live_proof_id(self, session_data: dict) -> str | None:
        return self._session_artifacts.active_session_live_proof_id(session_data)

    def _capture_session_live_proof_snapshot(self, proof_id: object, *, label: str) -> dict | None:
        return self._session_artifacts.capture_session_live_proof_snapshot(proof_id, label=label)

    def _restore_session_live_proof_snapshot(self, snapshot: dict) -> None:
        self._session_artifacts.restore_session_live_proof_snapshot(snapshot)
