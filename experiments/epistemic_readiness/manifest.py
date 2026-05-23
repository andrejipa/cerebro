from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import tomllib
from typing import Any

from .contract import BaselineMetrics, SourceManifestEntry
from .generator import generate_readiness_report
from .risk import ActionProposal, BlastRadiusDeclaration, RiskBudget


SUPPORTED_SCHEMA_VERSION = "1"
REQUIRED_AUTHORITY = "non-authoritative; advisory evidence only"


@dataclass(frozen=True)
class ReadinessManifest:
    schema_version: str
    generated_report: str
    generated_trace: str | None
    generator: str
    renderer: str
    authority: str
    state_change: str
    trigger: str
    sources: tuple[SourceManifestEntry, ...]
    baseline: BaselineMetrics | None = None
    action_proposal: ActionProposal | None = None

    def __post_init__(self) -> None:
        if self.schema_version != SUPPORTED_SCHEMA_VERSION:
            raise ValueError(f"unsupported manifest schema_version: {self.schema_version}")
        if self.authority != REQUIRED_AUTHORITY:
            raise ValueError(f"unsupported manifest authority: {self.authority}")
        if self.state_change != "none":
            raise ValueError("epistemic-readiness manifests must declare state_change = none")
        if not self.generated_report:
            raise ValueError("generated_report is required")
        if self.generated_trace == "":
            raise ValueError("generated_trace must not be empty when declared")
        if not self.generator:
            raise ValueError("generator is required")
        if not self.renderer:
            raise ValueError("renderer is required")
        if not self.trigger:
            raise ValueError("trigger is required")
        if not self.sources:
            raise ValueError("manifest must include at least one source")


def _require_str(mapping: dict[str, Any], key: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"{key} is required")
    return value


def _optional_tuple(mapping: dict[str, Any], key: str) -> tuple[str, ...]:
    value = mapping.get(key, [])
    if not isinstance(value, list):
        raise ValueError(f"{key} must be a list of strings")
    result: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item:
            raise ValueError(f"{key} must be a list of non-empty strings")
        result.append(item)
    return tuple(result)


def _optional_bool(mapping: dict[str, Any], key: str, *, default: bool = False) -> bool:
    value = mapping.get(key, default)
    if not isinstance(value, bool):
        raise ValueError(f"{key} must be a boolean")
    return value


def _optional_int(mapping: dict[str, Any], key: str, *, default: int = 0) -> int:
    value = mapping.get(key, default)
    if not isinstance(value, int):
        raise ValueError(f"{key} must be an integer")
    return value


def _optional_str(mapping: dict[str, Any], key: str) -> str | None:
    value = mapping.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"{key} must be a string")
    return value


def _load_sources(data: dict[str, Any]) -> tuple[SourceManifestEntry, ...]:
    raw_sources = data.get("source")
    if not isinstance(raw_sources, list):
        raise ValueError("manifest must include [[source]] entries")

    sources: list[SourceManifestEntry] = []
    for raw_source in raw_sources:
        if not isinstance(raw_source, dict):
            raise ValueError("source entries must be tables")
        sources.append(
            SourceManifestEntry(
                relative_path=_require_str(raw_source, "path"),
                max_lines=_optional_int(raw_source, "max_lines", default=80),
                source_role=_require_str(raw_source, "source_role"),
            )
        )
    return tuple(sources)


def _load_baseline(data: dict[str, Any]) -> BaselineMetrics | None:
    raw_baseline = data.get("baseline")
    if raw_baseline is None:
        return None
    if not isinstance(raw_baseline, dict):
        raise ValueError("baseline must be a table")
    return BaselineMetrics(
        label=_require_str(raw_baseline, "label"),
        candidates_extracted=_optional_int(raw_baseline, "candidates_extracted"),
        findings_evaluated=_optional_int(raw_baseline, "findings_evaluated"),
        ready_count=_optional_int(raw_baseline, "ready_count"),
        blocked_count=_optional_int(raw_baseline, "blocked_count"),
        insufficient_count=_optional_int(raw_baseline, "insufficient_count"),
    )


