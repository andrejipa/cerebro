from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import tempfile
from typing import Any

from .operator_evidence_final_review_index import (
    OperatorEvidenceFinalReviewIndexReport,
    build_operator_evidence_final_review_index,
)


OPERATOR_EVIDENCE_FINAL_REVIEW_INDEX_STRESS_MATRIX_SCHEMA_VERSION = "1"
OPERATOR_EVIDENCE_FINAL_REVIEW_INDEX_STRESS_MATRIX_AUTHORITY = (
    "non-authoritative; advisory operator evidence final review index stress matrix only"
)

_SCENARIO_IDS = (
    "clean_final_review_index",
    "missing_review_capsule",
    "malformed_stress_matrix",
    "mutating_reproducibility_check",
    "root_escape_input",
    "cerebro_state_input",
    "blocked_review_capsule",
    "failed_review_capsule_stress_matrix",
    "failed_review_capsule_reproducibility",
    "missing_summary",
)

_INPUT_PATHS = {
    "review_capsule": "capsule.json",
    "review_capsule_stress_matrix": "stress.json",
    "review_capsule_reproducibility": "repro.json",
}


@dataclass(frozen=True)
class OperatorEvidenceFinalReviewIndexStressScenario:
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
    authority: str = OPERATOR_EVIDENCE_FINAL_REVIEW_INDEX_STRESS_MATRIX_AUTHORITY

    def __post_init__(self) -> None:
        if self.scenario_id not in _SCENARIO_IDS:
            raise ValueError(f"unknown final review index stress scenario: {self.scenario_id}")
        if self.state_change != "none":
            raise ValueError("final review index stress scenarios must not change state")
        if self.authority != OPERATOR_EVIDENCE_FINAL_REVIEW_INDEX_STRESS_MATRIX_AUTHORITY:
            raise ValueError(
                f"unsupported final review index stress scenario authority: {self.authority}"
            )
        if not self.review_summary:
            raise ValueError("final review index stress scenarios require review_summary")
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
            raise ValueError("blocked final review index stress scenarios must expose evidence")

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
                "treat final review index stress output as permission",
                "treat final review index output as permission",
                "hide degraded final review input",
                "treat passing scenarios as permission",
                "treat digest equality as truth",
                "write memory from final review evidence",
                "register sources from final review evidence",
                "promote final review evidence to runtime authority",
                "infer negative evidence from silence",
            ],
        }


