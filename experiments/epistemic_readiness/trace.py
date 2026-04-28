from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

from .contract import ReadinessReport
from .manifest import ReadinessManifest, generate_readiness_report_from_manifest, load_readiness_manifest


TRACE_SCHEMA_VERSION = "1"
TRACE_AUTHORITY = "non-authoritative; advisory trace evidence only"


def _normalize_path(path: str | Path) -> str:
    return str(path).replace("\\", "/")


def _manifest_path_for_trace(root: Path, manifest_path: Path) -> str:
    resolved_root = root.resolve()
    resolved_manifest = manifest_path.resolve()
    try:
        return resolved_manifest.relative_to(resolved_root).as_posix()
    except ValueError:
        return _normalize_path(resolved_manifest)


@dataclass(frozen=True)
class DecisionTrace:
    manifest_path: str
    manifest: ReadinessManifest
    report: ReadinessReport
    state_change: str = "none"
    authority: str = TRACE_AUTHORITY
    trace_role: str = "advisory replay evidence only"

    def __post_init__(self) -> None:
        if self.state_change != "none":
            raise ValueError("decision traces must not change state")
        if self.report.state_change != "none":
            raise ValueError("decision traces cannot wrap mutating reports")
        if self.report.risk_assessment is not None and self.report.risk_assessment.state_change != "none":
            raise ValueError("decision traces cannot wrap mutating risk assessments")

    def to_dict(self) -> dict[str, Any]:
        risk = self.report.risk_assessment
        return {
            "schema_version": TRACE_SCHEMA_VERSION,
            "state_change": self.state_change,
            "authority": self.authority,
            "trace_role": self.trace_role,
            "manifest": {
                "path": self.manifest_path,
                "schema_version": self.manifest.schema_version,
                "generated_report": self.manifest.generated_report,
                "generated_trace": self.manifest.generated_trace,
                "generator": self.manifest.generator,
                "renderer": self.manifest.renderer,
                "trigger": self.manifest.trigger,
                "source_count": len(self.manifest.sources),
                "action_id": self.manifest.action_proposal.action_id
                if self.manifest.action_proposal is not None
                else None,
            },
            "summary": {
                "action_readiness": self.report.action_readiness,
                "source_count": len(self.report.source_reads),
                "candidates_extracted": self.report.candidate_count,
                "findings_evaluated": self.report.finding_count,
                "ready_count": self.report.ready_count,
                "blocked_count": self.report.blocked_count,
                "insufficient_count": self.report.insufficient_count,
            },
            "guardrails": {
                "registered_is_not_true": True,
                "retrieved_is_not_relevant": True,
                "remembered_is_not_trusted": True,
                "silence_is_not_negative_evidence": True,
                "report_readiness_is_not_permission": True,
                "risk_readiness_is_not_permission": True,
                "trace_presence_is_not_permission": True,
                "manifest_presence_is_not_permission": True,
            },
            "source_reads": [
                {
                    "path": read.relative_path,
                    "role": read.source_role,
                    "requested_max_lines": read.requested_max_lines,
                    "lines_read": read.lines_read,
                    "bytes_read": read.bytes_read,
                    "truncated": read.truncated,
                }
                for read in self.report.source_reads
            ],
            "candidates": [
                {
                    "claim_id": candidate.claim_id,
                    "semantic_id": candidate.semantic_id,
                    "evidence_id": candidate.evidence_id,
                    "source_path": candidate.source_path,
                    "evidence_span": candidate.evidence_span,
                    "subject": candidate.subject,
                    "predicate": candidate.predicate,
                    "object": candidate.object,
                    "polarity": candidate.polarity,
                    "modality": candidate.modality,
                    "criticality_hint": candidate.criticality_hint,
                    "source_role": candidate.source_role,
                    "authority_hint": candidate.authority_hint,
                    "extraction_basis": candidate.extraction_basis,
                }
                for candidate in self.report.candidates
            ],
            "findings": [
                {
                    "claim_id": finding.claim.claim_id,
                    "semantic_id": finding.claim.semantic_id,
                    "evidence_id": finding.claim.evidence_id,
                    "authority": finding.authority,
                    "confidence": finding.confidence,
                    "sufficiency": finding.sufficiency,
                    "conflict": finding.conflict,
                    "supersession": finding.supersession,
                    "staleness": finding.staleness,
                    "operational_readiness": finding.operational_readiness,
                    "reasons": list(finding.reasons),
                }
                for finding in self.report.evaluation.findings
            ],
            "risk_assessment": None
            if risk is None
            else {
                "action_id": risk.action_id,
                "purpose": risk.purpose,
                "zone": risk.zone,
                "risk_score": risk.risk_score,
                "declared_gate_level": risk.declared_gate_level,
                "required_gate_level": risk.required_gate_level,
                "budget_status": risk.budget_status,
                "budget_violations": list(risk.budget_violations),
                "human_approval_required": risk.human_approval_required,
                "action_readiness": risk.action_readiness,
                "stop_conditions": list(risk.stop_conditions),
                "state_change": risk.state_change,
                "authority": risk.authority,
            },
            "boundary": {
                "may_suggest": [
                    "inspect evidence",
                    "compare traces",
                    "request human review",
                    "propose a future trigger",
                ],
                "must_not_apply": [
                    "mutate state",
                    "register sources",
                    "act as runtime gate",
                    "create canonical claim graph",
                    "treat trace as permission",
                ],
            },
        }


def build_decision_trace(
    root: str | Path,
    manifest_path: str | Path,
    *,
    report: ReadinessReport | None = None,
) -> DecisionTrace:
    root_path = Path(root)
    manifest_file = Path(manifest_path)
    manifest = load_readiness_manifest(manifest_file)
    readiness_report = report if report is not None else generate_readiness_report_from_manifest(root_path, manifest_file)
    return DecisionTrace(
        manifest_path=_manifest_path_for_trace(root_path, manifest_file),
        manifest=manifest,
        report=readiness_report,
    )


def render_decision_trace_json(trace: DecisionTrace) -> str:
    return json.dumps(trace.to_dict(), indent=2, sort_keys=True) + "\n"
