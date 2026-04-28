from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping


OPERATOR_EVIDENCE_REVIEW_CAPSULE_SCHEMA_VERSION = "1"
OPERATOR_EVIDENCE_REVIEW_CAPSULE_AUTHORITY = (
    "non-authoritative; advisory operator evidence review capsule only"
)

DEFAULT_OPERATOR_EVIDENCE_REVIEW_CAPSULE_INPUTS = {
    "operator_decision_packet": "docs/operations/CEREBRO_SELF_EPISTEMIC_OPERATOR_DECISION_PACKET.json",
    "intake_reproducibility": (
        "docs/operations/"
        "CEREBRO_SELF_EPISTEMIC_OPERATOR_EVIDENCE_INTAKE_REPRODUCIBILITY_CHECK.json"
    ),
    "provenance_index": (
        "docs/operations/CEREBRO_SELF_EPISTEMIC_OPERATOR_EVIDENCE_PROVENANCE_INDEX.json"
    ),
    "provenance_stress_matrix": (
        "docs/operations/"
        "CEREBRO_SELF_EPISTEMIC_OPERATOR_EVIDENCE_PROVENANCE_STRESS_MATRIX.json"
    ),
}

_EXPECTED_AUTHORITIES = {
    "operator_decision_packet": (
        "non-authoritative; advisory operator decision packet evidence only"
    ),
    "intake_reproducibility": (
        "non-authoritative; advisory operator evidence intake reproducibility check only"
    ),
    "provenance_index": (
        "non-authoritative; advisory operator evidence provenance index only"
    ),
    "provenance_stress_matrix": (
        "non-authoritative; advisory operator evidence provenance stress matrix only"
    ),
}
_VALID_HUMAN_DECISIONS = {
    "none",
    "acknowledge",
    "approve_baseline_refresh",
    "review_blockers",
    "adjudicate_conflict",
    "provide_missing_evidence",
}
_VALID_ACTION_READINESS = {
    "no_action",
    "observe_only",
    "propose_only",
    "advisory_report_allowed",
    "derived_experiment_allowed",
    "canonical_change_requires_trigger",
    "human_approval_required",
    "blocked",
}


@dataclass(frozen=True)
class OperatorEvidenceReviewInput:
    input_id: str
    path: str
    exists: bool
    parse_status: str
    digest: str = ""
    schema_version: str = ""
    authority: str = ""
    state_change: str = ""
    action_readiness: str = ""
    recommended_human_decision: str = ""
    blockers: tuple[str, ...] = ()

    @property
    def blocked(self) -> bool:
        return bool(self.blockers)

    def to_dict(self) -> dict[str, Any]:
        return {
            "input_id": self.input_id,
            "path": self.path,
            "exists": self.exists,
            "parse_status": self.parse_status,
            "digest": self.digest,
            "schema_version": self.schema_version,
            "authority": self.authority,
            "state_change": self.state_change,
            "action_readiness": self.action_readiness,
            "recommended_human_decision": self.recommended_human_decision,
            "blocked": self.blocked,
            "blockers": list(self.blockers),
        }


