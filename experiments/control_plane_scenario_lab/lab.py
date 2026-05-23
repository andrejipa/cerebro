from __future__ import annotations

import json
from dataclasses import asdict, dataclass, replace
from typing import Iterable

from experiments.capability_policy import CapabilityAssessment
from experiments.control_plane_assessment import ControlPlaneAssessment
from experiments.control_plane_review_matrix import (
    ControlPlaneReviewMatrix,
    ControlPlaneReviewMatrixError,
    build_control_plane_review_matrix,
)
from experiments.control_plane_replay_eval import evaluate_control_plane_replay_jsonl
from experiments.control_plane_review_packet import build_control_plane_review_packet


class ControlPlaneScenarioLabError(ValueError):
    """Raised when an advisory scenario lab report cannot be built safely."""


@dataclass(frozen=True)
class ControlPlaneScenario:
    scenario_id: str
    assessment: ControlPlaneAssessment
    capability_assessments: tuple[CapabilityAssessment, ...] = ()
    expected_packet_verdict: str | None = None
    expected_combined_review_status: str | None = None
    expected_replay_evaluation_verdict: str | None = "replay_contract_passed"
    expected_required_human_decision: str | None = None
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class ControlPlaneScenarioResult:
    scenario_id: str
    packet_verdict: str
    combined_review_status: str
    replay_evaluation_verdict: str
    replay_status: str
    recommended_human_decision: str
    expectation_status: str
    expectation_failures: tuple[str, ...]
    blocker_count: int
    blockers: tuple[str, ...]
    required_capability_reviews: tuple[str, ...]
    replay_issue_codes: tuple[str, ...]
    notes: tuple[str, ...]


@dataclass(frozen=True)
class ControlPlaneAdversarialProbe:
    probe_id: str
    probe_kind: str
    description: str
    expected_finding_codes: tuple[str, ...]


@dataclass(frozen=True)
class ControlPlaneAdversarialFinding:
    probe_id: str
    code: str
    severity: str
    detail: str


@dataclass(frozen=True)
class ControlPlaneAdversarialProbeResult:
    probe_id: str
    probe_kind: str
    probe_status: str
    finding_codes: tuple[str, ...]
    expectation_status: str
    expectation_failures: tuple[str, ...]


@dataclass(frozen=True)
class ControlPlaneAdversarialReport:
    schema_version: str
    lab_role: str
    probe_count: int
    probe_status_counts: dict[str, int]
    expectation_status_counts: dict[str, int]
    finding_count: int
    findings: tuple[ControlPlaneAdversarialFinding, ...]
    results: tuple[ControlPlaneAdversarialProbeResult, ...]
    state_change: str = "none"
    authority: str = "non-authoritative; advisory control-plane adversarial probes only"
    lab_is_not_permission: bool = True
    adversarial_findings_are_not_execution_approval: bool = True
    replay_pass_is_not_truth: bool = True
    must_not_execute_automatically: bool = True


@dataclass(frozen=True)
class ControlPlaneScenarioLabReport:
    schema_version: str
    lab_role: str
    scenario_count: int
    expectation_status_counts: dict[str, int]
    expectation_failure_count: int
    scenarios_with_expectation_drift: tuple[str, ...]
    matrix: ControlPlaneReviewMatrix
    results: tuple[ControlPlaneScenarioResult, ...]
    state_change: str = "none"
    authority: str = "non-authoritative; advisory control-plane scenario lab only"
    lab_is_not_permission: bool = True
    expectation_match_is_not_execution_approval: bool = True
    replay_pass_is_not_truth: bool = True
    must_not_execute_automatically: bool = True


def _validate_scenario_id(scenario_id: str) -> None:
    if not scenario_id:
        raise ControlPlaneScenarioLabError("scenario_id is required")
    allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-")
    if any(char not in allowed for char in scenario_id):
        raise ControlPlaneScenarioLabError("scenario_id must be path-segment safe")


def _validate_probe_id(probe_id: str) -> None:
    if not probe_id:
        raise ControlPlaneScenarioLabError("probe_id is required")
    allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-")
    if any(char not in allowed for char in probe_id):
        raise ControlPlaneScenarioLabError("probe_id must be path-segment safe")


