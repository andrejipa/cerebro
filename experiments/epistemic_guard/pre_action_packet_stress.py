from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from json import JSONDecodeError
from pathlib import Path

from .evaluator import evaluate_decision_scenario
from .fixtures import clean_advisory_report, missing_trigger_for_runtime_mutation, silence_is_not_negative_evidence
from .pre_action import ProposedAction, build_pre_action_guard_report
from .pre_action_packet import (
    PreActionDecisionPacket,
    build_pre_action_decision_packet,
    render_pre_action_decision_packet_json,
    render_pre_action_decision_packet_markdown,
)
from .pre_action_stress import PreActionStressMatrixReport, build_default_pre_action_stress_matrix


class PreActionPacketStressError(ValueError):
    """Raised when packet stress/repro artifact paths are outside the boundary."""


@dataclass(frozen=True)
class PreActionPacketArtifactCheck:
    reproducibility_status: str
    action_readiness: str
    recommended_human_decision: str
    artifact_count: int
    blocker_count: int
    mismatch_count: int
    missing_artifact_count: int
    malformed_artifact_count: int
    json_digest_match: bool
    markdown_digest_match: bool
    reproducibility_is_not_permission: bool
    digest_equality_is_not_truth: bool
    must_not_execute_automatically: bool
    state_change: str
    authority: str
    blockers: tuple[str, ...]
    expected_json_digest: str
    actual_json_digest: str
    expected_markdown_digest: str
    actual_markdown_digest: str


@dataclass(frozen=True)
class PreActionPacketStressReproCaseResult:
    case_id: str
    description: str
    expected_operator_posture: str
    actual_operator_posture: str
    expected_action_readiness: str
    actual_action_readiness: str
    expected_human_decision: str
    actual_human_decision: str
    expected_reproducibility_status: str = ""
    actual_reproducibility_status: str = ""
    expected_error_contains: str = ""
    actual_error: str = ""
    blocker_count: int = 0
    boundary_error: bool = False
    passed: bool = False


@dataclass(frozen=True)
class PreActionPacketStressReproReport:
    case_count: int
    pass_count: int
    fail_count: int
    all_cases_passed: bool
    blocked_case_count: int
    human_review_case_count: int
    reproducible_case_count: int
    mismatch_case_count: int
    boundary_error_count: int
    blocker_count: int
    stress_pass_is_not_permission: bool
    reproducibility_is_not_permission: bool
    digest_equality_is_not_truth: bool
    must_not_execute_automatically: bool
    state_change: str
    authority: str
    cases: tuple[PreActionPacketStressReproCaseResult, ...]


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _resolve_artifact_path(path: str | Path, *, root: str | Path | None) -> Path:
    root_path = Path.cwd() if root is None else Path(root)
    resolved_root = root_path.resolve()
    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = resolved_root / candidate
    resolved = candidate.resolve()

    try:
        resolved.relative_to(resolved_root)
    except ValueError as exc:
        raise PreActionPacketStressError("packet artifact path escapes root") from exc
    if any(part.casefold() == ".cerebro" for part in resolved.parts):
        raise PreActionPacketStressError("packet artifact path may not live under .cerebro")
    return resolved


def check_pre_action_packet_artifacts(
    packet: PreActionDecisionPacket,
    *,
    json_path: str | Path,
    markdown_path: str | Path,
    root: str | Path | None = None,
) -> PreActionPacketArtifactCheck:
    expected_json = render_pre_action_decision_packet_json(packet)
    expected_markdown = render_pre_action_decision_packet_markdown(packet)
    blockers: list[str] = []
    missing = 0
    malformed = 0
    mismatch = 0

    json_artifact = _resolve_artifact_path(json_path, root=root)
    markdown_artifact = _resolve_artifact_path(markdown_path, root=root)

    actual_json = ""
    actual_markdown = ""
    try:
        actual_json = json_artifact.read_text(encoding="utf-8")
    except FileNotFoundError:
        missing += 1
        blockers.append(f"missing_artifact:{json_artifact.name}")
    else:
        try:
            json.loads(actual_json)
        except JSONDecodeError:
            malformed += 1
            blockers.append(f"malformed_json_artifact:{json_artifact.name}")

    try:
        actual_markdown = markdown_artifact.read_text(encoding="utf-8")
    except FileNotFoundError:
        missing += 1
        blockers.append(f"missing_artifact:{markdown_artifact.name}")

    json_digest_match = bool(actual_json) and actual_json == expected_json
    markdown_digest_match = bool(actual_markdown) and actual_markdown == expected_markdown
    if actual_json and not json_digest_match:
        mismatch += 1
        blockers.append(f"stale_artifact:{json_artifact.name}")
    if actual_markdown and not markdown_digest_match:
        mismatch += 1
        blockers.append(f"stale_artifact:{markdown_artifact.name}")

    status = "reproducible" if not blockers and json_digest_match and markdown_digest_match else "blocked"
    return PreActionPacketArtifactCheck(
        reproducibility_status=status,
        action_readiness="advisory_report_allowed" if status == "reproducible" else "blocked",
        recommended_human_decision="none" if status == "reproducible" else "review_blockers",
        artifact_count=2,
        blocker_count=len(blockers),
        mismatch_count=mismatch,
        missing_artifact_count=missing,
        malformed_artifact_count=malformed,
        json_digest_match=json_digest_match,
        markdown_digest_match=markdown_digest_match,
        reproducibility_is_not_permission=True,
        digest_equality_is_not_truth=True,
        must_not_execute_automatically=True,
        state_change="none",
        authority="non-authoritative; advisory pre-action packet reproducibility check only",
        blockers=tuple(blockers),
        expected_json_digest=_digest(expected_json),
        actual_json_digest=_digest(actual_json) if actual_json else "",
        expected_markdown_digest=_digest(expected_markdown),
        actual_markdown_digest=_digest(actual_markdown) if actual_markdown else "",
    )


