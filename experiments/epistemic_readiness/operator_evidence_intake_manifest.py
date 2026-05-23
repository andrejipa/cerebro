from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import tomllib
from typing import Any, Mapping

from .operator_evidence_bundle import (
    OperatorEvidenceBundleReport,
    build_operator_evidence_bundle,
)


OPERATOR_EVIDENCE_INTAKE_MANIFEST_SCHEMA_VERSION = "1"
OPERATOR_EVIDENCE_INTAKE_MANIFEST_AUTHORITY = (
    "non-authoritative; advisory operator evidence intake manifest only"
)
OPERATOR_EVIDENCE_INTAKE_REPORT_SCHEMA_VERSION = "1"
OPERATOR_EVIDENCE_INTAKE_REPORT_AUTHORITY = (
    "non-authoritative; advisory operator evidence intake report only"
)

_HEX_DIGITS = set("0123456789abcdef")
_REQUIRED_ARTIFACT_IDS = frozenset(
    {"operator_decision_packet", "operator_packet_stress_matrix"}
)


@dataclass(frozen=True)
class OperatorEvidenceIntakeArtifact:
    artifact_id: str
    path: str
    role: str
    expected_digest: str = ""
    state_change: str = "none"

    def __post_init__(self) -> None:
        if not self.artifact_id:
            raise ValueError("intake artifact artifact_id must be non-empty")
        if not self.path:
            raise ValueError("intake artifact path must be non-empty")
        if not self.role:
            raise ValueError("intake artifact role must be non-empty")
        if self.state_change != "none":
            raise ValueError("intake artifact declarations must preserve state_change none")
        if self.expected_digest and not _is_sha256_hex(self.expected_digest):
            raise ValueError("intake artifact expected_digest must be a lowercase sha256 hex digest")

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact_id": self.artifact_id,
            "path": self.path,
            "role": self.role,
            "expected_digest": self.expected_digest,
            "state_change": self.state_change,
        }


@dataclass(frozen=True)
class OperatorEvidenceIntakeManifest:
    root: str
    generated_report_json: str
    generated_report_markdown: str
    artifacts: tuple[OperatorEvidenceIntakeArtifact, ...]
    schema_version: str = OPERATOR_EVIDENCE_INTAKE_MANIFEST_SCHEMA_VERSION
    state_change: str = "none"
    authority: str = OPERATOR_EVIDENCE_INTAKE_MANIFEST_AUTHORITY

    def __post_init__(self) -> None:
        if self.schema_version != OPERATOR_EVIDENCE_INTAKE_MANIFEST_SCHEMA_VERSION:
            raise ValueError(f"unsupported intake manifest schema_version: {self.schema_version}")
        if self.state_change != "none":
            raise ValueError("operator evidence intake manifests must declare state_change = none")
        if self.authority != OPERATOR_EVIDENCE_INTAKE_MANIFEST_AUTHORITY:
            raise ValueError(f"unsupported intake manifest authority: {self.authority}")
        if not self.root:
            raise ValueError("operator evidence intake manifest root is required")
        if not self.generated_report_json:
            raise ValueError("generated_report_json is required")
        if not self.generated_report_markdown:
            raise ValueError("generated_report_markdown is required")
        if not self.artifacts:
            raise ValueError("operator evidence intake manifest must declare artifacts")
        artifact_ids = tuple(artifact.artifact_id for artifact in self.artifacts)
        if len(set(artifact_ids)) != len(artifact_ids):
            raise ValueError("operator evidence intake artifact ids must be unique")
        for artifact in self.artifacts:
            if artifact.state_change != "none":
                raise ValueError("operator evidence intake artifacts must preserve state_change none")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "state_change": self.state_change,
            "authority": self.authority,
            "root": self.root,
            "generated_report_json": self.generated_report_json,
            "generated_report_markdown": self.generated_report_markdown,
            "artifacts": [artifact.to_dict() for artifact in self.artifacts],
        }


@dataclass(frozen=True)
class OperatorEvidenceIntakeInput:
    artifact_id: str
    path: str
    role: str
    digest: str
    expected_digest: str = ""
    state_change: str = "none"

    def __post_init__(self) -> None:
        if not self.artifact_id:
            raise ValueError("intake input artifact_id must be non-empty")
        if not self.path:
            raise ValueError("intake input path must be non-empty")
        if not self.role:
            raise ValueError("intake input role must be non-empty")
        if self.state_change != "none":
            raise ValueError("intake inputs must preserve state_change none")
        if not _is_sha256_hex(self.digest):
            raise ValueError("intake input digest must be a lowercase sha256 hex digest")
        if self.expected_digest and not _is_sha256_hex(self.expected_digest):
            raise ValueError("intake input expected_digest must be a lowercase sha256 hex digest")

    @property
    def digest_match(self) -> bool | None:
        if not self.expected_digest:
            return None
        return self.digest == self.expected_digest

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact_id": self.artifact_id,
            "path": self.path,
            "role": self.role,
            "digest": self.digest,
            "expected_digest": self.expected_digest,
            "digest_match": self.digest_match,
            "state_change": self.state_change,
        }


