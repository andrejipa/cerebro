"""Implementation of the validate command."""

from __future__ import annotations

from pathlib import Path

from cli.output import print_fail, print_ok, state_store_user_error, state_store_user_errors
from core.state_store import StateStore, StateStoreError, StateValidationError


def run_validate(root: Path, args=None) -> int:
    store = StateStore(root)
    retention_report = bool(getattr(args, "retention_report", False))
    retention_apply = bool(getattr(args, "retention_apply", False))
    try:
        result = store.validate_state()
    except StateValidationError as exc:
        print_fail(exc.errors)
        return 1
    except StateStoreError as exc:
        print_fail([state_store_user_error(root, "operation_failed", str(exc))])
        return 1

    if result["ok"]:
        snapshot = result["snapshot"]
        lines = [
            "validation_passed: context is valid for runtime use",
            f"sources: {len(snapshot.sources)}",
            f"revision: {snapshot.revision}",
        ]
        if retention_report or retention_apply:
            try:
                retention = (
                    store.apply_retention(expected_revision=result["revision"])
                    if retention_apply
                    else store.inspect_retention(expected_revision=result["revision"])
                )
            except StateStoreError as exc:
                print_fail([state_store_user_error(root, "operation_failed", str(exc))])
                return 1
            policy = retention["policy"]
            lines.extend(
                [
                    "retention_policy: manual validate-gated report/apply",
                    f"retention_events_floor: keep all consolidations + last {policy['event_log']['retain_latest_non_consolidation_events']} non-consolidation events in events.jsonl",
                    f"retention_verification_floor: keep live refs + last {policy['artifacts']['retain_latest_unreferenced_verification_groups']} unreferenced verification groups",
                    f"retention_action_floor: keep live refs + last {policy['artifacts']['retain_latest_unreferenced_action_groups']} unreferenced action groups",
                    f"retention_event_candidates: {retention['events']['archived_line_count']} lines / {retention['events']['archived_bytes']} bytes",
                    f"retention_artifact_candidates: {retention['artifacts']['archive_group_count']} groups / {retention['artifacts']['archive_file_count']} files / {retention['artifacts']['archive_bytes']} bytes",
                    f"retention_unknown_surfaces_blocked: {retention['artifacts']['blocked_unknown_group_count']}",
                ]
            )
            if retention_apply:
                if retention["applied"]:
                    lines.extend(
                        [
                            "retention_applied: governed runtime cleanup archived only eligible surfaces",
                            f"retention_archive_root: {retention['archive_root_ref']}",
                            f"retention_event_id: {retention['retention_event_id']}",
                        ]
                    )
                else:
                    lines.append("retention_applied: no eligible cleanup candidates")
            else:
                lines.append("retention_next_step: rerun `cerebro validate --retention-apply` to archive the eligible set")
        print_ok(lines)
        return 0

    print_fail(state_store_user_errors(root, result["errors"]))
    return 1
