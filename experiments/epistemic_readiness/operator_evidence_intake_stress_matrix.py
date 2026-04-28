from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import tempfile
from typing import Any, Mapping

from .decision_taxonomy_conformance import evaluate_decision_taxonomy_conformance
from .metacognitive_handoff import evaluate_metacognitive_handoff
from .operator_decision_packet import build_operator_decision_packet
from .operator_evidence_intake_manifest import (
    OPERATOR_EVIDENCE_INTAKE_REPORT_AUTHORITY,
    OperatorEvidenceIntakeArtifact,
    OperatorEvidenceIntakeManifest,
    build_operator_evidence_intake_report,
)
from .operator_packet_stress_matrix import _clean_payloads, build_operator_packet_stress_matrix


OPERATOR_EVIDENCE_INTAKE_STRESS_MATRIX_SCHEMA_VERSION = "1"
OPERATOR_EVIDENCE_INTAKE_STRESS_MATRIX_AUTHORITY = (
    "non-authoritative; advisory operator evidence intake stress matrix only"
)

_SCENARIO_IDS = (
    "clean_manifest",
    "missing_artifact",
    "stale_digest",
    "root_escape",
    "non_json_artifact",
    "mutating_payload",
    "duplicate_artifact_id",
    "missing_required_artifact",
)


@dataclass(frozen=True)
class OperatorEvidenceIntakeStressScenario:
    scenario_id: str
    title: str
    purpose: str
    expected_recommended_human_decision: str
    expected_action_readiness: str
    observed_recommended_human_decision: str
    observed_action_readiness: str
    intake_summary: str
    blocker_count: int
    boundary_error_count: int
    expected_error: bool = False
    observed_error: str = ""
    state_change: str = "none"
    authority: str = OPERATOR_EVIDENCE_INTAKE_STRESS_MATRIX_AUTHORITY

    def __post_init__(self) -> None:
        if self.scenario_id not in _SCENARIO_IDS:
            raise ValueError(f"unknown operator evidence intake stress scenario: {self.scenario_id}")
        if self.state_change != "none":
            raise ValueError("operator evidence intake stress scenarios must not change state")
        if self.authority != OPERATOR_EVIDENCE_INTAKE_STRESS_MATRIX_AUTHORITY:
            raise ValueError(f"unsupported intake stress scenario authority: {self.authority}")
        if not self.intake_summary:
            raise ValueError("operator evidence intake stress scenarios require intake_summary")
        if self.blocker_count < 0:
            raise ValueError("blocker_count must be non-negative")
        if self.boundary_error_count < 0:
            raise ValueError("boundary_error_count must be non-negative")
        if self.observed_action_readiness == "blocked" and not (
            self.blocker_count or self.boundary_error_count or self.observed_error
        ):
            raise ValueError("blocked intake stress scenarios must expose blockers or boundary errors")

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
            "intake_summary": self.intake_summary,
            "blocker_count": self.blocker_count,
            "boundary_error_count": self.boundary_error_count,
            "forbidden_interpretations": [
                "treat intake output as permission",
                "hide degraded manifest evidence",
                "hide stale digest input",
                "hide root escape input",
                "treat digest equality as truth",
                "infer negative evidence from silence",
            ],
        }


