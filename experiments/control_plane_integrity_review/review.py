from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Iterable

from experiments.control_plane_boundary_audit import ControlPlaneBoundaryAuditReport
from experiments.control_plane_guardrail_eval import ControlPlaneGuardrailReport
from experiments.control_plane_lineage_invariant_eval import ControlPlaneLineageInvariantReport


class ControlPlaneIntegrityReviewError(ValueError):
    """Raised when integrity review evidence crosses its advisory boundary."""


@dataclass(frozen=True)
class ControlPlaneIntegrityEvidence:
    source_kind: str
    source_id: str
    source_role: str
    source_status: str
    finding_count: int
    severity_counts: dict[str, int]


@dataclass(frozen=True)
class ControlPlaneIntegrityFinding:
    code: str
    severity: str
    source_kind: str
    source_id: str
    detail: str


@dataclass(frozen=True)
class ControlPlaneIntegrityReview:
    schema_version: str
    review_role: str
    review_status: str
    evidence_count: int
    finding_count: int
    source_status_counts: dict[str, int]
    severity_counts: dict[str, int]
    finding_codes: tuple[str, ...]
    evidence: tuple[ControlPlaneIntegrityEvidence, ...]
    findings: tuple[ControlPlaneIntegrityFinding, ...]
    state_change: str = "none"
    authority: str = "non-authoritative; advisory control-plane integrity review only"
    review_is_not_permission: bool = True
    integrity_pass_is_not_truth: bool = True
    finding_is_not_execution_approval: bool = True
    must_not_execute_automatically: bool = True


_BOUNDARY_STATUSES = {"boundary_markers_preserved", "boundary_drift_observed"}
_GUARDRAIL_STATUSES = {"guardrails_preserved", "guardrail_drift_observed"}
_LINEAGE_STATUSES = {"lineage_invariants_preserved", "lineage_drift_observed"}
_CLEAN_STATUSES = {
    "boundary_markers_preserved",
    "guardrails_preserved",
    "lineage_invariants_preserved",
}


