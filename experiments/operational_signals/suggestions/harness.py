"""Evaluation harness for the derived tripwire ruleset.

Loads the labelled dataset, runs a rule against each case, and reports
precision / recall / F1 plus a conservative verdict. The harness is
deterministic: it injects a fixed timestamp so ids and timestamps do
not drift between runs.
"""

from __future__ import annotations

import inspect
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
import tomllib

from . import AUTHORITY, SCHEMA_VERSION
from .rules import (
    Suggestion,
    detect_stale_system_state,
    suggestion_as_dict,
)


DEFAULT_DATASET_PATH = Path(__file__).with_name("dataset.toml")

FIXED_EVAL_TIMESTAMP = datetime(2026, 4, 20, 0, 0, 0, tzinfo=timezone.utc)

ALLOWED_LABELS = {"positive", "negative"}
ALLOWED_EXPECTED_CONFIDENCE = {"low", "medium", "high"}

# Verdict thresholds. Precision has priority because the cost of noise
# is much higher than the cost of missing a borderline case.
ACCEPT_PRECISION = 0.70
ACCEPT_RECALL = 0.60
ITERATE_PRECISION = 0.60


class DatasetError(ValueError):
    """Raised when the dataset payload is malformed."""


def load_dataset(path: str | Path | None = None) -> list[dict[str, Any]]:
    dataset_path = Path(path) if path is not None else DEFAULT_DATASET_PATH
    with dataset_path.open("rb") as handle:
        payload = tomllib.load(handle)
    if str(payload.get("schema_version")) != SCHEMA_VERSION:
        raise DatasetError(f"unsupported schema_version: {payload.get('schema_version')!r}")
    cases = payload.get("case", [])
    if not isinstance(cases, list) or not cases:
        raise DatasetError("dataset must contain a non-empty [[case]] array")

    normalized: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for raw in cases:
        case = _normalize_case(raw)
        if case["id"] in seen_ids:
            raise DatasetError(f"duplicate case id: {case['id']}")
        seen_ids.add(case["id"])
        normalized.append(case)
    return normalized


