from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import tempfile
from typing import Any

from .operator_evidence_provenance_index import (
    OperatorEvidenceProvenanceArtifactSpec,
    OperatorEvidenceProvenanceIndexReport,
    build_operator_evidence_provenance_index,
)


OPERATOR_EVIDENCE_PROVENANCE_STRESS_MATRIX_SCHEMA_VERSION = "1"
OPERATOR_EVIDENCE_PROVENANCE_STRESS_MATRIX_AUTHORITY = (
    "non-authoritative; advisory operator evidence provenance stress matrix only"
)

_SCENARIO_IDS = (
    "clean_provenance_chain",
    "missing_artifact",
    "malformed_json",
    "mutating_artifact",
    "root_escape",
    "cerebro_state_target",
    "duplicate_artifact_id",
    "missing_upstream_dependency",
    "text_digest_only_report",
)


@dataclass(frozen=True)
class OperatorEvidenceProvenanceStressScenario:
    scenario_id: str
    title: str
    purpose: str
    expected_recommended_human_decision: str
    expected_action_readiness: str
    observed_recommended_human_decision: str
    observed_action_readiness: str
    provenance_summary: str
    blocker_count: int
    boundary_error_count: int
    text_digest_only_count: int = 0
    expected_error: bool = False
    observed_error: str = ""
    state_change: str = "none"
    authority: str = OPERATOR_EVIDENCE_PROVENANCE_STRESS_MATRIX_AUTHORITY

    def __post_init__(self) -> None:
        if self.scenario_id not in _SCENARIO_IDS:
            raise ValueError(f"unknown provenance stress scenario: {self.scenario_id}")
        if self.state_change != "none":
            raise ValueError("operator evidence provenance stress scenarios must not change state")
        if self.authority != OPERATOR_EVIDENCE_PROVENANCE_STRESS_MATRIX_AUTHORITY:
            raise ValueError(f"unsupported provenance stress scenario authority: {self.authority}")
        if not self.provenance_summary:
            raise ValueError("operator evidence provenance stress scenarios require provenance_summary")
        if self.blocker_count < 0:
            raise ValueError("blocker_count must be non-negative")
        if self.boundary_error_count < 0:
            raise ValueError("boundary_error_count must be non-negative")
        if self.text_digest_only_count < 0:
            raise ValueError("text_digest_only_count must be non-negative")
        if self.observed_action_readiness == "blocked" and not (
            self.blocker_count or self.boundary_error_count or self.observed_error
        ):
            raise ValueError("blocked provenance stress scenarios must expose blockers or boundary errors")

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
                "boundary_error": self.expected_error,
            },
            "observed": {
                "recommended_human_decision": self.observed_recommended_human_decision,
                "action_readiness": self.observed_action_readiness,
                "boundary_error": bool(self.observed_error),
                "error": self.observed_error,
            },
            "passed": self.passed,
            "provenance_summary": self.provenance_summary,
            "blocker_count": self.blocker_count,
            "boundary_error_count": self.boundary_error_count,
            "text_digest_only_count": self.text_digest_only_count,
            "forbidden_interpretations": [
                "treat provenance stress output as permission",
                "treat provenance index output as truth",
                "hide degraded provenance evidence",
                "register sources from provenance evidence",
                "write memory from provenance evidence",
                "promote provenance evidence to runtime authority",
                "infer negative evidence from silence",
            ],
        }