def _count(values: Iterable[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


def _validate_non_authoritative(obj: object, label: str, guardrails: tuple[str, ...]) -> None:
    if getattr(obj, "state_change", None) != "none" or "non-authoritative" not in str(getattr(obj, "authority", "")):
        raise ControlPlaneIntegrityReviewError(f"{label} must be non-authoritative with state_change none")
    missing = [guardrail for guardrail in guardrails if getattr(obj, guardrail, None) is not True]
    if missing:
        raise ControlPlaneIntegrityReviewError(f"{label} guardrails must remain true: {', '.join(missing)}")


def _evidence(
    *,
    source_kind: str,
    source_id: str,
    source_role: str,
    source_status: str,
    finding_count: int,
    severity_counts: dict[str, int],
) -> ControlPlaneIntegrityEvidence:
    return ControlPlaneIntegrityEvidence(
        source_kind=source_kind,
        source_id=source_id,
        source_role=source_role,
        source_status=source_status,
        finding_count=finding_count,
        severity_counts=dict(sorted(severity_counts.items())),
    )


def _finding(
    code: str,
    severity: str,
    source_kind: str,
    source_id: str,
    detail: str,
) -> ControlPlaneIntegrityFinding:
    return ControlPlaneIntegrityFinding(
        code=code,
        severity=severity,
        source_kind=source_kind,
        source_id=source_id,
        detail=detail,
    )


def _review_boundary_report(report: ControlPlaneBoundaryAuditReport) -> tuple[ControlPlaneIntegrityEvidence, tuple[ControlPlaneIntegrityFinding, ...]]:
    _validate_non_authoritative(
        report,
        "boundary audit report",
        (
            "audit_is_not_permission",
            "finding_is_not_truth",
            "audit_pass_is_not_execution_approval",
            "must_not_execute_automatically",
        ),
    )
    if report.audit_status not in _BOUNDARY_STATUSES:
        raise ControlPlaneIntegrityReviewError(f"unknown boundary audit status: {report.audit_status}")
    if report.finding_count != len(report.findings):
        raise ControlPlaneIntegrityReviewError("boundary audit finding_count must match findings")
    if report.finding_codes != tuple(finding.code for finding in report.findings):
        raise ControlPlaneIntegrityReviewError("boundary audit finding_codes must match findings")
    if report.severity_counts != _count(finding.severity for finding in report.findings):
        raise ControlPlaneIntegrityReviewError("boundary audit severity_counts must match findings")
    if report.package_counts != _count(finding.package_name for finding in report.findings):
        raise ControlPlaneIntegrityReviewError("boundary audit package_counts must match findings")
    evidence = _evidence(
        source_kind="boundary_audit",
        source_id="control_plane_boundary_audit",
        source_role=report.audit_role,
        source_status=report.audit_status,
        finding_count=report.finding_count,
        severity_counts=report.severity_counts,
    )
    findings = tuple(
        _finding(
            finding.code,
            finding.severity,
            "boundary_audit",
            f"{finding.package_name}/{finding.relative_path}",
            finding.detail,
        )
        for finding in report.findings
    )
    return evidence, findings


def _review_guardrail_report(
    report: ControlPlaneGuardrailReport,
) -> tuple[ControlPlaneIntegrityEvidence, tuple[ControlPlaneIntegrityFinding, ...]]:
    _validate_non_authoritative(
        report,
        "guardrail report",
        (
            "eval_is_not_permission",
            "finding_is_not_truth",
            "finding_is_not_execution_approval",
            "must_not_execute_automatically",
        ),
    )
    if report.eval_status not in _GUARDRAIL_STATUSES:
        raise ControlPlaneIntegrityReviewError(f"unknown guardrail eval status: {report.eval_status}")
    if report.finding_count != len(report.findings):
        raise ControlPlaneIntegrityReviewError("guardrail finding_count must match findings")
    if report.finding_codes != tuple(finding.code for finding in report.findings):
        raise ControlPlaneIntegrityReviewError("guardrail finding_codes must match findings")
    if report.category_counts != _count(finding.category for finding in report.findings):
        raise ControlPlaneIntegrityReviewError("guardrail category_counts must match findings")
    if report.severity_counts != _count(finding.severity for finding in report.findings):
        raise ControlPlaneIntegrityReviewError("guardrail severity_counts must match findings")
    evidence = _evidence(
        source_kind="guardrail_eval",
        source_id=report.source_projection_role,
        source_role=report.eval_role,
        source_status=report.eval_status,
        finding_count=report.finding_count,
        severity_counts=report.severity_counts,
    )
    findings = tuple(
        _finding(
            finding.code,
            finding.severity,
            "guardrail_eval",
            finding.location,
            finding.detail,
        )
        for finding in report.findings
    )
    return evidence, findings


def _review_lineage_report(
    report: ControlPlaneLineageInvariantReport,
) -> tuple[ControlPlaneIntegrityEvidence, tuple[ControlPlaneIntegrityFinding, ...]]:
    _validate_non_authoritative(
        report,
        "lineage invariant report",
        (
            "eval_is_not_permission",
            "invariant_pass_is_not_truth",
            "finding_is_not_execution_approval",
            "must_not_execute_automatically",
        ),
    )
    if report.eval_status not in _LINEAGE_STATUSES:
        raise ControlPlaneIntegrityReviewError(f"unknown lineage eval status: {report.eval_status}")
    if report.finding_count != len(report.findings):
        raise ControlPlaneIntegrityReviewError("lineage finding_count must match findings")
    if report.finding_codes != tuple(finding.code for finding in report.findings):
        raise ControlPlaneIntegrityReviewError("lineage finding_codes must match findings")
    if report.severity_counts != _count(finding.severity for finding in report.findings):
        raise ControlPlaneIntegrityReviewError("lineage severity_counts must match findings")
    if not report.checked_layer_pairs:
        raise ControlPlaneIntegrityReviewError("lineage checked_layer_pairs must not be empty")
    source_id = ",".join(report.checked_layer_pairs) if report.checked_layer_pairs else "none"
    evidence = _evidence(
        source_kind="lineage_invariant_eval",
        source_id=source_id,
        source_role=report.eval_role,
        source_status=report.eval_status,
        finding_count=report.finding_count,
        severity_counts=report.severity_counts,
    )
    findings = tuple(
        _finding(
            finding.code,
            finding.severity,
            "lineage_invariant_eval",
            finding.source_id,
            f"{finding.layer_pair}: {finding.detail}",
        )
        for finding in report.findings
    )
    return evidence, findings


def _validate_review(review: ControlPlaneIntegrityReview) -> None:
    if review.state_change != "none" or "non-authoritative" not in review.authority:
        raise ControlPlaneIntegrityReviewError("review must be non-authoritative with state_change none")
    if (
        not review.review_is_not_permission
        or not review.integrity_pass_is_not_truth
        or not review.finding_is_not_execution_approval
        or not review.must_not_execute_automatically
    ):
        raise ControlPlaneIntegrityReviewError("review guardrails must remain true")
    if review.evidence_count != len(review.evidence):
        raise ControlPlaneIntegrityReviewError("evidence_count must match evidence")
    if review.finding_count != len(review.findings):
        raise ControlPlaneIntegrityReviewError("finding_count must match findings")
    if review.finding_codes != tuple(finding.code for finding in review.findings):
        raise ControlPlaneIntegrityReviewError("finding_codes must match findings")
    if review.source_status_counts != _count(evidence.source_status for evidence in review.evidence):
        raise ControlPlaneIntegrityReviewError("source_status_counts must match evidence")
    if review.severity_counts != _count(finding.severity for finding in review.findings):
        raise ControlPlaneIntegrityReviewError("severity_counts must match findings")
    clean = all(evidence.source_status in _CLEAN_STATUSES and evidence.finding_count == 0 for evidence in review.evidence)
    expected_status = "control_plane_integrity_preserved" if clean else "control_plane_integrity_drift_observed"
    if review.review_status != expected_status:
        raise ControlPlaneIntegrityReviewError("review_status must follow source evidence")


def build_control_plane_integrity_review(
    *,
    boundary_audit: ControlPlaneBoundaryAuditReport,
    guardrail_reports: Iterable[ControlPlaneGuardrailReport] = (),
    lineage_reports: Iterable[ControlPlaneLineageInvariantReport] = (),
) -> ControlPlaneIntegrityReview:
    """Consolidate existing Control Plane advisory reports into one review surface."""

    evidence_items: list[ControlPlaneIntegrityEvidence] = []
    finding_items: list[ControlPlaneIntegrityFinding] = []

    evidence, findings = _review_boundary_report(boundary_audit)
    evidence_items.append(evidence)
    finding_items.extend(findings)

    for report in tuple(guardrail_reports):
        evidence, findings = _review_guardrail_report(report)
        evidence_items.append(evidence)
        finding_items.extend(findings)

    for report in tuple(lineage_reports):
        evidence, findings = _review_lineage_report(report)
        evidence_items.append(evidence)
        finding_items.extend(findings)

    if len(evidence_items) == 1:
        raise ControlPlaneIntegrityReviewError("integrity review requires boundary evidence plus guardrail or lineage evidence")

    clean = all(evidence.source_status in _CLEAN_STATUSES and evidence.finding_count == 0 for evidence in evidence_items)
    findings_tuple = tuple(finding_items)
    review = ControlPlaneIntegrityReview(
        schema_version="1",
        review_role="consolidates_control_plane_boundary_guardrail_and_lineage_evidence",
        review_status="control_plane_integrity_preserved" if clean else "control_plane_integrity_drift_observed",
        evidence_count=len(evidence_items),
        finding_count=len(findings_tuple),
        source_status_counts=_count(evidence.source_status for evidence in evidence_items),
        severity_counts=_count(finding.severity for finding in findings_tuple),
        finding_codes=tuple(finding.code for finding in findings_tuple),
        evidence=tuple(evidence_items),
        findings=findings_tuple,
    )
    _validate_review(review)
    return review


def render_control_plane_integrity_review_json(review: ControlPlaneIntegrityReview) -> str:
    _validate_review(review)
    payload = asdict(review)
    payload["state_change"] = "none"
    payload["authority"] = review.authority
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def render_control_plane_integrity_review_markdown(review: ControlPlaneIntegrityReview) -> str:
    _validate_review(review)
    lines = [
        "# Control Plane Integrity Review",
        "",
        "- state_change: none",
        "- authority: non-authoritative; advisory control-plane integrity review only",
        "- review_is_not_permission: true",
        "- integrity_pass_is_not_truth: true",
        "- finding_is_not_execution_approval: true",
        "- must_not_execute_automatically: true",
        "",
        "## Summary",
        "",
        f"- review_role: {review.review_role}",
        f"- review_status: {review.review_status}",
        f"- evidence_count: {review.evidence_count}",
        f"- finding_count: {review.finding_count}",
        f"- source_status_counts: {review.source_status_counts}",
        f"- severity_counts: {review.severity_counts}",
        "",
        "## Evidence",
        "",
    ]
    for evidence in review.evidence:
        lines.append(
            f"- {evidence.source_kind}:{evidence.source_id}: "
            f"status={evidence.source_status}; findings={evidence.finding_count}"
        )
    lines.extend(["", "## Findings", ""])
    if not review.findings:
        lines.append("- none")
    else:
        for finding in review.findings:
            lines.append(
                f"- {finding.severity}:{finding.source_kind}:{finding.code} "
                f"for {finding.source_id} - {finding.detail}"
            )
    return "\n".join(lines).rstrip() + "\n"
