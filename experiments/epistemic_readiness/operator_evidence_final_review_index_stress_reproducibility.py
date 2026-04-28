from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from .operator_evidence_final_review_index_stress_matrix import (
    OPERATOR_EVIDENCE_FINAL_REVIEW_INDEX_STRESS_MATRIX_AUTHORITY,
    build_operator_evidence_final_review_index_stress_matrix,
    render_operator_evidence_final_review_index_stress_matrix_json,
    render_operator_evidence_final_review_index_stress_matrix_markdown,
)


OPERATOR_EVIDENCE_FINAL_REVIEW_INDEX_STRESS_REPRODUCIBILITY_SCHEMA_VERSION = "1"
OPERATOR_EVIDENCE_FINAL_REVIEW_INDEX_STRESS_REPRODUCIBILITY_AUTHORITY = (
    "non-authoritative; advisory operator evidence final review index stress "
    "reproducibility check only"
)

DEFAULT_OPERATOR_EVIDENCE_FINAL_REVIEW_INDEX_STRESS_JSON_PATH = (
    "docs/operations/CEREBRO_SELF_EPISTEMIC_OPERATOR_EVIDENCE_FINAL_REVIEW_INDEX_STRESS_MATRIX.json"
)
DEFAULT_OPERATOR_EVIDENCE_FINAL_REVIEW_INDEX_STRESS_MARKDOWN_PATH = (
    "docs/operations/CEREBRO_SELF_EPISTEMIC_OPERATOR_EVIDENCE_FINAL_REVIEW_INDEX_STRESS_MATRIX.md"
)

_ARTIFACT_IDS = (
    "final_review_index_stress_json",
    "final_review_index_stress_markdown",
)
_REQUIRED_CHECKED_JSON_FIELDS = frozenset(
    {
        "schema_version",
        "state_change",
        "authority",
        "matrix_role",
        "summary",
        "scenarios",
        "guardrails",
        "boundary",
    }
)
_REQUIRED_MARKDOWN_GUARDRAILS = (
    "final_review_index_stress_matrix_is_not_permission: true",
    "final_review_index_stress_matrix_is_not_runtime_gate: true",
    "final_review_index_stress_matrix_is_not_source_registry: true",
    "digest_equality_is_not_truth: true",
    "degraded_final_review_evidence_is_review_evidence_only: true",
    "## Must Not Apply",
)
_MAX_MISMATCHES = 16
_HEX_DIGITS = set("0123456789abcdef")


@dataclass(frozen=True)
class OperatorEvidenceFinalReviewIndexStressArtifactCheck:
    artifact_id: str
    path: str
    exists: bool
    check_status: str
    checked_digest: str = ""
    regenerated_digest: str = ""
    digest_match: bool | None = None
    blockers: tuple[str, ...] = ()
    mismatches: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.artifact_id not in _ARTIFACT_IDS:
            raise ValueError(f"unknown final review index stress artifact id: {self.artifact_id}")
        if not self.path:
            raise ValueError("final review index stress artifact checks require path")
        if self.checked_digest and not _is_sha256_hex(self.checked_digest):
            raise ValueError("checked_digest must be a lowercase sha256 hex digest")
        if self.regenerated_digest and not _is_sha256_hex(self.regenerated_digest):
            raise ValueError("regenerated_digest must be a lowercase sha256 hex digest")
        if self.digest_match is True and (
            not self.checked_digest
            or not self.regenerated_digest
            or self.checked_digest != self.regenerated_digest
        ):
            raise ValueError("digest_match true requires equal checked and regenerated digests")
        if self.digest_match is False and self.checked_digest == self.regenerated_digest:
            raise ValueError("digest_match false requires divergent digests")
        if self.check_status == "matched" and (
            not self.exists
            or self.blockers
            or self.mismatches
            or self.digest_match is not True
        ):
            raise ValueError("matched artifact checks must be clean and digest-equal")
        if self.check_status != "matched" and not (self.blockers or self.mismatches):
            raise ValueError("non-matched artifact checks must expose blockers or mismatches")

    @property
    def blocked(self) -> bool:
        return bool(self.blockers or self.mismatches)

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact_id": self.artifact_id,
            "path": self.path,
            "exists": self.exists,
            "check_status": self.check_status,
            "checked_digest": self.checked_digest,
            "regenerated_digest": self.regenerated_digest,
            "digest_match": self.digest_match,
            "blocked": self.blocked,
            "blockers": list(self.blockers),
            "mismatches": list(self.mismatches),
        }