@dataclass(frozen=True)
class OperatorEvidenceReviewCapsule:
    inputs: tuple[OperatorEvidenceReviewInput, ...]
    decision_posture: str
    decision_posture_human_decision: str
    reproducibility_status: str
    digest_match: bool | None
    provenance_artifact_count: int
    provenance_present_count: int
    provenance_dependency_edge_count: int
    provenance_digest_manifest: str
    stress_scenario_count: int
    stress_pass_count: int
    stress_fail_count: int
    stress_blocker_count: int
    stress_boundary_error_count: int
    stress_text_digest_only_count: int
    blockers: tuple[str, ...] = ()
    missing_review_evidence: tuple[str, ...] = ()
    state_change: str = "none"
    authority: str = OPERATOR_EVIDENCE_REVIEW_CAPSULE_AUTHORITY
    capsule_role: str = "operator-facing advisory evidence review capsule only"

    def __post_init__(self) -> None:
        if self.state_change != "none":
            raise ValueError("operator evidence review capsule must not change state")
        if self.authority != OPERATOR_EVIDENCE_REVIEW_CAPSULE_AUTHORITY:
            raise ValueError(f"unsupported operator evidence review capsule authority: {self.authority}")
        if tuple(input_.input_id for input_ in self.inputs) != tuple(
            DEFAULT_OPERATOR_EVIDENCE_REVIEW_CAPSULE_INPUTS
        ):
            raise ValueError("operator evidence review capsule inputs must use the closed input set")
        if self.decision_posture not in _VALID_ACTION_READINESS:
            raise ValueError(f"invalid decision_posture: {self.decision_posture}")
        if self.decision_posture_human_decision not in _VALID_HUMAN_DECISIONS:
            raise ValueError(
                f"invalid decision_posture_human_decision: {self.decision_posture_human_decision}"
            )
        if self.action_readiness == "blocked" and not self.blockers:
            raise ValueError("blocked review capsules must expose blockers")
        for field_name, value in (
            ("provenance_artifact_count", self.provenance_artifact_count),
            ("provenance_present_count", self.provenance_present_count),
            ("provenance_dependency_edge_count", self.provenance_dependency_edge_count),
            ("stress_scenario_count", self.stress_scenario_count),
            ("stress_pass_count", self.stress_pass_count),
            ("stress_fail_count", self.stress_fail_count),
            ("stress_blocker_count", self.stress_blocker_count),
            ("stress_boundary_error_count", self.stress_boundary_error_count),
            ("stress_text_digest_only_count", self.stress_text_digest_only_count),
        ):
            if value < 0:
                raise ValueError(f"{field_name} must be non-negative")

    @property
    def review_status(self) -> str:
        if self.blockers:
            return "blocked_review"
        if self.missing_review_evidence:
            return "incomplete_review_evidence"
        return "review_clear"

    @property
    def recommended_human_decision(self) -> str:
        return "review_blockers" if self.blockers else "none"

    @property
    def action_readiness(self) -> str:
        return "blocked" if self.blockers else "advisory_report_allowed"

    @property
    def input_blocker_count(self) -> int:
        return sum(len(input_.blockers) for input_ in self.inputs)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": OPERATOR_EVIDENCE_REVIEW_CAPSULE_SCHEMA_VERSION,
            "state_change": self.state_change,
            "authority": self.authority,
            "capsule_role": self.capsule_role,
            "summary": {
                "review_status": self.review_status,
                "recommended_human_decision": self.recommended_human_decision,
                "action_readiness": self.action_readiness,
                "input_count": len(self.inputs),
                "input_blocker_count": self.input_blocker_count,
                "blocker_count": len(self.blockers),
                "missing_review_evidence_count": len(self.missing_review_evidence),
                "decision_posture": self.decision_posture,
                "decision_posture_human_decision": self.decision_posture_human_decision,
                "reproducibility_status": self.reproducibility_status,
                "digest_match": self.digest_match,
                "provenance_artifact_count": self.provenance_artifact_count,
                "provenance_present_count": self.provenance_present_count,
                "provenance_dependency_edge_count": self.provenance_dependency_edge_count,
                "provenance_digest_manifest": self.provenance_digest_manifest,
                "stress_scenario_count": self.stress_scenario_count,
                "stress_pass_count": self.stress_pass_count,
                "stress_fail_count": self.stress_fail_count,
                "stress_blocker_count": self.stress_blocker_count,
                "stress_boundary_error_count": self.stress_boundary_error_count,
                "stress_text_digest_only_count": self.stress_text_digest_only_count,
            },
            "inputs": [input_.to_dict() for input_ in self.inputs],
            "blockers": list(self.blockers),
            "missing_review_evidence": list(self.missing_review_evidence),
            "guardrails": {
                "registered_is_not_true": True,
                "retrieved_is_not_relevant": True,
                "remembered_is_not_trusted": True,
                "silence_is_not_negative_evidence": True,
                "review_capsule_is_not_permission": True,
                "review_capsule_is_not_memory": True,
                "review_capsule_is_not_authority": True,
                "review_capsule_is_not_runtime_gate": True,
                "review_capsule_is_not_claim_graph": True,
                "review_capsule_is_not_source_registry": True,
                "review_capsule_is_not_canonical_evidence_graph": True,
                "digest_equality_is_not_truth": True,
                "decision_posture_is_not_permission": True,
                "reproducibility_is_not_permission": True,
                "provenance_is_not_permission": True,
                "stress_pass_is_not_permission": True,
            },
            "boundary": {
                "may_suggest": [
                    "summarize current advisory decision posture",
                    "summarize checked intake reproducibility",
                    "summarize provenance health",
                    "summarize degraded-evidence stress coverage",
                    "surface blockers and missing review evidence",
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
                    "treat capsule output as permission",
                    "treat digest equality as truth",
                    "treat stress pass as permission",
                    "hide blockers",
                    "hide missing evidence",
                    "infer negative evidence from silence",
                ],
            },
        }


