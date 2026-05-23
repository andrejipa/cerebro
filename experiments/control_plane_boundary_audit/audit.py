from __future__ import annotations

import ast
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable


class ControlPlaneBoundaryAuditError(ValueError):
    """Raised when a boundary audit input cannot be evaluated safely."""


CONTROL_PLANE_BOUNDARY_PACKAGES = (
    "capability_policy",
    "control_plane_assessment",
    "control_plane_trace",
    "control_plane_event_ledger",
    "control_plane_replay_eval",
    "control_plane_review_packet",
    "control_plane_review_matrix",
    "control_plane_scenario_lab",
    "control_plane_telemetry_projection",
    "control_plane_guardrail_eval",
    "control_plane_lineage_invariant_eval",
    "control_plane_integrity_review",
    "control_plane_action_review",
    "control_plane_observation_set_review",
    "control_plane_observation_transition_review",
    "control_plane_handoff_review",
    "control_plane_decision_version_review",
    "control_plane_rule_promotion_review",
    "control_plane_runtime_adoption_review",
    "control_plane_runtime_state_review",
    "control_plane_runtime_contract_review",
    "control_plane_runtime_state_transition_review",
    "control_plane_tool_manifest_review",
    "control_plane_evidence_policy_review",
    "control_plane_work_queue_review",
    "control_plane_approval_policy_review",
    "control_plane_adversarial_posture_review",
    "control_plane_cross_review_consistency_eval",
    "control_plane_loop_stop_eval",
)


@dataclass(frozen=True)
class ControlPlaneBoundarySource:
    package_name: str
    relative_path: str
    text: str


@dataclass(frozen=True)
class ControlPlaneBoundaryAuditFinding:
    code: str
    severity: str
    package_name: str
    relative_path: str
    detail: str


@dataclass(frozen=True)
class ControlPlaneBoundaryAuditReport:
    schema_version: str
    audit_role: str
    package_count: int
    source_count: int
    audit_status: str
    finding_count: int
    severity_counts: dict[str, int]
    package_counts: dict[str, int]
    finding_codes: tuple[str, ...]
    findings: tuple[ControlPlaneBoundaryAuditFinding, ...]
    audited_packages: tuple[str, ...]
    state_change: str = "none"
    authority: str = "non-authoritative; advisory control-plane boundary audit only"
    audit_is_not_permission: bool = True
    finding_is_not_truth: bool = True
    audit_pass_is_not_execution_approval: bool = True
    must_not_execute_automatically: bool = True


_FORBIDDEN_IMPORT_PREFIXES = (
    "opentelemetry",
    "requests",
    "socket",
    "subprocess",
    "urllib",
    "http",
    "temporalio",
    "langgraph",
    "openai",
)

_FORBIDDEN_MODULE_REFERENCES = (
    "cli.",
    "extensions.",
)

_FORBIDDEN_CALL_NAMES = {
    "eval",
    "exec",
    "open",
}

_FORBIDDEN_ATTRIBUTE_CALLS = {
    "open",
    "remove",
    "rename",
    "rmdir",
    "rmtree",
    "send",
    "unlink",
    "write",
    "write_bytes",
    "write_text",
}

_FORBIDDEN_RUNTIME_TOKENS = (
    "mcp",
    "agents sdk",
    "otlp",
    "opentelemetry exporter",
    "temporal workflow",
    "langgraph graph",
)

