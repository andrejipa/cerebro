from __future__ import annotations

import re

from .contract import (
    Readiness,
    ThirdPartyTriggerReview,
    ThirdPartyTriggerReviewFinding,
    ThirdPartyTriggerReviewInput,
)


_TARGET_PATH_RE = re.compile(r"target_path\s*=\s*[\"']([^\"']+)[\"']", re.IGNORECASE)
_TARGET_PATH_UNDER_RE = re.compile(
    r"(?:allowed\s+)?(?:third-party\s+project\s+files|target\s+files|target\s+reads|target\s+writes)\s+under\s+`([^`]+)`",
    re.IGNORECASE,
)
_ABSOLUTE_TARGET_PATH_RE = re.compile(
    r"`([A-Za-z]:\\[^`]+?\\(?:rpg_caminhada|Portal|escritorio|pessoais)[^`]*)`",
    re.IGNORECASE,
)
_SLICE_KIND_RE = re.compile(r"slice_kind\s*=\s*[\"']([^\"']+)[\"']", re.IGNORECASE)

_RUNTIME_BOUNDARY_TERMS = (
    "core/",
    "cli/",
    "extensions/",
    "core/schema.py",
    "state.json",
    "runtime gate",
    "claim graph",
    "source registration",
    "memory write",
)

_SOURCE_ROLE_TERMS = (
    "project_identity",
    "current_state",
    "continuity_delta",
    "decision_ledger",
    "next_work_map",
)


def review_third_party_trigger(review_input: ThirdPartyTriggerReviewInput) -> ThirdPartyTriggerReview:
    text = review_input.trigger_text
    normalized = text.lower()
    findings: list[ThirdPartyTriggerReviewFinding] = []

    target_path = _extract_target_path(text)
    slice_kind = _extract(_SLICE_KIND_RE, text)
    dogfood_value_present = "dogfood_value" in normalized
    proof_cost_declared = "proof_cost" in normalized
    source_roles_declared = all(term in normalized for term in _SOURCE_ROLE_TERMS)
    target_cerebro_handling_declared = _has_target_cerebro_handling(normalized)
    rollback_declared = "rollback" in normalized
    cleanup_declared = "cleanup" in normalized or "cleanup_required" in normalized
    stop_lines_declared = "stop conditions" in normalized or "stop_conditions" in normalized or "stop lines" in normalized
    forbidden_paths_declared = _has_forbidden_path_boundary(normalized)
    runtime_boundary_drift = _has_runtime_boundary_drift(normalized)
    consecutive_target_slice_risk = _classify_consecutive_risk(
        review_input.consecutive_target_mutating_slices
    )

    if not target_path:
        findings.append(_blocker("missing_target_path", "Third-party trigger must declare target_path."))

    if not slice_kind:
        findings.append(_blocker("missing_slice_kind", "Trigger must classify slice_kind."))
    elif slice_kind not in {"management_proof", "target_product_work", "both"}:
        findings.append(
            _blocker(
                "invalid_slice_kind",
                "slice_kind must be management_proof, target_product_work, or both.",
            )
        )

    if not dogfood_value_present:
        findings.append(
            _blocker(
                "missing_dogfood_value",
                "Trigger must explain what Cerebro learns from this target work.",
            )
        )

    if slice_kind == "target_product_work" and not dogfood_value_present:
        findings.append(
            _blocker(
                "blocked_role_drift",
                "Pure target product work without dogfood value is role drift.",
            )
        )

    if not proof_cost_declared:
        findings.append(_warning("missing_proof_cost", "Trigger should declare proof_cost."))

    if not rollback_declared:
        findings.append(_blocker("missing_rollback", "Trigger must declare rollback evidence."))

    if not cleanup_declared:
        findings.append(_warning("missing_cleanup", "Trigger should declare cleanup_required or cleanup plan."))

    if not stop_lines_declared:
        findings.append(_blocker("missing_stop_conditions", "Trigger must declare stop conditions."))

    if not forbidden_paths_declared:
        findings.append(
            _blocker(
                "missing_forbidden_paths",
                "Trigger must explicitly forbid Cerebro runtime and target .cerebro drift.",
            )
        )

    if review_input.target_has_cerebro and not target_cerebro_handling_declared:
        findings.append(
            _blocker(
                "blocked_target_cerebro_ambiguity",
                "Target has .cerebro/ but trigger does not classify handling.",
            )
        )

    if not source_roles_declared:
        findings.append(
            _warning(
                "missing_source_roles",
                "Trigger should declare source-set roles: project_identity, current_state, continuity_delta, decision_ledger, next_work_map.",
            )
        )

    if runtime_boundary_drift:
        findings.append(
            _blocker(
                "blocked_runtime_boundary",
                "Trigger appears to authorize runtime/Cerebro authority work.",
            )
        )

    if review_input.consecutive_target_mutating_slices >= 3:
        findings.append(
            _blocker(
                "consolidation_required",
                "Three or more consecutive target-mutating slices require Cerebro-side consolidation first.",
            )
        )

    readiness = _determine_readiness(findings)

    return ThirdPartyTriggerReview(
        trigger_id=review_input.trigger_id,
        target_path=target_path,
        slice_kind=slice_kind,
        dogfood_value_present=dogfood_value_present,
        proof_cost_declared=proof_cost_declared,
        source_roles_declared=source_roles_declared,
        target_cerebro_handling_declared=target_cerebro_handling_declared,
        rollback_declared=rollback_declared,
        cleanup_declared=cleanup_declared,
        stop_lines_declared=stop_lines_declared,
        forbidden_paths_declared=forbidden_paths_declared,
        consecutive_target_slice_risk=consecutive_target_slice_risk,
        readiness=readiness,
        findings=tuple(findings),
    )


