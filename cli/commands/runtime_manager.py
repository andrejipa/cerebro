"""CLI orchestration for the core-owned runtime-manager store."""

from __future__ import annotations

import datetime
import json
import os
from pathlib import Path

from cli.output import print_fail, print_ok, user_error
from core.runtime_manager_store import (
    AcquiredLease,
    ApprovalRecord,
    CommandEligibilityResult,
    CommandRunResult,
    ExecutionEvidence,
    ManagedStopCondition,
    ManagedValidation,
    RollbackResult,
    RuntimeIntegrityReport,
    RuntimeManagerMetrics,
    RuntimeManagerStatus,
    RuntimeManagerStore,
    RuntimeManagerStoreError,
    RuntimeObservation,
    RuntimeReplayResult,
    RuntimeTrace,
)
from core.state_store import StateStore, StateStoreError, StateValidationError


def run_runtime_manager(root: Path, args) -> int:
    """Dispatch runtime-manager subcommands without taking runtime authority."""
    store = RuntimeManagerStore(root)
    command = getattr(args, "runtime_manager_command", "")
    output_format = getattr(args, "format", "text")

    try:
        if command == "sync":
            status = store.sync_observation_center()
            if output_format == "json":
                print(json.dumps(_status_payload(status), indent=2))
            else:
                print_ok(
                    [
                        "runtime_manager_synced: observation center imported into runtime.db",
                        f"state: {status.state}",
                        f"selected_id: {status.selected_id or '<none>'}",
                        f"source_sha256: {status.source_sha256}",
                    ]
                )
            return 0

        if command == "status":
            status = store.read_status(observation_center_path=root / "docs" / "operations" / "observation_center.toml")
            if output_format == "json":
                content = json.dumps(_status_payload(status), indent=2) + "\n"
            else:
                content = _render_status_text(status)
            output_path = getattr(args, "out", None)
            if output_path:
                target = _write_projection(root, output_path, content, status)
                print_ok(["runtime_manager_projection_written: runtime-manager status projection written", f"output: {target}"])
            else:
                print(content, end="")
            return 0 if status.state != "blocked" else 1

        if command == "next":
            status = store.read_status(observation_center_path=root / "docs" / "operations" / "observation_center.toml")
            next_item = store.read_next(observation_center_path=root / "docs" / "operations" / "observation_center.toml")
            if output_format == "json":
                content = json.dumps(_next_payload(status, next_item), indent=2) + "\n"
            else:
                content = _render_next_text(status, next_item)
            output_path = getattr(args, "out", None)
            if output_path:
                target = _write_projection(root, output_path, content, status)
                print_ok(["runtime_manager_projection_written: runtime-manager next projection written", f"output: {target}"])
            else:
                print(content, end="")
            return 0 if next_item is not None else 1

        if command == "check":
            command_id_arg = getattr(args, "command_id", "")
            if not command_id_arg:
                print_fail([user_error("runtime_manager_check_missing_command_id", "runtime-manager check requires a command_id argument")])
                return 1
            result = store.check_command_eligibility(
                command_id_arg,
                observation_center_path=root / "docs" / "operations" / "observation_center.toml",
            )
            if output_format == "json":
                content = json.dumps(_eligibility_payload(result), indent=2) + "\n"
            else:
                content = _render_eligibility_text(result)
            print(content, end="")
            return 0 if result.eligible else 1

        if command == "run":
            command_id_arg = getattr(args, "command_id", "")
            if not command_id_arg:
                print_fail([user_error("runtime_manager_run_missing_command_id", "runtime-manager run requires a command_id argument")])
                return 1
            result = store.run_command(
                command_id_arg,
                observation_center_path=root / "docs" / "operations" / "observation_center.toml",
            )
            if output_format == "json":
                content = json.dumps(_run_payload(result), indent=2) + "\n"
            else:
                content = _render_run_text(result)
            print(content, end="")
            return 0 if result.eligible and result.returncode == 0 else 1

        if command == "trace":
            trace_subcommand = getattr(args, "trace_command", "")
            if trace_subcommand == "list":
                operation_arg = getattr(args, "operation", None)
                subject_id_arg = getattr(args, "subject_id", None)
                limit_arg = getattr(args, "limit", 50)
                traces = store.list_traces(operation=operation_arg, subject_id=subject_id_arg, limit=limit_arg)
                if output_format == "json":
                    content = json.dumps({"traces": [_trace_payload(t, include_events=False) for t in traces], "total": len(traces)}, indent=2) + "\n"
                else:
                    content = _render_trace_list_text(traces)
                print(content, end="")
                return 0
            if trace_subcommand == "show":
                trace_id_arg = getattr(args, "trace_id", "")
                trace = store.read_trace(trace_id_arg)
                if output_format == "json":
                    content = json.dumps({"trace": None if trace is None else _trace_payload(trace)}, indent=2) + "\n"
                else:
                    content = _render_trace_text(trace, trace_id_arg)
                print(content, end="")
                return 0 if trace is not None else 1
            if trace_subcommand == "export":
                trace_id_arg = getattr(args, "trace_id", "")
                export_format = getattr(args, "export_format", "json")
                content = store.export_trace(trace_id_arg, export_format)
                print(content, end="")
                return 0
            print_fail([user_error("runtime_manager_trace_subcommand_missing", "runtime-manager trace requires a subcommand: list | show | export")])
            return 1

        if command == "metrics":
            metrics = store.read_metrics()
            if output_format == "json":
                content = json.dumps(_metrics_payload(metrics), indent=2) + "\n"
            else:
                content = _render_metrics_text(metrics)
            print(content, end="")
            return 0

        if command == "replay":
            scenario_arg = getattr(args, "scenario", "")
            if not scenario_arg:
                print_fail([user_error("runtime_manager_replay_missing_scenario", "runtime-manager replay requires --scenario")])
                return 1
            replay = store.replay_scenario(scenario_arg)
            if output_format == "json":
                content = json.dumps(_replay_payload(replay), indent=2) + "\n"
            else:
                content = _render_replay_text(replay)
            print(content, end="")
            return 0 if replay.passed else 1

        if command == "evidence":
            evidence_subcommand = getattr(args, "evidence_command", "")
            if evidence_subcommand == "show":
                evidence_id_arg = getattr(args, "evidence_id", None)
                if evidence_id_arg is None:
                    print_fail([user_error("runtime_manager_evidence_missing_id", "runtime-manager evidence show requires an evidence_id argument")])
                    return 1
                try:
                    evidence_id_int = int(evidence_id_arg)
                except (TypeError, ValueError):
                    print_fail([user_error("runtime_manager_evidence_invalid_id", f"evidence_id must be an integer: {evidence_id_arg}")])
                    return 1
                evidence = store.read_evidence(evidence_id_int)
                if output_format == "json":
                    content = json.dumps({"evidence": None if evidence is None else _evidence_payload(evidence)}, indent=2) + "\n"
                else:
                    content = _render_evidence_text(evidence, evidence_id_int)
                print(content, end="")
                return 0 if evidence is not None else 1

            if evidence_subcommand == "list":
                observation_id_arg = getattr(args, "observation_id", None)
                limit_arg = getattr(args, "limit", 50)
                evidence_rows = store.list_evidence(observation_id=observation_id_arg, limit=limit_arg)
                if output_format == "json":
                    content = json.dumps({"evidence": [_evidence_payload(e) for e in evidence_rows], "total": len(evidence_rows)}, indent=2) + "\n"
                else:
                    content = _render_evidence_list_text(evidence_rows)
                print(content, end="")
                return 0

            print_fail([user_error("runtime_manager_evidence_subcommand_missing", "runtime-manager evidence requires a subcommand: show | list")])
            return 1

        if command == "lease":
            lease_subcommand = getattr(args, "lease_command", "")
            if lease_subcommand == "acquire":
                observation_id_arg = getattr(args, "observation_id", "")
                owner_arg = getattr(args, "owner", "cli")
                ttl_arg = getattr(args, "ttl_seconds", 300)
                reason_arg = getattr(args, "reason", "")
                lease = store.acquire_lease(observation_id_arg, owner=owner_arg, ttl_seconds=ttl_arg, reason=reason_arg)
                if output_format == "json":
                    content = json.dumps(_lease_payload(lease), indent=2) + "\n"
                else:
                    content = _render_lease_text(lease, header="RUNTIME MANAGER LEASE ACQUIRE")
                print(content, end="")
                return 0

            if lease_subcommand == "release":
                lease_id_arg = getattr(args, "lease_id", "")
                owner_arg = getattr(args, "owner", "")
                ok = store.release_lease(lease_id_arg, owner=owner_arg)
                if output_format == "json":
                    print(json.dumps({"released": ok, "lease_id": lease_id_arg}, indent=2))
                else:
                    print(("OK" if ok else "FAIL") + f"\nRUNTIME MANAGER LEASE RELEASE\nlease_id: {lease_id_arg}\nreleased: {str(ok).lower()}\n", end="")
                return 0 if ok else 1

            if lease_subcommand == "heartbeat":
                lease_id_arg = getattr(args, "lease_id", "")
                owner_arg = getattr(args, "owner", "")
                ttl_arg = getattr(args, "ttl_seconds", 300)
                updated = store.heartbeat_lease(lease_id_arg, owner=owner_arg, ttl_seconds=ttl_arg)
                if updated is None:
                    if output_format == "json":
                        print(json.dumps({"renewed": False, "lease_id": lease_id_arg}, indent=2))
                    else:
                        print(f"FAIL\nRUNTIME MANAGER LEASE HEARTBEAT\nlease_id: {lease_id_arg}\nrenewed: false\n", end="")
                    return 1
                if output_format == "json":
                    content = json.dumps(_lease_payload(updated), indent=2) + "\n"
                else:
                    content = _render_lease_text(updated, header="RUNTIME MANAGER LEASE HEARTBEAT")
                print(content, end="")
                return 0

            if lease_subcommand == "list":
                limit_arg = getattr(args, "limit", 50)
                observation_id_arg = getattr(args, "observation_id", None)
                leases = store.list_leases(observation_id=observation_id_arg, limit=limit_arg)
                if output_format == "json":
                    content = json.dumps({"leases": [_lease_payload(l) for l in leases], "total": len(leases)}, indent=2) + "\n"
                else:
                    content = _render_lease_list_text(leases)
                print(content, end="")
                return 0

            print_fail([user_error("runtime_manager_lease_subcommand_missing", "runtime-manager lease requires a subcommand: acquire | release | heartbeat | list")])
            return 1

        if command == "stop":
            stop_subcommand = getattr(args, "stop_command", "")
            if stop_subcommand == "raise":
                subject_id_arg = getattr(args, "subject_id", "")
                reason_arg = getattr(args, "reason", "")
                severity_arg = getattr(args, "severity", "blocking")
                sc = store.raise_stop_condition(subject_id_arg, reason=reason_arg, severity=severity_arg)
                if output_format == "json":
                    content = json.dumps(_stop_condition_payload(sc), indent=2) + "\n"
                else:
                    content = _render_stop_condition_text(sc, header="RUNTIME MANAGER STOP RAISE")
                print(content, end="")
                return 0

            if stop_subcommand == "resolve":
                stop_condition_id_arg = getattr(args, "stop_condition_id", "")
                ok = store.resolve_stop_condition(stop_condition_id_arg)
                if output_format == "json":
                    print(json.dumps({"resolved": ok, "stop_condition_id": stop_condition_id_arg}, indent=2))
                else:
                    print(("OK" if ok else "FAIL") + f"\nRUNTIME MANAGER STOP RESOLVE\nstop_condition_id: {stop_condition_id_arg}\nresolved: {str(ok).lower()}\n", end="")
                return 0 if ok else 1

            if stop_subcommand == "list":
                subject_id_arg = getattr(args, "subject_id", None)
                limit_arg = getattr(args, "limit", 50)
                conditions = store.list_stop_conditions(subject_id=subject_id_arg, limit=limit_arg)
                if output_format == "json":
                    content = json.dumps({"stop_conditions": [_stop_condition_payload(sc) for sc in conditions], "total": len(conditions)}, indent=2) + "\n"
                else:
                    content = _render_stop_condition_list_text(conditions)
                print(content, end="")
                return 0

            print_fail([user_error("runtime_manager_stop_subcommand_missing", "runtime-manager stop requires a subcommand: raise | resolve | list")])
            return 1

        if command == "validation":
            val_subcommand = getattr(args, "validation_command", "")
            if val_subcommand == "record":
                validation_id_arg = getattr(args, "validation_id", "")
                subject_id_arg = getattr(args, "subject_id", "")
                status_arg = getattr(args, "status", "green")
                ttl_arg = getattr(args, "ttl_seconds", 0)
                reason_arg = getattr(args, "reason", "")
                command_id_arg = getattr(args, "command_id", "")
                if status_arg == "green":
                    if ttl_arg and ttl_arg > 0:
                        fresh_until = (
                            datetime.datetime.now(datetime.timezone.utc)
                            + datetime.timedelta(seconds=ttl_arg)
                        ).strftime("%Y-%m-%dT%H:%M:%SZ")
                    else:
                        fresh_until = "9999-12-31T23:59:59Z"
                else:
                    fresh_until = ""
                mv = store.record_validation(
                    validation_id_arg, subject_id_arg,
                    status=status_arg, fresh_until=fresh_until,
                    reason=reason_arg, command_id=command_id_arg,
                )
                if output_format == "json":
                    content = json.dumps(_validation_payload(mv), indent=2) + "\n"
                else:
                    content = _render_validation_text(mv, header="RUNTIME MANAGER VALIDATION RECORD")
                print(content, end="")
                return 0

            if val_subcommand == "show":
                validation_id_arg = getattr(args, "validation_id", "")
                mv = store.read_validation(validation_id_arg)
                if mv is None:
                    if output_format == "json":
                        print(json.dumps({"validation": None, "validation_id": validation_id_arg}, indent=2))
                    else:
                        print(f"FAIL\nRUNTIME MANAGER VALIDATION SHOW\nvalidation_id: {validation_id_arg}\nfound: false\n", end="")
                    return 1
                if output_format == "json":
                    content = json.dumps(_validation_payload(mv), indent=2) + "\n"
                else:
                    content = _render_validation_text(mv, header="RUNTIME MANAGER VALIDATION SHOW")
                print(content, end="")
                return 0

            print_fail([user_error("runtime_manager_validation_subcommand_missing", "runtime-manager validation requires a subcommand: record | show")])
            return 1

        if command == "approval":
            approval_subcommand = getattr(args, "approval_command", "")
            if approval_subcommand == "record":
                command_id_arg = getattr(args, "command_id", "")
                subject_id_arg = getattr(args, "subject_id", "")
                actor_arg = getattr(args, "actor", "cli")
                scope_arg = getattr(args, "scope", "single-use")
                expires_at_arg = getattr(args, "expires_at", "")
                ar = store.record_approval(
                    command_id_arg, subject_id_arg,
                    actor=actor_arg, scope=scope_arg, expires_at=expires_at_arg,
                )
                if output_format == "json":
                    content = json.dumps(_approval_payload(ar), indent=2) + "\n"
                else:
                    content = _render_approval_text(ar, header="RUNTIME MANAGER APPROVAL RECORD")
                print(content, end="")
                return 0

            if approval_subcommand == "revoke":
                approval_id_arg = getattr(args, "approval_id", "")
                ok = store.revoke_approval(approval_id_arg)
                if output_format == "json":
                    print(json.dumps({"revoked": ok, "approval_id": approval_id_arg}, indent=2))
                else:
                    print(("OK" if ok else "FAIL") + f"\nRUNTIME MANAGER APPROVAL REVOKE\napproval_id: {approval_id_arg}\nrevoked: {str(ok).lower()}\n", end="")
                return 0 if ok else 1

            if approval_subcommand == "list":
                subject_id_arg = getattr(args, "subject_id", None)
                command_id_arg = getattr(args, "command_id", None)
                limit_arg = getattr(args, "limit", 50)
                approvals = store.list_approvals(subject_id=subject_id_arg, command_id=command_id_arg, limit=limit_arg)
                if output_format == "json":
                    content = json.dumps({"approvals": [_approval_payload(a) for a in approvals], "total": len(approvals)}, indent=2) + "\n"
                else:
                    content = _render_approval_list_text(approvals)
                print(content, end="")
                return 0

            print_fail([user_error("runtime_manager_approval_subcommand_missing", "runtime-manager approval requires a subcommand: record | revoke | list")])
            return 1

        if command == "rollback":
            rollback_subcommand = getattr(args, "rollback_subcommand", "")
            if rollback_subcommand == "list":
                forward_command_id_arg = getattr(args, "forward_command_id", None)
                limit_arg = getattr(args, "limit", 50)
                runs = store.list_rollback_runs(forward_command_id=forward_command_id_arg, limit=limit_arg)
                if output_format == "json":
                    content = json.dumps({"rollback_runs": [_evidence_payload(r) for r in runs], "total": len(runs)}, indent=2) + "\n"
                else:
                    content = _render_rollback_list_text(runs)
                print(content, end="")
                return 0

            # rollback execute (default subcommand)
            evidence_id_arg = getattr(args, "evidence_id", None)
            if evidence_id_arg is None:
                print_fail([user_error("runtime_manager_rollback_missing_evidence_id", "runtime-manager rollback requires an evidence_id argument")])
                return 1
            try:
                evidence_id_int = int(evidence_id_arg)
            except (TypeError, ValueError):
                print_fail([user_error("runtime_manager_rollback_invalid_evidence_id", f"evidence_id must be an integer: {evidence_id_arg}")])
                return 1
            result = store.rollback_command(
                evidence_id_int,
                observation_center_path=root / "docs" / "operations" / "observation_center.toml",
            )
            if output_format == "json":
                content = json.dumps(_rollback_payload(result), indent=2) + "\n"
            else:
                content = _render_rollback_text(result)
            print(content, end="")
            return 0 if result.eligible and result.returncode == 0 else 1

        if command == "mcp-stdio":
            from adapters.runtime_manager_mcp_stdio.auth import AuthError
            from adapters.runtime_manager_mcp_stdio import run_stdio
            try:
                run_stdio(store)
            except ModuleNotFoundError as exc:
                if exc.name != "mcp":
                    raise
                print_fail([
                    user_error(
                        "runtime_manager_mcp_unavailable",
                        'MCP extra is not installed; run `python -m pip install -e ".[mcp]"` to enable runtime-manager mcp-stdio',
                    )
                ])
                return 1
            except AuthError as exc:
                print_fail([user_error("runtime_manager_mcp_auth_failed", str(exc))])
                return 1
            return 0

        if command == "policy":
            from core.runtime_manager_policy import explain_levels
            policy_subcommand = getattr(args, "policy_subcommand", "")
            if policy_subcommand == "explain-levels":
                levels = explain_levels()
                if output_format == "json":
                    content = json.dumps({"levels": levels}, indent=2) + "\n"
                else:
                    content = _render_explain_levels_text(levels)
                print(content, end="")
                return 0
            if policy_subcommand == "classify":
                command_id_arg = getattr(args, "command_id", "") or ""
                if not command_id_arg:
                    print_fail([user_error("runtime_manager_policy_classify_missing_id", "policy classify requires a command_id argument")])
                    return 1
                classification = store.classify_runtime_action(command_id_arg)
                if output_format == "json":
                    content = json.dumps({
                        "command_id": command_id_arg,
                        "autonomy_level": classification.autonomy_level,
                        "required_controls": list(classification.required_controls),
                        "blocked_reason": classification.blocked_reason,
                        "friction_budget": classification.friction_budget,
                        "rationale": classification.rationale,
                        "classification_is_not_permission": True,
                    }, indent=2) + "\n"
                else:
                    content = _render_classify_text(command_id_arg, classification)
                print(content, end="")
                return 0
            print_fail([user_error("runtime_manager_policy_subcommand_missing", "policy requires a subcommand: classify | explain-levels")])
            return 1

        if command == "integrity":
            integrity_subcommand = getattr(args, "integrity_subcommand", "")
            if integrity_subcommand == "check":
                report = store.check_integrity()
                if output_format == "json":
                    content = json.dumps(_integrity_payload(report), indent=2) + "\n"
                else:
                    content = _render_integrity_text(report)
                print(content, end="")
                return 0
            print_fail([user_error("runtime_manager_integrity_subcommand_missing", "integrity requires a subcommand: check")])
            return 1

        print_fail([user_error("runtime_manager_command_missing", "runtime-manager requires a subcommand")])
        return 1
    except RuntimeManagerStoreError as exc:
        print_fail([user_error("runtime_manager_failed", str(exc))])
        return 1