@dataclass(frozen=True)
class OperatorEvidenceFinalReviewIndexStressReproducibilityReport:
    artifacts: tuple[OperatorEvidenceFinalReviewIndexStressArtifactCheck, ...]
    state_change: str = "none"
    authority: str = OPERATOR_EVIDENCE_FINAL_REVIEW_INDEX_STRESS_REPRODUCIBILITY_AUTHORITY
    check_role: str = "advisory checked final-review-index stress artifact reproducibility evidence only"

    def __post_init__(self) -> None:
        if self.state_change != "none":
            raise ValueError("final review index stress reproducibility must not change state")
        if self.authority != OPERATOR_EVIDENCE_FINAL_REVIEW_INDEX_STRESS_REPRODUCIBILITY_AUTHORITY:
            raise ValueError(
                f"unsupported final review index stress reproducibility authority: {self.authority}"
            )
        if tuple(artifact.artifact_id for artifact in self.artifacts) != _ARTIFACT_IDS:
            raise ValueError(
                "final review index stress reproducibility artifacts must use the closed artifact set"
            )
        if not (self.blockers or self.mismatches):
            for artifact in self.artifacts:
                if artifact.digest_match is not True:
                    raise ValueError("clean reproducibility reports require every artifact digest to match")

    @property
    def blockers(self) -> tuple[str, ...]:
        return tuple(
            f"{artifact.artifact_id}: {blocker}"
            for artifact in self.artifacts
            for blocker in artifact.blockers
        )

    @property
    def mismatches(self) -> tuple[str, ...]:
        return tuple(
            f"{artifact.artifact_id}: {mismatch}"
            for artifact in self.artifacts
            for mismatch in artifact.mismatches
        )

    @property
    def blocked(self) -> bool:
        return bool(self.blockers or self.mismatches)

    @property
    def reproducibility_status(self) -> str:
        return "stale_or_mismatched" if self.blocked else "reproducible"

    @property
    def recommended_human_decision(self) -> str:
        return "review_blockers" if self.blocked else "none"

    @property
    def action_readiness(self) -> str:
        return "blocked" if self.blocked else "advisory_report_allowed"

    @property
    def missing_artifact_count(self) -> int:
        return sum(1 for artifact in self.artifacts if not artifact.exists)

    @property
    def mismatch_count(self) -> int:
        return len(self.mismatches)

    @property
    def blocker_count(self) -> int:
        return len(self.blockers) + len(self.mismatches)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": (
                OPERATOR_EVIDENCE_FINAL_REVIEW_INDEX_STRESS_REPRODUCIBILITY_SCHEMA_VERSION
            ),
            "state_change": self.state_change,
            "authority": self.authority,
            "check_role": self.check_role,
            "summary": {
                "reproducibility_status": self.reproducibility_status,
                "recommended_human_decision": self.recommended_human_decision,
                "action_readiness": self.action_readiness,
                "blocked": self.blocked,
                "artifact_count": len(self.artifacts),
                "blocker_count": self.blocker_count,
                "mismatch_count": self.mismatch_count,
                "missing_artifact_count": self.missing_artifact_count,
                "json_digest_match": self.artifacts[0].digest_match,
                "markdown_digest_match": self.artifacts[1].digest_match,
            },
            "artifacts": [artifact.to_dict() for artifact in self.artifacts],
            "blockers": list(self.blockers),
            "mismatches": list(self.mismatches),
            "guardrails": {
                "registered_is_not_true": True,
                "retrieved_is_not_relevant": True,
                "remembered_is_not_trusted": True,
                "silence_is_not_negative_evidence": True,
                "final_review_index_stress_reproducibility_is_not_permission": True,
                "final_review_index_stress_reproducibility_is_not_memory": True,
                "final_review_index_stress_reproducibility_is_not_authority": True,
                "final_review_index_stress_reproducibility_is_not_runtime_gate": True,
                "final_review_index_stress_reproducibility_is_not_claim_graph": True,
                "final_review_index_stress_reproducibility_is_not_source_registry": True,
                "digest_equality_is_not_truth": True,
                "artifact_reproducible_is_not_permission": True,
                "checked_artifact_is_not_memory": True,
                "stale_artifact_is_review_evidence_only": True,
            },
            "boundary": {
                "may_suggest": [
                    "compare checked final review index stress JSON with regenerated advisory output",
                    "compare checked final review index stress Markdown with regenerated advisory output",
                    "show stale checked artifacts as blockers",
                    "show missing checked artifacts as blockers",
                    "show malformed checked artifacts as blockers",
                    "show mutating checked artifacts as blockers",
                    "recommend future hardening slices",
                ],
                "must_not_apply": [
                    "mutate state",
                    "register sources",
                    "refresh checked artifacts automatically",
                    "update replay baseline",
                    "write memory automatically",
                    "act as runtime gate",
                    "create canonical claim graph",
                    "create canonical evidence graph",
                    "promote or demote authority",
                    "treat reproducibility as permission",
                    "treat digest equality as truth",
                    "hide blockers",
                    "hide mismatches",
                    "hide stale checked artifacts",
                    "infer negative evidence from silence",
                ],
            },
        }


