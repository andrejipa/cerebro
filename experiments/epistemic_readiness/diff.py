from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Mapping

from .trace import TRACE_SCHEMA_VERSION


TRACE_DIFF_SCHEMA_VERSION = "1"
TRACE_DIFF_AUTHORITY = "non-authoritative; advisory trace-diff evidence only"

_READINESS_SEVERITY = {
    "derived_experiment_allowed": 0,
    "advisory_report_allowed": 1,
    "propose_only": 2,
    "observe_only": 3,
    "no_action": 3,
    "human_approval_required": 4,
    "canonical_change_requires_trigger": 5,
    "blocked": 6,
}
_GATE_SEVERITY = {"G0": 0, "G1": 1, "G2": 2, "G3": 3, "G4": 4}
_BUDGET_SEVERITY = {"within_budget": 0, "exceeded": 1}


@dataclass(frozen=True)
class EntryChange:
    key: str
    changed_fields: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "changed_fields": list(self.changed_fields),
        }


@dataclass(frozen=True)
class FieldChange:
    field: str
    baseline: Any
    current: Any

    def to_dict(self) -> dict[str, Any]:
        return {
            "field": self.field,
            "baseline": self.baseline,
            "current": self.current,
        }


@dataclass(frozen=True)
class CollectionDiff:
    identity_basis: str
    added: tuple[str, ...]
    removed: tuple[str, ...]
    kept: tuple[str, ...]
    changed: tuple[EntryChange, ...]
    traceability_changed: tuple[EntryChange, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "identity_basis": self.identity_basis,
            "added": list(self.added),
            "removed": list(self.removed),
            "kept": list(self.kept),
            "changed": [change.to_dict() for change in self.changed],
            "traceability_changed": [change.to_dict() for change in self.traceability_changed],
        }


@dataclass(frozen=True)
class TraceDiff:
    baseline_label: str
    current_label: str
    source_reads: CollectionDiff
    candidates: CollectionDiff
    findings: CollectionDiff
    summary_changes: tuple[FieldChange, ...]
    risk_assessment_changes: tuple[FieldChange, ...]
    guardrail_changes: tuple[FieldChange, ...]
    regression_reasons: tuple[str, ...]
    state_change: str = "none"
    authority: str = TRACE_DIFF_AUTHORITY
    diff_role: str = "advisory replay comparison only"

    def __post_init__(self) -> None:
        if self.state_change != "none":
            raise ValueError("trace diffs must not change state")

    @property
    def has_regression(self) -> bool:
        return bool(self.regression_reasons)

    @property
    def advisory_readiness(self) -> str:
        return "human_review_recommended" if self.has_regression else "no_regression_observed"

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": TRACE_DIFF_SCHEMA_VERSION,
            "state_change": self.state_change,
            "authority": self.authority,
            "diff_role": self.diff_role,
            "baseline_label": self.baseline_label,
            "current_label": self.current_label,
            "advisory_readiness": self.advisory_readiness,
            "has_regression": self.has_regression,
            "regression_reasons": list(self.regression_reasons),
            "source_reads": self.source_reads.to_dict(),
            "candidates": self.candidates.to_dict(),
            "findings": self.findings.to_dict(),
            "summary_changes": [change.to_dict() for change in self.summary_changes],
            "risk_assessment_changes": [change.to_dict() for change in self.risk_assessment_changes],
            "guardrail_changes": [change.to_dict() for change in self.guardrail_changes],
            "boundary": {
                "may_suggest": [
                    "inspect trace drift",
                    "request human review",
                    "propose a future trigger",
                    "compare replay evidence",
                ],
                "must_not_apply": [
                    "mutate state",
                    "register sources",
                    "act as runtime gate",
                    "create canonical claim graph",
                    "promote or demote authority",
                    "treat trace diff as permission",
                ],
            },
        }