def _load_action(data: dict[str, Any]) -> ActionProposal | None:
    raw_action = data.get("action")
    if raw_action is None:
        return None
    if not isinstance(raw_action, dict):
        raise ValueError("action must be a table")

    raw_blast = raw_action.get("blast_radius")
    if not isinstance(raw_blast, dict):
        raise ValueError("action.blast_radius is required")

    raw_budget = raw_action.get("risk_budget")
    if not isinstance(raw_budget, dict):
        raise ValueError("action.risk_budget is required")

    return ActionProposal(
        action_id=_require_str(raw_action, "action_id"),
        purpose=_require_str(raw_action, "purpose"),
        zone=_require_str(raw_action, "zone"),
        uncertainty=_require_str(raw_action, "uncertainty"),
        blast_radius=BlastRadiusDeclaration(
            writes=_optional_tuple(raw_blast, "writes"),
            reads=_optional_tuple(raw_blast, "reads"),
            authority_impact=_require_str(raw_blast, "authority_impact"),
            runtime_impact=_require_str(raw_blast, "runtime_impact"),
            state_impact=_require_str(raw_blast, "state_impact"),
            third_party_impact=_require_str(raw_blast, "third_party_impact"),
            scope=_require_str(raw_blast, "scope"),
            reversibility=_require_str(raw_blast, "reversibility"),
            rollback=_require_str(raw_blast, "rollback"),
            gate_level=_require_str(raw_blast, "gate_level"),
            promotion_path=_require_str(raw_blast, "promotion_path"),
            stop_conditions=_optional_tuple(raw_blast, "stop_conditions"),
        ),
        risk_budget=RiskBudget(
            max_writes=_optional_int(raw_budget, "max_writes"),
            allowed_paths=_optional_tuple(raw_budget, "allowed_paths"),
            allowed_authority_impact=_require_str(raw_budget, "allowed_authority_impact"),
            allowed_runtime_impact=_require_str(raw_budget, "allowed_runtime_impact"),
            max_irreversibility=_require_str(raw_budget, "max_irreversibility"),
            required_rollback_evidence=_require_str(raw_budget, "required_rollback_evidence"),
            human_approval_required=_optional_bool(raw_budget, "human_approval_required"),
        ),
    )


def load_readiness_manifest(path: str | Path) -> ReadinessManifest:
    manifest_path = Path(path)
    data = tomllib.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("manifest root must be a table")

    return ReadinessManifest(
        schema_version=_require_str(data, "schema_version"),
        generated_report=_require_str(data, "generated_report"),
        generated_trace=_optional_str(data, "generated_trace"),
        generator=_require_str(data, "generator"),
        renderer=_require_str(data, "renderer"),
        authority=_require_str(data, "authority"),
        state_change=_require_str(data, "state_change"),
        trigger=_require_str(data, "trigger"),
        sources=_load_sources(data),
        baseline=_load_baseline(data),
        action_proposal=_load_action(data),
    )


def _resolve_generated_path(root: str | Path, relative_path: str, field_name: str) -> Path:
    root_path = Path(root).resolve()
    candidate = (root_path / relative_path).resolve()
    try:
        relative = candidate.relative_to(root_path)
    except ValueError as exc:
        raise ValueError(f"{field_name} escapes root: {relative_path}") from exc

    if any(part.lower() == ".cerebro" for part in relative.parts):
        raise ValueError(f"{field_name} points into .cerebro: {relative_path}")
    return candidate


def resolve_generated_report_path(root: str | Path, manifest: ReadinessManifest) -> Path:
    return _resolve_generated_path(root, manifest.generated_report, "generated_report")


def resolve_generated_trace_path(root: str | Path, manifest: ReadinessManifest) -> Path:
    if manifest.generated_trace is None:
        raise ValueError("generated_trace is not declared")
    return _resolve_generated_path(root, manifest.generated_trace, "generated_trace")


def generate_readiness_report_from_manifest(root: str | Path, manifest_path: str | Path):
    manifest = load_readiness_manifest(manifest_path)
    return generate_readiness_report(
        root,
        manifest.sources,
        baseline=manifest.baseline,
        action_proposal=manifest.action_proposal,
    )