def build_operator_evidence_review_capsule(
    project_root: str | Path,
    input_paths: Mapping[str, str | Path] | None = None,
) -> OperatorEvidenceReviewCapsule:
    root = Path(project_root).resolve()
    paths = dict(DEFAULT_OPERATOR_EVIDENCE_REVIEW_CAPSULE_INPUTS)
    if input_paths is not None:
        unknown = set(input_paths) - set(DEFAULT_OPERATOR_EVIDENCE_REVIEW_CAPSULE_INPUTS)
        if unknown:
            raise ValueError(f"unknown review capsule input id(s): {', '.join(sorted(unknown))}")
        paths.update({key: str(value) for key, value in input_paths.items()})

    loaded: dict[str, tuple[OperatorEvidenceReviewInput, dict[str, Any] | None]] = {}
    for input_id in DEFAULT_OPERATOR_EVIDENCE_REVIEW_CAPSULE_INPUTS:
        loaded[input_id] = _load_json_input(
            root,
            input_id,
            paths[input_id],
            _EXPECTED_AUTHORITIES[input_id],
        )

    inputs = tuple(loaded[input_id][0] for input_id in DEFAULT_OPERATOR_EVIDENCE_REVIEW_CAPSULE_INPUTS)
    payloads = {input_id: loaded[input_id][1] for input_id in DEFAULT_OPERATOR_EVIDENCE_REVIEW_CAPSULE_INPUTS}
    blockers: list[str] = []
    missing_review_evidence: list[str] = []
    for input_ in inputs:
        blockers.extend(f"{input_.input_id}: {blocker}" for blocker in input_.blockers)
        if input_.parse_status != "parsed":
            missing_review_evidence.append(input_.input_id)

    decision_summary = _summary(payloads["operator_decision_packet"])
    reproducibility_summary = _summary(payloads["intake_reproducibility"])
    provenance_summary = _summary(payloads["provenance_index"])
    stress_summary = _summary(payloads["provenance_stress_matrix"])

    decision_posture = _string_or(decision_summary, "action_readiness", "blocked")
    decision_human_decision = _string_or(
        decision_summary,
        "recommended_human_decision",
        "review_blockers",
    )
    packet_blocker_count = _int_or(decision_summary, "blocker_count", 0)
    packet_missing_count = _int_or(decision_summary, "missing_evidence_count", 0)
    if packet_blocker_count:
        blockers.append(f"operator decision packet reports {packet_blocker_count} blocker(s)")
    if packet_missing_count:
        blockers.append(f"operator decision packet reports {packet_missing_count} missing evidence item(s)")
    if decision_posture == "blocked":
        blockers.append("operator decision packet action readiness is blocked")

    reproducibility_status = _string_or(
        reproducibility_summary,
        "reproducibility_status",
        "unknown",
    )
    digest_match = _bool_or_none(reproducibility_summary, "digest_match")
    repro_blocker_count = _int_or(reproducibility_summary, "blocker_count", 0)
    repro_mismatch_count = _int_or(reproducibility_summary, "mismatch_count", 0)
    if reproducibility_status != "reproducible":
        blockers.append(f"operator evidence intake reproducibility is {reproducibility_status}")
    if repro_blocker_count:
        blockers.append(f"operator evidence intake reproducibility reports {repro_blocker_count} blocker(s)")
    if repro_mismatch_count:
        blockers.append(f"operator evidence intake reproducibility reports {repro_mismatch_count} mismatch(es)")
    if digest_match is False:
        blockers.append("operator evidence intake reproducibility digest does not match")

    provenance_artifact_count = _int_or(provenance_summary, "artifact_count", 0)
    provenance_present_count = _int_or(provenance_summary, "present_count", 0)
    provenance_dependency_edge_count = _int_or(provenance_summary, "dependency_edge_count", 0)
    provenance_digest_manifest = _string_or(provenance_summary, "digest_manifest", "")
    provenance_blocker_count = _int_or(provenance_summary, "blocker_count", 0)
    provenance_blocked = _bool_or(provenance_summary, "blocked", False)
    if provenance_blocked or provenance_blocker_count:
        blockers.append(f"operator evidence provenance index reports {provenance_blocker_count} blocker(s)")
    if provenance_artifact_count and provenance_present_count < provenance_artifact_count:
        blockers.append(
            "operator evidence provenance index has missing artifacts: "
            f"{provenance_present_count}/{provenance_artifact_count} present"
        )

    stress_scenario_count = _int_or(stress_summary, "scenario_count", 0)
    stress_pass_count = _int_or(stress_summary, "pass_count", 0)
    stress_fail_count = _int_or(stress_summary, "fail_count", 0)
    stress_blocker_count = _int_or(stress_summary, "blocker_count", 0)
    stress_boundary_error_count = _int_or(stress_summary, "boundary_error_count", 0)
    stress_text_digest_only_count = _int_or(stress_summary, "text_digest_only_count", 0)
    stress_all_passed = _bool_or(stress_summary, "all_scenarios_passed", False)
    if stress_scenario_count == 0:
        missing_review_evidence.append("provenance_stress_matrix_scenarios")
        blockers.append("operator evidence provenance stress matrix has no scenarios")
    if not stress_all_passed or stress_fail_count:
        blockers.append(
            f"operator evidence provenance stress matrix reports {stress_fail_count} failing scenario(s)"
        )
    if stress_pass_count > stress_scenario_count:
        blockers.append("operator evidence provenance stress matrix pass count exceeds scenario count")

    return OperatorEvidenceReviewCapsule(
        inputs=inputs,
        decision_posture=decision_posture,
        decision_posture_human_decision=decision_human_decision,
        reproducibility_status=reproducibility_status,
        digest_match=digest_match,
        provenance_artifact_count=provenance_artifact_count,
        provenance_present_count=provenance_present_count,
        provenance_dependency_edge_count=provenance_dependency_edge_count,
        provenance_digest_manifest=provenance_digest_manifest,
        stress_scenario_count=stress_scenario_count,
        stress_pass_count=stress_pass_count,
        stress_fail_count=stress_fail_count,
        stress_blocker_count=stress_blocker_count,
        stress_boundary_error_count=stress_boundary_error_count,
        stress_text_digest_only_count=stress_text_digest_only_count,
        blockers=tuple(blockers),
        missing_review_evidence=tuple(missing_review_evidence),
    )


