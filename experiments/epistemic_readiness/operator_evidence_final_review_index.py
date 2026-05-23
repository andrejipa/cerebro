from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from .operator_evidence_review_capsule import OPERATOR_EVIDENCE_REVIEW_CAPSULE_AUTHORITY
from .operator_evidence_review_capsule_reproducibility import (
    OPERATOR_EVIDENCE_REVIEW_CAPSULE_REPRODUCIBILITY_AUTHORITY,
)
from .operator_evidence_review_capsule_stress_matrix import (
    OPERATOR_EVIDENCE_REVIEW_CAPSULE_STRESS_MATRIX_AUTHORITY,
)


OPERATOR_EVIDENCE_FINAL_REVIEW_INDEX_SCHEMA_VERSION = "1"
OPERATOR_EVIDENCE_FINAL_REVIEW_INDEX_AUTHORITY = (
    "non-authoritative; advisory operator evidence final review index only"
)

DEFAULT_OPERATOR_EVIDENCE_FINAL_REVIEW_INPUTS = {
    "review_capsule": (
        "docs/operations/CEREBRO_SELF_EPISTEMIC_OPERATOR_EVIDENCE_REVIEW_CAPSULE.json"
    ),
    "review_capsule_stress_matrix": (
        "docs/operations/CEREBRO_SELF_EPISTEMIC_OPERATOR_EVIDENCE_REVIEW_CAPSULE_STRESS_MATRIX.json"
    ),
    "review_capsule_reproducibility": (
        "docs/operations/"
        "CEREBRO_SELF_EPISTEMIC_OPERATOR_EVIDENCE_REVIEW_CAPSULE_REPRODUCIBILITY_CHECK.json"
    ),
}

_EXPECTED_AUTHORITIES = {
    "review_capsule": OPERATOR_EVIDENCE_REVIEW_CAPSULE_AUTHORITY,
    "review_capsule_stress_matrix": OPERATOR_EVIDENCE_REVIEW_CAPSULE_STRESS_MATRIX_AUTHORITY,
    "review_capsule_reproducibility": OPERATOR_EVIDENCE_REVIEW_CAPSULE_REPRODUCIBILITY_AUTHORITY,
}
_INPUT_IDS = tuple(DEFAULT_OPERATOR_EVIDENCE_FINAL_REVIEW_INPUTS)
_VALID_REVIEW_STATUS = {
    "final_review_clear",
    "blocked_review",
    "incomplete_review_evidence",
}
_HEX_DIGITS = set("0123456789abcdef")


@dataclass(frozen=True)
class OperatorEvidenceFinalReviewInput:
    input_id: str
    path: str
    exists: bool
    parse_status: str
    digest: str = ""
    schema_version: str = ""
    authority: str = ""
    state_change: str = ""
    recommended_human_decision: str = ""
    action_readiness: str = ""
    summary: Mapping[str, Any] | None = None
    blockers: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.input_id not in _INPUT_IDS:
            raise ValueError(f"unknown final review input id: {self.input_id}")
        if not self.path:
            raise ValueError("final review inputs require path")
        if self.digest and not _is_sha256_hex(self.digest):
            raise ValueError("final review input digest must be a lowercase sha256 hex digest")
        if self.exists and self.parse_status == "missing":
            raise ValueError("existing final review inputs cannot be missing")
        if self.parse_status == "parsed" and not isinstance(self.summary, Mapping):
            raise ValueError("parsed final review inputs require summary object")
        if self.parse_status != "parsed" and not self.blockers:
            raise ValueError("non-parsed final review inputs must expose blockers")

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
            "recommended_human_decision": self.recommended_human_decision,
            "action_readiness": self.action_readiness,
            "blocked": self.blocked,
            "blockers": list(self.blockers),
            "summary": dict(self.summary or {}),
        }