_PERMISSION_LAUNDERING_TOKENS = (
    "execution_approved",
    "execution approval",
    "grants permission",
    "permission to execute",
    "permission_granted",
    "runtime_authority",
    "runtime authority",
    "canonical gate",
    "canonical_truth",
    "truth signal",
    "scheduler",
    "schedules work",
    "handoff approved",
    "handoff grants permission",
    "handoff schedules work",
    "handoff selected next action",
    "handoff is truth",
    "decision approved",
    "decision grants permission",
    "decision selected next action",
    "decision is truth",
    "promotion approved",
    "promotion grants permission",
    "promotion is truth",
    "rule promoted",
    "promotes rule",
    "rule is active",
    "activate rule",
    "applies rule",
    "enforce rule",
    "rule version is truth",
    "rule_version_is_truth",
    "rule supersession is truth",
    "supersession approved",
    "supersession grants permission",
    "supersession selected next action",
    "current rule is truth",
    "latest rule is truth",
    "rule store",
    "rule_store",
    "canonical rule store",
    "canonical_rule_store",
    "runtime adoption approved",
    "technology selected next action",
    "adapter grants permission",
    "adapter approved",
    "mcp grants permission",
    "mcp server is authority",
    "temporal workflow is truth",
    "langgraph graph is truth",
    "opentelemetry exporter is truth",
    "otel trace is truth",
    "agent handoff grants permission",
    "canonical state",
    "canonical_state",
    "state is truth",
    "state_is_truth",
    "runtime state is truth",
    "state store is truth",
    "snapshot is truth",
    "snapshot selected next action",
    "next action selected",
    "source of truth",
    "queue reader",
    "permission layer",
    "canonical runtime contract",
    "canonical_contract",
    "contract is truth",
    "contract_is_truth",
    "contract grants permission",
    "contract selected next action",
    "runtime state transition is truth",
    "state transition is truth",
    "transition is canonical state",
    "transition_is_truth",
    "transition grants permission",
    "transition approved",
    "transition selected next action",
    "transition schedules work",
    "transition applied",
    "applies transition",
    "commit transition",
    "state transition committed",
    "promote state",
    "promotes state",
    "after snapshot is truth",
    "before snapshot is truth",
    "next state is truth",
    "transition result is truth",
    "transition result is state store",
    "runtime state transition approved",
    "runtime state transition grants permission",
    "tool manifest is authority",
    "tool_manifest_is_authority",
    "tool manifest grants permission",
    "tool_manifest_grants_permission",
    "tool manifest approved",
    "approved tool manifest",
    "tool manifest selected next action",
    "tool manifest schedules work",
    "tool manifest is truth",
    "tool_manifest_is_truth",
    "canonical tool manifest",
    "canonical_tool_manifest",
    "canonical tool registry",
    "canonical_tool_registry",
    "tool registry is truth",
    "tool_registry_is_truth",
    "tool registry grants permission",
    "tool authority",
    "tool_authority",
    "tool call approved",
    "tool_call_approved",
    "tool call grants permission",
    "tool execution approved",
    "tool execution approval",
    "tool execution permission",
    "tool enabled",
    "auto invoke tool",
    "auto-invoke tool",
    "invoke tool automatically",
    "tool may run",
    "tool may execute",
    "allowed to call tool",
    "allowed_tool_call",
    "tool bridge approved",
    "tool bridge grants permission",
    "mcp tool approved",
    "mcp tool grants permission",
    "function call approved",
    "function call grants permission",
    "tool schema is authority",
    "tool schema grants permission",
    "manifest entry grants permission",
    "capability grants permission",
    "capability is runtime authority",
    "declared tool is executable",
    "registered tool is executable",
    "tool registration is authority",
    "tool registration grants permission",
    "evidence is truth",
    "evidence_is_truth",
    "evidence grants truth",
    "evidence establishes truth",
    "evidence proves canonical truth",
    "policy finding is truth",
    "evidence score is truth",
    "sufficiency score is truth",
    "verified evidence is canonical",
    "evidence packet is canonical",
    "evidence bundle is truth",
    "evidence policy is authority",
    "canonical evidence policy",
    "canonical_evidence_policy",
    "evidence source of truth",
    "source evidence is truth",
    "absence of evidence proves absence",
    "silence proves absence",
    "silence is negative evidence",
    "evidence grants permission",
    "evidence_grants_permission",
    "evidence approval",
    "evidence approved execution",
    "evidence permits execution",
    "evidence policy grants permission",
    "policy grants permission",
    "sufficiency grants permission",
    "sufficient evidence grants permission",
    "permission from evidence",
    "evidence gate passed",
    "evidence gate grants execution",
    "evidence review approved",
    "evidence review selected next action",
    "policy selected next action",
    "approval is sufficient evidence",
    "approval proves evidence",
    "approval grants truth",
    "human decision is evidence",
    "decision proves truth",
    "decision grants evidence sufficiency",
    "approval presence is permission",
    "retain raw evidence",
    "retains raw evidence",
    "store raw evidence",
    "stores raw evidence",
    "raw tool output retained",
    "retain secrets",
    "retains secrets",
    "secret retention",
    "stores secret material",
    "secret evidence is retained",
    "raw secret output",
    "sensitive output retained",
    "token retained",
    "api key retained",
    "credential retained",
    "env secret retained",
    "unredacted output",
    "unredacted evidence",
    "persist secret",
    "persist raw output",
    "memory writes evidence",
    "writes evidence memory",
    "evidence policy is runtime authority",
    "policy is runtime authority",
    "runtime evidence gate",
    "canonical runtime evidence",
    "evidence state store",
    "evidence store is truth",
    "evidence registry is truth",
    "registers evidence",
    "register evidence automatically",
    "updates evidence store",
    "mutates evidence state",
    "applies evidence policy",
    "enforces evidence policy",
    "policy schedules work",
    "policy is scheduler",
    "evidence queue reader",
    "work queue is truth",
    "work_queue_is_truth",
    "queue is truth",
    "queue_is_truth",
    "canonical work queue",
    "canonical_work_queue",
    "work queue source of truth",
    "queue source of truth",
    "work queue grants permission",
    "queue grants permission",
    "work queue selected next action",
    "queue selected next action",
    "queue selected work",
    "work queue selected work",
    "priority is truth",
    "priority_is_truth",
    "priority score is truth",
    "priority_score_is_truth",
    "priority grants permission",
    "priority selected next action",
    "priority selected work",
    "priority order is canonical",
    "canonical priority order",
    "dependencies satisfied is truth",
    "dependencies_satisfied_is_truth",
    "dependency satisfaction is truth",
    "dependency_satisfaction_is_truth",
    "dependency satisfaction grants permission",
    "dependencies satisfied grants permission",
    "dependencies satisfied selected next action",
    "ready to run",
    "ready-to-run",
    "ready_to_run",
    "ready work grants permission",
    "ready item grants permission",
    "ready item selected next action",
    "ready work selected next action",
    "runnable work is truth",
    "runnable_work_is_truth",
    "owner assignment is truth",
    "owner_assignment_is_truth",
    "owner assignment grants permission",
    "owner assigned work",
    "assigns owner automatically",
    "auto assigns owner",
    "auto-assigns owner",
    "claim owner automatically",
    "owner claim grants permission",
    "auto dispatch",
    "auto-dispatch",
    "auto_dispatch",
    "dispatch automatically",
    "automatically dispatch",
    "automatic dispatch",
    "auto dispatches work",
    "dispatch grants permission",
    "dispatch selected next action",
    "work queue schedules work",
    "queue schedules work",
    "queue is scheduler",
    "work queue is scheduler",
    "state reader is authority",
    "state_reader_is_authority",
    "store reader is authority",
    "store_reader_is_authority",
    "queue reader is authority",
    "queue_reader_is_authority",
    "reader is authority",
    "reader_is_authority",
    "state store selected next action",
    "store selected next action",
    "reader selected next action",
    "reader grants permission",
    "store grants permission",
    "state store grants permission",
    "approval policy is authority",
    "approval_policy_is_authority",
    "canonical approval policy",
    "canonical_approval_policy",
    "approval policy grants permission",
    "approval_policy_grants_permission",
    "approval policy grants execution",
    "approval policy approved execution",
    "approval record is truth",
    "approval_record_is_truth",
    "approval status is truth",
    "approval_status_is_truth",
    "approval status grants permission",
    "approved status grants permission",
    "approved approval grants permission",
    "approval grants execution",
    "approval grants permission",
    "approval selected next action",
    "approval schedules work",
    "approval is reusable",
    "approval_reuse_allowed",
    "reuse approval automatically",
    "reused approval grants permission",
    "stale approval grants permission",
    "expired approval grants permission",
    "approval expiration is advisory",
    "approval never expires",
    "approval ttl grants permission",
    "approval scope grants permission",
    "scope match grants permission",
    "scope wildcard grants permission",
    "approval covers all scopes",
    "approval covers any target",
    "fingerprint match grants permission",
    "fingerprint is optional",
    "missing fingerprint allowed",
    "approval fingerprint is advisory",
    "approval fingerprint grants permission",
    "fingerprint reuse allowed",
    "approval target mismatch allowed",
    "approval task mismatch allowed",
    "approval kind mismatch allowed",
    "approval applies across tasks",
    "approval applies across targets",
    "approval applies across action kinds",
)

