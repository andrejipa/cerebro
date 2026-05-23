from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

try:
    import tomllib  # type: ignore[import-not-found]
except ModuleNotFoundError:  # pragma: no cover - exercised only on Python 3.10.
    tomllib = None  # type: ignore[assignment]


OPERATOR_EVIDENCE_PROVENANCE_INDEX_SCHEMA_VERSION = "1"
OPERATOR_EVIDENCE_PROVENANCE_INDEX_AUTHORITY = (
    "non-authoritative; advisory operator evidence provenance index only"
)

_TEXT_PLACEHOLDER = "not_declared_text_digest_only"
_SUMMARY_KEYS = (
    "action_readiness",
    "recommended_human_decision",
    "reproducibility_status",
    "blocked",
    "blocker_count",
    "mismatch_count",
    "digest_match",
    "scenario_count",
    "pass_count",
    "fail_count",
    "all_scenarios_passed",
    "input_count",
    "source_artifact_count",
    "boundary_error_count",
    "authority_impact",
    "runtime_impact",
)


@dataclass(frozen=True)
class OperatorEvidenceProvenanceArtifactSpec:
    artifact_id: str
    path: str
    artifact_format: str
    upstream_artifacts: tuple[str, ...] = ()
    role: str = "operator-facing advisory evidence artifact"

    def __post_init__(self) -> None:
        if not self.artifact_id:
            raise ValueError("provenance artifact spec requires artifact_id")
        if not self.path:
            raise ValueError("provenance artifact spec requires path")
        if self.artifact_format not in {"json", "toml", "markdown"}:
            raise ValueError(f"unsupported provenance artifact format: {self.artifact_format}")


@dataclass(frozen=True)
class OperatorEvidenceProvenanceArtifact:
    artifact_id: str
    path: str
    artifact_format: str
    role: str
    upstream_artifacts: tuple[str, ...]
    exists: bool
    digest: str = ""
    parse_status: str = "missing"
    schema_version: str = ""
    authority: str = ""
    state_change: str = ""
    summary: str = ""
    blockers: tuple[str, ...] = ()

    @property
    def blocked(self) -> bool:
        return bool(self.blockers)

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact_id": self.artifact_id,
            "path": self.path,
            "artifact_format": self.artifact_format,
            "role": self.role,
            "upstream_artifacts": list(self.upstream_artifacts),
            "exists": self.exists,
            "digest": self.digest,
            "parse_status": self.parse_status,
            "schema_version": self.schema_version,
            "authority": self.authority,
            "state_change": self.state_change,
            "summary": self.summary,
            "blocked": self.blocked,
            "blockers": list(self.blockers),
        }


