from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import tempfile
from typing import Any

from .operator_evidence_review_capsule import (
    OperatorEvidenceReviewCapsule,
    build_operator_evidence_review_capsule,
)


OPERATOR_EVIDENCE_REVIEW_CAPSULE_STRESS_MATRIX_SCHEMA_VERSION = "1"
OPERATOR_EVIDENCE_REVIEW_CAPSULE_STRESS_MATRIX_AUTHORITY = (
    "non-authoritative; advisory operator evidence review capsule stress matrix only"
)

_SCENARIO_IDS = (
    "clean_review_capsule",
    "missing_decision_packet",
    "malformed_reproducibility_input",
    "mutating_provenance_input",
    "root_escape_input",
    "cerebro_state_input",
    "stale_reproducibility_input",
    "failed_stress_input",
    "provenance_blocker_input",
)

_INPUT_PATHS = {
    "operator_decision_packet": "packet.json",
    "intake_reproducibility": "repro.json",
    "provenance_index": "provenance.json",
    "provenance_stress_matrix": "stress.json",
}


@dataclass(frozen=True)
class OperatorEvidenceReviewCapsuleStressScenario:
    scenario_id: str
    title: str
    purpose: str
    expected_recommended_human_decision: str
    expected_action_readiness: str
    observed_recommended_human_decision: str
    observed_action_readiness: str
    observed_review_status: str
    review_summary: str
    blocker_count: int
    input_blocker_count: int
    missing_review_evidence_count: int
    boundary_error_count: int
    expected_error: bool = False
    observed_error: str = ""
    state_change: str = "none"
    authority: str = OPERATOR_EVIDENCE_REVIEW_CAPSULE_STRESS_MATRIX_AUTHORITY

    def __post_init__(self) -> None:
        if self.scenario_id not in _SCENARIO_IDS:
            raise ValueError(f"unknown operator evidence review capsule stress scenario: {self.scenario_id}")
        if self.state_change != "none":
            raise ValueError("operator evidence review capsule stress scenarios must not change state")
        if self.authority != OPERATOR_EVIDENCE_REVIEW_CAPSULE_STRESS_MATRIX_AUTHORITY:
            raise ValueError(
                f"unsupported review capsule stress scenario authority: {self.authority}"
            )
        if not self.review_summary:
            raise ValueError("operator evidence review capsule stress scenarios require review_summary")
        for field_name, value in (
            ("blocker_count", self.blocker_count),
            ("input_blocker_count", self.input_blocker_count),
            ("missing_review_evidence_count", self.missing_review_evidence_count),
            ("boundary_error_count", self.boundary_error_count),
        ):
            if value < 0:
                raise ValueError(f"{field_name} must be non-negative")
        if self.observed_action_readiness == "blocked" and not (
            self.blocker_count
            or self.input_blocker_count
            or self.missing_review_evidence_count
            or self.boundary_error_count
            or self.observed_error
        ):
            raise ValueError("blocked review capsule stress scenarios must expose visible evidence")

    @property
    def passed(self) -> bool:
        return (
            self.observed_recommended_human_decision
            == self.expected_recommended_human_decision
            and self.observed_action_readiness == self.expected_action_readiness
            and bool(self.observed_error) is self.expected_error
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "title": self.title,
            "purpose": self.purpose,
            "state_change": self.state_change,
            "authority": self.authority,
            "expected": {
                "recommended_human_decision": self.expected_recommended_human_decision,
                "action_readiness": self.expected_action_readiness,
                "visible_error": self.expected_error,
            },
            "observed": {
                "recommended_human_decision": self.observed_recommended_human_decision,
                "action_readiness": self.observed_action_readiness,
                "review_status": self.observed_review_status,
                "visible_error": bool(self.observed_error),
                "error": self.observed_error,
            },
            "passed": self.passed,
            "review_summary": self.review_summary,
            "blocker_count": self.blocker_count,
            "input_blocker_count": self.input_blocker_count,
            "missing_review_evidence_count": self.missing_review_evidence_count,
            "boundary_error_count": self.boundary_error_count,
            "forbidden_interpretations": [
                "treat review capsule stress output as permission",
                "treat review capsule output as permission",
                "hide degraded capsule input",
                "treat passing scenarios as permission",
                "treat digest equality as truth",
                "write memory from review capsule evidence",
                "register sources from review capsule evidence",
                "promote review capsule evidence to runtime authority",
                "infer negative evidence from silence",
            ],
        }