@dataclass(frozen=True)
class OperatorEvidenceFinalReviewIndexReport:
    inputs: tuple[OperatorEvidenceFinalReviewInput, ...]
    state_change: str = "none"
    authority: str = OPERATOR_EVIDENCE_FINAL_REVIEW_INDEX_AUTHORITY
    index_role: str = "operator-facing advisory final review index only"

    def __post_init__(self) -> None:
        if self.state_change != "none":
            raise ValueError("operator evidence final review index must not change state")
        if self.authority != OPERATOR_EVIDENCE_FINAL_REVIEW_INDEX_AUTHORITY:
            raise ValueError(f"unsupported final review index authority: {self.authority}")
        if tuple(input_.input_id for input_ in self.inputs) != _INPUT_IDS:
            raise ValueError("operator evidence final review index must use the closed input set")
        if self.review_status not in _VALID_REVIEW_STATUS:
            raise ValueError(f"invalid final review status: {self.review_status}")
        if self.review_status == "final_review_clear" and (
            self.blockers or self.missing_review_evidence
        ):
            raise ValueError("clear final review indexes cannot expose blockers or missing evidence")
        if self.action_readiness == "blocked" and not (
            self.blockers or self.missing_review_evidence
        ):
            raise ValueError("blocked final review indexes must expose visible evidence")

    @property
    def input_blocker_count(self) -> int:
        return sum(len(input_.blockers) for input_ in self.inputs)

    @property
    def blockers(self) -> tuple[str, ...]:
        return tuple(
            f"{input_.input_id}: {blocker}"
            for input_ in self.inputs
            for blocker in input_.blockers
        )

    @property
    def missing_review_evidence(self) -> tuple[str, ...]:
        return tuple(input_.input_id for input_ in self.inputs if not input_.exists)

    @property
    def blocker_count(self) -> int:
        return len(self.blockers)

    @property
    def blocked(self) -> bool:
        return bool(self.blockers or self.missing_review_evidence)

    @property
    def review_status(self) -> str:
        if self.blockers:
            return "blocked_review"
        if self.missing_review_evidence:
            return "incomplete_review_evidence"
        return "final_review_clear"

    @property
    def recommended_human_decision(self) -> str:
        return "review_blockers" if self.blocked else "none"

    @property
    def action_readiness(self) -> str:
        return "blocked" if self.blocked else "advisory_report_allowed"

    @property
    def review_capsule_input(self) -> OperatorEvidenceFinalReviewInput:
        return self.inputs[0]

    @property
    def stress_matrix_input(self) -> OperatorEvidenceFinalReviewInput:
        return self.inputs[1]

    @property
    def reproducibility_input(self) -> OperatorEvidenceFinalReviewInput:
        return self.inputs[2]

    def to_dict(self) -> dict[str, Any]:
        capsule_summary = self.review_capsule_input.summary or {}
        stress_summary = self.stress_matrix_input.summary or {}
        reproducibility_summary = self.reproducibility_input.summary or {}
        return {
            "schema_version": OPERATOR_EVIDENCE_FINAL_REVIEW_INDEX_SCHEMA_VERSION,
            "state_change": self.state_change,
            "authority": self.authority,
            "index_role": self.index_role,
            "summary": {
                "review_status": self.review_status,
                "recommended_human_decision": self.recommended_human_decision,
                "action_readiness": self.action_readiness,
                "blocked": self.blocked,
                "input_count": len(self.inputs),
                "input_blocker_count": self.input_blocker_count,
                "blocker_count": self.blocker_count,
                "missing_review_evidence_count": len(self.missing_review_evidence),
                "capsule_review_status": capsule_summary.get("review_status", ""),
                "capsule_recommended_human_decision": capsule_summary.get(
                    "recommended_human_decision",
                    "",
                ),
                "capsule_action_readiness": capsule_summary.get("action_readiness", ""),
                "capsule_blocker_count": _int_summary(capsule_summary, "blocker_count"),
                "capsule_missing_review_evidence_count": _int_summary(
                    capsule_summary,
                    "missing_review_evidence_count",
                ),
                "stress_scenario_count": _int_summary(stress_summary, "scenario_count"),
                "stress_pass_count": _int_summary(stress_summary, "pass_count"),
                "stress_fail_count": _int_summary(stress_summary, "fail_count"),
                "stress_all_scenarios_passed": stress_summary.get("all_scenarios_passed"),
                "stress_blocker_count": _int_summary(stress_summary, "blocker_count"),
                "stress_degraded_blocker_count": _int_summary(
                    stress_summary,
                    "degraded_blocker_count",
                ),
                "stress_boundary_error_count": _int_summary(
                    stress_summary,
                    "boundary_error_count",
                ),
                "reproducibility_status": reproducibility_summary.get(
                    "reproducibility_status",
                    "",
                ),
                "reproducibility_recommended_human_decision": reproducibility_summary.get(
                    "recommended_human_decision",
                    "",
                ),
                "reproducibility_action_readiness": reproducibility_summary.get(
                    "action_readiness",
                    "",
                ),
                "reproducibility_blocker_count": _int_summary(
                    reproducibility_summary,
                    "blocker_count",
                ),
                "reproducibility_mismatch_count": _int_summary(
                    reproducibility_summary,
                    "mismatch_count",
                ),
                "reproducibility_missing_artifact_count": _int_summary(
                    reproducibility_summary,
                    "missing_artifact_count",
                ),
                "json_digest_match": reproducibility_summary.get("json_digest_match"),
                "markdown_digest_match": reproducibility_summary.get(
                    "markdown_digest_match",
                ),
                "dependency_statuses": {
                    input_.input_id: {
                        "path": input_.path,
                        "parse_status": input_.parse_status,
                        "digest": input_.digest,
                        "blocked": input_.blocked,
                        "blocker_count": len(input_.blockers),
                    }
                    for input_ in self.inputs
                },
            },
            "inputs": [input_.to_dict() for input_ in self.inputs],
            "blockers": list(self.blockers),
            "missing_review_evidence": list(self.missing_review_evidence),
            "guardrails": {
                "registered_is_not_true": True,
                "retrieved_is_not_relevant": True,
                "remembered_is_not_trusted": True,
                "silence_is_not_negative_evidence": True,
                "final_review_index_is_not_permission": True,
                "final_review_index_is_not_memory": True,
                "final_review_index_is_not_authority": True,
                "final_review_index_is_not_runtime_gate": True,
                "final_review_index_is_not_claim_graph": True,
                "final_review_index_is_not_source_registry": True,
                "final_review_index_is_not_canonical_evidence_graph": True,
                "review_clear_is_not_permission": True,
                "stress_pass_is_not_permission": True,
                "reproducibility_is_not_permission": True,
                "digest_equality_is_not_truth": True,
                "dependency_clean_is_not_truth": True,
                "final_review_clear_is_review_evidence_only": True,
            },
            "boundary": {
                "may_suggest": [
                    "summarize the current checked operator evidence review chain",
                    "show missing final review inputs as blockers",
                    "show malformed final review inputs as blockers",
                    "show mutating final review inputs as blockers",
                    "show root escapes and .cerebro targets as boundary blockers",
                    "show failed review capsule inputs as blockers",
                    "show failed review capsule stress matrix as blockers",
                    "show stale or failed review capsule reproducibility as blockers",
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
                    "treat final review index as permission",
                    "treat review clear as permission",
                    "treat stress pass as permission",
                    "treat reproducibility as permission",
                    "treat digest equality as truth",
                    "hide blockers",
                    "hide missing evidence",
                    "infer negative evidence from silence",
                ],
            },
        }