def render_operator_evidence_review_capsule_json(
    capsule: OperatorEvidenceReviewCapsule,
) -> str:
    return json.dumps(capsule.to_dict(), indent=2, sort_keys=True) + "\n"


def render_operator_evidence_review_capsule_markdown(
    capsule: OperatorEvidenceReviewCapsule,
) -> str:
    lines = [
        "# Epistemic Readiness Operator Evidence Review Capsule",
        "",
        "## Boundary",
        "",
        f"- state_change: {capsule.state_change}",
        f"- authority: {capsule.authority}",
        f"- capsule_role: {capsule.capsule_role}",
        "- review_capsule_is_not_permission: true",
        "- review_capsule_is_not_memory: true",
        "- review_capsule_is_not_authority: true",
        "- review_capsule_is_not_runtime_gate: true",
        "- review_capsule_is_not_claim_graph: true",
        "- review_capsule_is_not_source_registry: true",
        "- review_capsule_is_not_canonical_evidence_graph: true",
        "- digest_equality_is_not_truth: true",
        "- stress_pass_is_not_permission: true",
        "- silence_is_not_negative_evidence: true",
        "",
        "## Summary",
        "",
        f"- review_status: {capsule.review_status}",
        f"- recommended_human_decision: {capsule.recommended_human_decision}",
        f"- action_readiness: {capsule.action_readiness}",
        f"- input_count: {len(capsule.inputs)}",
        f"- input_blocker_count: {capsule.input_blocker_count}",
        f"- blocker_count: {len(capsule.blockers)}",
        f"- missing_review_evidence_count: {len(capsule.missing_review_evidence)}",
        "",
        "## Decision Posture",
        "",
        f"- decision_posture: {capsule.decision_posture}",
        f"- decision_posture_human_decision: {capsule.decision_posture_human_decision}",
        "- decision_posture_is_not_permission: true",
        "",
        "## Intake Reproducibility",
        "",
        f"- reproducibility_status: {capsule.reproducibility_status}",
        f"- digest_match: {_json_bool(capsule.digest_match)}",
        "- reproducibility_is_not_permission: true",
        "",
        "## Provenance Health",
        "",
        f"- provenance_artifact_count: {capsule.provenance_artifact_count}",
        f"- provenance_present_count: {capsule.provenance_present_count}",
        f"- provenance_dependency_edge_count: {capsule.provenance_dependency_edge_count}",
        f"- provenance_digest_manifest: {capsule.provenance_digest_manifest}",
        "- provenance_is_not_permission: true",
        "",
        "## Stress Coverage",
        "",
        f"- stress_scenario_count: {capsule.stress_scenario_count}",
        f"- stress_pass_count: {capsule.stress_pass_count}",
        f"- stress_fail_count: {capsule.stress_fail_count}",
        f"- stress_blocker_count: {capsule.stress_blocker_count}",
        f"- stress_boundary_error_count: {capsule.stress_boundary_error_count}",
        f"- stress_text_digest_only_count: {capsule.stress_text_digest_only_count}",
        "",
        "## Inputs",
        "",
        "| Input | Status | Readiness | Decision | Blockers |",
        "|---|---|---|---|---:|",
    ]
    for input_ in capsule.inputs:
        lines.append(
            "| "
            f"{input_.input_id} | "
            f"{input_.parse_status} | "
            f"{input_.action_readiness or 'unknown'} | "
            f"{input_.recommended_human_decision or 'unknown'} | "
            f"{len(input_.blockers)} |"
        )
    if capsule.blockers:
        lines.extend(["", "## Blockers", ""])
        for blocker in capsule.blockers:
            lines.append(f"- {blocker}")
    if capsule.missing_review_evidence:
        lines.extend(["", "## Missing Review Evidence", ""])
        for item in capsule.missing_review_evidence:
            lines.append(f"- {item}")
    lines.extend(["", "## Must Not Apply", ""])
    for item in capsule.to_dict()["boundary"]["must_not_apply"]:
        lines.append(f"- {item}")
    return "\n".join(lines) + "\n"