def _require_non_empty_string(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise DatasetError(f"{field_name} must be a non-empty string")
    return value


def _normalize_case(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise DatasetError("each case must be a table")
    case_id = _require_non_empty_string(raw.get("id"), "id")
    label = _require_non_empty_string(raw.get("label"), "label")
    if label not in ALLOWED_LABELS:
        raise DatasetError(f"unsupported label for {case_id}: {label!r}")
    label_reason = _require_non_empty_string(raw.get("label_reason"), "label_reason")
    text_value = raw.get("text")
    if text_value is not None and (not isinstance(text_value, str) or not text_value.strip()):
        raise DatasetError(f"{case_id}: text must be a non-empty string when provided")
    expected_confidence = raw.get("expected_confidence")
    if expected_confidence is not None:
        if label != "positive":
            raise DatasetError(f"{case_id}: expected_confidence is only valid for positive cases")
        if expected_confidence not in ALLOWED_EXPECTED_CONFIDENCE:
            raise DatasetError(f"{case_id}: unsupported expected_confidence {expected_confidence!r}")
    exports_text = raw.get("exports_text")
    if exports_text is not None and not isinstance(exports_text, str):
        raise DatasetError(f"{case_id}: exports_text must be a string")
    surface_fields: dict[str, str] = {}
    for field in ("readme_text", "system_state_text", "opportunity_map_text", "phase_closure_text"):
        value = raw.get(field)
        if value is not None and not isinstance(value, str):
            raise DatasetError(f"{case_id}: {field} must be a string")
        surface_fields[field] = value if isinstance(value, str) else ""
    if not isinstance(text_value, str) or not text_value.strip():
        if not any(value.strip() for value in surface_fields.values()):
            raise DatasetError(f"{case_id}: text or at least one *_text field is required")
    return {
        "id": case_id,
        "label": label,
        "label_reason": label_reason.strip(),
        "text": text_value if isinstance(text_value, str) else "",
        "expected_confidence": expected_confidence,
        "exports_text": exports_text if isinstance(exports_text, str) else "",
        **surface_fields,
    }


RuleCallable = Callable[..., "Suggestion | None"]


def _apply_rule(rule: RuleCallable, case: dict[str, Any]) -> "Suggestion | None":
    sig = inspect.signature(rule)
    if "case" in sig.parameters:
        return rule(case=case, now=FIXED_EVAL_TIMESTAMP)
    return rule(
        source_artifact=case["id"],
        text=case["text"],
        project_context="dataset",
        now=FIXED_EVAL_TIMESTAMP,
    )


def evaluate_dataset(
    rule: RuleCallable = detect_stale_system_state,
    dataset: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    cases = dataset if dataset is not None else load_dataset()
    tp = fp = tn = fn = 0
    confidence_matches = 0
    confidence_required = 0
    per_case: list[dict[str, Any]] = []

    for case in cases:
        expected_positive = case["label"] == "positive"
        suggestion = _apply_rule(rule, case)
        actual_positive = suggestion is not None
        outcome = _outcome_label(expected_positive, actual_positive)

        if outcome == "tp":
            tp += 1
        elif outcome == "fp":
            fp += 1
        elif outcome == "tn":
            tn += 1
        else:
            fn += 1

        confidence_expected = case.get("expected_confidence")
        confidence_actual = suggestion.confidence if suggestion is not None else None
        if confidence_expected is not None:
            confidence_required += 1
            if confidence_actual == confidence_expected:
                confidence_matches += 1

        per_case.append(
            {
                "id": case["id"],
                "label": case["label"],
                "label_reason": case["label_reason"],
                "expected_suggestion": expected_positive,
                "actual_suggestion": actual_positive,
                "outcome": outcome,
                "expected_confidence": confidence_expected,
                "actual_confidence": confidence_actual,
                "suggestion": suggestion_as_dict(suggestion) if suggestion is not None else None,
            }
        )

    total = tp + fp + tn + fn
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0

    metrics = {
        "total_cases": total,
        "tp": tp,
        "fp": fp,
        "tn": tn,
        "fn": fn,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "confidence_checked": confidence_required,
        "confidence_match_rate": (
            round(confidence_matches / confidence_required, 4)
            if confidence_required
            else None
        ),
    }
    verdict = _verdict(precision, recall)

    return {
        "authority": AUTHORITY,
        "non_authoritative": True,
        "read_only": True,
        "schema_version": SCHEMA_VERSION,
        "evaluated_at": FIXED_EVAL_TIMESTAMP.isoformat().replace("+00:00", "Z"),
        "rule": rule.__name__,
        "thresholds": {
            "accept_precision": ACCEPT_PRECISION,
            "accept_recall": ACCEPT_RECALL,
            "iterate_precision": ITERATE_PRECISION,
        },
        "metrics": metrics,
        "verdict": verdict,
        "per_case": per_case,
    }


def _outcome_label(expected_positive: bool, actual_positive: bool) -> str:
    if expected_positive and actual_positive:
        return "tp"
    if expected_positive and not actual_positive:
        return "fn"
    if (not expected_positive) and actual_positive:
        return "fp"
    return "tn"


def _verdict(precision: float, recall: float) -> dict[str, Any]:
    if precision >= ACCEPT_PRECISION and recall >= ACCEPT_RECALL:
        classification = "accept_for_staged_promotion"
        rationale = (
            "precision and recall clear the conservative acceptance bar; "
            "rule is safe for opt-in derived use pending a second tripwire "
            "before any wider adoption"
        )
    elif precision >= ITERATE_PRECISION:
        classification = "iterate"
        rationale = (
            "precision is acceptable but recall or confidence signal is not "
            "strong enough for staged promotion; needs dataset expansion or "
            "threshold tuning before use"
        )
    else:
        classification = "reject"
        rationale = (
            "precision below the iterate threshold; rule is not safe for "
            "derived use and should not be promoted"
        )
    return {"classification": classification, "rationale": rationale}