def build_operator_evidence_final_review_index(
    project_root: str | Path,
    input_paths: Mapping[str, str | Path] | None = None,
) -> OperatorEvidenceFinalReviewIndexReport:
    root = Path(project_root).resolve()
    paths = dict(DEFAULT_OPERATOR_EVIDENCE_FINAL_REVIEW_INPUTS)
    if input_paths is not None:
        unknown = set(input_paths) - set(DEFAULT_OPERATOR_EVIDENCE_FINAL_REVIEW_INPUTS)
        if unknown:
            raise ValueError(f"unknown final review input ids: {', '.join(sorted(unknown))}")
        paths.update(input_paths)
    return OperatorEvidenceFinalReviewIndexReport(
        inputs=tuple(_load_final_review_input(root, input_id, paths[input_id]) for input_id in _INPUT_IDS)
    )


def render_operator_evidence_final_review_index_json(
    report: OperatorEvidenceFinalReviewIndexReport,
) -> str:
    return json.dumps(report.to_dict(), indent=2, sort_keys=True) + "\n"


def render_operator_evidence_final_review_index_markdown(
    report: OperatorEvidenceFinalReviewIndexReport,
) -> str:
    payload = report.to_dict()
    summary = payload["summary"]
    lines = [
        "# Epistemic Readiness Operator Evidence Final Review Index",
        "",
        "## Boundary",
        "",
        f"- state_change: {report.state_change}",
        f"- authority: {report.authority}",
        f"- index_role: {report.index_role}",
        "- final_review_index_is_not_permission: true",
        "- final_review_index_is_not_memory: true",
        "- final_review_index_is_not_authority: true",
        "- final_review_index_is_not_runtime_gate: true",
        "- final_review_index_is_not_claim_graph: true",
        "- final_review_index_is_not_source_registry: true",
        "- review_clear_is_not_permission: true",
        "- stress_pass_is_not_permission: true",
        "- reproducibility_is_not_permission: true",
        "- digest_equality_is_not_truth: true",
        "- silence_is_not_negative_evidence: true",
        "",
        "## Summary",
        "",
        f"- review_status: `{summary['review_status']}`",
        f"- recommended_human_decision: `{summary['recommended_human_decision']}`",
        f"- action_readiness: `{summary['action_readiness']}`",
        f"- blocked: `{_json_bool(summary['blocked'])}`",
        f"- input_count: `{summary['input_count']}`",
        f"- blocker_count: `{summary['blocker_count']}`",
        f"- missing_review_evidence_count: `{summary['missing_review_evidence_count']}`",
        "",
        "## Evidence Chain",
        "",
        "| Input | Status | Digest | Blockers |",
        "|---|---|---|---:|",
    ]
    for input_ in report.inputs:
        lines.append(
            "| "
            f"`{input_.input_id}` | "
            f"`{input_.parse_status}` | "
            f"`{input_.digest[:12] if input_.digest else ''}` | "
            f"{len(input_.blockers)} |"
        )

    lines.extend(
        [
            "",
            "## Capsule",
            "",
            f"- capsule_review_status: `{summary['capsule_review_status']}`",
            f"- capsule_recommended_human_decision: `{summary['capsule_recommended_human_decision']}`",
            f"- capsule_action_readiness: `{summary['capsule_action_readiness']}`",
            f"- capsule_blocker_count: `{summary['capsule_blocker_count']}`",
            "",
            "## Stress Matrix",
            "",
            f"- stress_scenario_count: `{summary['stress_scenario_count']}`",
            f"- stress_pass_count: `{summary['stress_pass_count']}`",
            f"- stress_fail_count: `{summary['stress_fail_count']}`",
            f"- stress_all_scenarios_passed: `{_json_bool(summary['stress_all_scenarios_passed'])}`",
            f"- stress_blocker_count: `{summary['stress_blocker_count']}`",
            f"- stress_degraded_blocker_count: `{summary['stress_degraded_blocker_count']}`",
            f"- stress_boundary_error_count: `{summary['stress_boundary_error_count']}`",
            "",
            "## Reproducibility",
            "",
            f"- reproducibility_status: `{summary['reproducibility_status']}`",
            f"- reproducibility_recommended_human_decision: `{summary['reproducibility_recommended_human_decision']}`",
            f"- reproducibility_action_readiness: `{summary['reproducibility_action_readiness']}`",
            f"- reproducibility_blocker_count: `{summary['reproducibility_blocker_count']}`",
            f"- reproducibility_mismatch_count: `{summary['reproducibility_mismatch_count']}`",
            f"- reproducibility_missing_artifact_count: `{summary['reproducibility_missing_artifact_count']}`",
            f"- json_digest_match: `{_json_bool(summary['json_digest_match'])}`",
            f"- markdown_digest_match: `{_json_bool(summary['markdown_digest_match'])}`",
            "",
            "## Blockers",
            "",
        ]
    )
    if report.blockers:
        for blocker in report.blockers:
            lines.append(f"- {blocker}")
    else:
        lines.append("- none")

    lines.extend(["", "## Missing Review Evidence", ""])
    if report.missing_review_evidence:
        for item in report.missing_review_evidence:
            lines.append(f"- {item}")
    else:
        lines.append("- none")

    lines.extend(["", "## Must Not Apply", ""])
    for item in payload["boundary"]["must_not_apply"]:
        lines.append(f"- {item}")
    return "\n".join(lines) + "\n"