@dataclass(frozen=True)
class OperatorEvidenceIntakeStressMatrixReport:
    scenarios: tuple[OperatorEvidenceIntakeStressScenario, ...]
    state_change: str = "none"
    authority: str = OPERATOR_EVIDENCE_INTAKE_STRESS_MATRIX_AUTHORITY
    matrix_role: str = "advisory degraded-evidence operator evidence intake stress matrix only"

    def __post_init__(self) -> None:
        if self.state_change != "none":
            raise ValueError("operator evidence intake stress matrix must not change state")
        if self.authority != OPERATOR_EVIDENCE_INTAKE_STRESS_MATRIX_AUTHORITY:
            raise ValueError(f"unsupported intake stress matrix authority: {self.authority}")
        scenario_ids = tuple(scenario.scenario_id for scenario in self.scenarios)
        if len(set(scenario_ids)) != len(scenario_ids):
            raise ValueError("operator evidence intake stress matrix scenario ids must be unique")
        if scenario_ids != _SCENARIO_IDS:
            raise ValueError(
                "operator evidence intake stress matrix must contain the closed "
                "scenario set in stable order"
            )
        for scenario in self.scenarios:
            if scenario.state_change != "none":
                raise ValueError("operator evidence intake stress scenarios must preserve state_change none")

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

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": OPERATOR_EVIDENCE_INTAKE_STRESS_MATRIX_SCHEMA_VERSION,
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
                "intake_stress_matrix_is_not_permission": True,
                "intake_stress_matrix_is_not_memory": True,
                "intake_stress_matrix_is_not_authority": True,
                "intake_stress_matrix_is_not_runtime_gate": True,
                "intake_stress_matrix_is_not_claim_graph": True,
                "intake_output_is_not_permission": True,
                "passing_scenario_is_not_permission": True,
                "digest_equality_is_not_truth": True,
                "malformed_intake_input_is_blocking_evidence": True,
            },
            "boundary": {
                "may_suggest": [
                    "compare intake output under degraded manifest evidence",
                    "show missing artifacts as blockers",
                    "show stale digest inputs as blockers",
                    "show root escape attempts as blockers",
                    "show mutating payloads as blockers",
                    "recommend future hardening slices",
                ],
                "must_not_apply": [
                    "mutate state",
                    "register sources",
                    "update replay baseline",
                    "write memory automatically",
                    "act as runtime gate",
                    "create canonical claim graph",
                    "promote or demote authority",
                    "treat intake output as permission",
                    "treat passing scenarios as permission",
                    "treat digest equality as truth",
                    "hide blockers",
                    "hide malformed manifest input",
                    "hide stale or mismatched digest input",
                    "infer negative evidence from silence",
                ],
            },
        }


def build_operator_evidence_intake_stress_matrix() -> OperatorEvidenceIntakeStressMatrixReport:
    with tempfile.TemporaryDirectory(prefix="cerebro-intake-stress-") as tmp_dir:
        root = Path(tmp_dir)
        clean_manifest = _write_clean_manifest(root)
        scenarios = (
            _scenario_from_manifest(
                "clean_manifest",
                "Clean manifest rebuilds the advisory bundle",
                "Proves declared evidence can reproduce the operator bundle without permission.",
                clean_manifest,
                expected_recommended_human_decision="none",
                expected_action_readiness="advisory_report_allowed",
            ),
            _scenario_from_manifest(
                "missing_artifact",
                "Missing declared artifact is visible",
                "Proves absent declared files block intake instead of being ignored.",
                _replace_artifact(clean_manifest, "drift_policy", path="missing-drift-policy.json"),
            ),
            _scenario_from_manifest(
                "stale_digest",
                "Digest mismatch is visible",
                "Proves stale expected digests block intake without treating digests as truth.",
                _replace_artifact(clean_manifest, "metacognitive_handoff", expected_digest="0" * 64),
            ),
            _scenario_from_manifest(
                "root_escape",
                "Root escape is visible",
                "Proves a declared path cannot escape the manifest root.",
                _replace_artifact(clean_manifest, "baseline_lifecycle", path="../outside.json"),
            ),
            _scenario_from_manifest(
                "non_json_artifact",
                "Non-JSON artifact is visible",
                "Proves intake refuses non-JSON declared artifact paths.",
                _replace_artifact(clean_manifest, "baseline_lifecycle", path="baseline_lifecycle.txt"),
            ),
            _scenario_from_mutating_payload(root, clean_manifest),
            _scenario_from_manifest_error(
                "duplicate_artifact_id",
                "Duplicate artifact id is visible",
                "Proves duplicate declared artifacts block intake before bundle construction.",
                lambda: OperatorEvidenceIntakeManifest(
                    root=clean_manifest.root,
                    generated_report_json=clean_manifest.generated_report_json,
                    generated_report_markdown=clean_manifest.generated_report_markdown,
                    artifacts=(clean_manifest.artifacts[0], clean_manifest.artifacts[0]),
                ),
            ),
            _scenario_from_manifest(
                "missing_required_artifact",
                "Missing required declaration is visible",
                "Proves omitting the packet stress matrix blocks intake.",
                OperatorEvidenceIntakeManifest(
                    root=clean_manifest.root,
                    generated_report_json=clean_manifest.generated_report_json,
                    generated_report_markdown=clean_manifest.generated_report_markdown,
                    artifacts=tuple(
                        artifact
                        for artifact in clean_manifest.artifacts
                        if artifact.artifact_id != "operator_packet_stress_matrix"
                    ),
                ),
            ),
        )
    return OperatorEvidenceIntakeStressMatrixReport(scenarios=scenarios)