@dataclass(frozen=True)
class OperatorEvidenceIntakeReport:
    manifest_root: str
    inputs: tuple[OperatorEvidenceIntakeInput, ...]
    blockers: tuple[str, ...]
    bundle: OperatorEvidenceBundleReport | None
    state_change: str = "none"
    authority: str = OPERATOR_EVIDENCE_INTAKE_REPORT_AUTHORITY
    report_role: str = "operator-facing advisory evidence intake report only"

    def __post_init__(self) -> None:
        if self.state_change != "none":
            raise ValueError("operator evidence intake report must not change state")
        if self.authority != OPERATOR_EVIDENCE_INTAKE_REPORT_AUTHORITY:
            raise ValueError(f"unsupported intake report authority: {self.authority}")
        if not self.manifest_root:
            raise ValueError("operator evidence intake report manifest_root is required")
        artifact_ids = tuple(item.artifact_id for item in self.inputs)
        if len(set(artifact_ids)) != len(artifact_ids):
            raise ValueError("operator evidence intake report input artifact ids must be unique")
        if self.blockers and self.bundle is not None:
            raise ValueError("blocked intake reports must not include a bundle")
        if not self.blockers and self.bundle is None:
            raise ValueError("clean intake reports must include a bundle")
        for item in self.inputs:
            if item.state_change != "none":
                raise ValueError("operator evidence intake inputs must preserve state_change none")

    @property
    def blocked(self) -> bool:
        return bool(self.blockers)

    @property
    def input_count(self) -> int:
        return len(self.inputs)

    @property
    def source_artifact_count(self) -> int:
        if self.bundle is not None:
            return self.bundle.source_artifact_count
        return max(0, len([item for item in self.inputs if item.artifact_id not in _REQUIRED_ARTIFACT_IDS]))

    @property
    def recommended_human_decision(self) -> str:
        return "review_blockers" if self.blocked else "none"

    @property
    def action_readiness(self) -> str:
        return "blocked" if self.blocked else "advisory_report_allowed"

    def to_dict(self) -> dict[str, Any]:
        bundle_summary: dict[str, Any] | None = None
        if self.bundle is not None:
            bundle_payload = self.bundle.to_dict()
            bundle_summary = dict(bundle_payload["summary"])
        return {
            "schema_version": OPERATOR_EVIDENCE_INTAKE_REPORT_SCHEMA_VERSION,
            "state_change": self.state_change,
            "authority": self.authority,
            "report_role": self.report_role,
            "summary": {
                "recommended_human_decision": self.recommended_human_decision,
                "action_readiness": self.action_readiness,
                "blocked": self.blocked,
                "blocker_count": len(self.blockers),
                "input_count": self.input_count,
                "source_artifact_count": self.source_artifact_count,
                "bundle_summary": bundle_summary,
            },
            "manifest": {
                "root": self.manifest_root,
                "required_artifacts": sorted(_REQUIRED_ARTIFACT_IDS),
            },
            "inputs": [item.to_dict() for item in self.inputs],
            "blockers": list(self.blockers),
            "guardrails": {
                "registered_is_not_true": True,
                "retrieved_is_not_relevant": True,
                "remembered_is_not_trusted": True,
                "silence_is_not_negative_evidence": True,
                "intake_report_is_not_permission": True,
                "intake_report_is_not_memory": True,
                "intake_report_is_not_authority": True,
                "intake_report_is_not_runtime_gate": True,
                "intake_report_is_not_claim_graph": True,
                "digest_equality_is_not_truth": True,
                "manifest_presence_is_not_permission": True,
                "bundle_output_is_not_permission": True,
            },
            "boundary": {
                "may_suggest": [
                    "rebuild an advisory operator evidence bundle from declared artifacts",
                    "show stale or digest-mismatched advisory artifacts",
                    "show missing or mutating advisory artifacts",
                    "show the declared evidence set used for operator handoff",
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
                    "treat digest equality as truth",
                    "hide blockers",
                    "hide missing artifacts",
                    "hide stale artifacts",
                    "hide mutating artifacts",
                    "infer negative evidence from silence",
                ],
            },
        }