@dataclass(frozen=True)
class OperatorEvidenceReviewCapsuleStressMatrixReport:
    scenarios: tuple[OperatorEvidenceReviewCapsuleStressScenario, ...]
    state_change: str = "none"
    authority: str = OPERATOR_EVIDENCE_REVIEW_CAPSULE_STRESS_MATRIX_AUTHORITY
    matrix_role: str = "advisory degraded-evidence operator evidence review capsule stress matrix only"

    def __post_init__(self) -> None:
        if self.state_change != "none":
            raise ValueError("operator evidence review capsule stress matrix must not change state")
        if self.authority != OPERATOR_EVIDENCE_REVIEW_CAPSULE_STRESS_MATRIX_AUTHORITY:
            raise ValueError(
                f"unsupported review capsule stress matrix authority: {self.authority}"
            )
        scenario_ids = tuple(scenario.scenario_id for scenario in self.scenarios)
        if len(set(scenario_ids)) != len(scenario_ids):
            raise ValueError("operator evidence review capsule stress scenario ids must be unique")
        if scenario_ids != _SCENARIO_IDS:
            raise ValueError(
                "operator evidence review capsule stress matrix must contain the "
                "closed scenario set in stable order"
            )
        for scenario in self.scenarios:
            if scenario.state_change != "none":
                raise ValueError("review capsule stress scenarios must preserve state_change none")

    @property
    def pass_count(self) -> int:
        return sum(1 for scenario in self.scenarios if scenario.passed)

    @property
    def fail_count(self) -> int:
        return len(self.scenarios) - self.pass_count

    @property
    def all_scenarios_passed(self) -> bool:
        return self.fail_count == 0

    @property
    def blocker_count(self) -> int:
        return sum(scenario.blocker_count for scenario in self.scenarios)

    @property
    def degraded_blocker_count(self) -> int:
        return sum(
            scenario.blocker_count
            for scenario in self.scenarios
            if scenario.scenario_id != "clean_review_capsule"
        )

    @property
    def input_blocker_count(self) -> int:
        return sum(scenario.input_blocker_count for scenario in self.scenarios)

    @property
    def missing_review_evidence_count(self) -> int:
        return sum(scenario.missing_review_evidence_count for scenario in self.scenarios)

    @property
    def boundary_error_count(self) -> int:
        return sum(scenario.boundary_error_count for scenario in self.scenarios)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": OPERATOR_EVIDENCE_REVIEW_CAPSULE_STRESS_MATRIX_SCHEMA_VERSION,
            "state_change": self.state_change,
            "authority": self.authority,
            "matrix_role": self.matrix_role,
            "summary": {
                "scenario_count": len(self.scenarios),
                "pass_count": self.pass_count,
                "fail_count": self.fail_count,
                "all_scenarios_passed": self.all_scenarios_passed,
                "blocker_count": self.blocker_count,
                "degraded_blocker_count": self.degraded_blocker_count,
                "input_blocker_count": self.input_blocker_count,
                "missing_review_evidence_count": self.missing_review_evidence_count,
                "boundary_error_count": self.boundary_error_count,
                "scenario_ids": list(_SCENARIO_IDS),
                "decisions": {
                    scenario.scenario_id: {
                        "recommended_human_decision": (
                            scenario.observed_recommended_human_decision
                        ),
                        "action_readiness": scenario.observed_action_readiness,
                        "review_status": scenario.observed_review_status,
                        "visible_error": bool(scenario.observed_error),
                        "boundary_error_count": scenario.boundary_error_count,
                    }
                    for scenario in self.scenarios
                },
            },
            "scenarios": [scenario.to_dict() for scenario in self.scenarios],
            "guardrails": {
                "registered_is_not_true": True,
                "retrieved_is_not_relevant": True,
                "remembered_is_not_trusted": True,
                "silence_is_not_negative_evidence": True,
                "review_capsule_stress_matrix_is_not_permission": True,
                "review_capsule_stress_matrix_is_not_memory": True,
                "review_capsule_stress_matrix_is_not_authority": True,
                "review_capsule_stress_matrix_is_not_runtime_gate": True,
                "review_capsule_stress_matrix_is_not_claim_graph": True,
                "review_capsule_stress_matrix_is_not_source_registry": True,
                "review_capsule_output_is_not_permission": True,
                "passing_scenario_is_not_permission": True,
                "digest_equality_is_not_truth": True,
                "degraded_capsule_evidence_is_review_evidence_only": True,
                "boundary_error_is_review_blocker_not_exception": True,
            },
            "boundary": {
                "may_suggest": [
                    "compare review capsule output under degraded input evidence",
                    "show missing capsule inputs as blockers",
                    "show malformed capsule inputs as blockers",
                    "show mutating capsule inputs as blockers",
                    "show root escapes and .cerebro targets as boundary blockers",
                    "show stale reproducibility as blocking review evidence",
                    "show failed upstream stress matrices as blocking review evidence",
                    "recommend future hardening slices",
                ],
                "must_not_apply": [
                    "mutate state",
                    "register sources",
                    "refresh artifacts automatically",
                    "update replay baseline",
                    "write memory automatically",
                    "act as runtime gate",
                    "create canonical claim graph",
                    "create canonical evidence graph",
                    "promote or demote authority",
                    "treat review capsule output as permission",
                    "treat stress matrix output as permission",
                    "treat passing scenarios as permission",
                    "treat digest equality as truth",
                    "hide blockers",
                    "hide malformed capsule input",
                    "hide stale or mismatched reproducibility",
                    "hide failed upstream stress coverage",
                    "infer negative evidence from silence",
                ],
            },
        }