_FORBIDDEN_QUEUE_READ_TOKENS = (
    "observation_center.toml",
    "docs/operations/observation_center",
    ".cerebro/state.json",
    "state.json",
    "session.local.json",
    "events.jsonl",
    "statestore",
    "load_state",
    "save_state",
    "validate_state",
    "open_session",
    "close_session",
    "runtime_lock",
    "tools.json",
    "tool_manifest.json",
    "tool_registry.json",
    "mcp.json",
    "server_tools",
    "available_tools",
    "registered_tools",
    "load_tools",
    "register_tool",
    "register_tools",
    "invoke_tool",
    "call_tool",
    "execute_tool",
    "dispatch_tool",
    "tool_router",
    "work_queue.json",
    "work-queue.json",
    "queue.json",
    "ready_queue.json",
    "ready-queue.json",
    "priority_queue.json",
    "priority-queue.json",
    "owner_assignments.json",
    "owner-assignment.json",
    "owner_claims.json",
    "dispatch_queue.json",
    "dispatch-queue.json",
    "work_queue_reader",
    "ready_queue_reader",
    "priority_queue_reader",
    "dispatch_queue_reader",
    "load_work_queue",
    "read_work_queue",
    "save_work_queue",
    "update_work_queue",
    "dispatch_work",
    "assign_owner",
    "claim_owner",
    "approval_store.json",
    "approval-store.json",
    "approvals.json",
    "approval_policy.json",
    "approval-policy.json",
    "approval_registry.json",
    "approval-registry.json",
    "approval_reader",
    "approval_policy_reader",
    "load_approvals",
    "load_approval_policy",
    "read_approvals",
    "read_approval_policy",
    "save_approvals",
    "save_approval_policy",
    "register_approval",
    "approve_execution",
)

