from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from .operator_evidence_final_review_index import OPERATOR_EVIDENCE_FINAL_REVIEW_INDEX_AUTHORITY
from .operator_evidence_final_review_index_stress_matrix import (
    OPERATOR_EVIDENCE_FINAL_REVIEW_INDEX_STRESS_MATRIX_AUTHORITY,
)
from .operator_evidence_final_review_index_stress_reproducibility import (
    OPERATOR_EVIDENCE_FINAL_REVIEW_INDEX_STRESS_REPRODUCIBILITY_AUTHORITY,
)


OPERATOR_EVIDENCE_CHAIN_CLOSEOUT_SCHEMA_VERSION = "1"
OPERATOR_EVIDENCE_CHAIN_CLOSEOUT_AUTHORITY = (
    "non-authoritative; advisory operator evidence chain closeout only"
)

DEFAULT_OPERATOR_EVIDENCE_CHAIN_CLOSEOUT_INPUTS = {
    "final_review_index": (
        "docs/operations/CEREBRO_SELF_EPISTEMIC_OPERATOR_EVIDENCE_FINAL_REVIEW_INDEX.json"
    ),
    "final_review_index_stress_matrix": (
        "docs/operations/"
        "CEREBRO_SELF_EPISTEMIC_OPERATOR_EVIDENCE_FINAL_REVIEW_INDEX_STRESS_MATRIX.json"
    ),
    "final_review_index_stress_reproducibility": (
        "docs/operations/"
        "CEREBRO_SELF_EPISTEMIC_OPERATOR_EVIDENCE_FINAL_REVIEW_INDEX_STRESS_REPRODUCIBILITY_CHECK.json"
    ),
}

_EXPECTED_AUTHORITIES = {
    "final_review_index": OPERATOR_EVIDENCE_FINAL_REVIEW_INDEX_AUTHORITY,
    "final_review_index_stress_matrix": (
        OPERATOR_EVIDENCE_FINAL_REVIEW_INDEX_STRESS_MATRIX_AUTHORITY
    ),
    "final_review_index_stress_reproducibility": (
        OPERATOR_EVIDENCE_FINAL_REVIEW_INDEX_STRESS_REPRODUCIBILITY_AUTHORITY
    ),
}
_INPUT_IDS = tuple(DEFAULT_OPERATOR_EVIDENCE_CHAIN_CLOSEOUT_INPUTS)
_HEX_DIGITS = set("0123456789abcdef")


@dataclass(frozen=True)
class OperatorEvidenceChainCloseoutInput:
    input_id: str
    path: str
    exists: bool
    parse_status: str
    digest: str = ""
    schema_version: str = ""
    authority: str = ""
    state_change: str = ""
    summary: Mapping[str, Any] | None = None
    blockers: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.input_id not in _INPUT_IDS:
            raise ValueError(f"unknown operator evidence chain closeout input id: {self.input_id}")
        if not self.path:
            raise ValueError("operator evidence chain closeout inputs require path")
        if self.digest and not _is_sha256_hex(self.digest):
            raise ValueError("closeout input digest must be a lowercase sha256 hex digest")
        if self.exists and self.parse_status == "missing":
            raise ValueError("existing closeout inputs cannot be missing")
        if self.parse_status == "parsed" and not isinstance(self.summary, Mapping):
            raise ValueError("parsed closeout inputs require summary object")
        if self.parse_status != "parsed" and not self.blockers:
            raise ValueError("non-parsed closeout inputs must expose blockers")

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
            "blocked": self.blocked,
            "blockers": list(self.blockers),
            "summary": dict(self.summary or {}),
        }