def _load_final_review_input(
    root: Path,
    input_id: str,
    path: str | Path,
) -> OperatorEvidenceFinalReviewInput:
    try:
        resolved, label = _resolve_under_project_root(root, path)
    except ValueError as exc:
        return OperatorEvidenceFinalReviewInput(
            input_id=input_id,
            path=str(path).replace("\\", "/"),
            exists=False,
            parse_status="blocked_path",
            blockers=(f"path blocked: {exc}",),
        )

    if not resolved.exists():
        return OperatorEvidenceFinalReviewInput(
            input_id=input_id,
            path=label,
            exists=False,
            parse_status="missing",
            blockers=(f"final review input is missing: {label}",),
        )

    try:
        text = resolved.read_text(encoding="utf-8")
    except OSError as exc:
        return OperatorEvidenceFinalReviewInput(
            input_id=input_id,
            path=label,
            exists=True,
            parse_status="unreadable",
            blockers=(f"final review input could not be read: {exc}",),
        )

    digest = _text_digest(text)
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        return OperatorEvidenceFinalReviewInput(
            input_id=input_id,
            path=label,
            exists=True,
            parse_status="malformed",
            digest=digest,
            blockers=(f"final review input is malformed: {exc.msg}",),
        )
    if not isinstance(payload, Mapping):
        return OperatorEvidenceFinalReviewInput(
            input_id=input_id,
            path=label,
            exists=True,
            parse_status="malformed",
            digest=digest,
            blockers=("final review input JSON root must be an object",),
        )

    summary = payload.get("summary")
    blockers = _generic_payload_blockers(input_id, payload)
    if isinstance(summary, Mapping):
        blockers.extend(_summary_blockers(input_id, summary))
    return OperatorEvidenceFinalReviewInput(
        input_id=input_id,
        path=label,
        exists=True,
        parse_status="parsed",
        digest=digest,
        schema_version=str(payload.get("schema_version", "")),
        authority=str(payload.get("authority", "")),
        state_change=str(payload.get("state_change", "")),
        recommended_human_decision=str(
            summary.get("recommended_human_decision", "") if isinstance(summary, Mapping) else ""
        ),
        action_readiness=str(summary.get("action_readiness", "") if isinstance(summary, Mapping) else ""),
        summary=dict(summary) if isinstance(summary, Mapping) else {},
        blockers=tuple(blockers),
    )


