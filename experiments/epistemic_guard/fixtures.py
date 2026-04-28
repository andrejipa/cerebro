from __future__ import annotations

from .contract import (
    ActionProfile,
    ApprovalContext,
    DecisionScenario,
    EvidenceClaim,
    EvidenceRequirement,
    EvidenceSource,
    PathDigest,
    PrewriteGuard,
)


def stale_next_action() -> DecisionScenario:
    return DecisionScenario(
        scenario_id="stale_next_action",
        intent="Decide whether the next project step is to create schema or implement Edge Functions.",
        action_profile=ActionProfile(
            zone="ZONE_1",
            reads=("04_DIAGNOSTICO_INICIAL_ATUAL.md", "04_MEMORIA_CONTINUIDADE_ATUAL.md"),
        ),
        sources=(
            EvidenceSource("diagnostic", "04_DIAGNOSTICO_INICIAL_ATUAL.md", freshness="stale"),
            EvidenceSource("continuity", "04_MEMORIA_CONTINUIDADE_ATUAL.md", freshness="current"),
        ),
        claims=(
            EvidenceClaim(
                "claim-old-next",
                "next_action",
                "is",
                "create_schema",
                "diagnostic",
                status="stale",
                staleness="stale_by_supersession",
            ),
            EvidenceClaim("claim-new-next", "next_action", "is", "implement_edge_functions", "continuity"),
            EvidenceClaim("claim-schema", "schema", "exists", "true", "continuity"),
        ),
    )


def silence_is_not_negative_evidence() -> DecisionScenario:
    return DecisionScenario(
        scenario_id="silence_is_not_negative_evidence",
        intent="Decide whether schema is absent because a diagnostic source did not mention it.",
        action_profile=ActionProfile(zone="ZONE_0", reads=("04_DIAGNOSTICO_INICIAL_ATUAL.md",)),
        sources=(EvidenceSource("diagnostic", "04_DIAGNOSTICO_INICIAL_ATUAL.md"),),
        claims=(
            EvidenceClaim(
                "claim-omission",
                "diagnostic",
                "does_not_declare",
                "schema_status",
                "diagnostic",
                status="unknown",
                confidence="low",
            ),
        ),
        requirements=(
            EvidenceRequirement(
                "req-schema-status",
                "schema",
                "exists",
                "explicit schema existence evidence",
                "schema-dependent action",
            ),
        ),
    )


def existing_state_ambiguity() -> DecisionScenario:
    return DecisionScenario(
        scenario_id="existing_state_ambiguity",
        intent="Start a third-party pilot where a prior .cerebro/state.json already exists.",
        action_profile=ActionProfile(
            zone="ZONE_1",
            reads=("target/.cerebro/state.json",),
            authority_impact="advisory",
            existing_state_policy="ambiguous",
        ),
        sources=(EvidenceSource("state-observation", "target/.cerebro/state.json", role="state-observation"),),
        claims=(
            EvidenceClaim("claim-prior-state", "target_cerebro_state", "exists", "true", "state-observation"),
        ),
    )


def missing_trigger_for_runtime_mutation() -> DecisionScenario:
    return DecisionScenario(
        scenario_id="missing_trigger_for_runtime_mutation",
        intent="Edit core runtime behavior without an active formal trigger.",
        action_profile=ActionProfile(
            zone="ZONE_3",
            reads=("core/state_store.py",),
            writes=("core/state_store.py",),
            authority_impact="canonical",
            runtime_impact="direct",
            reversibility="medium",
            active_trigger=False,
        ),
        sources=(EvidenceSource("runtime-file", "core/state_store.py"),),
        claims=(EvidenceClaim("claim-runtime-touch", "core_runtime", "would_change", "true", "runtime-file"),),
        approval=ApprovalContext(status="not_required"),
    )


def approval_expired_by_source_set_change() -> DecisionScenario:
    return DecisionScenario(
        scenario_id="approval_expired_by_source_set_change",
        intent="Apply a plan after a new decisive source entered the read set.",
        action_profile=ActionProfile(
            zone="ZONE_2",
            reads=("A.md", "B.md"),
            writes=("report.md",),
            authority_impact="advisory",
            runtime_impact="none",
            reversibility="high",
        ),
        sources=(EvidenceSource("a", "A.md"), EvidenceSource("b", "B.md")),
        claims=(EvidenceClaim("claim-plan", "plan", "is_ready", "true", "a"),),
        approval=ApprovalContext(
            status="approved",
            approval_id="approval-1",
            approved_reads=("A.md",),
            approved_writes=("report.md",),
        ),
    )


