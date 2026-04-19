"""Implementation of the alpha-runtime verify command."""

from __future__ import annotations

from pathlib import Path

from cli.commands._session_ownership import resolve_session_token
from cli.output import print_fail, print_ok, state_store_user_error, state_store_user_errors, user_error
from core.agent_runtime import iter_command_checks
from core.state_store import StateStore, StateStoreError, StateValidationError
from core.verification_runtime import (
    VerificationRuntimeError,
    covers_required_verification_scope,
    execute_verification_cycle,
)

def run_verify(root: Path, args) -> int:
    """Run the registered verification commands for the active alpha-runtime plan."""
    store = StateStore(root)
    try:
        result, verification_record, updated = execute_verification_cycle(
            root,
            store,
            command_ids=args.command_id or None,
            expected_session_token=resolve_session_token(args),
        )
        if not result["ok"] or verification_record is None or updated is None:
            print_fail(
                [
                    user_error("verify_blocked", "verify blocked because validation failed"),
                    *state_store_user_errors(root, result["errors"]),
                ]
            )
            return 1
    except StateValidationError as exc:
        print_fail(exc.errors)
        return 1
    except VerificationRuntimeError as exc:
        print_fail([user_error("verification_failed", str(exc))])
        return 1
    except StateStoreError as exc:
        print_fail([state_store_user_error(root, "operation_failed", str(exc))])
        return 1

    command_checks = iter_command_checks(verification_record)
    executed_command_ids = [
        item["command_id"]
        for item in command_checks
        if isinstance(item.get("command_id"), str)
    ]
    full_required_coverage = covers_required_verification_scope(
        verification_record["required_command_ids"],
        executed_command_ids,
    )
    final_verification = updated["agent_runtime"]["verification"]
    lines = [
        (
            "verification_passed: registered checks executed"
            if verification_record["status"] == "passed" and full_required_coverage
            else "verification_partial: selected checks passed but required coverage is incomplete"
            if verification_record["status"] == "passed"
            else f"verification_{verification_record['status']}: registered checks executed"
        ),
        f"revision: {updated['revision']}",
        f"checks: {len(verification_record['checks'])}",
    ]
    state_check = verification_record.get("state_check", {})
    if isinstance(state_check, dict):
        lines.append(f"state_check: {state_check.get('status', 'idle')}")
    required_total = len(
        [
            command_id
            for command_id in verification_record["required_command_ids"]
            if isinstance(command_id, str) and command_id
        ]
    )
    executed_total = len(executed_command_ids)
    if required_total:
        coverage_state = "full" if full_required_coverage else "partial"
        lines.append(f"coverage: {coverage_state} ({executed_total}/{required_total} required commands)")
    lines.append(f"gate_status: {final_verification['status']}")
    lines.append(f"pending_actions: {len(final_verification['pending_action_ids'])}")
    for item in command_checks:
        lines.append(f"- {item['command_id']}: {item['status']} (exit_code={item['exit_code']})")
    if verification_record["status"] != "passed":
        failure_items = [
            user_error(item["command_id"], item["artifact_ref"] or item.get("message", ""))
            for item in command_checks
            if item["status"] != "passed"
        ]
        if isinstance(state_check, dict) and state_check.get("status") == "failed":
            failure_items.insert(0, user_error("state_check", state_check.get("message", "")))
        print_fail(
            [
                user_error("verification_failed", "one or more verification commands failed"),
                *failure_items,
            ]
        )
        return 1
    print_ok(lines)
    return 0 if full_required_coverage else 1