_NEGATIVE_MARKERS = (
    "_is_not_",
    "not_",
    "non-authoritative",
    "non_authoritative",
    "does not",
    "do not",
    "are not",
    "is not",
    "not a",
    "not an",
    "not execution approval",
    "not permission",
    "non-permission",
    "never",
    "must not",
    "before any",
    "without",
    "fingerprint must match",
)


def _count(values: Iterable[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


def _finding(
    code: str,
    severity: str,
    source: ControlPlaneBoundarySource,
    detail: str,
) -> ControlPlaneBoundaryAuditFinding:
    return ControlPlaneBoundaryAuditFinding(
        code=code,
        severity=severity,
        package_name=source.package_name,
        relative_path=source.relative_path,
        detail=detail,
    )


def _validate_source(source: ControlPlaneBoundarySource) -> None:
    if source.package_name not in CONTROL_PLANE_BOUNDARY_PACKAGES:
        raise ControlPlaneBoundaryAuditError(f"unexpected control-plane package: {source.package_name}")
    if not source.relative_path or "\\" in source.relative_path:
        raise ControlPlaneBoundaryAuditError("relative_path must be a slash-separated relative path")
    if source.relative_path.startswith("/") or ".." in Path(source.relative_path).parts:
        raise ControlPlaneBoundaryAuditError("relative_path must not escape the package root")


def collect_control_plane_boundary_sources(
    experiments_root: Path,
    *,
    package_names: Iterable[str] = CONTROL_PLANE_BOUNDARY_PACKAGES,
) -> tuple[ControlPlaneBoundarySource, ...]:
    """Collect bounded source text for advisory Control Plane boundary audit."""

    root = experiments_root.resolve()
    if root.name != "experiments":
        raise ControlPlaneBoundaryAuditError("experiments_root must point to the experiments directory")

    sources: list[ControlPlaneBoundarySource] = []
    for package_name in tuple(package_names):
        if package_name not in CONTROL_PLANE_BOUNDARY_PACKAGES:
            raise ControlPlaneBoundaryAuditError(f"unexpected control-plane package: {package_name}")
        package_root = (root / package_name).resolve()
        if root not in package_root.parents:
            raise ControlPlaneBoundaryAuditError("package root escaped experiments directory")
        if not package_root.is_dir():
            raise ControlPlaneBoundaryAuditError(f"missing package directory: {package_name}")
        for path in sorted(package_root.rglob("*")):
            if path.name.startswith(".") or path.name == "__pycache__":
                continue
            if path.is_dir():
                continue
            if "__pycache__" in path.parts or "tests" in path.relative_to(package_root).parts:
                continue
            if path.suffix not in {".py", ".md"}:
                continue
            relative_path = path.relative_to(package_root).as_posix()
            sources.append(
                ControlPlaneBoundarySource(
                    package_name=package_name,
                    relative_path=relative_path,
                    text=path.read_text(encoding="utf-8"),
                )
            )
    return tuple(sources)


def _import_findings(source: ControlPlaneBoundarySource) -> tuple[ControlPlaneBoundaryAuditFinding, ...]:
    if not source.relative_path.endswith(".py"):
        return ()
    try:
        tree = ast.parse(source.text, filename=source.relative_path)
    except SyntaxError as exc:
        return (_finding("python_parse_error", "critical", source, str(exc)),)

    findings: list[ControlPlaneBoundaryAuditFinding] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                name = alias.name
                if name.startswith(_FORBIDDEN_IMPORT_PREFIXES):
                    findings.append(_finding("forbidden_import_surface", "critical", source, name))
                if name == "cli" or name == "extensions" or name.startswith(_FORBIDDEN_MODULE_REFERENCES):
                    findings.append(_finding("forbidden_runtime_surface_import", "high", source, name))
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module.startswith(_FORBIDDEN_IMPORT_PREFIXES):
                findings.append(_finding("forbidden_import_surface", "critical", source, module))
            if module.startswith(_FORBIDDEN_MODULE_REFERENCES):
                findings.append(_finding("forbidden_runtime_surface_import", "high", source, module))
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in _FORBIDDEN_CALL_NAMES:
            findings.append(_finding("forbidden_dynamic_or_file_call", "high", source, node.func.id))
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr in _FORBIDDEN_ATTRIBUTE_CALLS:
                findings.append(_finding("forbidden_mutating_or_io_call", "high", source, node.func.attr))
    return tuple(findings)


def _text_findings(source: ControlPlaneBoundarySource) -> tuple[ControlPlaneBoundaryAuditFinding, ...]:
    findings: list[ControlPlaneBoundaryAuditFinding] = []
    if source.relative_path.endswith(".md"):
        paragraphs = [paragraph.replace("\n", " ") for paragraph in re.split(r"\n\s*\n", source.text)]
        segments = [
            sentence
            for paragraph in paragraphs
            for sentence in re.split(r"(?<=[.!?])\s+", paragraph)
            if sentence.strip()
        ]
    else:
        segments = source.text.splitlines()

    for raw_segment in segments:
        stripped_segment = raw_segment.strip()
        if stripped_segment.startswith(("'", '"')) and stripped_segment.endswith((",", ")")):
            continue
        segment = raw_segment.lower()
        if (
            "_forbidden" in segment
            or "expected_finding_codes" in segment
            or "_requires_" in segment
            or "requires_" in segment
            or "requests_" in segment
            or "claims_" in segment
            or "enables_" in segment
            or " claimed " in segment
            or "proposal.runtime_family" in segment
            or "_runtime_boundaries" in segment
            or "_high_control_surfaces" in segment
            or "_manifest_scopes" in segment
            or "_tool_kinds" in segment
            or "exposes_mcp_server" in segment
            or "launders_tool_authority" in segment
            or "launders_authority" in segment
            or "_forbidden_authority_tokens" in segment
            or "claims_evidence_authority" in segment
            or "grants_permission" in segment
            or "accepted_evidence_is_not_truth" in segment
            or "evidence_record_is_not_truth" in segment
            or "silence_is_not_negative_evidence" in segment
            or "approval_presence_is_not_sufficient_evidence" in segment
            or "secret_material_must_not_be_retained" in segment
            or "raw_tool_output_must_not_be_retained" in segment
            or "claims_queue_authority" in segment
            or "claims_scheduler_authority" in segment
            or "claims_priority_truth" in segment
            or "auto_dispatch" in segment
            or "registers_queue_reader" in segment
            or "work_queue_review_is_not_permission" in segment
            or "work_queue_review_is_not_scheduler" in segment
            or "queue_priority_is_not_truth" in segment
            or "dependency_status_is_not_truth" in segment
            or "ready_status_is_not_execution_approval" in segment
            or "work_queue_review_is_not_queue_reader" in segment
            or "work_queue_review_is_not_state_store" in segment
            or "claims_approval_authority" in segment
            or "grants_execution_permission" in segment
            or "acts_as_permission_layer" in segment
            or "registers_approval_store" in segment
            or "reads_live_approval_store" in segment
            or "schedules_work" in segment
            or "selects_next_action" in segment
            or "approval_policy_review_is_not_permission" in segment
            or "approval_policy_review_is_not_approval_store" in segment
            or "approval_status_is_not_execution_approval" in segment
            or "approval_presence_is_not_sufficient_evidence" in segment
            or "approval_policy_review_is_not_scheduler" in segment
            or "approval_policy_review_is_not_runtime_gate" in segment
            or "approval_policy_review_is_not_state_store" in segment
            or "posture_review_is_not_permission" in segment
            or "posture_review_is_not_runtime_gate" in segment
            or "posture_status_is_not_truth" in segment
            or "posture_review_is_not_scheduler" in segment
            or "posture_review_is_not_state_store" in segment
            or "posture_review_is_not_approval" in segment
            or "subject_text_launders_authority" in segment
            or "subject_status_launders_authority" in segment
            or "expected_blocker_disappeared" in segment
            or "blocking_status_without_evidence" in segment
            or "consistency_eval_is_not_permission" in segment
            or "consistency_status_is_not_truth" in segment
            or "consistency_eval_is_not_execution_approval" in segment
            or "consistency_eval_is_not_scheduler" in segment
            or "consistency_eval_is_not_runtime_gate" in segment
            or "consistency_eval_is_not_state_store" in segment
            or "action_clean_over_integrity_drift" in segment
            or "ready_subject_over_blocked_dependency" in segment
            or "allowed_tool_over_blocked_dependency" in segment
            or "active_candidate_over_blocked_dependency" in segment
            or "shared_identity_replay_digest_conflict" in segment
            or "loop_stop_eval_is_not_permission" in segment
            or "loop_stop_status_is_not_truth" in segment
            or "loop_stop_eval_is_not_execution_approval" in segment
            or "loop_stop_eval_is_not_scheduler" in segment
            or "loop_stop_eval_is_not_runtime_gate" in segment
            or "loop_stop_eval_is_not_state_store" in segment
            or "claims_scheduler_authority" in segment
            or "grants_execution_permission" in segment
            or "loop_authority_text_laundering" in segment
            or "continue_without_active_trigger" in segment
            or "continue_over_non_open_queue_head" in segment
            or "continue_with_unsatisfied_dependencies" in segment
            or "single_flight_frontier_drift" in segment
            or "single_flight_ready_drift" in segment
            or "auto_continue_requested" in segment
            or "open_runtime_authority_trigger" in segment
            or 'rows[1]["authority"] = "runtime authority"' in segment
        ):
            continue
        if source.package_name == "control_plane_guardrail_eval" and source.relative_path == "evaluator.py":
            continue
        has_local_negative_marker = any(marker in segment for marker in _NEGATIVE_MARKERS)
        for token in _FORBIDDEN_RUNTIME_TOKENS:
            if token in segment and not has_local_negative_marker:
                findings.append(_finding("adapter_or_runtime_laundering_text", "high", source, token))

        for token in _PERMISSION_LAUNDERING_TOKENS:
            if token in segment and not has_local_negative_marker:
                findings.append(_finding("permission_laundering_text", "high", source, token))

        for token in _FORBIDDEN_QUEUE_READ_TOKENS:
            if token in segment and not has_local_negative_marker:
                findings.append(_finding("forbidden_observation_center_read_text", "high", source, token))

    return tuple(findings)


def _package_marker_findings(sources: tuple[ControlPlaneBoundarySource, ...]) -> tuple[ControlPlaneBoundaryAuditFinding, ...]:
    by_package: dict[str, list[ControlPlaneBoundarySource]] = {}
    for source in sources:
        by_package.setdefault(source.package_name, []).append(source)

    findings: list[ControlPlaneBoundaryAuditFinding] = []
    for package_name, package_sources in sorted(by_package.items()):
        text = "\n".join(source.text.lower() for source in package_sources)
        marker_source = next(
            (source for source in package_sources if source.relative_path.lower() == "readme.md"),
            package_sources[0],
        )
        if "state_change" not in text:
            findings.append(
                _finding("state_change_marker_missing", "medium", marker_source, f"{package_name} missing state_change marker")
            )
        if "non-authoritative" not in text:
            findings.append(
                _finding(
                    "non_authority_marker_missing",
                    "medium",
                    marker_source,
                    f"{package_name} missing non-authoritative marker",
                )
            )
        if "must_not_execute" not in text and "must not execute" not in text:
            findings.append(
                _finding(
                    "no_auto_execution_marker_missing",
                    "medium",
                    marker_source,
                    f"{package_name} missing no-auto-execute marker",
                )
            )
    return tuple(findings)


def _validate_report(report: ControlPlaneBoundaryAuditReport) -> None:
    if report.state_change != "none" or "non-authoritative" not in report.authority:
        raise ControlPlaneBoundaryAuditError("report must be non-authoritative with state_change none")
    if (
        not report.audit_is_not_permission
        or not report.finding_is_not_truth
        or not report.audit_pass_is_not_execution_approval
        or not report.must_not_execute_automatically
    ):
        raise ControlPlaneBoundaryAuditError("report guardrails must remain true")
    if report.finding_count != len(report.findings):
        raise ControlPlaneBoundaryAuditError("finding_count must match findings")


def audit_control_plane_boundary_sources(
    sources: Iterable[ControlPlaneBoundarySource],
) -> ControlPlaneBoundaryAuditReport:
    """Audit declared Control Plane package sources for cross-layer boundary drift."""

    source_items = tuple(sources)
    if not source_items:
        raise ControlPlaneBoundaryAuditError("boundary audit requires at least one source")
    for source in source_items:
        _validate_source(source)

    audited_packages = tuple(sorted({source.package_name for source in source_items}))
    findings: list[ControlPlaneBoundaryAuditFinding] = []
    findings.extend(_package_marker_findings(source_items))
    for source in source_items:
        findings.extend(_import_findings(source))
        findings.extend(_text_findings(source))

    finding_items = tuple(findings)
    report = ControlPlaneBoundaryAuditReport(
        schema_version="1",
        audit_role="audits_control_plane_experiment_boundary_drift",
        package_count=len(audited_packages),
        source_count=len(source_items),
        audit_status="boundary_drift_observed" if finding_items else "boundary_markers_preserved",
        finding_count=len(finding_items),
        severity_counts=_count(finding.severity for finding in finding_items),
        package_counts=_count(finding.package_name for finding in finding_items),
        finding_codes=tuple(finding.code for finding in finding_items),
        findings=finding_items,
        audited_packages=audited_packages,
    )
    _validate_report(report)
    return report


def audit_control_plane_boundary_tree(experiments_root: Path) -> ControlPlaneBoundaryAuditReport:
    return audit_control_plane_boundary_sources(collect_control_plane_boundary_sources(experiments_root))


def render_control_plane_boundary_audit_json(report: ControlPlaneBoundaryAuditReport) -> str:
    _validate_report(report)
    payload = asdict(report)
    payload["state_change"] = "none"
    payload["authority"] = report.authority
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def render_control_plane_boundary_audit_markdown(report: ControlPlaneBoundaryAuditReport) -> str:
    _validate_report(report)
    lines = [
        "# Control Plane Boundary Audit",
        "",
        "- state_change: none",
        "- authority: non-authoritative; advisory control-plane boundary audit only",
        "- audit_is_not_permission: true",
        "- finding_is_not_truth: true",
        "- audit_pass_is_not_execution_approval: true",
        "- must_not_execute_automatically: true",
        "",
        "## Summary",
        "",
        f"- audit_role: {report.audit_role}",
        f"- audit_status: {report.audit_status}",
        f"- package_count: {report.package_count}",
        f"- source_count: {report.source_count}",
        f"- finding_count: {report.finding_count}",
        f"- severity_counts: {report.severity_counts}",
        f"- package_counts: {report.package_counts}",
        "",
        "## Findings",
        "",
    ]
    if not report.findings:
        lines.append("- none")
    else:
        for finding in report.findings:
            lines.append(
                f"- {finding.severity}:{finding.package_name}:{finding.code} "
                f"at {finding.relative_path} - {finding.detail}"
            )
    return "\n".join(lines).rstrip() + "\n"
