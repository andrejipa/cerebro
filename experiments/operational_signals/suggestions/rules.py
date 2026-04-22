"""Derived tripwire rules for operational insufficiency suggestions.

Each rule is a pure function that inspects a static text artifact and
returns an optional `Suggestion`. Rules never read canonical runtime
state, never touch `.cerebro/`, and never decide insufficiency — they
only propose a record that a human must review.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
from pathlib import Path
import re
from typing import Any

from . import AUTHORITY, SCHEMA_VERSION


FAILURE_MODES = {
    "CONTEXT_NOT_FOUND",
    "CONTEXT_AMBIGUOUS",
    "STALE_INFORMATION",
    "INSUFFICIENT_EXPORT_SURFACE",
}
CONFIDENCE_LEVELS = {"low", "medium", "high"}
CANONICAL_SCOPE = Path("docs/operations")
REPO_ROOT = Path(__file__).resolve().parents[3]

SUITE_RESULT_RE = re.compile(
    r"Last suite result:\s*`?(\d+)`?\s*tests",
    re.IGNORECASE,
)
CURRENT_SECTION_RE = re.compile(
    r"^#+\s*Current Snapshot\b",
    re.IGNORECASE | re.MULTILINE,
)
GATE_SECTION_RE = re.compile(
    r"^#+\s*Gate Status\b",
    re.IGNORECASE | re.MULTILINE,
)
REQUIRED_EXPORT_ANCHORS_RE = re.compile(
    r"^#+\s*Required Export Anchors\b",
    re.IGNORECASE | re.MULTILINE,
)
BULLET_LINE_RE = re.compile(r"^\s*-\s*(.+?)\s*$", re.MULTILINE)
MARKDOWN_LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
SURFACE_TEXT_FIELDS = (
    "system_state_text",
    "opportunity_map_text",
)
SUPERCEDES_ALLOWED_EXTENSIONS = {".md", ".txt"}
SUPERCEDES_OUT_OF_SCOPE_FRAGMENTS = (
    "/core/",
    "/cli/",
    "/tests/",
    "/__pycache__/",
    "/experiments/operational_signals/suggestions/",
)
SUPERCEDES_ASSIGNMENT_RE = re.compile(r"\bsupersedes=[^\s;|]+", re.IGNORECASE)
STALE_CONSOLIDATION_RE = re.compile(
    r"\bstale_parallel_approach_consolidation_record\b",
    re.IGNORECASE,
)
WINNER_SIGNAL_RE = re.compile(r"\bwinner=", re.IGNORECASE)
RATIONALE_SIGNAL_RE = re.compile(r"\b(?:decision|basis):", re.IGNORECASE)
FENCED_CODE_BLOCK_RE = re.compile(r"```.*?```", re.DOTALL)
INLINE_CODE_SPAN_RE = re.compile(r"`[^`\n]+`")

# Conservative thresholds. Anything smaller is treated as noise because
# single-commit churn can move the live suite count by a small delta.
MIN_ABSOLUTE_DRIFT = 5
MEDIUM_CONFIDENCE_DRIFT = 10
HIGH_CONFIDENCE_DRIFT = 50
MIN_ABSOLUTE_BROKEN = 1
MIN_ABSOLUTE_MECHANICAL_SUPERSEDES = 1


@dataclass(frozen=True)
class Suggestion:
    id: str
    timestamp: str
    source_artifact: str
    project_context: str
    task_description: str
    suggested_failure_mode: str
    supporting_signals: tuple[str, ...]
    operational_cost_estimate: dict[str, int]
    confidence: str
    reason_flags: tuple[str, ...]
    human_review_required: bool = True
    authority: str = AUTHORITY
    schema_version: str = SCHEMA_VERSION
    notes: str = ""


@dataclass(frozen=True)
class SupersedesHit:
    token: str
    missing_context: tuple[str, ...]


@dataclass(frozen=True)
class SupersedesAnalysis:
    state: str
    ambiguous_hits: tuple[SupersedesHit, ...]


def _first_suite_count(section_text: str) -> int | None:
    match = SUITE_RESULT_RE.search(section_text)
    if match is None:
        return None
    return int(match.group(1))


def extract_suite_numbers_by_section(text: str) -> dict[str, int]:
    """Extract the first `Last suite result` count for each recognised section.

    Only the first match inside each section is used. Sections that are
    absent or do not contain a match are omitted from the result.
    """
    if not isinstance(text, str):
        raise TypeError("text must be a string")

    markers: list[tuple[str, int]] = []
    current_match = CURRENT_SECTION_RE.search(text)
    gate_match = GATE_SECTION_RE.search(text)
    if current_match is not None:
        markers.append(("current_snapshot", current_match.start()))
    if gate_match is not None:
        markers.append(("gate_status", gate_match.start()))
    markers.sort(key=lambda item: item[1])

    result: dict[str, int] = {}
    for index, (section_name, start) in enumerate(markers):
        end = markers[index + 1][1] if index + 1 < len(markers) else len(text)
        count = _first_suite_count(text[start:end])
        if count is not None:
            result[section_name] = count
    return result


def classify_confidence(abs_diff: int) -> str:
    if abs_diff >= HIGH_CONFIDENCE_DRIFT:
        return "high"
    if abs_diff >= MEDIUM_CONFIDENCE_DRIFT:
        return "medium"
    if abs_diff >= MIN_ABSOLUTE_DRIFT:
        return "low"
    raise ValueError("classify_confidence requires a drift >= MIN_ABSOLUTE_DRIFT")


def _normalize_search_text(text: str) -> str:
    lowered = text.lower()
    lowered = re.sub(r"[^a-z0-9]+", " ", lowered)
    return " ".join(lowered.split())


def _normalized_artifact_path(source_artifact: str) -> str:
    normalized = Path(source_artifact).as_posix().replace("\\", "/").lower()
    return normalized if normalized.startswith("/") else f"/{normalized}"


def _id_fragment(value: str) -> str:
    lowered = value.lower()
    lowered = re.sub(r"[^a-z0-9]+", "-", lowered).strip("-")
    return lowered[:24] or "artifact"


def _stable_artifact_digest(value: str) -> str:
    return hashlib.sha1(value.lower().encode("utf-8")).hexdigest()[:8]


def extract_required_export_anchors(text: str) -> tuple[str, ...]:
    """Extract a conservative list of required export anchors from a
    markdown section headed `## Required Export Anchors`.

    Only bullet items inside that section count. Prose mentions and
    free-form lists are ignored deliberately to avoid optimistic parsing.
    """
    if not isinstance(text, str):
        raise TypeError("text must be a string")

    match = REQUIRED_EXPORT_ANCHORS_RE.search(text)
    if match is None:
        return ()

    next_heading = re.search(r"^#+\s+", text[match.end() :], re.MULTILINE)
    end = match.end() + next_heading.start() if next_heading is not None else len(text)
    section_text = text[match.end() : end]
    anchors = [
        " ".join(item.strip().split())
        for item in BULLET_LINE_RE.findall(section_text)
        if item.strip()
    ]
    return tuple(anchors)


def _anchor_matches_exports(anchor: str, exports_text: str) -> bool:
    normalized_anchor = _normalize_search_text(anchor)
    normalized_exports = _normalize_search_text(exports_text)
    if not normalized_anchor or not normalized_exports:
        return False
    return normalized_anchor in normalized_exports


def _broken_ref_confidence(broken_count: int) -> str:
    if broken_count >= 4:
        return "high"
    if broken_count >= 2:
        return "medium"
    if broken_count >= MIN_ABSOLUTE_BROKEN:
        return "low"
    raise ValueError("broken_count must be >= MIN_ABSOLUTE_BROKEN")


def extract_current_surface_sources(case: dict[str, Any]) -> dict[str, str]:
    return {
        name: text
        for name in SURFACE_TEXT_FIELDS
        if isinstance((text := case.get(name, "")), str) and text.strip()
    }


def extract_current_surface_counts(case: dict[str, Any]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for name, text in extract_current_surface_sources(case).items():
        count = _first_suite_count(text)
        if count is not None:
            counts[name] = count
    return counts


def _is_in_canonical_scope(source_artifact: str) -> bool:
    normalized = _normalized_artifact_path(source_artifact)
    source_parts = [part for part in normalized.strip("/").split("/") if part]
    scope_parts = [part for part in CANONICAL_SCOPE.as_posix().lower().split("/") if part]
    span = len(scope_parts)
    return any(source_parts[index : index + span] == scope_parts for index in range(len(source_parts) - span + 1))


def _is_supersedes_operator_facing_scope(source_artifact: str, text: str) -> bool:
    if not isinstance(source_artifact, str) or not source_artifact.strip():
        return False
    if not isinstance(text, str) or not text.strip():
        return False
    normalized_path = _normalized_artifact_path(source_artifact)
    if Path(source_artifact).suffix.lower() not in SUPERCEDES_ALLOWED_EXTENSIONS:
        return False
    return not any(fragment in normalized_path for fragment in SUPERCEDES_OUT_OF_SCOPE_FRAGMENTS)


def _strip_non_operator_markup(text: str) -> str:
    without_blocks = FENCED_CODE_BLOCK_RE.sub("\n", text)
    return INLINE_CODE_SPAN_RE.sub("", without_blocks)


def _window_with_next_non_empty_lines(lines: list[str], start: int, count: int = 2) -> tuple[str, ...]:
    window = [lines[start].strip()]
    for candidate in lines[start + 1 :]:
        stripped = candidate.strip()
        if not stripped:
            continue
        window.append(stripped)
        if len(window) == count + 1:
            break
    return tuple(window)


def _mechanical_supersedes_tokens(line: str) -> tuple[str, ...]:
    return tuple(
        [
            *(match.group(0) for match in SUPERCEDES_ASSIGNMENT_RE.finditer(line)),
            *(match.group(0) for match in STALE_CONSOLIDATION_RE.finditer(line)),
        ]
    )


def analyze_supersedes_mechanical_metadata(
    *, source_artifact: str, text: str
) -> SupersedesAnalysis:
    if not _is_supersedes_operator_facing_scope(source_artifact, text):
        return SupersedesAnalysis(state="out_of_scope", ambiguous_hits=())

    searchable_text = _strip_non_operator_markup(text)
    lines = searchable_text.splitlines()
    ambiguous_hits: list[SupersedesHit] = []
    for index, line in enumerate(lines):
        tokens = _mechanical_supersedes_tokens(line)
        if not tokens:
            continue
        window_text = "\n".join(_window_with_next_non_empty_lines(lines, index))
        has_winner = WINNER_SIGNAL_RE.search(window_text) is not None
        has_rationale = RATIONALE_SIGNAL_RE.search(window_text) is not None
        if has_winner and has_rationale:
            continue
        missing_context = []
        if not has_winner:
            missing_context.append("winner")
        if not has_rationale:
            missing_context.append("rationale")
        ambiguous_hits.extend(
            SupersedesHit(token=token, missing_context=tuple(missing_context))
            for token in tokens
        )

    if ambiguous_hits:
        return SupersedesAnalysis(
            state="in_scope_mechanical_only",
            ambiguous_hits=tuple(ambiguous_hits),
        )
    return SupersedesAnalysis(state="in_scope_contextualized", ambiguous_hits=())


def _supersedes_confidence(ambiguous_hits: tuple[SupersedesHit, ...]) -> str:
    if len(ambiguous_hits) < MIN_ABSOLUTE_MECHANICAL_SUPERSEDES:
        raise ValueError(
            "ambiguous_hits must contain at least MIN_ABSOLUTE_MECHANICAL_SUPERSEDES items"
        )
    stale_hits = [
        hit
        for hit in ambiguous_hits
        if STALE_CONSOLIDATION_RE.fullmatch(hit.token) is not None
    ]
    if len(ambiguous_hits) >= 3 or any(
        {"winner", "rationale"}.issubset(set(hit.missing_context)) for hit in stale_hits
    ):
        return "high"
    if len(ambiguous_hits) >= 2 or stale_hits:
        return "medium"
    return "low"


def _normalize_markdown_target(target: str) -> str | None:
    normalized = target.strip()
    if not normalized:
        return None
    if normalized.startswith(("http://", "https://", "mailto:", "#")):
        return None
    if normalized.startswith("<") and normalized.endswith(">"):
        normalized = normalized[1:-1].strip()
    normalized = re.sub(r"#.*$", "", normalized)
    normalized = re.sub(r":\d+$", "", normalized)
    normalized = normalized.replace("%20", " ").strip()
    if re.match(r"^/[A-Za-z]:/", normalized):
        normalized = normalized[1:]
    return normalized or None


def _resolve_markdown_target(source_artifact: str, target: str) -> Path | None:
    normalized = _normalize_markdown_target(target)
    if normalized is None:
        return None
    target_path = Path(normalized)
    if target_path.is_absolute():
        return target_path
    return Path(source_artifact).parent / target_path


def _target_exists(path: Path) -> bool:
    if path.is_absolute():
        return path.exists()
    return (REPO_ROOT / path).exists()


def detect_broken_canonical_refs(
    *,
    source_artifact: str,
    text: str,
    project_context: str = "cerebro",
    now: datetime | None = None,
) -> Suggestion | None:
    """Emit `CONTEXT_NOT_FOUND` when a markdown artifact inside the
    canonical operations surface points to a local path that does not exist.

    The rule is intentionally narrow:
    - only markdown links are inspected
    - only source artifacts under `docs/operations/` are in scope
    - only local path existence is checked
    """
    if not _is_in_canonical_scope(source_artifact):
        return None

    broken: list[tuple[str, str]] = []
    for link_text, raw_target in MARKDOWN_LINK_RE.findall(text):
        resolved = _resolve_markdown_target(source_artifact, raw_target)
        if resolved is None:
            continue
        if not _target_exists(resolved):
            broken.append((link_text, resolved.as_posix()))

    if len(broken) < MIN_ABSOLUTE_BROKEN:
        return None

    confidence = _broken_ref_confidence(len(broken))
    anchor = now if now is not None else datetime.now(timezone.utc)
    if anchor.tzinfo is None:
        anchor = anchor.replace(tzinfo=timezone.utc)
    timestamp = anchor.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    artifact_fragment = _id_fragment(source_artifact)
    suggestion_id = (
        f"sugg-broken-ref-{anchor.astimezone(timezone.utc):%Y%m%dT%H%M%SZ}-"
        f"{artifact_fragment}-{len(broken):02d}"
    )

    supporting_signals = tuple(f"broken_ref={target}" for _, target in broken)
    reason_flags = ("broken_canonical_ref_detected",)
    return Suggestion(
        id=suggestion_id,
        timestamp=timestamp,
        source_artifact=source_artifact,
        project_context=project_context,
        task_description=(
            "A canonical operations document points to a local path that does not "
            "exist, so a reader may fail to recover the intended context cleanly."
        ),
        suggested_failure_mode="CONTEXT_NOT_FOUND",
        supporting_signals=supporting_signals,
        operational_cost_estimate={
            "minutes_spent": 0,
            "extra_files_opened": 0,
            "manual_search_rounds": 0,
        },
        confidence=confidence,
        reason_flags=reason_flags,
        human_review_required=True,
        authority=AUTHORITY,
        schema_version=SCHEMA_VERSION,
    )


def detect_current_surface_drift(
    *,
    case: dict[str, Any],
    now: datetime | None = None,
) -> Suggestion | None:
    sources = extract_current_surface_sources(case)
    if len(sources) < 2:
        return None

    counts = extract_current_surface_counts(case)
    if len(counts) < 2:
        return None

    max_drift = max(counts.values()) - min(counts.values())
    if max_drift < MIN_ABSOLUTE_DRIFT:
        return None

    confidence = classify_confidence(max_drift)
    anchor = now if now is not None else datetime.now(timezone.utc)
    if anchor.tzinfo is None:
        anchor = anchor.replace(tzinfo=timezone.utc)
    timestamp = anchor.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    artifact_fragment = _id_fragment(case["id"])
    suggestion_id = (
        f"sugg-surface-drift-{anchor.astimezone(timezone.utc):%Y%m%dT%H%M%SZ}-"
        f"{artifact_fragment}-{max_drift:04d}"
    )

    supporting_signals = tuple(
        [*(f"{name}_suite_count={counts[name]}" for name in SURFACE_TEXT_FIELDS if name in counts)]
        + [f"max_pairwise_drift={max_drift}"]
    )
    reason_flags = (
        "cross_doc_surface_drift_detected",
        "suite_count_mismatch_across_docs",
    )
    return Suggestion(
        id=suggestion_id,
        timestamp=timestamp,
        source_artifact=case["id"],
        project_context="dataset",
        task_description=(
            "Multiple live current-snapshot carriers expose divergent current suite "
            "counts, so the reader cannot recover a single current surface cleanly."
        ),
        suggested_failure_mode="CONTEXT_AMBIGUOUS",
        supporting_signals=supporting_signals,
        operational_cost_estimate={
            "minutes_spent": 0,
            "extra_files_opened": 0,
            "manual_search_rounds": 0,
        },
        confidence=confidence,
        reason_flags=reason_flags,
        human_review_required=True,
        authority=AUTHORITY,
        schema_version=SCHEMA_VERSION,
    )


def detect_supersedes_mechanical_metadata(
    *,
    source_artifact: str,
    text: str,
    project_context: str = "cerebro",
    now: datetime | None = None,
) -> Suggestion | None:
    analysis = analyze_supersedes_mechanical_metadata(
        source_artifact=source_artifact,
        text=text,
    )
    if analysis.state != "in_scope_mechanical_only":
        return None

    confidence = _supersedes_confidence(analysis.ambiguous_hits)
    anchor = now if now is not None else datetime.now(timezone.utc)
    if anchor.tzinfo is None:
        anchor = anchor.replace(tzinfo=timezone.utc)
    timestamp = anchor.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    artifact_fragment = _id_fragment(source_artifact)
    artifact_digest = _stable_artifact_digest(source_artifact)
    suggestion_id = (
        f"sugg-supersedes-{anchor.astimezone(timezone.utc):%Y%m%dT%H%M%SZ}-"
        f"{artifact_fragment}-{artifact_digest}-{len(analysis.ambiguous_hits):02d}"
    )

    supporting_signals = tuple(
        [
            *(f"ambiguous_token={hit.token}" for hit in analysis.ambiguous_hits),
            *(
                f"missing_context={','.join(hit.missing_context)}"
                for hit in analysis.ambiguous_hits
            ),
            f"ambiguous_token_count={len(analysis.ambiguous_hits)}",
        ]
    )
    reason_flags = ("mechanical_supersedes_metadata",)
    return Suggestion(
        id=suggestion_id,
        timestamp=timestamp,
        source_artifact=source_artifact,
        project_context=project_context,
        task_description=(
            "An operator-facing artifact exposes mechanical supersession metadata "
            "without enough nearby human context to recover the winner and rationale cleanly."
        ),
        suggested_failure_mode="CONTEXT_AMBIGUOUS",
        supporting_signals=supporting_signals,
        operational_cost_estimate={
            "minutes_spent": 0,
            "extra_files_opened": 0,
            "manual_search_rounds": 0,
        },
        confidence=confidence,
        reason_flags=reason_flags,
        human_review_required=True,
        authority=AUTHORITY,
        schema_version=SCHEMA_VERSION,
    )


def detect_stale_system_state(
    *,
    source_artifact: str,
    text: str,
    project_context: str = "cerebro",
    now: datetime | None = None,
) -> Suggestion | None:
    """Emit a `STALE_INFORMATION` suggestion when `SYSTEM_STATE.md`-shaped
    text carries two divergent suite-result counts across its canonical
    sections.

    Returns `None` unless both sections are present, both carry a
    `Last suite result` count, the counts differ, and the absolute drift
    meets the conservative threshold. The rule never auto-promotes a
    suggestion to a record; `human_review_required` is always true.
    """
    suite_numbers = extract_suite_numbers_by_section(text)
    if "current_snapshot" not in suite_numbers or "gate_status" not in suite_numbers:
        return None
    current = suite_numbers["current_snapshot"]
    gate = suite_numbers["gate_status"]
    diff = current - gate
    abs_diff = abs(diff)
    if abs_diff < MIN_ABSOLUTE_DRIFT:
        return None

    confidence = classify_confidence(abs_diff)
    anchor = now if now is not None else datetime.now(timezone.utc)
    if anchor.tzinfo is None:
        anchor = anchor.replace(tzinfo=timezone.utc)
    timestamp = anchor.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    artifact_fragment = _id_fragment(source_artifact)
    suggestion_id = (
        f"sugg-stale-{anchor.astimezone(timezone.utc):%Y%m%dT%H%M%SZ}-"
        f"{artifact_fragment}-{abs_diff:04d}"
    )

    supporting_signals = (
        f"current_snapshot_suite_count={current}",
        f"gate_status_suite_count={gate}",
        f"suite_count_drift={diff}",
    )
    reason_flags = (
        "stale_snapshot_detected",
        "suite_count_mismatch",
    )
    return Suggestion(
        id=suggestion_id,
        timestamp=timestamp,
        source_artifact=source_artifact,
        project_context=project_context,
        task_description=(
            "SYSTEM_STATE.md carries two divergent `Last suite result` counts "
            "across its canonical sections; the older number may still be "
            "consulted as ground truth."
        ),
        suggested_failure_mode="STALE_INFORMATION",
        supporting_signals=supporting_signals,
        operational_cost_estimate={
            "minutes_spent": 0,
            "extra_files_opened": 0,
            "manual_search_rounds": 0,
        },
        confidence=confidence,
        reason_flags=reason_flags,
        human_review_required=True,
        authority=AUTHORITY,
        schema_version=SCHEMA_VERSION,
    )


def detect_export_surface_gap(
    *, case: dict[str, Any], now: datetime | None = None
) -> Suggestion | None:
    """Emit `INSUFFICIENT_EXPORT_SURFACE` when a source artifact declares
    explicit required export anchors and none of them appear in the
    captured export outputs.

    This rule is intentionally conservative:
    - it requires a `## Required Export Anchors` section
    - it requires at least two anchors
    - it requires a non-empty captured export payload
    - it stays silent if even one required anchor is present
    """
    text = case.get("text", "")
    exports_text = case.get("exports_text", "")
    if not isinstance(text, str) or not isinstance(exports_text, str):
        return None
    if not exports_text.strip():
        return None

    anchors = extract_required_export_anchors(text)
    if len(anchors) < 2:
        return None

    matched = tuple(anchor for anchor in anchors if _anchor_matches_exports(anchor, exports_text))
    if matched:
        return None

    confidence = "high" if len(anchors) >= 3 else "medium"
    anchor = now if now is not None else datetime.now(timezone.utc)
    if anchor.tzinfo is None:
        anchor = anchor.replace(tzinfo=timezone.utc)
    timestamp = anchor.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    project_context = case.get("project_context", "dataset")
    source_artifact = case.get("id", "unknown")
    artifact_fragment = _id_fragment(str(source_artifact))
    suggestion_id = (
        f"sugg-export-gap-{anchor.astimezone(timezone.utc):%Y%m%dT%H%M%SZ}-"
        f"{artifact_fragment}-{len(anchors):02d}"
    )
    task_description = (
        "The source artifact declares export anchors required for a basic operational "
        "need, but none of those anchors were found in the captured export outputs."
    )
    supporting_signals = tuple(f"missing_anchor={item}" for item in anchors) + (
        f"captured_exports_chars={len(exports_text.strip())}",
    )
    reason_flags = (
        "insufficient_surface_detected",
        "required_export_anchors_missing",
    )
    return Suggestion(
        id=suggestion_id,
        timestamp=timestamp,
        source_artifact=source_artifact,
        project_context=project_context,
        task_description=task_description,
        suggested_failure_mode="INSUFFICIENT_EXPORT_SURFACE",
        supporting_signals=supporting_signals,
        operational_cost_estimate={
            "minutes_spent": 0,
            "extra_files_opened": 0,
            "manual_search_rounds": 0,
        },
        confidence=confidence,
        reason_flags=reason_flags,
        human_review_required=True,
        authority=AUTHORITY,
        schema_version=SCHEMA_VERSION,
    )


def suggestion_as_dict(suggestion: Suggestion) -> dict[str, Any]:
    payload = asdict(suggestion)
    payload["supporting_signals"] = list(suggestion.supporting_signals)
    payload["reason_flags"] = list(suggestion.reason_flags)
    return payload