def load_operator_evidence_intake_manifest(path: str | Path) -> OperatorEvidenceIntakeManifest:
    manifest_path = Path(path)
    data = tomllib.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("operator evidence intake manifest root must be a table")

    raw_artifacts = data.get("artifacts")
    if not isinstance(raw_artifacts, list):
        raise ValueError("operator evidence intake manifest must include [[artifacts]] entries")

    artifacts: list[OperatorEvidenceIntakeArtifact] = []
    for raw_artifact in raw_artifacts:
        if not isinstance(raw_artifact, dict):
            raise ValueError("operator evidence intake artifacts must be tables")
        artifacts.append(
            OperatorEvidenceIntakeArtifact(
                artifact_id=_require_str(raw_artifact, "artifact_id"),
                path=_require_str(raw_artifact, "path"),
                role=_require_str(raw_artifact, "role"),
                expected_digest=_optional_str(raw_artifact, "expected_digest"),
                state_change=_optional_str(raw_artifact, "state_change", default="none"),
            )
        )

    raw_root = _require_str(data, "root")
    root = _resolve_manifest_root(manifest_path.parent, raw_root)
    return OperatorEvidenceIntakeManifest(
        schema_version=_require_str(data, "schema_version"),
        state_change=_require_str(data, "state_change"),
        authority=_require_str(data, "authority"),
        root=str(root),
        generated_report_json=_require_str(data, "generated_report_json"),
        generated_report_markdown=_require_str(data, "generated_report_markdown"),
        artifacts=tuple(artifacts),
    )


