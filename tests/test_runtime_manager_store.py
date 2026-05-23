from __future__ import annotations

import hashlib
import json
import sqlite3
import sys
import tempfile
import tomllib
import unittest
from contextlib import closing
from pathlib import Path

from core.runtime_manager_policy import decide_runtime_state
from core.runtime_manager_store import AcquiredLease, ApprovalRecord, CommandRunResult, ExecutionEvidence, ManagedStopCondition, ManagedValidation, RollbackPolicy, RollbackResult, RuntimeManagerStore, RuntimeManagerStoreError


def _write_observation_center(root: Path, observations: str) -> Path:
    operations = root / "docs" / "operations"
    operations.mkdir(parents=True, exist_ok=True)
    path = operations / "observation_center.toml"
    path.write_text(
        f"""
[center]
version = 1
queue_authority = "machine-primary"
single_flight = true

[projections]
system_state = "projection only"
opportunity_map = "projection only"

{observations}
""".lstrip(),
        encoding="utf-8",
    )
    return path


def _observation(
    observation_id: str,
    *,
    status: str = "open",
    priority: str = "medium",
    dependencies_satisfied: str = "true",
    trigger: str = "FORMAL_RESUME_TRIGGER_RUNTIME_MANAGER_PHASE_1.md",
    boundary: str = "core/read-model only",
) -> str:
    return f"""
[[observations]]
id = "{observation_id}"
title = "{observation_id} title"
status = "{status}"
kind = "slice"
priority = "{priority}"
boundary = "{boundary}"
trigger = "{trigger}"
dependencies = ["dep-a"]
dependencies_satisfied = {dependencies_satisfied}
next_action = "do {observation_id}"
done_when = "done"
halt_if = "halt"
""".lstrip()


def _diagnostics(status) -> dict[tuple[str, str], tuple[str, ...]]:
    return {
        (diagnostic.code, diagnostic.subject_id): diagnostic.details
        for diagnostic in status.gate_diagnostics
    }


def _diagnostic_flags(status) -> dict[tuple[str, str], tuple[str, bool]]:
    return {
        (diagnostic.code, diagnostic.subject_id): (diagnostic.severity, diagnostic.blocking)
        for diagnostic in status.gate_diagnostics
    }


def _audit_entries(status) -> dict[str, object]:
    return {entry.observation_id: entry for entry in status.selection_audit.entries}