def _count(values: Iterable[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


def _assessment(**overrides) -> ControlPlaneAssessment:
    values = {
        "selected_task_id": "task-ready",
        "decision_runtime_reason": "selected executable task",
        "task_selection_status": "match",
        "task_selection_reason": "current task matches derived selection",
        "epistemic_action_readiness": "advisory_report_allowed",
        "blockers": (),
        "missing_evidence": (),
        "stale_claims": (),
        "conflicts": (),
        "claim_evaluation_summary": {"ready_count": 1, "blocked_count": 0, "insufficient_count": 0},
        "operational_signal_summary": {
            "record_count": 0,
            "candidate_trigger_count": 0,
            "authority": "derived-observability-only",
            "non_authoritative": True,
        },
        "recommended_human_decision": "none",
        "must_not_execute_automatically": True,
        "advisory_pass_is_not_permission": True,
    }
    values.update(overrides)
    return ControlPlaneAssessment(**values)


def _capability(decision: str = "advisory_allow", **overrides) -> CapabilityAssessment:
    values = {
        "request_id": f"req-{decision}",
        "matched_rule_id": "scenario-lab-rule",
        "decision": decision,
        "reasons": ("capability_request_within_declared_policy",),
        "warnings": ("advisory_allow_is_not_permission",) if decision == "advisory_allow" else (),
        "required_human_decision": "none" if decision == "advisory_allow" else "review_capability_request",
    }
    values.update(overrides)
    return CapabilityAssessment(**values)


def builtin_control_plane_scenarios() -> tuple[ControlPlaneScenario, ...]:
    """Return a small adversarial battery for the advisory Control Plane."""

    return (
        ControlPlaneScenario(
            scenario_id="scenario-advisory",
            assessment=_assessment(),
            capability_assessments=(_capability(),),
            expected_packet_verdict="packet_advisory_review_only",
            expected_combined_review_status="advisory_review_only",
            expected_required_human_decision="none",
            notes=("clean advisory path; still not permission",),
        ),
        ControlPlaneScenario(
            scenario_id="scenario-missing-capability",
            assessment=_assessment(),
            expected_packet_verdict="packet_human_review_required",
            expected_combined_review_status="human_review_required",
            expected_required_human_decision="provide_capability_assessment",
            notes=("missing capability evidence must force human review",),
        ),
        ControlPlaneScenario(
            scenario_id="scenario-runtime-blocked",
            assessment=_assessment(
                epistemic_action_readiness="canonical_change_requires_trigger",
                blockers=("missing_active_trigger_for_runtime_or_canonical_change",),
                recommended_human_decision="review_blockers",
            ),
            capability_assessments=(
                _capability(
                    "blocked",
                    request_id="req-runtime-write",
                    reasons=("cerebro_write_requires_runtime_authority",),
                    required_human_decision="open_runtime_authority_trigger",
                ),
            ),
            expected_packet_verdict="packet_blocked",
            expected_combined_review_status="blocked_review",
            expected_required_human_decision="review_blockers",
            notes=("runtime/canonical boundary remains blocked",),
        ),
        ControlPlaneScenario(
            scenario_id="scenario-network-review",
            assessment=_assessment(),
            capability_assessments=(
                _capability(
                    "review_required",
                    request_id="req-network",
                    reasons=("network_access_requires_review",),
                    required_human_decision="review_network_use",
                ),
            ),
            expected_packet_verdict="packet_human_review_required",
            expected_combined_review_status="human_review_required",
            expected_required_human_decision="review_capability_request",
            notes=("network capability review does not become permission",),
        ),
    )


def builtin_control_plane_adversarial_probes() -> tuple[ControlPlaneAdversarialProbe, ...]:
    """Return hostile in-memory probes for the current advisory chain."""

    return (
        ControlPlaneAdversarialProbe(
            probe_id="probe-replay-authority-drift",
            probe_kind="replay_authority_drift",
            description="mutate JSONL authority and state_change fields",
            expected_finding_codes=(
                "replay:authority_drift",
                "replay:state_change_drift",
                "replay:permission_guardrail_drift",
            ),
        ),
        ControlPlaneAdversarialProbe(
            probe_id="probe-replay-missing-open",
            probe_kind="replay_missing_open",
            description="remove decision_opened from JSONL replay",
            expected_finding_codes=("replay:missing_decision_opened",),
        ),
        ControlPlaneAdversarialProbe(
            probe_id="probe-packet-guardrail-drift",
            probe_kind="packet_guardrail_drift",
            description="weaken packet_is_not_permission before matrix aggregation",
            expected_finding_codes=("packet_guardrail_drift_rejected",),
        ),
        ControlPlaneAdversarialProbe(
            probe_id="probe-matrix-duplicate-trace",
            probe_kind="matrix_duplicate_trace",
            description="feed duplicate trace ids to matrix aggregation",
            expected_finding_codes=("matrix_duplicate_trace_rejected",),
        ),
        ControlPlaneAdversarialProbe(
            probe_id="probe-capability-allow-boundary",
            probe_kind="capability_allow_boundary",
            description="verify advisory_allow stays non-permission through packet and matrix",
            expected_finding_codes=("capability_allow_preserved_as_non_permission",),
        ),
        ControlPlaneAdversarialProbe(
            probe_id="probe-assessment-blocker-laundering",
            probe_kind="assessment_blocker_laundering",
            description="detect blockers paired with none human decision or advisory expectations",
            expected_finding_codes=("semantic:assessment_blocker_laundering",),
        ),
        ControlPlaneAdversarialProbe(
            probe_id="probe-readiness-contradiction",
            probe_kind="readiness_contradiction",
            description="detect permissive readiness with mismatch or missing evidence",
            expected_finding_codes=("semantic:readiness_contradiction",),
        ),
        ControlPlaneAdversarialProbe(
            probe_id="probe-capability-decision-contradiction",
            probe_kind="capability_decision_contradiction",
            description="detect advisory_allow with human review or missing non-permission warning",
            expected_finding_codes=("semantic:capability_decision_contradiction",),
        ),
        ControlPlaneAdversarialProbe(
            probe_id="probe-expectation-laundering",
            probe_kind="expectation_laundering",
            description="detect advisory expectation over blocked inputs",
            expected_finding_codes=("semantic:expectation_laundering",),
        ),
        ControlPlaneAdversarialProbe(
            probe_id="probe-replay-pass-laundering",
            probe_kind="replay_pass_laundering",
            description="mark replay_contract_passed on non-advisory packet as non-authority evidence",
            expected_finding_codes=("semantic:replay_pass_is_not_authority",),
        ),
        ControlPlaneAdversarialProbe(
            probe_id="probe-capability-identity-collision",
            probe_kind="capability_identity_collision",
            description="detect duplicate capability request ids with divergent decisions",
            expected_finding_codes=("semantic:capability_identity_collision",),
        ),
    )


def _expectation_failures(
    scenario: ControlPlaneScenario,
    *,
    packet_verdict: str,
    combined_review_status: str,
    replay_evaluation_verdict: str,
    recommended_human_decision: str,
) -> tuple[str, ...]:
    failures: list[str] = []
    expectations = (
        ("packet_verdict", scenario.expected_packet_verdict, packet_verdict),
        ("combined_review_status", scenario.expected_combined_review_status, combined_review_status),
        ("replay_evaluation_verdict", scenario.expected_replay_evaluation_verdict, replay_evaluation_verdict),
        ("recommended_human_decision", scenario.expected_required_human_decision, recommended_human_decision),
    )
    for field, expected, observed in expectations:
        if expected is not None and expected != observed:
            failures.append(f"{field}:expected={expected}:observed={observed}")
    return tuple(failures)


def _advisory_packet():
    return build_control_plane_review_packet(
        "probe-advisory",
        _assessment(),
        capability_assessments=(_capability(),),
    )


def _replay_finding(probe_id: str, code: str, severity: str, detail: str) -> ControlPlaneAdversarialFinding:
    return ControlPlaneAdversarialFinding(
        probe_id=probe_id,
        code=f"replay:{code}",
        severity=severity,
        detail=detail,
    )


def _semantic_finding(probe_id: str, code: str, severity: str, detail: str) -> ControlPlaneAdversarialFinding:
    return ControlPlaneAdversarialFinding(
        probe_id=probe_id,
        code=f"semantic:{code}",
        severity=severity,
        detail=detail,
    )


def _run_probe(probe: ControlPlaneAdversarialProbe) -> tuple[str, tuple[ControlPlaneAdversarialFinding, ...]]:
    if probe.probe_kind == "replay_authority_drift":
        rows = [json.loads(line) for line in _advisory_packet().ledger_jsonl.splitlines()]
        rows[1]["authority"] = "runtime authority"
        rows[1]["state_change"] = "writes_state"
        rows[1]["ledger_is_not_permission"] = False
        evaluation = evaluate_control_plane_replay_jsonl("\n".join(json.dumps(row) for row in rows) + "\n")
        return (
            "adversarial_drift_detected",
            tuple(_replay_finding(probe.probe_id, issue.code, issue.severity, issue.detail) for issue in evaluation.issues),
        )

    if probe.probe_kind == "replay_missing_open":
        rows = [json.loads(line) for line in _advisory_packet().ledger_jsonl.splitlines()]
        evaluation = evaluate_control_plane_replay_jsonl("\n".join(json.dumps(row) for row in rows[1:]) + "\n")
        return (
            "adversarial_drift_detected",
            tuple(_replay_finding(probe.probe_id, issue.code, issue.severity, issue.detail) for issue in evaluation.issues),
        )

    if probe.probe_kind == "packet_guardrail_drift":
        try:
            build_control_plane_review_matrix((replace(_advisory_packet(), packet_is_not_permission=False),))
        except ControlPlaneReviewMatrixError as exc:
            return (
                "adversarial_drift_rejected",
                (
                    ControlPlaneAdversarialFinding(
                        probe_id=probe.probe_id,
                        code="packet_guardrail_drift_rejected",
                        severity="critical",
                        detail=str(exc),
                    ),
                ),
            )
        return (
            "adversarial_drift_not_detected",
            (
                ControlPlaneAdversarialFinding(
                    probe_id=probe.probe_id,
                    code="packet_guardrail_drift_not_rejected",
                    severity="critical",
                    detail="weakened packet guardrail reached matrix without rejection",
                ),
            ),
        )

    if probe.probe_kind == "matrix_duplicate_trace":
        packet = _advisory_packet()
        try:
            build_control_plane_review_matrix((packet, packet))
        except ControlPlaneReviewMatrixError as exc:
            return (
                "adversarial_drift_rejected",
                (
                    ControlPlaneAdversarialFinding(
                        probe_id=probe.probe_id,
                        code="matrix_duplicate_trace_rejected",
                        severity="high",
                        detail=str(exc),
                    ),
                ),
            )
        return (
            "adversarial_drift_not_detected",
            (
                ControlPlaneAdversarialFinding(
                    probe_id=probe.probe_id,
                    code="matrix_duplicate_trace_not_rejected",
                    severity="high",
                    detail="duplicate trace ids reached matrix without rejection",
                ),
            ),
        )

    if probe.probe_kind == "capability_allow_boundary":
        packet = _advisory_packet()
        matrix = build_control_plane_review_matrix((packet,))
        if (
            packet.packet_pass_is_not_execution_approval
            and packet.packet_is_not_permission
            and matrix.matrix_pass_is_not_execution_approval
            and matrix.matrix_is_not_permission
        ):
            return (
                "boundary_preserved",
                (
                    ControlPlaneAdversarialFinding(
                        probe_id=probe.probe_id,
                        code="capability_allow_preserved_as_non_permission",
                        severity="info",
                        detail="advisory_allow remained marked as non-permission through packet and matrix",
                    ),
                ),
            )
        return (
            "adversarial_drift_detected",
            (
                ControlPlaneAdversarialFinding(
                    probe_id=probe.probe_id,
                    code="capability_allow_permission_drift",
                    severity="critical",
                    detail="advisory allow lost a non-permission marker",
                ),
            ),
        )

    if probe.probe_kind == "assessment_blocker_laundering":
        scenario = ControlPlaneScenario(
            scenario_id="probe-assessment-blocker",
            assessment=_assessment(blockers=("unresolved_runtime_boundary",), recommended_human_decision="none"),
            capability_assessments=(_capability(),),
            expected_packet_verdict="packet_advisory_review_only",
        )
        report = build_control_plane_scenario_lab_report((scenario,))
        result = report.results[0]
        if result.packet_verdict == "packet_blocked" and result.expectation_status == "expectation_drift_observed":
            return (
                "semantic_boundary_observed",
                (
                    _semantic_finding(
                        probe.probe_id,
                        "assessment_blocker_laundering",
                        "high",
                        "assessment blockers forced blocked packet despite advisory expectation or none human decision",
                    ),
                ),
            )

    if probe.probe_kind == "readiness_contradiction":
        packet = build_control_plane_review_packet(
            "probe-readiness-contradiction",
            _assessment(
                task_selection_status="mismatch",
                missing_evidence=("missing_capability_manifest",),
                stale_claims=("stale_runtime_claim",),
            ),
            capability_assessments=(_capability(),),
        )
        if packet.packet_verdict == "packet_advisory_review_only":
            return (
                "semantic_boundary_observed",
                (
                    _semantic_finding(
                        probe.probe_id,
                        "readiness_contradiction",
                        "high",
                        "permissive readiness coexisted with mismatch, missing evidence, or stale claims",
                    ),
                ),
            )

    if probe.probe_kind == "capability_decision_contradiction":
        packet = build_control_plane_review_packet(
            "probe-capability-contradiction",
            _assessment(),
            capability_assessments=(
                _capability(
                    "advisory_allow",
                    request_id="req-contradictory-allow",
                    warnings=(),
                    required_human_decision="review_capability_request",
                ),
            ),
        )
        if packet.packet_verdict == "packet_advisory_review_only":
            return (
                "semantic_boundary_observed",
                (
                    _semantic_finding(
                        probe.probe_id,
                        "capability_decision_contradiction",
                        "high",
                        "advisory_allow carried human-review semantics or missed the non-permission warning",
                    ),
                ),
            )

    if probe.probe_kind == "expectation_laundering":
        scenario = ControlPlaneScenario(
            scenario_id="probe-expectation-laundering",
            assessment=_assessment(
                blockers=("canonical_change_without_trigger",),
                recommended_human_decision="review_blockers",
            ),
            capability_assessments=(_capability(),),
            expected_packet_verdict="packet_advisory_review_only",
            expected_combined_review_status="advisory_review_only",
        )
        report = build_control_plane_scenario_lab_report((scenario,))
        result = report.results[0]
        if result.expectation_status == "expectation_drift_observed":
            return (
                "semantic_boundary_observed",
                (
                    _semantic_finding(
                        probe.probe_id,
                        "expectation_laundering",
                        "high",
                        "declared advisory expectation drifted against blocked scenario evidence",
                    ),
                ),
            )

    if probe.probe_kind == "replay_pass_laundering":
        packet = build_control_plane_review_packet(
            "probe-replay-pass-laundering",
            _assessment(
                blockers=("runtime_boundary_closed",),
                recommended_human_decision="review_blockers",
            ),
            capability_assessments=(_capability(),),
        )
        if packet.replay_evaluation_verdict == "replay_contract_passed" and packet.packet_verdict != "packet_advisory_review_only":
            return (
                "semantic_boundary_observed",
                (
                    _semantic_finding(
                        probe.probe_id,
                        "replay_pass_is_not_authority",
                        "info",
                        "valid replay coexisted with blocked or human-review packet and remains non-authority evidence",
                    ),
                ),
            )

    if probe.probe_kind == "capability_identity_collision":
        packet = build_control_plane_review_packet(
            "probe-capability-collision",
            _assessment(),
            capability_assessments=(
                _capability("advisory_allow", request_id="req-collision"),
                _capability(
                    "blocked",
                    request_id="req-collision",
                    reasons=("path_scope_violation",),
                    required_human_decision="review_path_scope",
                ),
            ),
        )
        statuses = set(packet.trace.capability_statuses)
        if "req-collision:advisory_allow" in statuses and "req-collision:blocked" in statuses:
            return (
                "semantic_boundary_observed",
                (
                    _semantic_finding(
                        probe.probe_id,
                        "capability_identity_collision",
                        "high",
                        "same capability request id carried divergent decisions in one trace",
                    ),
                ),
            )

    raise ControlPlaneScenarioLabError(f"unknown probe_kind: {probe.probe_kind}")


def _probe_expectation_failures(
    probe: ControlPlaneAdversarialProbe,
    findings: tuple[ControlPlaneAdversarialFinding, ...],
) -> tuple[str, ...]:
    observed = {finding.code for finding in findings}
    return tuple(
        f"missing_expected_finding:{code}"
        for code in probe.expected_finding_codes
        if code not in observed
    )


def _validate_report(report: ControlPlaneScenarioLabReport) -> None:
    if report.state_change != "none" or "non-authoritative" not in report.authority:
        raise ControlPlaneScenarioLabError("lab report must be non-authoritative with state_change none")
    if (
        not report.lab_is_not_permission
        or not report.expectation_match_is_not_execution_approval
        or not report.replay_pass_is_not_truth
        or not report.must_not_execute_automatically
    ):
        raise ControlPlaneScenarioLabError("lab guardrails must remain true")
    if report.scenario_count != len(report.results):
        raise ControlPlaneScenarioLabError("scenario_count must match results")
    if report.scenario_count != report.matrix.packet_count:
        raise ControlPlaneScenarioLabError("scenario_count must match matrix packet_count")


def _validate_adversarial_report(report: ControlPlaneAdversarialReport) -> None:
    if report.state_change != "none" or "non-authoritative" not in report.authority:
        raise ControlPlaneScenarioLabError("adversarial report must be non-authoritative with state_change none")
    if (
        not report.lab_is_not_permission
        or not report.adversarial_findings_are_not_execution_approval
        or not report.replay_pass_is_not_truth
        or not report.must_not_execute_automatically
    ):
        raise ControlPlaneScenarioLabError("adversarial report guardrails must remain true")
    if report.probe_count != len(report.results):
        raise ControlPlaneScenarioLabError("probe_count must match results")
    if report.finding_count != len(report.findings):
        raise ControlPlaneScenarioLabError("finding_count must match findings")


def build_control_plane_scenario_lab_report(
    scenarios: Iterable[ControlPlaneScenario],
) -> ControlPlaneScenarioLabReport:
    """Run declared in-memory scenarios through advisory Control Plane layers."""

    scenario_items = tuple(scenarios)
    if not scenario_items:
        raise ControlPlaneScenarioLabError("scenario lab requires at least one scenario")
    scenario_ids = [scenario.scenario_id for scenario in scenario_items]
    duplicates = sorted({scenario_id for scenario_id in scenario_ids if scenario_ids.count(scenario_id) > 1})
    if duplicates:
        raise ControlPlaneScenarioLabError(f"duplicate scenario_id: {', '.join(duplicates)}")

    packets = []
    results = []
    for scenario in scenario_items:
        _validate_scenario_id(scenario.scenario_id)
        packet = build_control_plane_review_packet(
            scenario.scenario_id,
            scenario.assessment,
            capability_assessments=scenario.capability_assessments,
        )
        packets.append(packet)
        failures = _expectation_failures(
            scenario,
            packet_verdict=packet.packet_verdict,
            combined_review_status=packet.combined_review_status,
            replay_evaluation_verdict=packet.replay_evaluation_verdict,
            recommended_human_decision=packet.recommended_human_decision,
        )
        results.append(
            ControlPlaneScenarioResult(
                scenario_id=scenario.scenario_id,
                packet_verdict=packet.packet_verdict,
                combined_review_status=packet.combined_review_status,
                replay_evaluation_verdict=packet.replay_evaluation_verdict,
                replay_status=packet.replay_status,
                recommended_human_decision=packet.recommended_human_decision,
                expectation_status=(
                    "expectation_drift_observed" if failures else "expectations_observed_as_declared"
                ),
                expectation_failures=failures,
                blocker_count=len(packet.blockers),
                blockers=packet.blockers,
                required_capability_reviews=packet.required_capability_reviews,
                replay_issue_codes=packet.replay_issue_codes,
                notes=scenario.notes,
            )
        )

    matrix = build_control_plane_review_matrix(tuple(packets))
    result_items = tuple(results)
    report = ControlPlaneScenarioLabReport(
        schema_version="1",
        lab_role="runs_declared_control_plane_scenarios_without_authority",
        scenario_count=len(result_items),
        expectation_status_counts=_count(result.expectation_status for result in result_items),
        expectation_failure_count=sum(len(result.expectation_failures) for result in result_items),
        scenarios_with_expectation_drift=tuple(
            result.scenario_id
            for result in result_items
            if result.expectation_status == "expectation_drift_observed"
        ),
        matrix=matrix,
        results=result_items,
    )
    _validate_report(report)
    return report


def build_control_plane_adversarial_report(
    probes: Iterable[ControlPlaneAdversarialProbe],
) -> ControlPlaneAdversarialReport:
    """Run hostile in-memory probes against the advisory Control Plane chain."""

    probe_items = tuple(probes)
    if not probe_items:
        raise ControlPlaneScenarioLabError("adversarial lab requires at least one probe")
    probe_ids = [probe.probe_id for probe in probe_items]
    duplicates = sorted({probe_id for probe_id in probe_ids if probe_ids.count(probe_id) > 1})
    if duplicates:
        raise ControlPlaneScenarioLabError(f"duplicate probe_id: {', '.join(duplicates)}")

    findings: list[ControlPlaneAdversarialFinding] = []
    results: list[ControlPlaneAdversarialProbeResult] = []
    for probe in probe_items:
        _validate_probe_id(probe.probe_id)
        status, probe_findings = _run_probe(probe)
        failures = _probe_expectation_failures(probe, probe_findings)
        findings.extend(probe_findings)
        results.append(
            ControlPlaneAdversarialProbeResult(
                probe_id=probe.probe_id,
                probe_kind=probe.probe_kind,
                probe_status=status,
                finding_codes=tuple(finding.code for finding in probe_findings),
                expectation_status=(
                    "expected_findings_observed" if not failures else "expected_findings_missing"
                ),
                expectation_failures=failures,
            )
        )

    result_items = tuple(results)
    finding_items = tuple(findings)
    report = ControlPlaneAdversarialReport(
        schema_version="1",
        lab_role="runs_hostile_control_plane_probes_without_authority",
        probe_count=len(result_items),
        probe_status_counts=_count(result.probe_status for result in result_items),
        expectation_status_counts=_count(result.expectation_status for result in result_items),
        finding_count=len(finding_items),
        findings=finding_items,
        results=result_items,
    )
    _validate_adversarial_report(report)
    return report


def render_control_plane_scenario_lab_json(report: ControlPlaneScenarioLabReport) -> str:
    _validate_report(report)
    payload = asdict(report)
    payload["state_change"] = "none"
    payload["authority"] = report.authority
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def render_control_plane_adversarial_json(report: ControlPlaneAdversarialReport) -> str:
    _validate_adversarial_report(report)
    payload = asdict(report)
    payload["state_change"] = "none"
    payload["authority"] = report.authority
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def render_control_plane_scenario_lab_markdown(report: ControlPlaneScenarioLabReport) -> str:
    _validate_report(report)
    lines = [
        "# Control Plane Scenario Lab",
        "",
        "- state_change: none",
        "- authority: non-authoritative; advisory control-plane scenario lab only",
        "- lab_is_not_permission: true",
        "- expectation_match_is_not_execution_approval: true",
        "- replay_pass_is_not_truth: true",
        "- must_not_execute_automatically: true",
        "",
        "## Summary",
        "",
        f"- lab_role: {report.lab_role}",
        f"- scenario_count: {report.scenario_count}",
        f"- expectation_status_counts: {report.expectation_status_counts}",
        f"- expectation_failure_count: {report.expectation_failure_count}",
        f"- scenarios_with_expectation_drift: {', '.join(report.scenarios_with_expectation_drift) if report.scenarios_with_expectation_drift else 'none'}",
        "",
        "## Scenarios",
        "",
    ]
    for result in report.results:
        lines.append(
            f"- {result.scenario_id}: {result.expectation_status}; "
            f"packet={result.packet_verdict}; review={result.combined_review_status}; "
            f"human={result.recommended_human_decision}; replay={result.replay_evaluation_verdict}"
        )
    return "\n".join(lines).rstrip() + "\n"


def render_control_plane_adversarial_markdown(report: ControlPlaneAdversarialReport) -> str:
    _validate_adversarial_report(report)
    lines = [
        "# Control Plane Adversarial Probes",
        "",
        "- state_change: none",
        "- authority: non-authoritative; advisory control-plane adversarial probes only",
        "- lab_is_not_permission: true",
        "- adversarial_findings_are_not_execution_approval: true",
        "- replay_pass_is_not_truth: true",
        "- must_not_execute_automatically: true",
        "",
        "## Summary",
        "",
        f"- lab_role: {report.lab_role}",
        f"- probe_count: {report.probe_count}",
        f"- finding_count: {report.finding_count}",
        f"- probe_status_counts: {report.probe_status_counts}",
        f"- expectation_status_counts: {report.expectation_status_counts}",
        "",
        "## Probes",
        "",
    ]
    for result in report.results:
        lines.append(
            f"- {result.probe_id}: {result.probe_status}; "
            f"expectation={result.expectation_status}; findings={', '.join(result.finding_codes) if result.finding_codes else 'none'}"
        )
    return "\n".join(lines).rstrip() + "\n"
