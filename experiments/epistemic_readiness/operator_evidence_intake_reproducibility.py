from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from .operator_evidence_intake_manifest import (
    OPERATOR_EVIDENCE_INTAKE_REPORT_AUTHORITY,
    build_operator_evidence_intake_report,
    load_operator_evidence_intake_manifest,
)


OPERATOR_EVIDENCE_INTAKE_REPRODUCIBILITY_SCHEMA_VERSION = "1"
OPERATOR_EVIDENCE_INTAKE_REPRODUCIBILITY_AUTHORITY = (
    "non-authoritative; advisory operator evidence intake reproducibility check only"
)

_REQUIRED_CHECKED_REPORT_FIELDS = frozenset(
    {
        "schema_version",
        "state_change",
        "authority",
        "summary",
        "manifest",
        "inputs",
        "blockers",
        "guardrails",
        "boundary",
    }
)
_MAX_MISMATCHES = 16
_HEX_DIGITS = set("0123456789abcdef")


@dataclass(frozen=True)
class OperatorEvidenceIntakeReproducibilityReport:
    manifest_path: str
    checked_report_path: str
    regenerated_report_digest: str = ""
    checked_report_digest: str = ""
    blockers: tuple[str, ...] = ()
    mismatches: tuple[str, ...] = ()
    state_change: str = "none"
    authority: str = OPERATOR_EVIDENCE_INTAKE_REPRODUCIBILITY_AUTHORITY
    check_role: str = "advisory checked-artifact reproducibility evidence only"

    def __post_init__(self) -> None:
        if self.state_change != "none":
            raise ValueError("operator evidence intake reproducibility checks must not change state")
        if self.authority != OPERATOR_EVIDENCE_INTAKE_REPRODUCIBILITY_AUTHORITY:
            raise ValueError(f"unsupported intake reproducibility authority: {self.authority}")
        if not self.manifest_path:
            raise ValueError("operator evidence intake reproducibility requires manifest_path")
        if not self.checked_report_path:
            raise ValueError("operator evidence intake reproducibility requires checked_report_path")
        if self.regenerated_report_digest and not _is_sha256_hex(self.regenerated_report_digest):
            raise ValueError("regenerated_report_digest must be a lowercase sha256 hex digest")
        if self.checked_report_digest and not _is_sha256_hex(self.checked_report_digest):
            raise ValueError("checked_report_digest must be a lowercase sha256 hex digest")
        if (
            not self.blockers
            and not self.mismatches
            and (
                not self.regenerated_report_digest
                or not self.checked_report_digest
                or self.regenerated_report_digest != self.checked_report_digest
            )
        ):
            raise ValueError("clean reproducibility reports require equal regenerated and checked digests")
        if (
            self.regenerated_report_digest
            and self.checked_report_digest
            and self.regenerated_report_digest != self.checked_report_digest
            and not (self.blockers or self.mismatches)
        ):
            raise ValueError("digest divergence must be represented as blockers or mismatches")

    @property
    def reproducibility_status(self) -> str:
        if self.blockers:
            return "blocked_input"
        if self.mismatches:
            return "stale_or_mismatched"
        return "reproducible"

    @property
    def blocked(self) -> bool:
        return bool(self.blockers or self.mismatches)

    @property
    def recommended_human_decision(self) -> str:
        return "review_blockers" if self.blocked else "none"

    @property
    def action_readiness(self) -> str:
        return "blocked" if self.blocked else "advisory_report_allowed"

    @property
    def digest_match(self) -> bool | None:
        if not self.regenerated_report_digest or not self.checked_report_digest:
            return None
        return self.regenerated_report_digest == self.checked_report_digest

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": OPERATOR_EVIDENCE_INTAKE_REPRODUCIBILITY_SCHEMA_VERSION,
            "state_change": self.state_change,
            "authority": self.authority,
            "check_role": self.check_role,
            "summary": {
                "reproducibility_status": self.reproducibility_status,
                "recommended_human_decision": self.recommended_human_decision,
                "action_readiness": self.action_readiness,
                "blocked": self.blocked,
                "blocker_count": len(self.blockers),
                "mismatch_count": len(self.mismatches),
                "digest_match": self.digest_match,
                "regenerated_report_digest": self.regenerated_report_digest,
                "checked_report_digest": self.checked_report_digest,
            },
            "evidence": {
                "manifest_path": self.manifest_path,
                "checked_report_path": self.checked_report_path,
                "comparison_basis": "full deterministic operator evidence intake report payload",
                "compared_report_authority": OPERATOR_EVIDENCE_INTAKE_REPORT_AUTHORITY,
            },
            "blockers": list(self.blockers),
            "mismatches": list(self.mismatches),
            "guardrails": {
                "registered_is_not_true": True,
                "retrieved_is_not_relevant": True,
                "remembered_is_not_trusted": True,
                "silence_is_not_negative_evidence": True,
                "reproducibility_check_is_not_permission": True,
                "reproducibility_check_is_not_memory": True,
                "reproducibility_check_is_not_authority": True,
                "reproducibility_check_is_not_runtime_gate": True,
                "reproducibility_check_is_not_claim_graph": True,
                "digest_equality_is_not_truth": True,
                "report_reproducible_is_not_permission": True,
                "checked_artifact_mismatch_is_review_evidence_only": True,
            },
            "boundary": {
                "may_suggest": [
                    "compare checked-in intake artifacts with regenerated advisory output",
                    "show stale checked reports as blockers",
                    "show missing checked reports as blockers",
                    "show malformed checked reports as blockers",
                    "show mutating checked reports as blockers",
                    "show stale current manifest evidence as blockers",
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
                    "promote or demote authority",
                    "treat reproducibility as permission",
                    "treat digest equality as truth",
                    "hide blockers",
                    "hide mismatches",
                    "hide stale checked reports",
                    "hide stale manifest evidence",
                    "infer negative evidence from silence",
                ],
            },
        }


