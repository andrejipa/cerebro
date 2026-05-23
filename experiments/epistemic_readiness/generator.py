from __future__ import annotations

from pathlib import Path

from experiments.claim_evaluation import evaluate_claims
from experiments.claim_extraction import SourceText, extract_candidates

from .contract import BaselineMetrics, BoundedSourceRead, ReadinessReport, SourceManifestEntry
from .risk import ActionProposal, RiskAssessment, evaluate_risk_budget


MAX_SOURCE_BYTES = 32768


def _safe_manifest_path(root: Path, relative_path: str) -> Path:
    root_resolved = root.resolve()
    candidate = (root_resolved / relative_path).resolve()
    try:
        candidate.relative_to(root_resolved)
    except ValueError as exc:
        raise ValueError(f"manifest path escapes root: {relative_path}") from exc

    if any(part.lower() == ".cerebro" for part in candidate.relative_to(root_resolved).parts):
        raise ValueError(f"manifest path points into .cerebro: {relative_path}")
    if not candidate.is_file():
        raise FileNotFoundError(f"manifest source is not a file: {relative_path}")
    return candidate


def _read_bounded_source(root: Path, entry: SourceManifestEntry) -> tuple[SourceText, BoundedSourceRead]:
    path = _safe_manifest_path(root, entry.relative_path)
    chunks: list[bytes] = []
    bytes_read = 0
    lines_read = 0
    truncated = False

    with path.open("rb") as handle:
        while lines_read < entry.max_lines and bytes_read < MAX_SOURCE_BYTES:
            remaining = MAX_SOURCE_BYTES - bytes_read
            line = handle.readline(remaining + 1)
            if not line:
                break
            if len(line) > remaining:
                chunks.append(line[:remaining])
                bytes_read += remaining
                truncated = True
                break
            chunks.append(line)
            bytes_read += len(line)
            lines_read += 1

        if lines_read >= entry.max_lines and handle.read(1):
            truncated = True

    text = b"".join(chunks).decode("utf-8", errors="replace")
    source = SourceText(
        source_path=entry.relative_path.replace("\\", "/"),
        text=text,
        source_role=entry.source_role,
    )
    read = BoundedSourceRead(
        relative_path=source.source_path,
        source_role=entry.source_role,
        requested_max_lines=entry.max_lines,
        lines_read=lines_read,
        bytes_read=bytes_read,
        truncated=truncated,
    )
    return source, read


def _action_readiness(report) -> str:
    if not report.findings:
        return "observe_only"
    if report.blocked_count:
        return "human_approval_required"
    if report.insufficient_count:
        return "propose_only"
    return "advisory_report_allowed"


def _combined_action_readiness(report, risk_assessment: RiskAssessment | None) -> str:
    evidence_readiness = _action_readiness(report)
    if risk_assessment is None:
        return evidence_readiness
    if risk_assessment.action_readiness in {
        "blocked",
        "canonical_change_requires_trigger",
        "human_approval_required",
    }:
        return risk_assessment.action_readiness
    if evidence_readiness in {"human_approval_required", "propose_only", "observe_only"}:
        return evidence_readiness
    return risk_assessment.action_readiness


def generate_readiness_report(
    root: str | Path,
    manifest: tuple[SourceManifestEntry, ...] | list[SourceManifestEntry],
    *,
    baseline: BaselineMetrics | None = None,
    action_proposal: ActionProposal | None = None,
) -> ReadinessReport:
    if len(manifest) > 24:
        raise ValueError("manifest must contain at most 24 sources")

    root_path = Path(root)
    sources: list[SourceText] = []
    reads: list[BoundedSourceRead] = []
    for entry in manifest:
        source, read = _read_bounded_source(root_path, entry)
        sources.append(source)
        reads.append(read)

    candidates = tuple(extract_candidates(sources))
    evaluation = evaluate_claims(candidates)
    risk_assessment = evaluate_risk_budget(action_proposal) if action_proposal is not None else None
    return ReadinessReport(
        source_reads=tuple(reads),
        candidates=candidates,
        evaluation=evaluation,
        action_readiness=_combined_action_readiness(evaluation, risk_assessment),
        risk_assessment=risk_assessment,
        baseline=baseline,
    )