def _load_json_input(
    root: Path,
    input_id: str,
    path: str | Path,
    expected_authority: str,
) -> tuple[OperatorEvidenceReviewInput, dict[str, Any] | None]:
    blockers: list[str] = []
    digest = ""
    schema_version = ""
    authority = ""
    state_change = ""
    action_readiness = ""
    recommended_human_decision = ""
    payload: dict[str, Any] | None = None
    label = str(path).replace("\\", "/")

    try:
        resolved, label = _resolve_under_project_root(root, path)
    except ValueError as exc:
        return (
            OperatorEvidenceReviewInput(
                input_id=input_id,
                path=label,
                exists=False,
                parse_status="blocked_path",
                blockers=(f"path blocked: {exc}",),
            ),
            None,
        )

    if not resolved.exists():
        return (
            OperatorEvidenceReviewInput(
                input_id=input_id,
                path=label,
                exists=False,
                parse_status="missing",
                blockers=(f"input file is missing: {label}",),
            ),
            None,
        )

    try:
        text = resolved.read_text(encoding="utf-8")
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        raw_payload = json.loads(text)
    except json.JSONDecodeError as exc:
        return (
            OperatorEvidenceReviewInput(
                input_id=input_id,
                path=label,
                exists=True,
                parse_status="malformed_json",
                digest=digest,
                blockers=(f"input JSON is malformed: {exc.msg}",),
            ),
            None,
        )
    except OSError as exc:
        return (
            OperatorEvidenceReviewInput(
                input_id=input_id,
                path=label,
                exists=True,
                parse_status="unreadable",
                digest=digest,
                blockers=(f"input file could not be read: {exc}",),
            ),
            None,
        )

    if not isinstance(raw_payload, Mapping):
        blockers.append("input JSON root must be an object")
    else:
        payload = dict(raw_payload)
        schema_version = str(payload.get("schema_version", ""))
        authority = str(payload.get("authority", ""))
        state_change = str(payload.get("state_change", ""))
        summary = _summary(payload)
        action_readiness = _string_or(summary, "action_readiness", "")
        recommended_human_decision = _string_or(summary, "recommended_human_decision", "")
        if schema_version != "1":
            blockers.append(f"input schema_version must be 1: {schema_version or 'missing'}")
        if state_change != "none":
            blockers.append(f"input must preserve state_change none: {state_change or 'missing'}")
        if authority != expected_authority:
            blockers.append(
                "input authority mismatch: "
                f"expected {expected_authority!r}, observed {authority!r}"
            )

    return (
        OperatorEvidenceReviewInput(
            input_id=input_id,
            path=label,
            exists=True,
            parse_status="parsed" if payload is not None else "invalid_shape",
            digest=digest,
            schema_version=schema_version,
            authority=authority,
            state_change=state_change,
            action_readiness=action_readiness,
            recommended_human_decision=recommended_human_decision,
            blockers=tuple(blockers),
        ),
        payload if not blockers else payload,
    )