def _proposed_action(case_id: str) -> ProposedAction:
    return ProposedAction(
        action_id=case_id,
        intent=f"Stress pre-action decision packet case {case_id}.",
        action_kind="derived_experiment",
        proposed_by="operator",
        created_at="2026-04-24",
        expected_state_change="none",
        notes=("packet stress case; advisory only",),
    )


def _packet_for_scenario(case_id: str, scenario) -> PreActionDecisionPacket:
    envelope = evaluate_decision_scenario(scenario)
    report = build_pre_action_guard_report(_proposed_action(case_id), (envelope,))
    stress = build_default_pre_action_stress_matrix()
    return build_pre_action_decision_packet(report, stress)


def _failed_stress() -> PreActionStressMatrixReport:
    return PreActionStressMatrixReport(
        case_count=1,
        pass_count=0,
        fail_count=1,
        all_cases_passed=False,
        blocked_or_human_count=0,
        blocker_count=1,
        boundary_error_count=0,
        stress_pass_is_not_permission=True,
        must_not_execute_automatically=True,
        state_change="none",
        authority="non-authoritative; advisory pre-action stress matrix only",
        cases=(),
    )


def _case_from_packet(
    *,
    case_id: str,
    description: str,
    packet: PreActionDecisionPacket,
    expected_operator_posture: str,
    expected_action_readiness: str,
    expected_human_decision: str,
) -> PreActionPacketStressReproCaseResult:
    passed = (
        packet.operator_posture == expected_operator_posture
        and packet.action_readiness == expected_action_readiness
        and packet.recommended_human_decision == expected_human_decision
        and packet.state_change == "none"
        and packet.packet_is_not_permission
        and packet.must_not_execute_automatically
    )
    return PreActionPacketStressReproCaseResult(
        case_id=case_id,
        description=description,
        expected_operator_posture=expected_operator_posture,
        actual_operator_posture=packet.operator_posture,
        expected_action_readiness=expected_action_readiness,
        actual_action_readiness=packet.action_readiness,
        expected_human_decision=expected_human_decision,
        actual_human_decision=packet.recommended_human_decision,
        blocker_count=packet.packet_blocker_count,
        passed=passed,
    )


def _case_from_repro(
    *,
    case_id: str,
    description: str,
    check: PreActionPacketArtifactCheck,
    expected_reproducibility_status: str,
) -> PreActionPacketStressReproCaseResult:
    passed = (
        check.reproducibility_status == expected_reproducibility_status
        and check.state_change == "none"
        and check.reproducibility_is_not_permission
        and check.digest_equality_is_not_truth
    )
    return PreActionPacketStressReproCaseResult(
        case_id=case_id,
        description=description,
        expected_operator_posture="not_applicable",
        actual_operator_posture="not_applicable",
        expected_action_readiness="advisory_report_allowed"
        if expected_reproducibility_status == "reproducible"
        else "blocked",
        actual_action_readiness=check.action_readiness,
        expected_human_decision="none" if expected_reproducibility_status == "reproducible" else "review_blockers",
        actual_human_decision=check.recommended_human_decision,
        expected_reproducibility_status=expected_reproducibility_status,
        actual_reproducibility_status=check.reproducibility_status,
        blocker_count=check.blocker_count,
        passed=passed,
    )