def _extract(pattern: re.Pattern[str], text: str) -> str | None:
    match = pattern.search(text)
    return match.group(1) if match else None


def _extract_target_path(text: str) -> str | None:
    explicit = _extract(_TARGET_PATH_RE, text)
    if explicit:
        return _project_root_from_path(explicit)

    under_path = _extract(_TARGET_PATH_UNDER_RE, text)
    if under_path:
        return _project_root_from_path(under_path)

    absolute = _extract(_ABSOLUTE_TARGET_PATH_RE, text)
    if absolute:
        return _project_root_from_path(absolute)

    return None


def _project_root_from_path(path: str) -> str:
    cleaned = path.rstrip("\\/")
    for marker in ("rpg_caminhada", "Portal", "escritorio", "pessoais"):
        marker_index = cleaned.lower().find(marker.lower())
        if marker_index >= 0:
            return cleaned[: marker_index + len(marker)].rstrip("\\/")
    return cleaned


def _has_target_cerebro_handling(normalized: str) -> bool:
    return "target_cerebro_handling" in normalized or (
        ".cerebro" in normalized
        and any(term in normalized for term in ("preserve", "legacy", "classify", "canonical_current", "blocked"))
    )


def _has_forbidden_path_boundary(normalized: str) -> bool:
    has_path_boundary = any(
        term in normalized
        for term in (
            "core/",
            "cli/",
            "extensions/",
            ".cerebro/",
            "core/schema.py",
            "forbidden_cerebro_paths",
        )
    )
    has_prohibition = any(
        term in normalized
        for term in (
            "forbidden",
            "explicit prohibitions",
            "explicitly not authorized",
            "do not modify",
            "do not touch",
            "not authorize",
        )
    )
    return has_path_boundary and has_prohibition


def _has_runtime_boundary_drift(normalized: str) -> bool:
    if _has_forbidden_path_boundary(normalized):
        return False
    authority_terms = ("allowed files", "whitelist", "authorized", "allowed_target_paths")
    return any(term in normalized for term in _RUNTIME_BOUNDARY_TERMS) and any(
        marker in normalized for marker in authority_terms
    ) and "forbidden" not in normalized


def _classify_consecutive_risk(count: int) -> str:
    if count >= 3:
        return "consolidation_required"
    if count == 2:
        return "near_stop_line"
    return "low"


def _determine_readiness(findings: list[ThirdPartyTriggerReviewFinding]) -> Readiness:
    codes = {finding.code for finding in findings if finding.severity == "blocker"}

    if "blocked_runtime_boundary" in codes:
        return "blocked_runtime_boundary"
    if "blocked_target_cerebro_ambiguity" in codes:
        return "blocked_target_cerebro_ambiguity"
    if "blocked_role_drift" in codes:
        return "blocked_role_drift"
    if "consolidation_required" in codes:
        return "consolidation_required"
    if codes:
        return "needs_missing_fields"
    return "ready_for_human_review"


def _blocker(code: str, message: str) -> ThirdPartyTriggerReviewFinding:
    return ThirdPartyTriggerReviewFinding(code=code, severity="blocker", message=message)


def _warning(code: str, message: str) -> ThirdPartyTriggerReviewFinding:
    return ThirdPartyTriggerReviewFinding(code=code, severity="warning", message=message)