def _resolve_under_project_root(root: Path, path: str | Path) -> tuple[Path, str]:
    path_obj = Path(path)
    if any(part == ".cerebro" for part in path_obj.parts):
        raise ValueError("path crosses canonical state boundary")
    resolved = path_obj.resolve() if path_obj.is_absolute() else (root / path_obj).resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"path escapes project root: {path}") from exc
    return resolved, resolved.relative_to(root).as_posix()


def _summary(payload: Mapping[str, Any] | None) -> Mapping[str, Any]:
    if not isinstance(payload, Mapping):
        return {}
    summary = payload.get("summary")
    return summary if isinstance(summary, Mapping) else {}


def _int_or(mapping: Mapping[str, Any], key: str, default: int) -> int:
    value = mapping.get(key)
    return value if isinstance(value, int) and not isinstance(value, bool) else default


def _bool_or(mapping: Mapping[str, Any], key: str, default: bool) -> bool:
    value = mapping.get(key)
    return value if isinstance(value, bool) else default


def _bool_or_none(mapping: Mapping[str, Any], key: str) -> bool | None:
    value = mapping.get(key)
    return value if isinstance(value, bool) else None


def _string_or(mapping: Mapping[str, Any], key: str, default: str) -> str:
    value = mapping.get(key)
    return value if isinstance(value, str) else default


def _json_bool(value: bool | None) -> str:
    if value is None:
        return "null"
    return str(value).lower()
