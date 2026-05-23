from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable

from experiments.claim_extraction import ClaimCandidate

from .contract import EvaluationFinding, EvaluationReport


POSITIVE_POLARITIES = {"positive", "required", "prohibited"}
WEAK_SOURCE_ROLES = {"citation", "derived", "historical"}
ABSENCE_BASES = {"structured_absence", "supersession_absence"}


def _topic(candidate: ClaimCandidate) -> tuple[str, str]:
    return (candidate.subject.lower(), candidate.predicate.lower())


def _authority(candidate: ClaimCandidate) -> tuple[str, str]:
    if candidate.source_role == "primary" and candidate.extraction_basis == "explicit":
        return "source-local", "primary explicit source"
    if candidate.source_role == "citation":
        return "citation-only", "citation does not upgrade authority"
    if candidate.source_role == "derived":
        return "derived-only", "derived candidate requires external support"
    if candidate.source_role == "historical":
        return "historical-only", "historical source cannot decide current state alone"
    return "weak", f"source_role={candidate.source_role}"


def _has_conflict(candidate: ClaimCandidate, topic_claims: tuple[ClaimCandidate, ...]) -> bool:
    if candidate.polarity == "unknown":
        return False
    for other in topic_claims:
        if other.claim_id == candidate.claim_id:
            continue
        if other.polarity == "unknown":
            continue
        if candidate.object != other.object and candidate.polarity != other.polarity:
            return True
        if candidate.object != other.object and {candidate.polarity, other.polarity} <= POSITIVE_POLARITIES:
            return True
    return False


def _has_supersession(candidate: ClaimCandidate, all_claims: tuple[ClaimCandidate, ...]) -> bool:
    needle = candidate.source_path
    for other in all_claims:
        if other.claim_id == candidate.claim_id:
            continue
        if other.extraction_basis != "supersession_absence":
            continue
        if needle in other.subject or needle in other.object:
            return True
    return False


def _evaluate_one(
    candidate: ClaimCandidate,
    *,
    topic_claims: tuple[ClaimCandidate, ...],
    all_claims: tuple[ClaimCandidate, ...],
) -> EvaluationFinding:
    reasons: list[str] = []
    authority, authority_reason = _authority(candidate)
    reasons.append(authority_reason)

    has_absence = candidate.extraction_basis in ABSENCE_BASES
    if has_absence:
        reasons.append(f"{candidate.extraction_basis} is insufficiency evidence, not truth")

    has_conflict = _has_conflict(candidate, topic_claims)
    if has_conflict:
        reasons.append("conflicting claim candidate exists on the same subject/predicate")

    has_supersession = _has_supersession(candidate, all_claims)
    if has_supersession:
        reasons.append("source is superseded or insufficient for this decision")

    if candidate.source_role in WEAK_SOURCE_ROLES:
        reasons.append(f"{candidate.source_role} source role cannot decide action alone")
    if candidate.polarity == "unknown":
        reasons.append("unknown polarity blocks factual readiness")

    conflict = "present" if has_conflict else "none"
    supersession = "present" if has_supersession or candidate.extraction_basis == "supersession_absence" else "none"
    staleness = "stale_by_conflict" if has_conflict or has_supersession else "not_detected"
    sufficiency = "insufficient" if has_absence or candidate.source_role in WEAK_SOURCE_ROLES else "sufficient"
    confidence = "low" if has_conflict or has_absence or candidate.polarity == "unknown" else "bounded"

    readiness_blocked = (
        has_conflict
        or has_absence
        or has_supersession
        or candidate.polarity == "unknown"
        or candidate.source_role in WEAK_SOURCE_ROLES
        or authority != "source-local"
    )
    operational_readiness = "blocked" if readiness_blocked else "ready"

    return EvaluationFinding(
        claim=candidate,
        authority=authority,
        confidence=confidence,
        sufficiency=sufficiency,
        conflict=conflict,
        supersession=supersession,
        staleness=staleness,
        operational_readiness=operational_readiness,
        reasons=tuple(reasons),
    )


def evaluate_claims(candidates: Iterable[ClaimCandidate]) -> EvaluationReport:
    ordered = tuple(sorted(candidates, key=lambda item: (item.source_path, item.evidence_span, item.claim_id)))
    by_topic: dict[tuple[str, str], list[ClaimCandidate]] = defaultdict(list)
    for candidate in ordered:
        by_topic[_topic(candidate)].append(candidate)

    findings = tuple(
        _evaluate_one(
            candidate,
            topic_claims=tuple(by_topic[_topic(candidate)]),
            all_claims=ordered,
        )
        for candidate in ordered
    )
    return EvaluationReport(findings=findings)
