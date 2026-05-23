from __future__ import annotations

from collections.abc import Iterable

from .contract import ClaimCandidate


def render_candidates_markdown(candidates: Iterable[ClaimCandidate]) -> str:
    lines = ["# Claim Candidates", ""]
    for candidate in candidates:
        lines.extend(
            [
                f"## {candidate.claim_id}",
                "",
                f"- subject: `{candidate.subject}`",
                f"- predicate: `{candidate.predicate}`",
                f"- object: `{candidate.object}`",
                f"- polarity: `{candidate.polarity}`",
                f"- modality: `{candidate.modality}`",
                f"- criticality_hint: `{candidate.criticality_hint}`",
                f"- semantic_id: `{candidate.semantic_id}`",
                f"- evidence_id: `{candidate.evidence_id}`",
                f"- source: `{candidate.source_path}:{candidate.evidence_span}`",
                f"- source_role: `{candidate.source_role}`",
                f"- extraction_basis: `{candidate.extraction_basis}`",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"