def build_operator_evidence_intake_report(
    manifest: OperatorEvidenceIntakeManifest,
) -> OperatorEvidenceIntakeReport:
    blockers: list[str] = []
    inputs: list[OperatorEvidenceIntakeInput] = []
    payloads: dict[str, dict[str, Any]] = {}
    root = Path(manifest.root).resolve()

    declared_ids = {artifact.artifact_id for artifact in manifest.artifacts}
    for required_id in sorted(_REQUIRED_ARTIFACT_IDS - declared_ids):
        blockers.append(f"missing required artifact declaration: {required_id}")

    for artifact in manifest.artifacts:
        try:
            artifact_path = _resolve_artifact_path(root, artifact.path)
        except ValueError as exc:
            blockers.append(f"{artifact.artifact_id}: {exc}")
            continue

        if artifact_path.suffix.lower() != ".json":
            blockers.append(f"{artifact.artifact_id}: artifact path must point to a .json file")
            continue
        if not artifact_path.exists():
            blockers.append(f"{artifact.artifact_id}: artifact file is missing: {artifact.path}")
            continue

        try:
            payload = json.loads(artifact_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            blockers.append(f"{artifact.artifact_id}: artifact JSON is malformed: {exc.msg}")
            continue

        if not isinstance(payload, Mapping):
            blockers.append(f"{artifact.artifact_id}: artifact JSON root must be an object")
            continue
        payload_dict = dict(payload)
        if payload_dict.get("state_change") != "none":
            blockers.append(f"{artifact.artifact_id}: artifact must declare state_change none")
            continue

        digest = _stable_digest(payload_dict)
        inputs.append(
            OperatorEvidenceIntakeInput(
                artifact_id=artifact.artifact_id,
                path=artifact.path,
                role=artifact.role,
                digest=digest,
                expected_digest=artifact.expected_digest,
            )
        )
        if artifact.expected_digest and digest != artifact.expected_digest:
            blockers.append(f"{artifact.artifact_id}: digest mismatch")
            continue
        payloads[artifact.artifact_id] = payload_dict

    if blockers:
        return OperatorEvidenceIntakeReport(
            manifest_root=str(root),
            inputs=tuple(inputs),
            blockers=tuple(blockers),
            bundle=None,
        )

    try:
        bundle = build_operator_evidence_bundle(
            payloads["operator_decision_packet"],
            payloads["operator_packet_stress_matrix"],
            {
                artifact_id: payload
                for artifact_id, payload in payloads.items()
                if artifact_id not in _REQUIRED_ARTIFACT_IDS
            },
        )
    except (KeyError, ValueError) as exc:
        return OperatorEvidenceIntakeReport(
            manifest_root=str(root),
            inputs=tuple(inputs),
            blockers=(f"bundle construction failed: {exc}",),
            bundle=None,
        )

    return OperatorEvidenceIntakeReport(
        manifest_root=str(root),
        inputs=tuple(inputs),
        blockers=(),
        bundle=bundle,
    )


def build_operator_evidence_intake_report_from_manifest(
    path: str | Path,
) -> OperatorEvidenceIntakeReport:
    return build_operator_evidence_intake_report(load_operator_evidence_intake_manifest(path))


def render_operator_evidence_intake_report_json(report: OperatorEvidenceIntakeReport) -> str:
    return json.dumps(report.to_dict(), indent=2, sort_keys=True) + "\n"


def render_operator_evidence_intake_report_markdown(report: OperatorEvidenceIntakeReport) -> str:
    lines = [
        "# Epistemic Readiness Operator Evidence Intake Report",
        "",
        "## Boundary",
        "",
        f"- state_change: {report.state_change}",
        f"- authority: {report.authority}",
        f"- report_role: {report.report_role}",
        "- intake_report_is_not_permission: true",
        "- intake_report_is_not_memory: true",
        "- intake_report_is_not_authority: true",
        "- intake_report_is_not_runtime_gate: true",
        "- intake_report_is_not_claim_graph: true",
        "- digest_equality_is_not_truth: true",
        "- manifest_presence_is_not_permission: true",
        "- silence_is_not_negative_evidence: true",
        "",
        "## Summary",
        "",
        f"- recommended_human_decision: `{report.recommended_human_decision}`",
        f"- action_readiness: `{report.action_readiness}`",
        f"- blocked: `{str(report.blocked).lower()}`",
        f"- blocker_count: `{len(report.blockers)}`",
        f"- input_count: `{report.input_count}`",
        f"- source_artifact_count: `{report.source_artifact_count}`",
        "",
        "## Inputs",
        "",
        "| Artifact | Role | Digest | Expected Digest | Match | Path |",
        "|---|---|---|---|---|---|",
    ]
    for item in report.inputs:
        expected = item.expected_digest or ""
        match = "" if item.digest_match is None else str(item.digest_match).lower()
        lines.append(
            f"| `{item.artifact_id}` | {item.role} | `{item.digest}` | `{expected}` | "
            f"`{match}` | `{item.path}` |"
        )

    lines.extend(["", "## Blockers", ""])
    if report.blockers:
        for blocker in report.blockers:
            lines.append(f"- {blocker}")
    else:
        lines.append("- none")

    if report.bundle is not None:
        lines.extend(
            [
                "",
                "## Bundle Summary",
                "",
                f"- packet_recommended_human_decision: `{report.bundle.packet_recommended_human_decision}`",
                f"- packet_action_readiness: `{report.bundle.packet_action_readiness}`",
                f"- packet_conformance_passed: `{str(report.bundle.packet_conformance_passed).lower()}`",
                f"- stress_scenario_count: `{report.bundle.stress_scenario_count}`",
                f"- stress_pass_count: `{report.bundle.stress_pass_count}`",
                f"- stress_fail_count: `{report.bundle.stress_fail_count}`",
                f"- stress_all_scenarios_passed: `{str(report.bundle.stress_all_scenarios_passed).lower()}`",
                f"- boundary_error_count: `{report.bundle.boundary_error_count}`",
            ]
        )

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
            "- treat digest equality as truth",
            "- hide blockers",
            "- hide missing artifacts",
            "- hide stale artifacts",
            "- hide mutating artifacts",
            "- infer negative evidence from silence",
            "",
        ]
    )
    return "\n".join(lines)


def _resolve_manifest_root(base_path: Path, root: str) -> Path:
    root_path = (base_path / root).resolve()
    if any(part.lower() == ".cerebro" for part in root_path.parts):
        raise ValueError("operator evidence intake manifest root must not point into .cerebro")
    return root_path


def _resolve_artifact_path(root: Path, relative_path: str) -> Path:
    candidate = (root / relative_path).resolve()
    try:
        relative = candidate.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"artifact path escapes root: {relative_path}") from exc
    if any(part.lower() == ".cerebro" for part in relative.parts):
        raise ValueError(f"artifact path points into .cerebro: {relative_path}")
    return candidate


def _stable_digest(payload: Mapping[str, Any]) -> str:
    rendered = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(rendered.encode("utf-8")).hexdigest()


def _is_sha256_hex(value: str) -> bool:
    return len(value) == 64 and all(char in _HEX_DIGITS for char in value)


def _require_str(mapping: Mapping[str, Any], key: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"{key} is required")
    return value


def _optional_str(
    mapping: Mapping[str, Any],
    key: str,
    *,
    default: str = "",
) -> str:
    value = mapping.get(key, default)
    if not isinstance(value, str):
        raise ValueError(f"{key} must be a string")
    return value