def check_operator_evidence_final_review_index_stress_reproducibility(
    project_root: str | Path,
    checked_json_path: str | Path = DEFAULT_OPERATOR_EVIDENCE_FINAL_REVIEW_INDEX_STRESS_JSON_PATH,
    checked_markdown_path: str | Path = (
        DEFAULT_OPERATOR_EVIDENCE_FINAL_REVIEW_INDEX_STRESS_MARKDOWN_PATH
    ),
) -> OperatorEvidenceFinalReviewIndexStressReproducibilityReport:
    root = Path(project_root).resolve()
    stress_matrix = build_operator_evidence_final_review_index_stress_matrix()
    regenerated_json = render_operator_evidence_final_review_index_stress_matrix_json(stress_matrix)
    regenerated_markdown = render_operator_evidence_final_review_index_stress_matrix_markdown(
        stress_matrix
    )

    return OperatorEvidenceFinalReviewIndexStressReproducibilityReport(
        artifacts=(
            _check_json_artifact(root, checked_json_path, regenerated_json),
            _check_markdown_artifact(root, checked_markdown_path, regenerated_markdown),
        ),
    )


def render_operator_evidence_final_review_index_stress_reproducibility_json(
    report: OperatorEvidenceFinalReviewIndexStressReproducibilityReport,
) -> str:
    return json.dumps(report.to_dict(), indent=2, sort_keys=True) + "\n"


def render_operator_evidence_final_review_index_stress_reproducibility_markdown(
    report: OperatorEvidenceFinalReviewIndexStressReproducibilityReport,
) -> str:
    lines = [
        "# Epistemic Readiness Operator Evidence Final Review Index Stress Reproducibility Check",
        "",
        "## Boundary",
        "",
        f"- state_change: {report.state_change}",
        f"- authority: {report.authority}",
        f"- check_role: {report.check_role}",
        "- final_review_index_stress_reproducibility_is_not_permission: true",
        "- final_review_index_stress_reproducibility_is_not_memory: true",
        "- final_review_index_stress_reproducibility_is_not_authority: true",
        "- final_review_index_stress_reproducibility_is_not_runtime_gate: true",
        "- final_review_index_stress_reproducibility_is_not_claim_graph: true",
        "- final_review_index_stress_reproducibility_is_not_source_registry: true",
        "- digest_equality_is_not_truth: true",
        "- artifact_reproducible_is_not_permission: true",
        "- stale_artifact_is_review_evidence_only: true",
        "- silence_is_not_negative_evidence: true",
        "",
        "## Summary",
        "",
        f"- reproducibility_status: `{report.reproducibility_status}`",
        f"- recommended_human_decision: `{report.recommended_human_decision}`",
        f"- action_readiness: `{report.action_readiness}`",
        f"- blocked: `{str(report.blocked).lower()}`",
        f"- artifact_count: `{len(report.artifacts)}`",
        f"- blocker_count: `{report.blocker_count}`",
        f"- mismatch_count: `{report.mismatch_count}`",
        f"- missing_artifact_count: `{report.missing_artifact_count}`",
        "",
        "## Artifacts",
        "",
        "| Artifact | Status | Digest Match | Blockers | Mismatches |",
        "|---|---|---:|---:|---:|",
    ]
    for artifact in report.artifacts:
        lines.append(
            "| "
            f"{artifact.artifact_id} | "
            f"{artifact.check_status} | "
            f"{_json_bool(artifact.digest_match)} | "
            f"{len(artifact.blockers)} | "
            f"{len(artifact.mismatches)} |"
        )

    lines.extend(["", "## Blockers", ""])
    if report.blockers:
        for blocker in report.blockers:
            lines.append(f"- {blocker}")
    else:
        lines.append("- none")

    lines.extend(["", "## Mismatches", ""])
    if report.mismatches:
        for mismatch in report.mismatches:
            lines.append(f"- {mismatch}")
    else:
        lines.append("- none")

    lines.extend(["", "## Must Not Apply", ""])
    for item in report.to_dict()["boundary"]["must_not_apply"]:
        lines.append(f"- {item}")
    return "\n".join(lines) + "\n"