def render_operator_evidence_intake_stress_matrix_json(
    report: OperatorEvidenceIntakeStressMatrixReport,
) -> str:
    return json.dumps(report.to_dict(), indent=2, sort_keys=True) + "\n"


def render_operator_evidence_intake_stress_matrix_markdown(
    report: OperatorEvidenceIntakeStressMatrixReport,
) -> str:
    lines = [
        "# Epistemic Readiness Operator Evidence Intake Stress Matrix",
        "",
        "## Boundary",
        "",
        f"- state_change: {report.state_change}",
        f"- authority: {report.authority}",
        f"- matrix_role: {report.matrix_role}",
        "- intake_stress_matrix_is_not_permission: true",
        "- intake_stress_matrix_is_not_memory: true",
        "- intake_stress_matrix_is_not_authority: true",
        "- intake_stress_matrix_is_not_runtime_gate: true",
        "- intake_stress_matrix_is_not_claim_graph: true",
        "- intake_output_is_not_permission: true",
        "- passing_scenario_is_not_permission: true",
        "- digest_equality_is_not_truth: true",
        "- malformed_intake_input_is_blocking_evidence: true",
        "- silence_is_not_negative_evidence: true",
        "",
        "## Summary",
        "",
        f"- scenario_count: `{len(report.scenarios)}`",
        f"- pass_count: `{report.pass_count}`",
        f"- fail_count: `{report.fail_count}`",
        f"- all_scenarios_passed: `{str(report.all_scenarios_passed).lower()}`",
        f"- blocker_count: `{report.blocker_count}`",
        f"- boundary_error_count: `{report.boundary_error_count}`",
        "",
        "## Scenarios",
        "",
        "| Scenario | Expected Decision | Observed Decision | Action Readiness | Boundary Error | Passed |",
        "|---|---|---|---|---|---|",
    ]
    for scenario in report.scenarios:
        lines.append(
            f"| `{scenario.scenario_id}` | `{scenario.expected_recommended_human_decision}` | "
            f"`{scenario.observed_recommended_human_decision}` | "
            f"`{scenario.observed_action_readiness}` | "
            f"`{str(bool(scenario.observed_error)).lower()}` | "
            f"`{str(scenario.passed).lower()}` |"
        )

    lines.extend(["", "## Visible Errors", ""])
    for scenario in report.scenarios:
        if scenario.observed_error:
            lines.append(f"- `{scenario.scenario_id}`: {scenario.observed_error}")
    if not any(scenario.observed_error for scenario in report.scenarios):
        lines.append("- none")

    lines.extend(
        [
            "",
            "## Must Not Apply",
            "",
            "- mutate state",
            "- register sources",
            "- update replay baseline",
            "- write memory automatically",
            "- act as runtime gate",
            "- create canonical claim graph",
            "- promote or demote authority",
            "- treat intake output as permission",
            "- treat passing scenarios as permission",
            "- treat digest equality as truth",
            "- hide blockers",
            "- hide malformed manifest input",
            "- hide stale or mismatched digest input",
            "- infer negative evidence from silence",
            "",
        ]
    )
    return "\n".join(lines)


def _scenario_from_manifest(
    scenario_id: str,
    title: str,
    purpose: str,
    manifest: OperatorEvidenceIntakeManifest,
    *,
    expected_recommended_human_decision: str = "review_blockers",
    expected_action_readiness: str = "blocked",
) -> OperatorEvidenceIntakeStressScenario:
    report = build_operator_evidence_intake_report(manifest)
    error = "; ".join(report.blockers)
    return OperatorEvidenceIntakeStressScenario(
        scenario_id=scenario_id,
        title=title,
        purpose=purpose,
        expected_recommended_human_decision=expected_recommended_human_decision,
        expected_action_readiness=expected_action_readiness,
        observed_recommended_human_decision=report.recommended_human_decision,
        observed_action_readiness=report.action_readiness,
        intake_summary=_intake_summary(report.to_dict()),
        blocker_count=len(report.blockers),
        boundary_error_count=1 if error else 0,
        expected_error=bool(error),
        observed_error=error,
    )


def _scenario_from_manifest_error(
    scenario_id: str,
    title: str,
    purpose: str,
    manifest_factory,
) -> OperatorEvidenceIntakeStressScenario:
    try:
        manifest_factory()
    except ValueError as exc:
        return OperatorEvidenceIntakeStressScenario(
            scenario_id=scenario_id,
            title=title,
            purpose=purpose,
            expected_recommended_human_decision="review_blockers",
            expected_action_readiness="blocked",
            observed_recommended_human_decision="review_blockers",
            observed_action_readiness="blocked",
            intake_summary="manifest construction blocked before intake",
            blocker_count=1,
            boundary_error_count=1,
            expected_error=True,
            observed_error=str(exc),
        )
    raise ValueError(f"{scenario_id} did not raise a manifest construction error")