@dataclass(frozen=True)
class OperatorEvidenceFinalReviewIndexStressMatrixReport:
    scenarios: tuple[OperatorEvidenceFinalReviewIndexStressScenario, ...]
    state_change: str = "none"
    authority: str = OPERATOR_EVIDENCE_FINAL_REVIEW_INDEX_STRESS_MATRIX_AUTHORITY
    matrix_role: str = "advisory degraded-evidence operator evidence final review index stress matrix only"

    def __post_init__(self) -> None:
        if self.state_change != "none":
            raise ValueError("final review index stress matrix must not change state")
        if self.authority != OPERATOR_EVIDENCE_FINAL_REVIEW_INDEX_STRESS_MATRIX_AUTHORITY:
            raise ValueError(f"unsupported final review index stress matrix authority: {self.authority}")
        scenario_ids = tuple(scenario.scenario_id for scenario in self.scenarios)
        if len(set(scenario_ids)) != len(scenario_ids):
            raise ValueError("final review index stress scenario ids must be unique")
        if scenario_ids != _SCENARIO_IDS:
            raise ValueError("final review index stress matrix must contain the closed scenario set")
        for scenario in self.scenarios:
            if scenario.state_change != "none":
                raise ValueError("final review index stress scenarios must preserve state_change none")

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
            if scenario.scenario_id != "clean_final_review_index"
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
            "schema_version": OPERATOR_EVIDENCE_FINAL_REVIEW_INDEX_STRESS_MATRIX_SCHEMA_VERSION,
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
                "final_review_index_stress_matrix_is_not_permission": True,
                "final_review_index_stress_matrix_is_not_memory": True,
                "final_review_index_stress_matrix_is_not_authority": True,
                "final_review_index_stress_matrix_is_not_runtime_gate": True,
                "final_review_index_stress_matrix_is_not_claim_graph": True,
                "final_review_index_stress_matrix_is_not_source_registry": True,
                "final_review_index_output_is_not_permission": True,
                "passing_scenario_is_not_permission": True,
                "digest_equality_is_not_truth": True,
                "degraded_final_review_evidence_is_review_evidence_only": True,
                "boundary_error_is_review_blocker_not_exception": True,
            },
            "boundary": {
                "may_suggest": [
                    "compare final review index output under degraded input evidence",
                    "show missing final review inputs as blockers",
                    "show malformed final review inputs as blockers",
                    "show mutating final review inputs as blockers",
                    "show root escapes and .cerebro targets as boundary blockers",
                    "show failed review capsule evidence as blocking review evidence",
                    "show failed review capsule stress matrices as blocking review evidence",
                    "show stale or failed reproducibility as blocking review evidence",
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
                    "treat final review index output as permission",
                    "treat final review index stress matrix output as permission",
                    "treat passing scenarios as permission",
                    "treat digest equality as truth",
                    "hide blockers",
                    "hide malformed final review input",
                    "hide missing final review input",
                    "hide failed stress coverage",
                    "hide stale or mismatched reproducibility",
                    "infer negative evidence from silence",
                ],
            },
        }


def build_operator_evidence_final_review_index_stress_matrix() -> (
    OperatorEvidenceFinalReviewIndexStressMatrixReport
):
    with tempfile.TemporaryDirectory(prefix="cerebro-final-review-index-stress-") as tmp_dir:
        root = Path(tmp_dir)
        outside_path = root / "outside-capsule.json"
        _write_json(outside_path, _capsule_payload())
        scenarios = (
            _scenario(
                root,
                "clean_final_review_index",
                "Clean final review index remains advisory",
                "Proves complete final review evidence stays clear without becoming permission.",
            ),
            _scenario(
                root,
                "missing_review_capsule",
                "Missing review capsule blocks final review",
                "Proves an absent required final review input becomes visible evidence.",
                overrides={"review_capsule": "missing-capsule.json"},
                expected_error=True,
            ),
            _scenario(
                root,
                "malformed_stress_matrix",
                "Malformed stress matrix blocks final review",
                "Proves malformed JSON stays visible to the operator.",
                mutate=lambda project_root: (project_root / "stress.json").write_text(
                    "{not-json",
                    encoding="utf-8",
                ),
                expected_error=True,
            ),
            _scenario(
                root,
                "mutating_reproducibility_check",
                "Mutating reproducibility blocks final review",
                "Proves state-changing reproducibility evidence cannot pass.",
                mutate=lambda project_root: _write_json(
                    project_root / "repro.json",
                    _repro_payload(state_change="canonical-mutation"),
                ),
                expected_error=True,
            ),
            _scenario(
                root,
                "root_escape_input",
                "Root escape blocks final review",
                "Proves relative paths escaping the project root become boundary blockers.",
                overrides={"review_capsule": "../outside-capsule.json"},
                expected_error=True,
            ),
            _scenario(
                root,
                "cerebro_state_input",
                ".cerebro target blocks final review",
                "Proves canonical state boundary targets are rejected as review evidence.",
                overrides={"review_capsule": ".cerebro/state.json"},
                expected_error=True,
            ),
            _scenario(
                root,
                "blocked_review_capsule",
                "Blocked review capsule blocks final review",
                "Proves a failed capsule summary stays visible instead of becoming clear.",
                mutate=lambda project_root: _write_json(
                    project_root / "capsule.json",
                    _capsule_payload(
                        review_status="blocked_review",
                        recommended_human_decision="review_blockers",
                        action_readiness="blocked",
                        blocker_count=1,
                    ),
                ),
                expected_error=True,
            ),
            _scenario(
                root,
                "failed_review_capsule_stress_matrix",
                "Failed review capsule stress matrix blocks final review",
                "Proves failed upstream stress coverage blocks the final index.",
                mutate=lambda project_root: _write_json(
                    project_root / "stress.json",
                    _stress_payload(all_scenarios_passed=False, pass_count=8, fail_count=1),
                ),
                expected_error=True,
            ),
            _scenario(
                root,
                "failed_review_capsule_reproducibility",
                "Failed reproducibility blocks final review",
                "Proves stale or mismatched checked artifacts remain blocking evidence.",
                mutate=lambda project_root: _write_json(
                    project_root / "repro.json",
                    _repro_payload(
                        reproducibility_status="stale_or_mismatched",
                        recommended_human_decision="review_blockers",
                        action_readiness="blocked",
                        blocker_count=1,
                        mismatch_count=1,
                        json_digest_match=False,
                    ),
                ),
                expected_error=True,
            ),
            _scenario(
                root,
                "missing_summary",
                "Missing summary blocks final review",
                "Proves structurally incomplete JSON cannot pass as review evidence.",
                mutate=lambda project_root: _write_json(
                    project_root / "capsule.json",
                    _without_summary(_capsule_payload()),
                ),
                expected_error=True,
            ),
        )
        return OperatorEvidenceFinalReviewIndexStressMatrixReport(scenarios=scenarios)


