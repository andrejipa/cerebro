"""Verification runtime for registered command checks."""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

from core.agent_runtime import MAX_VERIFICATION_CHECKS, build_command_registry_map
from core.command_sandbox import (
    capture_tree_manifest,
    has_meaningful_manifest_change,
    prepare_project_sandbox,
    summarize_manifest_diff,
)
from core.execution_policy import ExecutionPolicyError, ensure_command_allowed
from core.state_store import SESSION_CLAIMS_DIR_ENV_VAR, SESSION_LIVE_PROOFS_DIR_ENV_VAR, StateStoreError
from core.store_protocols import VerificationStoreSurface


class VerificationRuntimeError(Exception):
    """Raised when registered verification commands cannot be executed safely."""


SESSION_TOKEN_ENV_VAR = "CEREBRO_SESSION_TOKEN"
VERIFY_HOST_ENV_ALLOWLIST = (
    "COMSPEC",
    "PATHEXT",
    "PATH",
    "SYSTEMDRIVE",
    "SYSTEMROOT",
    "WINDIR",
)
VERIFY_ARTIFACT_REDACTION_ENV_KEYS = (
    "COMSPEC",
    "PATH",
    "SYSTEMROOT",
    "WINDIR",
)


def _timestamp_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _artifact_relpath(*parts: str) -> str:
    return Path("artifacts").joinpath(*parts).as_posix()