def _check_json_artifact(
    root: Path,
    checked_path: str | Path,
    regenerated_text: str,
) -> OperatorEvidenceFinalReviewIndexStressArtifactCheck:
    blockers, mismatches, label, checked_text = _read_checked_text(root, checked_path)
    checked_digest = _text_digest(checked_text) if checked_text is not None else ""
    regenerated_digest = _text_digest(regenerated_text)
    digest_match = None if checked_text is None else checked_digest == regenerated_digest

    if checked_text is not None:
        try:
            checked_payload = json.loads(checked_text)
        except json.JSONDecodeError as exc:
            blockers.append(f"checked JSON is malformed: {exc.msg}")
            checked_payload = None
        if checked_payload is not None:
            if not isinstance(checked_payload, Mapping):
                blockers.append("checked JSON root must be an object")
            else:
                blockers.extend(_checked_json_blockers(checked_payload))
                if digest_match is False:
                    expected_payload = json.loads(regenerated_text)
                    mismatches.extend(_payload_mismatches(expected_payload, checked_payload))
                    if not mismatches:
                        mismatches.append("checked JSON text does not match regenerated JSON text")

    return OperatorEvidenceFinalReviewIndexStressArtifactCheck(
        artifact_id="final_review_index_stress_json",
        path=label,
        exists=checked_text is not None and "path blocked" not in " ".join(blockers),
        check_status=_check_status(blockers, mismatches, digest_match),
        checked_digest=checked_digest,
        regenerated_digest=regenerated_digest,
        digest_match=digest_match,
        blockers=tuple(blockers),
        mismatches=tuple(mismatches),
    )


def _check_markdown_artifact(
    root: Path,
    checked_path: str | Path,
    regenerated_text: str,
) -> OperatorEvidenceFinalReviewIndexStressArtifactCheck:
    blockers, mismatches, label, checked_text = _read_checked_text(root, checked_path)
    checked_digest = _text_digest(checked_text) if checked_text is not None else ""
    regenerated_digest = _text_digest(regenerated_text)
    digest_match = None if checked_text is None else checked_digest == regenerated_digest

    if checked_text is not None:
        for guardrail in _REQUIRED_MARKDOWN_GUARDRAILS:
            if guardrail not in checked_text:
                blockers.append(f"checked Markdown missing guardrail: {guardrail}")
        if digest_match is False:
            mismatches.append("checked Markdown text does not match regenerated Markdown text")

    return OperatorEvidenceFinalReviewIndexStressArtifactCheck(
        artifact_id="final_review_index_stress_markdown",
        path=label,
        exists=checked_text is not None and "path blocked" not in " ".join(blockers),
        check_status=_check_status(blockers, mismatches, digest_match),
        checked_digest=checked_digest,
        regenerated_digest=regenerated_digest,
        digest_match=digest_match,
        blockers=tuple(blockers),
        mismatches=tuple(mismatches),
    )


def _read_checked_text(
    root: Path,
    checked_path: str | Path,
) -> tuple[list[str], list[str], str, str | None]:
    blockers: list[str] = []
    mismatches: list[str] = []
    try:
        resolved, label = _resolve_under_project_root(root, checked_path)
    except ValueError as exc:
        return [f"path blocked: {exc}"], mismatches, str(checked_path).replace("\\", "/"), None

    if not resolved.exists():
        return [f"checked artifact is missing: {label}"], mismatches, label, None
    try:
        return blockers, mismatches, label, resolved.read_text(encoding="utf-8")
    except OSError as exc:
        return [f"checked artifact could not be read: {exc}"], mismatches, label, None


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