def _status_payload(status: RuntimeManagerStatus) -> dict[str, object]:
    return {
        "projection_role": "projection_only_not_authority",
        "canonical_source": "core.runtime_manager_store",
        "state": status.state,
        "selected_id": status.selected_id,
        "reason": status.reason,
        "gate_diagnostics": [
            {
                "code": item.code,
                "subject_id": item.subject_id,
                "details": list(item.details),
                "severity": item.severity,
                "blocking": item.blocking,
            }
            for item in status.gate_diagnostics
        ],
        "selection_audit": {
            "policy_version": status.selection_audit.policy_version,
            "sort_policy": list(status.selection_audit.sort_policy),
            "decision": status.selection_audit.decision,
            "selected_id": status.selection_audit.selected_id,
            "global_blockers": list(status.selection_audit.global_blockers),
            "eligible_ids": list(status.selection_audit.eligible_ids),
            "entries": [
                {
                    "observation_id": item.observation_id,
                    "status": item.status,
                    "priority": item.priority,
                    "source_index": item.source_index,
                    "eligible": item.eligible,
                    "sort_key": list(item.sort_key),
                    "blockers": list(item.blockers),
                }
                for item in status.selection_audit.entries
            ],
        },
        "source_authority": status.source_authority,
        "source_path": status.source_path,
        "source_sha256": status.source_sha256,
        "stale_source": status.stale_source,
        "observations": {
            "total": status.observations_total,
            "open": status.observations_open,
            "blocked": status.observations_blocked,
            "waiting": status.observations_waiting,
        },
        "decisions": {
            "total": status.decisions_total,
            "current": status.decisions_current,
        },
        "evidence": {
            "total": status.evidence_total,
            "accepted": status.evidence_accepted,
            "rejected": status.evidence_rejected,
        },
        "tools": {
            "total": status.tools_total,
            "enabled": status.tools_enabled,
        },
        "approvals": {
            "total": status.approvals_total,
            "current": status.approvals_current,
        },
        "events": {
            "total": status.events_total,
        },
        "leases": {
            "active": status.active_leases,
            "expired": status.leases_expired,
        },
        "replay_runs": {
            "total": status.replay_runs_total,
            "passed": status.replay_runs_passed,
            "failed": status.replay_runs_failed,
        },
        "validations": {
            "total": status.validations_total,
            "green": status.validations_green,
            "red": status.validations_red,
            "stale": status.validations_stale,
            "expired": status.validations_expired,
        },
        "stop_conditions": {
            "total": status.stop_conditions_total,
            "active": status.stop_conditions_active,
        },
        "commands": {
            "total": status.commands_total,
            "enabled": status.commands_enabled,
        },
        "execution_evidence": {
            "total": status.execution_evidence_total,
        },
    }