def render_operator_evidence_final_review_index_stress_matrix_json(
    report: OperatorEvidenceFinalReviewIndexStressMatrixReport,
) -> str:
    return json.dumps(report.to_dict(), indent=2, sort_keys=True) + "\n"


def render_operator_evidence_final_review_index_stress_matrix_markdown(
    report: OperatorEvidenceFinalReviewIndexStressMatrixReport,
) -> str:
    lines = [
        "# Epistemic Readiness Operator Evidence Final Review Index Stress Matrix",
        "",
        "## Boundary",
        "",
        f"- state_change: {report.state_change}",
        f"- authority: {report.authority}",
        f"- matrix_role: {report.matrix_role}",
        "- final_review_index_stress_matrix_is_not_permission: true",
        "- final_review_index_stress_matrix_is_not_memory: true",
        "- final_review_index_stress_matrix_is_not_authority: true",
        "- final_review_index_stress_matrix_is_not_runtime_gate: true",
        "- final_review_index_stress_matrix_is_not_claim_graph: true",
        "- final_review_index_stress_matrix_is_not_source_registry: true",
        "- final_review_index_output_is_not_permission: true",
        "- passing_scenario_is_not_permission: true",
        "- digest_equality_is_not_truth: true",
        "- degraded_final_review_evidence_is_review_evidence_only: true",
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
) -> OperatorEvidenceFinalReviewIndexStressScenario:
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
        index = build_operator_evidence_final_review_index(project_root, input_paths)
    except Exception as exc:
        return OperatorEvidenceFinalReviewIndexStressScenario(
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

    visible_error = "; ".join(index.blockers)
    return OperatorEvidenceFinalReviewIndexStressScenario(
        scenario_id=scenario_id,
        title=title,
        purpose=purpose,
        expected_recommended_human_decision=expected_decision,
        expected_action_readiness=expected_readiness,
        observed_recommended_human_decision=index.recommended_human_decision,
        observed_action_readiness=index.action_readiness,
        observed_review_status=index.review_status,
        review_summary=_index_summary(index),
        blocker_count=len(index.blockers),
        input_blocker_count=index.input_blocker_count,
        missing_review_evidence_count=len(index.missing_review_evidence),
        boundary_error_count=_boundary_error_count(index.blockers),
        expected_error=expected_error,
        observed_error=visible_error,
    )


def _write_clean_fixture(project_root: Path) -> None:
    _write_json(project_root / "capsule.json", _capsule_payload())
    _write_json(project_root / "stress.json", _stress_payload())
    _write_json(project_root / "repro.json", _repro_payload())


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")


def _capsule_payload(
    *,
    review_status: str = "review_clear",
    recommended_human_decision: str = "none",
    action_readiness: str = "advisory_report_allowed",
    input_blocker_count: int = 0,
    blocker_count: int = 0,
    missing_review_evidence_count: int = 0,
) -> dict[str, Any]:
    return {
        "schema_version": "1",
        "state_change": "none",
        "authority": "non-authoritative; advisory operator evidence review capsule only",
        "summary": {
            "review_status": review_status,
            "recommended_human_decision": recommended_human_decision,
            "action_readiness": action_readiness,
            "input_count": 4,
            "input_blocker_count": input_blocker_count,
            "blocker_count": blocker_count,
            "missing_review_evidence_count": missing_review_evidence_count,
        },
    }


def _stress_payload(
    *,
    scenario_count: int = 9,
    pass_count: int = 9,
    fail_count: int = 0,
    all_scenarios_passed: bool = True,
) -> dict[str, Any]:
    return {
        "schema_version": "1",
        "state_change": "none",
        "authority": "non-authoritative; advisory operator evidence review capsule stress matrix only",
        "summary": {
            "scenario_count": scenario_count,
            "pass_count": pass_count,
            "fail_count": fail_count,
            "all_scenarios_passed": all_scenarios_passed,
            "blocker_count": 15,
            "degraded_blocker_count": 15,
            "input_blocker_count": 5,
            "missing_review_evidence_count": 4,
            "boundary_error_count": 2,
        },
    }


def _repro_payload(
    *,
    state_change: str = "none",
    reproducibility_status: str = "reproducible",
    recommended_human_decision: str = "none",
    action_readiness: str = "advisory_report_allowed",
    blocker_count: int = 0,
    mismatch_count: int = 0,
    missing_artifact_count: int = 0,
    json_digest_match: bool = True,
    markdown_digest_match: bool = True,
) -> dict[str, Any]:
    return {
        "schema_version": "1",
        "state_change": state_change,
        "authority": (
            "non-authoritative; advisory operator evidence review capsule "
            "reproducibility check only"
        ),
        "summary": {
            "reproducibility_status": reproducibility_status,
            "recommended_human_decision": recommended_human_decision,
            "action_readiness": action_readiness,
            "blocked": action_readiness == "blocked",
            "artifact_count": 2,
            "blocker_count": blocker_count,
            "mismatch_count": mismatch_count,
            "missing_artifact_count": missing_artifact_count,
            "json_digest_match": json_digest_match,
            "markdown_digest_match": markdown_digest_match,
        },
    }


def _without_summary(payload: dict[str, Any]) -> dict[str, Any]:
    next_payload = dict(payload)
    next_payload.pop("summary", None)
    return next_payload


def _index_summary(index: OperatorEvidenceFinalReviewIndexReport) -> str:
    return (
        f"review_status={index.review_status}; "
        f"recommended_human_decision={index.recommended_human_decision}; "
        f"action_readiness={index.action_readiness}; "
        f"blocker_count={len(index.blockers)}; "
        f"input_blocker_count={index.input_blocker_count}; "
        f"missing_review_evidence_count={len(index.missing_review_evidence)}"
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
    "OPERATOR_EVIDENCE_FINAL_REVIEW_INDEX_STRESS_MATRIX_AUTHORITY",
    "OperatorEvidenceFinalReviewIndexStressMatrixReport",
    "OperatorEvidenceFinalReviewIndexStressScenario",
    "build_operator_evidence_final_review_index_stress_matrix",
    "render_operator_evidence_final_review_index_stress_matrix_json",
    "render_operator_evidence_final_review_index_stress_matrix_markdown",
]