def _generic_payload_blockers(input_id: str, payload: Mapping[str, Any]) -> list[str]:
    blockers: list[str] = []
    if payload.get("schema_version") != "1":
        blockers.append("final review input schema_version must be 1")
    if payload.get("state_change") != "none":
        blockers.append("final review input must declare state_change none")
    if payload.get("authority") != _EXPECTED_AUTHORITIES[input_id]:
        blockers.append("final review input authority does not match expected advisory authority")
    if "summary" not in payload:
        blockers.append("final review input missing summary")
    elif not isinstance(payload.get("summary"), Mapping):
        blockers.append("final review input summary must be an object")
    return blockers


def _summary_blockers(input_id: str, summary: Mapping[str, Any]) -> list[str]:
    if input_id == "review_capsule":
        return _review_capsule_summary_blockers(summary)
    if input_id == "review_capsule_stress_matrix":
        return _stress_matrix_summary_blockers(summary)
    if input_id == "review_capsule_reproducibility":
        return _reproducibility_summary_blockers(summary)
    raise ValueError(f"unknown final review input id: {input_id}")


def _review_capsule_summary_blockers(summary: Mapping[str, Any]) -> list[str]:
    blockers: list[str] = []
    _require_summary_keys(
        blockers,
        summary,
        (
            "review_status",
            "recommended_human_decision",
            "action_readiness",
            "blocker_count",
            "input_blocker_count",
            "missing_review_evidence_count",
        ),
    )
    if summary.get("review_status") != "review_clear":
        blockers.append("review capsule must be review_clear")
    if summary.get("recommended_human_decision") != "none":
        blockers.append("review capsule recommended_human_decision must be none")
    if summary.get("action_readiness") != "advisory_report_allowed":
        blockers.append("review capsule action_readiness must be advisory_report_allowed")
    for field_name in ("blocker_count", "input_blocker_count", "missing_review_evidence_count"):
        if _int_summary(summary, field_name) != 0:
            blockers.append(f"review capsule {field_name} must be 0")
    return blockers