def _next_payload(status: RuntimeManagerStatus, next_item: RuntimeObservation | None) -> dict[str, object]:
    payload = _status_payload(status)
    payload["next"] = None if next_item is None else _observation_payload(next_item)
    return payload


def _observation_payload(observation: RuntimeObservation) -> dict[str, object]:
    return {
        "id": observation.id,
        "title": observation.title,
        "status": observation.status,
        "kind": observation.kind,
        "priority": observation.priority,
        "boundary": observation.boundary,
        "trigger": observation.trigger,
        "dependencies": list(observation.dependencies),
        "dependencies_satisfied": observation.dependencies_satisfied,
        "required_decisions": list(observation.required_decisions),
        "required_evidence": list(observation.required_evidence),
        "required_tools": list(observation.required_tools),
        "required_approvals": list(observation.required_approvals),
        "required_validations": list(observation.required_validations),
        "next_action": observation.next_action,
        "done_when": observation.done_when,
        "halt_if": observation.halt_if,
        "source_path": observation.source_path,
        "source_sha256": observation.source_sha256,
    }


def _eligibility_payload(result: CommandEligibilityResult) -> dict[str, object]:
    return {
        "projection_role": "projection_only_not_authority",
        "canonical_source": "core.runtime_manager_store",
        "eligible": result.eligible,
        "command_id": result.command_id,
        "reason": result.reason,
        "blockers": list(result.blockers),
        "selected_observation_id": result.selected_observation_id,
        "gate_diagnostics": [
            {"code": d.code, "subject_id": d.subject_id, "details": list(d.details), "severity": d.severity, "blocking": d.blocking}
            for d in result.gate_diagnostics
        ],
        "policy": None if result.policy is None else {
            "command_id": result.policy.command_id,
            "argv_prefix": list(result.policy.argv_prefix),
            "path_scope": result.policy.path_scope,
            "side_effect_class": result.policy.side_effect_class,
            "network_allowed": result.policy.network_allowed,
            "timeout_seconds": result.policy.timeout_seconds,
            "output_budget_bytes": result.policy.output_budget_bytes,
            "sensitive_output_policy": result.policy.sensitive_output_policy,
            "approval_requirement": result.policy.approval_requirement,
            "rollback_class": result.policy.rollback_class,
            "status": result.policy.status,
        },
    }