def check_operator_evidence_intake_reproducibility(
    project_root: str | Path,
    manifest_path: str | Path,
    checked_report_path: str | Path,
) -> OperatorEvidenceIntakeReproducibilityReport:
    root = Path(project_root).resolve()
    blockers: list[str] = []
    mismatches: list[str] = []
    regenerated_digest = ""
    checked_digest = ""

    try:
        resolved_manifest, manifest_label = _resolve_under_project_root(root, manifest_path)
    except ValueError as exc:
        resolved_manifest = None
        manifest_label = str(manifest_path)
        blockers.append(f"manifest path blocked: {exc}")

    try:
        resolved_checked, checked_label = _resolve_under_project_root(root, checked_report_path)
    except ValueError as exc:
        resolved_checked = None
        checked_label = str(checked_report_path)
        blockers.append(f"checked report path blocked: {exc}")

    regenerated_payload: dict[str, Any] | None = None
    if resolved_manifest is not None:
        if not resolved_manifest.exists():
            blockers.append(f"manifest file is missing: {manifest_label}")
        else:
            try:
                manifest = load_operator_evidence_intake_manifest(resolved_manifest)
                regenerated_report = build_operator_evidence_intake_report(manifest)
                regenerated_payload = regenerated_report.to_dict()
                regenerated_digest = _stable_digest(regenerated_payload)
                if regenerated_report.blockers:
                    for blocker in regenerated_report.blockers:
                        blockers.append(f"current manifest intake blocked: {blocker}")
            except (OSError, ValueError) as exc:
                blockers.append(f"manifest could not regenerate intake report: {exc}")

    checked_payload: dict[str, Any] | None = None
    if resolved_checked is not None:
        if not resolved_checked.exists():
            blockers.append(f"checked report file is missing: {checked_label}")
        else:
            try:
                raw_checked = json.loads(resolved_checked.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                blockers.append(f"checked report JSON is malformed: {exc.msg}")
            except OSError as exc:
                blockers.append(f"checked report could not be read: {exc}")
            else:
                if not isinstance(raw_checked, Mapping):
                    blockers.append("checked report JSON root must be an object")
                else:
                    checked_payload = dict(raw_checked)
                    checked_digest = _stable_digest(checked_payload)
                    blockers.extend(_checked_report_blockers(checked_payload))

    if not blockers and regenerated_payload is not None and checked_payload is not None:
        if regenerated_digest != checked_digest:
            mismatches.extend(_payload_mismatches(regenerated_payload, checked_payload))
            if not mismatches:
                mismatches.append("checked report digest does not match regenerated report digest")

    return OperatorEvidenceIntakeReproducibilityReport(
        manifest_path=manifest_label,
        checked_report_path=checked_label,
        regenerated_report_digest=regenerated_digest,
        checked_report_digest=checked_digest,
        blockers=tuple(blockers),
        mismatches=tuple(mismatches),
    )


def render_operator_evidence_intake_reproducibility_json(
    report: OperatorEvidenceIntakeReproducibilityReport,
) -> str:
    return json.dumps(report.to_dict(), indent=2, sort_keys=True) + "\n"


def render_operator_evidence_intake_reproducibility_markdown(
    report: OperatorEvidenceIntakeReproducibilityReport,
) -> str:
    lines = [
        "# Epistemic Readiness Operator Evidence Intake Reproducibility Check",
        "",
        "## Boundary",
        "",
        f"- state_change: {report.state_change}",
        f"- authority: {report.authority}",
        f"- check_role: {report.check_role}",
        "- reproducibility_check_is_not_permission: true",
        "- reproducibility_check_is_not_memory: true",
        "- reproducibility_check_is_not_authority: true",
        "- reproducibility_check_is_not_runtime_gate: true",
        "- reproducibility_check_is_not_claim_graph: true",
        "- digest_equality_is_not_truth: true",
        "- report_reproducible_is_not_permission: true",
        "- checked_artifact_mismatch_is_review_evidence_only: true",
        "- silence_is_not_negative_evidence: true",
        "",
        "## Summary",
        "",
        f"- reproducibility_status: `{report.reproducibility_status}`",
        f"- recommended_human_decision: `{report.recommended_human_decision}`",
        f"- action_readiness: `{report.action_readiness}`",
        f"- blocked: `{str(report.blocked).lower()}`",
        f"- blocker_count: `{len(report.blockers)}`",
        f"- mismatch_count: `{len(report.mismatches)}`",
        f"- digest_match: `{'' if report.digest_match is None else str(report.digest_match).lower()}`",
        f"- regenerated_report_digest: `{report.regenerated_report_digest}`",
        f"- checked_report_digest: `{report.checked_report_digest}`",
        "",
        "## Evidence",
        "",
        f"- manifest_path: `{report.manifest_path}`",
        f"- checked_report_path: `{report.checked_report_path}`",
        "- comparison_basis: `full deterministic operator evidence intake report payload`",
        "",
        "## Blockers",
        "",
    ]
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

    lines.extend(
        [
            "",
            "## Must Not Apply",
            "",
            "- mutate state",
            "- register sources",
            "- refresh checked artifacts automatically",
            "- update replay baseline",
            "- write memory automatically",
            "- act as runtime gate",
            "- create canonical claim graph",
            "- promote or demote authority",
            "- treat reproducibility as permission",
            "- treat digest equality as truth",
            "- hide blockers",
            "- hide mismatches",
            "- hide stale checked reports",
            "- hide stale manifest evidence",
            "- infer negative evidence from silence",
            "",
        ]
    )
    return "\n".join(lines)


def _resolve_under_project_root(root: Path, path: str | Path) -> tuple[Path, str]:
    raw_path = Path(path)
    candidate = raw_path if raw_path.is_absolute() else root / raw_path
    resolved = candidate.resolve()
    try:
        relative = resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"path escapes project root: {path}") from exc
    if any(part.lower() == ".cerebro" for part in relative.parts):
        raise ValueError(f"path points into .cerebro: {path}")
    return resolved, relative.as_posix()