def build_operator_evidence_review_capsule_stress_matrix() -> OperatorEvidenceReviewCapsuleStressMatrixReport:
    with tempfile.TemporaryDirectory(prefix="cerebro-review-capsule-stress-") as tmp_dir:
        root = Path(tmp_dir)
        outside_path = root / "outside-packet.json"
        outside_path.write_text(json.dumps(_packet_payload(), sort_keys=True), encoding="utf-8")
        scenarios = (
            _scenario(
                root,
                "clean_review_capsule",
                "Clean review capsule remains advisory",
                "Proves complete capsule evidence stays review-clear without becoming permission.",
            ),
            _scenario(
                root,
                "missing_decision_packet",
                "Missing decision packet blocks review",
                "Proves an absent required input becomes missing review evidence.",
                overrides={"operator_decision_packet": "missing-packet.json"},
                expected_error=True,
            ),
            _scenario(
                root,
                "malformed_reproducibility_input",
                "Malformed reproducibility blocks review",
                "Proves malformed JSON stays visible to the operator.",
                mutate=lambda project_root: (project_root / "repro.json").write_text(
                    "{not-json",
                    encoding="utf-8",
                ),
                expected_error=True,
            ),
            _scenario(
                root,
                "mutating_provenance_input",
                "Mutating provenance input blocks review",
                "Proves state-changing evidence cannot pass as advisory capsule input.",
                mutate=lambda project_root: _write_json(
                    project_root / "provenance.json",
                    _provenance_payload(state_change="canonical-mutation"),
                ),
                expected_error=True,
            ),
            _scenario(
                root,
                "root_escape_input",
                "Root escape blocks review",
                "Proves absolute paths outside the project root are visible boundary blockers.",
                overrides={"operator_decision_packet": str(outside_path)},
                expected_error=True,
            ),
            _scenario(
                root,
                "cerebro_state_input",
                ".cerebro target blocks review",
                "Proves canonical state boundary targets are rejected as review evidence.",
                overrides={"operator_decision_packet": ".cerebro/state.json"},
                expected_error=True,
            ),
            _scenario(
                root,
                "stale_reproducibility_input",
                "Stale reproducibility blocks review",
                "Proves digest mismatch and stale reproducibility remain blocking evidence.",
                mutate=lambda project_root: _write_json(
                    project_root / "repro.json",
                    _repro_payload(
                        reproducibility_status="stale_or_mismatched",
                        digest_match=False,
                        mismatch_count=1,
                    ),
                ),
                expected_error=True,
            ),
            _scenario(
                root,
                "failed_stress_input",
                "Failed upstream stress blocks review",
                "Proves failed upstream stress coverage blocks the review capsule.",
                mutate=lambda project_root: _write_json(
                    project_root / "stress.json",
                    _stress_payload(all_scenarios_passed=False, pass_count=8, fail_count=1),
                ),
                expected_error=True,
            ),
            _scenario(
                root,
                "provenance_blocker_input",
                "Provenance blocker blocks review",
                "Proves missing provenance artifacts remain visible as review blockers.",
                mutate=lambda project_root: _write_json(
                    project_root / "provenance.json",
                    _provenance_payload(
                        artifact_count=2,
                        present_count=1,
                        blocked=True,
                        blocker_count=1,
                    ),
                ),
                expected_error=True,
            ),
        )
        return OperatorEvidenceReviewCapsuleStressMatrixReport(scenarios=scenarios)


def render_operator_evidence_review_capsule_stress_matrix_json(
    report: OperatorEvidenceReviewCapsuleStressMatrixReport,
) -> str:
    return json.dumps(report.to_dict(), indent=2, sort_keys=True) + "\n"