@dataclass(frozen=True)
class OperatorEvidenceProvenanceStressMatrixReport:
    scenarios: tuple[OperatorEvidenceProvenanceStressScenario, ...]
    state_change: str = "none"
    authority: str = OPERATOR_EVIDENCE_PROVENANCE_STRESS_MATRIX_AUTHORITY
    matrix_role: str = "advisory degraded-evidence operator evidence provenance stress matrix only"

    def __post_init__(self) -> None:
        if self.state_change != "none":
            raise ValueError("operator evidence provenance stress matrix must not change state")
        if self.authority != OPERATOR_EVIDENCE_PROVENANCE_STRESS_MATRIX_AUTHORITY:
            raise ValueError(f"unsupported provenance stress matrix authority: {self.authority}")
        scenario_ids = tuple(scenario.scenario_id for scenario in self.scenarios)
        if len(set(scenario_ids)) != len(scenario_ids):
            raise ValueError("operator evidence provenance stress matrix scenario ids must be unique")
        if scenario_ids != _SCENARIO_IDS:
            raise ValueError(
                "operator evidence provenance stress matrix must contain the closed "
                "scenario set in stable order"
            )
        for scenario in self.scenarios:
            if scenario.state_change != "none":
                raise ValueError("operator evidence provenance stress scenarios must preserve state_change none")

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
    def boundary_error_count(self) -> int:
        return sum(scenario.boundary_error_count for scenario in self.scenarios)

    @property
    def text_digest_only_count(self) -> int:
        return sum(scenario.text_digest_only_count for scenario in self.scenarios)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": OPERATOR_EVIDENCE_PROVENANCE_STRESS_MATRIX_SCHEMA_VERSION,
            "state_change": self.state_change,
            "authority": self.authority,
            "matrix_role": self.matrix_role,
            "summary": {
                "scenario_count": len(self.scenarios),
                "pass_count": self.pass_count,
                "fail_count": self.fail_count,
                "all_scenarios_passed": self.all_scenarios_passed,
                "blocker_count": self.blocker_count,
                "boundary_error_count": self.boundary_error_count,
                "text_digest_only_count": self.text_digest_only_count,
                "scenario_ids": list(_SCENARIO_IDS),
                "decisions": {
                    scenario.scenario_id: {
                        "recommended_human_decision": (
                            scenario.observed_recommended_human_decision
                        ),
                        "action_readiness": scenario.observed_action_readiness,
                        "boundary_error": bool(scenario.observed_error),
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
                "provenance_stress_matrix_is_not_permission": True,
                "provenance_stress_matrix_is_not_memory": True,
                "provenance_stress_matrix_is_not_authority": True,
                "provenance_stress_matrix_is_not_runtime_gate": True,
                "provenance_stress_matrix_is_not_claim_graph": True,
                "provenance_stress_matrix_is_not_source_registry": True,
                "provenance_index_output_is_not_permission": True,
                "passing_scenario_is_not_permission": True,
                "artifact_digest_is_not_truth": True,
                "dependency_map_is_not_canonical_graph": True,
                "text_digest_only_is_not_truth": True,
                "degraded_provenance_is_review_evidence_only": True,
            },
            "boundary": {
                "may_suggest": [
                    "compare provenance index output under degraded evidence",
                    "show missing artifacts as blockers",
                    "show malformed artifacts as blockers",
                    "show mutating artifacts as blockers",
                    "show root escapes and .cerebro targets as boundary errors",
                    "show duplicate ids and missing dependencies as boundary errors",
                    "prove markdown/text-only reports remain advisory digest evidence",
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
                    "treat provenance output as permission",
                    "treat passing scenarios as permission",
                    "treat artifact digests as truth",
                    "hide blockers",
                    "hide malformed provenance input",
                    "hide dependency gaps",
                    "infer negative evidence from silence",
                ],
            },
        }


def build_operator_evidence_provenance_stress_matrix() -> OperatorEvidenceProvenanceStressMatrixReport:
    with tempfile.TemporaryDirectory(prefix="cerebro-provenance-stress-") as tmp_dir:
        root = Path(tmp_dir)
        _write_clean_json(root / "a.json")
        _write_clean_json(root / "b.json")
        (root / "report.md").write_text("# Advisory report\n\nEvidence only.\n", encoding="utf-8")
        (root / "bad.json").write_text("{not-json", encoding="utf-8")
        _write_clean_json(root / "mutating.json", state_change="canonical-mutation")
        outside_path = root.parent / f"outside-{root.name}.json"
        outside_path.write_text("{}", encoding="utf-8")
        try:
            scenarios = (
                _scenario_from_specs(
                    "clean_provenance_chain",
                    "Clean provenance chain remains advisory",
                    "Proves a complete JSON chain is inspectable without becoming permission.",
                    root,
                    (
                        OperatorEvidenceProvenanceArtifactSpec("a", "a.json", "json"),
                        OperatorEvidenceProvenanceArtifactSpec("b", "b.json", "json", ("a",)),
                    ),
                    expected_recommended_human_decision="none",
                    expected_action_readiness="advisory_report_allowed",
                ),
                _scenario_from_specs(
                    "missing_artifact",
                    "Missing artifact is visible",
                    "Proves absent declared provenance files block the advisory index.",
                    root,
                    (OperatorEvidenceProvenanceArtifactSpec("missing", "missing.json", "json"),),
                ),
                _scenario_from_specs(
                    "malformed_json",
                    "Malformed JSON is visible",
                    "Proves parse failure remains visible as blocker evidence.",
                    root,
                    (OperatorEvidenceProvenanceArtifactSpec("bad", "bad.json", "json"),),
                ),
                _scenario_from_specs(
                    "mutating_artifact",
                    "Mutating artifact is visible",
                    "Proves provenance artifacts cannot quietly declare state mutation.",
                    root,
                    (OperatorEvidenceProvenanceArtifactSpec("mutating", "mutating.json", "json"),),
                ),
                _scenario_from_specs(
                    "root_escape",
                    "Root escape is visible",
                    "Proves provenance specs cannot escape the project root.",
                    root,
                    (OperatorEvidenceProvenanceArtifactSpec("outside", str(outside_path), "json"),),
                    expected_error=True,
                ),
                _scenario_from_specs(
                    "cerebro_state_target",
                    ".cerebro target is visible",
                    "Proves provenance specs cannot target canonical Cerebro state.",
                    root,
                    (OperatorEvidenceProvenanceArtifactSpec("state", ".cerebro/state.json", "json"),),
                    expected_error=True,
                ),
                _scenario_from_specs(
                    "duplicate_artifact_id",
                    "Duplicate artifact id is visible",
                    "Proves duplicated provenance ids are blocker evidence, not silent overwrite.",
                    root,
                    (
                        OperatorEvidenceProvenanceArtifactSpec("dup", "a.json", "json"),
                        OperatorEvidenceProvenanceArtifactSpec("dup", "b.json", "json"),
                    ),
                    expected_error=True,
                ),
                _scenario_from_specs(
                    "missing_upstream_dependency",
                    "Missing upstream dependency is visible",
                    "Proves dependency gaps do not become a canonical graph by accident.",
                    root,
                    (OperatorEvidenceProvenanceArtifactSpec("a", "a.json", "json", ("missing",)),),
                    expected_error=True,
                ),
                _scenario_from_specs(
                    "text_digest_only_report",
                    "Text digest-only report remains advisory",
                    "Proves markdown reports can be fingerprinted without truth inference.",
                    root,
                    (OperatorEvidenceProvenanceArtifactSpec("report", "report.md", "markdown"),),
                    expected_recommended_human_decision="none",
                    expected_action_readiness="advisory_report_allowed",
                ),
            )
        finally:
            outside_path.unlink(missing_ok=True)
    return OperatorEvidenceProvenanceStressMatrixReport(scenarios=scenarios)


def render_operator_evidence_provenance_stress_matrix_json(
    report: OperatorEvidenceProvenanceStressMatrixReport,
) -> str:
    return json.dumps(report.to_dict(), indent=2, sort_keys=True) + "\n"


def render_operator_evidence_provenance_stress_matrix_markdown(
    report: OperatorEvidenceProvenanceStressMatrixReport,
) -> str:
    lines = [
        "# Epistemic Readiness Operator Evidence Provenance Stress Matrix",
        "",
        "## Boundary",
        "",
        f"- state_change: {report.state_change}",
        f"- authority: {report.authority}",
        f"- matrix_role: {report.matrix_role}",
        "- provenance_stress_matrix_is_not_permission: true",
        "- provenance_stress_matrix_is_not_memory: true",
        "- provenance_stress_matrix_is_not_authority: true",
        "- provenance_stress_matrix_is_not_runtime_gate: true",
        "- provenance_stress_matrix_is_not_claim_graph: true",
        "- provenance_stress_matrix_is_not_source_registry: true",
        "- dependency_map_is_not_canonical_graph: true",
        "- artifact_digest_is_not_truth: true",
        "- text_digest_only_is_not_truth: true",
        "- silence_is_not_negative_evidence: true",
        "",
        "## Summary",
        "",
        f"- scenario_count: {len(report.scenarios)}",
        f"- pass_count: {report.pass_count}",
        f"- fail_count: {report.fail_count}",
        f"- all_scenarios_passed: {str(report.all_scenarios_passed).lower()}",
        f"- blocker_count: {report.blocker_count}",
        f"- boundary_error_count: {report.boundary_error_count}",
        f"- text_digest_only_count: {report.text_digest_only_count}",
        "",
        "## Scenarios",
        "",
        "| Scenario | Expected | Observed | Passed | Blockers | Boundary Errors | Text Digest Only |",
        "|---|---|---|---|---:|---:|---:|",
    ]
    for scenario in report.scenarios:
        expected = (
            f"{scenario.expected_recommended_human_decision}/"
            f"{scenario.expected_action_readiness}"
        )
        observed = (
            f"{scenario.observed_recommended_human_decision}/"
            f"{scenario.observed_action_readiness}"
        )
        lines.append(
            "| "
            f"{scenario.scenario_id} | "
            f"{expected} | "
            f"{observed} | "
            f"{str(scenario.passed).lower()} | "
            f"{scenario.blocker_count} | "
            f"{scenario.boundary_error_count} | "
            f"{scenario.text_digest_only_count} |"
        )
    lines.extend(["", "## Must Not Apply", ""])
    for item in report.to_dict()["boundary"]["must_not_apply"]:
        lines.append(f"- {item}")
    return "\n".join(lines) + "\n"


def _scenario_from_specs(
    scenario_id: str,
    title: str,
    purpose: str,
    root: Path,
    specs: tuple[OperatorEvidenceProvenanceArtifactSpec, ...],
    expected_recommended_human_decision: str = "review_blockers",
    expected_action_readiness: str = "blocked",
    expected_error: bool = False,
) -> OperatorEvidenceProvenanceStressScenario:
    try:
        report = build_operator_evidence_provenance_index(root, specs)
        summary = _summary(report)
        observed_error = ""
        if expected_error and report.blocked:
            observed_error = _first_blocker(report)
    except ValueError as exc:
        summary = f"builder_error={exc}"
        return OperatorEvidenceProvenanceStressScenario(
            scenario_id=scenario_id,
            title=title,
            purpose=purpose,
            expected_recommended_human_decision=expected_recommended_human_decision,
            expected_action_readiness=expected_action_readiness,
            observed_recommended_human_decision="review_blockers",
            observed_action_readiness="blocked",
            provenance_summary=summary,
            blocker_count=1,
            boundary_error_count=1,
            expected_error=expected_error,
            observed_error=str(exc),
        )

    return OperatorEvidenceProvenanceStressScenario(
        scenario_id=scenario_id,
        title=title,
        purpose=purpose,
        expected_recommended_human_decision=expected_recommended_human_decision,
        expected_action_readiness=expected_action_readiness,
        observed_recommended_human_decision=report.recommended_human_decision,
        observed_action_readiness=report.action_readiness,
        provenance_summary=summary,
        blocker_count=len(report.blockers) + report.artifact_blocker_count,
        boundary_error_count=_boundary_error_count(report),
        text_digest_only_count=sum(
            1 for artifact in report.artifacts if artifact.parse_status == "text_digest_only"
        ),
        expected_error=expected_error,
        observed_error=observed_error,
    )


def _summary(report: OperatorEvidenceProvenanceIndexReport) -> str:
    return (
        f"artifacts={report.artifact_count}; "
        f"present={report.present_count}; "
        f"dependencies={report.dependency_edge_count}; "
        f"blockers={len(report.blockers) + report.artifact_blocker_count}; "
        f"readiness={report.action_readiness}"
    )


def _first_blocker(report: OperatorEvidenceProvenanceIndexReport) -> str:
    if report.blockers:
        return report.blockers[0]
    for artifact in report.artifacts:
        if artifact.blockers:
            return artifact.blockers[0]
    return "blocked provenance evidence"


def _boundary_error_count(report: OperatorEvidenceProvenanceIndexReport) -> int:
    count = len(report.blockers)
    for artifact in report.artifacts:
        for blocker in artifact.blockers:
            if "path blocked" in blocker:
                count += 1
    return count


def _write_clean_json(path: Path, state_change: str = "none") -> None:
    path.write_text(
        json.dumps(
            {
                "schema_version": "1",
                "state_change": state_change,
                "authority": "non-authoritative; advisory provenance stress fixture only",
                "summary": {
                    "action_readiness": "advisory_report_allowed",
                    "blocker_count": 0,
                },
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