def _checked_json_blockers(payload: Mapping[str, Any]) -> list[str]:
    blockers: list[str] = []
    missing_fields = sorted(_REQUIRED_CHECKED_JSON_FIELDS - set(payload))
    if missing_fields:
        blockers.append(f"checked JSON missing required fields: {', '.join(missing_fields)}")
    if payload.get("schema_version") != "1":
        blockers.append("checked JSON schema_version must be 1")
    if payload.get("state_change") != "none":
        blockers.append("checked JSON must declare state_change none")
    if payload.get("authority") != OPERATOR_EVIDENCE_FINAL_REVIEW_INDEX_STRESS_MATRIX_AUTHORITY:
        blockers.append("checked JSON authority is not final review index stress matrix authority")
    if "matrix_role" in payload and not isinstance(payload.get("matrix_role"), str):
        blockers.append("checked JSON matrix_role must be a string")
    if "summary" in payload and not isinstance(payload.get("summary"), Mapping):
        blockers.append("checked JSON summary must be an object")
    if "scenarios" in payload and not isinstance(payload.get("scenarios"), list):
        blockers.append("checked JSON scenarios must be a list")
    if "guardrails" in payload and not isinstance(payload.get("guardrails"), Mapping):
        blockers.append("checked JSON guardrails must be an object")
    if "boundary" in payload and not isinstance(payload.get("boundary"), Mapping):
        blockers.append("checked JSON boundary must be an object")
    return blockers


def _check_status(
    blockers: list[str],
    mismatches: list[str],
    digest_match: bool | None,
) -> str:
    if blockers:
        if any("missing" in blocker for blocker in blockers):
            return "missing"
        if any("malformed" in blocker for blocker in blockers):
            return "malformed"
        if any("state_change" in blocker for blocker in blockers):
            return "mutating"
        if any("path blocked" in blocker for blocker in blockers):
            return "blocked_path"
        return "blocked_input"
    if mismatches or digest_match is False:
        return "stale_or_mismatched"
    return "matched"


def _payload_mismatches(expected: Any, actual: Any, prefix: str = "$") -> list[str]:
    mismatches: list[str] = []
    _collect_payload_mismatches(expected, actual, prefix, mismatches)
    return mismatches


def _collect_payload_mismatches(
    expected: Any,
    actual: Any,
    prefix: str,
    mismatches: list[str],
) -> None:
    if len(mismatches) >= _MAX_MISMATCHES:
        return
    if isinstance(expected, Mapping) and isinstance(actual, Mapping):
        expected_keys = set(expected)
        actual_keys = set(actual)
        for key in sorted(expected_keys - actual_keys):
            _append_mismatch(mismatches, f"{prefix}.{key}: missing from checked JSON")
        for key in sorted(actual_keys - expected_keys):
            _append_mismatch(mismatches, f"{prefix}.{key}: unexpected in checked JSON")
        for key in sorted(expected_keys & actual_keys):
            _collect_payload_mismatches(expected[key], actual[key], f"{prefix}.{key}", mismatches)
        return
    if isinstance(expected, list) and isinstance(actual, list):
        if len(expected) != len(actual):
            _append_mismatch(
                mismatches,
                f"{prefix}: list length expected {len(expected)} checked {len(actual)}",
            )
        for index, (expected_item, actual_item) in enumerate(zip(expected, actual)):
            _collect_payload_mismatches(expected_item, actual_item, f"{prefix}[{index}]", mismatches)
        return
    if expected != actual:
        _append_mismatch(
            mismatches,
            f"{prefix}: expected {_short_repr(expected)} checked {_short_repr(actual)}",
        )


def _append_mismatch(mismatches: list[str], message: str) -> None:
    if len(mismatches) < _MAX_MISMATCHES - 1:
        mismatches.append(message)
    elif len(mismatches) == _MAX_MISMATCHES - 1:
        mismatches.append("additional mismatches omitted")


def _short_repr(value: Any) -> str:
    rendered = json.dumps(value, sort_keys=True, ensure_ascii=True)
    return rendered if len(rendered) <= 120 else rendered[:117] + "..."


def _text_digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _is_sha256_hex(value: str) -> bool:
    return len(value) == 64 and all(char in _HEX_DIGITS for char in value)


def _json_bool(value: bool | None) -> str:
    if value is None:
        return "null"
    return str(value).lower()


__all__ = [
    "OPERATOR_EVIDENCE_FINAL_REVIEW_INDEX_STRESS_REPRODUCIBILITY_AUTHORITY",
    "OperatorEvidenceFinalReviewIndexStressArtifactCheck",
    "OperatorEvidenceFinalReviewIndexStressReproducibilityReport",
    "check_operator_evidence_final_review_index_stress_reproducibility",
    "render_operator_evidence_final_review_index_stress_reproducibility_json",
    "render_operator_evidence_final_review_index_stress_reproducibility_markdown",
]