@dataclass(frozen=True)
class OperatorEvidenceProvenanceIndexReport:
    artifacts: tuple[OperatorEvidenceProvenanceArtifact, ...]
    blockers: tuple[str, ...] = ()
    state_change: str = "none"
    authority: str = OPERATOR_EVIDENCE_PROVENANCE_INDEX_AUTHORITY
    index_role: str = "advisory evidence provenance index, not a canonical graph"

    def __post_init__(self) -> None:
        if self.state_change != "none":
            raise ValueError("operator evidence provenance index must not change state")
        if self.authority != OPERATOR_EVIDENCE_PROVENANCE_INDEX_AUTHORITY:
            raise ValueError(f"unsupported provenance index authority: {self.authority}")

    @property
    def artifact_count(self) -> int:
        return len(self.artifacts)

    @property
    def present_count(self) -> int:
        return sum(1 for artifact in self.artifacts if artifact.exists)

    @property
    def dependency_edge_count(self) -> int:
        return sum(len(artifact.upstream_artifacts) for artifact in self.artifacts)

    @property
    def artifact_blocker_count(self) -> int:
        return sum(len(artifact.blockers) for artifact in self.artifacts)

    @property
    def blocked(self) -> bool:
        return bool(self.blockers or self.artifact_blocker_count)

    @property
    def recommended_human_decision(self) -> str:
        return "review_blockers" if self.blocked else "none"

    @property
    def action_readiness(self) -> str:
        return "blocked" if self.blocked else "advisory_report_allowed"

    @property
    def digest_manifest(self) -> str:
        manifest = [
            {
                "artifact_id": artifact.artifact_id,
                "path": artifact.path,
                "digest": artifact.digest,
            }
            for artifact in self.artifacts
        ]
        return _stable_digest(manifest)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": OPERATOR_EVIDENCE_PROVENANCE_INDEX_SCHEMA_VERSION,
            "state_change": self.state_change,
            "authority": self.authority,
            "index_role": self.index_role,
            "summary": {
                "artifact_count": self.artifact_count,
                "present_count": self.present_count,
                "dependency_edge_count": self.dependency_edge_count,
                "artifact_blocker_count": self.artifact_blocker_count,
                "blocker_count": len(self.blockers) + self.artifact_blocker_count,
                "blocked": self.blocked,
                "recommended_human_decision": self.recommended_human_decision,
                "action_readiness": self.action_readiness,
                "digest_manifest": self.digest_manifest,
            },
            "artifacts": [artifact.to_dict() for artifact in self.artifacts],
            "blockers": list(self.blockers),
            "guardrails": {
                "registered_is_not_true": True,
                "retrieved_is_not_relevant": True,
                "remembered_is_not_trusted": True,
                "silence_is_not_negative_evidence": True,
                "provenance_index_is_not_permission": True,
                "provenance_index_is_not_memory": True,
                "provenance_index_is_not_authority": True,
                "provenance_index_is_not_runtime_gate": True,
                "provenance_index_is_not_claim_graph": True,
                "provenance_index_is_not_source_registry": True,
                "digest_is_not_truth": True,
                "dependency_map_is_not_canonical_graph": True,
            },
            "boundary": {
                "may_suggest": [
                    "show checked-in advisory evidence artifacts",
                    "show evidence artifact digests",
                    "show declared upstream advisory dependencies",
                    "surface missing artifacts as blockers",
                    "surface malformed artifacts as blockers",
                    "surface mutating artifacts as blockers",
                    "surface dependency gaps as blockers",
                    "make operator review cheaper",
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
                    "treat provenance as permission",
                    "treat digests as truth",
                    "hide blockers",
                    "infer negative evidence from silence",
                ],
            },
        }