def read_write_drift() -> DecisionScenario:
    return DecisionScenario(
        scenario_id="read_write_drift",
        intent="Write a report based on a file whose digest changed after read.",
        action_profile=ActionProfile(
            zone="ZONE_2",
            reads=("SYSTEM_STATE.md",),
            writes=("derived-report.md",),
            authority_impact="advisory",
            reversibility="high",
        ),
        sources=(EvidenceSource("system-state", "SYSTEM_STATE.md"),),
        claims=(EvidenceClaim("claim-snapshot", "system_snapshot", "supports", "report", "system-state"),),
        approval=ApprovalContext(
            status="approved",
            approval_id="approval-2",
            approved_reads=("SYSTEM_STATE.md",),
            approved_writes=("derived-report.md",),
        ),
        prewrite_guard=PrewriteGuard(
            read_digests=(PathDigest("SYSTEM_STATE.md", "sha256:old"),),
            current_digests=(PathDigest("SYSTEM_STATE.md", "sha256:new"),),
        ),
    )


def protocol_induced_stale_source_route() -> DecisionScenario:
    return DecisionScenario(
        scenario_id="protocol_induced_stale_source_route",
        intent="Follow a protocol route that prioritizes a stale diagnostic over current continuity.",
        action_profile=ActionProfile(
            zone="ZONE_1",
            reads=("03_HIERARQUIA_DE_FONTES.md", "04_DIAGNOSTICO_INICIAL_ATUAL.md"),
        ),
        sources=(
            EvidenceSource("protocol", "03_HIERARQUIA_DE_FONTES.md", role="protocol", freshness="current"),
            EvidenceSource("diagnostic", "04_DIAGNOSTICO_INICIAL_ATUAL.md", freshness="stale"),
            EvidenceSource("continuity", "04_MEMORIA_CONTINUIDADE_ATUAL.md", freshness="current"),
        ),
        claims=(
            EvidenceClaim("claim-route", "protocol_route", "prefers", "diagnostic", "protocol"),
            EvidenceClaim(
                "claim-diagnostic-next",
                "next_action",
                "is",
                "create_schema",
                "diagnostic",
                status="stale",
                staleness="stale_by_protocol_drift",
            ),
            EvidenceClaim("claim-continuity-next", "next_action", "is", "implement_edge_functions", "continuity"),
        ),
        protocol_notes=("protocol_route_correlates_with_stale_source",),
    )


def clean_advisory_report() -> DecisionScenario:
    return DecisionScenario(
        scenario_id="clean_advisory_report",
        intent="Produce a read-only advisory report from current bounded evidence.",
        action_profile=ActionProfile(
            zone="ZONE_1",
            reads=("SYSTEM_STATE.md", "OPPORTUNITY_MAP.md"),
            authority_impact="none",
            runtime_impact="none",
            reversibility="high",
        ),
        sources=(
            EvidenceSource("system", "SYSTEM_STATE.md"),
            EvidenceSource("opportunity", "OPPORTUNITY_MAP.md"),
        ),
        claims=(
            EvidenceClaim("claim-current-boundary", "runtime_boundary", "is", "closed", "system"),
            EvidenceClaim("claim-next", "next_action", "is", "applied_decision_oracle", "opportunity"),
        ),
        requirements=(
            EvidenceRequirement("req-boundary", "runtime_boundary", "is", "current runtime boundary", "advisory report"),
            EvidenceRequirement("req-next", "next_action", "is", "current next action", "advisory report"),
        ),
    )


def all_fixture_scenarios() -> tuple[DecisionScenario, ...]:
    return (
        stale_next_action(),
        silence_is_not_negative_evidence(),
        existing_state_ambiguity(),
        missing_trigger_for_runtime_mutation(),
        approval_expired_by_source_set_change(),
        read_write_drift(),
        protocol_induced_stale_source_route(),
        clean_advisory_report(),
    )