def _render_eligibility_text(result: CommandEligibilityResult) -> str:
    lines = [
        "OK" if result.eligible else "FAIL",
        "RUNTIME MANAGER CHECK",
        "mode: read-only enforcement check",
        "projection_role: projection_only_not_authority",
        "canonical_source: core.runtime_manager_store",
        f"eligible: {str(result.eligible).lower()}",
        f"command_id: {result.command_id}",
        f"reason: {result.reason}",
        f"blockers: {', '.join(result.blockers) or '<none>'}",
        f"selected_observation_id: {result.selected_observation_id or '<none>'}",
        f"gate_diagnostics_total: {len(result.gate_diagnostics)}",
    ]
    if result.policy is not None:
        lines.extend([
            f"policy_path_scope: {result.policy.path_scope}",
            f"policy_side_effect_class: {result.policy.side_effect_class}",
            f"policy_network_allowed: {str(result.policy.network_allowed).lower()}",
            f"policy_timeout_seconds: {result.policy.timeout_seconds}",
            f"policy_output_budget_bytes: {result.policy.output_budget_bytes}",
            f"policy_approval_requirement: {result.policy.approval_requirement}",
            f"policy_rollback_class: {result.policy.rollback_class}",
            f"policy_status: {result.policy.status}",
        ])
    return "\n".join(lines) + "\n"