def render_operator_evidence_review_capsule_stress_matrix_markdown(
    report: OperatorEvidenceReviewCapsuleStressMatrixReport,
) -> str:
    lines = [
        "# Epistemic Readiness Operator Evidence Review Capsule Stress Matrix",
        "",
        "## Boundary",
        "",
        f"- state_change: {report.state_change}",
        f"- authority: {report.authority}",
        f"- matrix_role: {report.matrix_role}",
        "- review_capsule_stress_matrix_is_not_permission: true",
        "- review_capsule_stress_matrix_is_not_memory: true",
        "- review_capsule_stress_matrix_is_not_authority: true",
        "- review_capsule_stress_matrix_is_not_runtime_gate: true",
        "- review_capsule_stress_matrix_is_not_claim_graph: true",
        "- review_capsule_stress_matrix_is_not_source_registry: true",
        "- review_capsule_output_is_not_permission: true",
        "- passing_scenario_is_not_permission: true",
        "- digest_equality_is_not_truth: true",
        "- degraded_capsule_evidence_is_review_evidence_only: true",
        "- boundary_error_is_review_blocker_not_exception: true",
        "- silence_is_not_negative_evidence: true",
        "",
        "## Summary",
        "",
        f"- scenario_count: {len(report.scenarios)}",
        f"- pass_count: {report.pass_count}",
        f"- fail_count: {report.fail_count}",
        f"- all_scenarios_passed: {_json_bool(report.all_scenarios_passed)}",
        f"- blocker_count: {report.blocker_count}",
        f"- degraded_blocker_count: {report.degraded_blocker_count}",
        f"- input_blocker_count: {report.input_blocker_count}",
        f"- missing_review_evidence_count: {report.missing_review_evidence_count}",
        f"- boundary_error_count: {report.boundary_error_count}",
        "",
        "## Scenarios",
        "",
        "| Scenario | Expected Decision | Observed Decision | Observed Readiness | Review Status | Blockers | Boundary Errors | Passed |",
        "|---|---|---|---|---|---:|---:|---|",
    ]
    for scenario in report.scenarios:
        lines.append(
            "| "
            f"`{scenario.scenario_id}` | "
            f"`{scenario.expected_recommended_human_decision}` | "
            f"`{scenario.observed_recommended_human_decision}` | "
            f"`{scenario.observed_action_readiness}` | "
            f"`{scenario.observed_review_status}` | "
            f"{scenario.blocker_count} | "
            f"{scenario.boundary_error_count} | "
            f"`{_json_bool(scenario.passed)}` |"
        )
    visible_errors = [scenario for scenario in report.scenarios if scenario.observed_error]
    if visible_errors:
        lines.extend(["", "## Visible Errors", ""])
        for scenario in visible_errors:
            lines.append(f"- `{scenario.scenario_id}`: {scenario.observed_error}")
    lines.extend(["", "## Must Not Apply", ""])
    for item in report.to_dict()["boundary"]["must_not_apply"]:
        lines.append(f"- {item}")
    return "\n".join(lines) + "\n"


def _scenario(
    root: Path,
    scenario_id: str,
    title: str,
    purpose: str,
    *,
    overrides: dict[str, str] | None = None,
    mutate: Any = None,
    expected_error: bool = False,
) -> OperatorEvidenceReviewCapsuleStressScenario:
    project_root = root / scenario_id
    project_root.mkdir()
    _write_clean_fixture(project_root)
    if mutate is not None:
        mutate(project_root)
    input_paths = dict(_INPUT_PATHS)
    if overrides:
        input_paths.update(overrides)

    expected_decision = "review_blockers" if expected_error else "none"
    expected_readiness = "blocked" if expected_error else "advisory_report_allowed"

    try:
        capsule = build_operator_evidence_review_capsule(project_root, input_paths)
    except Exception as exc:
        return OperatorEvidenceReviewCapsuleStressScenario(
            scenario_id=scenario_id,
            title=title,
            purpose=purpose,
            expected_recommended_human_decision=expected_decision,
            expected_action_readiness=expected_readiness,
            observed_recommended_human_decision="exception",
            observed_action_readiness="blocked",
            observed_review_status="exception",
            review_summary=f"exception: {exc}",
            blocker_count=0,
            input_blocker_count=0,
            missing_review_evidence_count=0,
            boundary_error_count=0,
            expected_error=expected_error,
            observed_error=f"exception: {exc}",
        )

    visible_error = "; ".join(capsule.blockers)
    return OperatorEvidenceReviewCapsuleStressScenario(
        scenario_id=scenario_id,
        title=title,
        purpose=purpose,
        expected_recommended_human_decision=expected_decision,
        expected_action_readiness=expected_readiness,
        observed_recommended_human_decision=capsule.recommended_human_decision,
        observed_action_readiness=capsule.action_readiness,
        observed_review_status=capsule.review_status,
        review_summary=_capsule_summary(capsule),
        blocker_count=len(capsule.blockers),
        input_blocker_count=capsule.input_blocker_count,
        missing_review_evidence_count=len(capsule.missing_review_evidence),
        boundary_error_count=_boundary_error_count(capsule.blockers),
        expected_error=expected_error,
        observed_error=visible_error,
    )