def _sha256_text(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _guarded_runtime_relative_paths(root: Path, snapshots: list[dict]) -> set[str]:
    guarded: set[str] = set()
    root_resolved = root.resolve()
    for snapshot in snapshots:
        if not isinstance(snapshot, dict):
            continue
        path = snapshot.get("path")
        if not isinstance(path, Path):
            continue
        try:
            relative = path.resolve().relative_to(root_resolved).as_posix()
        except ValueError:
            continue
        guarded.add(relative)
    return guarded


def _capture_live_project_manifest(
    root: Path,
    *,
    ignored_prefixes: tuple[str, ...] = (),
    ignored_relatives: set[str] | None = None,
) -> dict[str, tuple]:
    ignored = ignored_relatives or set()
    manifest: dict[str, tuple] = {}
    for relative, marker in capture_tree_manifest(root).items():
        if relative in ignored:
            continue
        if any(relative == prefix or relative.startswith(f"{prefix}/") for prefix in ignored_prefixes):
            continue
        manifest[relative] = marker
    return manifest


def _manifest_changed_paths(before: dict[str, tuple], after: dict[str, tuple]) -> list[str]:
    changed: list[str] = []
    for relative in sorted(set(before).union(after)):
        if has_meaningful_manifest_change(before.get(relative), after.get(relative)):
            changed.append(relative)
    return changed


def _remove_live_project_path(path: Path) -> None:
    if not path.exists() and not path.is_symlink():
        return
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
        return
    path.unlink()


def _restore_live_project_changes(
    snapshot_root: Path,
    live_root: Path,
    changed_paths: list[str],
) -> list[tuple[str, OSError]]:
    candidates = [relative for relative in changed_paths if relative != "."]
    errors: list[tuple[str, OSError]] = []

    for relative in sorted(candidates, key=lambda item: (item.count("/"), item), reverse=True):
        target = live_root / relative
        try:
            _remove_live_project_path(target)
        except OSError as exc:
            errors.append((relative, exc))

    for relative in sorted(candidates, key=lambda item: (item.count("/"), item)):
        source = snapshot_root / relative
        target = live_root / relative
        try:
            if source.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            elif source.exists():
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
        except OSError as exc:
            errors.append((relative, exc))

    return errors


def _format_restore_errors(errors: list[tuple[str, OSError]]) -> str:
    if not errors:
        return ""
    preview = "; ".join(f"{relative}: {exc}" for relative, exc in errors[:3])
    if len(errors) > 3:
        preview = f"{preview}; +{len(errors) - 3} more"
    return preview


def _lookup_host_env(base_env: dict[str, str], key: str) -> str:
    """Return one host env value, matching case-insensitively on Windows."""
    if key in base_env:
        value = base_env[key]
        return value if isinstance(value, str) else ""
    if os.name != "nt":
        return ""
    target = key.lower()
    for candidate_key, candidate_value in base_env.items():
        if candidate_key.lower() == target and isinstance(candidate_value, str):
            return candidate_value
    return ""


def _resolve_verify_command_argv(argv: list[str], base_env: dict[str, str]) -> list[str]:
    """Resolve bare command heads before verify strips the host PATH."""
    if not argv:
        return []
    head = argv[0]
    if not isinstance(head, str) or not head.strip():
        return list(argv)
    candidate = Path(head)
    if candidate.is_absolute() or candidate.parent != Path("."):
        return list(argv)
    host_path = _lookup_host_env(base_env, "PATH") or os.defpath
    resolved = shutil.which(head, path=host_path)
    if not resolved:
        return list(argv)
    return [resolved, *argv[1:]]


def _build_verify_command_path(base_env: dict[str, str], resolved_argv: list[str]) -> str:
    """Build a minimal PATH for verify subprocesses."""
    path_entries: list[str] = []
    if resolved_argv and isinstance(resolved_argv[0], str) and resolved_argv[0]:
        path_entries.append(str(Path(resolved_argv[0]).resolve().parent))
    if os.name == "nt":
        system_root = _lookup_host_env(base_env, "SYSTEMROOT") or _lookup_host_env(base_env, "WINDIR")
        if system_root:
            path_entries.append(str(Path(system_root)))
            path_entries.append(str(Path(system_root) / "System32"))
    unique_entries: list[str] = []
    for entry in path_entries:
        if entry and entry not in unique_entries:
            unique_entries.append(entry)
    return os.pathsep.join(unique_entries)


def _collect_verify_artifact_redactions(base_env: dict[str, str]) -> tuple[str, ...]:
    """Return host env values that must never be persisted in verify artifacts."""
    redactions: list[str] = []
    for key in VERIFY_ARTIFACT_REDACTION_ENV_KEYS:
        value = _lookup_host_env(base_env, key)
        if value:
            redactions.append(value)
            if key == "PATH":
                redactions.extend(
                    segment
                    for segment in value.split(os.pathsep)
                    if segment
                )
    session_token = _lookup_host_env(base_env, SESSION_TOKEN_ENV_VAR)
    if session_token:
        redactions.append(session_token)
    unique_redactions = sorted(set(redactions), key=len, reverse=True)
    return tuple(unique_redactions)


def _redact_verify_artifact_text(text: str, redactions: tuple[str, ...]) -> str:
    """Strip host env values from persisted verify artifacts."""
    redacted = text
    for value in redactions:
        redacted = redacted.replace(value, "")
    return redacted


def _build_verify_command_env(
    base_env: dict[str, str],
    sandbox_root: Path,
    sandbox_owner_root: Path,
    *,
    resolved_argv: list[str],
) -> dict[str, str]:
    """Return one sanitized subprocess environment for verify commands."""
    del sandbox_root
    env = {
        key: value
        for key in VERIFY_HOST_ENV_ALLOWLIST
        if (value := _lookup_host_env(base_env, key))
    }

    sandbox_home = sandbox_owner_root / "home"
    sandbox_temp = sandbox_owner_root / "tmp"
    sandbox_local_app_data = sandbox_owner_root / "localappdata"
    sandbox_app_data = sandbox_owner_root / "appdata"
    sandbox_xdg_state = sandbox_owner_root / "xdg-state"
    sandbox_xdg_cache = sandbox_owner_root / "xdg-cache"
    sandbox_xdg_config = sandbox_owner_root / "xdg-config"
    sandbox_session_claims = sandbox_owner_root / "session-claims"
    sandbox_session_live_proofs = sandbox_owner_root / "session-live-proofs"
    sandbox_pycache = sandbox_owner_root / "pycache"
    for directory in (
        sandbox_home,
        sandbox_temp,
        sandbox_local_app_data,
        sandbox_app_data,
        sandbox_xdg_state,
        sandbox_xdg_cache,
        sandbox_xdg_config,
        sandbox_session_claims,
        sandbox_session_live_proofs,
        sandbox_pycache,
    ):
        directory.mkdir(parents=True, exist_ok=True)

    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONPYCACHEPREFIX"] = str(sandbox_pycache)
    env["HOME"] = str(sandbox_home)
    env["USERPROFILE"] = str(sandbox_home)
    env["LOCALAPPDATA"] = str(sandbox_local_app_data)
    env["APPDATA"] = str(sandbox_app_data)
    env["XDG_STATE_HOME"] = str(sandbox_xdg_state)
    env["XDG_CACHE_HOME"] = str(sandbox_xdg_cache)
    env["XDG_CONFIG_HOME"] = str(sandbox_xdg_config)
    env["TMP"] = str(sandbox_temp)
    env["TEMP"] = str(sandbox_temp)
    env["TMPDIR"] = str(sandbox_temp)
    env["PATH"] = _build_verify_command_path(base_env, resolved_argv)
    env[SESSION_CLAIMS_DIR_ENV_VAR] = str(sandbox_session_claims)
    env[SESSION_LIVE_PROOFS_DIR_ENV_VAR] = str(sandbox_session_live_proofs)
    env.pop(SESSION_TOKEN_ENV_VAR, None)
    return env


def _record_command_exception_event(
    store: VerificationStoreSurface,
    *,
    task_id: str,
    command: dict,
    exc: BaseException,
) -> None:
    """Append one audit event when verify command launch fails before a result is available."""
    recorder = getattr(store, "record_runtime_event", None)
    if not callable(recorder):
        return
    detail = str(exc).strip() or exc.__class__.__name__
    recorder(
        {
            "event": "verify_failed",
            "phase": "verify",
            "step": "verify_failed",
            "task_id": task_id,
            "command_id": command["id"],
            "side_effect": command["side_effect"],
            "reason_code": "command_execution_exception",
            "reason": f"command_id {command['id']} raised {exc.__class__.__name__}: {detail}",
        }
    )


def _record_command_artifact_persistence_event(
    store: VerificationStoreSurface,
    *,
    task_id: str,
    command: dict,
    exc: OSError,
) -> None:
    """Append one audit event when verify artifact persistence fails after execution."""
    recorder = getattr(store, "record_runtime_event", None)
    if not callable(recorder):
        return
    detail = str(exc).strip() or exc.__class__.__name__
    recorder(
        {
            "event": "verify_failed",
            "phase": "verify",
            "step": "verify_failed",
            "task_id": task_id,
            "command_id": command["id"],
            "side_effect": command["side_effect"],
            "reason_code": "command_artifact_persistence_exception",
            "reason": (
                f"command_id {command['id']} raised {exc.__class__.__name__} while "
                f"persisting verification artifacts: {detail}"
            ),
        }
    )


def _record_verification_preflight_failure_event(
    store: VerificationStoreSurface,
    *,
    task_id: str,
    reason_code: str,
    reason: str,
) -> None:
    """Append one audit event when verify fails before the first command starts."""
    recorder = getattr(store, "record_runtime_event", None)
    if not callable(recorder):
        return
    recorder(
        {
            "event": "verify_failed",
            "phase": "verify",
            "step": "verify_failed",
            "task_id": task_id,
            "command_id": "state",
            "side_effect": "read_only",
            "reason_code": reason_code,
            "reason": reason,
        }
    )


def _cleanup_partial_verification_artifacts(run_dir: Path, artifact_paths: tuple[Path, ...]) -> None:
    """Best-effort cleanup for partial verify artifact writes after one post-run failure."""
    for artifact_path in artifact_paths:
        try:
            artifact_path.unlink()
        except OSError:
            pass
    try:
        run_dir.rmdir()
    except OSError:
        pass


def _normalize_command_ids(command_ids: object) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    if not isinstance(command_ids, list):
        return normalized
    for item in command_ids:
        if not isinstance(item, str):
            continue
        command_id = item.strip()
        if not command_id or command_id in seen:
            continue
        normalized.append(command_id)
        seen.add(command_id)
    return normalized


def covers_required_verification_scope(required_command_ids: object, selected_command_ids: object) -> bool:
    """Return whether the selected command ids cover the full required verification set."""
    required = set(_normalize_command_ids(required_command_ids))
    selected = set(_normalize_command_ids(selected_command_ids))
    if not required:
        return True
    return required.issubset(selected)


def run_verification_commands(
    root: Path,
    store: VerificationStoreSurface,
    agent_runtime: dict,
    *,
    command_ids: list[str] | None = None,
) -> dict:
    """Run the registered verification commands and return a persisted record payload."""
    verification = agent_runtime["verification"]
    policy = agent_runtime["execution_policy"]
    task_id = agent_runtime["plan"].get("current_task_id", "")
    command_registry = build_command_registry_map(agent_runtime)

    required_command_ids = _normalize_command_ids(verification.get("required_command_ids", []))
    selected_ids = _normalize_command_ids(command_ids) if command_ids is not None else list(required_command_ids)
    selected = []
    for command_id in selected_ids:
        command = command_registry.get(command_id)
        if command is None:
            raise VerificationRuntimeError(f"unknown verification command id: {command_id}")
        if not command.get("allow_in_verify", False):
            raise VerificationRuntimeError(f"command is not allowed in verify: {command_id}")
        selected.append(command)

    pending_action_ids = [
        action_id
        for action_id in verification["pending_action_ids"]
        if isinstance(action_id, str)
    ]
    if not selected:
        raise VerificationRuntimeError("no verification commands are registered for the current plan")
    if len(selected) > MAX_VERIFICATION_CHECKS:
        max_verify_commands = MAX_VERIFICATION_CHECKS
        raise VerificationRuntimeError(
            "verification command selection exceeds the supported check budget: "
            f"{len(selected)} requested, but at most {max_verify_commands} commands can run"
        )

    full_required_coverage = covers_required_verification_scope(required_command_ids, selected_ids)
    covered_action_ids = pending_action_ids if full_required_coverage else []
    partial_coverage_message = ""
    if not full_required_coverage:
        partial_coverage_message = (
            "partial verification coverage; pending actions remain until the full required command set runs"
        )

    run_id = f"verify-{_timestamp_now().replace(':', '-').replace('+00:00', 'Z')}"
    run_dir: Path | None = None
    restore_dir = None
    try:
        sandbox_dir, sandbox_root = prepare_project_sandbox(root)
        restore_dir, restore_root = prepare_project_sandbox(root)
    except OSError as exc:
        if restore_dir is not None:
            restore_dir.cleanup()
        detail = str(exc).strip() or exc.__class__.__name__
        message = f"failed to prepare verification sandbox: {detail}"
        _record_verification_preflight_failure_event(
            store,
            task_id=task_id,
            reason_code="sandbox_prepare_failed",
            reason=message,
        )
        return {
            "last_run_at": _timestamp_now(),
            "status": "failed",
            "required_command_ids": list(required_command_ids),
            "pending_action_ids": list(pending_action_ids),
            "state_check": {
                "status": "failed",
                "exit_code": 1,
                "message": message,
            },
            "checks": [],
        }
    baseline_manifest = capture_tree_manifest(sandbox_root)
    guarded_runtime_files = store.capture_verify_authority_guard()
    ignored_live_prefixes = (".cerebro/artifacts/verification",)
    ignored_live_relatives = _guarded_runtime_relative_paths(root, guarded_runtime_files)
    baseline_live_project_manifest = _capture_live_project_manifest(
        root,
        ignored_prefixes=ignored_live_prefixes,
        ignored_relatives=ignored_live_relatives,
    )
    host_env = os.environ.copy()
    artifact_redactions = _collect_verify_artifact_redactions(host_env)

    state_check = {
        "status": "passed",
        "exit_code": 0,
        "message": partial_coverage_message,
    }
    checks: list[dict] = []
    overall_status = "passed"
    try:
        for command in selected:
            try:
                ensure_command_allowed(
                    policy["autonomy_level"],
                    command["argv"],
                    policy["blocked_command_prefixes"],
                )
            except ExecutionPolicyError as exc:
                raise VerificationRuntimeError(
                    f"verification command {command['id']} is blocked by execution policy: {exc}"
                ) from exc
            if command.get("side_effect") != "read_only":
                raise VerificationRuntimeError(
                    f"command must declare side_effect=read_only to run in verify: {command['id']}"
                )
            command_cwd = (root / command["cwd"]).resolve()
            try:
                relative_cwd = command_cwd.relative_to(root.resolve())
            except ValueError as exc:
                raise VerificationRuntimeError(f"command cwd resolves outside root: {command['cwd']}") from exc
            sandbox_cwd = (sandbox_root / relative_cwd).resolve()
            try:
                sandbox_cwd.relative_to(sandbox_root.resolve())
            except ValueError as exc:
                raise VerificationRuntimeError(f"command cwd resolves outside verification sandbox: {command['cwd']}") from exc

            if run_dir is None:
                run_dir = store.artifacts_dir / "verification" / run_id
                run_dir.mkdir(parents=True, exist_ok=True)
            resolved_argv = _resolve_verify_command_argv(command["argv"], host_env)
            command_env = _build_verify_command_env(
                host_env,
                sandbox_root,
                Path(sandbox_dir.name),
                resolved_argv=resolved_argv,
            )
            try:
                result = subprocess.run(
                    resolved_argv,
                    cwd=sandbox_cwd,
                    capture_output=True,
                    text=True,
                    timeout=command["timeout_ms"] / 1000,
                    check=False,
                    env=command_env,
                )
            except (OSError, subprocess.SubprocessError) as exc:
                _record_command_exception_event(
                    store,
                    task_id=task_id,
                    command=command,
                    exc=exc,
                )
                raise VerificationRuntimeError(
                    f"failed to execute verification command {command['id']}: {exc}"
                ) from exc
            mutation_summary = summarize_manifest_diff(
                baseline_manifest,
                capture_tree_manifest(sandbox_root),
            )
            live_project_manifest = _capture_live_project_manifest(
                root,
                ignored_prefixes=ignored_live_prefixes,
                ignored_relatives=ignored_live_relatives,
            )
            live_project_changed_paths = _manifest_changed_paths(
                baseline_live_project_manifest,
                live_project_manifest,
            )
            live_project_mutation_summary = summarize_manifest_diff(
                baseline_live_project_manifest,
                live_project_manifest,
            )
            live_project_restore_errors = (
                _restore_live_project_changes(
                    restore_root,
                    root,
                    live_project_changed_paths,
                )
                if live_project_changed_paths
                else []
            )
            authority_mutation_summary = store.restore_verify_authority_guard_if_changed(guarded_runtime_files)
            stdout_text = _redact_verify_artifact_text(result.stdout, artifact_redactions)
            stderr_text = _redact_verify_artifact_text(result.stderr, artifact_redactions)
            stdout_path = run_dir / f"{command['id']}.stdout.txt"
            stderr_path = run_dir / f"{command['id']}.stderr.txt"
            try:
                stdout_path.write_text(stdout_text, encoding="utf-8", newline="\n")
                stderr_path.write_text(stderr_text, encoding="utf-8", newline="\n")
            except OSError as exc:
                _cleanup_partial_verification_artifacts(run_dir, (stdout_path, stderr_path))
                _record_command_artifact_persistence_event(
                    store,
                    task_id=task_id,
                    command=command,
                    exc=exc,
                )
                failure_reasons = [f"failed to persist verification artifacts: {exc}"]
                if mutation_summary:
                    failure_reasons.append(
                        f"verify command mutated the observed sandbox state: {mutation_summary}"
                    )
                if live_project_mutation_summary:
                    failure_reasons.append(
                        f"verify command mutated the live project outside the sandbox: {live_project_mutation_summary}"
                    )
                if live_project_restore_errors:
                    failure_reasons.append(
                        "failed to restore the live project after verify mutation: "
                        + _format_restore_errors(live_project_restore_errors)
                    )
                if authority_mutation_summary:
                    failure_reasons.append(authority_mutation_summary)
                checks.append(
                    {
                        "id": f"check-{command['id']}",
                        "gate": "command",
                        "command_id": command["id"],
                        "status": "failed",
                        "exit_code": result.returncode,
                        "artifact_ref": "",
                        "artifact_sha256": "",
                        "covered_action_ids": covered_action_ids,
                        "message": "; ".join(failure_reasons),
                    }
                )
                overall_status = "failed"
                break
            artifact_ref = _artifact_relpath("verification", run_id, f"{command['id']}.stdout.txt")
            failure_reasons: list[str] = []
            if result.returncode != 0:
                failure_reasons.append("command exited with non-zero status")
            if mutation_summary:
                failure_reasons.append(
                    f"verify command mutated the observed sandbox state: {mutation_summary}"
                )
            if live_project_mutation_summary:
                failure_reasons.append(
                    f"verify command mutated the live project outside the sandbox: {live_project_mutation_summary}"
                )
            if live_project_restore_errors:
                failure_reasons.append(
                    "failed to restore the live project after verify mutation: "
                    + _format_restore_errors(live_project_restore_errors)
                )
            if authority_mutation_summary:
                failure_reasons.append(authority_mutation_summary)
            checks.append(
                {
                    "id": f"check-{command['id']}",
                    "gate": "command",
                    "command_id": command["id"],
                    "status": "passed" if not failure_reasons else "failed",
                    "exit_code": result.returncode,
                    "artifact_ref": artifact_ref,
                    "artifact_sha256": _sha256_text(stdout_text),
                    "covered_action_ids": covered_action_ids,
                    "message": (
                        partial_coverage_message
                        if not failure_reasons and partial_coverage_message
                        else "" if not failure_reasons else "; ".join(failure_reasons)
                    ),
                }
            )
            if failure_reasons:
                overall_status = "failed"
                if mutation_summary or authority_mutation_summary:
                    break
    finally:
        sandbox_dir.cleanup()
        restore_dir.cleanup()

    return {
        "required_command_ids": required_command_ids,
        "pending_action_ids": pending_action_ids,
        "last_run_at": _timestamp_now(),
        "status": overall_status,
        "state_check": state_check,
        "checks": checks,
    }


def execute_verification_cycle(
    root: Path,
    store: VerificationStoreSurface,
    *,
    command_ids: list[str] | None = None,
    expected_session_token: str | None = None,
) -> tuple[dict, dict | None, dict | None]:
    """Run one verify transaction under the core runtime boundary."""
    resolved_root = Path(root).resolve()
    if resolved_root != store.root:
        raise StateStoreError("verification cycle root must match state store root")

    with store.runtime_lock():
        validation_result, state_data = store.validate_state_locked()
        if not validation_result["ok"] or state_data is None:
            return validation_result, None, None
        store.read_owned_active_session(state_data, expected_session_token)

        verification_record = run_verification_commands(
            resolved_root,
            store,
            deepcopy(state_data["agent_runtime"]),
            command_ids=command_ids,
        )
        updated = store.update_agent_verification(
            verification_record,
            validated_revision=validation_result["revision"],
            expected_session_token=expected_session_token,
        )
        return validation_result, verification_record, updated