def _scenario_from_mutating_payload(
    root: Path,
    clean_manifest: OperatorEvidenceIntakeManifest,
) -> OperatorEvidenceIntakeStressScenario:
    payload_path = root / "drift_policy.json"
    payload = json.loads(payload_path.read_text(encoding="utf-8"))
    payload["state_change"] = "canonical-mutation"
    payload_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    try:
        return _scenario_from_manifest(
            "mutating_payload",
            "Mutating payload is visible",
            "Proves declared artifacts that try to change state block intake.",
            clean_manifest,
        )
    finally:
        payload["state_change"] = "none"
        payload_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _write_clean_manifest(root: Path) -> OperatorEvidenceIntakeManifest:
    trace, lifecycle, self_audit, drift_policy = _clean_payloads()
    handoff = evaluate_metacognitive_handoff(trace, lifecycle, self_audit, drift_policy)
    conformance = evaluate_decision_taxonomy_conformance()
    packet = build_operator_decision_packet(
        handoff.to_dict(),
        conformance.to_dict(),
        drift_policy,
        lifecycle,
    )
    stress = build_operator_packet_stress_matrix()
    payloads: dict[str, Mapping[str, Any]] = {
        "operator_decision_packet": packet.to_dict(),
        "operator_packet_stress_matrix": stress.to_dict(),
        "baseline_lifecycle": lifecycle,
        "decision_taxonomy_conformance": conformance.to_dict(),
        "drift_policy": drift_policy,
        "metacognitive_handoff": handoff.to_dict(),
    }
    artifacts: list[OperatorEvidenceIntakeArtifact] = []
    for artifact_id, payload in payloads.items():
        path = f"{artifact_id}.json"
        (root / path).write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        artifacts.append(
            OperatorEvidenceIntakeArtifact(
                artifact_id=artifact_id,
                path=path,
                role=(
                    "advisory bundle input"
                    if artifact_id in {"operator_decision_packet", "operator_packet_stress_matrix"}
                    else "source advisory artifact digest"
                ),
                expected_digest=_stable_digest(payload),
            )
        )
    return OperatorEvidenceIntakeManifest(
        root=str(root),
        generated_report_json="operator_evidence_intake_report.json",
        generated_report_markdown="operator_evidence_intake_report.md",
        artifacts=tuple(artifacts),
    )


def _replace_artifact(
    manifest: OperatorEvidenceIntakeManifest,
    artifact_id: str,
    *,
    path: str | None = None,
    expected_digest: str | None = None,
) -> OperatorEvidenceIntakeManifest:
    artifacts: list[OperatorEvidenceIntakeArtifact] = []
    for artifact in manifest.artifacts:
        if artifact.artifact_id == artifact_id:
            artifacts.append(
                OperatorEvidenceIntakeArtifact(
                    artifact_id=artifact.artifact_id,
                    path=path if path is not None else artifact.path,
                    role=artifact.role,
                    expected_digest=(
                        expected_digest if expected_digest is not None else artifact.expected_digest
                    ),
                )
            )
        else:
            artifacts.append(artifact)
    return OperatorEvidenceIntakeManifest(
        root=manifest.root,
        generated_report_json=manifest.generated_report_json,
        generated_report_markdown=manifest.generated_report_markdown,
        artifacts=tuple(artifacts),
    )


def _intake_summary(payload: Mapping[str, Any]) -> str:
    summary = payload["summary"]
    bundle = summary.get("bundle_summary") or {}
    packet = bundle.get("packet_action_readiness", "none")
    stress_pass = bundle.get("stress_pass_count", "n/a")
    stress_fail = bundle.get("stress_fail_count", "n/a")
    return (
        f"decision={summary['recommended_human_decision']}; "
        f"readiness={summary['action_readiness']}; "
        f"blockers={summary['blocker_count']}; "
        f"inputs={summary['input_count']}; "
        f"packet={packet}; "
        f"stress={stress_pass}/{stress_fail}; "
        f"authority={OPERATOR_EVIDENCE_INTAKE_REPORT_AUTHORITY}"
    )


def _stable_digest(payload: Mapping[str, Any]) -> str:
    rendered = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(rendered.encode("utf-8")).hexdigest()