def _case_from_boundary_error(
    *,
    case_id: str,
    description: str,
    expected_error_contains: str,
    actual_error: str,
) -> PreActionPacketStressReproCaseResult:
    return PreActionPacketStressReproCaseResult(
        case_id=case_id,
        description=description,
        expected_operator_posture="not_applicable",
        actual_operator_posture="not_applicable",
        expected_action_readiness="blocked",
        actual_action_readiness="blocked",
        expected_human_decision="review_blockers",
        actual_human_decision="review_blockers",
        expected_error_contains=expected_error_contains,
        actual_error=actual_error,
        blocker_count=1,
        boundary_error=True,
        passed=expected_error_contains in actual_error,
    )


def build_pre_action_packet_stress_repro_report(
    packet: PreActionDecisionPacket,
    *,
    json_path: str | Path,
    markdown_path: str | Path,
    root: str | Path | None = None,
    degraded_artifact_root: str | Path | None = None,
) -> PreActionPacketStressReproReport:
    clean_packet = _case_from_packet(
        case_id="clean_packet",
        description="Clean packet remains go_for_advisory_review without granting permission.",
        packet=packet,
        expected_operator_posture="go_for_advisory_review",
        expected_action_readiness=packet.action_readiness,
        expected_human_decision="none",
    )
    blocked_report_packet = _case_from_packet(
        case_id="blocked_report_packet",
        description="A packet built from a runtime/canonical mutation report remains blocked.",
        packet=_packet_for_scenario("blocked_report_packet", missing_trigger_for_runtime_mutation()),
        expected_operator_posture="no_go_blocked",
        expected_action_readiness="blocked",
        expected_human_decision="review_blockers",
    )
    human_review_packet = _case_from_packet(
        case_id="human_review_packet",
        description="A packet with insufficient evidence requires human review instead of action.",
        packet=_packet_for_scenario("human_review_packet", silence_is_not_negative_evidence()),
        expected_operator_posture="go_requires_human_review",
        expected_action_readiness="human_approval_required",
        expected_human_decision="provide_missing_evidence",
    )
    failed_stress_packet = _case_from_packet(
        case_id="failed_stress_packet",
        description="A clean report paired with a failed stress matrix is blocked.",
        packet=build_pre_action_decision_packet(
            build_pre_action_guard_report(
                _proposed_action("failed_stress_packet"),
                (evaluate_decision_scenario(clean_advisory_report()),),
            ),
            _failed_stress(),
        ),
        expected_operator_posture="no_go_blocked",
        expected_action_readiness="blocked",
        expected_human_decision="review_blockers",
    )

    reproducible = _case_from_repro(
        case_id="reproducible_checked_artifacts",
        description="Checked packet JSON/Markdown exactly match regenerated output.",
        check=check_pre_action_packet_artifacts(
            packet,
            json_path=json_path,
            markdown_path=markdown_path,
            root=root,
        ),
        expected_reproducibility_status="reproducible",
    )

    cases: list[PreActionPacketStressReproCaseResult] = [
        clean_packet,
        blocked_report_packet,
        human_review_packet,
        failed_stress_packet,
        reproducible,
    ]

    if degraded_artifact_root is not None:
        degraded_root = Path(degraded_artifact_root).resolve()
        degraded_root.mkdir(parents=True, exist_ok=True)
        expected_json = render_pre_action_decision_packet_json(packet)
        expected_markdown = render_pre_action_decision_packet_markdown(packet)
        good_markdown = degraded_root / "packet.md"
        good_markdown.write_text(expected_markdown, encoding="utf-8")

        stale_json = degraded_root / "stale_packet.json"
        stale_json.write_text(
            expected_json.replace('"packet_blocker_count": 0', '"packet_blocker_count": 999'),
            encoding="utf-8",
        )
        cases.append(
            _case_from_repro(
                case_id="stale_json_artifact",
                description="A stale checked JSON packet artifact is blocked.",
                check=check_pre_action_packet_artifacts(
                    packet,
                    json_path=stale_json,
                    markdown_path=good_markdown,
                    root=degraded_root,
                ),
                expected_reproducibility_status="blocked",
            )
        )

        malformed_json = degraded_root / "malformed_packet.json"
        malformed_json.write_text("{", encoding="utf-8")
        cases.append(
            _case_from_repro(
                case_id="malformed_json_artifact",
                description="A malformed checked JSON packet artifact is blocked.",
                check=check_pre_action_packet_artifacts(
                    packet,
                    json_path=malformed_json,
                    markdown_path=good_markdown,
                    root=degraded_root,
                ),
                expected_reproducibility_status="blocked",
            )
        )

        cases.append(
            _case_from_repro(
                case_id="missing_json_artifact",
                description="A missing checked packet artifact is blocked.",
                check=check_pre_action_packet_artifacts(
                    packet,
                    json_path=degraded_root / "missing_packet.json",
                    markdown_path=good_markdown,
                    root=degraded_root,
                ),
                expected_reproducibility_status="blocked",
            )
        )

        try:
            check_pre_action_packet_artifacts(
                packet,
                json_path=degraded_root.parent / "outside_packet.json",
                markdown_path=good_markdown,
                root=degraded_root,
            )
        except PreActionPacketStressError as exc:
            cases.append(
                _case_from_boundary_error(
                    case_id="root_escape_artifact",
                    description="A checked artifact path outside the declared root fails closed.",
                    expected_error_contains="escapes root",
                    actual_error=str(exc),
                )
            )

        try:
            check_pre_action_packet_artifacts(
                packet,
                json_path=degraded_root / ".cerebro" / "packet.json",
                markdown_path=good_markdown,
                root=degraded_root,
            )
        except PreActionPacketStressError as exc:
            cases.append(
                _case_from_boundary_error(
                    case_id="cerebro_state_artifact_target",
                    description="A checked artifact path under .cerebro fails closed.",
                    expected_error_contains=".cerebro",
                    actual_error=str(exc),
                )
            )

    return PreActionPacketStressReproReport(
        case_count=len(cases),
        pass_count=sum(1 for case in cases if case.passed),
        fail_count=sum(1 for case in cases if not case.passed),
        all_cases_passed=all(case.passed for case in cases),
        blocked_case_count=sum(1 for case in cases if case.actual_action_readiness == "blocked"),
        human_review_case_count=sum(1 for case in cases if case.actual_action_readiness == "human_approval_required"),
        reproducible_case_count=sum(1 for case in cases if case.actual_reproducibility_status == "reproducible"),
        mismatch_case_count=sum(1 for case in cases if case.actual_reproducibility_status == "blocked"),
        boundary_error_count=sum(1 for case in cases if case.boundary_error),
        blocker_count=sum(case.blocker_count for case in cases),
        stress_pass_is_not_permission=True,
        reproducibility_is_not_permission=True,
        digest_equality_is_not_truth=True,
        must_not_execute_automatically=True,
        state_change="none",
        authority="non-authoritative; advisory pre-action packet stress/repro report only",
        cases=tuple(cases),
    )


