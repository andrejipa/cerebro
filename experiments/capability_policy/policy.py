from __future__ import annotations

import json
import tomllib
from dataclasses import asdict, dataclass
from pathlib import PurePosixPath, Path
from typing import Iterable


class CapabilityPolicyError(ValueError):
    """Raised when a capability policy manifest or request is malformed."""


_DECISIONS = {"allow", "review_required", "deny"}
_NETWORK = {"denied", "review_required", "allowed"}
_SENSITIVITY = ("public", "internal", "sensitive", "secret")


@dataclass(frozen=True)
class CapabilityRule:
    rule_id: str
    decision: str
    argv_prefix: tuple[str, ...]
    path_scope: tuple[str, ...]
    max_data_sensitivity: str
    network_access: str
    approval_required: bool
    output_budget_kb: int
    retention: str
    rollback_expectation: str
    rationale: str


@dataclass(frozen=True)
class CapabilityRequest:
    request_id: str
    argv: tuple[str, ...]
    reads: tuple[str, ...] = ()
    writes: tuple[str, ...] = ()
    data_sensitivity: str = "internal"
    network_access: bool = False
    expected_output_kb: int = 0
    approval_present: bool = False


@dataclass(frozen=True)
class CapabilityAssessment:
    request_id: str
    matched_rule_id: str
    decision: str
    reasons: tuple[str, ...]
    warnings: tuple[str, ...]
    required_human_decision: str
    state_change: str = "none"
    authority: str = "non-authoritative; advisory capability policy only"
    advisory_allow_is_not_permission: bool = True
    must_not_execute_automatically: bool = True


def _required_str(table: dict, field: str) -> str:
    value = table.get(field)
    if not isinstance(value, str) or not value:
        raise CapabilityPolicyError(f"missing required string field: {field}")
    return value


def _optional_str(table: dict, field: str, default: str) -> str:
    value = table.get(field, default)
    if not isinstance(value, str) or not value:
        raise CapabilityPolicyError(f"{field} must be a non-empty string")
    return value


def _optional_bool(table: dict, field: str, default: bool) -> bool:
    value = table.get(field, default)
    if not isinstance(value, bool):
        raise CapabilityPolicyError(f"{field} must be a boolean")
    return value


def _optional_int(table: dict, field: str, default: int) -> int:
    value = table.get(field, default)
    if not isinstance(value, int) or value < 0:
        raise CapabilityPolicyError(f"{field} must be a non-negative integer")
    return value


