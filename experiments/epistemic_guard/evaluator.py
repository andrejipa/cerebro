from __future__ import annotations

from collections import defaultdict

from .contract import (
    ActionProfile,
    DecisionEnvelope,
    DecisionScenario,
    EvidenceClaim,
    EvidenceRequirement,
    EvidenceSource,
    PathDigest,
)


def _claim_key(claim: EvidenceClaim) -> tuple[str, str]:
    return (claim.subject.casefold(), claim.predicate.casefold())


def _claim_line(claim: EvidenceClaim) -> str:
    return f"{claim.claim_id}: {claim.subject} {claim.predicate} {claim.value} [{claim.source_id}]"


def _source_by_id(sources: tuple[EvidenceSource, ...]) -> dict[str, EvidenceSource]:
    return {source.source_id: source for source in sources}


def _detect_conflicts(claims: tuple[EvidenceClaim, ...]) -> tuple[str, ...]:
    grouped: dict[tuple[str, str], list[EvidenceClaim]] = defaultdict(list)
    for claim in claims:
        grouped[_claim_key(claim)].append(claim)

    conflicts: list[str] = []
    for key, key_claims in sorted(grouped.items()):
        values = {claim.value for claim in key_claims if claim.status != "unknown"}
        if len(values) < 2:
            continue
        claim_ids = ", ".join(sorted(claim.claim_id for claim in key_claims))
        conflicts.append(f"{key[0]}:{key[1]} has conflicting values across {claim_ids}")
    return tuple(conflicts)


def _detect_stale_claims(
    claims: tuple[EvidenceClaim, ...],
    sources: dict[str, EvidenceSource],
) -> tuple[str, ...]:
    stale: list[str] = []
    for claim in sorted(claims, key=lambda item: item.claim_id):
        source = sources.get(claim.source_id)
        source_stale = source is not None and source.freshness in {"stale", "superseded", "deprecated"}
        claim_stale = claim.status in {"stale", "superseded", "deprecated"} or claim.staleness != "not_detected"
        if source_stale or claim_stale:
            reason = claim.staleness
            if source_stale:
                reason = f"source_{source.freshness}"
            stale.append(f"{claim.claim_id}: {reason}")
    return tuple(stale)


def _detect_missing_evidence(
    claims: tuple[EvidenceClaim, ...],
    requirements: tuple[EvidenceRequirement, ...],
) -> tuple[str, ...]:
    present = {
        _claim_key(claim)
        for claim in claims
        if claim.status == "current" and claim.value not in {"unknown", "not_declared"}
    }

    missing = []
    for requirement in sorted(requirements, key=lambda item: item.requirement_id):
        if (requirement.subject.casefold(), requirement.predicate.casefold()) not in present:
            missing.append(
                f"{requirement.requirement_id}: missing {requirement.description} for {requirement.required_for}"
            )
    return tuple(missing)


def _digest_map(digests: tuple[PathDigest, ...]) -> dict[str, str]:
    return {digest.path: digest.digest for digest in digests}


def _prewrite_status(scenario: DecisionScenario) -> tuple[str, tuple[str, ...]]:
    if not scenario.action_profile.writes:
        return "not_applicable", ()

    read_digests = _digest_map(scenario.prewrite_guard.read_digests)
    current_digests = _digest_map(scenario.prewrite_guard.current_digests)
    drift = [
        path
        for path, read_digest in sorted(read_digests.items())
        if path in current_digests and current_digests[path] != read_digest
    ]
    if drift:
        return "blocked_read_write_drift", tuple(f"read_write_drift:{path}" for path in drift)

    if any(path.replace("\\", "/").endswith(".cerebro/state.json") for path in scenario.action_profile.writes):
        return "blocked_cerebro_state_write", ("write_to_canonical_state_requested",)

    return "passed", ()


def _approval_status(scenario: DecisionScenario) -> tuple[str, tuple[str, ...]]:
    approval = scenario.approval
    action = scenario.action_profile

    if approval.status == "not_required":
        if action.authority_impact == "canonical" or action.runtime_impact == "direct":
            return "missing_for_authority_impact", ("human_approval_missing_for_authority_impact",)
        return "not_required", ()

    if approval.status != "approved":
        return approval.status, (f"approval_{approval.status}",)

    approved_reads = tuple(sorted(approval.approved_reads))
    current_reads = tuple(sorted(action.reads))
    if approved_reads != current_reads:
        return "expired_by_source_set_change", ("approval_expired_by_source_set_change",)

    approved_writes = tuple(sorted(approval.approved_writes))
    current_writes = tuple(sorted(action.writes))
    if approved_writes != current_writes:
        return "expired_by_write_set_change", ("approval_expired_by_write_set_change",)

    return "approved_current", ()