def _stress_matrix_summary_blockers(summary: Mapping[str, Any]) -> list[str]:
    blockers: list[str] = []
    _require_summary_keys(
        blockers,
        summary,
        ("scenario_count", "pass_count", "fail_count", "all_scenarios_passed"),
    )
    scenario_count = _int_summary(summary, "scenario_count")
    pass_count = _int_summary(summary, "pass_count")
    fail_count = _int_summary(summary, "fail_count")
    if scenario_count <= 0:
        blockers.append("review capsule stress matrix scenario_count must be positive")
    if pass_count != scenario_count:
        blockers.append("review capsule stress matrix pass_count must equal scenario_count")
    if fail_count != 0:
        blockers.append("review capsule stress matrix fail_count must be 0")
    if summary.get("all_scenarios_passed") is not True:
        blockers.append("review capsule stress matrix all_scenarios_passed must be true")
    return blockers


def _reproducibility_summary_blockers(summary: Mapping[str, Any]) -> list[str]:
    blockers: list[str] = []
    _require_summary_keys(
        blockers,
        summary,
        (
            "reproducibility_status",
            "recommended_human_decision",
            "action_readiness",
            "blocker_count",
            "mismatch_count",
            "missing_artifact_count",
            "json_digest_match",
            "markdown_digest_match",
        ),
    )
    if summary.get("reproducibility_status") != "reproducible":
        blockers.append("review capsule reproducibility_status must be reproducible")
    if summary.get("recommended_human_decision") != "none":
        blockers.append("review capsule reproducibility recommended_human_decision must be none")
    if summary.get("action_readiness") != "advisory_report_allowed":
        blockers.append("review capsule reproducibility action_readiness must be advisory_report_allowed")
    for field_name in ("blocker_count", "mismatch_count", "missing_artifact_count"):
        if _int_summary(summary, field_name) != 0:
            blockers.append(f"review capsule reproducibility {field_name} must be 0")
    if summary.get("json_digest_match") is not True:
        blockers.append("review capsule reproducibility json_digest_match must be true")
    if summary.get("markdown_digest_match") is not True:
        blockers.append("review capsule reproducibility markdown_digest_match must be true")
    return blockers


def _require_summary_keys(
    blockers: list[str],
    summary: Mapping[str, Any],
    required_keys: tuple[str, ...],
) -> None:
    missing = [key for key in required_keys if key not in summary]
    if missing:
        blockers.append(f"final review input summary missing keys: {', '.join(missing)}")


def _resolve_under_project_root(root: Path, path: str | Path) -> tuple[Path, str]:
    path_obj = Path(path)
    if any(part == ".cerebro" for part in path_obj.parts):
        raise ValueError("path crosses canonical state boundary")
    resolved = path_obj.resolve() if path_obj.is_absolute() else (root / path_obj).resolve()
    try:
        relative = resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"path escapes project root: {path}") from exc
    if any(part == ".cerebro" for part in relative.parts):
        raise ValueError("path crosses canonical state boundary")
    return resolved, relative.as_posix()


def _int_summary(summary: Mapping[str, Any], key: str) -> int:
    value = summary.get(key)
    return value if isinstance(value, int) and not isinstance(value, bool) else -1


def _text_digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _is_sha256_hex(value: str) -> bool:
    return len(value) == 64 and all(char in _HEX_DIGITS for char in value)


def _json_bool(value: Any) -> str:
    if value is None:
        return "null"
    return str(bool(value)).lower() if isinstance(value, bool) else str(value).lower()
