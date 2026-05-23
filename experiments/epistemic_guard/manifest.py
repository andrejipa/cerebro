from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any

from .contract import (
    ActionProfile,
    ApprovalContext,
    DecisionEnvelope,
    DecisionScenario,
    EvidenceClaim,
    EvidenceRequirement,
    EvidenceSource,
    PathDigest,
    PrewriteGuard,
)
from .evaluator import evaluate_decision_scenario


class DecisionManifestError(ValueError):
    """Raised when a decision-envelope manifest is malformed or unsafe."""


def _as_tuple(value: object, *, field: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        raise DecisionManifestError(f"{field} must be a list")
    if not all(isinstance(item, str) for item in value):
        raise DecisionManifestError(f"{field} must contain only strings")
    return tuple(value)


def _as_table(value: object, *, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise DecisionManifestError(f"{field} must be a table")
    return value


def _as_table_list(value: object, *, field: str) -> tuple[dict[str, Any], ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        raise DecisionManifestError(f"{field} must be a list of tables")
    tables: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            raise DecisionManifestError(f"{field} must contain only tables")
        tables.append(item)
    return tuple(tables)


def _required_str(table: dict[str, Any], field: str) -> str:
    value = table.get(field)
    if not isinstance(value, str) or not value:
        raise DecisionManifestError(f"missing required string field: {field}")
    return value


def _optional_str(table: dict[str, Any], field: str, default: str) -> str:
    value = table.get(field, default)
    if not isinstance(value, str):
        raise DecisionManifestError(f"{field} must be a string")
    return value


def _optional_bool(table: dict[str, Any], field: str, default: bool) -> bool:
    value = table.get(field, default)
    if not isinstance(value, bool):
        raise DecisionManifestError(f"{field} must be a boolean")
    return value


def _resolve_manifest_path(path: str | Path, *, root: str | Path | None) -> Path:
    root_path = Path.cwd() if root is None else Path(root)
    resolved_root = root_path.resolve()
    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = resolved_root / candidate
    resolved = candidate.resolve()

    try:
        resolved.relative_to(resolved_root)
    except ValueError as exc:
        raise DecisionManifestError("manifest path escapes root") from exc

    if any(part.casefold() == ".cerebro" for part in resolved.parts):
        raise DecisionManifestError("manifest path may not live under .cerebro")
    return resolved


def _parse_sources(raw_sources: object, *, scenario_id: str) -> tuple[EvidenceSource, ...]:
    sources = []
    seen: set[str] = set()
    for raw in _as_table_list(raw_sources, field=f"{scenario_id}.sources"):
        source_id = _required_str(raw, "source_id")
        if source_id in seen:
            raise DecisionManifestError(f"{scenario_id} duplicates source_id {source_id}")
        seen.add(source_id)
        sources.append(
            EvidenceSource(
                source_id=source_id,
                path=_required_str(raw, "path"),
                authority_state=_optional_str(raw, "authority_state", "advisory"),
                freshness=_optional_str(raw, "freshness", "current"),
                role=_optional_str(raw, "role", "primary"),
            )
        )
    return tuple(sources)


def _parse_claims(
    raw_claims: object,
    *,
    scenario_id: str,
    source_ids: set[str],
) -> tuple[EvidenceClaim, ...]:
    claims = []
    seen: set[str] = set()
    for raw in _as_table_list(raw_claims, field=f"{scenario_id}.claims"):
        claim_id = _required_str(raw, "claim_id")
        if claim_id in seen:
            raise DecisionManifestError(f"{scenario_id} duplicates claim_id {claim_id}")
        seen.add(claim_id)
        source_id = _required_str(raw, "source_id")
        if source_id not in source_ids:
            raise DecisionManifestError(f"{scenario_id} claim {claim_id} references undeclared source {source_id}")
        claims.append(
            EvidenceClaim(
                claim_id=claim_id,
                subject=_required_str(raw, "subject"),
                predicate=_required_str(raw, "predicate"),
                value=_required_str(raw, "value"),
                source_id=source_id,
                status=_optional_str(raw, "status", "current"),
                confidence=_optional_str(raw, "confidence", "bounded"),
                staleness=_optional_str(raw, "staleness", "not_detected"),
                depends_on=_as_tuple(raw.get("depends_on"), field=f"{scenario_id}.{claim_id}.depends_on"),
            )
        )
    return tuple(claims)


def _parse_requirements(raw_requirements: object, *, scenario_id: str) -> tuple[EvidenceRequirement, ...]:
    requirements = []
    seen: set[str] = set()
    for raw in _as_table_list(raw_requirements, field=f"{scenario_id}.requirements"):
        requirement_id = _required_str(raw, "requirement_id")
        if requirement_id in seen:
            raise DecisionManifestError(f"{scenario_id} duplicates requirement_id {requirement_id}")
        seen.add(requirement_id)
        requirements.append(
            EvidenceRequirement(
                requirement_id=requirement_id,
                subject=_required_str(raw, "subject"),
                predicate=_required_str(raw, "predicate"),
                description=_required_str(raw, "description"),
                required_for=_required_str(raw, "required_for"),
            )
        )
    return tuple(requirements)


def _parse_digests(raw_digests: object, *, field: str) -> tuple[PathDigest, ...]:
    return tuple(
        PathDigest(path=_required_str(raw, "path"), digest=_required_str(raw, "digest"))
        for raw in _as_table_list(raw_digests, field=field)
    )


def _parse_action_profile(raw_profile: object, *, scenario_id: str) -> ActionProfile:
    raw = _as_table(raw_profile, field=f"{scenario_id}.action_profile")
    return ActionProfile(
        zone=_required_str(raw, "zone"),
        reads=_as_tuple(raw.get("reads"), field=f"{scenario_id}.action_profile.reads"),
        writes=_as_tuple(raw.get("writes"), field=f"{scenario_id}.action_profile.writes"),
        authority_impact=_optional_str(raw, "authority_impact", "none"),
        runtime_impact=_optional_str(raw, "runtime_impact", "none"),
        reversibility=_optional_str(raw, "reversibility", "high"),
        active_trigger=_optional_bool(raw, "active_trigger", False),
        existing_state_policy=_optional_str(raw, "existing_state_policy", "not_applicable"),
    )


def _parse_approval(raw_approval: object, *, scenario_id: str) -> ApprovalContext:
    if raw_approval is None:
        return ApprovalContext()
    raw = _as_table(raw_approval, field=f"{scenario_id}.approval")
    return ApprovalContext(
        status=_optional_str(raw, "status", "not_required"),
        approval_id=_optional_str(raw, "approval_id", ""),
        approved_reads=_as_tuple(raw.get("approved_reads"), field=f"{scenario_id}.approval.approved_reads"),
        approved_writes=_as_tuple(raw.get("approved_writes"), field=f"{scenario_id}.approval.approved_writes"),
    )


def _parse_prewrite_guard(raw_guard: object, *, scenario_id: str) -> PrewriteGuard:
    if raw_guard is None:
        return PrewriteGuard()
    raw = _as_table(raw_guard, field=f"{scenario_id}.prewrite_guard")
    return PrewriteGuard(
        read_digests=_parse_digests(raw.get("read_digests"), field=f"{scenario_id}.prewrite_guard.read_digests"),
        current_digests=_parse_digests(
            raw.get("current_digests"),
            field=f"{scenario_id}.prewrite_guard.current_digests",
        ),
    )


def _parse_scenario(raw: dict[str, Any]) -> DecisionScenario:
    scenario_id = _required_str(raw, "scenario_id")
    sources = _parse_sources(raw.get("sources"), scenario_id=scenario_id)
    source_ids = {source.source_id for source in sources}
    return DecisionScenario(
        scenario_id=scenario_id,
        intent=_required_str(raw, "intent"),
        action_profile=_parse_action_profile(raw.get("action_profile"), scenario_id=scenario_id),
        sources=sources,
        claims=_parse_claims(raw.get("claims"), scenario_id=scenario_id, source_ids=source_ids),
        requirements=_parse_requirements(raw.get("requirements"), scenario_id=scenario_id),
        approval=_parse_approval(raw.get("approval"), scenario_id=scenario_id),
        prewrite_guard=_parse_prewrite_guard(raw.get("prewrite_guard"), scenario_id=scenario_id),
        protocol_notes=_as_tuple(raw.get("protocol_notes"), field=f"{scenario_id}.protocol_notes"),
    )


def load_decision_manifest(path: str | Path, *, root: str | Path | None = None) -> tuple[DecisionScenario, ...]:
    manifest_path = _resolve_manifest_path(path, root=root)
    payload = tomllib.loads(manifest_path.read_text(encoding="utf-8"))

    if payload.get("schema_version") != "1":
        raise DecisionManifestError("schema_version must be '1'")
    raw_scenarios = payload.get("scenario")
    if not isinstance(raw_scenarios, list) or not raw_scenarios:
        raise DecisionManifestError("manifest must contain at least one [[scenario]]")

    scenarios = tuple(_parse_scenario(_as_table(raw, field="scenario")) for raw in raw_scenarios)
    scenario_ids = [scenario.scenario_id for scenario in scenarios]
    duplicates = sorted({scenario_id for scenario_id in scenario_ids if scenario_ids.count(scenario_id) > 1})
    if duplicates:
        raise DecisionManifestError(f"duplicate scenario_id: {', '.join(duplicates)}")
    return scenarios


def evaluate_manifest_file(path: str | Path, *, root: str | Path | None = None) -> tuple[DecisionEnvelope, ...]:
    return tuple(evaluate_decision_scenario(scenario) for scenario in load_decision_manifest(path, root=root))