def load_decision_trace_json(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return _validate_trace_payload(payload)


def compare_decision_traces(
    baseline: Mapping[str, Any],
    current: Mapping[str, Any],
    *,
    baseline_label: str = "baseline",
    current_label: str = "current",
) -> TraceDiff:
    baseline_payload = _validate_trace_payload(baseline)
    current_payload = _validate_trace_payload(current)

    source_reads = _compare_collection(
        baseline_payload,
        current_payload,
        collection_key="source_reads",
        identity_key="path",
        identity_basis="path",
    )
    baseline_candidate_entries = _list(baseline_payload.get("candidates"), "candidates")
    current_candidate_entries = _list(current_payload.get("candidates"), "candidates")
    baseline_candidates, baseline_claim_keys = _candidate_entry_map(baseline_candidate_entries, "candidates")
    current_candidates, current_claim_keys = _candidate_entry_map(current_candidate_entries, "candidates")
    candidates = _compare_entry_maps(
        baseline_candidates,
        current_candidates,
        identity_basis="candidate_semantic_identity",
        traceability_fields=("claim_id", "semantic_id", "evidence_id", "evidence_span"),
    )
    findings = _compare_entry_maps(
        _finding_entry_map(
            _list(baseline_payload.get("findings"), "findings"),
            baseline_claim_keys,
            "findings",
        ),
        _finding_entry_map(
            _list(current_payload.get("findings"), "findings"),
            current_claim_keys,
            "findings",
        ),
        identity_basis="candidate_semantic_identity",
        traceability_fields=("claim_id", "semantic_id", "evidence_id"),
    )
    summary_changes = _compare_mapping(
        _mapping(baseline_payload.get("summary"), "summary"),
        _mapping(current_payload.get("summary"), "summary"),
    )
    risk_assessment_changes = _compare_optional_mapping(
        baseline_payload.get("risk_assessment"),
        current_payload.get("risk_assessment"),
        "risk_assessment",
    )
    guardrail_changes = _compare_mapping(
        _mapping(baseline_payload.get("guardrails"), "guardrails"),
        _mapping(current_payload.get("guardrails"), "guardrails"),
    )
    regression_reasons = _regression_reasons(
        baseline_payload,
        current_payload,
        summary_changes=summary_changes,
        risk_assessment_changes=risk_assessment_changes,
        guardrail_changes=guardrail_changes,
    )

    return TraceDiff(
        baseline_label=baseline_label,
        current_label=current_label,
        source_reads=source_reads,
        candidates=candidates,
        findings=findings,
        summary_changes=summary_changes,
        risk_assessment_changes=risk_assessment_changes,
        guardrail_changes=guardrail_changes,
        regression_reasons=regression_reasons,
    )


def render_trace_diff_json(diff: TraceDiff) -> str:
    return json.dumps(diff.to_dict(), indent=2, sort_keys=True) + "\n"


def render_trace_diff_markdown(diff: TraceDiff) -> str:
    lines = [
        "# Epistemic Readiness Trace Diff",
        "",
        "## Boundary",
        "",
        f"- state_change: {diff.state_change}",
        f"- authority: {diff.authority}",
        f"- diff_role: {diff.diff_role}",
        "- trace_diff_is_not_permission: true",
        "- trace_diff_is_not_authority: true",
        "- promotion_or_demotion_is_not_applied: true",
        "",
        "## Summary",
        "",
        f"- baseline_label: `{diff.baseline_label}`",
        f"- current_label: `{diff.current_label}`",
        f"- advisory_readiness: `{diff.advisory_readiness}`",
        f"- has_regression: `{str(diff.has_regression).lower()}`",
        "",
    ]
    if diff.regression_reasons:
        lines.extend(["## Regression Reasons", ""])
        lines.extend(f"- {reason}" for reason in diff.regression_reasons)
        lines.append("")

    _append_collection(lines, "Source Reads", diff.source_reads)
    _append_collection(lines, "Candidates", diff.candidates)
    _append_collection(lines, "Findings", diff.findings)
    _append_field_changes(lines, "Summary Changes", diff.summary_changes)
    _append_field_changes(lines, "Risk Assessment Changes", diff.risk_assessment_changes)
    _append_field_changes(lines, "Guardrail Changes", diff.guardrail_changes)

    lines.extend(
        [
            "## Must Not Apply",
            "",
            "- mutate state",
            "- register sources",
            "- act as runtime gate",
            "- create canonical claim graph",
            "- promote or demote authority",
            "- treat trace diff as permission",
            "",
        ]
    )
    return "\n".join(lines)


def _validate_trace_payload(payload: Mapping[str, Any] | Any) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError("decision trace payload must be a JSON object")
    result = dict(payload)
    if result.get("schema_version") != TRACE_SCHEMA_VERSION:
        raise ValueError(f"unsupported decision trace schema_version: {result.get('schema_version')}")
    if result.get("state_change") != "none":
        raise ValueError("decision trace must declare state_change = none")
    return result


def _mapping(value: Any, field_name: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} must be an object")
    return dict(value)


def _list(value: Any, field_name: str) -> list[Any]:
    if not isinstance(value, list):
        raise ValueError(f"{field_name} must be a list")
    return value


def _entry_map(entries: list[Any], identity_key: str, collection_key: str) -> dict[str, dict[str, Any]]:
    mapped: dict[str, dict[str, Any]] = {}
    for entry in entries:
        if not isinstance(entry, Mapping):
            raise ValueError(f"{collection_key} entries must be objects")
        key = entry.get(identity_key)
        if not isinstance(key, str) or not key:
            raise ValueError(f"{collection_key} entries must include {identity_key}")
        if key in mapped:
            raise ValueError(f"duplicate {identity_key} in {collection_key}: {key}")
        mapped[key] = dict(entry)
    return mapped


def _candidate_entry_map(
    entries: list[Any],
    collection_key: str,
) -> tuple[dict[str, dict[str, Any]], dict[str, str]]:
    mapped: dict[str, dict[str, Any]] = {}
    claim_keys: dict[str, str] = {}
    counters: dict[str, int] = {}
    for entry in entries:
        if not isinstance(entry, Mapping):
            raise ValueError(f"{collection_key} entries must be objects")
        claim_id = entry.get("claim_id")
        if not isinstance(claim_id, str) or not claim_id:
            raise ValueError(f"{collection_key} entries must include claim_id")
        candidate = dict(entry)
        semantic_key = _candidate_semantic_key(candidate)
        counters[semantic_key] = counters.get(semantic_key, 0) + 1
        key = semantic_key if counters[semantic_key] == 1 else f"{semantic_key}#{counters[semantic_key]}"
        mapped[key] = candidate
        claim_keys[claim_id] = key
    return mapped, claim_keys


def _finding_entry_map(
    entries: list[Any],
    claim_keys: Mapping[str, str],
    collection_key: str,
) -> dict[str, dict[str, Any]]:
    mapped: dict[str, dict[str, Any]] = {}
    fallback_counters: dict[str, int] = {}
    for entry in entries:
        if not isinstance(entry, Mapping):
            raise ValueError(f"{collection_key} entries must be objects")
        claim_id = entry.get("claim_id")
        if not isinstance(claim_id, str) or not claim_id:
            raise ValueError(f"{collection_key} entries must include claim_id")
        finding = dict(entry)
        key = claim_keys.get(claim_id)
        if key is None:
            fallback_counters[claim_id] = fallback_counters.get(claim_id, 0) + 1
            key = claim_id if fallback_counters[claim_id] == 1 else f"{claim_id}#{fallback_counters[claim_id]}"
        mapped[key] = finding
    return mapped


def _candidate_semantic_key(entry: Mapping[str, Any]) -> str:
    parts = [
        entry.get("source_path"),
        entry.get("subject"),
        entry.get("predicate"),
        entry.get("object"),
        entry.get("polarity"),
        entry.get("modality"),
        entry.get("extraction_basis"),
    ]
    return " | ".join(str(part) for part in parts)


def _compare_collection(
    baseline: Mapping[str, Any],
    current: Mapping[str, Any],
    *,
    collection_key: str,
    identity_key: str,
    identity_basis: str,
) -> CollectionDiff:
    baseline_entries = _entry_map(_list(baseline.get(collection_key), collection_key), identity_key, collection_key)
    current_entries = _entry_map(_list(current.get(collection_key), collection_key), identity_key, collection_key)
    return _compare_entry_maps(baseline_entries, current_entries, identity_basis=identity_basis)


def _compare_entry_maps(
    baseline_entries: Mapping[str, Mapping[str, Any]],
    current_entries: Mapping[str, Mapping[str, Any]],
    *,
    identity_basis: str,
    traceability_fields: tuple[str, ...] = (),
) -> CollectionDiff:
    baseline_keys = set(baseline_entries)
    current_keys = set(current_entries)
    kept = tuple(sorted(baseline_keys & current_keys))
    changed: list[EntryChange] = []
    traceability_changed: list[EntryChange] = []
    traceability_field_set = set(traceability_fields)
    for key in kept:
        changed_field_set = {
            field
            for field in set(baseline_entries[key]) | set(current_entries[key])
            if baseline_entries[key].get(field) != current_entries[key].get(field)
        }
        fields = tuple(sorted(changed_field_set - traceability_field_set))
        traceability_fields_changed = tuple(sorted(changed_field_set & traceability_field_set))
        if traceability_fields_changed:
            traceability_changed.append(EntryChange(key=key, changed_fields=traceability_fields_changed))
        if fields:
            changed.append(EntryChange(key=key, changed_fields=fields))

    return CollectionDiff(
        identity_basis=identity_basis,
        added=tuple(sorted(current_keys - baseline_keys)),
        removed=tuple(sorted(baseline_keys - current_keys)),
        kept=kept,
        changed=tuple(changed),
        traceability_changed=tuple(traceability_changed),
    )


def _compare_mapping(baseline: Mapping[str, Any], current: Mapping[str, Any]) -> tuple[FieldChange, ...]:
    changes: list[FieldChange] = []
    for field in sorted(set(baseline) | set(current)):
        if baseline.get(field) != current.get(field):
            changes.append(FieldChange(field=field, baseline=baseline.get(field), current=current.get(field)))
    return tuple(changes)


def _compare_optional_mapping(baseline: Any, current: Any, field_name: str) -> tuple[FieldChange, ...]:
    if baseline is None and current is None:
        return ()
    if baseline is None:
        return (FieldChange(field=field_name, baseline=None, current=current),)
    if current is None:
        return (FieldChange(field=field_name, baseline=baseline, current=None),)
    return _compare_mapping(_mapping(baseline, field_name), _mapping(current, field_name))


def _regression_reasons(
    baseline: Mapping[str, Any],
    current: Mapping[str, Any],
    *,
    summary_changes: tuple[FieldChange, ...],
    risk_assessment_changes: tuple[FieldChange, ...],
    guardrail_changes: tuple[FieldChange, ...],
) -> tuple[str, ...]:
    reasons: list[str] = []
    baseline_summary = _mapping(baseline.get("summary"), "summary")
    current_summary = _mapping(current.get("summary"), "summary")
    _append_count_regression(reasons, baseline_summary, current_summary, "blocked_count")
    _append_count_regression(reasons, baseline_summary, current_summary, "insufficient_count")

    baseline_readiness = baseline_summary.get("action_readiness")
    current_readiness = current_summary.get("action_readiness")
    if _severity(current_readiness, _READINESS_SEVERITY) > _severity(baseline_readiness, _READINESS_SEVERITY):
        reasons.append(f"action_readiness worsened: {baseline_readiness} -> {current_readiness}")

    baseline_risk = baseline.get("risk_assessment")
    current_risk = current.get("risk_assessment")
    if baseline_risk is None and current_risk is not None:
        current_risk = _mapping(current_risk, "risk_assessment")
        if current_risk.get("budget_status") == "exceeded":
            reasons.append("risk budget newly exceeded")
    elif baseline_risk is not None and current_risk is not None:
        baseline_risk = _mapping(baseline_risk, "risk_assessment")
        current_risk = _mapping(current_risk, "risk_assessment")
        if _severity(current_risk.get("budget_status"), _BUDGET_SEVERITY) > _severity(
            baseline_risk.get("budget_status"), _BUDGET_SEVERITY
        ):
            reasons.append(
                "risk budget status worsened: "
                f"{baseline_risk.get('budget_status')} -> {current_risk.get('budget_status')}"
            )
        if _severity(current_risk.get("required_gate_level"), _GATE_SEVERITY) > _severity(
            baseline_risk.get("required_gate_level"), _GATE_SEVERITY
        ):
            reasons.append(
                "required gate level increased: "
                f"{baseline_risk.get('required_gate_level')} -> {current_risk.get('required_gate_level')}"
            )
        if not bool(baseline_risk.get("human_approval_required")) and bool(
            current_risk.get("human_approval_required")
        ):
            reasons.append("human approval became required")
        if _severity(current_risk.get("action_readiness"), _READINESS_SEVERITY) > _severity(
            baseline_risk.get("action_readiness"), _READINESS_SEVERITY
        ):
            reasons.append(
                "risk action_readiness worsened: "
                f"{baseline_risk.get('action_readiness')} -> {current_risk.get('action_readiness')}"
            )

    for change in guardrail_changes:
        if change.baseline is True and change.current is not True:
            reasons.append(f"guardrail weakened: {change.field}")

    # Keep these parameters part of the signature so callers can inspect the
    # exact evidence that produced each advisory reason without relying on
    # hidden global state or later recomputation.
    _ = summary_changes, risk_assessment_changes
    return tuple(reasons)


def _append_count_regression(
    reasons: list[str],
    baseline_summary: Mapping[str, Any],
    current_summary: Mapping[str, Any],
    field: str,
) -> None:
    baseline_value = _int_or_zero(baseline_summary.get(field))
    current_value = _int_or_zero(current_summary.get(field))
    if current_value > baseline_value:
        reasons.append(f"{field} increased: {baseline_value} -> {current_value}")


def _int_or_zero(value: Any) -> int:
    return value if isinstance(value, int) else 0


def _severity(value: Any, ranking: Mapping[str, int]) -> int:
    return ranking.get(value, -1) if isinstance(value, str) else -1


def _append_collection(lines: list[str], title: str, diff: CollectionDiff) -> None:
    lines.extend([f"## {title}", ""])
    lines.append(f"- identity_basis: `{diff.identity_basis}`")
    lines.append(f"- added: `{len(diff.added)}`")
    lines.append(f"- removed: `{len(diff.removed)}`")
    lines.append(f"- kept: `{len(diff.kept)}`")
    lines.append(f"- changed: `{len(diff.changed)}`")
    lines.append(f"- traceability_changed: `{len(diff.traceability_changed)}`")
    if diff.added:
        lines.append(f"- added_keys: `{', '.join(diff.added)}`")
    if diff.removed:
        lines.append(f"- removed_keys: `{', '.join(diff.removed)}`")
    if diff.changed:
        changed = "; ".join(f"{change.key} ({', '.join(change.changed_fields)})" for change in diff.changed)
        lines.append(f"- changed_keys: `{changed}`")
    if diff.traceability_changed:
        changed = "; ".join(
            f"{change.key} ({', '.join(change.changed_fields)})" for change in diff.traceability_changed
        )
        lines.append(f"- traceability_changed_keys: `{changed}`")
    lines.append("")


def _append_field_changes(lines: list[str], title: str, changes: tuple[FieldChange, ...]) -> None:
    lines.extend([f"## {title}", ""])
    if not changes:
        lines.extend(["- none", ""])
        return
    for change in changes:
        lines.append(f"- `{change.field}`: `{change.baseline}` -> `{change.current}`")
    lines.append("")
