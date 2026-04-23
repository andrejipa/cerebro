"""Retention planning and archive-journal helpers behind the StateStore facade.

StateStore continues to own runtime locking, revision checks, state
load/save, and trace ordering. This service owns only the retention-specific
policy, planning, and pending-archive finalization helpers.
"""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from typing import Callable, Iterable


RETENTION_NON_CONSOLIDATION_EVENT_LIMIT = 20_000
RETENTION_VERIFICATION_GROUP_LIMIT = 20
RETENTION_ACTION_GROUP_LIMIT = 64


class StateRetentionService:
    """Retention-specific helpers extracted from ``StateStore``."""

    def __init__(
        self,
        *,
        cerebro_dir: Path,
        events_path: Path,
        artifacts_dir: Path,
        trash_dir: Path,
        error_cls: type[Exception],
        parse_parallel_approach_consolidation_line: Callable[[bytes], dict | None],
        parse_event_log_event_type: Callable[[bytes], str | None],
        iter_live_runtime_artifact_refs: Callable[[dict], Iterable[tuple[str, str, object]]],
        resolve_runtime_artifact_ref: Callable[[str], Path],
        write_json_atomic: Callable[[Path, object], None],
        commit_trace_events: Callable[[dict, list[dict]], None],
    ) -> None:
        self.cerebro_dir = Path(cerebro_dir)
        self.events_path = Path(events_path)
        self.artifacts_dir = Path(artifacts_dir)
        self.trash_dir = Path(trash_dir)
        self._error_cls = error_cls
        self._parse_parallel_approach_consolidation_line = parse_parallel_approach_consolidation_line
        self._parse_event_log_event_type = parse_event_log_event_type
        self._iter_live_runtime_artifact_refs = iter_live_runtime_artifact_refs
        self._resolve_runtime_artifact_ref = resolve_runtime_artifact_ref
        self._write_json_atomic = write_json_atomic
        self._commit_trace_events = commit_trace_events

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

    def load_pending_retention_archive(self) -> tuple[Path, dict] | None:
        """Return one pending retention archive journal if the previous apply did not finish."""
        retention_root = self.trash_dir / "retention"
        if not retention_root.exists():
            return None
        pending_paths = sorted(retention_root.glob("retention-*/manifest.pending.json"))
        if not pending_paths:
            return None
        if len(pending_paths) > 1:
            raise self._error_cls("multiple pending retention journals require manual inspection")
        pending_path = pending_paths[0]
        try:
            pending_manifest = json.loads(pending_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise self._error_cls(f"failed to read pending retention manifest: {pending_path}") from exc
        if not isinstance(pending_manifest, dict):
            raise self._error_cls(f"pending retention manifest must be an object: {pending_path}")
        return pending_path.parent, pending_manifest

    def build_retention_pending_manifest(
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

    def build_retention_archive_manifest(
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

    def build_retention_apply_result(
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

    def event_log_contains_retention_event(self, event_id: str) -> bool:
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
            raise self._error_cls(f"failed to read event log: {self.events_path}") from exc
        return False

    def finalize_pending_retention_archive(self, state: dict, archive_root: Path, pending_manifest: dict) -> dict:
        """Finish one already-applied retention archive without recalculating eligibility."""
        archive_root_ref = pending_manifest.get("archive_root_ref", archive_root.relative_to(self.cerebro_dir).as_posix())
        if not isinstance(archive_root_ref, str) or not archive_root_ref:
            raise self._error_cls(f"pending retention manifest is missing archive_root_ref: {archive_root}")
        created_at = pending_manifest.get("created_at", "")
        if not isinstance(created_at, str) or not created_at:
            raise self._error_cls(f"pending retention manifest is missing created_at: {archive_root}")
        policy = pending_manifest.get("policy")
        events = pending_manifest.get("events")
        artifacts = pending_manifest.get("artifacts")
        if not isinstance(policy, dict) or not isinstance(events, dict) or not isinstance(artifacts, dict):
            raise self._error_cls(f"pending retention manifest is incomplete: {archive_root}")
        archived_group_paths = artifacts.get("archived_group_paths", [])
        if not isinstance(archived_group_paths, list) or not all(isinstance(item, str) for item in archived_group_paths):
            raise self._error_cls(f"pending retention manifest archived_group_paths must be a string list: {archive_root}")
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
            raise self._error_cls(f"pending retention manifest counts must be non-negative integers: {archive_root}")
        retention_event = pending_manifest.get("retention_event")
        if not isinstance(retention_event, dict):
            raise self._error_cls(f"pending retention manifest is missing retention_event: {archive_root}")
        retention_event_id = retention_event.get("event_id", "")
        if not isinstance(retention_event_id, str) or not retention_event_id:
            raise self._error_cls(f"pending retention manifest retention_event is missing event_id: {archive_root}")

        if not self.event_log_contains_retention_event(retention_event_id):
            self._commit_trace_events(state, [retention_event])
            trace_error = state["agent_runtime"]["audit"].get("last_trace_error", "")
            if trace_error.startswith(f"{retention_event_id}:"):
                raise self._error_cls(f"failed to append retention_applied trace event: {trace_error}")

        manifest = self.build_retention_archive_manifest(
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
            raise self._error_cls(f"failed to remove pending retention manifest: {pending_path}") from exc

        return self.build_retention_apply_result(
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

    def build_retention_report(self, state: dict) -> dict:
        """Build one dry-run retention report from the current canonical state."""
        event_plan = self.build_event_log_retention_plan()
        artifact_plan = self.build_artifact_retention_plan(state)
        return {
            "policy": self.describe_retention_policy(),
            "events": event_plan,
            "artifacts": artifact_plan,
            "has_candidates": bool(event_plan["archived_line_count"] or artifact_plan["archive_group_count"]),
        }

    def build_event_log_retention_plan(self) -> dict:
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
            raise self._error_cls(f"failed to read event log: {self.events_path}") from exc

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

    def build_artifact_retention_plan(self, state: dict) -> dict:
        """Return one retention plan for grouped runtime artifacts."""
        groups: dict[str, dict] = {}
        blocked_unknown_groups: set[str] = set()
        live_groups = self.live_artifact_group_paths(state)
        if self.artifacts_dir.exists():
            for path in self.artifacts_dir.rglob("*"):
                if not path.is_file():
                    continue
                relative_path = path.relative_to(self.artifacts_dir).as_posix()
                group_path = self.artifact_retention_group_path(relative_path)
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

    def live_artifact_group_paths(self, state: dict) -> set[str]:
        """Return grouped artifact paths that remain operationally live."""
        live_groups: set[str] = set()
        for ref, _label, _sha256 in self._iter_live_runtime_artifact_refs(state):
            try:
                resolved = self._resolve_runtime_artifact_ref(ref)
            except self._error_cls:
                continue
            try:
                relative = resolved.relative_to(self.artifacts_dir).as_posix()
            except ValueError:
                continue
            group_path = self.artifact_retention_group_path(relative)
            if group_path is not None:
                live_groups.add(group_path)
        return live_groups

    def artifact_retention_group_path(self, relative_artifact_path: str) -> str | None:
        """Map one artifact file path to the retention group that owns it."""
        candidate = Path(relative_artifact_path)
        if len(candidate.parts) < 2:
            return None
        if candidate.parts[0] not in {"verification", "actions"}:
            return None
        return Path(candidate.parts[0], candidate.parts[1]).as_posix()

    def remove_empty_artifact_parents(self, start: Path) -> None:
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
