"""SQLite-backed read model for the local runtime manager queue."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import secrets
import sqlite3
import subprocess
import time
import tomllib
import uuid
from contextlib import closing

from core.runtime_manager_policy import (
    ActionInput,
    ActionClassification,
    classify_action,
    decide_runtime_state,
    LEVEL_ORDER as _AUTONOMY_LEVEL_ORDER,
)

SCHEMA_VERSION = 16
CENTER_AUTHORITY_TOML_IMPORT = "toml_import"
CENTER_AUTHORITY_SQLITE_PRIMARY = "sqlite_primary"
ADAPTER_TOKEN_SCOPES: frozenset[str] = frozenset(
    {"runtime:read", "runtime:lease", "runtime:execute", "runtime:trace", "runtime:metrics", "runtime:replay"}
)
RATE_LIMIT_READ = 60
RATE_LIMIT_MUTATE = 10
RATE_LIMIT_MUTATE_OPS: frozenset[str] = frozenset(
    {"run", "acquire_lease", "release_lease", "heartbeat_lease", "record_approval",
     "revoke_approval", "raise_stop_condition", "resolve_stop_condition", "record_validation", "rollback", "sync"}
)
SELECTION_AUDIT_POLICY_VERSION = "runtime-manager-selection-v1"
SELECTION_AUDIT_SORT_POLICY = ("priority_rank", "source_index", "id")
TRACE_POLICY_VERSION = "runtime-manager-trace-v1"
PRIORITY_RANK = {
    "critical": 0,
    "high": 1,
    "medium": 2,
    "low": 3,
}
ELIGIBLE_STATUSES = {"open"}
INFORMATIONAL_DIAGNOSTIC_CODES = frozenset({"active_lease_expired", "failed_replay_run"})


class RuntimeManagerStoreError(RuntimeError):
    """Raised when the runtime-manager SQLite read model cannot be used.

    ``code`` is a stable machine-readable diagnostic code (empty string = generic).
    Stable codes: lease_contention, lease_owner_mismatch, lease_expired_reclaimed,
    token_revoked_mid_session.
    """

    def __init__(self, message: str, code: str = "") -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class RuntimeGateDiagnostic:
    """Structured reason why a runtime-manager gate is not satisfied."""

    code: str
    subject_id: str
    details: tuple[str, ...]
    severity: str
    blocking: bool


@dataclass(frozen=True)
class RuntimeSelectionAuditEntry:
    """Per-observation scheduler audit entry."""

    observation_id: str
    status: str
    priority: str
    source_index: int
    eligible: bool
    sort_key: tuple[str, ...]
    blockers: tuple[str, ...]


@dataclass(frozen=True)
class RuntimeSelectionAudit:
    """Structured explanation of the scheduler decision."""

    policy_version: str
    sort_policy: tuple[str, ...]
    decision: str
    selected_id: str
    global_blockers: tuple[str, ...]
    eligible_ids: tuple[str, ...]
    entries: tuple[RuntimeSelectionAuditEntry, ...]


@dataclass(frozen=True)
class RuntimeObservation:
    """One imported runtime-manager work item."""

    id: str
    title: str
    status: str
    kind: str
    priority: str
    boundary: str
    trigger: str
    dependencies: tuple[str, ...]
    dependencies_satisfied: bool
    required_decisions: tuple[str, ...]
    required_evidence: tuple[str, ...]
    required_tools: tuple[str, ...]
    required_approvals: tuple[str, ...]
    required_validations: tuple[str, ...]
    next_action: str
    done_when: str
    halt_if: str
    source_path: str
    source_sha256: str
    source_index: int


@dataclass(frozen=True)
class RuntimeManagerStatus:
    """Read-only status returned by the runtime-manager read model."""

    state: str
    selected_id: str
    reason: str
    gate_diagnostics: tuple[RuntimeGateDiagnostic, ...]
    selection_audit: RuntimeSelectionAudit
    center_authority_mode: str
    source_authority: str
    source_path: str
    source_sha256: str
    stale_source: bool
    observations_total: int
    observations_open: int
    observations_blocked: int
    observations_waiting: int
    decisions_total: int
    decisions_current: int
    evidence_total: int
    evidence_accepted: int
    evidence_rejected: int
    tools_total: int
    tools_enabled: int
    approvals_total: int
    approvals_current: int
    events_total: int
    active_leases: int
    leases_expired: int
    replay_runs_total: int
    replay_runs_passed: int
    replay_runs_failed: int
    validations_total: int
    validations_green: int
    validations_red: int
    validations_stale: int
    validations_expired: int
    stop_conditions_total: int
    stop_conditions_active: int
    commands_total: int
    commands_enabled: int
    execution_evidence_total: int


@dataclass(frozen=True)
class RuntimeTraceEvent:
    """One sanitized event inside a Runtime Manager trace."""

    trace_event_id: int
    trace_id: str
    sequence: int
    event_name: str
    subject_id: str
    payload_digest: str
    payload_json: str
    created_at: str


@dataclass(frozen=True)
class RuntimeTrace:
    """Sanitized, replayable trace envelope for one Runtime Manager operation."""

    trace_id: str
    operation: str
    subject_id: str
    status: str
    policy_version: str
    causation_id: str
    correlation_id: str
    input_digest: str
    output_digest: str
    started_at: str
    finished_at: str
    event_count: int
    events: tuple[RuntimeTraceEvent, ...]


@dataclass(frozen=True)
class RuntimeManagerMetrics:
    """Local health counters for the Runtime Manager."""

    generated_at: str
    runs_total: int
    runs_passed: int
    runs_failed: int
    runs_timed_out: int
    execution_evidence_total: int
    approvals_current: int
    approvals_revoked: int
    validations_green: int
    validations_red: int
    validations_stale: int
    validations_expired: int
    stop_conditions_active: int
    stop_conditions_resolved: int
    leases_active: int
    leases_expired: int
    leases_reclaimed: int
    rollback_runs_total: int
    rollback_runs_passed: int
    rollback_runs_failed: int
    traces_total: int
    traces_incomplete: int
    evals_total: int
    evals_passed: int
    evals_failed: int
    # Phase 8: autonomy level counters (derived from execution_evidence)
    actions_l0: int = 0
    actions_l1: int = 0
    actions_l2: int = 0
    actions_l3: int = 0
    actions_l4: int = 0
    mcp_level_blocked: int = 0
    metrics_is_not_permission: bool = True


@dataclass(frozen=True)
class RuntimeReplayCheckResult:
    """Result for one deterministic runtime replay check."""

    check_id: str
    passed: bool
    reason: str


@dataclass(frozen=True)
class RuntimeReplayResult:
    """Deterministic replay result for one scenario file."""

    scenario_id: str
    passed: bool
    replay_digest: str
    checks: tuple[RuntimeReplayCheckResult, ...]
    authority: str = "runtime replay evidence only; not permission"


@dataclass(frozen=True)
class CommandPolicy:
    """Policy record for a registered command in the command_registry."""
    command_id: str
    argv_prefix: tuple[str, ...]
    path_scope: str
    side_effect_class: str
    network_allowed: bool
    timeout_seconds: int
    output_budget_bytes: int
    sensitive_output_policy: str
    approval_requirement: str
    rollback_class: str
    status: str
    # Phase 8 optional fields (defaults preserve backward compat)
    risk_level_override: str = ""
    requires_human_decision: bool = False
    data_sensitivity: str = "none"
    target_scope: str = "local"


@dataclass(frozen=True)
class CommandEligibilityResult:
    """Read-only enforcement check: is this command eligible to run right now?"""
    eligible: bool
    command_id: str
    reason: str
    blockers: tuple[str, ...]
    policy: CommandPolicy | None
    selected_observation_id: str
    gate_diagnostics: tuple[RuntimeGateDiagnostic, ...]
    # Phase 8 autonomy metadata
    autonomy_level: str = "L3_runtime_mutation"
    required_controls: tuple[str, ...] = ()
    friction_budget: int = 4
    autonomy_rationale: str = ""


@dataclass(frozen=True)
class ExecutionEvidence:
    """Immutable evidence record captured after each constrained command execution."""
    evidence_id: int           # rowid in execution_evidence; -1 if not recorded
    command_id: str
    observation_id: str
    approval_id: str           # empty string when approval_requirement="none"
    action_fingerprint: str
    rollback_class: str
    returncode: int
    timed_out: bool
    duration_seconds: float
    stdout_digest: str         # sha256 of raw stdout before truncation/redaction
    stderr_digest: str
    stdout_truncated: bool
    stderr_truncated: bool
    output_redacted: bool
    event_id: int              # foreign-key to events.event_id
    recorded_at: str
    autonomy_level: str = ""  # Phase 8: L0-L4 classification at execution time


@dataclass(frozen=True)
class ApprovalRecord:
    """Write-API approval record from the managed_approvals table."""
    approval_id: str
    subject_id: str         # observation_id this approval is scoped to
    action_fingerprint: str # sha256 of {command_id, argv_prefix, path_scope}
    command_id: str
    actor: str
    scope: str
    status: str             # 'current' | 'revoked'
    granted_at: str
    expires_at: str         # empty string = no expiry
    revoked_at: str         # empty string if not yet revoked
    event_id: int


@dataclass(frozen=True)
class RollbackPolicy:
    """Registered rollback policy mapping a forward command to its undo command."""
    rollback_id: str
    forward_command_id: str
    argv_prefix: tuple[str, ...]
    path_scope: str
    timeout_seconds: int
    output_budget_bytes: int
    status: str   # 'enabled' | 'disabled'


@dataclass(frozen=True)
class RollbackResult:
    """Result of a rollback_command() call."""
    eligible: bool
    original_evidence_id: int
    rollback_evidence_id: int   # -1 if not executed
    command_id: str
    argv: tuple[str, ...]
    stdout: str
    stderr: str
    returncode: int
    timed_out: bool
    duration_seconds: float
    blockers: tuple[str, ...]
    event_id: int


@dataclass(frozen=True)
class ManagedStopCondition:
    """Write-API stop condition from the managed_stop_conditions table."""
    stop_condition_id: str
    subject_id: str
    status: str       # 'active' | 'resolved'
    severity: str     # 'blocking' | 'informational'
    opened_at: str
    resolved_at: str  # empty string if not yet resolved
    reason: str
    event_id: int


@dataclass(frozen=True)
class ManagedValidation:
    """Write-API validation record from the managed_validations table."""
    validation_id: str
    subject_id: str
    status: str       # 'green' | 'red' | 'stale'
    checked_at: str
    fresh_until: str  # required for status='green', else empty
    command_id: str
    reason: str
    event_id: int


@dataclass(frozen=True)
class AcquiredLease:
    """Managed write-API lease record from the managed_leases table."""
    lease_id: str
    observation_id: str
    owner: str
    status: str          # 'active' | 'released' | 'reclaimed'
    acquired_at: str
    expires_at: str
    renewed_at: str      # empty string if never heartbeat-renewed
    reason: str
    released_at: str     # empty string if not yet released/reclaimed
    event_id: int


@dataclass(frozen=True)
class AdapterToken:
    """Persisted adapter credential record.  Raw token never stored here."""

    token_id: str
    agent_id: str
    agent_role: str
    scopes: tuple[str, ...]
    status: str
    issued_at: str
    expires_at: str
    revoked_at: str
    max_autonomy_level: str = "L3_runtime_mutation"
    token_is_not_credential: bool = True


@dataclass(frozen=True)
class RateLimitResult:
    """Result of a persistent rate limit check."""

    allowed: bool
    retry_after_seconds: int
    agent_id: str
    operation: str
    rate_limit_is_not_permission: bool = True


@dataclass(frozen=True)
class RuntimeIntegrityReport:
    """Diagnostic report from check_integrity().  Not a runtime gate — advisory only.

    integrity_report_is_not_permission = True (always).
    """

    generated_at: str
    orphan_trace_events: int
    incomplete_old_traces: int
    expired_active_leases: int
    expired_active_tokens: int
    stale_rate_buckets: int
    evidence_without_trace: int
    policy_counter_plausibility: bool
    issues: tuple[str, ...]
    integrity_report_is_not_permission: bool = True


@dataclass(frozen=True)
class CommandRunResult:
    """Result of a constrained subprocess execution through the enforcement chain."""
    eligible: bool
    command_id: str
    observation_id: str
    argv: tuple[str, ...]
    stdout: str
    stderr: str
    returncode: int          # -1=ineligible, -2=timeout kill, -3=failed to start
    timed_out: bool
    duration_seconds: float
    stdout_truncated: bool
    stderr_truncated: bool
    blockers: tuple[str, ...]
    event_id: int            # -1 if no event recorded
    evidence_id: int         # -1 if no evidence recorded


class RuntimeManagerStore:
    """Own the local `runtime.db` schema and read-only queue selection."""

    def __init__(self, root: str | Path, *, db_path: str | Path | None = None):
        self.root = Path(root).resolve()
        self.cerebro_dir = self.root / ".cerebro"
        self.db_path = Path(db_path).resolve() if db_path is not None else self.cerebro_dir / "runtime.db"

    def initialize_schema(self) -> None:
        """Create the SQLite schema if it does not exist."""
        self.cerebro_dir.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as connection:
            self._create_schema(connection)
            self._upsert_metadata(connection, "schema_version", str(SCHEMA_VERSION))
            self._upsert_metadata(connection, "store_role", "runtime-manager-read-model")
            if not self._read_metadata(connection).get("center_authority_mode"):
                self._upsert_metadata(connection, "center_authority_mode", CENTER_AUTHORITY_TOML_IMPORT)
            connection.commit()

    def sync_observation_center(self, observation_center_path: str | Path | None = None) -> RuntimeManagerStatus:
        """Import the current observation center into the SQLite read model."""
        source_path = self._resolve_observation_center_path(observation_center_path)
        self.cerebro_dir.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as connection:
            self._create_schema(connection)
            metadata = self._read_metadata(connection)
            if metadata.get("center_authority_mode") == CENTER_AUTHORITY_SQLITE_PRIMARY:
                synced_at = _utc_now()
                self._upsert_metadata(connection, "synced_at", synced_at)
                self._append_event(
                    connection,
                    event_type="runtime_sync_skipped",
                    subject_id="runtime-manager",
                    payload={"reason": "center_authority_is_sqlite_primary"},
                    created_at=synced_at,
                )
                connection.commit()
                return self.read_status()

        payload = self._read_observation_center(source_path)
        source_sha256 = self._sha256(source_path)
        imported_at = _utc_now()
        observations = payload.get("observations", [])
        if not isinstance(observations, list):
            raise RuntimeManagerStoreError("observation_center.toml observations must be a list")

        center_payload = payload.get("center", {})
        if not isinstance(center_payload, dict):
            center_payload = {}
        projections_payload = payload.get("projections", {})
        if not isinstance(projections_payload, dict):
            projections_payload = {}

        with closing(self._connect()) as connection:
            self._create_schema(connection)
            is_first_sync = connection.execute("SELECT COUNT(*) FROM events").fetchone()[0] == 0
            connection.execute("BEGIN")
            try:
                connection.execute("DELETE FROM observation_dependencies")
                connection.execute("DELETE FROM observations")
                connection.execute("DELETE FROM observation_decision_requirements")
                connection.execute("DELETE FROM observation_evidence_requirements")
                connection.execute("DELETE FROM observation_tool_requirements")
                connection.execute("DELETE FROM observation_approval_requirements")
                connection.execute("DELETE FROM observation_validation_requirements")
                connection.execute("DELETE FROM decisions")
                connection.execute("DELETE FROM evidence_records")
                connection.execute("DELETE FROM tool_registry")
                connection.execute("DELETE FROM approval_records")
                connection.execute("DELETE FROM runtime_leases")
                connection.execute("DELETE FROM replay_runs")
                connection.execute("DELETE FROM validation_records")
                connection.execute("DELETE FROM stop_conditions")
                connection.execute("DELETE FROM command_registry")
                self._upsert_metadata(connection, "schema_version", str(SCHEMA_VERSION))
                self._upsert_metadata(connection, "store_role", "runtime-manager-read-model")
                self._upsert_metadata(connection, "center_authority_mode", CENTER_AUTHORITY_TOML_IMPORT)
                self._upsert_metadata(connection, "source_authority", "observation_center.toml")
                self._upsert_metadata(connection, "source_path", _relative_or_absolute(source_path, self.root))
                self._upsert_metadata(connection, "source_sha256", source_sha256)
                self._upsert_metadata(connection, "synced_at", imported_at)
                self._upsert_metadata(connection, "center_version", str(center_payload.get("version", "")))
                self._upsert_metadata(connection, "center_updated_at", _string(center_payload.get("updated_at")))
                self._upsert_metadata(connection, "center_projection_role", _string(center_payload.get("projection_role")))
                self._upsert_metadata(connection, "authority_order", _string(center_payload.get("authority_order")))
                self._upsert_metadata(connection, "selection_contract", _string(center_payload.get("selection_contract")))
                self._upsert_metadata(connection, "selection_order", _string(center_payload.get("selection_order")))
                self._upsert_metadata(connection, "reconciliation_rule", _string(center_payload.get("reconciliation_rule")))
                self._upsert_metadata(connection, "overlap_policy", _string(center_payload.get("overlap_policy")))
                self._upsert_metadata(connection, "idempotency_contract", _string(center_payload.get("idempotency_contract")))
                self._upsert_metadata(connection, "history_policy", _string(center_payload.get("history_policy")))
                self._upsert_metadata(connection, "rotation_policy", _string(center_payload.get("rotation_policy")))
                self._upsert_metadata(connection, "checkpoint_policy", _string(center_payload.get("checkpoint_policy")))
                self._upsert_metadata(connection, "queue_authority", _string(center_payload.get("queue_authority")))
                self._upsert_metadata(connection, "single_flight", json.dumps(bool(center_payload.get("single_flight", True))))
                self._upsert_metadata(connection, "notify_once_blocked", json.dumps(bool(center_payload.get("notify_once_blocked", False))))
                self._upsert_metadata(connection, "projection_system_state", _string(projections_payload.get("system_state")))
                self._upsert_metadata(connection, "projection_opportunity_map", _string(projections_payload.get("opportunity_map")))
                self._upsert_metadata(connection, "projection_trigger_docs", _string(projections_payload.get("trigger_docs")))
                if is_first_sync:
                    self._append_event(
                        connection,
                        event_type="runtime_opened",
                        subject_id="runtime-manager",
                        payload={"schema_version": str(SCHEMA_VERSION), "reason": "first_sync"},
                        created_at=imported_at,
                    )
                for index, raw_observation in enumerate(observations):
                    observation = self._normalize_observation(raw_observation, source_path, source_sha256, index)
                    self._insert_observation(connection, observation, imported_at)
                    for dependency_index, dependency in enumerate(observation.dependencies):
                        connection.execute(
                            """
                            INSERT INTO observation_dependencies(observation_id, dependency_id, source_index)
                            VALUES (?, ?, ?)
                            """,
                            (observation.id, dependency, dependency_index),
                        )
                    for decision_id in observation.required_decisions:
                        connection.execute(
                            """
                            INSERT INTO observation_decision_requirements(observation_id, decision_id)
                            VALUES (?, ?)
                            """,
                            (observation.id, decision_id),
                        )
                    for evidence_id in observation.required_evidence:
                        connection.execute(
                            """
                            INSERT INTO observation_evidence_requirements(observation_id, evidence_id)
                            VALUES (?, ?)
                            """,
                            (observation.id, evidence_id),
                        )
                    for tool_id in observation.required_tools:
                        connection.execute(
                            """
                            INSERT INTO observation_tool_requirements(observation_id, tool_id)
                            VALUES (?, ?)
                            """,
                            (observation.id, tool_id),
                        )
                    for approval_id in observation.required_approvals:
                        connection.execute(
                            """
                            INSERT INTO observation_approval_requirements(observation_id, approval_id)
                            VALUES (?, ?)
                            """,
                            (observation.id, approval_id),
                        )
                    for validation_id in observation.required_validations:
                        connection.execute(
                            """
                            INSERT INTO observation_validation_requirements(observation_id, validation_id)
                            VALUES (?, ?)
                            """,
                            (observation.id, validation_id),
                        )
                    self._append_event(
                        connection,
                        event_type="queue_item_observed",
                        subject_id=observation.id,
                        payload={"status": observation.status, "priority": observation.priority},
                        created_at=imported_at,
                    )
                for raw_decision in payload.get("decisions", []):
                    self._insert_decision(connection, raw_decision, source_path, source_sha256, imported_at)
                for raw_evidence in payload.get("evidence_records", []):
                    self._insert_evidence_record(connection, raw_evidence, source_path, source_sha256, imported_at)
                for raw_tool in payload.get("tool_registry", []):
                    self._insert_tool(connection, raw_tool, source_path, source_sha256, imported_at)
                for raw_approval in payload.get("approval_records", []):
                    self._insert_approval(connection, raw_approval, source_path, source_sha256, imported_at)
                for raw_lease in payload.get("runtime_leases", []):
                    self._insert_lease(connection, raw_lease, source_path, source_sha256, imported_at)
                for raw_replay in payload.get("replay_runs", []):
                    self._insert_replay_run(connection, raw_replay, source_path, source_sha256, imported_at)
                for raw_validation in payload.get("validation_records", []):
                    self._insert_validation_record(connection, raw_validation, source_path, source_sha256, imported_at)
                for raw_stop_condition in payload.get("stop_conditions", []):
                    self._insert_stop_condition(connection, raw_stop_condition, source_path, source_sha256, imported_at)
                for raw_command in payload.get("command_registry", []):
                    self._insert_command(connection, raw_command, source_path, source_sha256, imported_at)
                ee_count = connection.execute("SELECT COUNT(*) FROM execution_evidence").fetchone()[0]
                self._append_event(
                    connection,
                    event_type="runtime_synced",
                    subject_id="runtime-manager",
                    payload={
                        "source_sha256": source_sha256,
                        "observations": len(observations),
                        "decisions": len(payload.get("decisions", [])),
                        "evidence_records": len(payload.get("evidence_records", [])),
                        "tool_registry": len(payload.get("tool_registry", [])),
                        "approval_records": len(payload.get("approval_records", [])),
                        "runtime_leases": len(payload.get("runtime_leases", [])),
                        "replay_runs": len(payload.get("replay_runs", [])),
                        "validation_records": len(payload.get("validation_records", [])),
                        "stop_conditions": len(payload.get("stop_conditions", [])),
                        "command_registry": len(payload.get("command_registry", [])),
                        "execution_evidence": int(ee_count),
                    },
                    created_at=imported_at,
                )
                self._append_runtime_trace(
                    connection,
                    operation="sync",
                    subject_id="runtime-manager",
                    status="synced",
                    input_payload={"source_path": _relative_or_absolute(source_path, self.root)},
                    output_payload={
                        "source_sha256": source_sha256,
                        "observations": len(observations),
                        "schema_version": SCHEMA_VERSION,
                    },
                    events=(("runtime_synced", {"source_sha256": source_sha256, "observations": len(observations)}),),
                    causation_id="",
                    correlation_id="",
                    started_at=imported_at,
                    finished_at=imported_at,
                )
                connection.commit()
            except Exception:
                connection.rollback()
                raise
        return self.read_status(observation_center_path=source_path)

    def promote_observation_center(self, observation_center_path: str | Path | None = None) -> RuntimeManagerStatus:
        """Promote the imported observation center so runtime.db becomes primary authority."""
        if not self.db_path.exists():
            raise RuntimeManagerStoreError(
                f"runtime manager database not found: {self.db_path}",
                code="center_database_missing",
            )

        source_path = self._resolve_observation_center_path(observation_center_path)
        with closing(self._connect()) as connection:
            self._create_schema(connection)
            metadata = self._read_metadata(connection)
            if metadata.get("center_authority_mode") == CENTER_AUTHORITY_SQLITE_PRIMARY:
                raise RuntimeManagerStoreError(
                    "observation center is already promoted to SQLite authority",
                    code="center_already_promoted",
                )

        self.sync_observation_center(source_path)
        promoted_at = _utc_now()
        promoted_from_sha256 = self._sha256(source_path)
        promoted_from_path = _relative_or_absolute(source_path, self.root)
        db_source_path = _relative_or_absolute(self.db_path, self.root)

        with closing(self._connect()) as connection:
            self._create_schema(connection)
            metadata = self._read_metadata(connection)
            previous_revision = int(metadata.get("center_revision", "0") or "0")
            center_revision = previous_revision + 1
            center_digest = self._center_snapshot_digest(connection)
            connection.execute("BEGIN")
            try:
                self._upsert_metadata(connection, "schema_version", str(SCHEMA_VERSION))
                self._upsert_metadata(connection, "store_role", "runtime-manager-store")
                self._upsert_metadata(connection, "center_authority_mode", CENTER_AUTHORITY_SQLITE_PRIMARY)
                self._upsert_metadata(connection, "center_revision", str(center_revision))
                self._upsert_metadata(connection, "center_promoted_at", promoted_at)
                self._upsert_metadata(connection, "center_promoted_from_path", promoted_from_path)
                self._upsert_metadata(connection, "center_promoted_from_sha256", promoted_from_sha256)
                self._upsert_metadata(connection, "center_snapshot_sha256", center_digest)
                self._upsert_metadata(connection, "source_authority", "runtime.db")
                self._upsert_metadata(connection, "source_path", db_source_path)
                self._upsert_metadata(connection, "source_sha256", center_digest)
                self._append_center_authority_event(
                    connection,
                    event_type="center_promoted",
                    authority_mode=CENTER_AUTHORITY_SQLITE_PRIMARY,
                    revision=center_revision,
                    source_path=promoted_from_path,
                    source_sha256=promoted_from_sha256,
                    payload={"center_snapshot_sha256": center_digest},
                    created_at=promoted_at,
                )
                self._append_event(
                    connection,
                    event_type="center_promoted",
                    subject_id="runtime-manager",
                    payload={
                        "center_revision": center_revision,
                        "center_snapshot_sha256": center_digest,
                        "promoted_from_path": promoted_from_path,
                    },
                    created_at=promoted_at,
                )
                self._append_runtime_trace(
                    connection,
                    operation="center_promote",
                    subject_id="runtime-manager",
                    status="promoted",
                    input_payload={"source_path": promoted_from_path},
                    output_payload={
                        "center_revision": center_revision,
                        "center_snapshot_sha256": center_digest,
                        "source_authority": "runtime.db",
                    },
                    events=(("center_promoted", {"center_revision": center_revision}),),
                    causation_id="",
                    correlation_id="",
                    started_at=promoted_at,
                    finished_at=promoted_at,
                )
                connection.commit()
            except Exception:
                connection.rollback()
                raise
        return self.read_status()

    def export_observation_center_toml(self) -> str:
        """Render a deterministic TOML compatibility snapshot from runtime.db."""
        if not self.db_path.exists():
            raise RuntimeManagerStoreError(
                f"runtime manager database not found: {self.db_path}",
                code="center_database_missing",
            )
        with closing(self._connect()) as connection:
            self._require_schema(connection)
            metadata = self._read_metadata(connection)
            observations = self._read_observations(connection)
        return _render_observation_center_toml(metadata, observations)

    def read_status(self, observation_center_path: str | Path | None = None) -> RuntimeManagerStatus:
        """Return read-only queue status from `runtime.db`."""
        if not self.db_path.exists():
            raise RuntimeManagerStoreError(f"runtime manager database not found: {self.db_path}")
        with closing(self._connect()) as connection:
            self._require_schema(connection)
            metadata = self._read_metadata(connection)
            center_authority_mode = metadata.get("center_authority_mode", CENTER_AUTHORITY_TOML_IMPORT)
            source_path = metadata.get("source_path", "")
            source_sha256 = metadata.get("source_sha256", "")
            source_authority = metadata.get("source_authority", "")
            stale_source = (
                False
                if center_authority_mode == CENTER_AUTHORITY_SQLITE_PRIMARY
                else self._is_stale_source(source_sha256, observation_center_path)
            )
            observations = self._read_observations(connection)
            ledger = self._read_ledger_counts(connection)
            active_leases, expired_leases = self._read_lease_state(connection)

        selected, reason, gate_diagnostics, selection_audit = self._select_next(
            observations,
            stale_source=stale_source,
            current_decisions=ledger["current_decision_ids"],
            accepted_evidence=ledger["accepted_evidence_ids"],
            enabled_tools=ledger["enabled_tool_ids"],
            current_approvals=ledger["current_approval_ids"],
            green_validations=ledger["green_validation_ids"],
            validation_gate_states=ledger["validation_gate_states"],
            active_stop_subjects=ledger["active_stop_subjects"],
            active_leases=active_leases,
            expired_leases=expired_leases,
            failed_replay_ids=ledger["failed_replay_ids"],
        )
        state_decision = decide_runtime_state(
            stale_source=stale_source,
            selected_id=selected.id if selected is not None else "",
            has_observations=bool(observations),
        )

        status = RuntimeManagerStatus(
            state=state_decision.state,
            selected_id=selected.id if selected is not None else "",
            reason=reason,
            gate_diagnostics=gate_diagnostics,
            selection_audit=selection_audit,
            center_authority_mode=center_authority_mode,
            source_authority=source_authority,
            source_path=source_path,
            source_sha256=source_sha256,
            stale_source=stale_source,
            observations_total=len(observations),
            observations_open=sum(1 for item in observations if item.status == "open"),
            observations_blocked=sum(1 for item in observations if item.status == "blocked"),
            observations_waiting=sum(1 for item in observations if item.status == "waiting"),
            decisions_total=ledger["decisions_total"],
            decisions_current=ledger["decisions_current"],
            evidence_total=ledger["evidence_total"],
            evidence_accepted=ledger["evidence_accepted"],
            evidence_rejected=ledger["evidence_rejected"],
            tools_total=ledger["tools_total"],
            tools_enabled=ledger["tools_enabled"],
            approvals_total=ledger["approvals_total"],
            approvals_current=ledger["approvals_current"],
            events_total=ledger["events_total"],
            active_leases=len(active_leases),
            leases_expired=len(expired_leases),
            replay_runs_total=ledger["replay_runs_total"],
            replay_runs_passed=ledger["replay_runs_passed"],
            replay_runs_failed=ledger["replay_runs_failed"],
            validations_total=ledger["validations_total"],
            validations_green=ledger["validations_green"],
            validations_red=ledger["validations_red"],
            validations_stale=ledger["validations_stale"],
            validations_expired=ledger["validations_expired"],
            stop_conditions_total=ledger["stop_conditions_total"],
            stop_conditions_active=ledger["stop_conditions_active"],
            commands_total=ledger["commands_total"],
            commands_enabled=ledger["commands_enabled"],
            execution_evidence_total=ledger["execution_evidence_total"],
        )
        self._record_operation_trace(
            operation="status",
            subject_id=status.selected_id or "runtime-manager",
            status=status.state,
            input_payload={"observation_center_path": str(observation_center_path or "")},
            output_payload={
                "state": status.state,
                "selected_id": status.selected_id,
                "gate_diagnostics": [_diagnostic_payload(item) for item in status.gate_diagnostics],
                "selection_decision": status.selection_audit.decision,
            },
            events=(("status_read", {"state": status.state, "selected_id": status.selected_id}),),
        )
        return status

    def read_next(self, observation_center_path: str | Path | None = None) -> RuntimeObservation | None:
        """Return the selected eligible item without mutating runtime state."""
        status = self.read_status(observation_center_path=observation_center_path)
        if status.state != "ready" or not status.selected_id:
            self._record_operation_trace(
                operation="next",
                subject_id="runtime-manager",
                status="no_eligible",
                input_payload={"observation_center_path": str(observation_center_path or "")},
                output_payload={"selected_id": "", "state": status.state},
                events=(("next_read", {"selected_id": "", "state": status.state}),),
            )
            return None
        with closing(self._connect()) as connection:
            observations = self._read_observations(connection)
        selected = next((item for item in observations if item.id == status.selected_id), None)
        self._record_operation_trace(
            operation="next",
            subject_id=status.selected_id,
            status="selected" if selected is not None else "missing",
            input_payload={"observation_center_path": str(observation_center_path or "")},
            output_payload={"selected_id": status.selected_id, "found": selected is not None},
            events=(("next_read", {"selected_id": status.selected_id, "found": selected is not None}),),
        )
        return selected

    def check_command_eligibility(
        self,
        command_id: str,
        observation_center_path: str | Path | None = None,
    ) -> CommandEligibilityResult:
        """Read-only enforcement check: is command_id eligible to run right now?

        This is a gate check only. It does not execute, schedule, approve,
        or mutate any state. Eligible means all Phase 1 gates pass AND the
        command is registered with a matching policy.
        """
        def finish(result: CommandEligibilityResult) -> CommandEligibilityResult:
            self._record_operation_trace(
                operation="check",
                subject_id=result.selected_observation_id or command_id or "runtime-manager",
                status="eligible" if result.eligible else "blocked",
                input_payload={"command_id": command_id},
                output_payload={
                    "eligible": result.eligible,
                    "command_id": result.command_id,
                    "selected_observation_id": result.selected_observation_id,
                    "blockers": list(result.blockers),
                },
                events=(("command_checked", {"eligible": result.eligible, "blockers": list(result.blockers)}),),
            )
            return result

        if not self.db_path.exists():
            raise RuntimeManagerStoreError(f"runtime manager database not found: {self.db_path}")
        with closing(self._connect()) as connection:
            self._require_schema(connection)
            row = connection.execute(
                "SELECT * FROM command_registry WHERE command_id = ?", (command_id,)
            ).fetchone()
        if row is None:
            return finish(CommandEligibilityResult(
                eligible=False,
                command_id=command_id,
                reason=f"command not registered: {command_id}",
                blockers=("command_not_registered",),
                policy=None,
                selected_observation_id="",
                gate_diagnostics=(),
            ))
        policy = CommandPolicy(
            command_id=row["command_id"],
            argv_prefix=tuple(json.loads(row["argv_prefix_json"])),
            path_scope=row["path_scope"],
            side_effect_class=row["side_effect_class"],
            network_allowed=bool(row["network_allowed"]),
            timeout_seconds=row["timeout_seconds"],
            output_budget_bytes=row["output_budget_bytes"],
            sensitive_output_policy=row["sensitive_output_policy"],
            approval_requirement=row["approval_requirement"],
            rollback_class=row["rollback_class"],
            status=row["status"],
            risk_level_override=row["risk_level_override"] if "risk_level_override" in row.keys() else "",
            requires_human_decision=bool(row["requires_human_decision"]) if "requires_human_decision" in row.keys() else False,
            data_sensitivity=row["data_sensitivity"] if "data_sensitivity" in row.keys() else "none",
            target_scope=row["target_scope"] if "target_scope" in row.keys() else "local",
        )
        # Phase 8: classify the action and attach autonomy metadata
        _action_inp = ActionInput(
            side_effect_class=policy.side_effect_class,
            network_allowed=policy.network_allowed,
            approval_requirement=policy.approval_requirement,
            path_scope=policy.path_scope,
            sensitive_output_policy=policy.sensitive_output_policy,
            rollback_class=policy.rollback_class,
            target_scope=policy.target_scope,
            data_sensitivity=policy.data_sensitivity,
            risk_level_override=policy.risk_level_override,
            requires_human_decision=policy.requires_human_decision,
        )
        _classification = classify_action(_action_inp)

        if policy.status != "enabled":
            return finish(CommandEligibilityResult(
                eligible=False,
                command_id=command_id,
                reason=f"command not enabled: {command_id} (status={policy.status})",
                blockers=("command_not_enabled",),
                policy=policy,
                selected_observation_id="",
                gate_diagnostics=(),
                autonomy_level=_classification.autonomy_level,
                required_controls=_classification.required_controls,
                friction_budget=_classification.friction_budget,
                autonomy_rationale=_classification.rationale,
            ))
        # L4 commands are not autonomously executable
        if _classification.autonomy_level == "L4_external_high_risk":
            return finish(CommandEligibilityResult(
                eligible=False,
                command_id=command_id,
                reason=_classification.blocked_reason,
                blockers=("l4_external_high_risk_blocked",),
                policy=policy,
                selected_observation_id="",
                gate_diagnostics=(),
                autonomy_level=_classification.autonomy_level,
                required_controls=_classification.required_controls,
                friction_budget=_classification.friction_budget,
                autonomy_rationale=_classification.rationale,
            ))
        status = self.read_status(observation_center_path=observation_center_path)
        if status.state == "blocked":
            return finish(CommandEligibilityResult(
                eligible=False,
                command_id=command_id,
                reason="runtime gate is blocked; no item is eligible",
                blockers=("gate_blocked",),
                policy=policy,
                selected_observation_id="",
                gate_diagnostics=status.gate_diagnostics,
                autonomy_level=_classification.autonomy_level,
                required_controls=_classification.required_controls,
                friction_budget=_classification.friction_budget,
                autonomy_rationale=_classification.rationale,
            ))
        if not status.selected_id:
            return finish(CommandEligibilityResult(
                eligible=False,
                command_id=command_id,
                reason="no eligible observation selected",
                blockers=("no_eligible_observation",),
                policy=policy,
                selected_observation_id="",
                gate_diagnostics=status.gate_diagnostics,
                autonomy_level=_classification.autonomy_level,
                required_controls=_classification.required_controls,
                friction_budget=_classification.friction_budget,
                autonomy_rationale=_classification.rationale,
            ))
        if policy.approval_requirement != "none":
            action_fingerprint = _command_action_fingerprint(policy)
            with closing(self._connect()) as connection:
                approval = connection.execute(
                    """SELECT approval_id FROM approval_records
                       WHERE subject_id = ? AND action_fingerprint = ? AND status = 'current'
                       UNION ALL
                       SELECT approval_id FROM managed_approvals
                       WHERE subject_id = ? AND action_fingerprint = ? AND status = 'current'
                       LIMIT 1""",
                    (status.selected_id, action_fingerprint, status.selected_id, action_fingerprint),
                ).fetchone()
            if approval is None:
                return finish(CommandEligibilityResult(
                    eligible=False,
                    command_id=command_id,
                    reason=(
                        f"approval required but no current approval found for command {command_id} "
                        f"with fingerprint {action_fingerprint} on observation {status.selected_id}"
                    ),
                    blockers=("approval_required",),
                    policy=policy,
                    selected_observation_id=status.selected_id,
                    gate_diagnostics=status.gate_diagnostics,
                    autonomy_level=_classification.autonomy_level,
                    required_controls=_classification.required_controls,
                    friction_budget=_classification.friction_budget,
                    autonomy_rationale=_classification.rationale,
                ))
        return finish(CommandEligibilityResult(
            eligible=True,
            command_id=command_id,
            reason=f"command eligible for observation {status.selected_id}",
            blockers=(),
            policy=policy,
            selected_observation_id=status.selected_id,
            gate_diagnostics=status.gate_diagnostics,
            autonomy_level=_classification.autonomy_level,
            required_controls=_classification.required_controls,
            friction_budget=_classification.friction_budget,
            autonomy_rationale=_classification.rationale,
        ))

    def run_command(
        self,
        command_id: str,
        observation_center_path: str | Path | None = None,
        auto_stop_on_failure: bool = False,
    ) -> CommandRunResult:
        """Execute a registered command through the full enforcement chain.

        No subprocess runs unless check_command_eligibility() returns eligible.
        The argv executed is exactly policy.argv_prefix — no extra arguments are
        accepted so that the approval fingerprint covers the full execution unit.
        Path scope, timeout, and output budget are enforced; output is sanitized
        per the command's sensitive_output_policy before the event is recorded.

        When auto_stop_on_failure=True and the subprocess times out or returns a
        non-zero exit code, a managed stop condition is automatically raised on
        the selected observation so subsequent reads block selection until resolved.
        """
        eligibility = self.check_command_eligibility(
            command_id, observation_center_path=observation_center_path
        )
        if not eligibility.eligible:
            result = CommandRunResult(
                eligible=False,
                command_id=command_id,
                observation_id=eligibility.selected_observation_id,
                argv=(),
                stdout="",
                stderr="",
                returncode=-1,
                timed_out=False,
                duration_seconds=0.0,
                stdout_truncated=False,
                stderr_truncated=False,
                blockers=eligibility.blockers,
                event_id=-1,
                evidence_id=-1,
            )
            self._record_operation_trace(
                operation="run",
                subject_id=result.observation_id or command_id,
                status="blocked",
                input_payload={"command_id": command_id},
                output_payload={"eligible": False, "blockers": list(result.blockers)},
                events=(("command_run_blocked", {"blockers": list(result.blockers)}),),
            )
            return result

        policy = eligibility.policy
        assert policy is not None

        # Resolve and enforce path scope using Path.relative_to to avoid
        # string-prefix false positives on sibling directories.
        scope_path = (self.root / policy.path_scope).resolve()
        try:
            scope_path.relative_to(self.root.resolve())
        except ValueError:
            result = CommandRunResult(
                eligible=False,
                command_id=command_id,
                observation_id=eligibility.selected_observation_id,
                argv=(),
                stdout="",
                stderr="",
                returncode=-1,
                timed_out=False,
                duration_seconds=0.0,
                stdout_truncated=False,
                stderr_truncated=False,
                blockers=("path_scope_violation",),
                event_id=-1,
                evidence_id=-1,
            )
            self._record_operation_trace(
                operation="run",
                subject_id=result.observation_id or command_id,
                status="blocked",
                input_payload={"command_id": command_id},
                output_payload={"eligible": False, "blockers": list(result.blockers)},
                events=(("command_run_blocked", {"blockers": list(result.blockers)}),),
            )
            return result

        argv = tuple(policy.argv_prefix)
        timeout = policy.timeout_seconds if policy.timeout_seconds > 0 else None
        budget = policy.output_budget_bytes if policy.output_budget_bytes > 0 else None

        stdout_raw = ""
        stderr_raw = ""
        returncode = -3
        timed_out = False
        duration = 0.0

        try:
            t0 = time.monotonic()
            proc = subprocess.Popen(
                argv,
                cwd=str(scope_path),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            try:
                stdout_raw, stderr_raw = proc.communicate(timeout=timeout)
                returncode = proc.returncode
            except subprocess.TimeoutExpired:
                proc.kill()
                stdout_raw, stderr_raw = proc.communicate()
                returncode = -2
                timed_out = True
            duration = time.monotonic() - t0
        except OSError:
            returncode = -3
            duration = 0.0

        # Capture digests of raw output BEFORE truncation or redaction.
        stdout_digest = hashlib.sha256(stdout_raw.encode()).hexdigest()
        stderr_digest = hashlib.sha256(stderr_raw.encode()).hexdigest()

        stdout_truncated = False
        stderr_truncated = False
        if budget is not None:
            if len(stdout_raw.encode()) > budget:
                stdout_raw = stdout_raw.encode()[:budget].decode(errors="replace") + "\n[TRUNCATED]"
                stdout_truncated = True
            if len(stderr_raw.encode()) > budget:
                stderr_raw = stderr_raw.encode()[:budget].decode(errors="replace") + "\n[TRUNCATED]"
                stderr_truncated = True

        output_redacted = policy.sensitive_output_policy == "redact"
        if output_redacted:
            stdout_raw = "[REDACTED]"
            stderr_raw = "[REDACTED]"

        # Resolve the approval_id that satisfied the fingerprint check, if any.
        approval_id = ""
        if policy.approval_requirement != "none":
            action_fp = _command_action_fingerprint(policy)
            with closing(self._connect()) as conn:
                row = conn.execute(
                    """SELECT approval_id FROM approval_records
                       WHERE subject_id = ? AND action_fingerprint = ? AND status = 'current'
                       UNION ALL
                       SELECT approval_id FROM managed_approvals
                       WHERE subject_id = ? AND action_fingerprint = ? AND status = 'current'
                       LIMIT 1""",
                    (eligibility.selected_observation_id, action_fp,
                     eligibility.selected_observation_id, action_fp),
                ).fetchone()
            if row:
                approval_id = row["approval_id"]

        now = datetime.now(tz=timezone.utc).isoformat()
        event_id = -1
        evidence_id = -1
        with closing(self._connect()) as connection:
            self._append_event(
                connection,
                event_type="command_run",
                subject_id=eligibility.selected_observation_id,
                payload={
                    "command_id": command_id,
                    "observation_id": eligibility.selected_observation_id,
                    "argv": list(argv),
                    "returncode": returncode,
                    "timed_out": timed_out,
                    "duration_seconds": round(duration, 3),
                    "stdout_truncated": stdout_truncated,
                    "stderr_truncated": stderr_truncated,
                    "rollback_class": policy.rollback_class,
                },
                created_at=now,
            )
            event_id = connection.execute("SELECT last_insert_rowid()").fetchone()[0]
            connection.execute(
                """INSERT INTO execution_evidence (
                    command_id, observation_id, approval_id, action_fingerprint,
                    rollback_class, returncode, timed_out, duration_seconds,
                    stdout_digest, stderr_digest, stdout_truncated, stderr_truncated,
                    output_redacted, event_id, recorded_at, autonomy_level
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    command_id,
                    eligibility.selected_observation_id,
                    approval_id,
                    _command_action_fingerprint(policy),
                    policy.rollback_class,
                    returncode,
                    int(timed_out),
                    round(duration, 3),
                    stdout_digest,
                    stderr_digest,
                    int(stdout_truncated),
                    int(stderr_truncated),
                    int(output_redacted),
                    event_id,
                    now,
                    eligibility.autonomy_level,
                ),
            )
            evidence_id = connection.execute("SELECT last_insert_rowid()").fetchone()[0]
            connection.commit()

        result = CommandRunResult(
            eligible=True,
            command_id=command_id,
            observation_id=eligibility.selected_observation_id,
            argv=argv,
            stdout=stdout_raw,
            stderr=stderr_raw,
            returncode=returncode,
            timed_out=timed_out,
            duration_seconds=round(duration, 3),
            stdout_truncated=stdout_truncated,
            stderr_truncated=stderr_truncated,
            blockers=(),
            event_id=event_id,
            evidence_id=evidence_id,
        )
        if auto_stop_on_failure and (timed_out or returncode != 0):
            reason = (
                f"auto_stop_on_failure: command={command_id} "
                f"returncode={returncode} timed_out={timed_out}"
            )
            self.raise_stop_condition(
                subject_id=eligibility.selected_observation_id,
                reason=reason,
            )
        self._record_operation_trace(
            operation="run",
            subject_id=result.observation_id,
            status="passed" if result.returncode == 0 and not result.timed_out else "failed",
            input_payload={"command_id": command_id, "observation_id": result.observation_id},
            output_payload={
                "eligible": result.eligible,
                "returncode": result.returncode,
                "timed_out": result.timed_out,
                "evidence_id": result.evidence_id,
                "stdout_digest": stdout_digest,
                "stderr_digest": stderr_digest,
                "stdout_truncated": result.stdout_truncated,
                "stderr_truncated": result.stderr_truncated,
            },
            events=(
                (
                    "command_executed",
                    {
                        "command_id": command_id,
                        "returncode": result.returncode,
                        "timed_out": result.timed_out,
                        "evidence_id": result.evidence_id,
                    },
                ),
            ),
        )
        return result

    def read_evidence(self, evidence_id: int) -> ExecutionEvidence | None:
        """Return a single ExecutionEvidence row by primary key, or None if not found."""
        if not self.db_path.exists():
            raise RuntimeManagerStoreError(f"runtime manager database not found: {self.db_path}")
        with closing(self._connect()) as connection:
            self._require_schema(connection)
            row = connection.execute(
                "SELECT * FROM execution_evidence WHERE evidence_id = ?", (evidence_id,)
            ).fetchone()
        if row is None:
            return None
        return _row_to_evidence(row)

    def list_evidence(
        self,
        observation_id: str | None = None,
        limit: int = 50,
    ) -> tuple[ExecutionEvidence, ...]:
        """Return the most recent ExecutionEvidence rows, newest first.

        Pass observation_id to filter to a single work item. limit caps the
        number of rows returned (default 50; pass 0 for all rows).
        """
        if limit < 0:
            raise RuntimeManagerStoreError(f"evidence list limit must be >= 0: {limit}")
        if not self.db_path.exists():
            raise RuntimeManagerStoreError(f"runtime manager database not found: {self.db_path}")
        with closing(self._connect()) as connection:
            self._require_schema(connection)
            if observation_id is not None:
                if limit > 0:
                    rows = connection.execute(
                        "SELECT * FROM execution_evidence WHERE observation_id = ? ORDER BY evidence_id DESC LIMIT ?",
                        (observation_id, limit),
                    ).fetchall()
                else:
                    rows = connection.execute(
                        "SELECT * FROM execution_evidence WHERE observation_id = ? ORDER BY evidence_id DESC",
                        (observation_id,),
                    ).fetchall()
            else:
                if limit > 0:
                    rows = connection.execute(
                        "SELECT * FROM execution_evidence ORDER BY evidence_id DESC LIMIT ?",
                        (limit,),
                    ).fetchall()
                else:
                    rows = connection.execute(
                        "SELECT * FROM execution_evidence ORDER BY evidence_id DESC"
                    ).fetchall()
        return tuple(_row_to_evidence(row) for row in rows)

    def list_leases(
        self,
        observation_id: str | None = None,
        limit: int = 50,
    ) -> tuple["AcquiredLease", ...]:
        """Return managed_leases rows, newest first. limit=0 returns all."""
        if limit < 0:
            raise RuntimeManagerStoreError(f"lease list limit must be >= 0: {limit}")
        if not self.db_path.exists():
            raise RuntimeManagerStoreError(f"runtime manager database not found: {self.db_path}")
        with closing(self._connect()) as connection:
            self._require_schema(connection)
            if observation_id is not None:
                if limit > 0:
                    rows = connection.execute(
                        "SELECT * FROM managed_leases WHERE observation_id = ? ORDER BY acquired_at DESC LIMIT ?",
                        (observation_id, limit),
                    ).fetchall()
                else:
                    rows = connection.execute(
                        "SELECT * FROM managed_leases WHERE observation_id = ? ORDER BY acquired_at DESC",
                        (observation_id,),
                    ).fetchall()
            else:
                if limit > 0:
                    rows = connection.execute(
                        "SELECT * FROM managed_leases ORDER BY acquired_at DESC LIMIT ?", (limit,)
                    ).fetchall()
                else:
                    rows = connection.execute(
                        "SELECT * FROM managed_leases ORDER BY acquired_at DESC"
                    ).fetchall()
        return tuple(_row_to_managed_lease(row) for row in rows)

    def list_stop_conditions(
        self,
        subject_id: str | None = None,
        limit: int = 50,
    ) -> tuple["ManagedStopCondition", ...]:
        """Return managed_stop_conditions rows, newest first. limit=0 returns all."""
        if limit < 0:
            raise RuntimeManagerStoreError(f"stop condition list limit must be >= 0: {limit}")
        if not self.db_path.exists():
            raise RuntimeManagerStoreError(f"runtime manager database not found: {self.db_path}")
        with closing(self._connect()) as connection:
            self._require_schema(connection)
            if subject_id is not None:
                if limit > 0:
                    rows = connection.execute(
                        "SELECT * FROM managed_stop_conditions WHERE subject_id = ? ORDER BY opened_at DESC LIMIT ?",
                        (subject_id, limit),
                    ).fetchall()
                else:
                    rows = connection.execute(
                        "SELECT * FROM managed_stop_conditions WHERE subject_id = ? ORDER BY opened_at DESC",
                        (subject_id,),
                    ).fetchall()
            else:
                if limit > 0:
                    rows = connection.execute(
                        "SELECT * FROM managed_stop_conditions ORDER BY opened_at DESC LIMIT ?", (limit,)
                    ).fetchall()
                else:
                    rows = connection.execute(
                        "SELECT * FROM managed_stop_conditions ORDER BY opened_at DESC"
                    ).fetchall()
        return tuple(_row_to_managed_stop_condition(row) for row in rows)

    def read_validation(self, validation_id: str) -> "ManagedValidation | None":
        """Return the managed_validations row for the given id, or None if not found."""
        if not self.db_path.exists():
            raise RuntimeManagerStoreError(f"runtime manager database not found: {self.db_path}")
        with closing(self._connect()) as connection:
            self._require_schema(connection)
            row = connection.execute(
                "SELECT * FROM managed_validations WHERE validation_id = ?", (validation_id,)
            ).fetchone()
        if row is None:
            return None
        return _row_to_managed_validation(row)

    def list_approvals(
        self,
        subject_id: str | None = None,
        command_id: str | None = None,
        limit: int = 50,
    ) -> tuple["ApprovalRecord", ...]:
        """Return managed_approvals rows, newest first.

        Optionally filter by subject_id and/or command_id. limit=0 returns all.
        """
        if limit < 0:
            raise RuntimeManagerStoreError(f"approval list limit must be >= 0: {limit}")
        if not self.db_path.exists():
            raise RuntimeManagerStoreError(f"runtime manager database not found: {self.db_path}")
        with closing(self._connect()) as connection:
            self._require_schema(connection)
            filters: list[str] = []
            params: list[object] = []
            if subject_id is not None:
                filters.append("subject_id = ?")
                params.append(subject_id)
            if command_id is not None:
                filters.append("command_id = ?")
                params.append(command_id)
            where = ("WHERE " + " AND ".join(filters)) if filters else ""
            if limit > 0:
                params.append(limit)
                rows = connection.execute(
                    f"SELECT * FROM managed_approvals {where} ORDER BY granted_at DESC LIMIT ?", params
                ).fetchall()
            else:
                rows = connection.execute(
                    f"SELECT * FROM managed_approvals {where} ORDER BY granted_at DESC", params
                ).fetchall()
        return tuple(_row_to_managed_approval(row) for row in rows)

    def read_trace(self, trace_id: str) -> RuntimeTrace | None:
        """Return one Runtime Manager trace with sanitized events, or None."""
        if not self.db_path.exists():
            raise RuntimeManagerStoreError(f"runtime manager database not found: {self.db_path}")
        with closing(self._connect()) as connection:
            self._require_schema(connection)
            row = connection.execute(
                "SELECT * FROM runtime_traces WHERE trace_id = ?", (trace_id,)
            ).fetchone()
            if row is None:
                return None
            event_rows = connection.execute(
                "SELECT * FROM runtime_trace_events WHERE trace_id = ? ORDER BY sequence ASC",
                (trace_id,),
            ).fetchall()
        return _row_to_runtime_trace(row, event_rows)

    def list_traces(
        self,
        operation: str | None = None,
        subject_id: str | None = None,
        limit: int = 50,
    ) -> tuple[RuntimeTrace, ...]:
        """Return Runtime Manager traces newest first. limit=0 returns all."""
        if limit < 0:
            raise RuntimeManagerStoreError(f"trace list limit must be >= 0: {limit}")
        if not self.db_path.exists():
            raise RuntimeManagerStoreError(f"runtime manager database not found: {self.db_path}")
        filters: list[str] = []
        params: list[object] = []
        if operation is not None:
            filters.append("operation = ?")
            params.append(operation)
        if subject_id is not None:
            filters.append("subject_id = ?")
            params.append(subject_id)
        where = ("WHERE " + " AND ".join(filters)) if filters else ""
        with closing(self._connect()) as connection:
            self._require_schema(connection)
            if limit > 0:
                params.append(limit)
                rows = connection.execute(
                    f"SELECT * FROM runtime_traces {where} ORDER BY started_at DESC, trace_id DESC LIMIT ?",
                    params,
                ).fetchall()
            else:
                rows = connection.execute(
                    f"SELECT * FROM runtime_traces {where} ORDER BY started_at DESC, trace_id DESC",
                    params,
                ).fetchall()
            traces = []
            for row in rows:
                event_rows = connection.execute(
                    "SELECT * FROM runtime_trace_events WHERE trace_id = ? ORDER BY sequence ASC",
                    (row["trace_id"],),
                ).fetchall()
                traces.append(_row_to_runtime_trace(row, event_rows))
        return tuple(traces)

    def export_trace(self, trace_id: str, format: str = "json") -> str:
        """Export one trace as json, jsonl, or local otel-json compatibility data."""
        trace = self.read_trace(trace_id)
        if trace is None:
            raise RuntimeManagerStoreError(f"runtime trace not found: {trace_id}")
        payload = _trace_payload(trace)
        if format == "json":
            return json.dumps(payload, indent=2, sort_keys=True) + "\n"
        if format == "jsonl":
            lines = [json.dumps({"trace": payload}, sort_keys=True)]
            for event in trace.events:
                lines.append(json.dumps({"trace_event": _trace_event_payload(event)}, sort_keys=True))
            return "\n".join(lines) + "\n"
        if format == "otel-json":
            return json.dumps(_trace_to_otel_projection(trace), indent=2, sort_keys=True) + "\n"
        raise RuntimeManagerStoreError(f"unsupported trace export format: {format}")

    def read_metrics(self) -> RuntimeManagerMetrics:
        """Return local runtime-manager health counters."""
        if not self.db_path.exists():
            raise RuntimeManagerStoreError(f"runtime manager database not found: {self.db_path}")
        with closing(self._connect()) as connection:
            self._require_schema(connection)
            evidence_rows = connection.execute(
                "SELECT command_id, returncode, timed_out, autonomy_level FROM execution_evidence"
            ).fetchall()
            approval_rows = connection.execute("SELECT status FROM managed_approvals").fetchall()
            validation_rows = connection.execute(
                "SELECT status, fresh_until FROM managed_validations"
            ).fetchall()
            stop_rows = connection.execute("SELECT status FROM managed_stop_conditions").fetchall()
            lease_rows = connection.execute("SELECT status, expires_at FROM managed_leases").fetchall()
            trace_rows = connection.execute("SELECT finished_at FROM runtime_traces").fetchall()
            mcp_blocked_row = connection.execute(
                "SELECT count FROM policy_counters WHERE counter_key = 'mcp_level_blocked'"
            ).fetchone()
        checked_at = _utc_now()
        rollback_rows = [row for row in evidence_rows if str(row["command_id"]).startswith("rollback:")]
        _level_map = {
            "L0_observe": "l0", "L1_derived": "l1", "L2_local_code": "l2",
            "L3_runtime_mutation": "l3", "L4_external_high_risk": "l4",
        }
        _level_counts = {k: 0 for k in ("l0", "l1", "l2", "l3", "l4")}
        for row in evidence_rows:
            lvl = _level_map.get(row["autonomy_level"] or "", None)
            if lvl:
                _level_counts[lvl] += 1
        metrics = RuntimeManagerMetrics(
            generated_at=checked_at,
            runs_total=len(evidence_rows),
            runs_passed=sum(1 for row in evidence_rows if int(row["returncode"]) == 0),
            runs_failed=sum(1 for row in evidence_rows if int(row["returncode"]) != 0),
            runs_timed_out=sum(1 for row in evidence_rows if bool(row["timed_out"])),
            execution_evidence_total=len(evidence_rows),
            approvals_current=sum(1 for row in approval_rows if row["status"] == "current"),
            approvals_revoked=sum(1 for row in approval_rows if row["status"] == "revoked"),
            validations_green=sum(1 for row in validation_rows if row["status"] == "green" and _fresh_until_is_current(row["fresh_until"], checked_at)),
            validations_red=sum(1 for row in validation_rows if row["status"] == "red"),
            validations_stale=sum(1 for row in validation_rows if row["status"] == "stale"),
            validations_expired=sum(1 for row in validation_rows if row["status"] == "green" and not _fresh_until_is_current(row["fresh_until"], checked_at)),
            stop_conditions_active=sum(1 for row in stop_rows if row["status"] == "active"),
            stop_conditions_resolved=sum(1 for row in stop_rows if row["status"] == "resolved"),
            leases_active=sum(1 for row in lease_rows if row["status"] == "active" and _lease_expires_at_is_current(row["expires_at"], checked_at)),
            leases_expired=sum(1 for row in lease_rows if row["status"] == "active" and not _lease_expires_at_is_current(row["expires_at"], checked_at)),
            leases_reclaimed=sum(1 for row in lease_rows if row["status"] == "reclaimed"),
            rollback_runs_total=len(rollback_rows),
            rollback_runs_passed=sum(1 for row in rollback_rows if int(row["returncode"]) == 0),
            rollback_runs_failed=sum(1 for row in rollback_rows if int(row["returncode"]) != 0),
            traces_total=len(trace_rows),
            traces_incomplete=sum(1 for row in trace_rows if not row["finished_at"]),
            evals_total=0,
            evals_passed=0,
            evals_failed=0,
            actions_l0=_level_counts["l0"],
            actions_l1=_level_counts["l1"],
            actions_l2=_level_counts["l2"],
            actions_l3=_level_counts["l3"],
            actions_l4=_level_counts["l4"],
            mcp_level_blocked=mcp_blocked_row["count"] if mcp_blocked_row else 0,
        )
        self._record_operation_trace(
            operation="metrics",
            subject_id="runtime-manager",
            status="read",
            input_payload={},
            output_payload=_metrics_payload(metrics),
            events=(("metrics_read", {"runs_total": metrics.runs_total, "traces_total": metrics.traces_total}),),
        )
        return metrics

    def replay_scenario(self, scenario_path: str | Path) -> RuntimeReplayResult:
        """Run deterministic checks declared by one local replay scenario JSON file."""
        scenario_file = Path(scenario_path)
        if not scenario_file.is_absolute():
            scenario_file = self.root / scenario_file
        try:
            payload = json.loads(scenario_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise RuntimeManagerStoreError(f"runtime replay scenario JSON is invalid: {exc}") from exc
        except OSError as exc:
            raise RuntimeManagerStoreError(f"failed to read runtime replay scenario: {scenario_file}") from exc
        scenario_id = str(payload.get("scenario_id") or scenario_file.stem)
        checks = payload.get("checks", [])
        if not isinstance(checks, list):
            raise RuntimeManagerStoreError("runtime replay scenario checks must be a list")
        results = tuple(self._evaluate_replay_check(check) for check in checks)
        digest = "sha256:" + hashlib.sha256(
            json.dumps(
                {
                    "scenario_id": scenario_id,
                    "checks": [
                        {"check_id": item.check_id, "passed": item.passed, "reason": item.reason}
                        for item in results
                    ],
                },
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
        ).hexdigest()
        replay = RuntimeReplayResult(
            scenario_id=scenario_id,
            passed=all(item.passed for item in results),
            replay_digest=digest,
            checks=results,
        )
        self._record_operation_trace(
            operation="replay",
            subject_id=scenario_id,
            status="passed" if replay.passed else "failed",
            input_payload={"scenario_id": scenario_id, "checks": checks},
            output_payload=_replay_payload(replay),
            events=(("replay_evaluated", {"passed": replay.passed, "replay_digest": digest}),),
        )
        return replay

    def _evaluate_replay_check(self, raw_check: object) -> RuntimeReplayCheckResult:
        if not isinstance(raw_check, dict):
            return RuntimeReplayCheckResult("invalid", False, "check must be an object")
        check_id = str(raw_check.get("id") or raw_check.get("type") or "check")
        check_type = str(raw_check.get("type") or "")
        try:
            if check_type == "trace_exists":
                traces = self.list_traces(
                    operation=_optional_string(raw_check.get("operation")),
                    subject_id=_optional_string(raw_check.get("subject_id")),
                    limit=1,
                )
                return RuntimeReplayCheckResult(check_id, bool(traces), "trace found" if traces else "trace not found")
            if check_type == "metric_at_least":
                metric_name = str(raw_check.get("metric") or "")
                minimum = int(raw_check.get("min", 1))
                metrics = _metrics_payload(self.read_metrics())
                value = int(metrics.get(metric_name, 0))
                return RuntimeReplayCheckResult(
                    check_id,
                    value >= minimum,
                    f"{metric_name}={value}; min={minimum}",
                )
            if check_type == "command_blocker":
                command_id = str(raw_check.get("command_id") or "")
                expected = str(raw_check.get("expected_blocker") or "")
                result = self.check_command_eligibility(command_id)
                passed = expected in result.blockers
                return RuntimeReplayCheckResult(
                    check_id,
                    passed,
                    f"blockers={','.join(result.blockers) or '<none>'}; expected={expected}",
                )
            if check_type == "trace_forbids_text":
                forbidden = str(raw_check.get("text") or "")
                haystack = "\n".join(self.export_trace(trace.trace_id, "json") for trace in self.list_traces(limit=0))
                passed = bool(forbidden) and forbidden not in haystack
                return RuntimeReplayCheckResult(
                    check_id,
                    passed,
                    "forbidden text absent" if passed else "forbidden text present or empty",
                )
        except Exception as exc:
            return RuntimeReplayCheckResult(check_id, False, f"{check_type} raised {exc}")
        return RuntimeReplayCheckResult(check_id, False, f"unsupported replay check type: {check_type}")

    def check_rollback_eligibility(self, evidence_id: int) -> "RollbackResult":
        """Check eligibility for a rollback without executing it.

        Returns RollbackResult with eligible=True if a rollback is possible,
        eligible=False with blockers explaining why not.
        rollback_evidence_id is always -1 (no execution occurs).
        """
        if not self.db_path.exists():
            raise RuntimeManagerStoreError(f"runtime manager database not found: {self.db_path}")
        with closing(self._connect()) as connection:
            self._require_schema(connection)
            ev_row = connection.execute(
                "SELECT * FROM execution_evidence WHERE evidence_id = ?", (evidence_id,)
            ).fetchone()
        if ev_row is None:
            return RollbackResult(
                eligible=False, original_evidence_id=evidence_id, rollback_evidence_id=-1,
                command_id="", argv=(), stdout="", stderr="", returncode=-1,
                timed_out=False, duration_seconds=0.0, blockers=("evidence_not_found",), event_id=-1,
            )
        original_command_id = ev_row["command_id"]
        with closing(self._connect()) as connection:
            fwd_row = connection.execute(
                "SELECT rollback_class FROM command_registry WHERE command_id = ?", (original_command_id,)
            ).fetchone()
            rollback_row = connection.execute(
                "SELECT * FROM rollback_registry WHERE forward_command_id = ? AND status = 'enabled' LIMIT 1",
                (original_command_id,),
            ).fetchone()
        if fwd_row is not None and fwd_row["rollback_class"] == "irreversible":
            return RollbackResult(
                eligible=False, original_evidence_id=evidence_id, rollback_evidence_id=-1,
                command_id=original_command_id, argv=(), stdout="", stderr="", returncode=-1,
                timed_out=False, duration_seconds=0.0, blockers=("rollback_irreversible",), event_id=-1,
            )
        if rollback_row is None:
            return RollbackResult(
                eligible=False, original_evidence_id=evidence_id, rollback_evidence_id=-1,
                command_id=original_command_id, argv=(), stdout="", stderr="", returncode=-1,
                timed_out=False, duration_seconds=0.0, blockers=("no_rollback_policy",), event_id=-1,
            )
        argv = tuple(json.loads(rollback_row["argv_prefix_json"]))
        path_scope = rollback_row["path_scope"]
        scope_path = (self.root / path_scope).resolve()
        try:
            scope_path.relative_to(self.root.resolve())
        except ValueError:
            return RollbackResult(
                eligible=False, original_evidence_id=evidence_id, rollback_evidence_id=-1,
                command_id=original_command_id, argv=argv, stdout="", stderr="", returncode=-1,
                timed_out=False, duration_seconds=0.0, blockers=("path_scope_violation",), event_id=-1,
            )
        return RollbackResult(
            eligible=True, original_evidence_id=evidence_id, rollback_evidence_id=-1,
            command_id=original_command_id, argv=argv, stdout="", stderr="", returncode=-1,
            timed_out=False, duration_seconds=0.0, blockers=(), event_id=-1,
        )

    def list_rollback_runs(
        self,
        forward_command_id: str | None = None,
        limit: int = 50,
    ) -> tuple["ExecutionEvidence", ...]:
        """Return execution_evidence rows where command_id starts with 'rollback:'.

        Rollback runs are stored in execution_evidence with command_id=rollback:<original>.
        Optionally filter to a specific forward_command_id. limit=0 returns all.
        """
        if limit < 0:
            raise RuntimeManagerStoreError(f"rollback list limit must be >= 0: {limit}")
        if not self.db_path.exists():
            raise RuntimeManagerStoreError(f"runtime manager database not found: {self.db_path}")
        with closing(self._connect()) as connection:
            self._require_schema(connection)
            if forward_command_id is not None:
                target = f"rollback:{forward_command_id}"
                if limit > 0:
                    rows = connection.execute(
                        "SELECT * FROM execution_evidence WHERE command_id = ? ORDER BY evidence_id DESC LIMIT ?",
                        (target, limit),
                    ).fetchall()
                else:
                    rows = connection.execute(
                        "SELECT * FROM execution_evidence WHERE command_id = ? ORDER BY evidence_id DESC",
                        (target,),
                    ).fetchall()
            else:
                if limit > 0:
                    rows = connection.execute(
                        "SELECT * FROM execution_evidence WHERE command_id LIKE 'rollback:%' ORDER BY evidence_id DESC LIMIT ?",
                        (limit,),
                    ).fetchall()
                else:
                    rows = connection.execute(
                        "SELECT * FROM execution_evidence WHERE command_id LIKE 'rollback:%' ORDER BY evidence_id DESC"
                    ).fetchall()
        return tuple(_row_to_evidence(row) for row in rows)

    def register_rollback(
        self,
        forward_command_id: str,
        argv_prefix: tuple[str, ...] | list[str],
        path_scope: str = ".",
        timeout_seconds: int = 60,
        output_budget_bytes: int = 65536,
    ) -> RollbackPolicy:
        """Register or replace the rollback command for forward_command_id.

        Raises RuntimeManagerStoreError if the forward command does not exist in
        command_registry, or if the forward command's rollback_class is 'irreversible'.
        Only one enabled rollback policy per forward_command_id (UNIQUE index).
        Re-registering disables the old policy and inserts a new one.
        """
        if not self.db_path.exists():
            raise RuntimeManagerStoreError(f"runtime manager database not found: {self.db_path}")
        argv_list = list(argv_prefix)
        if not argv_list:
            raise RuntimeManagerStoreError("argv_prefix must not be empty")
        rollback_id = str(uuid.uuid4())
        now = _utc_now()
        with closing(self._connect()) as connection:
            self._require_schema(connection)
            fwd_row = connection.execute(
                "SELECT rollback_class FROM command_registry WHERE command_id = ?", (forward_command_id,)
            ).fetchone()
            if fwd_row is None:
                raise RuntimeManagerStoreError(
                    f"forward command not registered: {forward_command_id!r}"
                )
            if fwd_row["rollback_class"] == "irreversible":
                raise RuntimeManagerStoreError(
                    f"forward command is irreversible, cannot register rollback: {forward_command_id!r}"
                )
            try:
                # Disable any existing enabled policy for this forward command.
                connection.execute(
                    "UPDATE rollback_registry SET status = 'disabled' WHERE forward_command_id = ? AND status = 'enabled'",
                    (forward_command_id,),
                )
                connection.execute(
                    """INSERT INTO rollback_registry
                        (rollback_id, forward_command_id, argv_prefix_json, path_scope,
                         timeout_seconds, output_budget_bytes, status, registered_at)
                       VALUES (?, ?, ?, ?, ?, ?, 'enabled', ?)""",
                    (
                        rollback_id,
                        forward_command_id,
                        json.dumps(argv_list, sort_keys=True, separators=(",", ":")),
                        path_scope,
                        timeout_seconds,
                        output_budget_bytes,
                        now,
                    ),
                )
                self._append_event(
                    connection,
                    event_type="rollback_registered",
                    subject_id=forward_command_id,
                    payload={
                        "rollback_id": rollback_id,
                        "argv_prefix": argv_list,
                        "path_scope": path_scope,
                    },
                    created_at=now,
                )
                connection.commit()
            except Exception:
                connection.rollback()
                raise
        policy = RollbackPolicy(
            rollback_id=rollback_id,
            forward_command_id=forward_command_id,
            argv_prefix=tuple(argv_list),
            path_scope=path_scope,
            timeout_seconds=timeout_seconds,
            output_budget_bytes=output_budget_bytes,
            status="enabled",
        )
        self._record_operation_trace(
            operation="rollback",
            subject_id=forward_command_id,
            status="registered",
            input_payload={"forward_command_id": forward_command_id},
            output_payload={
                "rollback_id": policy.rollback_id,
                "forward_command_id": policy.forward_command_id,
                "path_scope": policy.path_scope,
                "status": policy.status,
            },
            events=(("rollback_registered", {"rollback_id": rollback_id}),),
        )
        return policy

    def rollback_command(
        self,
        evidence_id: int,
        observation_center_path: str | Path | None = None,
    ) -> RollbackResult:
        """Execute the rollback for a previous command execution.

        Looks up the original evidence by evidence_id, finds the registered rollback
        policy for that command, and executes the rollback through the same
        enforcement chain as run_command() (path scope, timeout, output budget).
        Records a rollback_executed event and a new execution_evidence row.
        Returns RollbackResult with eligible=False if no rollback is possible.
        """
        if not self.db_path.exists():
            raise RuntimeManagerStoreError(f"runtime manager database not found: {self.db_path}")

        with closing(self._connect()) as connection:
            self._require_schema(connection)
            ev_row = connection.execute(
                "SELECT * FROM execution_evidence WHERE evidence_id = ?", (evidence_id,)
            ).fetchone()
        if ev_row is None:
            return RollbackResult(
                eligible=False,
                original_evidence_id=evidence_id,
                rollback_evidence_id=-1,
                command_id="",
                argv=(),
                stdout="",
                stderr="",
                returncode=-1,
                timed_out=False,
                duration_seconds=0.0,
                blockers=("evidence_not_found",),
                event_id=-1,
            )

        original_command_id = ev_row["command_id"]
        original_observation_id = ev_row["observation_id"]

        with closing(self._connect()) as connection:
            self._require_schema(connection)
            fwd_row = connection.execute(
                "SELECT rollback_class FROM command_registry WHERE command_id = ?", (original_command_id,)
            ).fetchone()
            rollback_row = connection.execute(
                "SELECT * FROM rollback_registry WHERE forward_command_id = ? AND status = 'enabled' LIMIT 1",
                (original_command_id,),
            ).fetchone()

        if fwd_row is not None and fwd_row["rollback_class"] == "irreversible":
            return RollbackResult(
                eligible=False,
                original_evidence_id=evidence_id,
                rollback_evidence_id=-1,
                command_id=original_command_id,
                argv=(),
                stdout="",
                stderr="",
                returncode=-1,
                timed_out=False,
                duration_seconds=0.0,
                blockers=("rollback_irreversible",),
                event_id=-1,
            )

        if rollback_row is None:
            return RollbackResult(
                eligible=False,
                original_evidence_id=evidence_id,
                rollback_evidence_id=-1,
                command_id=original_command_id,
                argv=(),
                stdout="",
                stderr="",
                returncode=-1,
                timed_out=False,
                duration_seconds=0.0,
                blockers=("no_rollback_policy",),
                event_id=-1,
            )

        argv = tuple(json.loads(rollback_row["argv_prefix_json"]))
        path_scope = rollback_row["path_scope"]
        timeout = rollback_row["timeout_seconds"] if rollback_row["timeout_seconds"] > 0 else None
        budget = rollback_row["output_budget_bytes"] if rollback_row["output_budget_bytes"] > 0 else None

        scope_path = (self.root / path_scope).resolve()
        try:
            scope_path.relative_to(self.root.resolve())
        except ValueError:
            return RollbackResult(
                eligible=False,
                original_evidence_id=evidence_id,
                rollback_evidence_id=-1,
                command_id=original_command_id,
                argv=argv,
                stdout="",
                stderr="",
                returncode=-1,
                timed_out=False,
                duration_seconds=0.0,
                blockers=("path_scope_violation",),
                event_id=-1,
            )

        stdout_raw = ""
        stderr_raw = ""
        returncode = -3
        timed_out = False
        duration = 0.0

        try:
            t0 = time.monotonic()
            proc = subprocess.Popen(
                argv,
                cwd=str(scope_path),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            try:
                stdout_raw, stderr_raw = proc.communicate(timeout=timeout)
                returncode = proc.returncode
            except subprocess.TimeoutExpired:
                proc.kill()
                stdout_raw, stderr_raw = proc.communicate()
                returncode = -2
                timed_out = True
            duration = time.monotonic() - t0
        except OSError:
            returncode = -3
            duration = 0.0

        stdout_digest = hashlib.sha256(stdout_raw.encode()).hexdigest()
        stderr_digest = hashlib.sha256(stderr_raw.encode()).hexdigest()
        stdout_truncated = False
        stderr_truncated = False
        if budget is not None:
            if len(stdout_raw.encode()) > budget:
                stdout_raw = stdout_raw.encode()[:budget].decode(errors="replace") + "\n[TRUNCATED]"
                stdout_truncated = True
            if len(stderr_raw.encode()) > budget:
                stderr_raw = stderr_raw.encode()[:budget].decode(errors="replace") + "\n[TRUNCATED]"
                stderr_truncated = True

        rollback_command_id = f"rollback:{original_command_id}"
        now = _utc_now()
        event_id = -1
        rollback_evidence_id = -1
        with closing(self._connect()) as connection:
            self._append_event(
                connection,
                event_type="rollback_executed",
                subject_id=original_observation_id,
                payload={
                    "original_evidence_id": evidence_id,
                    "original_command_id": original_command_id,
                    "rollback_id": rollback_row["rollback_id"],
                    "argv": list(argv),
                    "returncode": returncode,
                    "timed_out": timed_out,
                    "duration_seconds": round(duration, 3),
                },
                created_at=now,
            )
            event_id = connection.execute("SELECT last_insert_rowid()").fetchone()[0]
            connection.execute(
                """INSERT INTO execution_evidence (
                    command_id, observation_id, approval_id, action_fingerprint,
                    rollback_class, returncode, timed_out, duration_seconds,
                    stdout_digest, stderr_digest, stdout_truncated, stderr_truncated,
                    output_redacted, event_id, recorded_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    rollback_command_id,
                    original_observation_id,
                    "",
                    f"rollback:{rollback_row['rollback_id']}",
                    "rollback",
                    returncode,
                    int(timed_out),
                    round(duration, 3),
                    stdout_digest,
                    stderr_digest,
                    int(stdout_truncated),
                    int(stderr_truncated),
                    0,
                    event_id,
                    now,
                ),
            )
            rollback_evidence_id = connection.execute("SELECT last_insert_rowid()").fetchone()[0]
            connection.commit()

        result = RollbackResult(
            eligible=True,
            original_evidence_id=evidence_id,
            rollback_evidence_id=rollback_evidence_id,
            command_id=rollback_command_id,
            argv=argv,
            stdout=stdout_raw,
            stderr=stderr_raw,
            returncode=returncode,
            timed_out=timed_out,
            duration_seconds=round(duration, 3),
            blockers=(),
            event_id=event_id,
        )
        self._record_operation_trace(
            operation="rollback",
            subject_id=original_observation_id,
            status="passed" if returncode == 0 and not timed_out else "failed",
            input_payload={"evidence_id": evidence_id, "original_command_id": original_command_id},
            output_payload={
                "rollback_evidence_id": rollback_evidence_id,
                "returncode": returncode,
                "timed_out": timed_out,
            },
            events=(("rollback_executed", {"rollback_evidence_id": rollback_evidence_id, "returncode": returncode}),),
        )
        return result

    def raise_stop_condition(
        self,
        subject_id: str,
        reason: str,
        severity: str = "blocking",
    ) -> ManagedStopCondition:
        """Create an active managed stop condition.

        severity must be 'blocking' or 'informational'. An active blocking stop
        condition whose subject_id matches the selected observation_id, 'runtime-manager',
        or '*' blocks all selection until resolved.
        """
        if not self.db_path.exists():
            raise RuntimeManagerStoreError(f"runtime manager database not found: {self.db_path}")
        if not subject_id:
            raise RuntimeManagerStoreError("subject_id must not be empty")
        if severity not in ("blocking", "informational"):
            raise RuntimeManagerStoreError(f"severity must be 'blocking' or 'informational': {severity!r}")
        stop_condition_id = str(uuid.uuid4())
        now = _utc_now()
        with closing(self._connect()) as connection:
            self._require_schema(connection)
            try:
                self._append_event(
                    connection,
                    event_type="stop_condition_raised",
                    subject_id=subject_id,
                    payload={
                        "stop_condition_id": stop_condition_id,
                        "severity": severity,
                        "reason": reason,
                    },
                    created_at=now,
                )
                event_id = connection.execute("SELECT last_insert_rowid()").fetchone()[0]
                connection.execute(
                    """INSERT INTO managed_stop_conditions
                        (stop_condition_id, subject_id, status, severity, opened_at,
                         resolved_at, reason, event_id)
                       VALUES (?, ?, 'active', ?, ?, '', ?, ?)""",
                    (stop_condition_id, subject_id, severity, now, reason, event_id),
                )
                connection.commit()
            except Exception:
                connection.rollback()
                raise
        condition = ManagedStopCondition(
            stop_condition_id=stop_condition_id,
            subject_id=subject_id,
            status="active",
            severity=severity,
            opened_at=now,
            resolved_at="",
            reason=reason,
            event_id=event_id,
        )
        self._record_operation_trace(
            operation="stop",
            subject_id=subject_id,
            status="raised",
            input_payload={"subject_id": subject_id, "severity": severity},
            output_payload=_stop_condition_payload(condition),
            events=(("stop_condition_raised", {"stop_condition_id": stop_condition_id}),),
        )
        return condition

    def resolve_stop_condition(self, stop_condition_id: str) -> bool:
        """Resolve an active managed stop condition.

        Returns True if found active and resolved; False if not found or already inactive.
        Only managed (write-API) stop conditions can be resolved this way.
        """
        if not self.db_path.exists():
            raise RuntimeManagerStoreError(f"runtime manager database not found: {self.db_path}")
        now = _utc_now()
        with closing(self._connect()) as connection:
            self._require_schema(connection)
            row = connection.execute(
                "SELECT subject_id, status FROM managed_stop_conditions WHERE stop_condition_id = ?",
                (stop_condition_id,),
            ).fetchone()
            if row is None or row["status"] != "active":
                self._record_operation_trace(
                    operation="stop",
                    subject_id=stop_condition_id,
                    status="resolve_noop",
                    input_payload={"stop_condition_id": stop_condition_id},
                    output_payload={"resolved": False},
                    events=(("stop_condition_resolve_noop", {"stop_condition_id": stop_condition_id}),),
                )
                return False
            try:
                self._append_event(
                    connection,
                    event_type="stop_condition_resolved",
                    subject_id=row["subject_id"],
                    payload={"stop_condition_id": stop_condition_id},
                    created_at=now,
                )
                connection.execute(
                    "UPDATE managed_stop_conditions SET status = 'resolved', resolved_at = ? WHERE stop_condition_id = ?",
                    (now, stop_condition_id),
                )
                connection.commit()
            except Exception:
                connection.rollback()
                raise
        self._record_operation_trace(
            operation="stop",
            subject_id=stop_condition_id,
            status="resolved",
            input_payload={"stop_condition_id": stop_condition_id},
            output_payload={"resolved": True},
            events=(("stop_condition_resolved", {"stop_condition_id": stop_condition_id}),),
        )
        return True

    def record_validation(
        self,
        validation_id: str,
        subject_id: str,
        status: str,
        reason: str,
        command_id: str = "",
        fresh_until: str = "",
    ) -> ManagedValidation:
        """Record or update a validation result in managed_validations.

        status must be 'green', 'red', or 'stale'.
        For status='green', fresh_until must be a non-empty ISO-8601 timestamp.
        Existing records with the same validation_id are overwritten.
        Managed validations take precedence over TOML-imported validations in selection.
        """
        if not self.db_path.exists():
            raise RuntimeManagerStoreError(f"runtime manager database not found: {self.db_path}")
        if status not in ("green", "red", "stale"):
            raise RuntimeManagerStoreError(f"status must be 'green', 'red', or 'stale': {status!r}")
        if status == "green" and not fresh_until:
            raise RuntimeManagerStoreError("fresh_until is required when status is 'green'")
        now = _utc_now()
        effective_fresh_until = fresh_until if status == "green" else ""
        with closing(self._connect()) as connection:
            self._require_schema(connection)
            try:
                self._append_event(
                    connection,
                    event_type="validation_recorded",
                    subject_id=subject_id,
                    payload={
                        "validation_id": validation_id,
                        "status": status,
                        "fresh_until": effective_fresh_until,
                        "command_id": command_id,
                        "reason": reason,
                    },
                    created_at=now,
                )
                event_id = connection.execute("SELECT last_insert_rowid()").fetchone()[0]
                connection.execute(
                    """INSERT INTO managed_validations
                        (validation_id, subject_id, status, checked_at, fresh_until, command_id, reason, event_id)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                       ON CONFLICT(validation_id) DO UPDATE SET
                        subject_id = excluded.subject_id,
                        status = excluded.status,
                        checked_at = excluded.checked_at,
                        fresh_until = excluded.fresh_until,
                        command_id = excluded.command_id,
                        reason = excluded.reason,
                        event_id = excluded.event_id""",
                    (validation_id, subject_id, status, now, effective_fresh_until, command_id, reason, event_id),
                )
                connection.commit()
            except Exception:
                connection.rollback()
                raise
        validation = ManagedValidation(
            validation_id=validation_id,
            subject_id=subject_id,
            status=status,
            checked_at=now,
            fresh_until=effective_fresh_until,
            command_id=command_id,
            reason=reason,
            event_id=event_id,
        )
        self._record_operation_trace(
            operation="validation",
            subject_id=subject_id,
            status=status,
            input_payload={"validation_id": validation_id, "subject_id": subject_id},
            output_payload=_validation_payload(validation),
            events=(("validation_recorded", {"validation_id": validation_id, "status": status}),),
        )
        return validation

    def acquire_lease(
        self,
        observation_id: str,
        owner: str,
        ttl_seconds: int,
        reason: str = "",
    ) -> AcquiredLease:
        """Create an active managed lease for observation_id.

        Raises RuntimeManagerStoreError if an active lease already exists for
        observation_id (UNIQUE partial index enforces single-flight per observation).
        """
        if not self.db_path.exists():
            raise RuntimeManagerStoreError(f"runtime manager database not found: {self.db_path}")
        if ttl_seconds <= 0:
            raise RuntimeManagerStoreError(f"ttl_seconds must be positive: {ttl_seconds}")
        lease_id = str(uuid.uuid4())
        now = _utc_now()
        expires_at = _utc_future(now, ttl_seconds)
        with closing(self._connect()) as connection:
            self._require_schema(connection)
            try:
                self._append_event(
                    connection,
                    event_type="lease_acquired",
                    subject_id=observation_id,
                    payload={
                        "lease_id": lease_id,
                        "owner": owner,
                        "expires_at": expires_at,
                        "reason": reason,
                    },
                    created_at=now,
                )
                event_id = connection.execute("SELECT last_insert_rowid()").fetchone()[0]
                connection.execute(
                    """INSERT INTO managed_leases
                        (lease_id, observation_id, owner, status, acquired_at, expires_at,
                         renewed_at, reason, released_at, event_id)
                       VALUES (?, ?, ?, 'active', ?, ?, '', ?, '', ?)""",
                    (lease_id, observation_id, owner, now, expires_at, reason, event_id),
                )
                connection.commit()
            except sqlite3.IntegrityError as exc:
                connection.rollback()
                raise RuntimeManagerStoreError(
                    f"active lease already exists for observation {observation_id!r}",
                    code="lease_contention",
                ) from exc
            except Exception:
                connection.rollback()
                raise
        lease = AcquiredLease(
            lease_id=lease_id,
            observation_id=observation_id,
            owner=owner,
            status="active",
            acquired_at=now,
            expires_at=expires_at,
            renewed_at="",
            reason=reason,
            released_at="",
            event_id=event_id,
        )
        self._record_operation_trace(
            operation="lease",
            subject_id=observation_id,
            status="acquired",
            input_payload={"observation_id": observation_id, "owner": owner, "ttl_seconds": ttl_seconds},
            output_payload=_lease_payload(lease),
            events=(("lease_acquired", {"lease_id": lease_id}),),
        )
        return lease

    def release_lease(self, lease_id: str, owner: str) -> bool:
        """Mark a managed lease as released.

        Returns True if the lease was found active and released; False if not found
        or the owner does not match or the lease is already inactive.
        """
        if not self.db_path.exists():
            raise RuntimeManagerStoreError(f"runtime manager database not found: {self.db_path}")
        now = _utc_now()
        with closing(self._connect()) as connection:
            self._require_schema(connection)
            row = connection.execute(
                "SELECT observation_id, owner, status FROM managed_leases WHERE lease_id = ?",
                (lease_id,),
            ).fetchone()
            if row is None or row["owner"] != owner or row["status"] != "active":
                noop_code = "lease_owner_mismatch" if (row is not None and row["owner"] != owner) else ""
                self._record_operation_trace(
                    operation="lease",
                    subject_id=lease_id,
                    status="release_noop",
                    input_payload={"lease_id": lease_id, "owner": owner},
                    output_payload={"released": False, "diagnostic_code": noop_code},
                    events=(("lease_release_noop", {"lease_id": lease_id, "code": noop_code}),),
                )
                return False
            try:
                self._append_event(
                    connection,
                    event_type="lease_released",
                    subject_id=row["observation_id"],
                    payload={"lease_id": lease_id, "owner": owner},
                    created_at=now,
                )
                connection.execute(
                    "UPDATE managed_leases SET status = 'released', released_at = ? WHERE lease_id = ?",
                    (now, lease_id),
                )
                connection.commit()
            except Exception:
                connection.rollback()
                raise
        self._record_operation_trace(
            operation="lease",
            subject_id=lease_id,
            status="released",
            input_payload={"lease_id": lease_id, "owner": owner},
            output_payload={"released": True},
            events=(("lease_released", {"lease_id": lease_id}),),
        )
        return True

    def heartbeat_lease(
        self,
        lease_id: str,
        owner: str,
        ttl_seconds: int,
    ) -> AcquiredLease | None:
        """Renew an active managed lease's expiry.

        Returns the updated AcquiredLease if found and active; None if the lease
        does not exist, does not belong to owner, or is no longer active.
        """
        if not self.db_path.exists():
            raise RuntimeManagerStoreError(f"runtime manager database not found: {self.db_path}")
        if ttl_seconds <= 0:
            raise RuntimeManagerStoreError(f"ttl_seconds must be positive: {ttl_seconds}")
        now = _utc_now()
        new_expires_at = _utc_future(now, ttl_seconds)
        with closing(self._connect()) as connection:
            self._require_schema(connection)
            row = connection.execute(
                "SELECT * FROM managed_leases WHERE lease_id = ?", (lease_id,)
            ).fetchone()
            if row is None or row["owner"] != owner or row["status"] != "active":
                noop_code = "lease_owner_mismatch" if (row is not None and row["owner"] != owner) else ""
                self._record_operation_trace(
                    operation="lease",
                    subject_id=lease_id,
                    status="heartbeat_noop",
                    input_payload={"lease_id": lease_id, "owner": owner},
                    output_payload={"renewed": False, "diagnostic_code": noop_code},
                    events=(("lease_heartbeat_noop", {"lease_id": lease_id, "code": noop_code}),),
                )
                return None
            try:
                self._append_event(
                    connection,
                    event_type="lease_heartbeat",
                    subject_id=row["observation_id"],
                    payload={
                        "lease_id": lease_id,
                        "owner": owner,
                        "new_expires_at": new_expires_at,
                    },
                    created_at=now,
                )
                connection.execute(
                    "UPDATE managed_leases SET expires_at = ?, renewed_at = ? WHERE lease_id = ?",
                    (new_expires_at, now, lease_id),
                )
                connection.commit()
            except Exception:
                connection.rollback()
                raise
        lease = AcquiredLease(
            lease_id=row["lease_id"],
            observation_id=row["observation_id"],
            owner=row["owner"],
            status="active",
            acquired_at=row["acquired_at"],
            expires_at=new_expires_at,
            renewed_at=now,
            reason=row["reason"],
            released_at=row["released_at"],
            event_id=int(row["event_id"]),
        )
        self._record_operation_trace(
            operation="lease",
            subject_id=row["observation_id"],
            status="heartbeat",
            input_payload={"lease_id": lease_id, "owner": owner, "ttl_seconds": ttl_seconds},
            output_payload=_lease_payload(lease),
            events=(("lease_heartbeat", {"lease_id": lease_id}),),
        )
        return lease

    def reclaim_expired_leases(self) -> int:
        """Mark all expired active managed leases as reclaimed.

        A lease is expired when status='active' and expires_at < now.
        Returns the count of leases reclaimed in this call.
        """
        if not self.db_path.exists():
            raise RuntimeManagerStoreError(f"runtime manager database not found: {self.db_path}")
        now = _utc_now()
        with closing(self._connect()) as connection:
            self._require_schema(connection)
            rows = connection.execute(
                """SELECT lease_id, observation_id, owner, expires_at
                   FROM managed_leases
                   WHERE status = 'active'
                   ORDER BY lease_id ASC"""
            ).fetchall()
            expired = [
                row for row in rows
                if not _lease_expires_at_is_current(row["expires_at"], now)
            ]
            if not expired:
                self._record_operation_trace(
                    operation="lease",
                    subject_id="runtime-manager",
                    status="reclaim_noop",
                    input_payload={},
                    output_payload={"reclaimed": 0},
                    events=(("lease_reclaim_noop", {"reclaimed": 0}),),
                )
                return 0
            try:
                for row in expired:
                    self._append_event(
                        connection,
                        event_type="lease_reclaimed",
                        subject_id=row["observation_id"],
                        payload={
                            "lease_id": row["lease_id"],
                            "owner": row["owner"],
                            "expired_at": row["expires_at"],
                        },
                        created_at=now,
                    )
                    connection.execute(
                        "UPDATE managed_leases SET status = 'reclaimed', released_at = ? WHERE lease_id = ?",
                        (now, row["lease_id"]),
                    )
                connection.commit()
            except Exception:
                connection.rollback()
                raise
        self._record_operation_trace(
            operation="lease",
            subject_id="runtime-manager",
            status="reclaimed",
            input_payload={},
            output_payload={"reclaimed": len(expired)},
            events=(("lease_reclaimed", {"reclaimed": len(expired)}),),
        )
        return len(expired)

    def record_approval(
        self,
        command_id: str,
        subject_id: str,
        actor: str,
        *,
        scope: str = "single-use",
        expires_at: str = "",
    ) -> "ApprovalRecord":
        """Record a write-API approval for a registered command on a specific observation.

        The action_fingerprint is computed from the command policy (command_id, argv_prefix,
        path_scope) so it matches exactly what check_command_eligibility() and run_command()
        verify.  The command must exist and be enabled in command_registry.
        """
        if not self.db_path.exists():
            raise RuntimeManagerStoreError(f"runtime manager database not found: {self.db_path}")
        with closing(self._connect()) as connection:
            self._require_schema(connection)
            policy_row = connection.execute(
                "SELECT * FROM command_registry WHERE command_id = ? AND status = 'enabled'",
                (command_id,),
            ).fetchone()
            if policy_row is None:
                raise RuntimeManagerStoreError(
                    f"record_approval: command not found or not enabled: {command_id}"
                )
            policy = CommandPolicy(
                command_id=policy_row["command_id"],
                argv_prefix=tuple(json.loads(policy_row["argv_prefix_json"])),
                path_scope=policy_row["path_scope"],
                side_effect_class=policy_row["side_effect_class"],
                network_allowed=bool(policy_row["network_allowed"]),
                timeout_seconds=policy_row["timeout_seconds"],
                output_budget_bytes=policy_row["output_budget_bytes"],
                sensitive_output_policy=policy_row["sensitive_output_policy"],
                approval_requirement=policy_row["approval_requirement"],
                rollback_class=policy_row["rollback_class"],
                status=policy_row["status"],
            )
            action_fingerprint = _command_action_fingerprint(policy)
            approval_id = str(uuid.uuid4())
            now = _utc_now()
            try:
                self._append_event(
                    connection,
                    event_type="approval_recorded",
                    subject_id=subject_id,
                    payload={
                        "approval_id": approval_id,
                        "command_id": command_id,
                        "action_fingerprint": action_fingerprint,
                        "actor": actor,
                        "scope": scope,
                        "expires_at": expires_at,
                    },
                    created_at=now,
                )
                event_id = connection.execute("SELECT last_insert_rowid()").fetchone()[0]
                connection.execute(
                    """INSERT INTO managed_approvals
                       (approval_id, subject_id, action_fingerprint, command_id,
                        actor, scope, status, granted_at, expires_at, revoked_at, event_id)
                       VALUES (?, ?, ?, ?, ?, ?, 'current', ?, ?, '', ?)""",
                    (approval_id, subject_id, action_fingerprint, command_id,
                     actor, scope, now, expires_at, event_id),
                )
                connection.commit()
            except Exception:
                connection.rollback()
                raise
            row = connection.execute(
                "SELECT * FROM managed_approvals WHERE approval_id = ?", (approval_id,)
            ).fetchone()
            approval = _row_to_managed_approval(row)
        self._record_operation_trace(
            operation="approval",
            subject_id=subject_id,
            status="recorded",
            input_payload={"command_id": command_id, "subject_id": subject_id, "actor": actor},
            output_payload=_approval_payload(approval),
            events=(("approval_recorded", {"approval_id": approval.approval_id, "command_id": command_id}),),
        )
        return approval

    def revoke_approval(self, approval_id: str) -> bool:
        """Revoke a write-API approval by approval_id.

        Returns True if the approval existed and was revoked, False if not found.
        Raises RuntimeManagerStoreError if the DB is missing.
        """
        if not self.db_path.exists():
            raise RuntimeManagerStoreError(f"runtime manager database not found: {self.db_path}")
        with closing(self._connect()) as connection:
            self._require_schema(connection)
            row = connection.execute(
                "SELECT approval_id, subject_id FROM managed_approvals WHERE approval_id = ? AND status = 'current'",
                (approval_id,),
            ).fetchone()
            if row is None:
                self._record_operation_trace(
                    operation="approval",
                    subject_id=approval_id,
                    status="revoke_noop",
                    input_payload={"approval_id": approval_id},
                    output_payload={"revoked": False},
                    events=(("approval_revoke_noop", {"approval_id": approval_id}),),
                )
                return False
            now = _utc_now()
            try:
                self._append_event(
                    connection,
                    event_type="approval_revoked",
                    subject_id=row["subject_id"],
                    payload={"approval_id": approval_id},
                    created_at=now,
                )
                connection.execute(
                    "UPDATE managed_approvals SET status = 'revoked', revoked_at = ? WHERE approval_id = ?",
                    (now, approval_id),
                )
                connection.commit()
            except Exception:
                connection.rollback()
                raise
        self._record_operation_trace(
            operation="approval",
            subject_id=approval_id,
            status="revoked",
            input_payload={"approval_id": approval_id},
            output_payload={"revoked": True},
            events=(("approval_revoked", {"approval_id": approval_id}),),
        )
        return True

    # ------------------------------------------------------------------
    # Adapter token management (schema v15)
    # ------------------------------------------------------------------

    def issue_adapter_token(
        self,
        agent_id: str,
        agent_role: str,
        scopes: list[str],
        ttl_seconds: int = 86400,
        max_autonomy_level: str = "L3_runtime_mutation",
    ) -> tuple["AdapterToken", str]:
        """Issue a new adapter credential.  Returns (AdapterToken, raw_token).

        The raw token is returned exactly once and is never stored.  Only its
        SHA-256 hash is persisted.  The caller must treat raw_token as a secret.
        max_autonomy_level caps which operation levels this token may execute.
        L4 is never issuable for MCP tokens.
        """
        if not self.db_path.exists():
            raise RuntimeManagerStoreError(f"runtime manager database not found: {self.db_path}")
        if ttl_seconds < 1:
            raise RuntimeManagerStoreError("issue_adapter_token: ttl_seconds must be >= 1")
        unknown = set(scopes) - ADAPTER_TOKEN_SCOPES
        if unknown:
            raise RuntimeManagerStoreError(f"issue_adapter_token: unknown scopes: {sorted(unknown)}")
        if max_autonomy_level not in _AUTONOMY_LEVEL_ORDER:
            raise RuntimeManagerStoreError(
                f"issue_adapter_token: unknown max_autonomy_level: {max_autonomy_level!r}"
            )
        if max_autonomy_level == "L4_external_high_risk":
            raise RuntimeManagerStoreError(
                "issue_adapter_token: max_autonomy_level L4_external_high_risk is not issuable; "
                "L4 actions require explicit human decision and are not executable via MCP"
            )
        raw_token = secrets.token_hex(32)
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        token_id = f"tok-{uuid.uuid4().hex}"
        now = _utc_now()
        expires_at = _utc_future(now, ttl_seconds)
        with closing(self._connect()) as connection:
            self._require_schema(connection)
            connection.execute(
                """INSERT INTO adapter_tokens
                   (token_id, agent_id, agent_role, scopes_json, token_hash,
                    status, issued_at, expires_at, revoked_at, max_autonomy_level)
                   VALUES (?, ?, ?, ?, ?, 'active', ?, ?, '', ?)""",
                (token_id, agent_id, agent_role, json.dumps(sorted(scopes)), token_hash,
                 now, expires_at, max_autonomy_level),
            )
            connection.commit()
        token = AdapterToken(
            token_id=token_id,
            agent_id=agent_id,
            agent_role=agent_role,
            scopes=tuple(sorted(scopes)),
            status="active",
            issued_at=now,
            expires_at=expires_at,
            revoked_at="",
            max_autonomy_level=max_autonomy_level,
        )
        self._record_operation_trace(
            operation="token",
            subject_id=agent_id,
            status="issued",
            input_payload={"agent_id": agent_id, "agent_role": agent_role, "scopes": sorted(scopes)},
            output_payload={"token_id": token_id, "expires_at": expires_at},
            events=(("token_issued", {"token_id": token_id, "agent_id": agent_id}),),
        )
        return token, raw_token

    def revoke_adapter_token(self, token_id: str) -> bool:
        """Revoke an adapter token by token_id.  Returns True if revoked."""
        if not self.db_path.exists():
            raise RuntimeManagerStoreError(f"runtime manager database not found: {self.db_path}")
        now = _utc_now()
        with closing(self._connect()) as connection:
            self._require_schema(connection)
            cursor = connection.execute(
                "UPDATE adapter_tokens SET status='revoked', revoked_at=? WHERE token_id=? AND status='active'",
                (now, token_id),
            )
            connection.commit()
        if cursor.rowcount == 0:
            return False
        self._record_operation_trace(
            operation="token",
            subject_id=token_id,
            status="revoked",
            input_payload={"token_id": token_id},
            output_payload={"revoked": True},
            events=(("token_revoked", {"token_id": token_id}),),
        )
        return True

    def authenticate_adapter_token(self, raw_token: str) -> "AdapterToken | None":
        """Authenticate a raw token.  Returns AdapterToken if valid, None otherwise.

        Computes SHA-256 of raw_token and looks up by hash.  Returns None if the
        token does not exist, is revoked, or has expired.  The raw_token is never
        stored; only its hash is compared.
        """
        if not self.db_path.exists():
            raise RuntimeManagerStoreError(f"runtime manager database not found: {self.db_path}")
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        with closing(self._connect()) as connection:
            self._require_schema(connection)
            row = connection.execute(
                "SELECT * FROM adapter_tokens WHERE token_hash = ?", (token_hash,)
            ).fetchone()
        if row is None:
            return None
        if row["status"] != "active":
            return None
        now = _utc_now()
        if row["expires_at"] and row["expires_at"] < now:
            return None
        keys = row.keys()
        return AdapterToken(
            token_id=row["token_id"],
            agent_id=row["agent_id"],
            agent_role=row["agent_role"],
            scopes=tuple(json.loads(row["scopes_json"])),
            status=row["status"],
            issued_at=row["issued_at"],
            expires_at=row["expires_at"],
            revoked_at=row["revoked_at"] or "",
            max_autonomy_level=row["max_autonomy_level"] if "max_autonomy_level" in keys else "L3_runtime_mutation",
        )

    def check_and_increment_rate_limit(
        self, agent_id: str, operation: str
    ) -> "RateLimitResult":
        """Persistent fixed-window rate limit check (per minute per agent_id+operation).

        Uses SQLite for durability across process restarts.  Fixed window per
        calendar minute (not sliding); count resets when the minute rolls over.
        Returns RateLimitResult with allowed=True if under limit.
        """
        if not self.db_path.exists():
            raise RuntimeManagerStoreError(f"runtime manager database not found: {self.db_path}")
        limit = RATE_LIMIT_MUTATE if operation in RATE_LIMIT_MUTATE_OPS else RATE_LIMIT_READ
        window_minute = int(time.time() // 60)
        bucket_key = f"{agent_id}:{operation}:{window_minute}"
        with closing(self._connect()) as connection:
            self._require_schema(connection)
            # BEGIN IMMEDIATE claims the write lock before increment+read so no
            # concurrent writer can interleave between our UPDATE and our SELECT.
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                """INSERT INTO adapter_rate_buckets(bucket_key, count, window_start)
                   VALUES (?, 1, ?)
                   ON CONFLICT(bucket_key) DO UPDATE SET count = count + 1""",
                (bucket_key, window_minute),
            )
            count = connection.execute(
                "SELECT count FROM adapter_rate_buckets WHERE bucket_key = ?", (bucket_key,)
            ).fetchone()["count"]
            old_window = window_minute - 2
            connection.execute(
                "DELETE FROM adapter_rate_buckets WHERE window_start < ?", (old_window,)
            )
            connection.commit()
        if count > limit:
            seconds_left = 60 - (int(time.time()) % 60) + 1
            return RateLimitResult(
                allowed=False,
                retry_after_seconds=seconds_left,
                agent_id=agent_id,
                operation=operation,
            )
        return RateLimitResult(
            allowed=True,
            retry_after_seconds=0,
            agent_id=agent_id,
            operation=operation,
        )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute("PRAGMA busy_timeout = 5000")
        return connection

    # ------------------------------------------------------------------
    # Policy / autonomy level API (Phase 8)
    # ------------------------------------------------------------------

    def classify_runtime_action(self, command_id: str) -> "ActionClassification":
        """Classify the autonomy level of a registered command.

        Returns ActionClassification with autonomy_level, required_controls,
        friction_budget, rationale, and classification_is_not_permission=True.
        Raises RuntimeManagerStoreError if the command is not registered.
        """
        if not self.db_path.exists():
            raise RuntimeManagerStoreError(f"runtime manager database not found: {self.db_path}")
        with closing(self._connect()) as connection:
            self._require_schema(connection)
            row = connection.execute(
                "SELECT * FROM command_registry WHERE command_id = ?", (command_id,)
            ).fetchone()
        if row is None:
            raise RuntimeManagerStoreError(f"classify_runtime_action: command not registered: {command_id}")
        keys = row.keys()
        inp = ActionInput(
            side_effect_class=row["side_effect_class"],
            network_allowed=bool(row["network_allowed"]),
            approval_requirement=row["approval_requirement"],
            path_scope=row["path_scope"],
            sensitive_output_policy=row["sensitive_output_policy"],
            rollback_class=row["rollback_class"],
            target_scope=row["target_scope"] if "target_scope" in keys else "local",
            data_sensitivity=row["data_sensitivity"] if "data_sensitivity" in keys else "none",
            risk_level_override=row["risk_level_override"] if "risk_level_override" in keys else "",
            requires_human_decision=bool(row["requires_human_decision"]) if "requires_human_decision" in keys else False,
        )
        return classify_action(inp)

    def increment_policy_counter(self, counter_key: str) -> None:
        """Increment a named policy counter in policy_counters table."""
        if not self.db_path.exists():
            return
        now = _utc_now()
        with closing(self._connect()) as connection:
            self._require_schema(connection)
            connection.execute(
                """INSERT INTO policy_counters(counter_key, count, updated_at)
                   VALUES(?, 1, ?)
                   ON CONFLICT(counter_key) DO UPDATE SET count=count+1, updated_at=?""",
                (counter_key, now, now),
            )
            connection.commit()

    def read_policy_counter(self, counter_key: str) -> int:
        """Return the current value of a policy counter (0 if not set)."""
        if not self.db_path.exists():
            return 0
        with closing(self._connect()) as connection:
            self._require_schema(connection)
            row = connection.execute(
                "SELECT count FROM policy_counters WHERE counter_key = ?", (counter_key,)
            ).fetchone()
        return row["count"] if row else 0

    def check_integrity(self) -> "RuntimeIntegrityReport":
        """Run local diagnostic checks on runtime.db.  Advisory only — not a gate.

        Returns RuntimeIntegrityReport with counts and issue descriptions.
        integrity_report_is_not_permission = True always.
        """
        if not self.db_path.exists():
            raise RuntimeManagerStoreError(f"runtime manager database not found: {self.db_path}")

        now = _utc_now()
        issues: list[str] = []

        with closing(self._connect()) as conn:
            self._require_schema(conn)

            # Orphan trace events: events referencing a non-existent trace
            orphan_trace_events: int = conn.execute(
                """SELECT COUNT(*) FROM runtime_trace_events rte
                   WHERE NOT EXISTS (
                       SELECT 1 FROM runtime_traces rt WHERE rt.trace_id = rte.trace_id
                   )"""
            ).fetchone()[0]
            if orphan_trace_events > 0:
                issues.append(f"orphan_trace_events:{orphan_trace_events}")

            # Incomplete old traces: started > 5 min ago but no finished_at
            incomplete_old_traces: int = conn.execute(
                """SELECT COUNT(*) FROM runtime_traces
                   WHERE (finished_at IS NULL OR finished_at = '')
                   AND started_at < ?""",
                (_utc_before_seconds(300),),
            ).fetchone()[0]
            if incomplete_old_traces > 0:
                issues.append(f"incomplete_old_traces:{incomplete_old_traces}")

            # Expired-but-active managed leases
            expired_active_leases: int = conn.execute(
                """SELECT COUNT(*) FROM managed_leases
                   WHERE status = 'active'
                   AND expires_at != ''
                   AND expires_at < ?""",
                (now,),
            ).fetchone()[0]
            if expired_active_leases > 0:
                issues.append(f"expired_active_leases:{expired_active_leases}")

            # Expired-but-active adapter tokens
            expired_active_tokens: int = conn.execute(
                """SELECT COUNT(*) FROM adapter_tokens
                   WHERE status = 'active'
                   AND expires_at != ''
                   AND expires_at < ?""",
                (now,),
            ).fetchone()[0]
            if expired_active_tokens > 0:
                issues.append(f"expired_active_tokens:{expired_active_tokens}")

            # Stale rate buckets: window_start is minutes-since-epoch (integer)
            stale_rate_buckets: int = conn.execute(
                """SELECT COUNT(*) FROM adapter_rate_buckets
                   WHERE window_start < ?""",
                (int(time.time() // 60) - 2,),
            ).fetchone()[0]
            if stale_rate_buckets > 0:
                issues.append(f"stale_rate_buckets:{stale_rate_buckets}")

            # Evidence without corresponding event in events table
            evidence_without_trace: int = conn.execute(
                """SELECT COUNT(*) FROM execution_evidence ee
                   WHERE ee.event_id != -1
                   AND NOT EXISTS (
                       SELECT 1 FROM events e WHERE e.event_id = ee.event_id
                   )"""
            ).fetchone()[0]
            if evidence_without_trace > 0:
                issues.append(f"evidence_without_trace:{evidence_without_trace}")

            # Policy counter plausibility: mcp_level_blocked must be >= 0
            row = conn.execute(
                "SELECT count FROM policy_counters WHERE counter_key = 'mcp_level_blocked'"
            ).fetchone()
            mcp_blocked_count = row["count"] if row else 0
            policy_counter_plausibility = mcp_blocked_count >= 0
            if not policy_counter_plausibility:
                issues.append("policy_counter_implausible:mcp_level_blocked_negative")

        return RuntimeIntegrityReport(
            generated_at=now,
            orphan_trace_events=orphan_trace_events,
            incomplete_old_traces=incomplete_old_traces,
            expired_active_leases=expired_active_leases,
            expired_active_tokens=expired_active_tokens,
            stale_rate_buckets=stale_rate_buckets,
            evidence_without_trace=evidence_without_trace,
            policy_counter_plausibility=policy_counter_plausibility,
            issues=tuple(issues),
        )

    def _create_schema(self, connection: sqlite3.Connection) -> None:
        connection.executescript(
            """
            PRAGMA foreign_keys = ON;
            CREATE TABLE IF NOT EXISTS metadata (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS observations (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                status TEXT NOT NULL,
                kind TEXT NOT NULL,
                priority TEXT NOT NULL,
                boundary TEXT NOT NULL,
                trigger TEXT NOT NULL,
                dependencies_satisfied INTEGER NOT NULL,
                next_action TEXT NOT NULL,
                done_when TEXT NOT NULL,
                halt_if TEXT NOT NULL,
                source_path TEXT NOT NULL,
                source_sha256 TEXT NOT NULL,
                source_index INTEGER NOT NULL,
                imported_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS observation_dependencies (
                observation_id TEXT NOT NULL,
                dependency_id TEXT NOT NULL,
                source_index INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (observation_id, dependency_id),
                FOREIGN KEY (observation_id) REFERENCES observations(id) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS observation_decision_requirements (
                observation_id TEXT NOT NULL,
                decision_id TEXT NOT NULL,
                PRIMARY KEY (observation_id, decision_id),
                FOREIGN KEY (observation_id) REFERENCES observations(id) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS observation_evidence_requirements (
                observation_id TEXT NOT NULL,
                evidence_id TEXT NOT NULL,
                PRIMARY KEY (observation_id, evidence_id),
                FOREIGN KEY (observation_id) REFERENCES observations(id) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS observation_tool_requirements (
                observation_id TEXT NOT NULL,
                tool_id TEXT NOT NULL,
                PRIMARY KEY (observation_id, tool_id),
                FOREIGN KEY (observation_id) REFERENCES observations(id) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS observation_approval_requirements (
                observation_id TEXT NOT NULL,
                approval_id TEXT NOT NULL,
                PRIMARY KEY (observation_id, approval_id),
                FOREIGN KEY (observation_id) REFERENCES observations(id) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS observation_validation_requirements (
                observation_id TEXT NOT NULL,
                validation_id TEXT NOT NULL,
                PRIMARY KEY (observation_id, validation_id),
                FOREIGN KEY (observation_id) REFERENCES observations(id) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS decisions (
                decision_id TEXT PRIMARY KEY,
                subject_id TEXT NOT NULL,
                revision INTEGER NOT NULL,
                status TEXT NOT NULL,
                effective_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                human_decision_id TEXT NOT NULL,
                evidence_ids_json TEXT NOT NULL,
                supersedes_id TEXT NOT NULL,
                source_path TEXT NOT NULL,
                source_sha256 TEXT NOT NULL,
                imported_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS evidence_records (
                evidence_id TEXT PRIMARY KEY,
                kind TEXT NOT NULL,
                source TEXT NOT NULL,
                sanitized_digest TEXT NOT NULL,
                retention_class TEXT NOT NULL,
                status TEXT NOT NULL,
                reason TEXT NOT NULL,
                linked_subject_id TEXT NOT NULL,
                source_path TEXT NOT NULL,
                source_sha256 TEXT NOT NULL,
                imported_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS tool_registry (
                tool_id TEXT PRIMARY KEY,
                argv_prefix_json TEXT NOT NULL,
                path_scope TEXT NOT NULL,
                side_effect_class TEXT NOT NULL,
                network_cloud TEXT NOT NULL,
                timeout_seconds INTEGER NOT NULL,
                output_budget_bytes INTEGER NOT NULL,
                sensitive_output_policy TEXT NOT NULL,
                approval_requirement TEXT NOT NULL,
                rollback_expectation TEXT NOT NULL,
                status TEXT NOT NULL,
                source_path TEXT NOT NULL,
                source_sha256 TEXT NOT NULL,
                imported_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS approval_records (
                approval_id TEXT PRIMARY KEY,
                subject_id TEXT NOT NULL,
                action_fingerprint TEXT NOT NULL,
                scope TEXT NOT NULL,
                actor TEXT NOT NULL,
                status TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                revocation_path TEXT NOT NULL,
                audit_event_id TEXT NOT NULL,
                source_path TEXT NOT NULL,
                source_sha256 TEXT NOT NULL,
                imported_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS runtime_leases (
                lease_id TEXT PRIMARY KEY,
                observation_id TEXT NOT NULL,
                owner TEXT NOT NULL,
                status TEXT NOT NULL,
                acquired_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                reason TEXT NOT NULL,
                source_path TEXT NOT NULL,
                source_sha256 TEXT NOT NULL,
                imported_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS replay_runs (
                replay_id TEXT PRIMARY KEY,
                source_event_id TEXT NOT NULL,
                status TEXT NOT NULL,
                replay_digest TEXT NOT NULL,
                checked_at TEXT NOT NULL,
                reason TEXT NOT NULL,
                source_path TEXT NOT NULL,
                source_sha256 TEXT NOT NULL,
                imported_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS validation_records (
                validation_id TEXT PRIMARY KEY,
                subject_id TEXT NOT NULL,
                status TEXT NOT NULL,
                checked_at TEXT NOT NULL,
                fresh_until TEXT NOT NULL DEFAULT '',
                command_id TEXT NOT NULL,
                evidence_id TEXT NOT NULL,
                reason TEXT NOT NULL,
                source_path TEXT NOT NULL,
                source_sha256 TEXT NOT NULL,
                imported_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS stop_conditions (
                stop_condition_id TEXT PRIMARY KEY,
                subject_id TEXT NOT NULL,
                status TEXT NOT NULL,
                severity TEXT NOT NULL,
                opened_at TEXT NOT NULL,
                resolved_at TEXT NOT NULL,
                reason TEXT NOT NULL,
                source_path TEXT NOT NULL,
                source_sha256 TEXT NOT NULL,
                imported_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS events (
                event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT NOT NULL,
                subject_id TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS center_authority_events (
                center_event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT NOT NULL,
                authority_mode TEXT NOT NULL,
                revision INTEGER NOT NULL,
                source_path TEXT NOT NULL,
                source_sha256 TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS runtime_traces (
                trace_id TEXT PRIMARY KEY,
                operation TEXT NOT NULL,
                subject_id TEXT NOT NULL,
                status TEXT NOT NULL,
                policy_version TEXT NOT NULL,
                causation_id TEXT NOT NULL DEFAULT '',
                correlation_id TEXT NOT NULL DEFAULT '',
                input_digest TEXT NOT NULL,
                output_digest TEXT NOT NULL,
                started_at TEXT NOT NULL,
                finished_at TEXT NOT NULL,
                event_count INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS runtime_trace_events (
                trace_event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                trace_id TEXT NOT NULL,
                sequence INTEGER NOT NULL,
                event_name TEXT NOT NULL,
                subject_id TEXT NOT NULL,
                payload_digest TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS adapter_tokens (
                token_id TEXT PRIMARY KEY,
                agent_id TEXT NOT NULL,
                agent_role TEXT NOT NULL,
                scopes_json TEXT NOT NULL,
                token_hash TEXT NOT NULL UNIQUE,
                status TEXT NOT NULL DEFAULT 'active',
                issued_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                revoked_at TEXT NOT NULL DEFAULT '',
                max_autonomy_level TEXT NOT NULL DEFAULT 'L3_runtime_mutation'
            );
            CREATE TABLE IF NOT EXISTS adapter_rate_buckets (
                bucket_key TEXT PRIMARY KEY,
                count INTEGER NOT NULL DEFAULT 0,
                window_start INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS policy_counters (
                counter_key TEXT PRIMARY KEY,
                count INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS command_registry (
                command_id TEXT PRIMARY KEY,
                argv_prefix_json TEXT NOT NULL,
                path_scope TEXT NOT NULL,
                side_effect_class TEXT NOT NULL,
                network_allowed INTEGER NOT NULL DEFAULT 0,
                timeout_seconds INTEGER NOT NULL DEFAULT 60,
                output_budget_bytes INTEGER NOT NULL DEFAULT 65536,
                sensitive_output_policy TEXT NOT NULL DEFAULT 'none',
                approval_requirement TEXT NOT NULL DEFAULT 'required',
                rollback_class TEXT NOT NULL DEFAULT 'irreversible',
                status TEXT NOT NULL DEFAULT 'enabled',
                source_path TEXT NOT NULL,
                source_sha256 TEXT NOT NULL,
                imported_at TEXT NOT NULL,
                risk_level_override TEXT NOT NULL DEFAULT '',
                requires_human_decision INTEGER NOT NULL DEFAULT 0,
                data_sensitivity TEXT NOT NULL DEFAULT 'none',
                target_scope TEXT NOT NULL DEFAULT 'local'
            );
            CREATE TABLE IF NOT EXISTS execution_evidence (
                evidence_id INTEGER PRIMARY KEY AUTOINCREMENT,
                command_id TEXT NOT NULL,
                observation_id TEXT NOT NULL,
                approval_id TEXT NOT NULL DEFAULT '',
                action_fingerprint TEXT NOT NULL,
                rollback_class TEXT NOT NULL,
                returncode INTEGER NOT NULL,
                timed_out INTEGER NOT NULL DEFAULT 0,
                duration_seconds REAL NOT NULL DEFAULT 0.0,
                stdout_digest TEXT NOT NULL,
                stderr_digest TEXT NOT NULL,
                stdout_truncated INTEGER NOT NULL DEFAULT 0,
                stderr_truncated INTEGER NOT NULL DEFAULT 0,
                output_redacted INTEGER NOT NULL DEFAULT 0,
                event_id INTEGER NOT NULL DEFAULT -1,
                recorded_at TEXT NOT NULL,
                autonomy_level TEXT NOT NULL DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS managed_leases (
                lease_id TEXT PRIMARY KEY,
                observation_id TEXT NOT NULL,
                owner TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'active',
                acquired_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                renewed_at TEXT NOT NULL DEFAULT '',
                reason TEXT NOT NULL DEFAULT '',
                released_at TEXT NOT NULL DEFAULT '',
                event_id INTEGER NOT NULL DEFAULT -1
            );
            CREATE UNIQUE INDEX IF NOT EXISTS managed_leases_active_observation_unique
                ON managed_leases(observation_id)
                WHERE status = 'active';
            CREATE TABLE IF NOT EXISTS managed_stop_conditions (
                stop_condition_id TEXT PRIMARY KEY,
                subject_id TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'active',
                severity TEXT NOT NULL DEFAULT 'blocking',
                opened_at TEXT NOT NULL,
                resolved_at TEXT NOT NULL DEFAULT '',
                reason TEXT NOT NULL DEFAULT '',
                event_id INTEGER NOT NULL DEFAULT -1
            );
            CREATE TABLE IF NOT EXISTS managed_validations (
                validation_id TEXT PRIMARY KEY,
                subject_id TEXT NOT NULL,
                status TEXT NOT NULL,
                checked_at TEXT NOT NULL,
                fresh_until TEXT NOT NULL DEFAULT '',
                command_id TEXT NOT NULL DEFAULT '',
                reason TEXT NOT NULL DEFAULT '',
                event_id INTEGER NOT NULL DEFAULT -1
            );
            CREATE TABLE IF NOT EXISTS rollback_registry (
                rollback_id TEXT PRIMARY KEY,
                forward_command_id TEXT NOT NULL,
                argv_prefix_json TEXT NOT NULL,
                path_scope TEXT NOT NULL DEFAULT '.',
                timeout_seconds INTEGER NOT NULL DEFAULT 60,
                output_budget_bytes INTEGER NOT NULL DEFAULT 65536,
                status TEXT NOT NULL DEFAULT 'enabled',
                registered_at TEXT NOT NULL
            );
            CREATE UNIQUE INDEX IF NOT EXISTS rollback_registry_forward_command_unique
                ON rollback_registry(forward_command_id)
                WHERE status = 'enabled';
            CREATE TABLE IF NOT EXISTS managed_approvals (
                approval_id TEXT PRIMARY KEY,
                subject_id TEXT NOT NULL,
                action_fingerprint TEXT NOT NULL,
                command_id TEXT NOT NULL,
                actor TEXT NOT NULL,
                scope TEXT NOT NULL DEFAULT 'single-use',
                status TEXT NOT NULL DEFAULT 'current',
                granted_at TEXT NOT NULL,
                expires_at TEXT NOT NULL DEFAULT '',
                revoked_at TEXT NOT NULL DEFAULT '',
                event_id INTEGER NOT NULL DEFAULT -1
            );
            """
        )
        self._migrate_schema(connection)

    def _migrate_schema(self, connection: sqlite3.Connection) -> None:
        dependency_columns = self._table_columns(connection, "observation_dependencies")
        if dependency_columns and "source_index" not in dependency_columns:
            connection.execute("ALTER TABLE observation_dependencies ADD COLUMN source_index INTEGER NOT NULL DEFAULT 0")

        validation_columns = self._table_columns(connection, "validation_records")
        if validation_columns and "fresh_until" not in validation_columns:
            connection.execute("ALTER TABLE validation_records ADD COLUMN fresh_until TEXT NOT NULL DEFAULT ''")

        # Phase 8 migrations: add new columns to existing tables
        command_cols = self._table_columns(connection, "command_registry")
        if command_cols:
            for col, defn in [
                ("risk_level_override",    "TEXT NOT NULL DEFAULT ''"),
                ("requires_human_decision","INTEGER NOT NULL DEFAULT 0"),
                ("data_sensitivity",       "TEXT NOT NULL DEFAULT 'none'"),
                ("target_scope",           "TEXT NOT NULL DEFAULT 'local'"),
            ]:
                if col not in command_cols:
                    connection.execute(
                        f"ALTER TABLE command_registry ADD COLUMN {col} {defn}"
                    )

        token_cols = self._table_columns(connection, "adapter_tokens")
        if token_cols and "max_autonomy_level" not in token_cols:
            connection.execute(
                "ALTER TABLE adapter_tokens ADD COLUMN max_autonomy_level TEXT NOT NULL DEFAULT 'L3_runtime_mutation'"
            )

        evidence_cols = self._table_columns(connection, "execution_evidence")
        if evidence_cols and "autonomy_level" not in evidence_cols:
            connection.execute(
                "ALTER TABLE execution_evidence ADD COLUMN autonomy_level TEXT NOT NULL DEFAULT ''"
            )

        existing_tables = {row["name"] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if "managed_approvals" not in existing_tables:
            connection.execute("""CREATE TABLE IF NOT EXISTS managed_approvals (
                approval_id TEXT PRIMARY KEY,
                subject_id TEXT NOT NULL,
                action_fingerprint TEXT NOT NULL,
                command_id TEXT NOT NULL,
                actor TEXT NOT NULL,
                scope TEXT NOT NULL DEFAULT 'single-use',
                status TEXT NOT NULL DEFAULT 'current',
                granted_at TEXT NOT NULL,
                expires_at TEXT NOT NULL DEFAULT '',
                revoked_at TEXT NOT NULL DEFAULT '',
                event_id INTEGER NOT NULL DEFAULT -1
            )""")
        if "rollback_registry" not in existing_tables:
            connection.execute("""CREATE TABLE IF NOT EXISTS rollback_registry (
                rollback_id TEXT PRIMARY KEY,
                forward_command_id TEXT NOT NULL,
                argv_prefix_json TEXT NOT NULL,
                path_scope TEXT NOT NULL DEFAULT '.',
                timeout_seconds INTEGER NOT NULL DEFAULT 60,
                output_budget_bytes INTEGER NOT NULL DEFAULT 65536,
                status TEXT NOT NULL DEFAULT 'enabled',
                registered_at TEXT NOT NULL
            )""")
            connection.execute("""CREATE UNIQUE INDEX IF NOT EXISTS rollback_registry_forward_command_unique
                ON rollback_registry(forward_command_id)
                WHERE status = 'enabled'""")
        if "managed_stop_conditions" not in existing_tables:
            connection.execute("""CREATE TABLE IF NOT EXISTS managed_stop_conditions (
                stop_condition_id TEXT PRIMARY KEY,
                subject_id TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'active',
                severity TEXT NOT NULL DEFAULT 'blocking',
                opened_at TEXT NOT NULL,
                resolved_at TEXT NOT NULL DEFAULT '',
                reason TEXT NOT NULL DEFAULT '',
                event_id INTEGER NOT NULL DEFAULT -1
            )""")
        if "managed_validations" not in existing_tables:
            connection.execute("""CREATE TABLE IF NOT EXISTS managed_validations (
                validation_id TEXT PRIMARY KEY,
                subject_id TEXT NOT NULL,
                status TEXT NOT NULL,
                checked_at TEXT NOT NULL,
                fresh_until TEXT NOT NULL DEFAULT '',
                command_id TEXT NOT NULL DEFAULT '',
                reason TEXT NOT NULL DEFAULT '',
                event_id INTEGER NOT NULL DEFAULT -1
            )""")
        if "managed_leases" not in existing_tables:
            connection.execute("""CREATE TABLE IF NOT EXISTS managed_leases (
                lease_id TEXT PRIMARY KEY,
                observation_id TEXT NOT NULL,
                owner TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'active',
                acquired_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                renewed_at TEXT NOT NULL DEFAULT '',
                reason TEXT NOT NULL DEFAULT '',
                released_at TEXT NOT NULL DEFAULT '',
                event_id INTEGER NOT NULL DEFAULT -1
            )""")
            connection.execute("""CREATE UNIQUE INDEX IF NOT EXISTS managed_leases_active_observation_unique
                ON managed_leases(observation_id)
                WHERE status = 'active'""")
        if "command_registry" not in existing_tables:
            connection.execute("""CREATE TABLE IF NOT EXISTS command_registry (
                command_id TEXT PRIMARY KEY,
                argv_prefix_json TEXT NOT NULL,
                path_scope TEXT NOT NULL,
                side_effect_class TEXT NOT NULL,
                network_allowed INTEGER NOT NULL DEFAULT 0,
                timeout_seconds INTEGER NOT NULL DEFAULT 60,
                output_budget_bytes INTEGER NOT NULL DEFAULT 65536,
                sensitive_output_policy TEXT NOT NULL DEFAULT 'none',
                approval_requirement TEXT NOT NULL DEFAULT 'required',
                rollback_class TEXT NOT NULL DEFAULT 'irreversible',
                status TEXT NOT NULL DEFAULT 'enabled',
                source_path TEXT NOT NULL,
                source_sha256 TEXT NOT NULL,
                imported_at TEXT NOT NULL
            )""")
        if "execution_evidence" not in existing_tables:
            connection.execute("""CREATE TABLE IF NOT EXISTS execution_evidence (
                evidence_id INTEGER PRIMARY KEY AUTOINCREMENT,
                command_id TEXT NOT NULL,
                observation_id TEXT NOT NULL,
                approval_id TEXT NOT NULL DEFAULT '',
                action_fingerprint TEXT NOT NULL,
                rollback_class TEXT NOT NULL,
                returncode INTEGER NOT NULL,
                timed_out INTEGER NOT NULL DEFAULT 0,
                duration_seconds REAL NOT NULL DEFAULT 0.0,
                stdout_digest TEXT NOT NULL,
                stderr_digest TEXT NOT NULL,
                stdout_truncated INTEGER NOT NULL DEFAULT 0,
                stderr_truncated INTEGER NOT NULL DEFAULT 0,
                output_redacted INTEGER NOT NULL DEFAULT 0,
                event_id INTEGER NOT NULL DEFAULT -1,
                recorded_at TEXT NOT NULL
            )""")
        if "runtime_traces" not in existing_tables:
            connection.execute("""CREATE TABLE IF NOT EXISTS runtime_traces (
                trace_id TEXT PRIMARY KEY,
                operation TEXT NOT NULL,
                subject_id TEXT NOT NULL,
                status TEXT NOT NULL,
                policy_version TEXT NOT NULL,
                causation_id TEXT NOT NULL DEFAULT '',
                correlation_id TEXT NOT NULL DEFAULT '',
                input_digest TEXT NOT NULL,
                output_digest TEXT NOT NULL,
                started_at TEXT NOT NULL,
                finished_at TEXT NOT NULL,
                event_count INTEGER NOT NULL DEFAULT 0
            )""")
        if "runtime_trace_events" not in existing_tables:
            connection.execute("""CREATE TABLE IF NOT EXISTS runtime_trace_events (
                trace_event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                trace_id TEXT NOT NULL,
                sequence INTEGER NOT NULL,
                event_name TEXT NOT NULL,
                subject_id TEXT NOT NULL,
                payload_digest TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            )""")
        if "adapter_tokens" not in existing_tables:
            connection.execute("""CREATE TABLE IF NOT EXISTS adapter_tokens (
                token_id TEXT PRIMARY KEY,
                agent_id TEXT NOT NULL,
                agent_role TEXT NOT NULL,
                scopes_json TEXT NOT NULL,
                token_hash TEXT NOT NULL UNIQUE,
                status TEXT NOT NULL DEFAULT 'active',
                issued_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                revoked_at TEXT NOT NULL DEFAULT ''
            )""")
        if "adapter_rate_buckets" not in existing_tables:
            connection.execute("""CREATE TABLE IF NOT EXISTS adapter_rate_buckets (
                bucket_key TEXT PRIMARY KEY,
                count INTEGER NOT NULL DEFAULT 0,
                window_start INTEGER NOT NULL
            )""")
        if "policy_counters" not in existing_tables:
            connection.execute("""CREATE TABLE IF NOT EXISTS policy_counters (
                counter_key TEXT PRIMARY KEY,
                count INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL DEFAULT ''
            )""")
        if "center_authority_events" not in existing_tables:
            connection.execute("""CREATE TABLE IF NOT EXISTS center_authority_events (
                center_event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT NOT NULL,
                authority_mode TEXT NOT NULL,
                revision INTEGER NOT NULL,
                source_path TEXT NOT NULL,
                source_sha256 TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            )""")

    def _require_schema(self, connection: sqlite3.Connection) -> None:
        tables = {
            row["name"]
            for row in connection.execute(
                """
                SELECT name FROM sqlite_master
                WHERE type = 'table'
                  AND name IN (
                    'metadata', 'observations', 'observation_dependencies',
                    'observation_decision_requirements', 'observation_evidence_requirements',
                    'decisions', 'evidence_records',
                    'observation_tool_requirements', 'observation_approval_requirements',
                    'observation_validation_requirements',
                    'tool_registry', 'approval_records', 'runtime_leases',
                    'replay_runs', 'validation_records', 'stop_conditions', 'events',
                    'center_authority_events',
                    'runtime_traces', 'runtime_trace_events',
                    'command_registry', 'execution_evidence', 'managed_leases',
                    'managed_stop_conditions', 'managed_validations', 'rollback_registry',
                    'managed_approvals', 'adapter_tokens', 'adapter_rate_buckets',
                    'policy_counters'
                  )
                """
            )
        }
        expected = {
            "metadata",
            "observations",
            "observation_dependencies",
            "observation_decision_requirements",
            "observation_evidence_requirements",
            "decisions",
            "evidence_records",
            "observation_tool_requirements",
            "observation_approval_requirements",
            "observation_validation_requirements",
            "tool_registry",
            "approval_records",
            "runtime_leases",
            "replay_runs",
            "validation_records",
            "stop_conditions",
            "events",
            "center_authority_events",
            "runtime_traces",
            "runtime_trace_events",
            "command_registry",
            "execution_evidence",
            "managed_leases",
            "managed_stop_conditions",
            "managed_validations",
            "rollback_registry",
            "managed_approvals",
            "adapter_tokens",
            "adapter_rate_buckets",
            "policy_counters",
        }
        if tables != expected:
            raise RuntimeManagerStoreError("runtime manager database schema is missing or incomplete")
        self._require_table_columns(
            connection,
            "observation_dependencies",
            {
                "observation_id",
                "dependency_id",
                "source_index",
            },
        )
        self._require_table_columns(
            connection,
            "runtime_leases",
            {
                "lease_id",
                "observation_id",
                "owner",
                "status",
                "acquired_at",
                "expires_at",
                "reason",
                "source_path",
                "source_sha256",
                "imported_at",
            },
        )
        self._require_table_columns(
            connection,
            "replay_runs",
            {
                "replay_id",
                "source_event_id",
                "status",
                "replay_digest",
                "checked_at",
                "reason",
                "source_path",
                "source_sha256",
                "imported_at",
            },
        )
        self._require_table_columns(
            connection,
            "validation_records",
            {
                "validation_id",
                "subject_id",
                "status",
                "checked_at",
                "fresh_until",
                "command_id",
                "evidence_id",
                "reason",
                "source_path",
                "source_sha256",
                "imported_at",
            },
        )
        self._require_table_columns(
            connection,
            "stop_conditions",
            {
                "stop_condition_id",
                "subject_id",
                "status",
                "severity",
                "opened_at",
                "resolved_at",
                "reason",
                "source_path",
                "source_sha256",
                "imported_at",
            },
        )
        self._require_table_columns(
            connection,
            "command_registry",
            {
                "command_id",
                "argv_prefix_json",
                "path_scope",
                "side_effect_class",
                "network_allowed",
                "timeout_seconds",
                "output_budget_bytes",
                "sensitive_output_policy",
                "approval_requirement",
                "rollback_class",
                "status",
                "source_path",
                "source_sha256",
                "imported_at",
                "risk_level_override",
                "requires_human_decision",
                "data_sensitivity",
                "target_scope",
            },
        )
        self._require_table_columns(
            connection,
            "execution_evidence",
            {
                "evidence_id",
                "command_id",
                "observation_id",
                "approval_id",
                "action_fingerprint",
                "rollback_class",
                "returncode",
                "timed_out",
                "duration_seconds",
                "stdout_digest",
                "stderr_digest",
                "stdout_truncated",
                "stderr_truncated",
                "output_redacted",
                "event_id",
                "recorded_at",
                "autonomy_level",
            },
        )
        self._require_table_columns(
            connection,
            "policy_counters",
            {"counter_key", "count", "updated_at"},
        )
        self._require_table_columns(
            connection,
            "center_authority_events",
            {
                "center_event_id",
                "event_type",
                "authority_mode",
                "revision",
                "source_path",
                "source_sha256",
                "payload_json",
                "created_at",
            },
        )
        self._require_table_columns(
            connection,
            "runtime_traces",
            {
                "trace_id",
                "operation",
                "subject_id",
                "status",
                "policy_version",
                "causation_id",
                "correlation_id",
                "input_digest",
                "output_digest",
                "started_at",
                "finished_at",
                "event_count",
            },
        )
        self._require_table_columns(
            connection,
            "runtime_trace_events",
            {
                "trace_event_id",
                "trace_id",
                "sequence",
                "event_name",
                "subject_id",
                "payload_digest",
                "payload_json",
                "created_at",
            },
        )
        self._require_table_columns(
            connection,
            "managed_leases",
            {
                "lease_id",
                "observation_id",
                "owner",
                "status",
                "acquired_at",
                "expires_at",
                "renewed_at",
                "reason",
                "released_at",
                "event_id",
            },
        )
        self._require_table_columns(
            connection,
            "managed_stop_conditions",
            {
                "stop_condition_id",
                "subject_id",
                "status",
                "severity",
                "opened_at",
                "resolved_at",
                "reason",
                "event_id",
            },
        )
        self._require_table_columns(
            connection,
            "managed_validations",
            {
                "validation_id",
                "subject_id",
                "status",
                "checked_at",
                "fresh_until",
                "command_id",
                "reason",
                "event_id",
            },
        )
        self._require_table_columns(
            connection,
            "rollback_registry",
            {
                "rollback_id",
                "forward_command_id",
                "argv_prefix_json",
                "path_scope",
                "timeout_seconds",
                "output_budget_bytes",
                "status",
                "registered_at",
            },
        )
        self._require_table_columns(
            connection,
            "managed_approvals",
            {
                "approval_id",
                "subject_id",
                "action_fingerprint",
                "command_id",
                "actor",
                "scope",
                "status",
                "granted_at",
                "expires_at",
                "revoked_at",
                "event_id",
            },
        )
        metadata = self._read_metadata(connection)
        if metadata.get("schema_version") != str(SCHEMA_VERSION):
            raise RuntimeManagerStoreError("runtime manager database schema version is unsupported")

    def _require_table_columns(self, connection: sqlite3.Connection, table: str, expected: set[str]) -> None:
        columns = self._table_columns(connection, table)
        if not expected.issubset(columns):
            raise RuntimeManagerStoreError("runtime manager database schema is missing or incomplete")

    def _table_columns(self, connection: sqlite3.Connection, table: str) -> set[str]:
        return {row["name"] for row in connection.execute(f"PRAGMA table_info({table})")}

    def _read_observation_center(self, source_path: Path) -> dict:
        if not source_path.exists():
            raise RuntimeManagerStoreError(f"observation center not found: {source_path}")
        try:
            return tomllib.loads(source_path.read_text(encoding="utf-8"))
        except tomllib.TOMLDecodeError as exc:
            raise RuntimeManagerStoreError(f"observation center TOML is invalid: {exc}") from exc
        except OSError as exc:
            raise RuntimeManagerStoreError(f"failed to read observation center: {source_path}") from exc

    def _resolve_observation_center_path(self, path: str | Path | None) -> Path:
        candidate = Path(path) if path is not None else self.root / "docs" / "operations" / "observation_center.toml"
        if not candidate.is_absolute():
            candidate = self.root / candidate
        return candidate.resolve()

    def _normalize_observation(
        self,
        raw_observation: object,
        source_path: Path,
        source_sha256: str,
        source_index: int,
    ) -> RuntimeObservation:
        if not isinstance(raw_observation, dict):
            raise RuntimeManagerStoreError("each observation must be a table")
        observation_id = _string(raw_observation.get("id"))
        if not observation_id:
            raise RuntimeManagerStoreError("observation id is required")
        dependencies = raw_observation.get("dependencies", [])
        if not isinstance(dependencies, list) or not all(isinstance(item, str) for item in dependencies):
            raise RuntimeManagerStoreError(f"observation dependencies must be a list of strings: {observation_id}")
        required_decisions = raw_observation.get("required_decisions", [])
        if not isinstance(required_decisions, list) or not all(isinstance(item, str) for item in required_decisions):
            raise RuntimeManagerStoreError(f"observation required_decisions must be a list of strings: {observation_id}")
        required_evidence = raw_observation.get("required_evidence", [])
        if not isinstance(required_evidence, list) or not all(isinstance(item, str) for item in required_evidence):
            raise RuntimeManagerStoreError(f"observation required_evidence must be a list of strings: {observation_id}")
        required_tools = raw_observation.get("required_tools", [])
        if not isinstance(required_tools, list) or not all(isinstance(item, str) for item in required_tools):
            raise RuntimeManagerStoreError(f"observation required_tools must be a list of strings: {observation_id}")
        required_approvals = raw_observation.get("required_approvals", [])
        if not isinstance(required_approvals, list) or not all(isinstance(item, str) for item in required_approvals):
            raise RuntimeManagerStoreError(f"observation required_approvals must be a list of strings: {observation_id}")
        required_validations = raw_observation.get("required_validations", [])
        if not isinstance(required_validations, list) or not all(isinstance(item, str) for item in required_validations):
            raise RuntimeManagerStoreError(f"observation required_validations must be a list of strings: {observation_id}")
        return RuntimeObservation(
            id=observation_id,
            title=_string(raw_observation.get("title")),
            status=_string(raw_observation.get("status")),
            kind=_string(raw_observation.get("kind")),
            priority=_string(raw_observation.get("priority")),
            boundary=_string(raw_observation.get("boundary")),
            trigger=_string(raw_observation.get("trigger")),
            dependencies=tuple(dependencies),
            dependencies_satisfied=bool(raw_observation.get("dependencies_satisfied", False)),
            required_decisions=tuple(required_decisions),
            required_evidence=tuple(required_evidence),
            required_tools=tuple(required_tools),
            required_approvals=tuple(required_approvals),
            required_validations=tuple(required_validations),
            next_action=_string(raw_observation.get("next_action")),
            done_when=_string(raw_observation.get("done_when")),
            halt_if=_string(raw_observation.get("halt_if")),
            source_path=_relative_or_absolute(source_path, self.root),
            source_sha256=source_sha256,
            source_index=source_index,
        )

    def _insert_tool(
        self,
        connection: sqlite3.Connection,
        raw_tool: object,
        source_path: Path,
        source_sha256: str,
        imported_at: str,
    ) -> None:
        if not isinstance(raw_tool, dict):
            raise RuntimeManagerStoreError("each tool registry record must be a table")
        tool_id = _string(raw_tool.get("id"))
        if not tool_id:
            raise RuntimeManagerStoreError("tool id is required")
        argv_prefix = raw_tool.get("argv_prefix", [])
        if not isinstance(argv_prefix, list) or not all(isinstance(item, str) for item in argv_prefix):
            raise RuntimeManagerStoreError(f"tool argv_prefix must be a list of strings: {tool_id}")
        connection.execute(
            """
            INSERT INTO tool_registry(
                tool_id, argv_prefix_json, path_scope, side_effect_class, network_cloud,
                timeout_seconds, output_budget_bytes, sensitive_output_policy,
                approval_requirement, rollback_expectation, status,
                source_path, source_sha256, imported_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                tool_id,
                json.dumps(argv_prefix, sort_keys=True, separators=(",", ":")),
                _string(raw_tool.get("path_scope")),
                _string(raw_tool.get("side_effect_class")),
                _string(raw_tool.get("network_cloud")),
                int(raw_tool.get("timeout_seconds", 0)),
                int(raw_tool.get("output_budget_bytes", 0)),
                _string(raw_tool.get("sensitive_output_policy")),
                _string(raw_tool.get("approval_requirement")),
                _string(raw_tool.get("rollback_expectation")),
                _string(raw_tool.get("status")),
                _relative_or_absolute(source_path, self.root),
                source_sha256,
                imported_at,
            ),
        )

    def _insert_command(self, connection, raw_command, source_path, source_sha256, imported_at):
        if not isinstance(raw_command, dict):
            raise RuntimeManagerStoreError("each command registry record must be a table")
        command_id = _string(raw_command.get("id"))
        if not command_id:
            raise RuntimeManagerStoreError("command id is required")
        argv_prefix = raw_command.get("argv_prefix", [])
        if not isinstance(argv_prefix, list) or not all(isinstance(item, str) for item in argv_prefix):
            raise RuntimeManagerStoreError(f"command argv_prefix must be a list of strings: {command_id}")
        connection.execute(
            """INSERT INTO command_registry(
                command_id, argv_prefix_json, path_scope, side_effect_class,
                network_allowed, timeout_seconds, output_budget_bytes,
                sensitive_output_policy, approval_requirement, rollback_class,
                status, source_path, source_sha256, imported_at,
                risk_level_override, requires_human_decision, data_sensitivity, target_scope
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                command_id,
                json.dumps(argv_prefix, sort_keys=True, separators=(",", ":")),
                _string(raw_command.get("path_scope", ".")),
                _string(raw_command.get("side_effect_class", "read-only")),
                1 if raw_command.get("network_allowed", False) else 0,
                int(raw_command.get("timeout_seconds", 60)),
                int(raw_command.get("output_budget_bytes", 65536)),
                _string(raw_command.get("sensitive_output_policy", "none")),
                _string(raw_command.get("approval_requirement", "required")),
                _string(raw_command.get("rollback_class", "irreversible")),
                _string(raw_command.get("status", "enabled")),
                _relative_or_absolute(source_path, self.root),
                source_sha256,
                imported_at,
                _string(raw_command.get("risk_level_override", "")),
                1 if raw_command.get("requires_human_decision", False) else 0,
                _string(raw_command.get("data_sensitivity", "none")),
                _string(raw_command.get("target_scope", "local")),
            ),
        )

    def _insert_approval(
        self,
        connection: sqlite3.Connection,
        raw_approval: object,
        source_path: Path,
        source_sha256: str,
        imported_at: str,
    ) -> None:
        if not isinstance(raw_approval, dict):
            raise RuntimeManagerStoreError("each approval record must be a table")
        approval_id = _string(raw_approval.get("id"))
        if not approval_id:
            raise RuntimeManagerStoreError("approval id is required")
        connection.execute(
            """
            INSERT INTO approval_records(
                approval_id, subject_id, action_fingerprint, scope, actor, status,
                expires_at, revocation_path, audit_event_id,
                source_path, source_sha256, imported_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                approval_id,
                _string(raw_approval.get("subject_id")),
                _string(raw_approval.get("action_fingerprint")),
                _string(raw_approval.get("scope")),
                _string(raw_approval.get("actor")),
                _string(raw_approval.get("status")),
                _string(raw_approval.get("expires_at")),
                _string(raw_approval.get("revocation_path")),
                _string(raw_approval.get("audit_event_id")),
                _relative_or_absolute(source_path, self.root),
                source_sha256,
                imported_at,
            ),
        )

    def _insert_lease(
        self,
        connection: sqlite3.Connection,
        raw_lease: object,
        source_path: Path,
        source_sha256: str,
        imported_at: str,
    ) -> None:
        if not isinstance(raw_lease, dict):
            raise RuntimeManagerStoreError("each runtime lease must be a table")
        lease_id = _string(raw_lease.get("id"))
        if not lease_id:
            raise RuntimeManagerStoreError("runtime lease id is required")
        connection.execute(
            """
            INSERT INTO runtime_leases(
                lease_id, observation_id, owner, status, acquired_at, expires_at,
                reason, source_path, source_sha256, imported_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                lease_id,
                _string(raw_lease.get("observation_id")),
                _string(raw_lease.get("owner")),
                _string(raw_lease.get("status")),
                _string(raw_lease.get("acquired_at")),
                _string(raw_lease.get("expires_at")),
                _string(raw_lease.get("reason")),
                _relative_or_absolute(source_path, self.root),
                source_sha256,
                imported_at,
            ),
        )

    def _insert_replay_run(
        self,
        connection: sqlite3.Connection,
        raw_replay: object,
        source_path: Path,
        source_sha256: str,
        imported_at: str,
    ) -> None:
        if not isinstance(raw_replay, dict):
            raise RuntimeManagerStoreError("each replay run must be a table")
        replay_id = _string(raw_replay.get("id"))
        if not replay_id:
            raise RuntimeManagerStoreError("replay run id is required")
        connection.execute(
            """
            INSERT INTO replay_runs(
                replay_id, source_event_id, status, replay_digest, checked_at,
                reason, source_path, source_sha256, imported_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                replay_id,
                _string(raw_replay.get("source_event_id")),
                _string(raw_replay.get("status")),
                _string(raw_replay.get("replay_digest")),
                _string(raw_replay.get("checked_at")),
                _string(raw_replay.get("reason")),
                _relative_or_absolute(source_path, self.root),
                source_sha256,
                imported_at,
            ),
        )

    def _insert_validation_record(
        self,
        connection: sqlite3.Connection,
        raw_validation: object,
        source_path: Path,
        source_sha256: str,
        imported_at: str,
    ) -> None:
        if not isinstance(raw_validation, dict):
            raise RuntimeManagerStoreError("each validation record must be a table")
        validation_id = _string(raw_validation.get("id"))
        if not validation_id:
            raise RuntimeManagerStoreError("validation record id is required")
        connection.execute(
            """
            INSERT INTO validation_records(
                validation_id, subject_id, status, checked_at, command_id,
                fresh_until, evidence_id, reason, source_path, source_sha256, imported_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                validation_id,
                _string(raw_validation.get("subject_id")),
                _string(raw_validation.get("status")),
                _string(raw_validation.get("checked_at")),
                _string(raw_validation.get("command_id")),
                _string(raw_validation.get("fresh_until")),
                _string(raw_validation.get("evidence_id")),
                _string(raw_validation.get("reason")),
                _relative_or_absolute(source_path, self.root),
                source_sha256,
                imported_at,
            ),
        )

    def _insert_stop_condition(
        self,
        connection: sqlite3.Connection,
        raw_stop_condition: object,
        source_path: Path,
        source_sha256: str,
        imported_at: str,
    ) -> None:
        if not isinstance(raw_stop_condition, dict):
            raise RuntimeManagerStoreError("each stop condition must be a table")
        stop_condition_id = _string(raw_stop_condition.get("id"))
        if not stop_condition_id:
            raise RuntimeManagerStoreError("stop condition id is required")
        connection.execute(
            """
            INSERT INTO stop_conditions(
                stop_condition_id, subject_id, status, severity, opened_at,
                resolved_at, reason, source_path, source_sha256, imported_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                stop_condition_id,
                _string(raw_stop_condition.get("subject_id")),
                _string(raw_stop_condition.get("status")),
                _string(raw_stop_condition.get("severity")),
                _string(raw_stop_condition.get("opened_at")),
                _string(raw_stop_condition.get("resolved_at")),
                _string(raw_stop_condition.get("reason")),
                _relative_or_absolute(source_path, self.root),
                source_sha256,
                imported_at,
            ),
        )

    def _insert_decision(
        self,
        connection: sqlite3.Connection,
        raw_decision: object,
        source_path: Path,
        source_sha256: str,
        imported_at: str,
    ) -> None:
        if not isinstance(raw_decision, dict):
            raise RuntimeManagerStoreError("each decision must be a table")
        decision_id = _string(raw_decision.get("id"))
        if not decision_id:
            raise RuntimeManagerStoreError("decision id is required")
        evidence_ids = raw_decision.get("evidence_ids", [])
        if not isinstance(evidence_ids, list) or not all(isinstance(item, str) for item in evidence_ids):
            raise RuntimeManagerStoreError(f"decision evidence_ids must be a list of strings: {decision_id}")
        connection.execute(
            """
            INSERT INTO decisions(
                decision_id, subject_id, revision, status, effective_at, expires_at,
                human_decision_id, evidence_ids_json, supersedes_id,
                source_path, source_sha256, imported_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                decision_id,
                _string(raw_decision.get("subject_id")),
                int(raw_decision.get("revision", 0)),
                _string(raw_decision.get("status")),
                _string(raw_decision.get("effective_at")),
                _string(raw_decision.get("expires_at")),
                _string(raw_decision.get("human_decision_id")),
                json.dumps(evidence_ids, sort_keys=True, separators=(",", ":")),
                _string(raw_decision.get("supersedes_id")),
                _relative_or_absolute(source_path, self.root),
                source_sha256,
                imported_at,
            ),
        )

    def _insert_evidence_record(
        self,
        connection: sqlite3.Connection,
        raw_evidence: object,
        source_path: Path,
        source_sha256: str,
        imported_at: str,
    ) -> None:
        if not isinstance(raw_evidence, dict):
            raise RuntimeManagerStoreError("each evidence record must be a table")
        evidence_id = _string(raw_evidence.get("id"))
        if not evidence_id:
            raise RuntimeManagerStoreError("evidence id is required")
        connection.execute(
            """
            INSERT INTO evidence_records(
                evidence_id, kind, source, sanitized_digest, retention_class,
                status, reason, linked_subject_id, source_path, source_sha256, imported_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                evidence_id,
                _string(raw_evidence.get("kind")),
                _string(raw_evidence.get("source")),
                _string(raw_evidence.get("sanitized_digest")),
                _string(raw_evidence.get("retention_class")),
                _string(raw_evidence.get("status")),
                _string(raw_evidence.get("reason")),
                _string(raw_evidence.get("linked_subject_id")),
                _relative_or_absolute(source_path, self.root),
                source_sha256,
                imported_at,
            ),
        )

    def _insert_observation(self, connection: sqlite3.Connection, observation: RuntimeObservation, imported_at: str) -> None:
        connection.execute(
            """
            INSERT INTO observations(
                id, title, status, kind, priority, boundary, trigger,
                dependencies_satisfied, next_action, done_when, halt_if,
                source_path, source_sha256, source_index, imported_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                observation.id,
                observation.title,
                observation.status,
                observation.kind,
                observation.priority,
                observation.boundary,
                observation.trigger,
                int(observation.dependencies_satisfied),
                observation.next_action,
                observation.done_when,
                observation.halt_if,
                observation.source_path,
                observation.source_sha256,
                observation.source_index,
                imported_at,
            ),
        )

    def _read_metadata(self, connection: sqlite3.Connection) -> dict[str, str]:
        return {row["key"]: row["value"] for row in connection.execute("SELECT key, value FROM metadata")}

    def _upsert_metadata(self, connection: sqlite3.Connection, key: str, value: str) -> None:
        connection.execute(
            """
            INSERT INTO metadata(key, value) VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (key, value),
        )

    def _append_event(
        self,
        connection: sqlite3.Connection,
        *,
        event_type: str,
        subject_id: str,
        payload: dict,
        created_at: str,
    ) -> None:
        connection.execute(
            """
            INSERT INTO events(event_type, subject_id, payload_json, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (event_type, subject_id, json.dumps(payload, sort_keys=True, separators=(",", ":")), created_at),
        )

    def _append_center_authority_event(
        self,
        connection: sqlite3.Connection,
        *,
        event_type: str,
        authority_mode: str,
        revision: int,
        source_path: str,
        source_sha256: str,
        payload: dict,
        created_at: str,
    ) -> None:
        connection.execute(
            """
            INSERT INTO center_authority_events(
                event_type, authority_mode, revision, source_path, source_sha256,
                payload_json, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event_type,
                authority_mode,
                revision,
                source_path,
                source_sha256,
                json.dumps(payload, sort_keys=True, separators=(",", ":")),
                created_at,
            ),
        )

    def _center_snapshot_digest(self, connection: sqlite3.Connection) -> str:
        payload = {
            "observations": [
                _observation_snapshot_payload(item)
                for item in self._read_observations(connection)
            ],
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def _record_operation_trace(
        self,
        *,
        operation: str,
        subject_id: str,
        status: str,
        input_payload: dict,
        output_payload: dict,
        events: tuple[tuple[str, dict], ...] = (),
        causation_id: str = "",
        correlation_id: str = "",
    ) -> str:
        if not self.db_path.exists():
            return ""
        now = _utc_now()
        with closing(self._connect()) as connection:
            self._require_schema(connection)
            trace_id = self._append_runtime_trace(
                connection,
                operation=operation,
                subject_id=subject_id,
                status=status,
                input_payload=input_payload,
                output_payload=output_payload,
                events=events,
                causation_id=causation_id,
                correlation_id=correlation_id,
                started_at=now,
                finished_at=now,
            )
            connection.commit()
        return trace_id

    def _append_runtime_trace(
        self,
        connection: sqlite3.Connection,
        *,
        operation: str,
        subject_id: str,
        status: str,
        input_payload: dict,
        output_payload: dict,
        events: tuple[tuple[str, dict], ...],
        causation_id: str,
        correlation_id: str,
        started_at: str,
        finished_at: str,
    ) -> str:
        sanitized_input = _sanitize_trace_payload(input_payload)
        sanitized_output = _sanitize_trace_payload(output_payload)
        trace_id = f"rt-{uuid.uuid4().hex}"
        connection.execute(
            """
            INSERT INTO runtime_traces(
                trace_id, operation, subject_id, status, policy_version,
                causation_id, correlation_id, input_digest, output_digest,
                started_at, finished_at, event_count
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                trace_id,
                operation,
                subject_id,
                status,
                TRACE_POLICY_VERSION,
                causation_id,
                correlation_id,
                _stable_payload_digest(sanitized_input),
                _stable_payload_digest(sanitized_output),
                started_at,
                finished_at,
                len(events),
            ),
        )
        for index, (event_name, payload) in enumerate(events, start=1):
            sanitized_event_payload = _sanitize_trace_payload(payload)
            connection.execute(
                """
                INSERT INTO runtime_trace_events(
                    trace_id, sequence, event_name, subject_id, payload_digest,
                    payload_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    trace_id,
                    index,
                    event_name,
                    subject_id,
                    _stable_payload_digest(sanitized_event_payload),
                    json.dumps(sanitized_event_payload, sort_keys=True, separators=(",", ":")),
                    finished_at,
                ),
            )
        return trace_id

    def _read_observations(self, connection: sqlite3.Connection) -> tuple[RuntimeObservation, ...]:
        rows = connection.execute(
            """
            SELECT id, title, status, kind, priority, boundary, trigger,
                   dependencies_satisfied, next_action, done_when, halt_if,
                   source_path, source_sha256, source_index
            FROM observations
            ORDER BY source_index ASC, id ASC
            """
        ).fetchall()
        dependencies_by_id: dict[str, list[str]] = {}
        for row in connection.execute(
            "SELECT observation_id, dependency_id FROM observation_dependencies ORDER BY source_index ASC, dependency_id ASC"
        ):
            dependencies_by_id.setdefault(row["observation_id"], []).append(row["dependency_id"])
        decisions_by_id: dict[str, list[str]] = {}
        for row in connection.execute(
            "SELECT observation_id, decision_id FROM observation_decision_requirements ORDER BY decision_id ASC"
        ):
            decisions_by_id.setdefault(row["observation_id"], []).append(row["decision_id"])
        evidence_by_id: dict[str, list[str]] = {}
        for row in connection.execute(
            "SELECT observation_id, evidence_id FROM observation_evidence_requirements ORDER BY evidence_id ASC"
        ):
            evidence_by_id.setdefault(row["observation_id"], []).append(row["evidence_id"])
        tools_by_id: dict[str, list[str]] = {}
        for row in connection.execute(
            "SELECT observation_id, tool_id FROM observation_tool_requirements ORDER BY tool_id ASC"
        ):
            tools_by_id.setdefault(row["observation_id"], []).append(row["tool_id"])
        approvals_by_id: dict[str, list[str]] = {}
        for row in connection.execute(
            "SELECT observation_id, approval_id FROM observation_approval_requirements ORDER BY approval_id ASC"
        ):
            approvals_by_id.setdefault(row["observation_id"], []).append(row["approval_id"])
        validations_by_id: dict[str, list[str]] = {}
        for row in connection.execute(
            "SELECT observation_id, validation_id FROM observation_validation_requirements ORDER BY validation_id ASC"
        ):
            validations_by_id.setdefault(row["observation_id"], []).append(row["validation_id"])
        return tuple(
            RuntimeObservation(
                id=row["id"],
                title=row["title"],
                status=row["status"],
                kind=row["kind"],
                priority=row["priority"],
                boundary=row["boundary"],
                trigger=row["trigger"],
                dependencies=tuple(dependencies_by_id.get(row["id"], [])),
                dependencies_satisfied=bool(row["dependencies_satisfied"]),
                required_decisions=tuple(decisions_by_id.get(row["id"], [])),
                required_evidence=tuple(evidence_by_id.get(row["id"], [])),
                required_tools=tuple(tools_by_id.get(row["id"], [])),
                required_approvals=tuple(approvals_by_id.get(row["id"], [])),
                required_validations=tuple(validations_by_id.get(row["id"], [])),
                next_action=row["next_action"],
                done_when=row["done_when"],
                halt_if=row["halt_if"],
                source_path=row["source_path"],
                source_sha256=row["source_sha256"],
                source_index=int(row["source_index"]),
            )
            for row in rows
        )

    def _read_ledger_counts(self, connection: sqlite3.Connection) -> dict[str, object]:
        decision_rows = connection.execute("SELECT decision_id, status FROM decisions").fetchall()
        evidence_rows = connection.execute("SELECT evidence_id, status FROM evidence_records").fetchall()
        tool_rows = connection.execute("SELECT tool_id, status FROM tool_registry").fetchall()
        approval_rows = connection.execute("SELECT approval_id, status FROM approval_records").fetchall()
        checked_at = _utc_now()
        validation_rows = connection.execute("SELECT validation_id, status, fresh_until FROM validation_records").fetchall()
        stop_condition_rows = connection.execute("SELECT subject_id, status FROM stop_conditions").fetchall()
        event_count = connection.execute("SELECT COUNT(*) FROM events").fetchone()[0]
        replay_run_rows = connection.execute("SELECT replay_id, status FROM replay_runs").fetchall()
        commands_total = connection.execute("SELECT COUNT(*) FROM command_registry").fetchone()[0]
        commands_enabled = connection.execute("SELECT COUNT(*) FROM command_registry WHERE status = 'enabled'").fetchone()[0]
        execution_evidence_total = connection.execute("SELECT COUNT(*) FROM execution_evidence").fetchone()[0]
        current_decision_ids = {row["decision_id"] for row in decision_rows if row["status"] == "current"}
        accepted_evidence_ids = {row["evidence_id"] for row in evidence_rows if row["status"] == "accepted"}
        enabled_tool_ids = {row["tool_id"] for row in tool_rows if row["status"] == "enabled"}
        current_approval_ids = {row["approval_id"] for row in approval_rows if row["status"] == "current"}
        green_validation_ids = {
            row["validation_id"]
            for row in validation_rows
            if row["status"] == "green" and _fresh_until_is_current(row["fresh_until"], checked_at)
        }
        expired_validation_ids = {
            row["validation_id"]
            for row in validation_rows
            if row["status"] == "green" and not _fresh_until_is_current(row["fresh_until"], checked_at)
        }
        validation_gate_states = {
            row["validation_id"]: (
                "green"
                if row["status"] == "green" and _fresh_until_is_current(row["fresh_until"], checked_at)
                else "expired"
                if row["status"] == "green"
                else row["status"] or "unknown"
            )
            for row in validation_rows
        }
        active_stop_subjects = {row["subject_id"] for row in stop_condition_rows if row["status"] == "active"}
        # Merge write-API managed records into the selection state.
        managed_stop_rows = connection.execute(
            "SELECT subject_id, status FROM managed_stop_conditions"
        ).fetchall()
        managed_validation_rows = connection.execute(
            "SELECT validation_id, status, fresh_until FROM managed_validations"
        ).fetchall()
        managed_approval_rows = connection.execute(
            "SELECT approval_id, status FROM managed_approvals"
        ).fetchall()
        for row in managed_approval_rows:
            if row["status"] == "current":
                current_approval_ids.add(row["approval_id"])
        for row in managed_stop_rows:
            if row["status"] == "active":
                active_stop_subjects.add(row["subject_id"])
        for row in managed_validation_rows:
            gate_state = (
                "green"
                if row["status"] == "green" and _fresh_until_is_current(row["fresh_until"], checked_at)
                else "expired"
                if row["status"] == "green"
                else row["status"] or "unknown"
            )
            validation_gate_states[row["validation_id"]] = gate_state
            if gate_state == "green":
                green_validation_ids.add(row["validation_id"])
            else:
                green_validation_ids.discard(row["validation_id"])
        return {
            "decisions_total": len(decision_rows),
            "decisions_current": len(current_decision_ids),
            "current_decision_ids": current_decision_ids,
            "evidence_total": len(evidence_rows),
            "evidence_accepted": len(accepted_evidence_ids),
            "evidence_rejected": sum(1 for row in evidence_rows if row["status"] == "rejected"),
            "accepted_evidence_ids": accepted_evidence_ids,
            "tools_total": len(tool_rows),
            "tools_enabled": len(enabled_tool_ids),
            "enabled_tool_ids": enabled_tool_ids,
            "approvals_total": len(approval_rows),
            "approvals_current": len(current_approval_ids),
            "current_approval_ids": current_approval_ids,
            "events_total": int(event_count),
            "replay_runs_total": len(replay_run_rows),
            "replay_runs_passed": sum(1 for row in replay_run_rows if row["status"] == "passed"),
            "replay_runs_failed": sum(1 for row in replay_run_rows if row["status"] == "failed"),
            "failed_replay_ids": {row["replay_id"] for row in replay_run_rows if row["status"] == "failed"},
            "validations_total": len(validation_rows),
            "validations_green": len(green_validation_ids),
            "validations_red": sum(1 for row in validation_rows if row["status"] == "red"),
            "validations_stale": sum(1 for row in validation_rows if row["status"] == "stale"),
            "validations_expired": len(expired_validation_ids),
            "green_validation_ids": green_validation_ids,
            "validation_gate_states": validation_gate_states,
            "stop_conditions_total": len(stop_condition_rows),
            "stop_conditions_active": sum(1 for row in stop_condition_rows if row["status"] == "active"),
            "active_stop_subjects": active_stop_subjects,
            "commands_total": commands_total,
            "commands_enabled": commands_enabled,
            "execution_evidence_total": int(execution_evidence_total),
        }

    def _read_lease_state(self, connection: sqlite3.Connection) -> tuple[dict[str, str], dict[str, str]]:
        """Return (truly_active_leases, expired_leases) for all status='active' lease rows.

        Includes both TOML-imported runtime_leases and write-API managed_leases.
        Truly active: expires_at is empty, malformed, or a future timestamp (conservative).
        Expired: expires_at is a parseable past timestamp.
        Neither dict mutates runtime state; this is read-model classification only.
        """
        checked_at = _utc_now()
        toml_rows = connection.execute(
            "SELECT observation_id, owner, expires_at FROM runtime_leases WHERE status = 'active' ORDER BY lease_id ASC"
        ).fetchall()
        managed_rows = connection.execute(
            "SELECT observation_id, owner, expires_at FROM managed_leases WHERE status = 'active' ORDER BY lease_id ASC"
        ).fetchall()
        active: dict[str, str] = {}
        expired: dict[str, str] = {}
        for row in list(toml_rows) + list(managed_rows):
            if _lease_expires_at_is_current(row["expires_at"], checked_at):
                active[row["observation_id"]] = row["owner"]
            else:
                expired[row["observation_id"]] = row["owner"]
        return active, expired

    def _select_next(
        self,
        observations: tuple[RuntimeObservation, ...],
        *,
        stale_source: bool,
        current_decisions: set[str],
        accepted_evidence: set[str],
        enabled_tools: set[str],
        current_approvals: set[str],
        green_validations: set[str],
        validation_gate_states: dict[str, str],
        active_stop_subjects: set[str],
        active_leases: dict[str, str],
        expired_leases: dict[str, str],
        failed_replay_ids: set[str],
    ) -> tuple[RuntimeObservation | None, str, tuple[RuntimeGateDiagnostic, ...], RuntimeSelectionAudit]:
        diagnostics = self._build_gate_diagnostics(
            observations,
            stale_source=stale_source,
            current_decisions=current_decisions,
            accepted_evidence=accepted_evidence,
            enabled_tools=enabled_tools,
            current_approvals=current_approvals,
            green_validations=green_validations,
            validation_gate_states=validation_gate_states,
            active_stop_subjects=active_stop_subjects,
            active_leases=active_leases,
            expired_leases=expired_leases,
            failed_replay_ids=failed_replay_ids,
        )
        selection_audit = self._build_selection_audit(
            observations,
            stale_source=stale_source,
            current_decisions=current_decisions,
            accepted_evidence=accepted_evidence,
            enabled_tools=enabled_tools,
            current_approvals=current_approvals,
            green_validations=green_validations,
            validation_gate_states=validation_gate_states,
            active_stop_subjects=active_stop_subjects,
            active_leases=active_leases,
        )
        if stale_source:
            return None, "runtime.db source digest no longer matches observation_center.toml", diagnostics, selection_audit
        if active_leases:
            leased_ids = set(active_leases)
            open_ids = {item.id for item in observations if item.status == "open"}
            if not leased_ids.issubset(open_ids):
                return (
                    None,
                    "no open observation is eligible; active lease references a non-open observation",
                    diagnostics,
                    selection_audit,
                )
        active_runtime_stops = {"*", "runtime-manager", "runtime-manager-phase-1"} & active_stop_subjects
        if active_runtime_stops:
            return (
                None,
                "no open observation is eligible; active stop condition blocks runtime-manager readiness",
                diagnostics,
                selection_audit,
            )
        eligible_ids = set(selection_audit.eligible_ids)
        if active_leases and not eligible_ids:
            return None, "no open observation is eligible; single-flight lease is active for another item", diagnostics, selection_audit
        if eligible_ids:
            selected = sorted(
                [item for item in observations if item.id in eligible_ids],
                key=lambda item: (PRIORITY_RANK.get(item.priority, 99), item.source_index, item.id),
            )[0]
            # Informational only: surface stale/bad records even on success so operators can act.
            informational_items: list[RuntimeGateDiagnostic] = []
            if expired_leases:
                informational_items.append(_diagnostic("active_lease_expired", "runtime-manager", sorted(expired_leases)))
            if failed_replay_ids:
                informational_items.append(_diagnostic("failed_replay_run", "runtime-manager", sorted(failed_replay_ids)))
            informational = tuple(informational_items)
            return (
                selected,
                "selected highest-priority eligible open observation",
                informational,
                _replace_selection_decision(selection_audit, decision="selected", selected_id=selected.id),
            )
        blocked = [item for item in observations if item.status == "blocked"]
        waiting = [item for item in observations if item.status == "waiting"]
        missing_decision_items = [
            item for item in observations if item.status == "open" and not set(item.required_decisions).issubset(current_decisions)
        ]
        missing_evidence_items = [
            item for item in observations if item.status == "open" and not set(item.required_evidence).issubset(accepted_evidence)
        ]
        missing_tool_items = [
            item for item in observations if item.status == "open" and not set(item.required_tools).issubset(enabled_tools)
        ]
        missing_approval_items = [
            item for item in observations if item.status == "open" and not set(item.required_approvals).issubset(current_approvals)
        ]
        missing_validation_items = [
            item for item in observations if item.status == "open" and not set(item.required_validations).issubset(green_validations)
        ]
        stop_blocked_items = [item for item in observations if item.status == "open" and item.id in active_stop_subjects]
        if missing_decision_items or missing_evidence_items:
            return None, "no open observation is eligible; required decisions or evidence are missing", diagnostics, selection_audit
        if missing_tool_items or missing_approval_items:
            return None, "no open observation is eligible; required tools or approvals are missing", diagnostics, selection_audit
        if missing_validation_items:
            return None, "no open observation is eligible; required validations are missing or not green", diagnostics, selection_audit
        if stop_blocked_items:
            return None, "no open observation is eligible; active stop condition blocks selected work", diagnostics, selection_audit
        if waiting and not any(item.status == "open" for item in observations):
            return None, "no open observation is eligible; queue is waiting on dependencies or checkpoint", diagnostics, selection_audit
        if blocked and not any(item.status == "open" for item in observations):
            return None, "no open observation is eligible; queue head is blocked under current boundary", diagnostics, selection_audit
        return None, "no eligible open observation found", diagnostics, selection_audit

    def _build_selection_audit(
        self,
        observations: tuple[RuntimeObservation, ...],
        *,
        stale_source: bool,
        current_decisions: set[str],
        accepted_evidence: set[str],
        enabled_tools: set[str],
        current_approvals: set[str],
        green_validations: set[str],
        validation_gate_states: dict[str, str],
        active_stop_subjects: set[str],
        active_leases: dict[str, str],
    ) -> RuntimeSelectionAudit:
        # expired_leases intentionally not propagated: expired leases do not block selection entries
        global_blockers = _global_selection_blockers(observations, stale_source, active_stop_subjects, active_leases)
        entries = tuple(
            self._build_selection_audit_entry(
                observation,
                current_decisions=current_decisions,
                accepted_evidence=accepted_evidence,
                enabled_tools=enabled_tools,
                current_approvals=current_approvals,
                green_validations=green_validations,
                validation_gate_states=validation_gate_states,
                active_stop_subjects=active_stop_subjects,
                active_leases=active_leases,
                global_blockers=global_blockers,
            )
            for observation in observations
        )
        eligible_ids = tuple(
            entry.observation_id
            for entry in sorted(entries, key=lambda entry: tuple(int(part) if part.isdigit() else part for part in entry.sort_key))
            if entry.eligible
        )
        decision = "global_blocked" if global_blockers else "no_eligible"
        return RuntimeSelectionAudit(
            policy_version=SELECTION_AUDIT_POLICY_VERSION,
            sort_policy=SELECTION_AUDIT_SORT_POLICY,
            decision=decision,
            selected_id="",
            global_blockers=global_blockers,
            eligible_ids=eligible_ids,
            entries=entries,
        )

    def _build_selection_audit_entry(
        self,
        observation: RuntimeObservation,
        *,
        current_decisions: set[str],
        accepted_evidence: set[str],
        enabled_tools: set[str],
        current_approvals: set[str],
        green_validations: set[str],
        validation_gate_states: dict[str, str],
        active_stop_subjects: set[str],
        active_leases: dict[str, str],
        global_blockers: tuple[str, ...],
    ) -> RuntimeSelectionAuditEntry:
        blockers = list(
            _observation_selection_blockers(
                observation,
                current_decisions=current_decisions,
                accepted_evidence=accepted_evidence,
                enabled_tools=enabled_tools,
                current_approvals=current_approvals,
                green_validations=green_validations,
                validation_gate_states=validation_gate_states,
                active_stop_subjects=active_stop_subjects,
            )
        )
        if active_leases and observation.status == "open" and observation.id not in active_leases:
            blockers.append("active_lease_other_item=" + ",".join(sorted(active_leases)))
        eligible = not global_blockers and not blockers
        priority_rank = PRIORITY_RANK.get(observation.priority, 99)
        sort_key = (f"{priority_rank:03d}", f"{observation.source_index:06d}", observation.id)
        return RuntimeSelectionAuditEntry(
            observation_id=observation.id,
            status=observation.status,
            priority=observation.priority,
            source_index=observation.source_index,
            eligible=eligible,
            sort_key=sort_key,
            blockers=tuple(blockers),
        )

    def _build_gate_diagnostics(
        self,
        observations: tuple[RuntimeObservation, ...],
        *,
        stale_source: bool,
        current_decisions: set[str],
        accepted_evidence: set[str],
        enabled_tools: set[str],
        current_approvals: set[str],
        green_validations: set[str],
        validation_gate_states: dict[str, str],
        active_stop_subjects: set[str],
        active_leases: dict[str, str],
        expired_leases: dict[str, str],
        failed_replay_ids: set[str],
    ) -> tuple[RuntimeGateDiagnostic, ...]:
        diagnostics: list[RuntimeGateDiagnostic] = []
        if stale_source:
            diagnostics.append(_diagnostic("stale_source", "runtime-manager"))
        if expired_leases:
            diagnostics.append(_diagnostic("active_lease_expired", "runtime-manager", sorted(expired_leases)))
        if failed_replay_ids:
            diagnostics.append(_diagnostic("failed_replay_run", "runtime-manager", sorted(failed_replay_ids)))
        if active_leases:
            leased_ids = set(active_leases)
            open_ids = {item.id for item in observations if item.status == "open"}
            non_open_leases = sorted(leased_ids - open_ids)
            if non_open_leases:
                diagnostics.append(_diagnostic("active_lease_non_open", "runtime-manager", non_open_leases))
            else:
                diagnostics.append(_diagnostic("active_lease", "runtime-manager", sorted(leased_ids)))
        runtime_stop_subjects = sorted({"*", "runtime-manager", "runtime-manager-phase-1"} & active_stop_subjects)
        if runtime_stop_subjects:
            diagnostics.append(_diagnostic("active_stop_condition", "runtime-manager", runtime_stop_subjects))
        for observation in observations:
            if observation.status == "waiting":
                diagnostics.append(_diagnostic("waiting_status", observation.id))
            if observation.status == "blocked":
                diagnostics.append(_diagnostic("blocked_status", observation.id))
            if observation.status != "open":
                continue
            if not observation.dependencies_satisfied:
                diagnostics.append(_diagnostic("dependencies_unsatisfied", observation.id, observation.dependencies))
            missing_decisions = sorted(set(observation.required_decisions) - current_decisions)
            if missing_decisions:
                diagnostics.append(_diagnostic("missing_decisions", observation.id, missing_decisions))
            missing_evidence = sorted(set(observation.required_evidence) - accepted_evidence)
            if missing_evidence:
                diagnostics.append(_diagnostic("missing_evidence", observation.id, missing_evidence))
            missing_tools = sorted(set(observation.required_tools) - enabled_tools)
            if missing_tools:
                diagnostics.append(_diagnostic("missing_tools", observation.id, missing_tools))
            missing_approvals = sorted(set(observation.required_approvals) - current_approvals)
            if missing_approvals:
                diagnostics.append(_diagnostic("missing_approvals", observation.id, missing_approvals))
            missing_validations = sorted(set(observation.required_validations) - green_validations)
            if missing_validations:
                diagnostics.append(
                    _diagnostic(
                        "missing_validations",
                        observation.id,
                        [
                            f"{validation_id}:{validation_gate_states.get(validation_id, 'missing')}"
                            for validation_id in missing_validations
                        ],
                    )
                )
            if observation.id in active_stop_subjects:
                diagnostics.append(_diagnostic("active_stop_condition", observation.id))
            if not observation.trigger or observation.trigger == "not open":
                diagnostics.append(_diagnostic("missing_trigger", observation.id))
            if not observation.boundary:
                diagnostics.append(_diagnostic("missing_boundary", observation.id))
        return tuple(diagnostics)

    def _is_stale_source(self, source_sha256: str, observation_center_path: str | Path | None) -> bool:
        if observation_center_path is None:
            return False
        source_path = self._resolve_observation_center_path(observation_center_path)
        if not source_path.exists():
            return True
        return self._sha256(source_path) != source_sha256

    def _sha256(self, path: Path) -> str:
        digest = hashlib.sha256()
        try:
            with path.open("rb") as handle:
                for chunk in iter(lambda: handle.read(65536), b""):
                    digest.update(chunk)
        except OSError as exc:
            raise RuntimeManagerStoreError(f"failed to hash file: {path}") from exc
        return digest.hexdigest()


def _string(value: object) -> str:
    return value if isinstance(value, str) else ""


def _observation_snapshot_payload(observation: RuntimeObservation) -> dict[str, object]:
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
        "source_index": observation.source_index,
    }


def _render_observation_center_toml(metadata: dict[str, str], observations: tuple[RuntimeObservation, ...]) -> str:
    center_version = metadata.get("center_version") or "1"
    try:
        center_version_text = str(int(center_version))
    except ValueError:
        center_version_text = "1"
    single_flight = _metadata_bool(metadata.get("single_flight"), default=True)
    notify_once_blocked = _metadata_bool(metadata.get("notify_once_blocked"), default=False)
    sqlite_primary = metadata.get("center_authority_mode") == CENTER_AUTHORITY_SQLITE_PRIMARY
    projection_role = (
        "runtime.db is the primary observation-center authority; this TOML is a deterministic compatibility export/bootstrap surface."
        if sqlite_primary
        else metadata.get("center_projection_role", "")
    )
    authority_order = (
        "AGENTS.md -> active triggers -> runtime.db -> observation_center.toml -> SYSTEM_STATE.md -> OPPORTUNITY_MAP.md -> active plans -> code/tests"
        if sqlite_primary
        else metadata.get("authority_order", "")
    )
    lines = [
        "[center]",
        f"version = {center_version_text}",
        f"updated_at = {_toml_quote(metadata.get('center_updated_at') or metadata.get('center_promoted_at') or metadata.get('synced_at', ''))}",
        f"queue_authority = {_toml_quote(metadata.get('queue_authority', 'machine-primary'))}",
        f"projection_role = {_toml_quote(projection_role or 'runtime.db is primary; this TOML is a compatibility export.')}",
        f"authority_order = {_toml_quote(authority_order)}",
        f"selection_contract = {_toml_quote(metadata.get('selection_contract', ''))}",
        f"selection_order = {_toml_quote(metadata.get('selection_order', ''))}",
        f"reconciliation_rule = {_toml_quote(metadata.get('reconciliation_rule', ''))}",
        f"single_flight = {str(single_flight).lower()}",
        f"overlap_policy = {_toml_quote(metadata.get('overlap_policy', ''))}",
        f"idempotency_contract = {_toml_quote(metadata.get('idempotency_contract', ''))}",
        f"notify_once_blocked = {str(notify_once_blocked).lower()}",
        f"history_policy = {_toml_quote(metadata.get('history_policy', ''))}",
        f"rotation_policy = {_toml_quote(metadata.get('rotation_policy', ''))}",
        f"checkpoint_policy = {_toml_quote(metadata.get('checkpoint_policy', ''))}",
        "",
        "[projections]",
        f"system_state = {_toml_quote(metadata.get('projection_system_state', ''))}",
        f"opportunity_map = {_toml_quote(metadata.get('projection_opportunity_map', ''))}",
        f"trigger_docs = {_toml_quote(metadata.get('projection_trigger_docs', ''))}",
        "",
    ]
    for observation in sorted(observations, key=lambda item: (item.source_index, item.id)):
        lines.extend(
            [
                "",
                "[[observations]]",
                f"id = {_toml_quote(observation.id)}",
                f"title = {_toml_quote(observation.title)}",
                f"status = {_toml_quote(observation.status)}",
                f"kind = {_toml_quote(observation.kind)}",
                f"priority = {_toml_quote(observation.priority)}",
                f"boundary = {_toml_quote(observation.boundary)}",
                f"trigger = {_toml_quote(observation.trigger)}",
                f"dependencies = {_toml_list(observation.dependencies)}",
                f"dependencies_satisfied = {str(observation.dependencies_satisfied).lower()}",
            ]
        )
        for field_name, values in (
            ("required_decisions", observation.required_decisions),
            ("required_evidence", observation.required_evidence),
            ("required_tools", observation.required_tools),
            ("required_approvals", observation.required_approvals),
            ("required_validations", observation.required_validations),
        ):
            if values:
                lines.append(f"{field_name} = {_toml_list(values)}")
        lines.extend(
            [
                f"next_action = {_toml_quote(observation.next_action)}",
                f"done_when = {_toml_quote(observation.done_when)}",
                f"halt_if = {_toml_quote(observation.halt_if)}",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def _metadata_bool(value: str | None, *, default: bool) -> bool:
    if value is None or value == "":
        return default
    try:
        return bool(json.loads(value))
    except json.JSONDecodeError:
        return default


def _toml_quote(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _toml_list(values: tuple[str, ...]) -> str:
    return "[" + ", ".join(_toml_quote(value) for value in values) + "]"


def _diagnostic(code: str, subject_id: str, details: tuple[str, ...] | list[str] = ()) -> RuntimeGateDiagnostic:
    blocking = code not in INFORMATIONAL_DIAGNOSTIC_CODES
    severity = "blocking" if blocking else "informational"
    return RuntimeGateDiagnostic(
        code=code,
        subject_id=subject_id,
        details=tuple(details),
        severity=severity,
        blocking=blocking,
    )


def _command_action_fingerprint(policy: CommandPolicy) -> str:
    payload = {
        "command_id": policy.command_id,
        "argv_prefix": list(policy.argv_prefix),
        "path_scope": policy.path_scope,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _replace_selection_decision(
    audit: RuntimeSelectionAudit,
    *,
    decision: str,
    selected_id: str,
) -> RuntimeSelectionAudit:
    return RuntimeSelectionAudit(
        policy_version=audit.policy_version,
        sort_policy=audit.sort_policy,
        decision=decision,
        selected_id=selected_id,
        global_blockers=audit.global_blockers,
        eligible_ids=audit.eligible_ids,
        entries=audit.entries,
    )


def _global_selection_blockers(
    observations: tuple[RuntimeObservation, ...],
    stale_source: bool,
    active_stop_subjects: set[str],
    active_leases: dict[str, str],
) -> tuple[str, ...]:
    blockers: list[str] = []
    if stale_source:
        blockers.append("stale_source")
    if active_leases:
        leased_ids = set(active_leases)
        open_ids = {item.id for item in observations if item.status == "open"}
        non_open_leases = sorted(leased_ids - open_ids)
        if non_open_leases:
            blockers.append("active_lease_non_open=" + ",".join(non_open_leases))
    runtime_stop_subjects = sorted({"*", "runtime-manager", "runtime-manager-phase-1"} & active_stop_subjects)
    if runtime_stop_subjects:
        blockers.append("active_stop_condition=" + ",".join(runtime_stop_subjects))
    return tuple(blockers)


def _observation_selection_blockers(
    observation: RuntimeObservation,
    *,
    current_decisions: set[str],
    accepted_evidence: set[str],
    enabled_tools: set[str],
    current_approvals: set[str],
    green_validations: set[str],
    validation_gate_states: dict[str, str],
    active_stop_subjects: set[str],
) -> tuple[str, ...]:
    blockers: list[str] = []
    if observation.status != "open":
        blockers.append(f"status={observation.status}")
        return tuple(blockers)
    if not observation.dependencies_satisfied:
        blockers.append("dependencies_unsatisfied=" + ",".join(observation.dependencies))
    missing_decisions = sorted(set(observation.required_decisions) - current_decisions)
    if missing_decisions:
        blockers.append("missing_decisions=" + ",".join(missing_decisions))
    missing_evidence = sorted(set(observation.required_evidence) - accepted_evidence)
    if missing_evidence:
        blockers.append("missing_evidence=" + ",".join(missing_evidence))
    missing_tools = sorted(set(observation.required_tools) - enabled_tools)
    if missing_tools:
        blockers.append("missing_tools=" + ",".join(missing_tools))
    missing_approvals = sorted(set(observation.required_approvals) - current_approvals)
    if missing_approvals:
        blockers.append("missing_approvals=" + ",".join(missing_approvals))
    missing_validations = sorted(set(observation.required_validations) - green_validations)
    if missing_validations:
        blockers.append(
            "missing_validations="
            + ",".join(
                f"{validation_id}:{validation_gate_states.get(validation_id, 'missing')}"
                for validation_id in missing_validations
            )
        )
    if observation.id in active_stop_subjects:
        blockers.append("active_stop_condition")
    if not observation.trigger or observation.trigger == "not open":
        blockers.append("missing_trigger")
    if not observation.boundary:
        blockers.append("missing_boundary")
    return tuple(blockers)


def _row_to_managed_stop_condition(row: sqlite3.Row) -> ManagedStopCondition:
    return ManagedStopCondition(
        stop_condition_id=row["stop_condition_id"],
        subject_id=row["subject_id"],
        status=row["status"],
        severity=row["severity"],
        opened_at=row["opened_at"],
        resolved_at=row["resolved_at"],
        reason=row["reason"],
        event_id=int(row["event_id"]),
    )


def _row_to_managed_validation(row: sqlite3.Row) -> ManagedValidation:
    return ManagedValidation(
        validation_id=row["validation_id"],
        subject_id=row["subject_id"],
        status=row["status"],
        checked_at=row["checked_at"],
        fresh_until=row["fresh_until"],
        command_id=row["command_id"],
        reason=row["reason"],
        event_id=int(row["event_id"]),
    )


def _row_to_managed_lease(row: sqlite3.Row) -> AcquiredLease:
    return AcquiredLease(
        lease_id=row["lease_id"],
        observation_id=row["observation_id"],
        owner=row["owner"],
        status=row["status"],
        acquired_at=row["acquired_at"],
        expires_at=row["expires_at"],
        renewed_at=row["renewed_at"],
        reason=row["reason"],
        released_at=row["released_at"],
        event_id=int(row["event_id"]),
    )


def _row_to_managed_approval(row: sqlite3.Row) -> ApprovalRecord:
    return ApprovalRecord(
        approval_id=row["approval_id"],
        subject_id=row["subject_id"],
        action_fingerprint=row["action_fingerprint"],
        command_id=row["command_id"],
        actor=row["actor"],
        scope=row["scope"],
        status=row["status"],
        granted_at=row["granted_at"],
        expires_at=row["expires_at"],
        revoked_at=row["revoked_at"],
        event_id=int(row["event_id"]),
    )


def _row_to_evidence(row: sqlite3.Row) -> ExecutionEvidence:
    return ExecutionEvidence(
        evidence_id=int(row["evidence_id"]),
        command_id=row["command_id"],
        observation_id=row["observation_id"],
        approval_id=row["approval_id"],
        action_fingerprint=row["action_fingerprint"],
        rollback_class=row["rollback_class"],
        returncode=int(row["returncode"]),
        timed_out=bool(row["timed_out"]),
        duration_seconds=float(row["duration_seconds"]),
        stdout_digest=row["stdout_digest"],
        stderr_digest=row["stderr_digest"],
        stdout_truncated=bool(row["stdout_truncated"]),
        stderr_truncated=bool(row["stderr_truncated"]),
        output_redacted=bool(row["output_redacted"]),
        event_id=int(row["event_id"]),
        recorded_at=row["recorded_at"],
    )


def _row_to_runtime_trace(row: sqlite3.Row, event_rows: list[sqlite3.Row]) -> RuntimeTrace:
    return RuntimeTrace(
        trace_id=row["trace_id"],
        operation=row["operation"],
        subject_id=row["subject_id"],
        status=row["status"],
        policy_version=row["policy_version"],
        causation_id=row["causation_id"],
        correlation_id=row["correlation_id"],
        input_digest=row["input_digest"],
        output_digest=row["output_digest"],
        started_at=row["started_at"],
        finished_at=row["finished_at"],
        event_count=int(row["event_count"]),
        events=tuple(_row_to_runtime_trace_event(event_row) for event_row in event_rows),
    )


def _row_to_runtime_trace_event(row: sqlite3.Row) -> RuntimeTraceEvent:
    return RuntimeTraceEvent(
        trace_event_id=int(row["trace_event_id"]),
        trace_id=row["trace_id"],
        sequence=int(row["sequence"]),
        event_name=row["event_name"],
        subject_id=row["subject_id"],
        payload_digest=row["payload_digest"],
        payload_json=row["payload_json"],
        created_at=row["created_at"],
    )


def _diagnostic_payload(diagnostic: RuntimeGateDiagnostic) -> dict[str, object]:
    return {
        "code": diagnostic.code,
        "subject_id": diagnostic.subject_id,
        "details": list(diagnostic.details),
        "severity": diagnostic.severity,
        "blocking": diagnostic.blocking,
    }


def _trace_payload(trace: RuntimeTrace) -> dict[str, object]:
    return {
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
        "events": [_trace_event_payload(event) for event in trace.events],
        "trace_is_not_permission": True,
    }


def _trace_event_payload(event: RuntimeTraceEvent) -> dict[str, object]:
    return {
        "trace_event_id": event.trace_event_id,
        "trace_id": event.trace_id,
        "sequence": event.sequence,
        "event_name": event.event_name,
        "subject_id": event.subject_id,
        "payload_digest": event.payload_digest,
        "payload": json.loads(event.payload_json),
        "created_at": event.created_at,
    }


def _trace_to_otel_projection(trace: RuntimeTrace) -> dict[str, object]:
    return {
        "resourceSpans": [
            {
                "resource": {
                    "attributes": [
                        {"key": "service.name", "value": {"stringValue": "cerebro-runtime-manager"}},
                        {"key": "cerebro.runtime.trace_is_not_permission", "value": {"boolValue": True}},
                    ]
                },
                "scopeSpans": [
                    {
                        "scope": {"name": "cerebro.runtime_manager"},
                        "spans": [
                            {
                                "traceId": trace.trace_id.replace("rt-", "")[:32].ljust(32, "0"),
                                "spanId": hashlib.sha256(trace.trace_id.encode()).hexdigest()[:16],
                                "name": f"runtime-manager.{trace.operation}",
                                "kind": "SPAN_KIND_INTERNAL",
                                "attributes": [
                                    {"key": "cerebro.runtime.operation", "value": {"stringValue": trace.operation}},
                                    {"key": "cerebro.runtime.subject_id", "value": {"stringValue": trace.subject_id}},
                                    {"key": "cerebro.runtime.status", "value": {"stringValue": trace.status}},
                                    {"key": "cerebro.runtime.policy_version", "value": {"stringValue": trace.policy_version}},
                                    {"key": "cerebro.runtime.trace_is_not_permission", "value": {"boolValue": True}},
                                    {"key": "otel.compat.exported", "value": {"boolValue": False}},
                                ],
                                "events": [
                                    {
                                        "name": event.event_name,
                                        "attributes": [
                                            {"key": "cerebro.runtime.event_digest", "value": {"stringValue": event.payload_digest}},
                                            {"key": "cerebro.runtime.sequence", "value": {"intValue": event.sequence}},
                                        ],
                                    }
                                    for event in trace.events
                                ],
                            }
                        ],
                    }
                ],
            }
        ],
        "projection_is_not_opentelemetry_export": True,
        "telemetry_is_not_permission": True,
    }


def _metrics_payload(metrics: RuntimeManagerMetrics) -> dict[str, int | str]:
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


def _stop_condition_payload(condition: ManagedStopCondition) -> dict[str, object]:
    return {
        "stop_condition_id": condition.stop_condition_id,
        "subject_id": condition.subject_id,
        "status": condition.status,
        "severity": condition.severity,
        "opened_at": condition.opened_at,
        "resolved_at": condition.resolved_at,
        "reason": condition.reason,
        "event_id": condition.event_id,
    }


def _validation_payload(validation: ManagedValidation) -> dict[str, object]:
    return {
        "validation_id": validation.validation_id,
        "subject_id": validation.subject_id,
        "status": validation.status,
        "checked_at": validation.checked_at,
        "fresh_until": validation.fresh_until,
        "command_id": validation.command_id,
        "reason": validation.reason,
        "event_id": validation.event_id,
    }


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


def _approval_payload(approval: ApprovalRecord) -> dict[str, object]:
    return {
        "approval_id": approval.approval_id,
        "subject_id": approval.subject_id,
        "command_id": approval.command_id,
        "action_fingerprint": approval.action_fingerprint,
        "actor": approval.actor,
        "scope": approval.scope,
        "status": approval.status,
        "granted_at": approval.granted_at,
        "expires_at": approval.expires_at,
        "revoked_at": approval.revoked_at,
        "event_id": approval.event_id,
    }


def _stable_payload_digest(payload: object) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _sanitize_trace_payload(value: object) -> object:
    sensitive_keys = ("secret", "token", "password", "credential", "stdout", "stderr", "raw_output", "output")
    if isinstance(value, dict):
        sanitized: dict[str, object] = {}
        for key, item in value.items():
            key_text = str(key)
            if any(marker in key_text.lower() for marker in sensitive_keys):
                sanitized[key_text] = "[REDACTED]"
            else:
                sanitized[key_text] = _sanitize_trace_payload(item)
        return sanitized
    if isinstance(value, (list, tuple)):
        return [_sanitize_trace_payload(item) for item in value]
    if isinstance(value, str):
        lowered = value.lower()
        if any(marker in lowered for marker in ("secret=", "token=", "password=", "credential=")):
            return "[REDACTED]"
        if len(value) > 512:
            return value[:512] + "[TRUNCATED]"
    return value


def _optional_string(value: object) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text if text else None


def _relative_or_absolute(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path.resolve())


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _utc_before_seconds(seconds: int) -> str:
    """Return an ISO-8601 UTC timestamp that is `seconds` before now."""
    from datetime import timedelta
    return (datetime.now(timezone.utc) - timedelta(seconds=seconds)).isoformat(timespec="seconds")


def _utc_future(base_iso: str, seconds: int) -> str:
    """Return an ISO-8601 UTC timestamp that is `seconds` after base_iso."""
    from datetime import timedelta
    base = datetime.fromisoformat(base_iso.replace("Z", "+00:00"))
    if base.tzinfo is None:
        base = base.replace(tzinfo=timezone.utc)
    return (base + timedelta(seconds=seconds)).isoformat(timespec="seconds")


def _fresh_until_is_current(fresh_until: str, checked_at: str) -> bool:
    if not fresh_until:
        return False
    try:
        fresh_until_dt = datetime.fromisoformat(fresh_until.replace("Z", "+00:00"))
        checked_at_dt = datetime.fromisoformat(checked_at.replace("Z", "+00:00"))
        if fresh_until_dt.tzinfo is None:
            fresh_until_dt = fresh_until_dt.replace(tzinfo=timezone.utc)
        if checked_at_dt.tzinfo is None:
            checked_at_dt = checked_at_dt.replace(tzinfo=timezone.utc)
    except ValueError:
        return False
    return fresh_until_dt >= checked_at_dt


def _lease_expires_at_is_current(expires_at: str, checked_at: str) -> bool:
    """Return True when the lease has NOT yet expired (conservative: empty or malformed counts as still active).

    Rules:
    - empty/blank expires_at  → True  (no expiry declared; conservatively still active)
    - malformed timestamp     → True  (conservatively still active; fail open for leases)
    - future timestamp        → True  (lease still valid)
    - past timestamp          → False (lease has expired; does not block single-flight selection)
    """
    if not expires_at:
        return True
    try:
        expires_at_dt = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
        checked_at_dt = datetime.fromisoformat(checked_at.replace("Z", "+00:00"))
        if expires_at_dt.tzinfo is None:
            expires_at_dt = expires_at_dt.replace(tzinfo=timezone.utc)
        if checked_at_dt.tzinfo is None:
            checked_at_dt = checked_at_dt.replace(tzinfo=timezone.utc)
    except ValueError:
        return True
    return expires_at_dt >= checked_at_dt