def _write_clean_fixture(project_root: Path) -> None:
    _write_json(project_root / "packet.json", _packet_payload())
    _write_json(project_root / "repro.json", _repro_payload())
    _write_json(project_root / "provenance.json", _provenance_payload())
    _write_json(project_root / "stress.json", _stress_payload())


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")


def _packet_payload() -> dict[str, Any]:
    return {
        "schema_version": "1",
        "state_change": "none",
        "authority": "non-authoritative; advisory operator decision packet evidence only",
        "summary": {
            "recommended_human_decision": "none",
            "action_readiness": "no_action",
            "blocker_count": 0,
            "missing_evidence_count": 0,
        },
    }


def _repro_payload(
    *,
    reproducibility_status: str = "reproducible",
    digest_match: bool = True,
    mismatch_count: int = 0,
) -> dict[str, Any]:
    return {
        "schema_version": "1",
        "state_change": "none",
        "authority": (
            "non-authoritative; advisory operator evidence intake reproducibility check only"
        ),
        "summary": {
            "recommended_human_decision": "none",
            "action_readiness": "advisory_report_allowed",
            "reproducibility_status": reproducibility_status,
            "digest_match": digest_match,
            "blocker_count": 0,
            "mismatch_count": mismatch_count,
        },
    }


def _provenance_payload(
    *,
    state_change: str = "none",
    artifact_count: int = 2,
    present_count: int = 2,
    blocked: bool = False,
    blocker_count: int = 0,
) -> dict[str, Any]:
    return {
        "schema_version": "1",
        "state_change": state_change,
        "authority": "non-authoritative; advisory operator evidence provenance index only",
        "summary": {
            "recommended_human_decision": "none",
            "action_readiness": "advisory_report_allowed",
            "artifact_count": artifact_count,
            "present_count": present_count,
            "dependency_edge_count": 1,
            "digest_manifest": "a" * 64,
            "blocked": blocked,
            "blocker_count": blocker_count,
        },
    }


def _stress_payload(
    *,
    all_scenarios_passed: bool = True,
    pass_count: int = 9,
    fail_count: int = 0,
) -> dict[str, Any]:
    return {
        "schema_version": "1",
        "state_change": "none",
        "authority": (
            "non-authoritative; advisory operator evidence provenance stress matrix only"
        ),
        "summary": {
            "recommended_human_decision": "none",
            "action_readiness": "advisory_report_allowed",
            "scenario_count": 9,
            "pass_count": pass_count,
            "fail_count": fail_count,
            "all_scenarios_passed": all_scenarios_passed,
            "blocker_count": 7,
            "boundary_error_count": 4,
            "text_digest_only_count": 1,
        },
    }


def _capsule_summary(capsule: OperatorEvidenceReviewCapsule) -> str:
    return (
        f"review_status={capsule.review_status}; "
        f"recommended_human_decision={capsule.recommended_human_decision}; "
        f"action_readiness={capsule.action_readiness}; "
        f"blocker_count={len(capsule.blockers)}; "
        f"input_blocker_count={capsule.input_blocker_count}; "
        f"missing_review_evidence_count={len(capsule.missing_review_evidence)}"
    )


def _boundary_error_count(blockers: tuple[str, ...]) -> int:
    return sum(
        1
        for blocker in blockers
        if "path escapes project root" in blocker or "canonical state boundary" in blocker
    )


def _json_bool(value: bool) -> str:
    return str(value).lower()


__all__ = [
    "OPERATOR_EVIDENCE_REVIEW_CAPSULE_STRESS_MATRIX_AUTHORITY",
    "OperatorEvidenceReviewCapsuleStressMatrixReport",
    "OperatorEvidenceReviewCapsuleStressScenario",
    "build_operator_evidence_review_capsule_stress_matrix",
    "render_operator_evidence_review_capsule_stress_matrix_json",
    "render_operator_evidence_review_capsule_stress_matrix_markdown",
]