@dataclass(frozen=True)
class OperatorEvidenceChainCloseoutReport:
    inputs: tuple[OperatorEvidenceChainCloseoutInput, ...]
    state_change: str = "none"
    authority: str = OPERATOR_EVIDENCE_CHAIN_CLOSEOUT_AUTHORITY
    closeout_role: str = "advisory operator evidence recursion-stop report only"

    def __post_init__(self) -> None:
        if self.state_change != "none":
            raise ValueError("operator evidence chain closeout must not change state")
        if self.authority != OPERATOR_EVIDENCE_CHAIN_CLOSEOUT_AUTHORITY:
            raise ValueError(f"unsupported operator evidence chain closeout authority: {self.authority}")
        if tuple(input_.input_id for input_ in self.inputs) != _INPUT_IDS:
            raise ValueError("operator evidence chain closeout must use the closed input set")
        if self.recursive_hardening_stopped and self.blockers:
            raise ValueError("recursive hardening cannot stop while blockers are visible")
        if self.action_readiness == "no_action" and self.blockers:
            raise ValueError("blocked closeouts cannot report no_action readiness")

    @property
    def blockers(self) -> tuple[str, ...]:
        return tuple(
            f"{input_.input_id}: {blocker}"
            for input_ in self.inputs
            for blocker in input_.blockers
        )

    @property
    def missing_evidence(self) -> tuple[str, ...]:
        return tuple(input_.input_id for input_ in self.inputs if not input_.exists)

    @property
    def blocker_count(self) -> int:
        return len(self.blockers)

    @property
    def blocked(self) -> bool:
        return bool(self.blockers)

    @property
    def closeout_status(self) -> str:
        return "blocked_closeout" if self.blocked else "closed_until_new_evidence"

    @property
    def recommended_human_decision(self) -> str:
        return "review_blockers" if self.blocked else "none"

    @property
    def action_readiness(self) -> str:
        return "blocked" if self.blocked else "no_action"

    @property
    def recursive_hardening_stopped(self) -> bool:
        return not self.blocked

    @property
    def final_review_index_input(self) -> OperatorEvidenceChainCloseoutInput:
        return self.inputs[0]

    @property
    def stress_matrix_input(self) -> OperatorEvidenceChainCloseoutInput:
        return self.inputs[1]

    @property
    def stress_reproducibility_input(self) -> OperatorEvidenceChainCloseoutInput:
        return self.inputs[2]

    def to_dict(self) -> dict[str, Any]:
        final_summary = self.final_review_index_input.summary or {}
        stress_summary = self.stress_matrix_input.summary or {}
        repro_summary = self.stress_reproducibility_input.summary or {}
        return {
            "schema_version": OPERATOR_EVIDENCE_CHAIN_CLOSEOUT_SCHEMA_VERSION,
            "state_change": self.state_change,
            "authority": self.authority,
            "closeout_role": self.closeout_role,
            "summary": {
                "closeout_status": self.closeout_status,
                "recommended_human_decision": self.recommended_human_decision,
                "action_readiness": self.action_readiness,
                "recursive_hardening_stopped": self.recursive_hardening_stopped,
                "input_count": len(self.inputs),
                "blocker_count": self.blocker_count,
                "missing_evidence_count": len(self.missing_evidence),
                "final_review_status": final_summary.get("review_status", ""),
                "final_review_action_readiness": final_summary.get("action_readiness", ""),
                "final_review_blocker_count": _int_summary(final_summary, "blocker_count"),
                "stress_scenario_count": _int_summary(stress_summary, "scenario_count"),
                "stress_pass_count": _int_summary(stress_summary, "pass_count"),
                "stress_fail_count": _int_summary(stress_summary, "fail_count"),
                "stress_all_scenarios_passed": stress_summary.get("all_scenarios_passed"),
                "stress_degraded_blocker_count": _int_summary(
                    stress_summary,
                    "degraded_blocker_count",
                ),
                "stress_boundary_error_count": _int_summary(
                    stress_summary,
                    "boundary_error_count",
                ),
                "reproducibility_status": repro_summary.get("reproducibility_status", ""),
                "reproducibility_blocker_count": _int_summary(
                    repro_summary,
                    "blocker_count",
                ),
                "reproducibility_mismatch_count": _int_summary(
                    repro_summary,
                    "mismatch_count",
                ),
                "reproducibility_missing_artifact_count": _int_summary(
                    repro_summary,
                    "missing_artifact_count",
                ),
                "json_digest_match": repro_summary.get("json_digest_match"),
                "markdown_digest_match": repro_summary.get("markdown_digest_match"),
            },
            "closeout_criteria": [
                "final review index is final_review_clear",
                "final review index exposes no blockers or missing review evidence",
                "final review index stress matrix has all closed scenarios passing",
                "final review index stress matrix exposes degraded blockers in stress cases",
                "stress reproducibility check is reproducible",
                "stress reproducibility check has no blockers, mismatches, or missing artifacts",
                "all upstream artifacts declare state_change none",
                "all upstream artifacts retain expected non-authoritative advisory authority",
            ],
            "reopen_triggers": [
                "any upstream closeout input becomes missing, malformed, stale, mutating, or blocked",
                "final review index no longer reports final_review_clear",
                "final review index stress matrix adds, removes, or fails a scenario",
                "stress reproducibility stops matching checked JSON or Markdown artifacts",
                "a new operator decision surface is introduced",
                "a real operator blocker or mismatch appears",
                "human approval asks to evaluate promotion beyond derived advisory evidence",
                "any consumer starts treating advisory closeout as permission, memory, truth, or authority",
            ],
            "inputs": [input_.to_dict() for input_ in self.inputs],
            "blockers": list(self.blockers),
            "missing_evidence": list(self.missing_evidence),
            "guardrails": {
                "registered_is_not_true": True,
                "retrieved_is_not_relevant": True,
                "remembered_is_not_trusted": True,
                "silence_is_not_negative_evidence": True,
                "closeout_is_not_permission": True,
                "closeout_is_not_memory": True,
                "closeout_is_not_authority": True,
                "closeout_is_not_runtime_gate": True,
                "closeout_is_not_claim_graph": True,
                "closeout_is_not_source_registry": True,
                "recursive_stop_is_not_permanent_freeze": True,
                "review_clear_is_not_permission": True,
                "stress_pass_is_not_permission": True,
                "reproducibility_is_not_permission": True,
                "digest_equality_is_not_truth": True,
                "no_action_is_not_human_approval": True,
            },
            "boundary": {
                "may_suggest": [
                    "stop recursive hardening of the current derived operator evidence lane",
                    "summarize why the current final review chain is closed until new evidence",
                    "show upstream blockers as closeout blockers",
                    "declare reopen triggers for future slices",
                    "recommend human review if a real blocker, mismatch, or promotion question appears",
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
                    "treat closeout as permission",
                    "treat no_action as human approval",
                    "treat recursive stop as permanent freeze",
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


def build_operator_evidence_chain_closeout(
    project_root: str | Path,
    input_paths: Mapping[str, str | Path] | None = None,
) -> OperatorEvidenceChainCloseoutReport:
    root = Path(project_root).resolve()
    paths = dict(DEFAULT_OPERATOR_EVIDENCE_CHAIN_CLOSEOUT_INPUTS)
    if input_paths is not None:
        unknown = set(input_paths) - set(DEFAULT_OPERATOR_EVIDENCE_CHAIN_CLOSEOUT_INPUTS)
        if unknown:
            raise ValueError(f"unknown closeout input ids: {', '.join(sorted(unknown))}")
        paths.update(input_paths)
    return OperatorEvidenceChainCloseoutReport(
        inputs=tuple(_load_closeout_input(root, input_id, paths[input_id]) for input_id in _INPUT_IDS)
    )


def render_operator_evidence_chain_closeout_json(
    report: OperatorEvidenceChainCloseoutReport,
) -> str:
    return json.dumps(report.to_dict(), indent=2, sort_keys=True) + "\n"


def render_operator_evidence_chain_closeout_markdown(
    report: OperatorEvidenceChainCloseoutReport,
) -> str:
    payload = report.to_dict()
    summary = payload["summary"]
    lines = [
        "# Epistemic Readiness Operator Evidence Chain Closeout",
        "",
        "## Boundary",
        "",
        f"- state_change: {report.state_change}",
        f"- authority: {report.authority}",
        f"- closeout_role: {report.closeout_role}",
        "- closeout_is_not_permission: true",
        "- closeout_is_not_memory: true",
        "- closeout_is_not_authority: true",
        "- closeout_is_not_runtime_gate: true",
        "- closeout_is_not_claim_graph: true",
        "- closeout_is_not_source_registry: true",
        "- recursive_stop_is_not_permanent_freeze: true",
        "- no_action_is_not_human_approval: true",
        "- digest_equality_is_not_truth: true",
        "- silence_is_not_negative_evidence: true",
        "",
        "## Summary",
        "",
        f"- closeout_status: `{summary['closeout_status']}`",
        f"- recommended_human_decision: `{summary['recommended_human_decision']}`",
        f"- action_readiness: `{summary['action_readiness']}`",
        f"- recursive_hardening_stopped: `{_json_bool(summary['recursive_hardening_stopped'])}`",
        f"- input_count: `{summary['input_count']}`",
        f"- blocker_count: `{summary['blocker_count']}`",
        f"- missing_evidence_count: `{summary['missing_evidence_count']}`",
        "",
        "## Upstream Evidence",
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

    lines.extend(["", "## Closeout Criteria", ""])
    for item in payload["closeout_criteria"]:
        lines.append(f"- {item}")

    lines.extend(["", "## Reopen Triggers", ""])
    for item in payload["reopen_triggers"]:
        lines.append(f"- {item}")

    lines.extend(["", "## Blockers", ""])
    if report.blockers:
        for blocker in report.blockers:
            lines.append(f"- {blocker}")
    else:
        lines.append("- none")

    lines.extend(["", "## Must Not Apply", ""])
    for item in payload["boundary"]["must_not_apply"]:
        lines.append(f"- {item}")
    return "\n".join(lines) + "\n"


def _load_closeout_input(
    root: Path,
    input_id: str,
    path: str | Path,
) -> OperatorEvidenceChainCloseoutInput:
    try:
        resolved, label = _resolve_under_project_root(root, path)
    except ValueError as exc:
        return OperatorEvidenceChainCloseoutInput(
            input_id=input_id,
            path=str(path).replace("\\", "/"),
            exists=False,
            parse_status="blocked_path",
            blockers=(f"path blocked: {exc}",),
        )

    if not resolved.exists():
        return OperatorEvidenceChainCloseoutInput(
            input_id=input_id,
            path=label,
            exists=False,
            parse_status="missing",
            blockers=(f"closeout input is missing: {label}",),
        )

    try:
        text = resolved.read_text(encoding="utf-8")
    except OSError as exc:
        return OperatorEvidenceChainCloseoutInput(
            input_id=input_id,
            path=label,
            exists=True,
            parse_status="unreadable",
            blockers=(f"closeout input could not be read: {exc}",),
        )

    digest = _text_digest(text)
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        return OperatorEvidenceChainCloseoutInput(
            input_id=input_id,
            path=label,
            exists=True,
            parse_status="malformed",
            digest=digest,
            blockers=(f"closeout input is malformed: {exc.msg}",),
        )
    if not isinstance(payload, Mapping):
        return OperatorEvidenceChainCloseoutInput(
            input_id=input_id,
            path=label,
            exists=True,
            parse_status="malformed",
            digest=digest,
            blockers=("closeout input JSON root must be an object",),
        )

    summary = payload.get("summary")
    blockers = _generic_payload_blockers(input_id, payload)
    if isinstance(summary, Mapping):
        blockers.extend(_summary_blockers(input_id, summary))
    return OperatorEvidenceChainCloseoutInput(
        input_id=input_id,
        path=label,
        exists=True,
        parse_status="parsed",
        digest=digest,
        schema_version=str(payload.get("schema_version", "")),
        authority=str(payload.get("authority", "")),
        state_change=str(payload.get("state_change", "")),
        summary=dict(summary) if isinstance(summary, Mapping) else {},
        blockers=tuple(blockers),
    )


def _generic_payload_blockers(input_id: str, payload: Mapping[str, Any]) -> list[str]:
    blockers: list[str] = []
    if payload.get("schema_version") != "1":
        blockers.append("closeout input schema_version must be 1")
    if payload.get("state_change") != "none":
        blockers.append("closeout input must declare state_change none")
    if payload.get("authority") != _EXPECTED_AUTHORITIES[input_id]:
        blockers.append("closeout input authority does not match expected advisory authority")
    if "summary" not in payload:
        blockers.append("closeout input missing summary")
    elif not isinstance(payload.get("summary"), Mapping):
        blockers.append("closeout input summary must be an object")
    return blockers


def _summary_blockers(input_id: str, summary: Mapping[str, Any]) -> list[str]:
    if input_id == "final_review_index":
        return _final_review_summary_blockers(summary)
    if input_id == "final_review_index_stress_matrix":
        return _stress_summary_blockers(summary)
    if input_id == "final_review_index_stress_reproducibility":
        return _reproducibility_summary_blockers(summary)
    raise ValueError(f"unknown closeout input id: {input_id}")


def _final_review_summary_blockers(summary: Mapping[str, Any]) -> list[str]:
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
    if summary.get("review_status") != "final_review_clear":
        blockers.append("final review index must be final_review_clear")
    if summary.get("recommended_human_decision") != "none":
        blockers.append("final review index recommended_human_decision must be none")
    if summary.get("action_readiness") != "advisory_report_allowed":
        blockers.append("final review index action_readiness must be advisory_report_allowed")
    for field_name in ("blocker_count", "input_blocker_count", "missing_review_evidence_count"):
        if _int_summary(summary, field_name) != 0:
            blockers.append(f"final review index {field_name} must be 0")
    return blockers


def _stress_summary_blockers(summary: Mapping[str, Any]) -> list[str]:
    blockers: list[str] = []
    _require_summary_keys(
        blockers,
        summary,
        (
            "scenario_count",
            "pass_count",
            "fail_count",
            "all_scenarios_passed",
            "degraded_blocker_count",
        ),
    )
    scenario_count = _int_summary(summary, "scenario_count")
    pass_count = _int_summary(summary, "pass_count")
    fail_count = _int_summary(summary, "fail_count")
    if scenario_count <= 0:
        blockers.append("final review index stress matrix scenario_count must be positive")
    if pass_count != scenario_count:
        blockers.append("final review index stress matrix pass_count must equal scenario_count")
    if fail_count != 0:
        blockers.append("final review index stress matrix fail_count must be 0")
    if summary.get("all_scenarios_passed") is not True:
        blockers.append("final review index stress matrix all_scenarios_passed must be true")
    if _int_summary(summary, "degraded_blocker_count") <= 0:
        blockers.append("final review index stress matrix must expose degraded blockers")
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
        blockers.append("stress reproducibility_status must be reproducible")
    if summary.get("recommended_human_decision") != "none":
        blockers.append("stress reproducibility recommended_human_decision must be none")
    if summary.get("action_readiness") != "advisory_report_allowed":
        blockers.append("stress reproducibility action_readiness must be advisory_report_allowed")
    for field_name in ("blocker_count", "mismatch_count", "missing_artifact_count"):
        if _int_summary(summary, field_name) != 0:
            blockers.append(f"stress reproducibility {field_name} must be 0")
    if summary.get("json_digest_match") is not True:
        blockers.append("stress reproducibility json_digest_match must be true")
    if summary.get("markdown_digest_match") is not True:
        blockers.append("stress reproducibility markdown_digest_match must be true")
    return blockers


def _require_summary_keys(
    blockers: list[str],
    summary: Mapping[str, Any],
    required_keys: tuple[str, ...],
) -> None:
    missing = [key for key in required_keys if key not in summary]
    if missing:
        blockers.append(f"closeout input summary missing keys: {', '.join(missing)}")


def _resolve_under_project_root(root: Path, path: str | Path) -> tuple[Path, str]:
    path_obj = Path(path)
    if any(part.lower() == ".cerebro" for part in path_obj.parts):
        raise ValueError("path crosses canonical state boundary")
    resolved = path_obj.resolve() if path_obj.is_absolute() else (root / path_obj).resolve()
    try:
        relative = resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"path escapes project root: {path}") from exc
    if any(part.lower() == ".cerebro" for part in relative.parts):
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


__all__ = [
    "OPERATOR_EVIDENCE_CHAIN_CLOSEOUT_AUTHORITY",
    "OperatorEvidenceChainCloseoutInput",
    "OperatorEvidenceChainCloseoutReport",
    "build_operator_evidence_chain_closeout",
    "render_operator_evidence_chain_closeout_json",
    "render_operator_evidence_chain_closeout_markdown",
]