def render_pre_action_packet_stress_repro_json(report: PreActionPacketStressReproReport) -> str:
    return json.dumps(asdict(report), indent=2, sort_keys=True) + "\n"


def render_pre_action_packet_stress_repro_markdown(report: PreActionPacketStressReproReport) -> str:
    lines = [
        "# Epistemic Guard Pre-Action Packet Stress/Repro Report",
        "",
        "- state_change: none",
        "- authority: non-authoritative; advisory pre-action packet stress/repro report only",
        "- stress_pass_is_not_permission: true",
        "- reproducibility_is_not_permission: true",
        "- digest_equality_is_not_truth: true",
        "- must_not_execute_automatically: true",
        "- silence_is_not_negative_evidence: true",
        "",
        "## Summary",
        "",
        f"- case_count: {report.case_count}",
        f"- pass_count: {report.pass_count}",
        f"- fail_count: {report.fail_count}",
        f"- all_cases_passed: {str(report.all_cases_passed).lower()}",
        f"- blocked_case_count: {report.blocked_case_count}",
        f"- human_review_case_count: {report.human_review_case_count}",
        f"- reproducible_case_count: {report.reproducible_case_count}",
        f"- mismatch_case_count: {report.mismatch_case_count}",
        f"- boundary_error_count: {report.boundary_error_count}",
        f"- blocker_count: {report.blocker_count}",
        "",
        "## Cases",
        "",
    ]
    for case in report.cases:
        lines.extend(
            [
                f"### {case.case_id}",
                "",
                f"- description: {case.description}",
                f"- expected_operator_posture: {case.expected_operator_posture}",
                f"- actual_operator_posture: {case.actual_operator_posture}",
                f"- expected_action_readiness: {case.expected_action_readiness}",
                f"- actual_action_readiness: {case.actual_action_readiness}",
                f"- expected_human_decision: {case.expected_human_decision}",
                f"- actual_human_decision: {case.actual_human_decision}",
                f"- expected_reproducibility_status: {case.expected_reproducibility_status or 'not_applicable'}",
                f"- actual_reproducibility_status: {case.actual_reproducibility_status or 'not_applicable'}",
                f"- blocker_count: {case.blocker_count}",
                f"- boundary_error: {str(case.boundary_error).lower()}",
                f"- passed: {str(case.passed).lower()}",
                f"- actual_error: {case.actual_error or 'none'}",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"