def _runtime_authority_blocks(action: ActionProfile) -> tuple[str, ...]:
    blockers: list[str] = []
    if action.existing_state_policy == "ambiguous":
        blockers.append("existing_state_ambiguity")
    if (action.authority_impact == "canonical" or action.runtime_impact == "direct") and not action.active_trigger:
        blockers.append("missing_active_trigger_for_runtime_or_canonical_change")
    return tuple(blockers)


def _sufficiency(
    *,
    blockers: tuple[str, ...],
    conflicts: tuple[str, ...],
    stale_claims: tuple[str, ...],
    missing_evidence: tuple[str, ...],
) -> str:
    if blockers:
        return "blocked"
    if conflicts or stale_claims:
        return "insufficient"
    if missing_evidence:
        return "partial"
    return "sufficient"


def _readiness(
    scenario: DecisionScenario,
    *,
    sufficiency: str,
    blockers: tuple[str, ...],
    conflicts: tuple[str, ...],
    stale_claims: tuple[str, ...],
    missing_evidence: tuple[str, ...],
    approval_status: str,
) -> str:
    if "missing_active_trigger_for_runtime_or_canonical_change" in blockers:
        return "canonical_change_requires_trigger"
    if blockers:
        return "blocked"
    if conflicts or stale_claims or missing_evidence:
        return "human_approval_required"
    if approval_status.startswith("expired") or approval_status == "missing_for_authority_impact":
        return "human_approval_required"
    if sufficiency == "sufficient" and not scenario.action_profile.writes:
        return "advisory_report_allowed"
    if scenario.action_profile.authority_impact == "none" and scenario.action_profile.reversibility == "high":
        return "derived_experiment_allowed"
    return "propose_only"


def _recommended_human_decision(
    *,
    blockers: tuple[str, ...],
    conflicts: tuple[str, ...],
    stale_claims: tuple[str, ...],
    missing_evidence: tuple[str, ...],
    approval_status: str,
) -> str:
    if "missing_active_trigger_for_runtime_or_canonical_change" in blockers:
        return "review_blockers"
    if "existing_state_ambiguity" in blockers:
        return "adjudicate_conflict"
    if blockers:
        return "review_blockers"
    if conflicts or stale_claims:
        return "adjudicate_conflict"
    if missing_evidence:
        return "provide_missing_evidence"
    if approval_status.startswith("expired") or approval_status == "missing_for_authority_impact":
        return "approve_action"
    return "none"


def evaluate_decision_scenario(scenario: DecisionScenario) -> DecisionEnvelope:
    sources = _source_by_id(scenario.sources)
    ordered_claims = tuple(sorted(scenario.claims, key=lambda item: item.claim_id))
    claim_summary = tuple(_claim_line(claim) for claim in ordered_claims)
    conflicts = _detect_conflicts(ordered_claims)
    stale_claims = _detect_stale_claims(ordered_claims, sources)
    missing_evidence = _detect_missing_evidence(ordered_claims, scenario.requirements)
    approval_status, approval_blocks = _approval_status(scenario)
    prewrite_guard_status, prewrite_blocks = _prewrite_status(scenario)
    runtime_blocks = _runtime_authority_blocks(scenario.action_profile)

    blockers = tuple(sorted({*approval_blocks, *prewrite_blocks, *runtime_blocks}))
    sufficiency = _sufficiency(
        blockers=blockers,
        conflicts=conflicts,
        stale_claims=stale_claims,
        missing_evidence=missing_evidence,
    )
    action_readiness = _readiness(
        scenario,
        sufficiency=sufficiency,
        blockers=blockers,
        conflicts=conflicts,
        stale_claims=stale_claims,
        missing_evidence=missing_evidence,
        approval_status=approval_status,
    )
    recommended = _recommended_human_decision(
        blockers=blockers,
        conflicts=conflicts,
        stale_claims=stale_claims,
        missing_evidence=missing_evidence,
        approval_status=approval_status,
    )

    warnings = tuple(sorted(scenario.protocol_notes))
    return DecisionEnvelope(
        scenario_id=scenario.scenario_id,
        intent=scenario.intent,
        action_profile=scenario.action_profile,
        read_set=tuple(sorted(scenario.action_profile.reads)),
        claim_summary=claim_summary,
        missing_evidence=missing_evidence,
        stale_claims=stale_claims,
        conflicts=conflicts,
        approval_status=approval_status,
        prewrite_guard_status=prewrite_guard_status,
        sufficiency=sufficiency,
        action_readiness=action_readiness,
        recommended_human_decision=recommended,
        blockers=blockers,
        warnings=warnings,
    )