def _as_str_tuple(value: object, *, field: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not value:
        raise CapabilityPolicyError(f"{field} must be a non-empty list")
    if not all(isinstance(item, str) and item for item in value):
        raise CapabilityPolicyError(f"{field} must contain only non-empty strings")
    return tuple(value)


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
        raise CapabilityPolicyError("manifest path escapes root") from exc
    if any(part.casefold() == ".cerebro" for part in resolved.parts):
        raise CapabilityPolicyError("manifest path may not live under .cerebro")
    return resolved


def _normalize_relative_path(value: str, *, field: str) -> str:
    normalized = value.replace("\\", "/").strip("/")
    if not normalized:
        raise CapabilityPolicyError(f"{field} must not be empty")
    path = PurePosixPath(normalized)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise CapabilityPolicyError(f"{field} must be a normalized relative path")
    return path.as_posix()


def _parse_rule(raw: dict) -> CapabilityRule:
    rule_id = _required_str(raw, "rule_id")
    decision = _required_str(raw, "decision")
    if decision not in _DECISIONS:
        raise CapabilityPolicyError(f"{rule_id}.decision must be one of {sorted(_DECISIONS)}")
    max_data_sensitivity = _optional_str(raw, "max_data_sensitivity", "internal")
    if max_data_sensitivity not in _SENSITIVITY:
        raise CapabilityPolicyError(f"{rule_id}.max_data_sensitivity is invalid")
    network_access = _optional_str(raw, "network_access", "denied")
    if network_access not in _NETWORK:
        raise CapabilityPolicyError(f"{rule_id}.network_access must be one of {sorted(_NETWORK)}")

    return CapabilityRule(
        rule_id=rule_id,
        decision=decision,
        argv_prefix=_as_str_tuple(raw.get("argv_prefix"), field=f"{rule_id}.argv_prefix"),
        path_scope=tuple(
            _normalize_relative_path(item, field=f"{rule_id}.path_scope")
            for item in _as_str_tuple(raw.get("path_scope"), field=f"{rule_id}.path_scope")
        ),
        max_data_sensitivity=max_data_sensitivity,
        network_access=network_access,
        approval_required=_optional_bool(raw, "approval_required", False),
        output_budget_kb=_optional_int(raw, "output_budget_kb", 64),
        retention=_optional_str(raw, "retention", "ephemeral"),
        rollback_expectation=_optional_str(raw, "rollback_expectation", "not_applicable"),
        rationale=_required_str(raw, "rationale"),
    )


def load_capability_manifest(path: str | Path, *, root: str | Path | None = None) -> tuple[CapabilityRule, ...]:
    manifest_path = _resolve_manifest_path(path, root=root)
    payload = tomllib.loads(manifest_path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "1":
        raise CapabilityPolicyError("schema_version must be '1'")
    raw_rules = payload.get("capability")
    if not isinstance(raw_rules, list) or not raw_rules:
        raise CapabilityPolicyError("manifest must contain at least one [[capability]]")

    rules = tuple(_parse_rule(raw) for raw in raw_rules)
    ids = [rule.rule_id for rule in rules]
    duplicates = sorted({rule_id for rule_id in ids if ids.count(rule_id) > 1})
    if duplicates:
        raise CapabilityPolicyError(f"duplicate rule_id: {', '.join(duplicates)}")
    return rules


def _argv_matches(argv: tuple[str, ...], prefix: tuple[str, ...]) -> bool:
    return len(argv) >= len(prefix) and argv[: len(prefix)] == prefix


def _path_in_scope(path: str, scopes: tuple[str, ...]) -> bool:
    normalized = _normalize_relative_path(path, field="request path")
    return any(normalized == scope or normalized.startswith(f"{scope.rstrip('/')}/") for scope in scopes)


def _request_paths(request: CapabilityRequest) -> tuple[str, ...]:
    return (*request.reads, *request.writes)


def _sensitivity_index(value: str) -> int:
    if value not in _SENSITIVITY:
        raise CapabilityPolicyError(f"invalid data_sensitivity: {value}")
    return _SENSITIVITY.index(value)


def _matched_rule(rules: Iterable[CapabilityRule], request: CapabilityRequest) -> CapabilityRule | None:
    candidates = [rule for rule in rules if _argv_matches(request.argv, rule.argv_prefix)]
    if not candidates:
        return None
    return sorted(candidates, key=lambda rule: (-len(rule.argv_prefix), rule.rule_id))[0]


def evaluate_capability_request(
    rules: Iterable[CapabilityRule],
    request: CapabilityRequest,
) -> CapabilityAssessment:
    if not request.request_id:
        raise CapabilityPolicyError("request_id is required")
    if not request.argv:
        raise CapabilityPolicyError("argv must not be empty")
    if request.expected_output_kb < 0:
        raise CapabilityPolicyError("expected_output_kb must be non-negative")

    rule = _matched_rule(rules, request)
    if rule is None:
        return CapabilityAssessment(
            request_id=request.request_id,
            matched_rule_id="none",
            decision="blocked",
            reasons=("no_matching_capability_rule",),
            warnings=(),
            required_human_decision="define_or_select_capability_rule",
        )

    reasons: list[str] = []
    warnings: list[str] = []
    decision = "advisory_allow"
    required_human_decision = "none"

    if rule.decision == "deny":
        decision = "blocked"
        reasons.append("capability_rule_denies_request")
        required_human_decision = "choose_different_capability"
    elif rule.decision == "review_required":
        decision = "review_required"
        reasons.append("capability_rule_requires_review")
        required_human_decision = "review_capability_request"

    for path in _request_paths(request):
        if not _path_in_scope(path, rule.path_scope):
            decision = "blocked"
            reasons.append(f"path_out_of_scope:{path}")
            required_human_decision = "review_path_scope"

    for path in request.writes:
        normalized = _normalize_relative_path(path, field="request write path")
        if any(part.casefold() == ".cerebro" for part in PurePosixPath(normalized).parts):
            decision = "blocked"
            reasons.append("cerebro_write_requires_runtime_authority")
            required_human_decision = "open_runtime_authority_trigger"

    if _sensitivity_index(request.data_sensitivity) > _sensitivity_index(rule.max_data_sensitivity):
        decision = "blocked"
        reasons.append("data_sensitivity_exceeds_capability")
        required_human_decision = "reduce_or_reclassify_data_scope"

    if request.network_access:
        if rule.network_access == "denied":
            decision = "blocked"
            reasons.append("network_access_denied_by_capability")
            required_human_decision = "open_network_boundary_review"
        elif rule.network_access == "review_required" and decision != "blocked":
            decision = "review_required"
            reasons.append("network_access_requires_review")
            required_human_decision = "review_network_use"

    if request.expected_output_kb > rule.output_budget_kb:
        decision = "blocked"
        reasons.append("output_budget_exceeded")
        required_human_decision = "reduce_output_or_raise_budget"

    if rule.approval_required and not request.approval_present and decision != "blocked":
        decision = "review_required"
        reasons.append("approval_required_but_missing")
        required_human_decision = "provide_human_approval"

    if not reasons:
        reasons.append("capability_request_within_declared_policy")

    if decision == "advisory_allow":
        warnings.append("advisory_allow_is_not_permission")

    return CapabilityAssessment(
        request_id=request.request_id,
        matched_rule_id=rule.rule_id,
        decision=decision,
        reasons=tuple(reasons),
        warnings=tuple(warnings),
        required_human_decision=required_human_decision,
    )


def render_capability_assessment_json(assessment: CapabilityAssessment) -> str:
    payload = asdict(assessment)
    payload["state_change"] = "none"
    payload["authority"] = assessment.authority
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def render_capability_assessment_markdown(assessment: CapabilityAssessment) -> str:
    return (
        "# Capability Policy Assessment\n\n"
        "- state_change: none\n"
        "- authority: non-authoritative; advisory capability policy only\n"
        "- advisory_allow_is_not_permission: true\n"
        "- must_not_execute_automatically: true\n\n"
        "## Request\n\n"
        f"- request_id: {assessment.request_id}\n"
        f"- matched_rule_id: {assessment.matched_rule_id}\n"
        f"- decision: {assessment.decision}\n"
        f"- required_human_decision: {assessment.required_human_decision}\n"
        f"- reasons: {', '.join(assessment.reasons) if assessment.reasons else 'none'}\n"
        f"- warnings: {', '.join(assessment.warnings) if assessment.warnings else 'none'}\n"
    )
