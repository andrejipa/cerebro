"""Typed action validation, execution, and rollback for the alpha runtime."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from core.agent_runtime import current_plan_generation_id
from core.digests import sha256_bytes as _sha256_bytes
from core.digests import sha256_text as _sha256_text
from core.execution_policy import (
    ExecutionPolicyError,
    ensure_command_allowed,
    ensure_mutation_path_allowed,
    required_action_approval_error,
)
from core.store_protocols import ActionStoreSurface


class ActionRuntimeError(Exception):
    """Raised when a typed action is structurally invalid or cannot be executed safely."""


TRANSACTIONAL_BATCH_ACTION_KINDS = {
    "fs.create_file",
    "fs.move",
    "fs.delete_soft",
    "fs.write_patch",
}


def _timestamp_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _require_non_empty_string(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ActionRuntimeError(f"{label} must be a non-empty string")
    return value.strip()


def _require_bool(value: object, label: str) -> bool:
    if not isinstance(value, bool):
        raise ActionRuntimeError(f"{label} must be a boolean")
    return value


def _require_list(value: object, label: str) -> list:
    if not isinstance(value, list):
        raise ActionRuntimeError(f"{label} must be an array")
    return value


def _require_int(value: object, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ActionRuntimeError(f"{label} must be an integer")
    return value


def _resolve_workspace_path(root: Path, raw_path: str) -> Path:
    candidate = Path(_require_non_empty_string(raw_path, "path"))
    if candidate.is_absolute():
        raise ActionRuntimeError(f"path must be relative: {raw_path}")
    if any(part == ".." for part in candidate.parts):
        raise ActionRuntimeError(f"path cannot contain '..': {raw_path}")
    return (root / candidate).resolve()


def _resolve_runtime_ref(root: Path, store: ActionStoreSurface, ref: str) -> Path:
    path = (store.cerebro_dir / Path(ref)).resolve()
    try:
        path.relative_to(store.cerebro_dir.resolve())
    except ValueError as exc:
        raise ActionRuntimeError(f"runtime reference resolves outside the runtime directory: {ref}") from exc
    return path


def _collect_missing_parent_dirs(root: Path, path: Path) -> list[str]:
    """Return workspace-relative parent directories that do not exist yet."""
    missing_dirs: list[str] = []
    current = path.parent
    root_resolved = root.resolve()
    while current != root_resolved and not current.exists():
        missing_dirs.append(current.relative_to(root_resolved).as_posix())
        current = current.parent
    return missing_dirs


def _prune_empty_workspace_dirs(root: Path, raw_dirs: list[str]) -> None:
    """Remove previously-created workspace directories when they are now empty."""
    for raw_dir in raw_dirs:
        if not isinstance(raw_dir, str) or not raw_dir:
            continue
        candidate = _resolve_workspace_path(root, raw_dir)
        try:
            candidate.rmdir()
        except OSError:
            continue


def _write_text_atomic(path: Path, content: str) -> None:
    tmp_path = path.with_suffix(f"{path.suffix}.tmp")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path.write_text(content, encoding="utf-8", newline="\n")
        os.replace(tmp_path, path)
    finally:
        try:
            if tmp_path.exists():
                tmp_path.unlink()
        except OSError:
            pass


def _exec_command_binding_payload(command: dict | None, command_id: str) -> dict:
    """Return the approval/retry-relevant snapshot for one exec.command entry."""
    if not isinstance(command, dict):
        return {"command_id": command_id, "missing": True}

    argv = command.get("argv", [])
    if not isinstance(argv, list):
        argv = []

    return {
        "command_id": command_id,
        "argv": list(argv),
        "cwd": command.get("cwd", "") if isinstance(command.get("cwd"), str) else "",
        "timeout_ms": command.get("timeout_ms"),
        "determinism": command.get("determinism", "") if isinstance(command.get("determinism"), str) else "",
        "side_effect": command.get("side_effect", "") if isinstance(command.get("side_effect"), str) else "",
        "risk": command.get("risk", "") if isinstance(command.get("risk"), str) else "",
        "allow_in_verify": bool(command.get("allow_in_verify", False)),
    }


def compute_exec_command_signature(command_registry: dict[str, dict], command_id: str) -> str:
    """Return a stable digest for the resolved exec.command registry snapshot."""
    payload = _exec_command_binding_payload(command_registry.get(command_id), command_id)
    serialized = json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return _sha256_text(serialized)


def _attach_plan_generation(agent_runtime: dict, details: dict) -> dict:
    """Stamp action details with the current plan generation marker."""
    return {
        **details,
        "plan_generation_id": current_plan_generation_id(agent_runtime),
    }


def _approval_items(agent_runtime: dict) -> list[dict]:
    approvals = agent_runtime.get("approvals", {})
    items = approvals.get("items", []) if isinstance(approvals, dict) else []
    if not isinstance(items, list):
        return []
    return [
        item
        for item in items
        if isinstance(item, dict)
    ]


def _approval_item_by_id(agent_runtime: dict, approval_id: str) -> dict | None:
    for item in _approval_items(agent_runtime):
        if item.get("id") == approval_id:
            return item
    return None


def _executable_task_ids(agent_runtime: dict) -> tuple[str, ...]:
    plan = agent_runtime.get("plan", {})
    tasks = plan.get("tasks", []) if isinstance(plan, dict) else []
    task_ids: list[str] = []
    for task in tasks:
        if not isinstance(task, dict):
            continue
        task_id = task.get("id")
        if not isinstance(task_id, str) or not task_id:
            continue
        if task.get("status") in {"ready", "running"}:
            task_ids.append(task_id)
    return tuple(task_ids)


def _ensure_action_approval(
    agent_runtime: dict,
    action: dict,
    approval_id: str,
    *,
    target_exists: bool | None = None,
    fingerprint: str = "",
    task_id: str = "",
    target: str = "",
) -> None:
    policy = agent_runtime["execution_policy"]
    approval = _approval_item_by_id(agent_runtime, approval_id) if approval_id else None
    legacy_single_task_fallback = (
        task_id
        and isinstance(approval, dict)
        and not approval.get("task_id")
        and _executable_task_ids(agent_runtime) == (task_id,)
    )
    approval_error = required_action_approval_error(
        action,
        approval_id,
        _approval_items(agent_runtime),
        policy["approval_required_kinds"],
        target_exists=target_exists,
        action_fingerprint=fingerprint,
        action_task_id="" if legacy_single_task_fallback else task_id,
        action_target=target,
    )
    if approval_error:
        raise ActionRuntimeError(approval_error)


def _artifact_relpath(*parts: str) -> str:
    return Path("artifacts").joinpath(*parts).as_posix()


def _trash_relpath(*parts: str) -> str:
    return Path("trash").joinpath(*parts).as_posix()


def _record_command_exception_event(
    store: ActionStoreSurface,
    *,
    action: dict,
    command: dict,
    task_id: str,
    batch_id: str,
    approval_id: str,
    exc: BaseException,
) -> None:
    """Append one audit event when exec.command fails before a result is available."""
    recorder = getattr(store, "record_runtime_event", None)
    if not callable(recorder):
        return
    detail = str(exc).strip() or exc.__class__.__name__
    recorder(
        {
            "event": "apply_failed",
            "phase": "apply",
            "step": "apply_failed",
            "task_id": task_id,
            "action_id": action["id"],
            "action_kind": action["kind"],
            "command_id": action["command_id"],
            "batch_id": batch_id,
            "approval_id": approval_id,
            "side_effect": command["side_effect"],
            "reason_code": "command_execution_exception",
            "reason": f"command_id {action['command_id']} raised {exc.__class__.__name__}: {detail}",
        }
    )


def _build_exec_command_record(
    action: dict,
    command: dict,
    agent_runtime: dict,
    result: subprocess.CompletedProcess[str],
    *,
    task_id: str,
    batch_id: str,
    approval_id: str,
    artifact_refs: list[str],
    failure_message: str,
) -> dict:
    """Build one canonical exec.command action record from one subprocess result."""
    return {
        "id": action["id"],
        "kind": action["kind"],
        "status": "applied" if not failure_message else "failed",
        "summary": action["summary"],
        "target": action["command_id"],
        "task_id": task_id,
        "batch_id": batch_id,
        "approval_id": approval_id,
        "artifact_refs": artifact_refs,
        "rollback_ref": "",
        "details": _attach_plan_generation(agent_runtime, {
            "command_id": action["command_id"],
            "side_effect": command["side_effect"],
            "observed_side_effect": command["side_effect"],
            "exit_code": result.returncode,
            "failure_message": failure_message,
        }),
        "updated_at": _timestamp_now(),
    }


def _cleanup_partial_command_artifacts(action_dir: Path, artifact_paths: tuple[Path, ...]) -> None:
    """Best-effort cleanup for partial exec.command artifact writes after one post-run failure."""
    for artifact_path in artifact_paths:
        try:
            artifact_path.unlink()
        except OSError:
            pass
    try:
        action_dir.rmdir()
    except OSError:
        pass


def _copy_path_if_present(source: Path, destination: Path) -> None:
    """Copy one existing file or directory into the sandbox when present."""
    if not source.exists():
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    if source.is_dir():
        shutil.copytree(source, destination, dirs_exist_ok=True)
        return
    shutil.copy2(source, destination)


def _remove_path_if_present(path: Path) -> None:
    """Remove one file or directory when compensation needs to restore absence."""
    if not path.exists() and not path.is_symlink():
        return
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
        return
    path.unlink()


def _restore_path_from_snapshot(snapshot_path: Path, live_path: Path) -> None:
    """Restore one file-system path back to the captured snapshot state."""
    if snapshot_path.exists():
        _remove_path_if_present(live_path)
        live_path.parent.mkdir(parents=True, exist_ok=True)
        if snapshot_path.is_dir():
            shutil.copytree(snapshot_path, live_path, dirs_exist_ok=True)
        else:
            shutil.copy2(snapshot_path, live_path)
        return
    _remove_path_if_present(live_path)


def _restore_paths_best_effort(snapshot_pairs: list[tuple[Path, Path]]) -> list[tuple[Path, OSError]]:
    """Attempt every compensation restore and report any paths that still failed."""
    restore_errors: list[tuple[Path, OSError]] = []
    for snapshot_path, live_path in snapshot_pairs:
        try:
            _restore_path_from_snapshot(snapshot_path, live_path)
        except OSError as exc:
            restore_errors.append((live_path, exc))
    return restore_errors


def _compensation_restore_error(prefix: str, restore_errors: list[tuple[Path, OSError]]) -> ActionRuntimeError:
    """Return one stable error after best-effort compensation has already finished."""
    first_path, first_exc = restore_errors[0]
    return ActionRuntimeError(
        f"{prefix} failed and compensation restore failed after best-effort replay "
        f"({len(restore_errors)} restore error(s)); first error at {first_path}: {first_exc}"
    )


def _apply_workspace_paths(root: Path, action: dict) -> list[Path]:
    """Return workspace paths whose state may change during one apply action."""
    kind = action.get("kind", "")
    if kind in {"fs.create_file", "fs.write_patch", "fs.delete_soft"}:
        return [_resolve_workspace_path(root, action.get("path", ""))]
    if kind == "fs.move":
        return [
            _resolve_workspace_path(root, action.get("from", "")),
            _resolve_workspace_path(root, action.get("to", "")),
        ]
    raise ActionRuntimeError(f"multi-file apply batches currently support only filesystem action kinds: {kind}")


def _apply_runtime_paths(root: Path, store: ActionStoreSurface, action: dict) -> list[Path]:
    """Return runtime-owned paths whose state may change during one apply action."""
    kind = action.get("kind", "")
    action_id = action.get("id", "")
    if not isinstance(action_id, str) or not action_id:
        raise ActionRuntimeError("action id must be available before batch apply")
    paths = [store.artifacts_dir / "actions" / action_id]
    if kind == "fs.delete_soft":
        target = _resolve_workspace_path(root, action.get("path", ""))
        normalized = target.relative_to(root)
        paths.append(store.trash_dir / action_id / normalized)
    return paths


def _collect_apply_surface(root: Path, store: ActionStoreSurface, actions: list[dict]) -> tuple[dict[Path, Path], dict[Path, Path]]:
    """Return the workspace and runtime paths that one apply batch can touch."""
    workspace_paths: dict[Path, Path] = {}
    runtime_paths: dict[Path, Path] = {}

    for action in actions:
        for source_path in _apply_workspace_paths(root, action):
            try:
                relative_path = source_path.relative_to(root)
            except ValueError as exc:
                raise ActionRuntimeError(f"workspace path resolves outside root during apply: {source_path}") from exc
            workspace_paths[source_path] = relative_path
        for runtime_path in _apply_runtime_paths(root, store, action):
            try:
                relative_path = runtime_path.relative_to(store.cerebro_dir)
            except ValueError as exc:
                raise ActionRuntimeError(
                    f"runtime path resolves outside the runtime directory during apply: {runtime_path}"
                ) from exc
            runtime_paths[runtime_path] = relative_path

    return workspace_paths, runtime_paths


def load_action_payload(path: Path) -> dict:
    """Read one JSON action payload from disk."""
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ActionRuntimeError(f"failed to read action file: {path}") from exc
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ActionRuntimeError(f"invalid JSON in action file: {exc.msg}") from exc
    if not isinstance(payload, dict):
        raise ActionRuntimeError("action payload must be a JSON object")
    return payload


def normalize_action_payload(payload: dict) -> dict:
    """Validate and normalize one action payload."""
    kind = _require_non_empty_string(payload.get("kind"), "kind")
    action_id = _require_non_empty_string(payload.get("id", kind.replace(".", "-")), "id")
    summary = _require_non_empty_string(payload.get("summary", kind), "summary")

    normalized = {
        "id": action_id,
        "kind": kind,
        "summary": summary,
    }

    if kind == "fs.create_file":
        normalized["path"] = _require_non_empty_string(payload.get("path"), "path")
        content = payload.get("content")
        if not isinstance(content, str):
            raise ActionRuntimeError("content must be a string")
        normalized["content"] = content
        normalized["overwrite"] = _require_bool(payload.get("overwrite", False), "overwrite")
        return normalized

    if kind == "fs.move":
        normalized["from"] = _require_non_empty_string(payload.get("from"), "from")
        normalized["to"] = _require_non_empty_string(payload.get("to"), "to")
        normalized["overwrite"] = _require_bool(payload.get("overwrite", False), "overwrite")
        return normalized

    if kind == "fs.delete_soft":
        normalized["path"] = _require_non_empty_string(payload.get("path"), "path")
        return normalized

    if kind == "fs.write_patch":
        normalized["path"] = _require_non_empty_string(payload.get("path"), "path")
        normalized["expected_sha256"] = _require_non_empty_string(payload.get("expected_sha256"), "expected_sha256")
        replacements = _require_list(payload.get("replacements"), "replacements")
        if not replacements:
            raise ActionRuntimeError("replacements must contain at least one item")
        normalized_replacements: list[dict] = []
        for index, item in enumerate(replacements):
            if not isinstance(item, dict):
                raise ActionRuntimeError(f"replacements[{index}] must be an object")
            old = item.get("old")
            new = item.get("new")
            count = item.get("count", 1)
            if not isinstance(old, str):
                raise ActionRuntimeError(f"replacements[{index}].old must be a string")
            if not isinstance(new, str):
                raise ActionRuntimeError(f"replacements[{index}].new must be a string")
            count_value = _require_int(count, f"replacements[{index}].count")
            if count_value <= 0:
                raise ActionRuntimeError(f"replacements[{index}].count must be greater than zero")
            normalized_replacements.append({"old": old, "new": new, "count": count_value})
        normalized["replacements"] = normalized_replacements
        return normalized

    if kind == "exec.command":
        normalized["command_id"] = _require_non_empty_string(payload.get("command_id"), "command_id")
        return normalized

    raise ActionRuntimeError(f"unsupported action kind: {kind}")


def compute_action_fingerprint(payload: dict, *, command_registry: dict[str, dict] | None = None) -> str:
    """Return a deterministic fingerprint for approval and retry matching."""
    normalized = normalize_action_payload(payload)
    fingerprint_payload = {key: value for key, value in normalized.items() if key not in {"id", "summary"}}
    if normalized["kind"] == "exec.command" and command_registry is not None:
        fingerprint_payload["command_signature"] = compute_exec_command_signature(
            command_registry,
            normalized["command_id"],
        )
    serialized = json.dumps(fingerprint_payload, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return _sha256_text(serialized)


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ActionRuntimeError(f"failed to read file: {path}") from exc


def _read_bytes(path: Path) -> bytes:
    try:
        return path.read_bytes()
    except OSError as exc:
        raise ActionRuntimeError(f"failed to read file: {path}") from exc


def _assert_runtime_artifact_integrity(root: Path, store: ActionStoreSurface, ref: str, expected_sha256: object, label: str) -> None:
    """Reject rollback when the persisted runtime artifact content no longer matches the recorded digest."""
    if not isinstance(expected_sha256, str) or not expected_sha256:
        return
    if len(expected_sha256) != 64 or any(char not in "0123456789abcdef" for char in expected_sha256):
        raise ActionRuntimeError(f"{label} hash metadata is invalid: {ref}")
    resolved_path = _resolve_runtime_ref(root, store, ref)
    current_sha256 = _sha256_bytes(_read_bytes(resolved_path))
    if current_sha256 != expected_sha256:
        raise ActionRuntimeError(f"{label} content diverged since apply: {ref}")


def _rollback_workspace_paths(root: Path, action_record: dict) -> list[Path]:
    """Return workspace paths whose current state affects rollback readiness."""
    kind = action_record.get("kind", "")
    details = action_record.get("details", {})
    if not isinstance(details, dict):
        raise ActionRuntimeError("action details must be an object for rollback")

    paths: list[Path] = []
    if kind in {"fs.create_file", "fs.write_patch", "fs.delete_soft"}:
        raw_path = details.get("path", action_record.get("target", ""))
        paths.append(_resolve_workspace_path(root, raw_path))
    elif kind == "fs.move":
        paths.append(_resolve_workspace_path(root, details.get("from_path", "")))
        paths.append(_resolve_workspace_path(root, details.get("to_path", "")))
    else:
        raise ActionRuntimeError(f"action kind does not support rollback: {kind}")
    return paths


def _rollback_runtime_refs(action_record: dict) -> list[str]:
    """Return runtime refs whose availability affects rollback readiness."""
    kind = action_record.get("kind", "")
    details = action_record.get("details", {})
    if not isinstance(details, dict):
        raise ActionRuntimeError("action details must be an object for rollback")

    refs: list[str] = []
    if kind in {"fs.create_file", "fs.write_patch"}:
        rollback_ref = action_record.get("rollback_ref", "")
        if isinstance(rollback_ref, str) and rollback_ref:
            refs.append(rollback_ref)
    elif kind == "fs.move":
        target_preimage_ref = details.get("target_preimage_ref", "")
        if isinstance(target_preimage_ref, str) and target_preimage_ref:
            refs.append(target_preimage_ref)
    elif kind == "fs.delete_soft":
        trash_ref = details.get("trash_ref", action_record.get("rollback_ref", ""))
        if isinstance(trash_ref, str) and trash_ref:
            refs.append(trash_ref)
    else:
        raise ActionRuntimeError(f"action kind does not support rollback: {kind}")
    return refs


def _collect_rollback_surface(root: Path, store: ActionStoreSurface, action_records: list[dict]) -> tuple[dict[Path, Path], dict[Path, Path]]:
    """Return the workspace paths and runtime refs that rollback may touch."""
    workspace_paths: dict[Path, Path] = {}
    runtime_refs: dict[Path, Path] = {}

    for action_record in action_records:
        for source_path in _rollback_workspace_paths(root, action_record):
            try:
                relative_path = source_path.relative_to(root)
            except ValueError as exc:
                raise ActionRuntimeError(f"workspace path resolves outside root during rollback: {source_path}") from exc
            workspace_paths[source_path] = relative_path
        for ref in _rollback_runtime_refs(action_record):
            source_ref_path = _resolve_runtime_ref(root, store, ref)
            try:
                relative_ref = source_ref_path.relative_to(store.cerebro_dir)
            except ValueError as exc:
                raise ActionRuntimeError(f"runtime reference resolves outside the runtime directory during rollback: {ref}") from exc
            runtime_refs[source_ref_path] = relative_ref

    return workspace_paths, runtime_refs


def preflight_apply_batch(
    root: Path,
    store: ActionStoreSurface,
    agent_runtime: dict,
    action_specs: list[dict],
    command_registry: dict[str, dict],
    registered_paths: set[str],
) -> None:
    """Fail closed before the first real mutation when a multi-file apply batch cannot replay cleanly."""
    if not action_specs:
        raise ActionRuntimeError("no actions supplied for apply preflight")

    normalized_actions = [item["normalized_action"] for item in action_specs]
    workspace_paths, runtime_paths = _collect_apply_surface(root, store, normalized_actions)

    with tempfile.TemporaryDirectory() as sandbox_dir:
        sandbox_root = Path(sandbox_dir)
        sandbox_store = type(
            "SandboxStore",
            (),
            {
                "cerebro_dir": sandbox_root / store.cerebro_dir.name,
                "artifacts_dir": sandbox_root / store.cerebro_dir.name / "artifacts",
                "trash_dir": sandbox_root / store.cerebro_dir.name / "trash",
            },
        )()
        sandbox_store.cerebro_dir.mkdir(parents=True, exist_ok=True)

        for source_path, relative_path in workspace_paths.items():
            _copy_path_if_present(source_path, sandbox_root / relative_path)
        for source_path, relative_path in runtime_paths.items():
            _copy_path_if_present(source_path, sandbox_store.cerebro_dir / relative_path)

        for action_spec in action_specs:
            try:
                apply_action(
                    sandbox_root,
                    sandbox_store,
                    agent_runtime,
                    action_spec["payload"],
                    command_registry,
                    registered_paths,
                    task_id=action_spec["task_id"],
                    batch_id=action_spec["batch_id"],
                    approval_id=action_spec["approval_id"],
                )
            except (ActionRuntimeError, ExecutionPolicyError) as exc:
                raise ActionRuntimeError(
                    f"apply preflight failed before mutation at {action_spec['normalized_action'].get('id', '')}: {exc}"
                ) from exc


def preflight_rollback_actions(
    root: Path,
    store: ActionStoreSurface,
    agent_runtime: dict,
    action_records: list[dict],
    registered_paths: set[str],
) -> None:
    """Fail closed before mutation when the selected rollback set cannot reverse cleanly from current state."""
    if not action_records:
        raise ActionRuntimeError("no actions supplied for rollback preflight")

    ordered_actions = list(reversed(action_records))
    workspace_paths, runtime_refs = _collect_rollback_surface(root, store, ordered_actions)

    with tempfile.TemporaryDirectory() as sandbox_dir:
        sandbox_root = Path(sandbox_dir)
        sandbox_cerebro_dir = sandbox_root / store.cerebro_dir.name
        sandbox_cerebro_dir.mkdir(parents=True, exist_ok=True)
        sandbox_store = type("SandboxStore", (), {"cerebro_dir": sandbox_cerebro_dir})()

        for source_path, relative_path in workspace_paths.items():
            _copy_path_if_present(source_path, sandbox_root / relative_path)
        for source_path, relative_path in runtime_refs.items():
            _copy_path_if_present(source_path, sandbox_cerebro_dir / relative_path)

        for action_record in ordered_actions:
            try:
                rollback_action(sandbox_root, sandbox_store, agent_runtime, action_record, registered_paths)
            except (ActionRuntimeError, ExecutionPolicyError) as exc:
                raise ActionRuntimeError(
                    f"rollback preflight failed before mutation at {action_record.get('id', '')}: {exc}"
                ) from exc


def _restore_rollback_surface(
    root: Path,
    store: ActionStoreSurface,
    *,
    snapshot_root: Path,
    snapshot_cerebro_dir: Path,
    workspace_paths: dict[Path, Path],
    runtime_refs: dict[Path, Path],
) -> list[tuple[Path, OSError]]:
    """Restore every touched rollback path back to the captured pre-batch state."""
    snapshot_pairs = [
        *[(snapshot_root / relative_path, live_path) for live_path, relative_path in workspace_paths.items()],
        *[(snapshot_cerebro_dir / relative_path, live_path) for live_path, relative_path in runtime_refs.items()],
    ]
    return _restore_paths_best_effort(snapshot_pairs)


@contextmanager
def guarded_rollback_batch(
    root: Path,
    store: ActionStoreSurface,
    agent_runtime: dict,
    action_records: list[dict],
    registered_paths: set[str],
):
    """Yield the ordered rollback batch and restore pre-batch state if any later step fails."""
    if not action_records:
        raise ActionRuntimeError("no actions supplied for rollback")

    preflight_rollback_actions(root, store, agent_runtime, action_records, registered_paths)
    ordered_actions = list(reversed(action_records))
    workspace_paths, runtime_refs = _collect_rollback_surface(root, store, ordered_actions)

    with tempfile.TemporaryDirectory() as snapshot_dir:
        snapshot_root = Path(snapshot_dir)
        snapshot_cerebro_dir = snapshot_root / store.cerebro_dir.name
        snapshot_cerebro_dir.mkdir(parents=True, exist_ok=True)

        for source_path, relative_path in workspace_paths.items():
            _copy_path_if_present(source_path, snapshot_root / relative_path)
        for source_path, relative_path in runtime_refs.items():
            _copy_path_if_present(source_path, snapshot_cerebro_dir / relative_path)

        try:
            yield ordered_actions
        except Exception as exc:
            restore_errors = _restore_rollback_surface(
                root,
                store,
                snapshot_root=snapshot_root,
                snapshot_cerebro_dir=snapshot_cerebro_dir,
                workspace_paths=workspace_paths,
                runtime_refs=runtime_refs,
            )
            if restore_errors:
                raise _compensation_restore_error("rollback batch", restore_errors) from exc
            raise


@contextmanager
def guarded_apply_batch(root: Path, store: ActionStoreSurface, normalized_actions: list[dict]):
    """Restore the pre-batch workspace/runtime surface if one multi-file apply later fails."""
    if not normalized_actions:
        raise ActionRuntimeError("no actions supplied for apply batch")

    workspace_paths, runtime_paths = _collect_apply_surface(root, store, normalized_actions)

    with tempfile.TemporaryDirectory() as snapshot_dir:
        snapshot_root = Path(snapshot_dir)
        snapshot_cerebro_dir = snapshot_root / store.cerebro_dir.name
        snapshot_cerebro_dir.mkdir(parents=True, exist_ok=True)

        for source_path, relative_path in workspace_paths.items():
            _copy_path_if_present(source_path, snapshot_root / relative_path)
        for source_path, relative_path in runtime_paths.items():
            _copy_path_if_present(source_path, snapshot_cerebro_dir / relative_path)

        try:
            yield
        except Exception as exc:
            restore_errors = _restore_paths_best_effort(
                [
                    *[(snapshot_root / relative_path, live_path) for live_path, relative_path in workspace_paths.items()],
                    *[
                        (snapshot_cerebro_dir / relative_path, live_path)
                        for live_path, relative_path in runtime_paths.items()
                    ],
                ]
            )
            if restore_errors:
                raise _compensation_restore_error("apply batch", restore_errors) from exc
            raise


def apply_action(
    root: Path,
    store: ActionStoreSurface,
    agent_runtime: dict,
    payload: dict,
    command_registry: dict[str, dict],
    registered_paths: set[str],
    *,
    task_id: str = "",
    batch_id: str = "",
    approval_id: str = "",
) -> dict:
    """Execute one supported action and return the stored action record."""
    action = normalize_action_payload(payload)
    policy = agent_runtime["execution_policy"]
    action_dir = store.artifacts_dir / "actions" / action["id"]
    fingerprint = compute_action_fingerprint(payload, command_registry=command_registry)

    if action["kind"] == "fs.create_file":
        target = _resolve_workspace_path(root, action["path"])
        normalized = ensure_mutation_path_allowed(root, target, policy["protected_paths"], registered_paths)
        target_exists = target.exists()
        if target_exists and not action["overwrite"]:
            raise ActionRuntimeError(f"target file already exists: {normalized}")
        if target_exists and not target.is_file():
            raise ActionRuntimeError(f"target path must be a file: {normalized}")
        _ensure_action_approval(
            agent_runtime,
            action,
            approval_id,
            target_exists=target_exists,
            fingerprint=fingerprint,
            task_id=task_id,
            target=normalized,
        )

        rollback_ref = ""
        created_new = not target_exists
        created_target_dirs = _collect_missing_parent_dirs(root, target) if created_new else []
        if target_exists:
            original = _read_text(target)
            action_dir.mkdir(parents=True, exist_ok=True)
            preimage_path = action_dir / "preimage.txt"
            preimage_path.write_text(original, encoding="utf-8", newline="\n")
            rollback_ref = _artifact_relpath("actions", action["id"], "preimage.txt")
        _write_text_atomic(target, action["content"])
        return {
            "id": action["id"],
            "kind": action["kind"],
            "status": "applied",
            "summary": action["summary"],
            "target": normalized,
            "task_id": task_id,
            "batch_id": batch_id,
            "approval_id": approval_id,
            "artifact_refs": [rollback_ref] if rollback_ref else [],
            "rollback_ref": rollback_ref,
            "details": _attach_plan_generation(agent_runtime, {
                "path": normalized,
                "created_new": created_new,
                "created_target_dirs": created_target_dirs,
                "post_sha256": _sha256_text(action["content"]),
                "rollback_artifact_sha256": _sha256_text(original) if not created_new else "",
            }),
            "updated_at": _timestamp_now(),
        }

    if action["kind"] == "fs.move":
        source = _resolve_workspace_path(root, action["from"])
        target = _resolve_workspace_path(root, action["to"])
        normalized_source = ensure_mutation_path_allowed(root, source, policy["protected_paths"], registered_paths)
        normalized_target = ensure_mutation_path_allowed(root, target, policy["protected_paths"], registered_paths)
        if not source.exists() or not source.is_file():
            raise ActionRuntimeError(f"source file does not exist: {normalized_source}")
        target_exists = target.exists()
        if target_exists and not action["overwrite"]:
            raise ActionRuntimeError(f"target path already exists: {normalized_target}")
        if target_exists and not target.is_file():
            raise ActionRuntimeError(f"target path must be a file: {normalized_target}")
        _ensure_action_approval(
            agent_runtime,
            action,
            approval_id,
            target_exists=target_exists,
            fingerprint=fingerprint,
            task_id=task_id,
            target=normalized_target,
        )

        original_content = _read_text(source)
        target_preimage_ref = ""
        target_preimage_sha256 = ""
        if target_exists:
            target_original = _read_text(target)
            action_dir.mkdir(parents=True, exist_ok=True)
            target_preimage_path = action_dir / "target-preimage.txt"
            target_preimage_path.write_text(target_original, encoding="utf-8", newline="\n")
            target_preimage_ref = _artifact_relpath("actions", action["id"], "target-preimage.txt")
            target_preimage_sha256 = _sha256_text(target_original)
        created_target_dirs = _collect_missing_parent_dirs(root, target)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source), str(target))
        return {
            "id": action["id"],
            "kind": action["kind"],
            "status": "applied",
            "summary": action["summary"],
            "target": f"{normalized_source} -> {normalized_target}",
            "task_id": task_id,
            "batch_id": batch_id,
            "approval_id": approval_id,
            "artifact_refs": [ref for ref in [target_preimage_ref] if ref],
            "rollback_ref": "",
            "details": _attach_plan_generation(agent_runtime, {
                "from_path": normalized_source,
                "to_path": normalized_target,
                "post_sha256": _sha256_text(original_content),
                "overwrote_target": bool(target_preimage_ref),
                "target_preimage_ref": target_preimage_ref,
                "target_preimage_sha256": target_preimage_sha256,
                "created_target_dirs": created_target_dirs,
            }),
            "updated_at": _timestamp_now(),
        }

    if action["kind"] == "fs.delete_soft":
        source = _resolve_workspace_path(root, action["path"])
        normalized = ensure_mutation_path_allowed(root, source, policy["protected_paths"], registered_paths)
        if not source.exists() or not source.is_file():
            raise ActionRuntimeError(f"source file does not exist: {normalized}")
        _ensure_action_approval(
            agent_runtime,
            action,
            approval_id,
            fingerprint=fingerprint,
            task_id=task_id,
            target=normalized,
        )
        trash_target = store.trash_dir / action["id"] / Path(normalized)
        trash_target.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source), str(trash_target))
        rollback_ref = _trash_relpath(action["id"], Path(normalized).as_posix())
        return {
            "id": action["id"],
            "kind": action["kind"],
            "status": "applied",
            "summary": action["summary"],
            "target": normalized,
            "task_id": task_id,
            "batch_id": batch_id,
            "approval_id": approval_id,
            "artifact_refs": [rollback_ref],
            "rollback_ref": rollback_ref,
            "details": _attach_plan_generation(agent_runtime, {
                "path": normalized,
                "trash_ref": rollback_ref,
                "trash_sha256": _sha256_bytes(_read_bytes(trash_target)),
            }),
            "updated_at": _timestamp_now(),
        }

    if action["kind"] == "fs.write_patch":
        target = _resolve_workspace_path(root, action["path"])
        normalized = ensure_mutation_path_allowed(root, target, policy["protected_paths"], registered_paths)
        if not target.exists() or not target.is_file():
            raise ActionRuntimeError(f"target file does not exist: {normalized}")
        original = _read_text(target)
        if _sha256_text(original) != action["expected_sha256"]:
            raise ActionRuntimeError(f"expected_sha256 does not match current file: {normalized}")
        _ensure_action_approval(
            agent_runtime,
            action,
            approval_id,
            fingerprint=fingerprint,
            task_id=task_id,
            target=normalized,
        )
        updated = original
        for replacement in action["replacements"]:
            occurrences = updated.count(replacement["old"])
            if occurrences < replacement["count"]:
                raise ActionRuntimeError(f"replacement source text not found enough times in {normalized}")
            updated = updated.replace(replacement["old"], replacement["new"], replacement["count"])
        action_dir.mkdir(parents=True, exist_ok=True)
        preimage_path = action_dir / "preimage.txt"
        preimage_path.write_text(original, encoding="utf-8", newline="\n")
        _write_text_atomic(target, updated)
        rollback_ref = _artifact_relpath("actions", action["id"], "preimage.txt")
        return {
            "id": action["id"],
            "kind": action["kind"],
            "status": "applied",
            "summary": action["summary"],
            "target": normalized,
            "task_id": task_id,
            "batch_id": batch_id,
            "approval_id": approval_id,
            "artifact_refs": [rollback_ref],
            "rollback_ref": rollback_ref,
            "details": _attach_plan_generation(agent_runtime, {
                "path": normalized,
                "post_sha256": _sha256_text(updated),
                "rollback_artifact_sha256": _sha256_text(original),
            }),
            "updated_at": _timestamp_now(),
        }

    command = command_registry.get(action["command_id"])
    if command is None:
        raise ActionRuntimeError(f"unknown command_id: {action['command_id']}")
    ensure_command_allowed(policy["autonomy_level"], command["argv"], policy["blocked_command_prefixes"])
    command_cwd = (root / command["cwd"]).resolve()
    try:
        command_cwd.relative_to(root.resolve())
    except ValueError as exc:
        raise ActionRuntimeError(f"command cwd resolves outside root: {command['cwd']}") from exc

    if command["side_effect"] == "read_only":
        raise ActionRuntimeError(
            f"apply does not execute command_id declared side_effect=read_only: {action['command_id']}; run it through verify"
        )
    _ensure_action_approval(
        agent_runtime,
        action,
        approval_id,
        fingerprint=fingerprint,
        task_id=task_id,
        target=action["command_id"],
    )
    try:
        result = subprocess.run(
            command["argv"],
            cwd=command_cwd,
            capture_output=True,
            text=True,
            timeout=command["timeout_ms"] / 1000,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        _record_command_exception_event(
            store,
            action=action,
            command=command,
            task_id=task_id,
            batch_id=batch_id,
            approval_id=approval_id,
            exc=exc,
        )
        raise ActionRuntimeError(f"failed to execute command_id {action['command_id']}: {exc}") from exc
    stdout_path = action_dir / "stdout.txt"
    stderr_path = action_dir / "stderr.txt"
    try:
        action_dir.mkdir(parents=True, exist_ok=True)
        stdout_path.write_text(result.stdout, encoding="utf-8", newline="\n")
        stderr_path.write_text(result.stderr, encoding="utf-8", newline="\n")
    except OSError as exc:
        _cleanup_partial_command_artifacts(action_dir, (stdout_path, stderr_path))
        return _build_exec_command_record(
            action,
            command,
            agent_runtime,
            result,
            task_id=task_id,
            batch_id=batch_id,
            approval_id=approval_id,
            artifact_refs=[],
            failure_message=f"failed to persist command artifacts: {exc}",
        )
    failure_message = ""
    if result.returncode != 0:
        failure_message = "command exited with non-zero status"
    return _build_exec_command_record(
        action,
        command,
        agent_runtime,
        result,
        task_id=task_id,
        batch_id=batch_id,
        approval_id=approval_id,
        artifact_refs=[
            _artifact_relpath("actions", action["id"], "stdout.txt"),
            _artifact_relpath("actions", action["id"], "stderr.txt"),
        ],
        failure_message=failure_message,
    )


def rollback_action(root: Path, store: ActionStoreSurface, agent_runtime: dict, action_record: dict, registered_paths: set[str]) -> dict:
    """Rollback one previously applied reversible action."""
    policy = agent_runtime["execution_policy"]
    if action_record.get("status") != "applied":
        raise ActionRuntimeError(f"only applied actions can be rolled back: {action_record.get('id', '')}")

    kind = action_record["kind"]
    details = action_record.get("details", {})
    if not isinstance(details, dict):
        raise ActionRuntimeError("action details must be an object for rollback")

    if kind == "fs.create_file":
        target = _resolve_workspace_path(root, details.get("path", action_record["target"]))
        normalized = ensure_mutation_path_allowed(root, target, policy["protected_paths"], registered_paths)
        if details.get("created_new", False):
            if not target.exists() or not target.is_file():
                raise ActionRuntimeError(f"created file no longer exists for rollback: {normalized}")
            if _sha256_text(_read_text(target)) != details.get("post_sha256"):
                raise ActionRuntimeError(f"current file content diverged since apply: {normalized}")
            target.unlink()
            _prune_empty_workspace_dirs(root, details.get("created_target_dirs", []))
        else:
            rollback_ref = action_record.get("rollback_ref", "")
            if not rollback_ref:
                raise ActionRuntimeError(f"missing rollback ref for overwritten file: {normalized}")
            if not target.exists() or not target.is_file():
                raise ActionRuntimeError(f"overwritten file missing before rollback: {normalized}")
            if _sha256_text(_read_text(target)) != details.get("post_sha256"):
                raise ActionRuntimeError(f"current file content diverged since apply: {normalized}")
            _assert_runtime_artifact_integrity(
                root,
                store,
                rollback_ref,
                details.get("rollback_artifact_sha256", ""),
                "rollback artifact",
            )
            _write_text_atomic(target, _read_text(_resolve_runtime_ref(root, store, rollback_ref)))
    elif kind == "fs.move":
        source = _resolve_workspace_path(root, details.get("from_path", ""))
        target = _resolve_workspace_path(root, details.get("to_path", ""))
        normalized_source = ensure_mutation_path_allowed(root, source, policy["protected_paths"], registered_paths)
        normalized_target = ensure_mutation_path_allowed(root, target, policy["protected_paths"], registered_paths)
        if not target.exists() or not target.is_file():
            raise ActionRuntimeError(f"moved file no longer exists for rollback: {normalized_target}")
        if source.exists():
            raise ActionRuntimeError(f"original source path already exists and blocks rollback: {normalized_source}")
        if _sha256_text(_read_text(target)) != details.get("post_sha256"):
            raise ActionRuntimeError(f"moved file content diverged since apply: {normalized_target}")
        source.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(target), str(source))
        target_preimage_ref = details.get("target_preimage_ref", "")
        if target_preimage_ref:
            _assert_runtime_artifact_integrity(
                root,
                store,
                target_preimage_ref,
                details.get("target_preimage_sha256", ""),
                "rollback artifact",
            )
            _write_text_atomic(target, _read_text(_resolve_runtime_ref(root, store, target_preimage_ref)))
        else:
            _prune_empty_workspace_dirs(root, details.get("created_target_dirs", []))
    elif kind == "fs.delete_soft":
        target = _resolve_workspace_path(root, details.get("path", action_record["target"]))
        normalized = ensure_mutation_path_allowed(root, target, policy["protected_paths"], registered_paths)
        if target.exists():
            raise ActionRuntimeError(f"original path already exists and blocks rollback: {normalized}")
        trash_ref = details.get("trash_ref", action_record.get("rollback_ref", ""))
        if not trash_ref:
            raise ActionRuntimeError(f"missing trash ref for rollback: {normalized}")
        trash_target = _resolve_runtime_ref(root, store, trash_ref)
        if not trash_target.exists() or not trash_target.is_file():
            raise ActionRuntimeError(f"soft-deleted file is missing from trash: {normalized}")
        _assert_runtime_artifact_integrity(
            root,
            store,
            trash_ref,
            details.get("trash_sha256", ""),
            "rollback artifact",
        )
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(trash_target), str(target))
    elif kind == "fs.write_patch":
        target = _resolve_workspace_path(root, details.get("path", action_record["target"]))
        normalized = ensure_mutation_path_allowed(root, target, policy["protected_paths"], registered_paths)
        rollback_ref = action_record.get("rollback_ref", "")
        if not rollback_ref:
            raise ActionRuntimeError(f"missing rollback ref for patched file: {normalized}")
        if not target.exists() or not target.is_file():
            raise ActionRuntimeError(f"patched file no longer exists for rollback: {normalized}")
        if _sha256_text(_read_text(target)) != details.get("post_sha256"):
            raise ActionRuntimeError(f"patched file content diverged since apply: {normalized}")
        _assert_runtime_artifact_integrity(
            root,
            store,
            rollback_ref,
            details.get("rollback_artifact_sha256", ""),
            "rollback artifact",
        )
        _write_text_atomic(target, _read_text(_resolve_runtime_ref(root, store, rollback_ref)))
    else:
        raise ActionRuntimeError(f"action kind does not support rollback: {kind}")

    updated = dict(action_record)
    updated["status"] = "rolled_back"
    updated["updated_at"] = _timestamp_now()
    updated["details"] = {
        **details,
        "rolled_back_at": updated["updated_at"],
    }
    return updated