class RuntimeManagerStoreTests(unittest.TestCase):
    def test_initialize_schema_creates_runtime_db_idempotently(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            store = RuntimeManagerStore(root)

            store.initialize_schema()
            store.initialize_schema()

            self.assertTrue((root / ".cerebro" / "runtime.db").is_file())
            with closing(sqlite3.connect(root / ".cerebro" / "runtime.db")) as connection:
                tables = {
                    row[0]
                    for row in connection.execute(
                        "SELECT name FROM sqlite_master WHERE type = 'table'"
                    )
                }
            self.assertIn("metadata", tables)
            self.assertIn("observations", tables)
            self.assertIn("observation_dependencies", tables)
            self.assertIn("observation_decision_requirements", tables)
            self.assertIn("observation_evidence_requirements", tables)
            self.assertIn("observation_tool_requirements", tables)
            self.assertIn("observation_approval_requirements", tables)
            self.assertIn("decisions", tables)
            self.assertIn("evidence_records", tables)
            self.assertIn("tool_registry", tables)
            self.assertIn("approval_records", tables)
            self.assertIn("runtime_leases", tables)
            self.assertIn("replay_runs", tables)
            self.assertIn("runtime_traces", tables)
            self.assertIn("runtime_trace_events", tables)
            self.assertIn("observation_validation_requirements", tables)
            self.assertIn("validation_records", tables)
            self.assertIn("stop_conditions", tables)
            self.assertIn("events", tables)
            self.assertIn("center_authority_events", tables)
            with closing(sqlite3.connect(root / ".cerebro" / "runtime.db")) as connection:
                metadata = dict(connection.execute("SELECT key, value FROM metadata").fetchall())
                validation_columns = {
                    row[1]
                    for row in connection.execute("PRAGMA table_info(validation_records)")
                }
                dependency_columns = {
                    row[1]
                    for row in connection.execute("PRAGMA table_info(observation_dependencies)")
                }
            self.assertEqual(metadata["schema_version"], "16")
            self.assertEqual(metadata["center_authority_mode"], "toml_import")
            self.assertIn("fresh_until", validation_columns)
            self.assertIn("source_index", dependency_columns)

    def test_sync_imports_observation_center_with_source_authority_and_digest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            source = _write_observation_center(root, _observation("runtime-manager-phase-1", priority="critical"))
            store = RuntimeManagerStore(root)

            status = store.sync_observation_center()

            self.assertEqual(status.state, "ready")
            self.assertEqual(status.selected_id, "runtime-manager-phase-1")
            self.assertEqual(status.center_authority_mode, "toml_import")
            self.assertEqual(status.source_authority, "observation_center.toml")
            self.assertEqual(status.source_path, "docs/operations/observation_center.toml")
            self.assertFalse(status.stale_source)
            self.assertEqual(status.observations_total, 1)
            self.assertEqual(status.decisions_total, 0)
            self.assertEqual(status.evidence_total, 0)
            self.assertEqual(status.tools_total, 0)
            self.assertEqual(status.approvals_total, 0)
            self.assertEqual(status.active_leases, 0)
            self.assertEqual(status.replay_runs_total, 0)
            self.assertEqual(status.validations_total, 0)
            self.assertEqual(status.validations_expired, 0)
            self.assertEqual(status.stop_conditions_active, 0)
            self.assertEqual(status.gate_diagnostics, ())
            self.assertEqual(status.selection_audit.policy_version, "runtime-manager-selection-v1")
            self.assertEqual(status.selection_audit.sort_policy, ("priority_rank", "source_index", "id"))
            self.assertEqual(status.selection_audit.decision, "selected")
            self.assertEqual(status.selection_audit.selected_id, "runtime-manager-phase-1")
            self.assertEqual(status.selection_audit.global_blockers, ())
            self.assertEqual(status.selection_audit.eligible_ids, ("runtime-manager-phase-1",))
            self.assertEqual(len(status.source_sha256), 64)
            self.assertEqual(status.source_sha256, store.read_status(observation_center_path=source).source_sha256)

    def test_required_decisions_and_evidence_gate_selection(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            source = _write_observation_center(
                root,
                _observation("ledger-gated").replace(
                    'dependencies_satisfied = true',
                    'dependencies_satisfied = true\nrequired_decisions = ["dec-1"]\nrequired_evidence = ["ev-1"]',
                ),
            )
            store = RuntimeManagerStore(root)

            blocked_status = store.sync_observation_center()

            self.assertEqual(blocked_status.state, "idle")
            self.assertIn("required decisions or evidence", blocked_status.reason)
            self.assertEqual(_diagnostics(blocked_status)[("missing_decisions", "ledger-gated")], ("dec-1",))
            self.assertEqual(_diagnostics(blocked_status)[("missing_evidence", "ledger-gated")], ("ev-1",))
            self.assertEqual(blocked_status.selection_audit.decision, "no_eligible")
            self.assertEqual(blocked_status.selection_audit.eligible_ids, ())
            self.assertEqual(
                _audit_entries(blocked_status)["ledger-gated"].blockers,
                ("missing_decisions=dec-1", "missing_evidence=ev-1"),
            )
            self.assertIsNone(store.read_next())

            source.write_text(
                source.read_text(encoding="utf-8")
                + """

[[decisions]]
id = "dec-1"
subject_id = "ledger-gated"
revision = 1
status = "current"
effective_at = "2026-05-08T00:00:00Z"
expires_at = ""
human_decision_id = "human-1"
evidence_ids = ["ev-1"]
supersedes_id = ""

[[evidence_records]]
id = "ev-1"
kind = "sanitized-test"
source = "tests"
sanitized_digest = "sha256:abc"
retention_class = "short"
status = "accepted"
reason = "fixture"
linked_subject_id = "ledger-gated"
""",
                encoding="utf-8",
            )
            ready_status = store.sync_observation_center()
            selected = store.read_next(observation_center_path=source)

            self.assertEqual(ready_status.state, "ready")
            self.assertEqual(ready_status.selected_id, "ledger-gated")
            self.assertEqual(ready_status.decisions_total, 1)
            self.assertEqual(ready_status.decisions_current, 1)
            self.assertEqual(ready_status.evidence_total, 1)
            self.assertEqual(ready_status.evidence_accepted, 1)
            self.assertEqual(ready_status.gate_diagnostics, ())
            self.assertIsNotNone(selected)
            self.assertEqual(selected.required_decisions, ("dec-1",))
            self.assertEqual(selected.required_evidence, ("ev-1",))

    def test_required_tools_and_approvals_gate_selection_without_execution(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            source = _write_observation_center(
                root,
                _observation("tool-gated").replace(
                    'dependencies_satisfied = true',
                    'dependencies_satisfied = true\nrequired_tools = ["tool-1"]\nrequired_approvals = ["approval-1"]',
                ),
            )
            store = RuntimeManagerStore(root)

            blocked_status = store.sync_observation_center()

            self.assertEqual(blocked_status.state, "idle")
            self.assertIn("required tools or approvals", blocked_status.reason)
            self.assertEqual(_diagnostics(blocked_status)[("missing_tools", "tool-gated")], ("tool-1",))
            self.assertEqual(_diagnostics(blocked_status)[("missing_approvals", "tool-gated")], ("approval-1",))
            self.assertIsNone(store.read_next())

            source.write_text(
                source.read_text(encoding="utf-8")
                + """

[[tool_registry]]
id = "tool-1"
argv_prefix = ["python", "-m", "unittest"]
path_scope = "repo"
side_effect_class = "read_only_validation"
network_cloud = "none"
timeout_seconds = 120
output_budget_bytes = 65536
sensitive_output_policy = "redact"
approval_requirement = "none_for_read_only"
rollback_expectation = "none"
status = "enabled"

[[approval_records]]
id = "approval-1"
subject_id = "tool-gated"
action_fingerprint = "sha256:tool-gated"
scope = "read-only validation"
actor = "human"
status = "current"
expires_at = ""
revocation_path = "docs/operations/observation_center.toml"
audit_event_id = "event-1"
""",
                encoding="utf-8",
            )
            ready_status = store.sync_observation_center()
            selected = store.read_next(observation_center_path=source)

            self.assertEqual(ready_status.state, "ready")
            self.assertEqual(ready_status.selected_id, "tool-gated")
            self.assertEqual(ready_status.tools_total, 1)
            self.assertEqual(ready_status.tools_enabled, 1)
            self.assertEqual(ready_status.approvals_total, 1)
            self.assertEqual(ready_status.approvals_current, 1)
            self.assertIsNotNone(selected)
            self.assertEqual(selected.required_tools, ("tool-1",))
            self.assertEqual(selected.required_approvals, ("approval-1",))

    def test_active_lease_enforces_single_flight_selection(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            source = _write_observation_center(
                root,
                "\n".join(
                    [
                        _observation("critical-item", priority="critical"),
                        _observation("high-item", priority="high"),
                    ]
                ),
            )
            source.write_text(
                source.read_text(encoding="utf-8")
                + """

[[runtime_leases]]
id = "lease-1"
observation_id = "high-item"
owner = "agent-a"
status = "active"
acquired_at = "2026-05-08T00:00:00Z"
expires_at = "2099-01-01T00:00:00Z"
reason = "single flight"
""",
                encoding="utf-8",
            )
            store = RuntimeManagerStore(root)

            status = store.sync_observation_center()
            selected = store.read_next(observation_center_path=source)

            self.assertEqual(status.state, "ready")
            self.assertEqual(status.active_leases, 1)
            self.assertEqual(status.selected_id, "high-item")
            self.assertEqual(status.gate_diagnostics, ())
            self.assertEqual(status.selection_audit.decision, "selected")
            self.assertEqual(status.selection_audit.eligible_ids, ("high-item",))
            self.assertEqual(_audit_entries(status)["high-item"].sort_key, ("001", "000001", "high-item"))
            self.assertIn("active_lease_other_item=high-item", _audit_entries(status)["critical-item"].blockers)
            self.assertIsNotNone(selected)
            self.assertEqual(selected.id, "high-item")

    def test_active_lease_for_non_open_item_blocks_scheduler(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            source = _write_observation_center(root, _observation("open-item"))
            source.write_text(
                source.read_text(encoding="utf-8")
                + """

[[runtime_leases]]
id = "lease-1"
observation_id = "closed-item"
owner = "agent-a"
status = "active"
acquired_at = "2026-05-08T00:00:00Z"
expires_at = "2099-01-01T00:00:00Z"
reason = "stale lease"
""",
                encoding="utf-8",
            )
            store = RuntimeManagerStore(root)

            status = store.sync_observation_center()

            self.assertEqual(status.state, "idle")
            self.assertEqual(status.selected_id, "")
            self.assertEqual(status.active_leases, 1)
            self.assertIn("active lease", status.reason)
            self.assertEqual(_diagnostics(status)[("active_lease_non_open", "runtime-manager")], ("closed-item",))
            self.assertEqual(status.selection_audit.decision, "global_blocked")
            self.assertEqual(status.selection_audit.global_blockers, ("active_lease_non_open=closed-item",))
            self.assertIsNone(store.read_next(observation_center_path=source))

    def test_replay_runs_are_counted_without_becoming_permission(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            source = _write_observation_center(root, _observation("runtime-manager-phase-1", priority="critical"))
            source.write_text(
                source.read_text(encoding="utf-8")
                + """

[[replay_runs]]
id = "replay-1"
source_event_id = "event-1"
status = "passed"
replay_digest = "sha256:replay"
checked_at = "2026-05-08T00:00:00Z"
reason = "fixture replay"
""",
                encoding="utf-8",
            )
            store = RuntimeManagerStore(root)

            status = store.sync_observation_center()

            self.assertEqual(status.state, "ready")
            self.assertEqual(status.replay_runs_total, 1)
            self.assertEqual(status.replay_runs_passed, 1)
            self.assertEqual(status.replay_runs_failed, 0)
            self.assertEqual(status.selected_id, "runtime-manager-phase-1")

    def test_required_validation_gates_selection_until_green(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            source = _write_observation_center(
                root,
                _observation("validation-gated").replace(
                    'dependencies_satisfied = true',
                    'dependencies_satisfied = true\nrequired_validations = ["val-1"]',
                ),
            )
            store = RuntimeManagerStore(root)

            blocked_status = store.sync_observation_center()

            self.assertEqual(blocked_status.state, "idle")
            self.assertIn("required validations", blocked_status.reason)
            self.assertEqual(_diagnostics(blocked_status)[("missing_validations", "validation-gated")], ("val-1:missing",))
            self.assertEqual(
                _diagnostic_flags(blocked_status)[("missing_validations", "validation-gated")],
                ("blocking", True),
            )
            self.assertEqual(
                _audit_entries(blocked_status)["validation-gated"].blockers,
                ("missing_validations=val-1:missing",),
            )
            self.assertIsNone(store.read_next(observation_center_path=source))

            source.write_text(
                source.read_text(encoding="utf-8")
                + """

[[validation_records]]
id = "val-1"
subject_id = "validation-gated"
status = "green"
checked_at = "2026-05-08T00:00:00Z"
fresh_until = "2099-01-01T00:00:00Z"
command_id = "unit-test"
evidence_id = "ev-validation"
reason = "fixture green validation"
""",
                encoding="utf-8",
            )
            ready_status = store.sync_observation_center()
            selected = store.read_next(observation_center_path=source)

            self.assertEqual(ready_status.state, "ready")
            self.assertEqual(ready_status.selected_id, "validation-gated")
            self.assertEqual(ready_status.validations_total, 1)
            self.assertEqual(ready_status.validations_green, 1)
            self.assertEqual(ready_status.validations_red, 0)
            self.assertEqual(ready_status.validations_stale, 0)
            self.assertEqual(ready_status.validations_expired, 0)
            self.assertEqual(ready_status.gate_diagnostics, ())
            self.assertIsNotNone(selected)
            self.assertEqual(selected.required_validations, ("val-1",))

    def test_green_validation_without_fresh_until_does_not_satisfy_readiness(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            source = _write_observation_center(
                root,
                _observation("validation-gated").replace(
                    'dependencies_satisfied = true',
                    'dependencies_satisfied = true\nrequired_validations = ["val-1"]',
                ),
            )
            source.write_text(
                source.read_text(encoding="utf-8")
                + """

[[validation_records]]
id = "val-1"
subject_id = "validation-gated"
status = "green"
checked_at = "2026-05-08T00:00:00Z"
command_id = "unit-test"
evidence_id = "ev-validation"
reason = "fixture missing freshness"
""",
                encoding="utf-8",
            )
            store = RuntimeManagerStore(root)

            status = store.sync_observation_center()

            self.assertEqual(status.state, "idle")
            self.assertEqual(status.selected_id, "")
            self.assertEqual(status.validations_green, 0)
            self.assertEqual(status.validations_expired, 1)
            self.assertIn("required validations", status.reason)
            self.assertEqual(_diagnostics(status)[("missing_validations", "validation-gated")], ("val-1:expired",))

    def test_green_validation_with_future_fresh_until_satisfies_readiness(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            source = _write_observation_center(
                root,
                _observation("validation-gated").replace(
                    'dependencies_satisfied = true',
                    'dependencies_satisfied = true\nrequired_validations = ["val-1"]',
                ),
            )
            source.write_text(
                source.read_text(encoding="utf-8")
                + """

[[validation_records]]
id = "val-1"
subject_id = "validation-gated"
status = "green"
checked_at = "2026-05-08T00:00:00Z"
fresh_until = "2099-01-01T00:00:00Z"
command_id = "unit-test"
evidence_id = "ev-validation"
reason = "fixture fresh validation"
""",
                encoding="utf-8",
            )
            store = RuntimeManagerStore(root)

            status = store.sync_observation_center()

            self.assertEqual(status.state, "ready")
            self.assertEqual(status.selected_id, "validation-gated")
            self.assertEqual(status.validations_green, 1)
            self.assertEqual(status.validations_expired, 0)

    def test_green_validation_with_expired_fresh_until_blocks_readiness(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            source = _write_observation_center(
                root,
                _observation("validation-gated").replace(
                    'dependencies_satisfied = true',
                    'dependencies_satisfied = true\nrequired_validations = ["val-1"]',
                ),
            )
            source.write_text(
                source.read_text(encoding="utf-8")
                + """

[[validation_records]]
id = "val-1"
subject_id = "validation-gated"
status = "green"
checked_at = "2026-05-08T00:00:00Z"
fresh_until = "2000-01-01T00:00:00Z"
command_id = "unit-test"
evidence_id = "ev-validation"
reason = "fixture expired validation"
""",
                encoding="utf-8",
            )
            store = RuntimeManagerStore(root)

            status = store.sync_observation_center()

            self.assertEqual(status.state, "idle")
            self.assertEqual(status.selected_id, "")
            self.assertEqual(status.validations_green, 0)
            self.assertEqual(status.validations_expired, 1)
            self.assertIn("required validations", status.reason)
            self.assertEqual(_diagnostics(status)[("missing_validations", "validation-gated")], ("val-1:expired",))
            self.assertIsNone(store.read_next(observation_center_path=source))

    def test_red_or_stale_validation_does_not_satisfy_readiness(self) -> None:
        for validation_status in ("red", "stale"):
            with self.subTest(validation_status=validation_status):
                with tempfile.TemporaryDirectory() as tmp_dir:
                    root = Path(tmp_dir)
                    source = _write_observation_center(
                        root,
                        _observation("validation-gated").replace(
                            'dependencies_satisfied = true',
                            'dependencies_satisfied = true\nrequired_validations = ["val-1"]',
                        ),
                    )
                    source.write_text(
                        source.read_text(encoding="utf-8")
                        + f"""

[[validation_records]]
id = "val-1"
subject_id = "validation-gated"
status = "{validation_status}"
checked_at = "2026-05-08T00:00:00Z"
command_id = "unit-test"
evidence_id = "ev-validation"
reason = "fixture non-green validation"
""",
                        encoding="utf-8",
                    )
                    store = RuntimeManagerStore(root)

                    status = store.sync_observation_center()

                    self.assertEqual(status.state, "idle")
                    self.assertEqual(status.selected_id, "")
                    self.assertIn("required validations", status.reason)
                    self.assertEqual(
                        _diagnostics(status)[("missing_validations", "validation-gated")],
                        (f"val-1:{validation_status}",),
                    )
                    self.assertIsNone(store.read_next(observation_center_path=source))

    def test_active_stop_condition_blocks_readiness(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            source = _write_observation_center(root, _observation("stop-gated"))
            source.write_text(
                source.read_text(encoding="utf-8")
                + """

[[stop_conditions]]
id = "stop-1"
subject_id = "stop-gated"
status = "active"
severity = "high"
opened_at = "2026-05-08T00:00:00Z"
resolved_at = ""
reason = "fixture active stop"
""",
                encoding="utf-8",
            )
            store = RuntimeManagerStore(root)

            status = store.sync_observation_center()

            self.assertEqual(status.state, "idle")
            self.assertEqual(status.selected_id, "")
            self.assertEqual(status.stop_conditions_total, 1)
            self.assertEqual(status.stop_conditions_active, 1)
            self.assertIn("active stop condition", status.reason)
            self.assertEqual(_diagnostics(status)[("active_stop_condition", "stop-gated")], ())
            self.assertIsNone(store.read_next(observation_center_path=source))

    def test_resolved_stop_condition_is_counted_without_blocking_readiness(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            source = _write_observation_center(root, _observation("stop-gated"))
            source.write_text(
                source.read_text(encoding="utf-8")
                + """

[[stop_conditions]]
id = "stop-1"
subject_id = "stop-gated"
status = "resolved"
severity = "high"
opened_at = "2026-05-08T00:00:00Z"
resolved_at = "2026-05-08T00:10:00Z"
reason = "fixture resolved stop"
""",
                encoding="utf-8",
            )
            store = RuntimeManagerStore(root)

            status = store.sync_observation_center()

            self.assertEqual(status.state, "ready")
            self.assertEqual(status.selected_id, "stop-gated")
            self.assertEqual(status.stop_conditions_total, 1)
            self.assertEqual(status.stop_conditions_active, 0)

    def test_global_stop_condition_blocks_runtime_manager_readiness(self) -> None:
        for subject_id in ("*", "runtime-manager"):
            with self.subTest(subject_id=subject_id):
                with tempfile.TemporaryDirectory() as tmp_dir:
                    root = Path(tmp_dir)
                    source = _write_observation_center(root, _observation("open-item"))
                    source.write_text(
                        source.read_text(encoding="utf-8")
                        + f"""

[[stop_conditions]]
id = "stop-1"
subject_id = "{subject_id}"
status = "active"
severity = "critical"
opened_at = "2026-05-08T00:00:00Z"
resolved_at = ""
reason = "fixture global stop"
""",
                        encoding="utf-8",
                    )
                    store = RuntimeManagerStore(root)

                    status = store.sync_observation_center()

                    self.assertEqual(status.state, "idle")
                    self.assertEqual(status.selected_id, "")
                    self.assertEqual(status.stop_conditions_active, 1)
                    self.assertIn("active stop condition", status.reason)
                    self.assertEqual(_diagnostics(status)[("active_stop_condition", "runtime-manager")], (subject_id,))

    def test_read_next_selects_highest_priority_open_observation_by_stable_order(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            _write_observation_center(
                root,
                "\n".join(
                    [
                        _observation("medium-item", priority="medium"),
                        _observation("critical-item", priority="critical"),
                        _observation("high-item", priority="high"),
                    ]
                ),
            )
            store = RuntimeManagerStore(root)
            store.sync_observation_center()

            selected = store.read_next()

            self.assertIsNotNone(selected)
            self.assertEqual(selected.id, "critical-item")
            self.assertEqual(selected.next_action, "do critical-item")

    def test_dependencies_not_satisfied_blocks_selection(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            _write_observation_center(
                root,
                _observation("blocked-by-dependency", dependencies_satisfied="false"),
            )
            store = RuntimeManagerStore(root)
            status = store.sync_observation_center()

            self.assertEqual(status.state, "idle")
            self.assertEqual(status.selected_id, "")
            self.assertIn("no eligible open observation", status.reason)
            self.assertEqual(
                _diagnostics(status)[("dependencies_unsatisfied", "blocked-by-dependency")],
                ("dep-a",),
            )
            self.assertEqual(
                _audit_entries(status)["blocked-by-dependency"].blockers,
                ("dependencies_unsatisfied=dep-a",),
            )
            self.assertIsNone(store.read_next())

    def test_waiting_and_blocked_items_explain_noop_without_execution(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            _write_observation_center(root, _observation("waiting-item", status="waiting"))
            store = RuntimeManagerStore(root)
            waiting_status = store.sync_observation_center()

            self.assertEqual(waiting_status.state, "idle")
            self.assertIn("waiting", waiting_status.reason)
            self.assertIn(("waiting_status", "waiting-item"), _diagnostics(waiting_status))

            _write_observation_center(root, _observation("blocked-item", status="blocked"))
            blocked_status = store.sync_observation_center()

            self.assertEqual(blocked_status.state, "idle")
            self.assertIn("blocked", blocked_status.reason)
            self.assertIn(("blocked_status", "blocked-item"), _diagnostics(blocked_status))

    def test_stale_observation_center_digest_blocks_read_model_selection(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            source = _write_observation_center(root, _observation("runtime-manager-phase-1"))
            store = RuntimeManagerStore(root)
            store.sync_observation_center()
            source.write_text(source.read_text(encoding="utf-8") + "\n# drift\n", encoding="utf-8")

            status = store.read_status(observation_center_path=source)

            self.assertEqual(status.state, "blocked")
            self.assertTrue(status.stale_source)
            self.assertEqual(status.selected_id, "")
            self.assertIn("source digest", status.reason)
            self.assertIn(("stale_source", "runtime-manager"), _diagnostics(status))
            self.assertEqual(status.selection_audit.decision, "global_blocked")
            self.assertEqual(status.selection_audit.global_blockers, ("stale_source",))
            self.assertEqual(status.selection_audit.eligible_ids, ())

    def test_promote_observation_center_to_sqlite_primary_ignores_toml_staleness(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            observations = (
                _observation("first-item", priority="critical").replace(
                    'dependencies = ["dep-a"]',
                    'dependencies = ["dep-b", "dep-a"]',
                )
                + _observation("second-item", priority="low").replace(
                    'dependencies = ["dep-a"]',
                    'dependencies = ["dep-c"]',
                )
            )
            source = _write_observation_center(root, observations)
            store = RuntimeManagerStore(root)
            store.initialize_schema()

            promoted = store.promote_observation_center(source)
            source.write_text(source.read_text(encoding="utf-8") + "\n# drift after promotion\n", encoding="utf-8")
            status = store.read_status(observation_center_path=source)
            selected = store.read_next(observation_center_path=source)

            self.assertEqual(promoted.center_authority_mode, "sqlite_primary")
            self.assertEqual(promoted.source_authority, "runtime.db")
            self.assertEqual(promoted.source_path, ".cerebro/runtime.db")
            self.assertEqual(status.center_authority_mode, "sqlite_primary")
            self.assertFalse(status.stale_source)
            self.assertEqual(status.state, "ready")
            self.assertEqual(status.selected_id, "first-item")
            self.assertIsNotNone(selected)
            self.assertEqual(selected.dependencies, ("dep-b", "dep-a"))
            self.assertEqual(len(status.source_sha256), 64)

    def test_export_promoted_observation_center_toml_is_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            observations = (
                _observation("first-item", priority="critical").replace(
                    'dependencies = ["dep-a"]',
                    'dependencies = ["dep-b", "dep-a"]',
                )
                + _observation("second-item", priority="low")
            )
            source = _write_observation_center(root, observations)
            store = RuntimeManagerStore(root)
            store.initialize_schema()
            store.promote_observation_center(source)

            first_export = store.export_observation_center_toml()
            second_export = store.export_observation_center_toml()
            payload = tomllib.loads(first_export)

            self.assertEqual(first_export, second_export)
            self.assertEqual(payload["center"]["queue_authority"], "machine-primary")
            self.assertEqual(payload["observations"][0]["id"], "first-item")
            self.assertEqual(payload["observations"][0]["dependencies"], ["dep-b", "dep-a"])
            self.assertEqual(payload["observations"][1]["id"], "second-item")

    def test_promote_observation_center_fails_closed_when_repeated_or_db_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            source = _write_observation_center(root, _observation("runtime-manager-phase-1"))
            store = RuntimeManagerStore(root)

            with self.assertRaises(RuntimeManagerStoreError) as missing:
                store.promote_observation_center(source)
            self.assertEqual(missing.exception.code, "center_database_missing")

            store.initialize_schema()
            store.promote_observation_center(source)
            with self.assertRaises(RuntimeManagerStoreError) as repeated:
                store.promote_observation_center(source)
            self.assertEqual(repeated.exception.code, "center_already_promoted")

    def test_schema_v15_to_v16_migration_preserves_managed_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            source = _write_observation_center(root, _observation("runtime-manager-phase-1"))
            store = RuntimeManagerStore(root)
            store.sync_observation_center(source)
            store.acquire_lease("runtime-manager-phase-1", owner="tester", ttl_seconds=60)

            with closing(sqlite3.connect(root / ".cerebro" / "runtime.db")) as connection:
                connection.execute("ALTER TABLE observation_dependencies RENAME TO observation_dependencies_v16")
                connection.execute(
                    """CREATE TABLE observation_dependencies (
                        observation_id TEXT NOT NULL,
                        dependency_id TEXT NOT NULL,
                        PRIMARY KEY (observation_id, dependency_id),
                        FOREIGN KEY (observation_id) REFERENCES observations(id) ON DELETE CASCADE
                    )"""
                )
                connection.execute(
                    """INSERT INTO observation_dependencies(observation_id, dependency_id)
                       SELECT observation_id, dependency_id FROM observation_dependencies_v16"""
                )
                connection.execute("DROP TABLE observation_dependencies_v16")
                connection.execute("DROP TABLE center_authority_events")
                connection.execute("UPDATE metadata SET value = '15' WHERE key = 'schema_version'")
                connection.commit()

            store.initialize_schema()

            with closing(sqlite3.connect(root / ".cerebro" / "runtime.db")) as connection:
                metadata = dict(connection.execute("SELECT key, value FROM metadata").fetchall())
                dependency_columns = {
                    row[1]
                    for row in connection.execute("PRAGMA table_info(observation_dependencies)")
                }
                tables = {
                    row[0]
                    for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
                }
                managed_lease_count = connection.execute("SELECT COUNT(*) FROM managed_leases").fetchone()[0]

            self.assertEqual(metadata["schema_version"], "16")
            self.assertIn("source_index", dependency_columns)
            self.assertIn("center_authority_events", tables)
            self.assertEqual(managed_lease_count, 1)

    def test_repeated_sync_replaces_rows_but_keeps_events_append_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            _write_observation_center(root, _observation("runtime-manager-phase-1"))
            store = RuntimeManagerStore(root)

            first_status = store.sync_observation_center()
            second_status = store.sync_observation_center()

            self.assertEqual(first_status.selected_id, second_status.selected_id)
            with closing(sqlite3.connect(root / ".cerebro" / "runtime.db")) as connection:
                connection.row_factory = sqlite3.Row
                observation_count = connection.execute("SELECT COUNT(*) FROM observations").fetchone()[0]
                dependency_count = connection.execute("SELECT COUNT(*) FROM observation_dependencies").fetchone()[0]
                event_count = connection.execute("SELECT COUNT(*) FROM events").fetchone()[0]
                event_types = [row["event_type"] for row in connection.execute(
                    "SELECT event_type FROM events ORDER BY event_id ASC"
                ).fetchall()]
                first_payload = json.loads(connection.execute(
                    "SELECT payload_json FROM events WHERE event_type = 'runtime_synced' ORDER BY event_id ASC LIMIT 1"
                ).fetchone()[0])
            self.assertEqual(observation_count, 1)
            self.assertEqual(dependency_count, 1)
            # First sync: runtime_opened + queue_item_observed + runtime_synced = 3
            # Second sync: queue_item_observed + runtime_synced = 2 → total = 5
            self.assertEqual(event_count, 5)
            self.assertEqual(second_status.events_total, 5)
            # runtime_opened fires only once (first sync)
            self.assertEqual(event_types.count("runtime_opened"), 1)
            self.assertEqual(event_types[0], "runtime_opened")
            # runtime_synced payload carries per-table import counts
            self.assertIn("observations", first_payload)
            self.assertIn("decisions", first_payload)
            self.assertIn("evidence_records", first_payload)
            self.assertIn("tool_registry", first_payload)
            self.assertIn("validation_records", first_payload)
            self.assertEqual(first_payload["observations"], 1)

    def test_markdown_projections_are_not_read_as_authority(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            _write_observation_center(root, _observation("canonical-open-item"))
            operations = root / "docs" / "operations"
            (operations / "SYSTEM_STATE.md").write_text(
                "Next action: blocked fake markdown item\n",
                encoding="utf-8",
            )
            (operations / "OPPORTUNITY_MAP.md").write_text(
                "Next action: blocked fake markdown item\n",
                encoding="utf-8",
            )
            store = RuntimeManagerStore(root)

            status = store.sync_observation_center()

            self.assertEqual(status.selected_id, "canonical-open-item")
            self.assertNotIn("markdown", status.reason.lower())

    def test_read_status_requires_initialized_runtime_db(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = RuntimeManagerStore(Path(tmp_dir))

            with self.assertRaisesRegex(RuntimeManagerStoreError, "database not found"):
                store.read_status()

    def test_read_status_rejects_unsupported_schema_version(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            _write_observation_center(root, _observation("runtime-manager-phase-1"))
            store = RuntimeManagerStore(root)
            store.sync_observation_center()
            with closing(sqlite3.connect(root / ".cerebro" / "runtime.db")) as connection:
                connection.execute("UPDATE metadata SET value = '5' WHERE key = 'schema_version'")
                connection.commit()

            with self.assertRaisesRegex(RuntimeManagerStoreError, "schema version is unsupported"):
                store.read_status()

    def test_read_status_rejects_missing_runtime_manager_table(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            _write_observation_center(root, _observation("runtime-manager-phase-1"))
            store = RuntimeManagerStore(root)
            store.sync_observation_center()
            with closing(sqlite3.connect(root / ".cerebro" / "runtime.db")) as connection:
                connection.execute("DROP TABLE stop_conditions")
                connection.commit()

            with self.assertRaisesRegex(RuntimeManagerStoreError, "schema is missing or incomplete"):
                store.read_status()

    def test_expired_active_lease_does_not_block_selection(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            source = _write_observation_center(
                root,
                "\n".join(
                    [
                        _observation("critical-item", priority="critical"),
                        _observation("high-item", priority="high"),
                    ]
                ),
            )
            source.write_text(
                source.read_text(encoding="utf-8")
                + """

[[runtime_leases]]
id = "lease-1"
observation_id = "high-item"
owner = "agent-a"
status = "active"
acquired_at = "2026-05-08T00:00:00Z"
expires_at = "2000-01-01T00:00:00Z"
reason = "expired lease"
""",
                encoding="utf-8",
            )
            store = RuntimeManagerStore(root)

            status = store.sync_observation_center()
            selected = store.read_next(observation_center_path=source)

            self.assertEqual(status.active_leases, 0)
            self.assertEqual(status.leases_expired, 1)
            self.assertEqual(status.state, "ready")
            self.assertEqual(status.selected_id, "critical-item")
            self.assertIn(("active_lease_expired", "runtime-manager"), _diagnostics(status))
            self.assertEqual(_diagnostics(status)[("active_lease_expired", "runtime-manager")], ("high-item",))
            self.assertEqual(
                _diagnostic_flags(status)[("active_lease_expired", "runtime-manager")],
                ("informational", False),
            )
            self.assertNotIn(("active_lease", "runtime-manager"), _diagnostics(status))
            self.assertNotIn(("active_lease_non_open", "runtime-manager"), _diagnostics(status))
            self.assertEqual(status.selection_audit.decision, "selected")
            self.assertEqual(status.selection_audit.global_blockers, ())
            self.assertNotIn("active_lease_other_item", str(_audit_entries(status)["critical-item"].blockers))
            self.assertIsNotNone(selected)
            self.assertEqual(selected.id, "critical-item")

    def test_active_lease_without_expires_at_blocks_conservatively(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            source = _write_observation_center(
                root,
                "\n".join(
                    [
                        _observation("critical-item", priority="critical"),
                        _observation("high-item", priority="high"),
                    ]
                ),
            )
            source.write_text(
                source.read_text(encoding="utf-8")
                + """

[[runtime_leases]]
id = "lease-1"
observation_id = "high-item"
owner = "agent-a"
status = "active"
acquired_at = "2026-05-08T00:00:00Z"
expires_at = ""
reason = "no expiry declared"
""",
                encoding="utf-8",
            )
            store = RuntimeManagerStore(root)

            status = store.sync_observation_center()

            self.assertEqual(status.active_leases, 1)
            self.assertEqual(status.leases_expired, 0)
            self.assertEqual(status.state, "ready")
            self.assertEqual(status.selected_id, "high-item")
            # On successful selection, only informational diagnostics are returned.
            # active_lease_expired is not emitted when the lease is conservatively active.
            self.assertNotIn(("active_lease_expired", "runtime-manager"), _diagnostics(status))
            self.assertEqual(status.gate_diagnostics, ())

    def test_active_lease_with_malformed_expires_at_blocks_conservatively(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            source = _write_observation_center(
                root,
                "\n".join(
                    [
                        _observation("critical-item", priority="critical"),
                        _observation("high-item", priority="high"),
                    ]
                ),
            )
            source.write_text(
                source.read_text(encoding="utf-8")
                + """

[[runtime_leases]]
id = "lease-1"
observation_id = "high-item"
owner = "agent-a"
status = "active"
acquired_at = "2026-05-08T00:00:00Z"
expires_at = "not-a-timestamp"
reason = "malformed expiry"
""",
                encoding="utf-8",
            )
            store = RuntimeManagerStore(root)

            status = store.sync_observation_center()

            self.assertEqual(status.active_leases, 1)
            self.assertEqual(status.leases_expired, 0)
            self.assertEqual(status.state, "ready")
            self.assertEqual(status.selected_id, "high-item")
            # Malformed expires_at is treated conservatively as still active: no expired diagnostic.
            self.assertNotIn(("active_lease_expired", "runtime-manager"), _diagnostics(status))
            self.assertEqual(status.gate_diagnostics, ())

    def test_active_lease_with_future_expires_at_blocks_selection(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            source = _write_observation_center(
                root,
                "\n".join(
                    [
                        _observation("critical-item", priority="critical"),
                        _observation("high-item", priority="high"),
                    ]
                ),
            )
            source.write_text(
                source.read_text(encoding="utf-8")
                + """

[[runtime_leases]]
id = "lease-1"
observation_id = "high-item"
owner = "agent-a"
status = "active"
acquired_at = "2026-05-08T00:00:00Z"
expires_at = "2099-01-01T00:00:00Z"
reason = "future expiry"
""",
                encoding="utf-8",
            )
            store = RuntimeManagerStore(root)

            status = store.sync_observation_center()
            selected = store.read_next(observation_center_path=source)

            self.assertEqual(status.active_leases, 1)
            self.assertEqual(status.leases_expired, 0)
            self.assertEqual(status.state, "ready")
            self.assertEqual(status.selected_id, "high-item")
            # On successful selection without expired leases, gate_diagnostics is empty.
            self.assertEqual(status.gate_diagnostics, ())
            self.assertIsNotNone(selected)
            self.assertEqual(selected.id, "high-item")

    def test_expired_lease_counter_and_active_counter_are_independent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            source = _write_observation_center(
                root,
                "\n".join(
                    [
                        _observation("item-a", priority="critical"),
                        _observation("item-b", priority="high"),
                        _observation("item-c", priority="medium"),
                    ]
                ),
            )
            source.write_text(
                source.read_text(encoding="utf-8")
                + """

[[runtime_leases]]
id = "lease-expired"
observation_id = "item-c"
owner = "agent-old"
status = "active"
acquired_at = "2026-05-08T00:00:00Z"
expires_at = "2000-01-01T00:00:00Z"
reason = "expired"

[[runtime_leases]]
id = "lease-active"
observation_id = "item-b"
owner = "agent-current"
status = "active"
acquired_at = "2026-05-08T00:00:00Z"
expires_at = "2099-01-01T00:00:00Z"
reason = "active"
""",
                encoding="utf-8",
            )
            store = RuntimeManagerStore(root)

            status = store.sync_observation_center()

            self.assertEqual(status.active_leases, 1)
            self.assertEqual(status.leases_expired, 1)
            self.assertEqual(status.selected_id, "item-b")
            # Expired lease appears as informational diagnostic even on successful selection.
            self.assertIn(("active_lease_expired", "runtime-manager"), _diagnostics(status))
            self.assertEqual(_diagnostics(status)[("active_lease_expired", "runtime-manager")], ("item-c",))
            # active_lease is only in gate_diagnostics when selection fails; on success it is absent.
            self.assertNotIn(("active_lease", "runtime-manager"), _diagnostics(status))
            # Active lease on item-b blocks both item-a and item-c via single-flight enforcement.
            self.assertIn("active_lease_other_item=item-b", _audit_entries(status)["item-a"].blockers)
            self.assertIn("active_lease_other_item=item-b", _audit_entries(status)["item-c"].blockers)
            # The expired lease on item-c does not add any extra blocker to item-a.
            self.assertNotIn("active_lease_expired", str(_audit_entries(status)["item-a"].blockers))

    def test_failed_replay_run_appears_in_diagnostics_but_does_not_block_selection(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            source = _write_observation_center(root, _observation("runtime-manager-phase-1", priority="critical"))
            source.write_text(
                source.read_text(encoding="utf-8")
                + """

[[replay_runs]]
id = "replay-fail-1"
source_event_id = "event-1"
status = "failed"
replay_digest = "sha256:fail"
checked_at = "2026-05-08T00:00:00Z"
reason = "fixture failed replay"

[[replay_runs]]
id = "replay-pass-1"
source_event_id = "event-2"
status = "passed"
replay_digest = "sha256:pass"
checked_at = "2026-05-08T00:00:00Z"
reason = "fixture passed replay"
""",
                encoding="utf-8",
            )
            store = RuntimeManagerStore(root)

            status = store.sync_observation_center()

            self.assertEqual(status.replay_runs_total, 2)
            self.assertEqual(status.replay_runs_passed, 1)
            self.assertEqual(status.replay_runs_failed, 1)
            # Failed replay is informational — selection still proceeds.
            self.assertEqual(status.state, "ready")
            self.assertEqual(status.selected_id, "runtime-manager-phase-1")
            self.assertIn(("failed_replay_run", "runtime-manager"), _diagnostics(status))
            self.assertEqual(_diagnostics(status)[("failed_replay_run", "runtime-manager")], ("replay-fail-1",))
            self.assertEqual(
                _diagnostic_flags(status)[("failed_replay_run", "runtime-manager")],
                ("informational", False),
            )
            self.assertIsNotNone(store.read_next(observation_center_path=source))

    def test_passed_replay_runs_have_no_failed_replay_diagnostic(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            source = _write_observation_center(root, _observation("runtime-manager-phase-1", priority="critical"))
            source.write_text(
                source.read_text(encoding="utf-8")
                + """

[[replay_runs]]
id = "replay-pass-1"
source_event_id = "event-1"
status = "passed"
replay_digest = "sha256:pass"
checked_at = "2026-05-08T00:00:00Z"
reason = "fixture passed replay"
""",
                encoding="utf-8",
            )
            store = RuntimeManagerStore(root)

            status = store.sync_observation_center()

            self.assertEqual(status.replay_runs_total, 1)
            self.assertEqual(status.replay_runs_passed, 1)
            self.assertEqual(status.replay_runs_failed, 0)
            self.assertEqual(status.state, "ready")
            self.assertEqual(status.gate_diagnostics, ())
            self.assertNotIn(("failed_replay_run", "runtime-manager"), _diagnostics(status))

    def test_read_status_and_read_next_do_not_append_events(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            source = _write_observation_center(root, _observation("runtime-manager-phase-1", priority="critical"))
            store = RuntimeManagerStore(root)
            store.sync_observation_center()

            with closing(sqlite3.connect(root / ".cerebro" / "runtime.db")) as connection:
                count_after_sync = connection.execute("SELECT COUNT(*) FROM events").fetchone()[0]

            store.read_status(observation_center_path=source)
            store.read_status(observation_center_path=source)
            store.read_next(observation_center_path=source)
            store.read_next(observation_center_path=source)

            with closing(sqlite3.connect(root / ".cerebro" / "runtime.db")) as connection:
                count_after_reads = connection.execute("SELECT COUNT(*) FROM events").fetchone()[0]

            self.assertEqual(count_after_sync, count_after_reads,
                "read_status and read_next must not append events to the event log")

    def test_read_status_rejects_missing_runtime_leases_expires_at_column(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            _write_observation_center(root, _observation("runtime-manager-phase-1"))
            store = RuntimeManagerStore(root)
            store.sync_observation_center()
            with closing(sqlite3.connect(root / ".cerebro" / "runtime.db")) as connection:
                connection.executescript(
                    """
                    ALTER TABLE runtime_leases RENAME TO runtime_leases_old;
                    CREATE TABLE runtime_leases (
                        lease_id TEXT PRIMARY KEY,
                        observation_id TEXT NOT NULL,
                        owner TEXT NOT NULL,
                        status TEXT NOT NULL,
                        acquired_at TEXT NOT NULL,
                        reason TEXT NOT NULL,
                        source_path TEXT NOT NULL,
                        source_sha256 TEXT NOT NULL,
                        imported_at TEXT NOT NULL
                    );
                    DROP TABLE runtime_leases_old;
                    """
                )
                connection.commit()

            with self.assertRaisesRegex(RuntimeManagerStoreError, "schema is missing or incomplete"):
                store.read_status()

    def test_read_status_rejects_missing_validation_freshness_column(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            _write_observation_center(root, _observation("runtime-manager-phase-1"))
            store = RuntimeManagerStore(root)
            store.sync_observation_center()
            with closing(sqlite3.connect(root / ".cerebro" / "runtime.db")) as connection:
                connection.executescript(
                    """
                    ALTER TABLE validation_records RENAME TO validation_records_old;
                    CREATE TABLE validation_records (
                        validation_id TEXT PRIMARY KEY,
                        subject_id TEXT NOT NULL,
                        status TEXT NOT NULL,
                        checked_at TEXT NOT NULL,
                        command_id TEXT NOT NULL,
                        evidence_id TEXT NOT NULL,
                        reason TEXT NOT NULL,
                        source_path TEXT NOT NULL,
                        source_sha256 TEXT NOT NULL,
                        imported_at TEXT NOT NULL
                    );
                    DROP TABLE validation_records_old;
                    """
                )
                connection.commit()

            with self.assertRaisesRegex(RuntimeManagerStoreError, "schema is missing or incomplete"):
                store.read_status()


def _command_registry_entry(
    command_id: str,
    *,
    argv_prefix: tuple[str, ...] | list[str] | None = None,
    path_scope: str = ".",
    status: str = "enabled",
    approval_requirement: str = "none",
    side_effect_class: str = "read-only",
    rollback_class: str = "reversible",
) -> str:
    argv = ", ".join(json.dumps(item) for item in (argv_prefix or ("python", "-m", command_id)))
    return f"""
[[command_registry]]
id = "{command_id}"
argv_prefix = [{argv}]
path_scope = {json.dumps(path_scope)}
side_effect_class = "{side_effect_class}"
network_allowed = false
timeout_seconds = 60
output_budget_bytes = 65536
sensitive_output_policy = "none"
approval_requirement = "{approval_requirement}"
rollback_class = "{rollback_class}"
status = "{status}"
""".lstrip()


def _command_action_fingerprint(
    command_id: str,
    *,
    argv_prefix: tuple[str, ...] | list[str] | None = None,
    path_scope: str = ".",
) -> str:
    payload = {
        "command_id": command_id,
        "argv_prefix": list(argv_prefix or ("python", "-m", command_id)),
        "path_scope": path_scope,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


class CommandEligibilityTests(unittest.TestCase):
    def test_check_command_eligibility_unknown_command_is_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            _write_observation_center(root, _observation("obs-a"))
            store = RuntimeManagerStore(root)
            store.sync_observation_center()

            result = store.check_command_eligibility("cmd-not-registered")

            self.assertFalse(result.eligible)
            self.assertIn("command_not_registered", result.blockers)
            self.assertIsNone(result.policy)

    def test_check_command_eligibility_disabled_command_is_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "docs" / "operations").mkdir(parents=True, exist_ok=True)
            (root / "docs" / "operations" / "observation_center.toml").write_text(
                "[center]\nversion = 1\nqueue_authority = \"machine-primary\"\nsingle_flight = true\n"
                "[projections]\nsystem_state = \"p\"\nopportunity_map = \"p\"\n"
                + _observation("obs-a") + _command_registry_entry("cmd-disabled", status="disabled"),
                encoding="utf-8",
            )
            store = RuntimeManagerStore(root)
            store.sync_observation_center()

            result = store.check_command_eligibility("cmd-disabled")

            self.assertFalse(result.eligible)
            self.assertIn("command_not_enabled", result.blockers)
            self.assertIsNotNone(result.policy)
            self.assertEqual(result.policy.status, "disabled")

    def test_check_command_eligibility_no_open_observation_blocks_execution(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "docs" / "operations").mkdir(parents=True, exist_ok=True)
            (root / "docs" / "operations" / "observation_center.toml").write_text(
                "[center]\nversion = 1\nqueue_authority = \"machine-primary\"\nsingle_flight = true\n"
                "[projections]\nsystem_state = \"p\"\nopportunity_map = \"p\"\n"
                + _observation("obs-blocked", status="blocked") + _command_registry_entry("cmd-ok"),
                encoding="utf-8",
            )
            store = RuntimeManagerStore(root)
            store.sync_observation_center()

            result = store.check_command_eligibility("cmd-ok")

            self.assertFalse(result.eligible)
            self.assertIn("no_eligible_observation", result.blockers)
            self.assertEqual(result.selected_observation_id, "")

    def test_check_command_eligibility_eligible_when_open_item_and_no_approval_required(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "docs" / "operations").mkdir(parents=True, exist_ok=True)
            (root / "docs" / "operations" / "observation_center.toml").write_text(
                "[center]\nversion = 1\nqueue_authority = \"machine-primary\"\nsingle_flight = true\n"
                "[projections]\nsystem_state = \"p\"\nopportunity_map = \"p\"\n"
                + _observation("obs-open") + _command_registry_entry("cmd-free", approval_requirement="none"),
                encoding="utf-8",
            )
            store = RuntimeManagerStore(root)
            store.sync_observation_center()

            result = store.check_command_eligibility("cmd-free")

            self.assertTrue(result.eligible)
            self.assertEqual(result.blockers, ())
            self.assertEqual(result.selected_observation_id, "obs-open")
            self.assertIsNotNone(result.policy)
            self.assertEqual(result.policy.approval_requirement, "none")

    def test_check_command_eligibility_blocked_when_approval_required_and_none_present(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "docs" / "operations").mkdir(parents=True, exist_ok=True)
            (root / "docs" / "operations" / "observation_center.toml").write_text(
                "[center]\nversion = 1\nqueue_authority = \"machine-primary\"\nsingle_flight = true\n"
                "[projections]\nsystem_state = \"p\"\nopportunity_map = \"p\"\n"
                + _observation("obs-open") + _command_registry_entry("cmd-guarded", approval_requirement="required"),
                encoding="utf-8",
            )
            store = RuntimeManagerStore(root)
            store.sync_observation_center()

            result = store.check_command_eligibility("cmd-guarded")

            self.assertFalse(result.eligible)
            self.assertIn("approval_required", result.blockers)
            self.assertEqual(result.selected_observation_id, "obs-open")

    def test_check_command_eligibility_eligible_when_current_approval_present(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "docs" / "operations").mkdir(parents=True, exist_ok=True)
            (root / "docs" / "operations" / "observation_center.toml").write_text(
                "[center]\nversion = 1\nqueue_authority = \"machine-primary\"\nsingle_flight = true\n"
                "[projections]\nsystem_state = \"p\"\nopportunity_map = \"p\"\n"
                + _observation("obs-open") + _command_registry_entry("cmd-guarded", approval_requirement="required")
                + f"""
[[approval_records]]
id = "appr-1"
subject_id = "obs-open"
action_fingerprint = "{_command_action_fingerprint("cmd-guarded")}"
scope = "obs-open"
actor = "human"
status = "current"
expires_at = "2099-01-01T00:00:00Z"
revocation_path = "none"
audit_event_id = "evt-1"
""",
                encoding="utf-8",
            )
            store = RuntimeManagerStore(root)
            store.sync_observation_center()

            result = store.check_command_eligibility("cmd-guarded")

            self.assertTrue(result.eligible)
            self.assertEqual(result.blockers, ())
            self.assertEqual(result.selected_observation_id, "obs-open")

    def test_check_command_eligibility_rejects_command_id_only_approval_fingerprint(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "docs" / "operations").mkdir(parents=True, exist_ok=True)
            (root / "docs" / "operations" / "observation_center.toml").write_text(
                "[center]\nversion = 1\nqueue_authority = \"machine-primary\"\nsingle_flight = true\n"
                "[projections]\nsystem_state = \"p\"\nopportunity_map = \"p\"\n"
                + _observation("obs-open") + _command_registry_entry("cmd-guarded", approval_requirement="required")
                + """
[[approval_records]]
id = "appr-1"
subject_id = "obs-open"
action_fingerprint = "cmd-guarded"
scope = "obs-open"
actor = "human"
status = "current"
expires_at = "2099-01-01T00:00:00Z"
revocation_path = "none"
audit_event_id = "evt-1"
""",
                encoding="utf-8",
            )
            store = RuntimeManagerStore(root)
            store.sync_observation_center()

            result = store.check_command_eligibility("cmd-guarded")

            self.assertFalse(result.eligible)
            self.assertIn("approval_required", result.blockers)

    def test_check_command_eligibility_rejects_approval_for_changed_command_policy(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            old_fingerprint = _command_action_fingerprint("cmd-guarded")
            new_fingerprint = _command_action_fingerprint(
                "cmd-guarded",
                argv_prefix=("python", "-m", "cmd-guarded", "--new-mode"),
                path_scope="tools",
            )
            (root / "docs" / "operations").mkdir(parents=True, exist_ok=True)
            (root / "tools").mkdir()
            (root / "docs" / "operations" / "observation_center.toml").write_text(
                "[center]\nversion = 1\nqueue_authority = \"machine-primary\"\nsingle_flight = true\n"
                "[projections]\nsystem_state = \"p\"\nopportunity_map = \"p\"\n"
                + _observation("obs-open")
                + _command_registry_entry(
                    "cmd-guarded",
                    argv_prefix=("python", "-m", "cmd-guarded", "--new-mode"),
                    path_scope="tools",
                    approval_requirement="required",
                )
                + f"""
[[approval_records]]
id = "appr-1"
subject_id = "obs-open"
action_fingerprint = "{old_fingerprint}"
scope = "obs-open"
actor = "human"
status = "current"
expires_at = "2099-01-01T00:00:00Z"
revocation_path = "none"
audit_event_id = "evt-1"
""",
                encoding="utf-8",
            )
            store = RuntimeManagerStore(root)
            store.sync_observation_center()

            result = store.check_command_eligibility("cmd-guarded")

            self.assertFalse(result.eligible)
            self.assertIn("approval_required", result.blockers)
            self.assertIn(new_fingerprint, result.reason)
            self.assertNotIn(old_fingerprint, result.reason)

    def test_check_command_eligibility_returns_full_policy_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "docs" / "operations").mkdir(parents=True, exist_ok=True)
            (root / "docs" / "operations" / "observation_center.toml").write_text(
                "[center]\nversion = 1\nqueue_authority = \"machine-primary\"\nsingle_flight = true\n"
                "[projections]\nsystem_state = \"p\"\nopportunity_map = \"p\"\n"
                + _observation("obs-open")
                + """
[[command_registry]]
id = "cmd-full"
argv_prefix = ["python", "-m", "pytest"]
path_scope = "/tmp/scope"
side_effect_class = "local-write"
network_allowed = false
timeout_seconds = 120
output_budget_bytes = 32768
sensitive_output_policy = "redact"
approval_requirement = "none"
rollback_class = "reversible"
status = "enabled"
""",
                encoding="utf-8",
            )
            store = RuntimeManagerStore(root)
            store.sync_observation_center()

            result = store.check_command_eligibility("cmd-full")

            self.assertTrue(result.eligible)
            self.assertIsNotNone(result.policy)
            self.assertEqual(result.policy.argv_prefix, ("python", "-m", "pytest"))
            self.assertEqual(result.policy.path_scope, "/tmp/scope")
            self.assertEqual(result.policy.side_effect_class, "local-write")
            self.assertFalse(result.policy.network_allowed)
            self.assertEqual(result.policy.timeout_seconds, 120)
            self.assertEqual(result.policy.output_budget_bytes, 32768)
            self.assertEqual(result.policy.sensitive_output_policy, "redact")
            self.assertEqual(result.policy.rollback_class, "reversible")

    def test_schema_guard_requires_command_registry_table(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            _write_observation_center(root, _observation("obs-a"))
            store = RuntimeManagerStore(root)
            store.sync_observation_center()

            with closing(sqlite3.connect(root / ".cerebro" / "runtime.db")) as connection:
                connection.execute("DROP TABLE command_registry")
                connection.commit()

            with self.assertRaisesRegex(RuntimeManagerStoreError, "schema is missing or incomplete"):
                store.read_status()

    def test_commands_total_and_enabled_counts_in_status(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "docs" / "operations").mkdir(parents=True, exist_ok=True)
            (root / "docs" / "operations" / "observation_center.toml").write_text(
                "[center]\nversion = 1\nqueue_authority = \"machine-primary\"\nsingle_flight = true\n"
                "[projections]\nsystem_state = \"p\"\nopportunity_map = \"p\"\n"
                + _observation("obs-open")
                + _command_registry_entry("cmd-on", status="enabled")
                + _command_registry_entry("cmd-off", status="disabled"),
                encoding="utf-8",
            )
            store = RuntimeManagerStore(root)
            status = store.sync_observation_center()

            self.assertEqual(status.commands_total, 2)
            self.assertEqual(status.commands_enabled, 1)

    def test_check_command_eligibility_raises_when_db_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            store = RuntimeManagerStore(root)

            with self.assertRaises(RuntimeManagerStoreError):
                store.check_command_eligibility("any-cmd")


def _run_command_center(root: Path, *, argv_prefix: list[str], approval_requirement: str = "none",
                        timeout_seconds: int = 10, output_budget_bytes: int = 65536,
                        sensitive_output_policy: str = "none", rollback_class: str = "reversible") -> None:
    """Write an observation center with a single enabled command using the given argv_prefix."""
    argv_json = json.dumps(argv_prefix)
    (root / "docs" / "operations").mkdir(parents=True, exist_ok=True)
    (root / "docs" / "operations" / "observation_center.toml").write_text(
        f"""[center]
version = 1
queue_authority = "machine-primary"
single_flight = true

[projections]
system_state = "p"
opportunity_map = "p"

[[observations]]
id = "obs-run"
title = "run test observation"
status = "open"
kind = "slice"
priority = "critical"
boundary = "authorized"
trigger = "TRIGGER.md"
dependencies = []
dependencies_satisfied = true
next_action = "run"
done_when = "done"
halt_if = "never"

[[command_registry]]
id = "cmd-run"
argv_prefix = {argv_json}
path_scope = "."
side_effect_class = "read-only"
network_allowed = false
timeout_seconds = {timeout_seconds}
output_budget_bytes = {output_budget_bytes}
sensitive_output_policy = "{sensitive_output_policy}"
approval_requirement = "{approval_requirement}"
rollback_class = "{rollback_class}"
status = "enabled"
""",
        encoding="utf-8",
    )


class CommandRunTests(unittest.TestCase):
    def _setup_and_sync(self, root: Path, **kwargs) -> None:
        _run_command_center(root, **kwargs)
        store = RuntimeManagerStore(root)
        store.sync_observation_center()

    def test_run_command_ineligible_returns_ineligible_result(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            _write_observation_center(root, _observation("obs-a"))
            store = RuntimeManagerStore(root)
            store.sync_observation_center()

            result = store.run_command("cmd-not-registered")

            self.assertIsInstance(result, CommandRunResult)
            self.assertFalse(result.eligible)
            self.assertIn("command_not_registered", result.blockers)
            self.assertEqual(result.returncode, -1)
            self.assertEqual(result.event_id, -1)

    def test_run_command_executes_and_captures_stdout(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            argv = [sys.executable, "-c", "print('hello-from-test')"]
            self._setup_and_sync(root, argv_prefix=argv)
            store = RuntimeManagerStore(root)

            result = store.run_command("cmd-run")

            self.assertTrue(result.eligible)
            self.assertEqual(result.returncode, 0)
            self.assertIn("hello-from-test", result.stdout)
            self.assertFalse(result.timed_out)
            self.assertFalse(result.stdout_truncated)
            self.assertGreater(result.duration_seconds, 0.0)

    def test_run_command_captures_stderr(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            argv = [sys.executable, "-c", "import sys; sys.stderr.write('err-output\\n')"]
            self._setup_and_sync(root, argv_prefix=argv)
            store = RuntimeManagerStore(root)

            result = store.run_command("cmd-run")

            self.assertTrue(result.eligible)
            self.assertIn("err-output", result.stderr)

    def test_run_command_captures_nonzero_returncode(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            argv = [sys.executable, "-c", "raise SystemExit(42)"]
            self._setup_and_sync(root, argv_prefix=argv)
            store = RuntimeManagerStore(root)

            result = store.run_command("cmd-run")

            self.assertTrue(result.eligible)
            self.assertEqual(result.returncode, 42)

    def test_run_command_enforces_output_budget(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            argv = [sys.executable, "-c", "print('x' * 10000)"]
            self._setup_and_sync(root, argv_prefix=argv, output_budget_bytes=50)
            store = RuntimeManagerStore(root)

            result = store.run_command("cmd-run")

            self.assertTrue(result.eligible)
            self.assertTrue(result.stdout_truncated)
            self.assertIn("[TRUNCATED]", result.stdout)
            self.assertLessEqual(len(result.stdout.encode()), 50 + len("\n[TRUNCATED]"))

    def test_run_command_redacts_sensitive_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            argv = [sys.executable, "-c", "print('secret-data')"]
            self._setup_and_sync(root, argv_prefix=argv, sensitive_output_policy="redact")
            store = RuntimeManagerStore(root)

            result = store.run_command("cmd-run")

            self.assertTrue(result.eligible)
            self.assertEqual(result.stdout, "[REDACTED]")
            self.assertEqual(result.stderr, "[REDACTED]")
            self.assertNotIn("secret-data", result.stdout)

    def test_run_command_records_command_run_event(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            argv = [sys.executable, "-c", "print('event-test')"]
            self._setup_and_sync(root, argv_prefix=argv)
            store = RuntimeManagerStore(root)

            result = store.run_command("cmd-run")

            self.assertTrue(result.eligible)
            self.assertGreater(result.event_id, 0)

            with closing(sqlite3.connect(store.db_path)) as conn:
                conn.row_factory = sqlite3.Row
                row = conn.execute(
                    "SELECT event_type, payload_json FROM events WHERE event_id = ?", (result.event_id,)
                ).fetchone()

            self.assertIsNotNone(row)
            self.assertEqual(row["event_type"], "command_run")
            payload = json.loads(row["payload_json"])
            self.assertEqual(payload["command_id"], "cmd-run")
            self.assertEqual(payload["observation_id"], "obs-run")
            self.assertFalse(payload["timed_out"])
            self.assertEqual(payload["rollback_class"], "reversible")

    def test_run_command_path_scope_violation_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            # Manually write a center with path_scope that escapes root
            import json as _json
            (root / "docs" / "operations").mkdir(parents=True, exist_ok=True)
            (root / "docs" / "operations" / "observation_center.toml").write_text(
                f"""[center]
version = 1
queue_authority = "machine-primary"
single_flight = true

[projections]
system_state = "p"
opportunity_map = "p"

[[observations]]
id = "obs-scope"
title = "scope test"
status = "open"
kind = "slice"
priority = "critical"
boundary = "authorized"
trigger = "TRIGGER.md"
dependencies = []
dependencies_satisfied = true
next_action = "run"
done_when = "done"
halt_if = "never"

[[command_registry]]
id = "cmd-escape"
argv_prefix = {_json.dumps([sys.executable, "-c", "print('escape')"])}
path_scope = "../../.."
side_effect_class = "read-only"
network_allowed = false
timeout_seconds = 10
output_budget_bytes = 65536
sensitive_output_policy = "none"
approval_requirement = "none"
rollback_class = "reversible"
status = "enabled"
""",
                encoding="utf-8",
            )
            store = RuntimeManagerStore(root)
            store.sync_observation_center()

            result = store.run_command("cmd-escape")

            self.assertFalse(result.eligible)
            self.assertIn("path_scope_violation", result.blockers)
            self.assertEqual(result.event_id, -1)

    def test_run_command_no_bypass_without_eligibility(self) -> None:
        """run_command must not launch a subprocess when check_command_eligibility blocks."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            # No observation center → DB doesn't exist
            store = RuntimeManagerStore(root)

            with self.assertRaises(RuntimeManagerStoreError):
                store.run_command("cmd-any")

    def test_run_command_argv_is_exactly_registered_prefix(self) -> None:
        """run_command executes exactly argv_prefix — no extra args accepted."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            argv = [sys.executable, "-c", "print('fixed-argv')"]
            self._setup_and_sync(root, argv_prefix=argv)
            store = RuntimeManagerStore(root)

            result = store.run_command("cmd-run")

            self.assertTrue(result.eligible)
            self.assertEqual(result.argv, tuple(argv))
            self.assertIn("fixed-argv", result.stdout)

    def test_run_command_path_scope_sibling_prefix_is_rejected(self) -> None:
        """Path scope check uses relative_to, not startswith — sibling with same prefix is rejected."""
        import json as _json
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            # Create a sibling directory whose name starts with root's name
            root_name = root.name
            sibling = root.parent / (root_name + "_sibling")
            sibling.mkdir()

            (root / "docs" / "operations").mkdir(parents=True, exist_ok=True)
            (root / "docs" / "operations" / "observation_center.toml").write_text(
                f"""[center]
version = 1
queue_authority = "machine-primary"
single_flight = true

[projections]
system_state = "p"
opportunity_map = "p"

[[observations]]
id = "obs-sib"
title = "sibling test"
status = "open"
kind = "slice"
priority = "critical"
boundary = "authorized"
trigger = "TRIGGER.md"
dependencies = []
dependencies_satisfied = true
next_action = "run"
done_when = "done"
halt_if = "never"

[[command_registry]]
id = "cmd-sib"
argv_prefix = {_json.dumps([sys.executable, "-c", "print('sib')"])}
path_scope = "../{root_name}_sibling"
side_effect_class = "read-only"
network_allowed = false
timeout_seconds = 10
output_budget_bytes = 65536
sensitive_output_policy = "none"
approval_requirement = "none"
rollback_class = "reversible"
status = "enabled"
""",
                encoding="utf-8",
            )
            store = RuntimeManagerStore(root)
            store.sync_observation_center()

            result = store.run_command("cmd-sib")

            self.assertFalse(result.eligible)
            self.assertIn("path_scope_violation", result.blockers)


class ExecutionEvidenceTests(unittest.TestCase):
    def _setup_and_sync(self, root: Path, **kwargs) -> None:
        _run_command_center(root, **kwargs)
        store = RuntimeManagerStore(root)
        store.sync_observation_center()

    def test_execution_evidence_table_exists_in_schema(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            _write_observation_center(root, _observation("obs-a"))
            store = RuntimeManagerStore(root)
            store.sync_observation_center()

            with closing(sqlite3.connect(store.db_path)) as conn:
                tables = {row[0] for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )}
            self.assertIn("execution_evidence", tables)

    def test_run_command_records_execution_evidence_row(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            argv = [sys.executable, "-c", "print('evidence-test')"]
            self._setup_and_sync(root, argv_prefix=argv)
            store = RuntimeManagerStore(root)

            result = store.run_command("cmd-run")

            self.assertTrue(result.eligible)
            self.assertGreater(result.evidence_id, 0)

            with closing(sqlite3.connect(store.db_path)) as conn:
                conn.row_factory = sqlite3.Row
                row = conn.execute(
                    "SELECT * FROM execution_evidence WHERE evidence_id = ?",
                    (result.evidence_id,),
                ).fetchone()

            self.assertIsNotNone(row)
            self.assertEqual(row["command_id"], "cmd-run")
            self.assertEqual(row["observation_id"], "obs-run")
            self.assertEqual(row["rollback_class"], "reversible")
            self.assertEqual(row["returncode"], 0)
            self.assertFalse(bool(row["timed_out"]))
            self.assertFalse(bool(row["stdout_truncated"]))
            self.assertFalse(bool(row["stderr_truncated"]))
            self.assertFalse(bool(row["output_redacted"]))
            self.assertEqual(row["event_id"], result.event_id)

    def test_evidence_stdout_digest_matches_raw_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            argv = [sys.executable, "-c", "print('digest-check')"]
            self._setup_and_sync(root, argv_prefix=argv)
            store = RuntimeManagerStore(root)

            result = store.run_command("cmd-run")

            with closing(sqlite3.connect(store.db_path)) as conn:
                conn.row_factory = sqlite3.Row
                row = conn.execute(
                    "SELECT stdout_digest FROM execution_evidence WHERE evidence_id = ?",
                    (result.evidence_id,),
                ).fetchone()

            expected_digest = hashlib.sha256("digest-check\n".encode()).hexdigest()
            self.assertEqual(row["stdout_digest"], expected_digest)

    def test_evidence_digest_captured_before_truncation(self) -> None:
        """stdout_digest must reflect raw output even when truncated in the result."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            argv = [sys.executable, "-c", "print('x' * 500)"]
            self._setup_and_sync(root, argv_prefix=argv, output_budget_bytes=50)
            store = RuntimeManagerStore(root)

            result = store.run_command("cmd-run")

            self.assertTrue(result.stdout_truncated)
            self.assertIn("[TRUNCATED]", result.stdout)

            with closing(sqlite3.connect(store.db_path)) as conn:
                conn.row_factory = sqlite3.Row
                row = conn.execute(
                    "SELECT stdout_digest FROM execution_evidence WHERE evidence_id = ?",
                    (result.evidence_id,),
                ).fetchone()

            # Digest must NOT be of the truncated string — it must be of the full raw output.
            raw_full = "x" * 500 + "\n"
            self.assertEqual(row["stdout_digest"], hashlib.sha256(raw_full.encode()).hexdigest())

    def test_evidence_output_redacted_flag_set_when_policy_redact(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            argv = [sys.executable, "-c", "print('secret')"]
            self._setup_and_sync(root, argv_prefix=argv, sensitive_output_policy="redact")
            store = RuntimeManagerStore(root)

            result = store.run_command("cmd-run")

            self.assertEqual(result.stdout, "[REDACTED]")

            with closing(sqlite3.connect(store.db_path)) as conn:
                conn.row_factory = sqlite3.Row
                row = conn.execute(
                    "SELECT output_redacted, stdout_digest FROM execution_evidence WHERE evidence_id = ?",
                    (result.evidence_id,),
                ).fetchone()

            self.assertTrue(bool(row["output_redacted"]))
            # Digest still reflects raw output, not the redacted string.
            self.assertNotEqual(
                row["stdout_digest"],
                hashlib.sha256(b"[REDACTED]").hexdigest(),
            )

    def test_evidence_approval_id_recorded_when_approval_present(self) -> None:
        import json as _json
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            argv = [sys.executable, "-c", "print('approved')"]
            fp = _json.dumps(
                {"command_id": "cmd-run", "argv_prefix": argv, "path_scope": "."},
                separators=(",", ":"), sort_keys=True,
            )
            import hashlib as _hashlib
            fp_hash = "sha256:" + _hashlib.sha256(fp.encode()).hexdigest()
            (root / "docs" / "operations").mkdir(parents=True, exist_ok=True)
            (root / "docs" / "operations" / "observation_center.toml").write_text(
                f"""[center]
version = 1
queue_authority = "machine-primary"
single_flight = true

[projections]
system_state = "p"
opportunity_map = "p"

[[observations]]
id = "obs-run"
title = "run test observation"
status = "open"
kind = "slice"
priority = "critical"
boundary = "authorized"
trigger = "TRIGGER.md"
dependencies = []
dependencies_satisfied = true
next_action = "run"
done_when = "done"
halt_if = "never"

[[command_registry]]
id = "cmd-run"
argv_prefix = {_json.dumps(argv)}
path_scope = "."
side_effect_class = "read-only"
network_allowed = false
timeout_seconds = 10
output_budget_bytes = 65536
sensitive_output_policy = "none"
approval_requirement = "required"
rollback_class = "reversible"
status = "enabled"

[[approval_records]]
id = "appr-001"
subject_id = "obs-run"
action_fingerprint = "{fp_hash}"
status = "current"
scope = "obs-run"
actor = "human"
expiry = ""
revocation_path = "none"
audit_event_id = "evt-001"
""",
                encoding="utf-8",
            )
            store = RuntimeManagerStore(root)
            store.sync_observation_center()

            result = store.run_command("cmd-run")

            self.assertTrue(result.eligible)

            with closing(sqlite3.connect(store.db_path)) as conn:
                conn.row_factory = sqlite3.Row
                row = conn.execute(
                    "SELECT approval_id FROM execution_evidence WHERE evidence_id = ?",
                    (result.evidence_id,),
                ).fetchone()

            self.assertEqual(row["approval_id"], "appr-001")

    def test_evidence_ineligible_run_has_no_evidence_row(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            _write_observation_center(root, _observation("obs-a"))
            store = RuntimeManagerStore(root)
            store.sync_observation_center()

            result = store.run_command("cmd-not-registered")

            self.assertFalse(result.eligible)
            self.assertEqual(result.evidence_id, -1)

            with closing(sqlite3.connect(store.db_path)) as conn:
                count = conn.execute("SELECT COUNT(*) FROM execution_evidence").fetchone()[0]
            self.assertEqual(count, 0)

    def test_schema_guard_requires_execution_evidence_table(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            _write_observation_center(root, _observation("obs-a"))
            store = RuntimeManagerStore(root)
            store.sync_observation_center()

            with closing(sqlite3.connect(store.db_path)) as conn:
                conn.execute("DROP TABLE execution_evidence")
                conn.commit()

            with self.assertRaisesRegex(RuntimeManagerStoreError, "schema is missing or incomplete"):
                store.read_status()


class EvidenceReadAPITests(unittest.TestCase):
    """Tests for read_evidence() and list_evidence() on RuntimeManagerStore."""

    def _setup(self, root: Path, argv: list[str] | None = None) -> RuntimeManagerStore:
        _run_command_center(root, argv_prefix=argv or [sys.executable, "-c", "print('ok')"])
        store = RuntimeManagerStore(root)
        store.sync_observation_center()
        return store

    def test_read_evidence_returns_none_for_unknown_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            store = self._setup(root)
            self.assertIsNone(store.read_evidence(99999))

    def test_read_evidence_returns_evidence_after_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            store = self._setup(root)
            result = store.run_command("cmd-run")
            self.assertGreater(result.evidence_id, 0)

            ev = store.read_evidence(result.evidence_id)
            self.assertIsNotNone(ev)
            assert ev is not None
            self.assertIsInstance(ev, ExecutionEvidence)
            self.assertEqual(ev.evidence_id, result.evidence_id)
            self.assertEqual(ev.command_id, "cmd-run")
            self.assertEqual(ev.observation_id, "obs-run")

    def test_read_evidence_all_fields_match_run_result(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            store = self._setup(root, argv=[sys.executable, "-c", "print('field-check')"])
            result = store.run_command("cmd-run")

            ev = store.read_evidence(result.evidence_id)
            assert ev is not None
            self.assertEqual(ev.returncode, result.returncode)
            self.assertEqual(ev.timed_out, result.timed_out)
            self.assertAlmostEqual(ev.duration_seconds, result.duration_seconds, places=2)
            self.assertEqual(ev.stdout_truncated, result.stdout_truncated)
            self.assertEqual(ev.stderr_truncated, result.stderr_truncated)
            self.assertEqual(ev.event_id, result.event_id)
            self.assertTrue(ev.action_fingerprint.startswith("sha256:"))

    def test_list_evidence_empty_before_any_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            store = self._setup(root)
            rows = store.list_evidence()
            self.assertEqual(rows, ())

    def test_list_evidence_returns_rows_newest_first(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            store = self._setup(root)
            result1 = store.run_command("cmd-run")
            result2 = store.run_command("cmd-run")

            rows = store.list_evidence()
            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[0].evidence_id, result2.evidence_id)
            self.assertEqual(rows[1].evidence_id, result1.evidence_id)

    def test_list_evidence_limit_caps_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            store = self._setup(root)
            for _ in range(5):
                store.run_command("cmd-run")

            rows = store.list_evidence(limit=3)
            self.assertEqual(len(rows), 3)

    def test_list_evidence_limit_zero_returns_all_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            store = self._setup(root)
            for _ in range(4):
                store.run_command("cmd-run")

            rows = store.list_evidence(limit=0)
            self.assertEqual(len(rows), 4)

    def test_list_evidence_negative_limit_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            store = self._setup(root)
            store.run_command("cmd-run")

            with self.assertRaisesRegex(RuntimeManagerStoreError, "limit must be >= 0"):
                store.list_evidence(limit=-1)

    def test_list_evidence_observation_id_filter(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            store = self._setup(root)
            store.run_command("cmd-run")

            rows_match = store.list_evidence(observation_id="obs-run")
            rows_no_match = store.list_evidence(observation_id="nonexistent-obs")
            self.assertGreater(len(rows_match), 0)
            self.assertEqual(len(rows_no_match), 0)

    def test_execution_evidence_total_in_status(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            store = self._setup(root)
            status_before = store.read_status()
            self.assertEqual(status_before.execution_evidence_total, 0)

            store.run_command("cmd-run")
            store.run_command("cmd-run")
            status_after = store.read_status()
            self.assertEqual(status_after.execution_evidence_total, 2)

    def test_read_evidence_raises_when_db_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            store = RuntimeManagerStore(root)
            with self.assertRaises(RuntimeManagerStoreError):
                store.read_evidence(1)

    def test_list_evidence_raises_when_db_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            store = RuntimeManagerStore(root)
            with self.assertRaises(RuntimeManagerStoreError):
                store.list_evidence()


class StopConditionWriteAPITests(unittest.TestCase):
    """Tests for raise_stop_condition and resolve_stop_condition."""

    def _setup(self, tmp_dir: str) -> RuntimeManagerStore:
        root = Path(tmp_dir)
        source = _write_observation_center(root, _observation("obs-a", status="open"))
        store = RuntimeManagerStore(root)
        store.sync_observation_center(source)
        return store

    def _query_one(self, db_path: Path, sql: str, params: tuple = ()) -> tuple:
        with closing(sqlite3.connect(str(db_path))) as conn:
            return conn.execute(sql, params).fetchone()

    def _query_scalar(self, db_path: Path, sql: str, params: tuple = ()) -> object:
        row = self._query_one(db_path, sql, params)
        return row[0] if row else None

    def test_raise_stop_condition_returns_managed_stop_condition(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = self._setup(tmp_dir)
            sc = store.raise_stop_condition("obs-a", reason="gate failed", severity="blocking")
            self.assertIsInstance(sc, ManagedStopCondition)
            self.assertEqual(sc.subject_id, "obs-a")
            self.assertEqual(sc.status, "active")
            self.assertEqual(sc.severity, "blocking")
            self.assertEqual(sc.reason, "gate failed")
            self.assertEqual(sc.resolved_at, "")
            self.assertNotEqual(sc.stop_condition_id, "")
            self.assertGreater(sc.event_id, 0)

    def test_raise_stop_condition_default_severity_is_blocking(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = self._setup(tmp_dir)
            sc = store.raise_stop_condition("obs-a", reason="auto")
            self.assertEqual(sc.severity, "blocking")

    def test_raise_stop_condition_informational_is_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = self._setup(tmp_dir)
            sc = store.raise_stop_condition("obs-a", reason="info", severity="informational")
            self.assertEqual(sc.severity, "informational")
            self.assertEqual(sc.status, "active")

    def test_raise_stop_condition_raises_on_invalid_severity(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = self._setup(tmp_dir)
            with self.assertRaises(RuntimeManagerStoreError):
                store.raise_stop_condition("obs-a", reason="x", severity="critical")

    def test_raise_stop_condition_raises_on_empty_subject_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = self._setup(tmp_dir)
            with self.assertRaises(RuntimeManagerStoreError):
                store.raise_stop_condition("", reason="test")

    def test_raise_stop_condition_raises_when_db_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            store = RuntimeManagerStore(root)
            with self.assertRaises(RuntimeManagerStoreError):
                store.raise_stop_condition("obs-a", reason="x")

    def test_raise_stop_condition_appends_stop_condition_raised_event(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = self._setup(tmp_dir)
            store.raise_stop_condition("obs-a", reason="gate")
            event = self._query_one(
                store.db_path, "SELECT event_type, subject_id FROM events ORDER BY event_id DESC LIMIT 1"
            )
            self.assertEqual(event[0], "stop_condition_raised")
            self.assertEqual(event[1], "obs-a")

    def test_active_blocking_stop_condition_blocks_selection_on_observation_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = self._setup(tmp_dir)
            store.raise_stop_condition("obs-a", reason="test-block")
            status = store.read_status()
            self.assertNotEqual(status.state, "ready")

    def test_active_blocking_stop_condition_on_runtime_manager_blocks_all(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = self._setup(tmp_dir)
            store.raise_stop_condition("runtime-manager", reason="global block")
            status = store.read_status()
            self.assertNotEqual(status.state, "ready")

    def test_active_stop_condition_on_star_blocks_all(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = self._setup(tmp_dir)
            store.raise_stop_condition("*", reason="wildcard block")
            status = store.read_status()
            self.assertNotEqual(status.state, "ready")

    def test_resolved_stop_condition_does_not_block_selection(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = self._setup(tmp_dir)
            sc = store.raise_stop_condition("obs-a", reason="test")
            store.resolve_stop_condition(sc.stop_condition_id)
            status = store.read_status()
            self.assertEqual(status.state, "ready")

    def test_resolve_stop_condition_returns_true_and_marks_resolved(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = self._setup(tmp_dir)
            sc = store.raise_stop_condition("obs-a", reason="test")
            result = store.resolve_stop_condition(sc.stop_condition_id)
            self.assertTrue(result)
            status_val = self._query_scalar(
                store.db_path,
                "SELECT status FROM managed_stop_conditions WHERE stop_condition_id = ?",
                (sc.stop_condition_id,),
            )
            self.assertEqual(status_val, "resolved")

    def test_resolve_stop_condition_returns_false_for_unknown_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = self._setup(tmp_dir)
            result = store.resolve_stop_condition("nonexistent-id")
            self.assertFalse(result)

    def test_resolve_stop_condition_returns_false_if_already_resolved(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = self._setup(tmp_dir)
            sc = store.raise_stop_condition("obs-a", reason="test")
            store.resolve_stop_condition(sc.stop_condition_id)
            result = store.resolve_stop_condition(sc.stop_condition_id)
            self.assertFalse(result)

    def test_resolve_stop_condition_appends_stop_condition_resolved_event(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = self._setup(tmp_dir)
            sc = store.raise_stop_condition("obs-a", reason="test")
            store.resolve_stop_condition(sc.stop_condition_id)
            event_type = self._query_scalar(
                store.db_path, "SELECT event_type FROM events ORDER BY event_id DESC LIMIT 1"
            )
            self.assertEqual(event_type, "stop_condition_resolved")

    def test_resolve_stop_condition_raises_when_db_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            store = RuntimeManagerStore(root)
            with self.assertRaises(RuntimeManagerStoreError):
                store.resolve_stop_condition("some-id")

    def test_multiple_stop_conditions_all_must_be_resolved_to_unblock(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = self._setup(tmp_dir)
            sc1 = store.raise_stop_condition("obs-a", reason="first")
            sc2 = store.raise_stop_condition("obs-a", reason="second")
            store.resolve_stop_condition(sc1.stop_condition_id)
            status_after_first = store.read_status()
            self.assertNotEqual(status_after_first.state, "ready")
            store.resolve_stop_condition(sc2.stop_condition_id)
            status_after_both = store.read_status()
            self.assertEqual(status_after_both.state, "ready")


class ValidationWriterAPITests(unittest.TestCase):
    """Tests for record_validation."""

    def _setup(self, tmp_dir: str) -> RuntimeManagerStore:
        root = Path(tmp_dir)
        source = _write_observation_center(root, _observation("obs-a", status="open"))
        store = RuntimeManagerStore(root)
        store.sync_observation_center(source)
        return store

    def _query_one(self, db_path: Path, sql: str, params: tuple = ()) -> tuple:
        with closing(sqlite3.connect(str(db_path))) as conn:
            return conn.execute(sql, params).fetchone()

    def _query_scalar(self, db_path: Path, sql: str, params: tuple = ()) -> object:
        row = self._query_one(db_path, sql, params)
        return row[0] if row else None

    def _future_iso(self, seconds: int = 300) -> str:
        from datetime import datetime, timedelta, timezone
        return (datetime.now(timezone.utc) + timedelta(seconds=seconds)).isoformat(timespec="seconds")

    def test_record_validation_returns_managed_validation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = self._setup(tmp_dir)
            fresh = self._future_iso()
            val = store.record_validation("val-1", "obs-a", "green", reason="passed", fresh_until=fresh)
            self.assertIsInstance(val, ManagedValidation)
            self.assertEqual(val.validation_id, "val-1")
            self.assertEqual(val.subject_id, "obs-a")
            self.assertEqual(val.status, "green")
            self.assertEqual(val.fresh_until, fresh)
            self.assertGreater(val.event_id, 0)

    def test_record_validation_green_requires_fresh_until(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = self._setup(tmp_dir)
            with self.assertRaises(RuntimeManagerStoreError):
                store.record_validation("val-1", "obs-a", "green", reason="x", fresh_until="")

    def test_record_validation_red_clears_fresh_until(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = self._setup(tmp_dir)
            val = store.record_validation("val-1", "obs-a", "red", reason="failed", fresh_until="2099-01-01T00:00:00+00:00")
            self.assertEqual(val.fresh_until, "")
            self.assertEqual(val.status, "red")

    def test_record_validation_stale_clears_fresh_until(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = self._setup(tmp_dir)
            val = store.record_validation("val-1", "obs-a", "stale", reason="stale")
            self.assertEqual(val.fresh_until, "")

    def test_record_validation_raises_on_invalid_status(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = self._setup(tmp_dir)
            with self.assertRaises(RuntimeManagerStoreError):
                store.record_validation("val-1", "obs-a", "unknown", reason="x")

    def test_record_validation_overwrites_existing_record(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = self._setup(tmp_dir)
            fresh = self._future_iso()
            store.record_validation("val-1", "obs-a", "green", reason="first", fresh_until=fresh)
            val = store.record_validation("val-1", "obs-a", "red", reason="second")
            self.assertEqual(val.status, "red")
            status_val = self._query_scalar(
                store.db_path, "SELECT status FROM managed_validations WHERE validation_id = ?", ("val-1",)
            )
            self.assertEqual(status_val, "red")

    def test_record_validation_appends_validation_recorded_event(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = self._setup(tmp_dir)
            store.record_validation("val-1", "obs-a", "red", reason="x")
            event = self._query_one(
                store.db_path, "SELECT event_type, subject_id FROM events ORDER BY event_id DESC LIMIT 1"
            )
            self.assertEqual(event[0], "validation_recorded")
            self.assertEqual(event[1], "obs-a")

    def _write_obs_with_validation_req(self, root: Path, validation_id: str) -> Path:
        operations = root / "docs" / "operations"
        operations.mkdir(parents=True, exist_ok=True)
        path = operations / "observation_center.toml"
        path.write_text(f"""
[center]
version = 1
queue_authority = "machine-primary"
single_flight = true

[projections]
system_state = "projection only"
opportunity_map = "projection only"

[[observations]]
id = "obs-a"
title = "obs-a title"
status = "open"
kind = "slice"
priority = "medium"
boundary = "core/read-model only"
trigger = "trigger.md"
dependencies = []
dependencies_satisfied = true
required_validations = ["{validation_id}"]
next_action = "do obs-a"
done_when = "done"
halt_if = "halt"
""".lstrip(), encoding="utf-8")
        return path

    def test_green_managed_validation_satisfies_required_validation_gate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            source = self._write_obs_with_validation_req(root, "val-gate")
            store = RuntimeManagerStore(root)
            store.sync_observation_center(source)
            status_before = store.read_status()
            self.assertNotEqual(status_before.state, "ready")
            fresh = self._future_iso()
            store.record_validation("val-gate", "obs-a", "green", reason="ok", fresh_until=fresh)
            status_after = store.read_status()
            self.assertEqual(status_after.state, "ready")

    def test_red_managed_validation_blocks_required_validation_gate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            source = self._write_obs_with_validation_req(root, "val-gate")
            store = RuntimeManagerStore(root)
            store.sync_observation_center(source)
            store.record_validation("val-gate", "obs-a", "red", reason="fail")
            status = store.read_status()
            self.assertNotEqual(status.state, "ready")

    def test_managed_validation_overrides_toml_green_with_red(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            fresh = self._future_iso()
            source = self._write_obs_with_validation_req(root, "val-gate")
            source.write_text(source.read_text(encoding="utf-8") + f"""
[[validation_records]]
id = "val-gate"
subject_id = "obs-a"
status = "green"
checked_at = "2026-01-01T00:00:00+00:00"
fresh_until = "{fresh}"
command_id = ""
evidence_id = ""
reason = "toml-green"
""", encoding="utf-8")
            store = RuntimeManagerStore(root)
            store.sync_observation_center(source)
            status_before = store.read_status()
            self.assertEqual(status_before.state, "ready")
            store.record_validation("val-gate", "obs-a", "red", reason="managed-red")
            status_after = store.read_status()
            self.assertNotEqual(status_after.state, "ready")

    def test_record_validation_raises_when_db_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            store = RuntimeManagerStore(root)
            with self.assertRaises(RuntimeManagerStoreError):
                store.record_validation("val-1", "obs-a", "red", reason="x")


class RollbackRegistryTests(unittest.TestCase):
    """Tests for register_rollback and rollback_command."""

    def _setup(self, tmp_dir: str, rollback_class: str = "reversible") -> tuple[RuntimeManagerStore, Path]:
        root = Path(tmp_dir)
        source = _write_observation_center(
            root,
            _observation("obs-a", status="open")
            + _command_registry_entry(
                "cmd-fwd",
                argv_prefix=["python", "-c", "print('fwd')"],
                approval_requirement="none",
                rollback_class=rollback_class,
            ),
        )
        store = RuntimeManagerStore(root)
        store.sync_observation_center(source)
        return store, source

    def _query_one(self, db_path: Path, sql: str, params: tuple = ()) -> tuple:
        with closing(sqlite3.connect(str(db_path))) as conn:
            return conn.execute(sql, params).fetchone()

    def _query_scalar(self, db_path: Path, sql: str, params: tuple = ()) -> object:
        row = self._query_one(db_path, sql, params)
        return row[0] if row else None

    def test_register_rollback_returns_rollback_policy(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            store, _ = self._setup(tmp_dir)
            policy = store.register_rollback("cmd-fwd", argv_prefix=["python", "-c", "print('undo')"])
            self.assertIsInstance(policy, RollbackPolicy)
            self.assertEqual(policy.forward_command_id, "cmd-fwd")
            self.assertEqual(policy.status, "enabled")
            self.assertEqual(policy.argv_prefix, ("python", "-c", "print('undo')"))
            self.assertNotEqual(policy.rollback_id, "")

    def test_register_rollback_raises_when_forward_command_not_found(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            store, _ = self._setup(tmp_dir)
            with self.assertRaises(RuntimeManagerStoreError):
                store.register_rollback("nonexistent-cmd", argv_prefix=["echo", "undo"])

    def test_register_rollback_raises_when_forward_command_is_irreversible(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            store, _ = self._setup(tmp_dir, rollback_class="irreversible")
            with self.assertRaises(RuntimeManagerStoreError):
                store.register_rollback("cmd-fwd", argv_prefix=["echo", "undo"])

    def test_register_rollback_raises_on_empty_argv(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            store, _ = self._setup(tmp_dir)
            with self.assertRaises(RuntimeManagerStoreError):
                store.register_rollback("cmd-fwd", argv_prefix=[])

    def test_register_rollback_raises_when_db_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            store = RuntimeManagerStore(root)
            with self.assertRaises(RuntimeManagerStoreError):
                store.register_rollback("cmd-fwd", argv_prefix=["echo", "undo"])

    def test_register_rollback_disables_previous_policy_on_re_registration(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            store, _ = self._setup(tmp_dir)
            first = store.register_rollback("cmd-fwd", argv_prefix=["echo", "first"])
            second = store.register_rollback("cmd-fwd", argv_prefix=["echo", "second"])
            first_status = self._query_scalar(
                store.db_path, "SELECT status FROM rollback_registry WHERE rollback_id = ?", (first.rollback_id,)
            )
            second_status = self._query_scalar(
                store.db_path, "SELECT status FROM rollback_registry WHERE rollback_id = ?", (second.rollback_id,)
            )
            self.assertEqual(first_status, "disabled")
            self.assertEqual(second_status, "enabled")

    def test_register_rollback_appends_rollback_registered_event(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            store, _ = self._setup(tmp_dir)
            store.register_rollback("cmd-fwd", argv_prefix=["echo", "undo"])
            event = self._query_one(
                store.db_path, "SELECT event_type, subject_id FROM events ORDER BY event_id DESC LIMIT 1"
            )
            self.assertEqual(event[0], "rollback_registered")
            self.assertEqual(event[1], "cmd-fwd")

    def test_rollback_command_returns_ineligible_when_evidence_not_found(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            store, _ = self._setup(tmp_dir)
            result = store.rollback_command(999)
            self.assertIsInstance(result, RollbackResult)
            self.assertFalse(result.eligible)
            self.assertIn("evidence_not_found", result.blockers)

    def test_rollback_command_returns_ineligible_when_command_is_irreversible(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            store, _ = self._setup(tmp_dir, rollback_class="irreversible")
            run = store.run_command("cmd-fwd")
            result = store.rollback_command(run.evidence_id)
            self.assertFalse(result.eligible)
            self.assertIn("rollback_irreversible", result.blockers)

    def test_rollback_command_returns_ineligible_when_no_rollback_policy(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            store, _ = self._setup(tmp_dir)
            run = store.run_command("cmd-fwd")
            result = store.rollback_command(run.evidence_id)
            self.assertFalse(result.eligible)
            self.assertIn("no_rollback_policy", result.blockers)

    def test_rollback_command_executes_and_records_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            store, _ = self._setup(tmp_dir)
            run = store.run_command("cmd-fwd")
            store.register_rollback("cmd-fwd", argv_prefix=["python", "-c", "print('rollback ok')"])
            result = store.rollback_command(run.evidence_id)
            self.assertTrue(result.eligible)
            self.assertEqual(result.original_evidence_id, run.evidence_id)
            self.assertGreater(result.rollback_evidence_id, 0)
            self.assertEqual(result.returncode, 0)
            self.assertIn("rollback:cmd-fwd", result.command_id)

    def test_rollback_command_appends_rollback_executed_event(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            store, _ = self._setup(tmp_dir)
            run = store.run_command("cmd-fwd")
            store.register_rollback("cmd-fwd", argv_prefix=["python", "-c", "print('undo')"])
            store.rollback_command(run.evidence_id)
            event = self._query_one(
                store.db_path, "SELECT event_type FROM events ORDER BY event_id DESC LIMIT 1"
            )
            self.assertEqual(event[0], "rollback_executed")

    def test_rollback_command_records_rollback_evidence_in_execution_evidence_table(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            store, _ = self._setup(tmp_dir)
            run = store.run_command("cmd-fwd")
            store.register_rollback("cmd-fwd", argv_prefix=["python", "-c", "print('undo')"])
            result = store.rollback_command(run.evidence_id)
            ev = store.read_evidence(result.rollback_evidence_id)
            self.assertIsNotNone(ev)
            assert ev is not None
            self.assertEqual(ev.command_id, "rollback:cmd-fwd")
            self.assertEqual(ev.observation_id, "obs-a")

    def test_rollback_command_raises_when_db_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            store = RuntimeManagerStore(root)
            with self.assertRaises(RuntimeManagerStoreError):
                store.rollback_command(1)


class LeaseWriteAPITests(unittest.TestCase):
    """Tests for acquire_lease, release_lease, heartbeat_lease, reclaim_expired_leases."""

    def _setup(self, tmp_dir: str) -> RuntimeManagerStore:
        root = Path(tmp_dir)
        source = _write_observation_center(root, _observation("obs-a", status="open"))
        store = RuntimeManagerStore(root)
        store.sync_observation_center(source)
        return store

    def _query_one(self, db_path: Path, sql: str, params: tuple = ()) -> tuple:
        with closing(sqlite3.connect(str(db_path))) as conn:
            return conn.execute(sql, params).fetchone()

    def _query_scalar(self, db_path: Path, sql: str, params: tuple = ()) -> object:
        row = self._query_one(db_path, sql, params)
        return row[0] if row else None

    def test_acquire_lease_returns_acquired_lease_with_correct_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = self._setup(tmp_dir)
            lease = store.acquire_lease("obs-a", owner="agent-1", ttl_seconds=60, reason="testing")
            self.assertIsInstance(lease, AcquiredLease)
            self.assertEqual(lease.observation_id, "obs-a")
            self.assertEqual(lease.owner, "agent-1")
            self.assertEqual(lease.status, "active")
            self.assertEqual(lease.reason, "testing")
            self.assertEqual(lease.renewed_at, "")
            self.assertEqual(lease.released_at, "")
            self.assertNotEqual(lease.lease_id, "")
            self.assertNotEqual(lease.acquired_at, "")
            self.assertNotEqual(lease.expires_at, "")
            self.assertGreater(lease.event_id, 0)

    def test_acquire_lease_expires_at_is_after_acquired_at(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = self._setup(tmp_dir)
            lease = store.acquire_lease("obs-a", owner="agent-1", ttl_seconds=300)
            self.assertGreater(lease.expires_at, lease.acquired_at)

    def test_acquire_lease_raises_on_second_active_lease_for_same_observation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = self._setup(tmp_dir)
            store.acquire_lease("obs-a", owner="agent-1", ttl_seconds=60)
            with self.assertRaises(RuntimeManagerStoreError):
                store.acquire_lease("obs-a", owner="agent-2", ttl_seconds=60)

    def test_acquire_lease_succeeds_after_previous_lease_is_released(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = self._setup(tmp_dir)
            lease = store.acquire_lease("obs-a", owner="agent-1", ttl_seconds=60)
            store.release_lease(lease.lease_id, owner="agent-1")
            new_lease = store.acquire_lease("obs-a", owner="agent-2", ttl_seconds=60)
            self.assertEqual(new_lease.status, "active")
            self.assertEqual(new_lease.owner, "agent-2")

    def test_acquire_lease_raises_when_db_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            store = RuntimeManagerStore(root)
            with self.assertRaises(RuntimeManagerStoreError):
                store.acquire_lease("obs-a", owner="agent-1", ttl_seconds=60)

    def test_acquire_lease_raises_on_non_positive_ttl(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = self._setup(tmp_dir)
            with self.assertRaises(RuntimeManagerStoreError):
                store.acquire_lease("obs-a", owner="agent-1", ttl_seconds=0)
            with self.assertRaises(RuntimeManagerStoreError):
                store.acquire_lease("obs-a", owner="agent-1", ttl_seconds=-1)

    def test_acquire_lease_appends_lease_acquired_event(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = self._setup(tmp_dir)
            before_events = self._query_scalar(store.db_path, "SELECT COUNT(*) FROM events")
            store.acquire_lease("obs-a", owner="agent-1", ttl_seconds=60)
            after_events = self._query_scalar(store.db_path, "SELECT COUNT(*) FROM events")
            self.assertEqual(after_events, before_events + 1)
            event = self._query_one(
                store.db_path, "SELECT event_type, subject_id FROM events ORDER BY event_id DESC LIMIT 1"
            )
            self.assertEqual(event[0], "lease_acquired")
            self.assertEqual(event[1], "obs-a")

    def test_release_lease_returns_true_and_marks_released(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = self._setup(tmp_dir)
            lease = store.acquire_lease("obs-a", owner="agent-1", ttl_seconds=60)
            result = store.release_lease(lease.lease_id, owner="agent-1")
            self.assertTrue(result)
            status = self._query_scalar(
                store.db_path, "SELECT status FROM managed_leases WHERE lease_id = ?", (lease.lease_id,)
            )
            self.assertEqual(status, "released")

    def test_release_lease_returns_false_for_unknown_lease_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = self._setup(tmp_dir)
            result = store.release_lease("nonexistent-id", owner="agent-1")
            self.assertFalse(result)

    def test_release_lease_returns_false_for_wrong_owner(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = self._setup(tmp_dir)
            lease = store.acquire_lease("obs-a", owner="agent-1", ttl_seconds=60)
            result = store.release_lease(lease.lease_id, owner="agent-2")
            self.assertFalse(result)

    def test_release_lease_returns_false_for_already_released_lease(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = self._setup(tmp_dir)
            lease = store.acquire_lease("obs-a", owner="agent-1", ttl_seconds=60)
            store.release_lease(lease.lease_id, owner="agent-1")
            result = store.release_lease(lease.lease_id, owner="agent-1")
            self.assertFalse(result)

    def test_release_lease_appends_lease_released_event(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = self._setup(tmp_dir)
            lease = store.acquire_lease("obs-a", owner="agent-1", ttl_seconds=60)
            store.release_lease(lease.lease_id, owner="agent-1")
            event_type = self._query_scalar(
                store.db_path, "SELECT event_type FROM events ORDER BY event_id DESC LIMIT 1"
            )
            self.assertEqual(event_type, "lease_released")

    def test_heartbeat_lease_renews_expires_at_and_sets_renewed_at(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = self._setup(tmp_dir)
            lease = store.acquire_lease("obs-a", owner="agent-1", ttl_seconds=60)
            updated = store.heartbeat_lease(lease.lease_id, owner="agent-1", ttl_seconds=120)
            self.assertIsNotNone(updated)
            assert updated is not None
            self.assertEqual(updated.status, "active")
            self.assertEqual(updated.lease_id, lease.lease_id)
            self.assertGreater(updated.expires_at, lease.expires_at)
            self.assertNotEqual(updated.renewed_at, "")

    def test_heartbeat_lease_returns_none_for_unknown_lease_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = self._setup(tmp_dir)
            result = store.heartbeat_lease("nonexistent-id", owner="agent-1", ttl_seconds=60)
            self.assertIsNone(result)

    def test_heartbeat_lease_returns_none_for_wrong_owner(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = self._setup(tmp_dir)
            lease = store.acquire_lease("obs-a", owner="agent-1", ttl_seconds=60)
            result = store.heartbeat_lease(lease.lease_id, owner="agent-2", ttl_seconds=60)
            self.assertIsNone(result)

    def test_heartbeat_lease_returns_none_for_released_lease(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = self._setup(tmp_dir)
            lease = store.acquire_lease("obs-a", owner="agent-1", ttl_seconds=60)
            store.release_lease(lease.lease_id, owner="agent-1")
            result = store.heartbeat_lease(lease.lease_id, owner="agent-1", ttl_seconds=60)
            self.assertIsNone(result)

    def test_heartbeat_lease_raises_on_non_positive_ttl(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = self._setup(tmp_dir)
            lease = store.acquire_lease("obs-a", owner="agent-1", ttl_seconds=60)
            with self.assertRaises(RuntimeManagerStoreError):
                store.heartbeat_lease(lease.lease_id, owner="agent-1", ttl_seconds=0)

    def test_heartbeat_lease_appends_lease_heartbeat_event(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = self._setup(tmp_dir)
            lease = store.acquire_lease("obs-a", owner="agent-1", ttl_seconds=60)
            store.heartbeat_lease(lease.lease_id, owner="agent-1", ttl_seconds=120)
            event = self._query_one(
                store.db_path, "SELECT event_type, subject_id FROM events ORDER BY event_id DESC LIMIT 1"
            )
            self.assertEqual(event[0], "lease_heartbeat")
            self.assertEqual(event[1], "obs-a")

    def test_reclaim_expired_leases_returns_zero_when_no_expired_leases(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = self._setup(tmp_dir)
            store.acquire_lease("obs-a", owner="agent-1", ttl_seconds=300)
            count = store.reclaim_expired_leases()
            self.assertEqual(count, 0)

    def test_reclaim_expired_leases_marks_expired_as_reclaimed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = self._setup(tmp_dir)
            lease = store.acquire_lease("obs-a", owner="agent-1", ttl_seconds=60)
            with closing(sqlite3.connect(str(store.db_path))) as conn:
                conn.execute(
                    "UPDATE managed_leases SET expires_at = '2000-01-01T00:00:00+00:00' WHERE lease_id = ?",
                    (lease.lease_id,),
                )
                conn.commit()
            count = store.reclaim_expired_leases()
            self.assertEqual(count, 1)
            status = self._query_scalar(
                store.db_path, "SELECT status FROM managed_leases WHERE lease_id = ?", (lease.lease_id,)
            )
            self.assertEqual(status, "reclaimed")

    def test_reclaim_expired_leases_does_not_touch_non_expired_leases(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            source = _write_observation_center(
                root,
                _observation("obs-a", status="open") + "\n" + _observation("obs-b", status="open"),
            )
            store = RuntimeManagerStore(root)
            store.sync_observation_center(source)
            lease_a = store.acquire_lease("obs-a", owner="agent-1", ttl_seconds=60)
            with closing(sqlite3.connect(str(store.db_path))) as conn:
                conn.execute(
                    "UPDATE managed_leases SET expires_at = '2000-01-01T00:00:00+00:00', status = 'released' WHERE lease_id = ?",
                    (lease_a.lease_id,),
                )
                conn.commit()
            lease_b = store.acquire_lease("obs-b", owner="agent-2", ttl_seconds=300)
            count = store.reclaim_expired_leases()
            self.assertEqual(count, 0)
            status = self._query_scalar(
                store.db_path, "SELECT status FROM managed_leases WHERE lease_id = ?", (lease_b.lease_id,)
            )
            self.assertEqual(status, "active")

    def test_reclaim_expired_leases_appends_lease_reclaimed_event_per_lease(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            source = _write_observation_center(
                root,
                _observation("obs-a", status="open") + "\n" + _observation("obs-b", status="open"),
            )
            store = RuntimeManagerStore(root)
            store.sync_observation_center(source)
            lease_a = store.acquire_lease("obs-a", owner="agent-1", ttl_seconds=60)
            with closing(sqlite3.connect(str(store.db_path))) as conn:
                conn.execute(
                    "UPDATE managed_leases SET expires_at = '2000-01-01T00:00:00+00:00', status = 'released' WHERE lease_id = ?",
                    (lease_a.lease_id,),
                )
                conn.execute(
                    "INSERT INTO managed_leases (lease_id, observation_id, owner, status, acquired_at, expires_at, renewed_at, reason, released_at, event_id) "
                    "VALUES ('fake-lease', 'obs-b', 'agent-2', 'active', '2025-01-01T00:00:00+00:00', '2000-01-01T00:00:00+00:00', '', '', '', -1)"
                )
                conn.commit()
            before_events = self._query_scalar(store.db_path, "SELECT COUNT(*) FROM events")
            count = store.reclaim_expired_leases()
            self.assertEqual(count, 1)
            after_events = self._query_scalar(store.db_path, "SELECT COUNT(*) FROM events")
            self.assertEqual(after_events, before_events + 1)

    def test_reclaim_expired_leases_raises_when_db_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            store = RuntimeManagerStore(root)
            with self.assertRaises(RuntimeManagerStoreError):
                store.reclaim_expired_leases()

    def test_active_managed_lease_appears_in_read_status_active_leases(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = self._setup(tmp_dir)
            store.acquire_lease("obs-a", owner="agent-1", ttl_seconds=300)
            status = store.read_status()
            self.assertGreaterEqual(status.active_leases, 1)

    def test_wal_mode_is_active_after_initialize_schema(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            store = RuntimeManagerStore(root)
            store.initialize_schema()
            mode = self._query_scalar(store.db_path, "PRAGMA journal_mode")
            self.assertEqual(mode, "wal")


class ApprovalWriteAPITests(unittest.TestCase):
    """Tests for record_approval and revoke_approval."""

    def _setup(self, tmp_dir: str, *, approval_requirement: str = "required") -> RuntimeManagerStore:
        root = Path(tmp_dir)
        source = _write_observation_center(
            root,
            _observation("obs-a", status="open")
            + _command_registry_entry("cmd-guarded", approval_requirement=approval_requirement),
        )
        store = RuntimeManagerStore(root)
        store.sync_observation_center(source)
        return store

    def _query_one(self, db_path: Path, sql: str, params: tuple = ()) -> tuple:
        with closing(sqlite3.connect(str(db_path))) as conn:
            return conn.execute(sql, params).fetchone()

    def _query_scalar(self, db_path: Path, sql: str, params: tuple = ()) -> object:
        row = self._query_one(db_path, sql, params)
        return row[0] if row else None

    def test_record_approval_returns_approval_record(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = self._setup(tmp_dir)
            rec = store.record_approval("cmd-guarded", "obs-a", actor="human-operator")
            self.assertIsInstance(rec, ApprovalRecord)
            self.assertEqual(rec.command_id, "cmd-guarded")
            self.assertEqual(rec.subject_id, "obs-a")
            self.assertEqual(rec.actor, "human-operator")
            self.assertEqual(rec.status, "current")
            self.assertEqual(rec.scope, "single-use")
            self.assertNotEqual(rec.approval_id, "")
            self.assertNotEqual(rec.action_fingerprint, "")

    def test_record_approval_sets_action_fingerprint_matching_check_eligibility(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = self._setup(tmp_dir)
            rec = store.record_approval("cmd-guarded", "obs-a", actor="tester")
            expected_fp = _command_action_fingerprint("cmd-guarded")
            self.assertEqual(rec.action_fingerprint, expected_fp)

    def test_record_approval_raises_when_command_not_found(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = self._setup(tmp_dir)
            with self.assertRaises(RuntimeManagerStoreError):
                store.record_approval("cmd-unknown", "obs-a", actor="tester")

    def test_record_approval_raises_when_command_disabled(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            source = _write_observation_center(
                root,
                _observation("obs-a", status="open")
                + _command_registry_entry("cmd-off", approval_requirement="required", status="disabled"),
            )
            store = RuntimeManagerStore(root)
            store.sync_observation_center(source)
            with self.assertRaises(RuntimeManagerStoreError):
                store.record_approval("cmd-off", "obs-a", actor="tester")

    def test_record_approval_raises_when_db_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            store = RuntimeManagerStore(root)
            with self.assertRaises(RuntimeManagerStoreError):
                store.record_approval("cmd-guarded", "obs-a", actor="tester")

    def test_record_approval_appends_approval_recorded_event(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = self._setup(tmp_dir)
            before = self._query_scalar(store.db_path, "SELECT COUNT(*) FROM events")
            store.record_approval("cmd-guarded", "obs-a", actor="tester")
            after = self._query_scalar(store.db_path, "SELECT COUNT(*) FROM events")
            self.assertEqual(after, before + 1)
            event_type = self._query_scalar(
                store.db_path, "SELECT event_type FROM events ORDER BY event_id DESC LIMIT 1"
            )
            self.assertEqual(event_type, "approval_recorded")

    def test_record_approval_satisfies_eligibility_for_guarded_command(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = self._setup(tmp_dir)
            result_before = store.check_command_eligibility("cmd-guarded")
            self.assertFalse(result_before.eligible)
            self.assertIn("approval_required", result_before.blockers)
            store.record_approval("cmd-guarded", "obs-a", actor="human-operator")
            result_after = store.check_command_eligibility("cmd-guarded")
            self.assertTrue(result_after.eligible)

    def test_record_approval_appears_in_managed_approvals_as_current(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = self._setup(tmp_dir)
            rec = store.record_approval("cmd-guarded", "obs-a", actor="tester")
            status_val = self._query_scalar(
                store.db_path,
                "SELECT status FROM managed_approvals WHERE approval_id = ?",
                (rec.approval_id,),
            )
            self.assertEqual(status_val, "current")

    def test_record_approval_accepts_custom_scope_and_expires_at(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = self._setup(tmp_dir)
            from datetime import datetime, timedelta, timezone
            future = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(timespec="seconds")
            rec = store.record_approval(
                "cmd-guarded", "obs-a", actor="tester", scope="session", expires_at=future
            )
            self.assertEqual(rec.scope, "session")
            self.assertEqual(rec.expires_at, future)

    def test_revoke_approval_returns_true_and_marks_revoked(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = self._setup(tmp_dir)
            rec = store.record_approval("cmd-guarded", "obs-a", actor="tester")
            result = store.revoke_approval(rec.approval_id)
            self.assertTrue(result)
            status_val = self._query_scalar(
                store.db_path,
                "SELECT status FROM managed_approvals WHERE approval_id = ?",
                (rec.approval_id,),
            )
            self.assertEqual(status_val, "revoked")

    def test_revoke_approval_returns_false_for_unknown_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = self._setup(tmp_dir)
            result = store.revoke_approval("no-such-id")
            self.assertFalse(result)

    def test_revoke_approval_returns_false_for_already_revoked(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = self._setup(tmp_dir)
            rec = store.record_approval("cmd-guarded", "obs-a", actor="tester")
            store.revoke_approval(rec.approval_id)
            result = store.revoke_approval(rec.approval_id)
            self.assertFalse(result)

    def test_revoke_approval_unblocks_guarded_command_after_revocation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = self._setup(tmp_dir)
            rec = store.record_approval("cmd-guarded", "obs-a", actor="tester")
            eligible_before = store.check_command_eligibility("cmd-guarded").eligible
            self.assertTrue(eligible_before)
            store.revoke_approval(rec.approval_id)
            eligible_after = store.check_command_eligibility("cmd-guarded").eligible
            self.assertFalse(eligible_after)

    def test_revoke_approval_appends_approval_revoked_event(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = self._setup(tmp_dir)
            rec = store.record_approval("cmd-guarded", "obs-a", actor="tester")
            store.revoke_approval(rec.approval_id)
            event_type = self._query_scalar(
                store.db_path, "SELECT event_type FROM events ORDER BY event_id DESC LIMIT 1"
            )
            self.assertEqual(event_type, "approval_revoked")

    def test_revoke_approval_raises_when_db_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            store = RuntimeManagerStore(root)
            with self.assertRaises(RuntimeManagerStoreError):
                store.revoke_approval("any-id")

    def test_managed_approval_survives_sync(self) -> None:
        """record_approval must survive a subsequent sync_observation_center call."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = self._setup(tmp_dir)
            rec = store.record_approval("cmd-guarded", "obs-a", actor="tester")
            store.sync_observation_center()
            status_val = self._query_scalar(
                store.db_path,
                "SELECT status FROM managed_approvals WHERE approval_id = ?",
                (rec.approval_id,),
            )
            self.assertEqual(status_val, "current")


class ClosingSprintAPITests(unittest.TestCase):
    """Tests for list_leases, list_stop_conditions, read_validation, list_approvals,
    check_rollback_eligibility, list_rollback_runs, auto_stop_on_failure."""

    def _setup(self, tmp_dir: str) -> RuntimeManagerStore:
        root = Path(tmp_dir)
        source = _write_observation_center(
            root,
            _observation("obs-a", status="open")
            + _command_registry_entry("cmd-free", approval_requirement="none"),
        )
        store = RuntimeManagerStore(root)
        store.sync_observation_center(source)
        return store

    def _setup_guarded(self, tmp_dir: str) -> RuntimeManagerStore:
        root = Path(tmp_dir)
        source = _write_observation_center(
            root,
            _observation("obs-a", status="open")
            + _command_registry_entry("cmd-guarded", approval_requirement="required"),
        )
        store = RuntimeManagerStore(root)
        store.sync_observation_center(source)
        return store

    def _query_scalar(self, db_path: Path, sql: str, params: tuple = ()) -> object:
        with closing(sqlite3.connect(str(db_path))) as conn:
            row = conn.execute(sql, params).fetchone()
            return row[0] if row else None

    # ── list_leases ──────────────────────────────────────────────────────────

    def test_list_leases_returns_empty_when_no_leases(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = self._setup(tmp_dir)
            leases = store.list_leases()
            self.assertEqual(leases, ())

    def test_list_leases_returns_acquired_lease(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = self._setup(tmp_dir)
            store.acquire_lease("obs-a", owner="agent-1", ttl_seconds=60)
            leases = store.list_leases()
            self.assertEqual(len(leases), 1)
            self.assertEqual(leases[0].observation_id, "obs-a")
            self.assertEqual(leases[0].owner, "agent-1")

    def test_list_leases_filters_by_observation_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            source = _write_observation_center(
                root, _observation("obs-a", status="open") + _observation("obs-b", status="open")
            )
            store = RuntimeManagerStore(root)
            store.sync_observation_center(source)
            store.acquire_lease("obs-a", owner="a1", ttl_seconds=60)
            store.acquire_lease("obs-b", owner="b1", ttl_seconds=60)
            leases = store.list_leases(observation_id="obs-a")
            self.assertEqual(len(leases), 1)
            self.assertEqual(leases[0].observation_id, "obs-a")

    def test_list_leases_raises_when_db_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = RuntimeManagerStore(Path(tmp_dir))
            with self.assertRaises(RuntimeManagerStoreError):
                store.list_leases()

    # ── list_stop_conditions ─────────────────────────────────────────────────

    def test_list_stop_conditions_returns_empty_initially(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = self._setup(tmp_dir)
            conditions = store.list_stop_conditions()
            self.assertEqual(conditions, ())

    def test_list_stop_conditions_returns_raised_condition(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = self._setup(tmp_dir)
            store.raise_stop_condition("obs-a", reason="test")
            conditions = store.list_stop_conditions()
            self.assertEqual(len(conditions), 1)
            self.assertEqual(conditions[0].subject_id, "obs-a")

    def test_list_stop_conditions_filters_by_subject_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = self._setup(tmp_dir)
            store.raise_stop_condition("obs-a", reason="r1")
            store.raise_stop_condition("runtime-manager", reason="r2")
            conditions = store.list_stop_conditions(subject_id="obs-a")
            self.assertEqual(len(conditions), 1)
            self.assertEqual(conditions[0].subject_id, "obs-a")

    def test_list_stop_conditions_raises_when_db_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = RuntimeManagerStore(Path(tmp_dir))
            with self.assertRaises(RuntimeManagerStoreError):
                store.list_stop_conditions()

    # ── read_validation ──────────────────────────────────────────────────────

    def test_read_validation_returns_none_when_not_found(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = self._setup(tmp_dir)
            result = store.read_validation("no-such-id")
            self.assertIsNone(result)

    def test_read_validation_returns_recorded_validation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = self._setup(tmp_dir)
            from core.runtime_manager_store import ManagedValidation
            store.record_validation("val-1", "obs-a", status="green", reason="ok",
                                   fresh_until="2099-01-01T00:00:00Z")
            result = store.read_validation("val-1")
            self.assertIsNotNone(result)
            assert result is not None
            self.assertIsInstance(result, ManagedValidation)
            self.assertEqual(result.validation_id, "val-1")
            self.assertEqual(result.subject_id, "obs-a")
            self.assertEqual(result.status, "green")

    def test_read_validation_raises_when_db_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = RuntimeManagerStore(Path(tmp_dir))
            with self.assertRaises(RuntimeManagerStoreError):
                store.read_validation("val-1")

    # ── list_approvals ───────────────────────────────────────────────────────

    def test_list_approvals_returns_empty_initially(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = self._setup_guarded(tmp_dir)
            approvals = store.list_approvals()
            self.assertEqual(approvals, ())

    def test_list_approvals_returns_recorded_approval(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = self._setup_guarded(tmp_dir)
            from core.runtime_manager_store import ApprovalRecord
            store.record_approval("cmd-guarded", "obs-a", actor="tester")
            approvals = store.list_approvals()
            self.assertEqual(len(approvals), 1)
            self.assertIsInstance(approvals[0], ApprovalRecord)
            self.assertEqual(approvals[0].command_id, "cmd-guarded")

    def test_list_approvals_filters_by_subject_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            source = _write_observation_center(
                root,
                _observation("obs-a", status="open")
                + _observation("obs-b", status="open")
                + _command_registry_entry("cmd-guarded", approval_requirement="required"),
            )
            store = RuntimeManagerStore(root)
            store.sync_observation_center(source)
            store.record_approval("cmd-guarded", "obs-a", actor="t1")
            store.record_approval("cmd-guarded", "obs-b", actor="t2")
            approvals = store.list_approvals(subject_id="obs-a")
            self.assertEqual(len(approvals), 1)
            self.assertEqual(approvals[0].subject_id, "obs-a")

    def test_list_approvals_filters_by_command_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            source = _write_observation_center(
                root,
                _observation("obs-a", status="open")
                + _command_registry_entry("cmd-a", approval_requirement="required")
                + _command_registry_entry("cmd-b", approval_requirement="required"),
            )
            store = RuntimeManagerStore(root)
            store.sync_observation_center(source)
            store.record_approval("cmd-a", "obs-a", actor="t1")
            store.record_approval("cmd-b", "obs-a", actor="t2")
            approvals = store.list_approvals(command_id="cmd-a")
            self.assertEqual(len(approvals), 1)
            self.assertEqual(approvals[0].command_id, "cmd-a")

    def test_list_approvals_raises_when_db_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = RuntimeManagerStore(Path(tmp_dir))
            with self.assertRaises(RuntimeManagerStoreError):
                store.list_approvals()

    # ── check_rollback_eligibility ───────────────────────────────────────────

    def test_check_rollback_eligibility_returns_ineligible_for_unknown_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = self._setup(tmp_dir)
            result = store.check_rollback_eligibility(9999)
            self.assertFalse(result.eligible)
            self.assertIn("evidence_not_found", result.blockers)

    def test_check_rollback_eligibility_returns_ineligible_when_no_policy(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            _run_command_center(root, argv_prefix=[sys.executable, "-c", "print('ok')"])
            store = RuntimeManagerStore(root)
            store.sync_observation_center()
            run = store.run_command("cmd-run")
            result = store.check_rollback_eligibility(run.evidence_id)
            self.assertFalse(result.eligible)
            self.assertIn("no_rollback_policy", result.blockers)
            self.assertEqual(result.rollback_evidence_id, -1)

    def test_check_rollback_eligibility_returns_eligible_when_policy_registered(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            _run_command_center(root, argv_prefix=[sys.executable, "-c", "print('ok')"])
            store = RuntimeManagerStore(root)
            store.sync_observation_center()
            run = store.run_command("cmd-run")
            store.register_rollback("cmd-run", argv_prefix=(sys.executable, "-c", "print('undo')"))
            result = store.check_rollback_eligibility(run.evidence_id)
            self.assertTrue(result.eligible)
            self.assertEqual(result.blockers, ())
            self.assertEqual(result.rollback_evidence_id, -1)

    def test_check_rollback_eligibility_raises_when_db_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = RuntimeManagerStore(Path(tmp_dir))
            with self.assertRaises(RuntimeManagerStoreError):
                store.check_rollback_eligibility(1)

    # ── list_rollback_runs ───────────────────────────────────────────────────

    def test_list_rollback_runs_returns_empty_when_no_rollbacks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = self._setup(tmp_dir)
            runs = store.list_rollback_runs()
            self.assertEqual(runs, ())

    def test_list_rollback_runs_returns_rollback_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            _run_command_center(root, argv_prefix=[sys.executable, "-c", "print('ok')"])
            store = RuntimeManagerStore(root)
            store.sync_observation_center()
            run = store.run_command("cmd-run")
            store.register_rollback("cmd-run", argv_prefix=(sys.executable, "-c", "print('undo')"))
            store.rollback_command(run.evidence_id)
            runs = store.list_rollback_runs()
            self.assertEqual(len(runs), 1)
            self.assertTrue(runs[0].command_id.startswith("rollback:"))

    def test_list_rollback_runs_filters_by_forward_command_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            _run_command_center(root, argv_prefix=[sys.executable, "-c", "print('ok')"])
            store = RuntimeManagerStore(root)
            store.sync_observation_center()
            run = store.run_command("cmd-run")
            store.register_rollback("cmd-run", argv_prefix=(sys.executable, "-c", "print('undo')"))
            store.rollback_command(run.evidence_id)
            runs_all = store.list_rollback_runs()
            runs_filtered = store.list_rollback_runs(forward_command_id="cmd-run")
            self.assertEqual(len(runs_filtered), len(runs_all))
            runs_none = store.list_rollback_runs(forward_command_id="cmd-other")
            self.assertEqual(len(runs_none), 0)

    def test_list_rollback_runs_raises_when_db_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = RuntimeManagerStore(Path(tmp_dir))
            with self.assertRaises(RuntimeManagerStoreError):
                store.list_rollback_runs()

    # ── auto_stop_on_failure ─────────────────────────────────────────────────

    def test_auto_stop_on_failure_raises_stop_condition_on_nonzero_returncode(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            _run_command_center(root, argv_prefix=[sys.executable, "-c", "import sys; sys.exit(1)"])
            store = RuntimeManagerStore(root)
            store.sync_observation_center()
            result = store.run_command("cmd-run", auto_stop_on_failure=True)
            self.assertFalse(result.returncode == 0)
            conditions = store.list_stop_conditions()
            self.assertEqual(len(conditions), 1)
            self.assertEqual(conditions[0].subject_id, "obs-run")
            self.assertEqual(conditions[0].status, "active")

    def test_auto_stop_on_failure_false_does_not_raise_stop_on_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            _run_command_center(root, argv_prefix=[sys.executable, "-c", "import sys; sys.exit(1)"])
            store = RuntimeManagerStore(root)
            store.sync_observation_center()
            store.run_command("cmd-run", auto_stop_on_failure=False)
            conditions = store.list_stop_conditions()
            self.assertEqual(len(conditions), 0)

    def test_auto_stop_on_failure_does_not_raise_stop_on_success(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            _run_command_center(root, argv_prefix=[sys.executable, "-c", "print('ok')"])
            store = RuntimeManagerStore(root)
            store.sync_observation_center()
            result = store.run_command("cmd-run", auto_stop_on_failure=True)
            self.assertEqual(result.returncode, 0)
            conditions = store.list_stop_conditions()
            self.assertEqual(len(conditions), 0)

    def test_auto_stop_condition_blocks_subsequent_selection(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            _run_command_center(root, argv_prefix=[sys.executable, "-c", "import sys; sys.exit(1)"])
            store = RuntimeManagerStore(root)
            store.sync_observation_center()
            store.run_command("cmd-run", auto_stop_on_failure=True)
            status = store.read_status()
            # per-observation stop → obs-run ineligible → state "idle", not "blocked"
            self.assertIn(status.state, ("blocked", "idle"))
            self.assertTrue(any(d.code == "active_stop_condition" for d in status.gate_diagnostics))


class RuntimeManagerPhase5TraceMetricsReplayTests(unittest.TestCase):
    """Phase 5: native traces, local metrics, deterministic replay, and policy seam."""

    def _setup(self, root: Path, *, argv: list[str] | None = None) -> RuntimeManagerStore:
        _run_command_center(
            root,
            argv_prefix=argv or [sys.executable, "-c", "print('phase5-ok')"],
            sensitive_output_policy="none",
        )
        store = RuntimeManagerStore(root)
        store.sync_observation_center()
        return store

    def test_policy_decide_runtime_state_is_pure_and_matches_status_shape(self) -> None:
        self.assertEqual(
            decide_runtime_state(stale_source=True, selected_id="", has_observations=True).state,
            "blocked",
        )
        self.assertEqual(
            decide_runtime_state(stale_source=False, selected_id="obs-run", has_observations=True).state,
            "ready",
        )
        self.assertEqual(
            decide_runtime_state(stale_source=False, selected_id="", has_observations=True).state,
            "idle",
        )

    def test_sync_status_next_check_and_run_create_sanitized_traces(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            store = self._setup(root, argv=[sys.executable, "-c", "print('SECRET_TOKEN=abc123')"])

            status = store.read_status()
            next_item = store.read_next()
            eligibility = store.check_command_eligibility("cmd-run")
            result = store.run_command("cmd-run")

            self.assertEqual(status.state, "ready")
            self.assertIsNotNone(next_item)
            self.assertTrue(eligibility.eligible)
            self.assertEqual(result.returncode, 0)

            operations = {trace.operation for trace in store.list_traces(limit=0)}
            self.assertTrue({"sync", "status", "next", "check", "run"}.issubset(operations))
            run_trace = store.list_traces(operation="run", limit=1)[0]
            exported = store.export_trace(run_trace.trace_id, "json")
            self.assertIn('"trace_is_not_permission": true', exported)
            self.assertNotIn("SECRET_TOKEN=abc123", exported)
            self.assertNotIn("stdout", exported.lower())
            self.assertNotIn("stderr", exported.lower())

    def test_trace_export_jsonl_and_otel_json_are_projection_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            store = self._setup(root)
            store.read_status()
            trace = store.list_traces(operation="status", limit=1)[0]

            jsonl = store.export_trace(trace.trace_id, "jsonl")
            otel_json = json.loads(store.export_trace(trace.trace_id, "otel-json"))

            self.assertTrue(jsonl.splitlines()[0].startswith('{"trace":'))
            self.assertTrue(otel_json["projection_is_not_opentelemetry_export"])
            self.assertTrue(otel_json["telemetry_is_not_permission"])

    def test_metrics_count_runs_managed_records_and_trace_health(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            store = self._setup(root, argv=[sys.executable, "-c", "import sys; sys.exit(7)"])
            # run before raising stop/lease — stop condition on obs blocks selection
            store.run_command("cmd-run")
            store.record_validation(
                "val-green",
                "obs-run",
                status="green",
                reason="ok",
                fresh_until="2099-01-01T00:00:00+00:00",
            )
            store.raise_stop_condition("obs-run", reason="phase5 stop")
            store.acquire_lease("obs-run", owner="phase5", ttl_seconds=60)

            metrics = store.read_metrics()

            self.assertEqual(metrics.runs_total, 1)
            self.assertEqual(metrics.runs_failed, 1)
            self.assertEqual(metrics.execution_evidence_total, 1)
            self.assertEqual(metrics.validations_green, 1)
            self.assertEqual(metrics.stop_conditions_active, 1)
            self.assertEqual(metrics.leases_active, 1)
            self.assertGreaterEqual(metrics.traces_total, 1)

    def test_replay_scenario_passes_with_trace_metric_and_redaction_checks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            scenario = root / "scenario.json"
            store = self._setup(root, argv=[sys.executable, "-c", "print('SECRET_TOKEN=abc123')"])
            store.run_command("cmd-run")
            scenario.write_text(
                json.dumps(
                    {
                        "scenario_id": "phase5-replay-pass",
                        "checks": [
                            {"id": "has-run-trace", "type": "trace_exists", "operation": "run"},
                            {"id": "has-run-metric", "type": "metric_at_least", "metric": "runs_total", "min": 1},
                            {"id": "redacted-secret", "type": "trace_forbids_text", "text": "SECRET_TOKEN=abc123"},
                        ],
                    }
                ),
                encoding="utf-8",
            )

            replay = store.replay_scenario(scenario)

            self.assertTrue(replay.passed)
            self.assertEqual(replay.scenario_id, "phase5-replay-pass")
            self.assertTrue(replay.replay_digest.startswith("sha256:"))
            self.assertEqual({check.check_id for check in replay.checks}, {"has-run-trace", "has-run-metric", "redacted-secret"})
            self.assertEqual(store.list_traces(operation="replay", limit=1)[0].subject_id, "phase5-replay-pass")

    def test_replay_command_blocker_detects_missing_approval(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            source = _write_observation_center(
                root,
                _observation("obs-open")
                + _command_registry_entry("cmd-guarded", approval_requirement="required"),
            )
            scenario = root / "missing-approval.json"
            scenario.write_text(
                json.dumps(
                    {
                        "scenario_id": "approval-missing",
                        "checks": [
                            {
                                "id": "blocked-by-approval",
                                "type": "command_blocker",
                                "command_id": "cmd-guarded",
                                "expected_blocker": "approval_required",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            store = RuntimeManagerStore(root)
            store.sync_observation_center(source)

            replay = store.replay_scenario(scenario)

            self.assertTrue(replay.passed)


class RuntimeManagerIntegrityCheckTests(unittest.TestCase):
    """Phase 10 — RuntimeIntegrityReport and check_integrity() tests."""

    def _make_store(self, tmp_dir: str):
        root = Path(tmp_dir)
        store = RuntimeManagerStore(root)
        source = _write_observation_center(root, _observation("obs-open"))
        store.sync_observation_center(source)
        return store

    def test_integrity_report_is_not_permission(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = self._make_store(tmp)
            report = store.check_integrity()
            self.assertTrue(report.integrity_report_is_not_permission)

    def test_integrity_report_clean_on_fresh_db(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = self._make_store(tmp)
            report = store.check_integrity()
            self.assertEqual(report.orphan_trace_events, 0)
            self.assertEqual(report.incomplete_old_traces, 0)
            self.assertEqual(report.expired_active_leases, 0)
            self.assertEqual(report.expired_active_tokens, 0)
            self.assertEqual(report.evidence_without_trace, 0)
            self.assertTrue(report.policy_counter_plausibility)
            self.assertEqual(len(report.issues), 0)

    def test_integrity_report_detects_expired_active_token(self) -> None:
        import sqlite3 as _sqlite3

        with tempfile.TemporaryDirectory() as tmp:
            store = self._make_store(tmp)
            store.issue_adapter_token(
                agent_id="integrity-test-agent",
                agent_role="runner",
                scopes=["runtime:read"],
                ttl_seconds=3600,
            )
            # Force expiry to the past
            db_path = store.db_path
            conn = _sqlite3.connect(str(db_path))
            try:
                conn.execute(
                    "UPDATE adapter_tokens SET expires_at = '2000-01-01T00:00:00+00:00'"
                )
                conn.commit()
            finally:
                conn.close()

            report = store.check_integrity()
            self.assertGreater(report.expired_active_tokens, 0)
            self.assertTrue(any("expired_active_tokens" in i for i in report.issues))

    def test_integrity_report_detects_expired_active_lease(self) -> None:
        import sqlite3 as _sqlite3

        with tempfile.TemporaryDirectory() as tmp:
            store = self._make_store(tmp)
            store.acquire_lease("obs-open", "integrity-owner", 60, "integrity-test")

            db_path = store.db_path
            conn = _sqlite3.connect(str(db_path))
            try:
                conn.execute(
                    "UPDATE managed_leases SET expires_at = '2000-01-01T00:00:00+00:00'"
                )
                conn.commit()
            finally:
                conn.close()

            report = store.check_integrity()
            self.assertGreater(report.expired_active_leases, 0)
            self.assertTrue(any("expired_active_leases" in i for i in report.issues))

    def test_integrity_raises_when_db_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = RuntimeManagerStore(Path(tmp))
            with self.assertRaises(RuntimeManagerStoreError):
                store.check_integrity()

    def test_integrity_policy_counter_plausible_after_increment(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = self._make_store(tmp)
            store.increment_policy_counter("mcp_level_blocked")
            report = store.check_integrity()
            self.assertTrue(report.policy_counter_plausibility)

    def test_integrity_generated_at_is_iso8601(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = self._make_store(tmp)
            report = store.check_integrity()
            # Must parse as ISO-8601
            from datetime import datetime
            datetime.fromisoformat(report.generated_at)

    def test_integrity_current_minute_bucket_not_stale(self) -> None:
        """A rate bucket inserted this minute must NOT appear as stale."""
        import sqlite3 as _sqlite3
        import time as _time
        with tempfile.TemporaryDirectory() as tmp:
            store = self._make_store(tmp)
            conn = _sqlite3.connect(str(store.db_path))
            try:
                current_minute = int(_time.time() // 60)
                conn.execute(
                    "INSERT OR REPLACE INTO adapter_rate_buckets(bucket_key, count, window_start)"
                    " VALUES (?, 1, ?)",
                    ("test-current", current_minute),
                )
                conn.commit()
            finally:
                conn.close()
            report = store.check_integrity()
            self.assertEqual(report.stale_rate_buckets, 0)
            self.assertFalse(any("stale_rate_buckets" in i for i in report.issues))

    def test_integrity_old_bucket_is_stale(self) -> None:
        """A rate bucket with window_start 3 minutes ago must appear as stale."""
        import sqlite3 as _sqlite3
        import time as _time
        with tempfile.TemporaryDirectory() as tmp:
            store = self._make_store(tmp)
            conn = _sqlite3.connect(str(store.db_path))
            try:
                old_minute = int(_time.time() // 60) - 3
                conn.execute(
                    "INSERT OR REPLACE INTO adapter_rate_buckets(bucket_key, count, window_start)"
                    " VALUES (?, 1, ?)",
                    ("test-old", old_minute),
                )
                conn.commit()
            finally:
                conn.close()
            report = store.check_integrity()
            self.assertGreater(report.stale_rate_buckets, 0)
            self.assertTrue(any("stale_rate_buckets" in i for i in report.issues))

    def test_integrity_no_stale_issue_when_no_old_buckets(self) -> None:
        """A fresh DB with no rate buckets must have no stale_rate_buckets issue."""
        with tempfile.TemporaryDirectory() as tmp:
            store = self._make_store(tmp)
            report = store.check_integrity()
            self.assertEqual(report.stale_rate_buckets, 0)
            self.assertFalse(any("stale_rate_buckets" in i for i in report.issues))


if __name__ == "__main__":
    unittest.main()