DEFAULT_OPERATOR_EVIDENCE_PROVENANCE_ARTIFACTS = (
    OperatorEvidenceProvenanceArtifactSpec(
        "readiness_manifest",
        "docs/operations/CEREBRO_SELF_EPISTEMIC_READINESS_MANIFEST.toml",
        "toml",
    ),
    OperatorEvidenceProvenanceArtifactSpec(
        "readiness_report",
        "docs/operations/CEREBRO_SELF_EPISTEMIC_READINESS_REPORT.md",
        "markdown",
        ("readiness_manifest",),
    ),
    OperatorEvidenceProvenanceArtifactSpec(
        "readiness_trace",
        "docs/operations/CEREBRO_SELF_EPISTEMIC_READINESS_TRACE.json",
        "json",
        ("readiness_manifest",),
    ),
    OperatorEvidenceProvenanceArtifactSpec(
        "readiness_trace_baseline",
        "docs/operations/CEREBRO_SELF_EPISTEMIC_READINESS_TRACE_BASELINE.json",
        "json",
        ("readiness_trace",),
    ),
    OperatorEvidenceProvenanceArtifactSpec(
        "readiness_trace_diff",
        "docs/operations/CEREBRO_SELF_EPISTEMIC_READINESS_TRACE_DIFF.json",
        "json",
        ("readiness_trace", "readiness_trace_baseline"),
    ),
    OperatorEvidenceProvenanceArtifactSpec(
        "protocol_self_audit",
        "docs/operations/CEREBRO_SELF_EPISTEMIC_PROTOCOL_SELF_AUDIT.json",
        "json",
        ("readiness_trace_diff",),
    ),
    OperatorEvidenceProvenanceArtifactSpec(
        "baseline_lifecycle",
        "docs/operations/CEREBRO_SELF_EPISTEMIC_BASELINE_LIFECYCLE.json",
        "json",
        ("readiness_trace", "readiness_trace_baseline", "readiness_trace_diff", "protocol_self_audit"),
    ),
    OperatorEvidenceProvenanceArtifactSpec(
        "drift_policy",
        "docs/operations/CEREBRO_SELF_EPISTEMIC_DRIFT_POLICY.json",
        "json",
        ("readiness_trace_diff", "protocol_self_audit", "baseline_lifecycle"),
    ),
    OperatorEvidenceProvenanceArtifactSpec(
        "metacognitive_handoff",
        "docs/operations/CEREBRO_SELF_EPISTEMIC_METACOGNITIVE_HANDOFF.json",
        "json",
        ("readiness_trace", "baseline_lifecycle", "protocol_self_audit", "drift_policy"),
    ),
    OperatorEvidenceProvenanceArtifactSpec(
        "handoff_stress_matrix",
        "docs/operations/CEREBRO_SELF_EPISTEMIC_HANDOFF_STRESS_MATRIX.json",
        "json",
        ("metacognitive_handoff",),
    ),
    OperatorEvidenceProvenanceArtifactSpec(
        "human_decision_taxonomy",
        "docs/operations/CEREBRO_SELF_EPISTEMIC_HUMAN_DECISION_TAXONOMY.json",
        "json",
        ("handoff_stress_matrix",),
    ),
    OperatorEvidenceProvenanceArtifactSpec(
        "decision_taxonomy_conformance",
        "docs/operations/CEREBRO_SELF_EPISTEMIC_DECISION_TAXONOMY_CONFORMANCE.json",
        "json",
        ("human_decision_taxonomy", "handoff_stress_matrix"),
    ),
    OperatorEvidenceProvenanceArtifactSpec(
        "operator_decision_packet",
        "docs/operations/CEREBRO_SELF_EPISTEMIC_OPERATOR_DECISION_PACKET.json",
        "json",
        ("metacognitive_handoff", "decision_taxonomy_conformance", "drift_policy", "baseline_lifecycle"),
    ),
    OperatorEvidenceProvenanceArtifactSpec(
        "operator_packet_stress_matrix",
        "docs/operations/CEREBRO_SELF_EPISTEMIC_OPERATOR_PACKET_STRESS_MATRIX.json",
        "json",
        ("operator_decision_packet",),
    ),
    OperatorEvidenceProvenanceArtifactSpec(
        "operator_evidence_bundle",
        "docs/operations/CEREBRO_SELF_EPISTEMIC_OPERATOR_EVIDENCE_BUNDLE.json",
        "json",
        (
            "operator_decision_packet",
            "operator_packet_stress_matrix",
            "baseline_lifecycle",
            "decision_taxonomy_conformance",
            "drift_policy",
            "metacognitive_handoff",
        ),
    ),
    OperatorEvidenceProvenanceArtifactSpec(
        "operator_evidence_bundle_stress_matrix",
        "docs/operations/CEREBRO_SELF_EPISTEMIC_OPERATOR_EVIDENCE_BUNDLE_STRESS_MATRIX.json",
        "json",
        ("operator_evidence_bundle",),
    ),
    OperatorEvidenceProvenanceArtifactSpec(
        "operator_evidence_intake_manifest",
        "docs/operations/CEREBRO_SELF_EPISTEMIC_OPERATOR_EVIDENCE_INTAKE_MANIFEST.toml",
        "toml",
        ("operator_evidence_bundle",),
    ),
    OperatorEvidenceProvenanceArtifactSpec(
        "operator_evidence_intake_report",
        "docs/operations/CEREBRO_SELF_EPISTEMIC_OPERATOR_EVIDENCE_INTAKE_REPORT.json",
        "json",
        ("operator_evidence_intake_manifest", "operator_evidence_bundle"),
    ),
    OperatorEvidenceProvenanceArtifactSpec(
        "operator_evidence_intake_stress_matrix",
        "docs/operations/CEREBRO_SELF_EPISTEMIC_OPERATOR_EVIDENCE_INTAKE_STRESS_MATRIX.json",
        "json",
        ("operator_evidence_intake_report",),
    ),
    OperatorEvidenceProvenanceArtifactSpec(
        "operator_evidence_intake_reproducibility_check",
        "docs/operations/CEREBRO_SELF_EPISTEMIC_OPERATOR_EVIDENCE_INTAKE_REPRODUCIBILITY_CHECK.json",
        "json",
        ("operator_evidence_intake_manifest", "operator_evidence_intake_report"),
    ),
)