def _run_payload(result: CommandRunResult) -> dict[str, object]:
    return {
        "projection_role": "projection_only_not_authority",
        "canonical_source": "core.runtime_manager_store",
        "eligible": result.eligible,
        "command_id": result.command_id,
        "observation_id": result.observation_id,
        "argv": list(result.argv),
        "returncode": result.returncode,
        "timed_out": result.timed_out,
        "duration_seconds": result.duration_seconds,
        "stdout_truncated": result.stdout_truncated,
        "stderr_truncated": result.stderr_truncated,
        "blockers": list(result.blockers),
        "event_id": result.event_id,
        "evidence_id": result.evidence_id,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


def _render_run_text(result: CommandRunResult) -> str:
    status = "OK" if (result.eligible and result.returncode == 0) else "FAIL"
    lines = [
        status,
        "RUNTIME MANAGER RUN",
        "mode: constrained subprocess execution",
        "projection_role: projection_only_not_authority",
        "canonical_source: core.runtime_manager_store",
        f"eligible: {str(result.eligible).lower()}",
        f"command_id: {result.command_id}",
        f"observation_id: {result.observation_id or '<none>'}",
        f"argv: {' '.join(result.argv) or '<none>'}",
        f"returncode: {result.returncode}",
        f"timed_out: {str(result.timed_out).lower()}",
        f"duration_seconds: {result.duration_seconds}",
        f"stdout_truncated: {str(result.stdout_truncated).lower()}",
        f"stderr_truncated: {str(result.stderr_truncated).lower()}",
        f"blockers: {', '.join(result.blockers) or '<none>'}",
        f"event_id: {result.event_id}",
        f"evidence_id: {result.evidence_id}",
    ]
    if result.stdout:
        lines.append(f"stdout: {result.stdout}")
    if result.stderr:
        lines.append(f"stderr: {result.stderr}")
    return "\n".join(lines) + "\n"


def _print_status(status: RuntimeManagerStatus) -> None:
    print(_render_status_text(status), end="")


def _print_next(status: RuntimeManagerStatus, next_item: RuntimeObservation | None) -> None:
    print(_render_next_text(status, next_item), end="")


def _render_status_text(status: RuntimeManagerStatus) -> str:
    lines = [
        "OK",
        "RUNTIME MANAGER",
        "mode: read-only status",
        "projection_role: projection_only_not_authority",
        "canonical_source: core.runtime_manager_store",
        f"state: {status.state}",
        f"selected_id: {status.selected_id or '<none>'}",
        f"reason: {status.reason}",
        f"gate_diagnostics_total: {len(status.gate_diagnostics)}",
        *[
            f"gate_diagnostic: {item.code} subject={item.subject_id} details={','.join(item.details) or '<none>'} "
            f"severity={item.severity} blocking={str(item.blocking).lower()}"
            for item in status.gate_diagnostics
        ],
        f"selection_audit_decision: {status.selection_audit.decision}",
        f"selection_audit_policy_version: {status.selection_audit.policy_version}",
        f"selection_audit_sort_policy: {', '.join(status.selection_audit.sort_policy)}",
        f"selection_audit_selected_id: {status.selection_audit.selected_id or '<none>'}",
        f"selection_audit_global_blockers: {', '.join(status.selection_audit.global_blockers) or '<none>'}",
        f"selection_audit_eligible_ids: {', '.join(status.selection_audit.eligible_ids) or '<none>'}",
        f"selection_audit_entries_total: {len(status.selection_audit.entries)}",
        f"source_authority: {status.source_authority}",
        f"source_path: {status.source_path}",
        f"source_sha256: {status.source_sha256}",
        f"stale_source: {str(status.stale_source).lower()}",
        f"observations_total: {status.observations_total}",
        f"observations_open: {status.observations_open}",
        f"observations_blocked: {status.observations_blocked}",
        f"observations_waiting: {status.observations_waiting}",
        f"decisions_total: {status.decisions_total}",
        f"decisions_current: {status.decisions_current}",
        f"evidence_total: {status.evidence_total}",
        f"evidence_accepted: {status.evidence_accepted}",
        f"evidence_rejected: {status.evidence_rejected}",
        f"tools_total: {status.tools_total}",
        f"tools_enabled: {status.tools_enabled}",
        f"approvals_total: {status.approvals_total}",
        f"approvals_current: {status.approvals_current}",
        f"events_total: {status.events_total}",
        f"active_leases: {status.active_leases}",
        f"leases_expired: {status.leases_expired}",
        f"replay_runs_total: {status.replay_runs_total}",
        f"replay_runs_passed: {status.replay_runs_passed}",
        f"replay_runs_failed: {status.replay_runs_failed}",
        f"validations_total: {status.validations_total}",
        f"validations_green: {status.validations_green}",
        f"validations_red: {status.validations_red}",
        f"validations_stale: {status.validations_stale}",
        f"validations_expired: {status.validations_expired}",
        f"stop_conditions_total: {status.stop_conditions_total}",
        f"stop_conditions_active: {status.stop_conditions_active}",
        f"commands_total: {status.commands_total}",
        f"commands_enabled: {status.commands_enabled}",
        f"execution_evidence_total: {status.execution_evidence_total}",
    ]
    return "\n".join(lines) + "\n"


def _render_next_text(status: RuntimeManagerStatus, next_item: RuntimeObservation | None) -> str:
    lines = [
        "OK" if next_item is not None else "FAIL",
        "RUNTIME MANAGER NEXT",
        "mode: read-only selection",
        "projection_role: projection_only_not_authority",
        "canonical_source: core.runtime_manager_store",
        f"state: {status.state}",
        f"reason: {status.reason}",
        f"gate_diagnostics_total: {len(status.gate_diagnostics)}",
        *[
            f"gate_diagnostic: {item.code} subject={item.subject_id} details={','.join(item.details) or '<none>'} "
            f"severity={item.severity} blocking={str(item.blocking).lower()}"
            for item in status.gate_diagnostics
        ],
        f"selection_audit_decision: {status.selection_audit.decision}",
        f"selection_audit_policy_version: {status.selection_audit.policy_version}",
        f"selection_audit_sort_policy: {', '.join(status.selection_audit.sort_policy)}",
        f"selection_audit_selected_id: {status.selection_audit.selected_id or '<none>'}",
        f"selection_audit_global_blockers: {', '.join(status.selection_audit.global_blockers) or '<none>'}",
        f"selection_audit_eligible_ids: {', '.join(status.selection_audit.eligible_ids) or '<none>'}",
        f"selection_audit_entries_total: {len(status.selection_audit.entries)}",
    ]
    if next_item is None:
        lines.append("selected_id: <none>")
        return "\n".join(lines) + "\n"
    lines.extend(
        [
            f"selected_id: {next_item.id}",
            f"title: {next_item.title}",
            f"priority: {next_item.priority}",
            f"status: {next_item.status}",
            f"trigger: {next_item.trigger}",
            f"boundary: {next_item.boundary}",
            f"required_decisions: {', '.join(next_item.required_decisions) or '<none>'}",
            f"required_evidence: {', '.join(next_item.required_evidence) or '<none>'}",
            f"required_tools: {', '.join(next_item.required_tools) or '<none>'}",
            f"required_approvals: {', '.join(next_item.required_approvals) or '<none>'}",
            f"required_validations: {', '.join(next_item.required_validations) or '<none>'}",
            f"next_action: {next_item.next_action}",
        ]
    )
    return "\n".join(lines) + "\n"


def _write_projection(root: Path, output_path: str | Path, content: str, status: RuntimeManagerStatus) -> Path:
    target = _resolve_projection_target(root, output_path)
    _reject_projection_target(root, target, status)
    tmp_path = target.with_suffix(f"{target.suffix}.tmp")
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp_path.write_text(content, encoding="utf-8", newline="\n")
        os.replace(tmp_path, target)
    except OSError as exc:
        raise RuntimeManagerStoreError(f"failed to write projection file: {target}") from exc
    finally:
        try:
            if tmp_path.exists():
                tmp_path.unlink()
        except OSError:
            pass
    return target


def _resolve_projection_target(root: Path, output_path: str | Path) -> Path:
    target = Path(output_path)
    if not target.is_absolute():
        target = root / target
    return target.resolve()


def _reject_projection_target(root: Path, target: Path, status: RuntimeManagerStatus) -> None:
    store = StateStore(root)
    if store.is_runtime_path(target):
        raise RuntimeManagerStoreError(f"projection output path is reserved for runtime files: {target}")

    source_path = Path(status.source_path)
    if source_path and not source_path.is_absolute():
        source_path = root / source_path
    if target == source_path.resolve():
        raise RuntimeManagerStoreError(f"projection output path is the imported queue authority: {target}")

    for protected_name in ("SYSTEM_STATE.md", "OPPORTUNITY_MAP.md"):
        protected_path = (root / "docs" / "operations" / protected_name).resolve()
        if target == protected_path:
            raise RuntimeManagerStoreError(f"projection output path is a governed operational projection: {target}")

    if not store.state_path.exists():
        return
    try:
        snapshot = store.read_snapshot()
    except (StateStoreError, StateValidationError) as exc:
        raise RuntimeManagerStoreError(f"failed to read checkpoint state before projection write: {exc}") from exc
    registered_source_paths = {(store.root / source.path).resolve() for source in snapshot.sources}
    if target in registered_source_paths:
        raise RuntimeManagerStoreError(f"projection output path is reserved for registered source files: {target}")


def _trace_payload(trace: RuntimeTrace, *, include_events: bool = True) -> dict[str, object]:
    payload: dict[str, object] = {
        "trace_id": trace.trace_id,
        "operation": trace.operation,
        "subject_id": trace.subject_id,
        "status": trace.status,
        "policy_version": trace.policy_version,
        "causation_id": trace.causation_id,
        "correlation_id": trace.correlation_id,
        "input_digest": trace.input_digest,
        "output_digest": trace.output_digest,
        "started_at": trace.started_at,
        "finished_at": trace.finished_at,
        "event_count": trace.event_count,
        "trace_is_not_permission": True,
    }
    if include_events:
        payload["events"] = [
            {
                "trace_event_id": event.trace_event_id,
                "sequence": event.sequence,
                "event_name": event.event_name,
                "subject_id": event.subject_id,
                "payload_digest": event.payload_digest,
                "payload": json.loads(event.payload_json),
                "created_at": event.created_at,
            }
            for event in trace.events
        ]
    return payload


def _render_trace_text(trace: RuntimeTrace | None, trace_id: str) -> str:
    if trace is None:
        return f"FAIL\nRUNTIME MANAGER TRACE SHOW\ntrace_id: {trace_id}\nfound: false\n"
    lines = [
        "OK",
        "RUNTIME MANAGER TRACE SHOW",
        f"trace_id: {trace.trace_id}",
        f"operation: {trace.operation}",
        f"subject_id: {trace.subject_id}",
        f"status: {trace.status}",
        f"policy_version: {trace.policy_version}",
        f"input_digest: {trace.input_digest}",
        f"output_digest: {trace.output_digest}",
        f"event_count: {trace.event_count}",
        "trace_is_not_permission: true",
    ]
    for event in trace.events:
        lines.append(f"event[{event.sequence}]: {event.event_name} {event.payload_digest}")
    return "\n".join(lines) + "\n"


def _render_trace_list_text(traces: tuple[RuntimeTrace, ...]) -> str:
    lines = ["OK", "RUNTIME MANAGER TRACE LIST", f"total: {len(traces)}"]
    for trace in traces:
        lines.append(
            f"trace_id={trace.trace_id} operation={trace.operation} subject_id={trace.subject_id} "
            f"status={trace.status} events={trace.event_count} started_at={trace.started_at}"
        )
    return "\n".join(lines) + "\n"


def _metrics_payload(metrics: RuntimeManagerMetrics) -> dict[str, object]:
    return {
        "generated_at": metrics.generated_at,
        "runs_total": metrics.runs_total,
        "runs_passed": metrics.runs_passed,
        "runs_failed": metrics.runs_failed,
        "runs_timed_out": metrics.runs_timed_out,
        "execution_evidence_total": metrics.execution_evidence_total,
        "approvals_current": metrics.approvals_current,
        "approvals_revoked": metrics.approvals_revoked,
        "validations_green": metrics.validations_green,
        "validations_red": metrics.validations_red,
        "validations_stale": metrics.validations_stale,
        "validations_expired": metrics.validations_expired,
        "stop_conditions_active": metrics.stop_conditions_active,
        "stop_conditions_resolved": metrics.stop_conditions_resolved,
        "leases_active": metrics.leases_active,
        "leases_expired": metrics.leases_expired,
        "leases_reclaimed": metrics.leases_reclaimed,
        "rollback_runs_total": metrics.rollback_runs_total,
        "rollback_runs_passed": metrics.rollback_runs_passed,
        "rollback_runs_failed": metrics.rollback_runs_failed,
        "traces_total": metrics.traces_total,
        "traces_incomplete": metrics.traces_incomplete,
        "evals_total": metrics.evals_total,
        "evals_passed": metrics.evals_passed,
        "evals_failed": metrics.evals_failed,
    }


def _render_metrics_text(metrics: RuntimeManagerMetrics) -> str:
    lines = ["OK", "RUNTIME MANAGER METRICS"]
    for key, value in _metrics_payload(metrics).items():
        lines.append(f"{key}: {value}")
    return "\n".join(lines) + "\n"


def _replay_payload(replay: RuntimeReplayResult) -> dict[str, object]:
    return {
        "scenario_id": replay.scenario_id,
        "passed": replay.passed,
        "replay_digest": replay.replay_digest,
        "authority": replay.authority,
        "checks": [
            {"check_id": item.check_id, "passed": item.passed, "reason": item.reason}
            for item in replay.checks
        ],
    }


def _render_replay_text(replay: RuntimeReplayResult) -> str:
    lines = [
        "OK" if replay.passed else "FAIL",
        "RUNTIME MANAGER REPLAY",
        f"scenario_id: {replay.scenario_id}",
        f"passed: {str(replay.passed).lower()}",
        f"replay_digest: {replay.replay_digest}",
        f"authority: {replay.authority}",
    ]
    for check in replay.checks:
        lines.append(f"check={check.check_id} passed={str(check.passed).lower()} reason={check.reason}")
    return "\n".join(lines) + "\n"


def _evidence_payload(evidence: ExecutionEvidence) -> dict[str, object]:
    return {
        "evidence_id": evidence.evidence_id,
        "command_id": evidence.command_id,
        "observation_id": evidence.observation_id,
        "approval_id": evidence.approval_id,
        "action_fingerprint": evidence.action_fingerprint,
        "rollback_class": evidence.rollback_class,
        "returncode": evidence.returncode,
        "timed_out": evidence.timed_out,
        "duration_seconds": evidence.duration_seconds,
        "stdout_digest": evidence.stdout_digest,
        "stderr_digest": evidence.stderr_digest,
        "stdout_truncated": evidence.stdout_truncated,
        "stderr_truncated": evidence.stderr_truncated,
        "output_redacted": evidence.output_redacted,
        "event_id": evidence.event_id,
        "recorded_at": evidence.recorded_at,
    }


def _render_evidence_text(evidence: ExecutionEvidence | None, evidence_id: int) -> str:
    if evidence is None:
        return f"FAIL\nRUNTIME MANAGER EVIDENCE SHOW\nevidence_id: {evidence_id}\nfound: false\n"
    lines = [
        "OK",
        "RUNTIME MANAGER EVIDENCE SHOW",
        f"evidence_id: {evidence.evidence_id}",
        f"command_id: {evidence.command_id}",
        f"observation_id: {evidence.observation_id}",
        f"approval_id: {evidence.approval_id or '<none>'}",
        f"action_fingerprint: {evidence.action_fingerprint}",
        f"rollback_class: {evidence.rollback_class}",
        f"returncode: {evidence.returncode}",
        f"timed_out: {str(evidence.timed_out).lower()}",
        f"duration_seconds: {evidence.duration_seconds}",
        f"stdout_digest: {evidence.stdout_digest}",
        f"stderr_digest: {evidence.stderr_digest}",
        f"stdout_truncated: {str(evidence.stdout_truncated).lower()}",
        f"stderr_truncated: {str(evidence.stderr_truncated).lower()}",
        f"output_redacted: {str(evidence.output_redacted).lower()}",
        f"event_id: {evidence.event_id}",
        f"recorded_at: {evidence.recorded_at}",
    ]
    return "\n".join(lines) + "\n"


def _render_evidence_list_text(evidence_rows: tuple[ExecutionEvidence, ...]) -> str:
    lines = [
        "OK",
        "RUNTIME MANAGER EVIDENCE LIST",
        f"total: {len(evidence_rows)}",
    ]
    for ev in evidence_rows:
        lines.append(
            f"evidence_id={ev.evidence_id} command_id={ev.command_id} observation_id={ev.observation_id} "
            f"returncode={ev.returncode} timed_out={str(ev.timed_out).lower()} "
            f"duration_seconds={ev.duration_seconds} recorded_at={ev.recorded_at}"
        )
    return "\n".join(lines) + "\n"


# ── Lease ──────────────────────────────────────────────────────────────────

def _lease_payload(lease: AcquiredLease) -> dict[str, object]:
    return {
        "lease_id": lease.lease_id,
        "observation_id": lease.observation_id,
        "owner": lease.owner,
        "status": lease.status,
        "acquired_at": lease.acquired_at,
        "expires_at": lease.expires_at,
        "renewed_at": lease.renewed_at,
        "reason": lease.reason,
        "released_at": lease.released_at,
        "event_id": lease.event_id,
    }


def _render_lease_text(lease: AcquiredLease, header: str) -> str:
    lines = [
        "OK", header,
        f"lease_id: {lease.lease_id}",
        f"observation_id: {lease.observation_id}",
        f"owner: {lease.owner}",
        f"status: {lease.status}",
        f"acquired_at: {lease.acquired_at}",
        f"expires_at: {lease.expires_at or '<none>'}",
        f"renewed_at: {lease.renewed_at or '<none>'}",
        f"reason: {lease.reason or '<none>'}",
        f"released_at: {lease.released_at or '<none>'}",
        f"event_id: {lease.event_id}",
    ]
    return "\n".join(lines) + "\n"


def _render_lease_list_text(leases: tuple[AcquiredLease, ...]) -> str:
    lines = ["OK", "RUNTIME MANAGER LEASE LIST", f"total: {len(leases)}"]
    for l in leases:
        lines.append(
            f"lease_id={l.lease_id} observation_id={l.observation_id} owner={l.owner} "
            f"status={l.status} expires_at={l.expires_at or '<none>'} acquired_at={l.acquired_at}"
        )
    return "\n".join(lines) + "\n"


# ── Stop condition ──────────────────────────────────────────────────────────

def _stop_condition_payload(sc: ManagedStopCondition) -> dict[str, object]:
    return {
        "stop_condition_id": sc.stop_condition_id,
        "subject_id": sc.subject_id,
        "status": sc.status,
        "severity": sc.severity,
        "opened_at": sc.opened_at,
        "resolved_at": sc.resolved_at,
        "reason": sc.reason,
        "event_id": sc.event_id,
    }


def _render_stop_condition_text(sc: ManagedStopCondition, header: str) -> str:
    lines = [
        "OK", header,
        f"stop_condition_id: {sc.stop_condition_id}",
        f"subject_id: {sc.subject_id}",
        f"status: {sc.status}",
        f"severity: {sc.severity}",
        f"opened_at: {sc.opened_at}",
        f"resolved_at: {sc.resolved_at or '<none>'}",
        f"reason: {sc.reason}",
        f"event_id: {sc.event_id}",
    ]
    return "\n".join(lines) + "\n"


def _render_stop_condition_list_text(conditions: tuple[ManagedStopCondition, ...]) -> str:
    lines = ["OK", "RUNTIME MANAGER STOP LIST", f"total: {len(conditions)}"]
    for sc in conditions:
        lines.append(
            f"stop_condition_id={sc.stop_condition_id} subject_id={sc.subject_id} "
            f"status={sc.status} severity={sc.severity} opened_at={sc.opened_at}"
        )
    return "\n".join(lines) + "\n"


# ── Validation ─────────────────────────────────────────────────────────────

def _validation_payload(mv: ManagedValidation) -> dict[str, object]:
    return {
        "validation_id": mv.validation_id,
        "subject_id": mv.subject_id,
        "status": mv.status,
        "checked_at": mv.checked_at,
        "fresh_until": mv.fresh_until,
        "command_id": mv.command_id,
        "reason": mv.reason,
        "event_id": mv.event_id,
    }


def _render_validation_text(mv: ManagedValidation, header: str) -> str:
    lines = [
        "OK", header,
        f"validation_id: {mv.validation_id}",
        f"subject_id: {mv.subject_id}",
        f"status: {mv.status}",
        f"checked_at: {mv.checked_at}",
        f"fresh_until: {mv.fresh_until or '<none>'}",
        f"command_id: {mv.command_id or '<none>'}",
        f"reason: {mv.reason or '<none>'}",
        f"event_id: {mv.event_id}",
    ]
    return "\n".join(lines) + "\n"


# ── Approval ───────────────────────────────────────────────────────────────

def _approval_payload(ar: ApprovalRecord) -> dict[str, object]:
    return {
        "approval_id": ar.approval_id,
        "subject_id": ar.subject_id,
        "action_fingerprint": ar.action_fingerprint,
        "command_id": ar.command_id,
        "actor": ar.actor,
        "scope": ar.scope,
        "status": ar.status,
        "granted_at": ar.granted_at,
        "expires_at": ar.expires_at,
        "revoked_at": ar.revoked_at,
        "event_id": ar.event_id,
    }


def _render_approval_text(ar: ApprovalRecord, header: str) -> str:
    lines = [
        "OK", header,
        f"approval_id: {ar.approval_id}",
        f"subject_id: {ar.subject_id}",
        f"action_fingerprint: {ar.action_fingerprint}",
        f"command_id: {ar.command_id}",
        f"actor: {ar.actor}",
        f"scope: {ar.scope}",
        f"status: {ar.status}",
        f"granted_at: {ar.granted_at}",
        f"expires_at: {ar.expires_at or '<none>'}",
        f"revoked_at: {ar.revoked_at or '<none>'}",
        f"event_id: {ar.event_id}",
    ]
    return "\n".join(lines) + "\n"


def _render_approval_list_text(approvals: tuple[ApprovalRecord, ...]) -> str:
    lines = ["OK", "RUNTIME MANAGER APPROVAL LIST", f"total: {len(approvals)}"]
    for ar in approvals:
        lines.append(
            f"approval_id={ar.approval_id} command_id={ar.command_id} subject_id={ar.subject_id} "
            f"status={ar.status} actor={ar.actor} granted_at={ar.granted_at}"
        )
    return "\n".join(lines) + "\n"


# ── Rollback ───────────────────────────────────────────────────────────────

def _rollback_payload(result: RollbackResult) -> dict[str, object]:
    return {
        "projection_role": "projection_only_not_authority",
        "canonical_source": "core.runtime_manager_store",
        "eligible": result.eligible,
        "original_evidence_id": result.original_evidence_id,
        "rollback_evidence_id": result.rollback_evidence_id,
        "command_id": result.command_id,
        "argv": list(result.argv),
        "returncode": result.returncode,
        "timed_out": result.timed_out,
        "duration_seconds": result.duration_seconds,
        "blockers": list(result.blockers),
        "event_id": result.event_id,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


def _render_rollback_text(result: RollbackResult) -> str:
    status = "OK" if (result.eligible and result.returncode == 0) else "FAIL"
    lines = [
        status,
        "RUNTIME MANAGER ROLLBACK",
        "mode: constrained rollback execution",
        "projection_role: projection_only_not_authority",
        "canonical_source: core.runtime_manager_store",
        f"eligible: {str(result.eligible).lower()}",
        f"original_evidence_id: {result.original_evidence_id}",
        f"rollback_evidence_id: {result.rollback_evidence_id}",
        f"command_id: {result.command_id or '<none>'}",
        f"argv: {' '.join(result.argv) or '<none>'}",
        f"returncode: {result.returncode}",
        f"timed_out: {str(result.timed_out).lower()}",
        f"duration_seconds: {result.duration_seconds}",
        f"blockers: {', '.join(result.blockers) or '<none>'}",
        f"event_id: {result.event_id}",
    ]
    if result.stdout:
        lines.append(f"stdout: {result.stdout}")
    if result.stderr:
        lines.append(f"stderr: {result.stderr}")
    return "\n".join(lines) + "\n"


def _render_rollback_list_text(runs: tuple[ExecutionEvidence, ...]) -> str:
    lines = ["OK", "RUNTIME MANAGER ROLLBACK LIST", f"total: {len(runs)}"]
    for ev in runs:
        lines.append(
            f"evidence_id={ev.evidence_id} command_id={ev.command_id} observation_id={ev.observation_id} "
            f"returncode={ev.returncode} recorded_at={ev.recorded_at}"
        )
    return "\n".join(lines) + "\n"


# ── Policy ─────────────────────────────────────────────────────────────────

def _render_explain_levels_text(levels: list[dict]) -> str:
    lines = ["OK", "RUNTIME MANAGER POLICY EXPLAIN-LEVELS"]
    for lv in levels:
        mcp = "yes" if lv.get("mcp_executable") else "no"
        controls = ", ".join(lv.get("required_controls") or []) or "<none>"
        lines.append(
            f"level={lv['level']} friction_budget={lv['friction_budget']} "
            f"mcp_executable={mcp} required_controls=[{controls}]"
        )
        lines.append(f"  description: {lv.get('description', '')}")
    lines.append("classification_is_not_permission: true")
    return "\n".join(lines) + "\n"


def _render_classify_text(command_id: str, classification) -> str:
    blocked = classification.blocked_reason or "<none>"
    controls = ", ".join(classification.required_controls) or "<none>"
    lines = [
        "OK",
        "RUNTIME MANAGER POLICY CLASSIFY",
        f"command_id: {command_id}",
        f"autonomy_level: {classification.autonomy_level}",
        f"friction_budget: {classification.friction_budget}",
        f"blocked_reason: {blocked}",
        f"required_controls: {controls}",
        f"rationale: {classification.rationale}",
        "classification_is_not_permission: true",
    ]
    return "\n".join(lines) + "\n"


def _integrity_payload(report: RuntimeIntegrityReport) -> dict[str, object]:
    return {
        "generated_at": report.generated_at,
        "orphan_trace_events": report.orphan_trace_events,
        "incomplete_old_traces": report.incomplete_old_traces,
        "expired_active_leases": report.expired_active_leases,
        "expired_active_tokens": report.expired_active_tokens,
        "stale_rate_buckets": report.stale_rate_buckets,
        "evidence_without_trace": report.evidence_without_trace,
        "policy_counter_plausibility": report.policy_counter_plausibility,
        "issues": list(report.issues),
        "integrity_report_is_not_permission": True,
    }


def _render_integrity_text(report: RuntimeIntegrityReport) -> str:
    status = "CLEAN" if not report.issues else "ISSUES_FOUND"
    lines = [
        "OK",
        "RUNTIME MANAGER INTEGRITY CHECK",
        f"generated_at: {report.generated_at}",
        f"status: {status}",
        f"orphan_trace_events: {report.orphan_trace_events}",
        f"incomplete_old_traces: {report.incomplete_old_traces}",
        f"expired_active_leases: {report.expired_active_leases}",
        f"expired_active_tokens: {report.expired_active_tokens}",
        f"stale_rate_buckets: {report.stale_rate_buckets}",
        f"evidence_without_trace: {report.evidence_without_trace}",
        f"policy_counter_plausibility: {report.policy_counter_plausibility}",
    ]
    if report.issues:
        lines.append(f"issues: {', '.join(report.issues)}")
    else:
        lines.append("issues: <none>")
    lines.append("integrity_report_is_not_permission: true")
    return "\n".join(lines) + "\n"