def _checked_report_blockers(payload: Mapping[str, Any]) -> list[str]:
    blockers: list[str] = []
    missing_fields = sorted(_REQUIRED_CHECKED_REPORT_FIELDS - set(payload))
    if missing_fields:
        blockers.append(f"checked report missing required fields: {', '.join(missing_fields)}")
    if payload.get("schema_version") != "1":
        blockers.append("checked report schema_version must be 1")
    if payload.get("state_change") != "none":
        blockers.append("checked report must declare state_change none")
    if payload.get("authority") != OPERATOR_EVIDENCE_INTAKE_REPORT_AUTHORITY:
        blockers.append("checked report authority is not operator evidence intake report authority")
    if "summary" in payload and not isinstance(payload.get("summary"), Mapping):
        blockers.append("checked report summary must be an object")
    if "inputs" in payload and not isinstance(payload.get("inputs"), list):
        blockers.append("checked report inputs must be a list")
    if "blockers" in payload and not isinstance(payload.get("blockers"), list):
        blockers.append("checked report blockers must be a list")
    if "guardrails" in payload and not isinstance(payload.get("guardrails"), Mapping):
        blockers.append("checked report guardrails must be an object")
    if "boundary" in payload and not isinstance(payload.get("boundary"), Mapping):
        blockers.append("checked report boundary must be an object")
    return blockers


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
            _append_mismatch(mismatches, f"{prefix}.{key}: missing from checked report")
        for key in sorted(actual_keys - expected_keys):
            _append_mismatch(mismatches, f"{prefix}.{key}: unexpected in checked report")
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
    if len(rendered) > 120:
        return rendered[:117] + "..."
    return rendered


def _stable_digest(payload: Mapping[str, Any]) -> str:
    rendered = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(rendered.encode("utf-8")).hexdigest()


def _is_sha256_hex(value: str) -> bool:
    return len(value) == 64 and all(char in _HEX_DIGITS for char in value)