def build_operator_evidence_provenance_index(
    project_root: str | Path,
    artifacts: tuple[OperatorEvidenceProvenanceArtifactSpec, ...] = DEFAULT_OPERATOR_EVIDENCE_PROVENANCE_ARTIFACTS,
) -> OperatorEvidenceProvenanceIndexReport:
    root = Path(project_root).resolve()
    report_blockers = list(_spec_blockers(artifacts))
    indexed: list[OperatorEvidenceProvenanceArtifact] = []

    for spec in artifacts:
        indexed.append(_index_artifact(root, spec))

    return OperatorEvidenceProvenanceIndexReport(
        artifacts=tuple(indexed),
        blockers=tuple(report_blockers),
    )


def render_operator_evidence_provenance_index_json(
    report: OperatorEvidenceProvenanceIndexReport,
) -> str:
    return json.dumps(report.to_dict(), indent=2, sort_keys=True) + "\n"


def render_operator_evidence_provenance_index_markdown(
    report: OperatorEvidenceProvenanceIndexReport,
) -> str:
    lines = [
        "# Epistemic Readiness Operator Evidence Provenance Index",
        "",
        "This is advisory operator evidence only. It is not a runtime gate, not memory, not a canonical graph, and not permission to act.",
        "",
        "## Summary",
        "",
        f"- authority: {report.authority}",
        f"- state_change: {report.state_change}",
        f"- action_readiness: {report.action_readiness}",
        f"- recommended_human_decision: {report.recommended_human_decision}",
        f"- artifact_count: {report.artifact_count}",
        f"- present_count: {report.present_count}",
        f"- dependency_edge_count: {report.dependency_edge_count}",
        f"- blocker_count: {len(report.blockers) + report.artifact_blocker_count}",
        f"- digest_manifest: {report.digest_manifest}",
        "",
        "## Artifacts",
        "",
        "| Artifact | Format | Digest | State Change | Authority | Parse | Dependencies | Summary |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for artifact in report.artifacts:
        dependencies = ", ".join(artifact.upstream_artifacts) or "none"
        digest = artifact.digest or "missing"
        state_change = artifact.state_change or "missing"
        authority = artifact.authority or "missing"
        summary = artifact.summary or "none"
        lines.append(
            "| "
            f"{_md(artifact.artifact_id)} | "
            f"{_md(artifact.artifact_format)} | "
            f"{_md(digest)} | "
            f"{_md(state_change)} | "
            f"{_md(authority)} | "
            f"{_md(artifact.parse_status)} | "
            f"{_md(dependencies)} | "
            f"{_md(summary)} |"
        )

    lines.extend(["", "## Blockers", ""])
    if report.blockers:
        for blocker in report.blockers:
            lines.append(f"- {blocker}")
    artifact_blockers = [
        (artifact.artifact_id, blocker)
        for artifact in report.artifacts
        for blocker in artifact.blockers
    ]
    if artifact_blockers:
        for artifact_id, blocker in artifact_blockers:
            lines.append(f"- {artifact_id}: {blocker}")
    if not report.blockers and not artifact_blockers:
        lines.append("- none")

    lines.extend(
        [
            "",
            "## Guardrails",
            "",
            "- provenance_index_is_not_permission: true",
            "- provenance_index_is_not_memory: true",
            "- provenance_index_is_not_authority: true",
            "- provenance_index_is_not_runtime_gate: true",
            "- provenance_index_is_not_claim_graph: true",
            "- provenance_index_is_not_source_registry: true",
            "- dependency_map_is_not_canonical_graph: true",
            "- digest_is_not_truth: true",
            "- silence_is_not_negative_evidence: true",
            "",
            "## Must Not Apply",
            "",
        ]
    )
    for item in report.to_dict()["boundary"]["must_not_apply"]:
        lines.append(f"- {item}")
    return "\n".join(lines) + "\n"


def _index_artifact(
    root: Path,
    spec: OperatorEvidenceProvenanceArtifactSpec,
) -> OperatorEvidenceProvenanceArtifact:
    blockers: list[str] = []
    try:
        resolved, relative_label = _resolve_under_project_root(root, spec.path)
    except ValueError as exc:
        return OperatorEvidenceProvenanceArtifact(
            artifact_id=spec.artifact_id,
            path=spec.path,
            artifact_format=spec.artifact_format,
            role=spec.role,
            upstream_artifacts=spec.upstream_artifacts,
            exists=False,
            parse_status="path_blocked",
            blockers=(f"path blocked: {exc}",),
        )

    if not resolved.exists():
        return OperatorEvidenceProvenanceArtifact(
            artifact_id=spec.artifact_id,
            path=relative_label,
            artifact_format=spec.artifact_format,
            role=spec.role,
            upstream_artifacts=spec.upstream_artifacts,
            exists=False,
            parse_status="missing",
            blockers=(f"artifact file is missing: {relative_label}",),
        )

    try:
        raw_bytes = resolved.read_bytes()
    except OSError as exc:
        return OperatorEvidenceProvenanceArtifact(
            artifact_id=spec.artifact_id,
            path=relative_label,
            artifact_format=spec.artifact_format,
            role=spec.role,
            upstream_artifacts=spec.upstream_artifacts,
            exists=True,
            parse_status="read_error",
            blockers=(f"artifact could not be read: {exc}",),
        )

    digest = hashlib.sha256(raw_bytes).hexdigest()
    if spec.artifact_format == "markdown":
        return OperatorEvidenceProvenanceArtifact(
            artifact_id=spec.artifact_id,
            path=relative_label,
            artifact_format=spec.artifact_format,
            role=spec.role,
            upstream_artifacts=spec.upstream_artifacts,
            exists=True,
            digest=digest,
            parse_status="text_digest_only",
            schema_version=_TEXT_PLACEHOLDER,
            authority=_TEXT_PLACEHOLDER,
            state_change=_TEXT_PLACEHOLDER,
            summary="text digest only; no truth inferred",
        )

    try:
        text = raw_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        blockers.append(f"artifact is not valid UTF-8: {exc}")
        return OperatorEvidenceProvenanceArtifact(
            artifact_id=spec.artifact_id,
            path=relative_label,
            artifact_format=spec.artifact_format,
            role=spec.role,
            upstream_artifacts=spec.upstream_artifacts,
            exists=True,
            digest=digest,
            parse_status="decode_error",
            blockers=tuple(blockers),
        )

    if spec.artifact_format == "json":
        return _index_json_artifact(spec, relative_label, digest, text)
    if spec.artifact_format == "toml":
        return _index_toml_artifact(spec, relative_label, digest, raw_bytes, text)
    raise ValueError(f"unsupported provenance artifact format: {spec.artifact_format}")


def _index_json_artifact(
    spec: OperatorEvidenceProvenanceArtifactSpec,
    relative_label: str,
    digest: str,
    text: str,
) -> OperatorEvidenceProvenanceArtifact:
    blockers: list[str] = []
    payload: Mapping[str, Any] | None = None
    try:
        raw_payload = json.loads(text)
    except json.JSONDecodeError as exc:
        blockers.append(f"artifact JSON is malformed: {exc.msg}")
        parse_status = "malformed_json"
    else:
        if not isinstance(raw_payload, Mapping):
            blockers.append("artifact JSON root must be an object")
            parse_status = "invalid_json_root"
        else:
            payload = raw_payload
            parse_status = "parsed_json"

    schema_version = ""
    authority = ""
    state_change = ""
    summary = ""
    if payload is not None:
        schema_version = _optional_string(payload.get("schema_version"))
        authority = _optional_string(payload.get("authority"))
        state_change = _optional_string(payload.get("state_change"))
        summary = _summary_from_payload(payload)
        blockers.extend(_payload_blockers(payload))

    return OperatorEvidenceProvenanceArtifact(
        artifact_id=spec.artifact_id,
        path=relative_label,
        artifact_format=spec.artifact_format,
        role=spec.role,
        upstream_artifacts=spec.upstream_artifacts,
        exists=True,
        digest=digest,
        parse_status=parse_status,
        schema_version=schema_version,
        authority=authority,
        state_change=state_change,
        summary=summary,
        blockers=tuple(blockers),
    )


def _index_toml_artifact(
    spec: OperatorEvidenceProvenanceArtifactSpec,
    relative_label: str,
    digest: str,
    raw_bytes: bytes,
    text: str,
) -> OperatorEvidenceProvenanceArtifact:
    blockers: list[str] = []
    payload: Mapping[str, Any] | None = None
    try:
        payload = _load_toml_mapping(raw_bytes, text)
        parse_status = "parsed_toml"
    except ValueError as exc:
        blockers.append(f"artifact TOML is malformed: {exc}")
        parse_status = "malformed_toml"

    schema_version = ""
    authority = ""
    state_change = ""
    summary = ""
    if payload is not None:
        schema_version = _optional_string(payload.get("schema_version"))
        authority = _optional_string(payload.get("authority"))
        state_change = _optional_string(payload.get("state_change"))
        summary = _summary_from_payload(payload)
        blockers.extend(_payload_blockers(payload))

    return OperatorEvidenceProvenanceArtifact(
        artifact_id=spec.artifact_id,
        path=relative_label,
        artifact_format=spec.artifact_format,
        role=spec.role,
        upstream_artifacts=spec.upstream_artifacts,
        exists=True,
        digest=digest,
        parse_status=parse_status,
        schema_version=schema_version,
        authority=authority,
        state_change=state_change,
        summary=summary,
        blockers=tuple(blockers),
    )


def _spec_blockers(
    artifacts: tuple[OperatorEvidenceProvenanceArtifactSpec, ...],
) -> tuple[str, ...]:
    blockers: list[str] = []
    ids = [artifact.artifact_id for artifact in artifacts]
    seen: set[str] = set()
    duplicates: set[str] = set()
    for artifact_id in ids:
        if artifact_id in seen:
            duplicates.add(artifact_id)
        seen.add(artifact_id)
    for artifact_id in sorted(duplicates):
        blockers.append(f"duplicate artifact id declared: {artifact_id}")
    known = set(ids)
    for artifact in artifacts:
        for dependency in artifact.upstream_artifacts:
            if dependency not in known:
                blockers.append(
                    f"artifact {artifact.artifact_id} declares unknown upstream artifact: {dependency}"
                )
    return tuple(blockers)


def _resolve_under_project_root(root: Path, path: str | Path) -> tuple[Path, str]:
    candidate = Path(path)
    resolved = (root / candidate).resolve() if not candidate.is_absolute() else candidate.resolve()
    if not _is_relative_to(resolved, root):
        raise ValueError(f"path escapes project root: {path}")
    relative = resolved.relative_to(root).as_posix()
    if relative == ".cerebro" or relative.startswith(".cerebro/"):
        raise ValueError(f"path targets canonical state boundary: {relative}")
    return resolved, relative


def _payload_blockers(payload: Mapping[str, Any]) -> tuple[str, ...]:
    blockers: list[str] = []
    if payload.get("state_change") != "none":
        blockers.append("artifact must declare state_change none")
    authority = payload.get("authority")
    if not isinstance(authority, str) or "non-authoritative" not in authority:
        blockers.append("artifact must declare non-authoritative authority")
    return tuple(blockers)


def _summary_from_payload(payload: Mapping[str, Any]) -> str:
    summary = payload.get("summary")
    if isinstance(summary, Mapping):
        pairs = []
        for key in _SUMMARY_KEYS:
            if key in summary:
                pairs.append(f"{key}={_compact(summary[key])}")
        if pairs:
            return "; ".join(pairs)
    return "no indexed summary fields"


def _load_toml_mapping(raw_bytes: bytes, text: str) -> Mapping[str, Any]:
    if tomllib is not None:
        try:
            payload = tomllib.loads(raw_bytes.decode("utf-8"))
        except Exception as exc:  # tomllib raises TOMLDecodeError on malformed files.
            raise ValueError(str(exc)) from exc
        if not isinstance(payload, Mapping):
            raise ValueError("TOML root must be a table")
        return payload
    return _fallback_top_level_toml_mapping(text)


def _fallback_top_level_toml_mapping(text: str) -> Mapping[str, Any]:
    payload: dict[str, Any] = {}
    in_nested_section = False
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("["):
            in_nested_section = True
            continue
        if in_nested_section or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if value.startswith('"') and value.endswith('"'):
            payload[key] = value[1:-1]
        elif value in {"true", "false"}:
            payload[key] = value == "true"
        else:
            payload[key] = value
    return payload


def _stable_digest(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _optional_string(value: Any) -> str:
    return value if isinstance(value, str) else ""


def _compact(value: Any) -> str:
    if isinstance(value, bool):
        return str(value).lower()
    if value is None:
        return "none"
    return str(value)


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _md(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")

