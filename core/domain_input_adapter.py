"""Deterministic domain-input adapter for mapping text into canonical plan payloads."""

from __future__ import annotations

from copy import deepcopy
import re


VALID_INPUT_KINDS = {"auto", "list", "task", "structured"}
_LIST_BULLET_PATTERN = re.compile(r"^(?:[-*]|\d+[.)])\s+(?P<item>.+)$")
_TASK_METADATA_KEYS = {"id", "depends", "working_set", "acceptance"}
_VAGUE_INPUTS = {
    "isso",
    "isto",
    "that",
    "this",
    "organiza isso",
    "organiza isto",
    "organize this",
}
_INVALID_LIST_FRAGMENTS = {
    *_VAGUE_INPUTS,
    "por favor",
    "please",
}
_TRAILING_PUNCTUATION_PATTERN = re.compile(r"[.!?]+$")
_COORDINATED_CONNECTOR_PATTERN = re.compile(r"\b(?:and|or|e|ou)\b", re.IGNORECASE)
_SEMANTIC_AMBIGUOUS_LEAD_VERBS = {
    "arrange",
    "arrumar",
    "organizar",
    "organize",
    "plan",
    "planejar",
    "prepare",
    "preparar",
    "review",
    "revisar",
}
_SEMANTIC_GENERIC_OBJECT_TOKENS = {
    "agenda",
    "backlog",
    "closing",
    "fechamento",
    "mes",
    "mês",
    "month",
    "project",
    "projeto",
    "routine",
    "rotina",
    "semana",
    "trip",
    "viagem",
    "week",
}
_SEMANTIC_FILLER_TOKENS = {"a", "as", "do", "dos", "da", "das", "de", "del", "for", "o", "os", "the"}
_SEMANTIC_QUALIFIED_BROAD_OBJECT_TOKENS = {
    "backlog",
    "closing",
    "fechamento",
    "mes",
    "mês",
    "month",
    "project",
    "projeto",
    "routine",
    "rotina",
    "semana",
    "trip",
    "viagem",
    "week",
}


class DomainInputAdapterError(ValueError):
    """Raised when text input cannot be adapted safely into canonical plan state."""


class DomainInputAmbiguityError(DomainInputAdapterError):
    """Raised when more than one plausible interpretation exists for auto mode."""

    def __init__(self, message: str, *, interpretations: list[dict], ambiguity_type: str = "structural", ambiguity_level: str = "medium") -> None:
        super().__init__(message)
        self.interpretations = deepcopy(interpretations)
        self.ambiguity_type = ambiguity_type
        self.ambiguity_level = ambiguity_level


def _normalize_text(raw_text: object) -> str:
    if not isinstance(raw_text, str):
        raise DomainInputAdapterError("domain input must be a text string")
    normalized = raw_text.replace("\r\n", "\n").replace("\r", "\n").strip().lstrip("\ufeff")
    if not normalized:
        raise DomainInputAdapterError("domain input must not be empty")
    return normalized


def _non_empty_lines(text: str) -> list[str]:
    return [line.strip() for line in text.split("\n") if line.strip()]


def _dedupe_preserve_order(values: list[str]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for item in values:
        cleaned = item.strip()
        if not cleaned:
            continue
        key = cleaned.casefold()
        if key in seen:
            raise DomainInputAdapterError(f"duplicate normalized value is not allowed: {cleaned}")
        normalized.append(cleaned)
        seen.add(key)
    return normalized


def _normalize_phrase(text: str) -> str:
    collapsed = " ".join(text.split())
    collapsed = _TRAILING_PUNCTUATION_PATTERN.sub("", collapsed)
    return collapsed.casefold()


def _is_invalid_list_fragment(text: str) -> bool:
    return _normalize_phrase(text) in _INVALID_LIST_FRAGMENTS


def _reject_vague_task_title(title: str) -> None:
    if _normalize_phrase(title) in _VAGUE_INPUTS:
        raise DomainInputAdapterError("single-task input is too vague to adapt safely")


def _line_has_structured_metadata(line: str) -> bool:
    match = _LIST_BULLET_PATTERN.match(line)
    candidate = match.group("item").strip() if match is not None else line.strip()
    segments = [segment.strip() for segment in candidate.split("|")]
    if len(segments) <= 1:
        return False
    for segment in segments[1:]:
        if "=" not in segment:
            return False
        key, _ = [part.strip() for part in segment.split("=", 1)]
        if key not in _TASK_METADATA_KEYS:
            return False
    return True


def _build_task(task_id: str, title: str, *, depends_on: list[str] | None = None, working_set: list[str] | None = None, acceptance: list[str] | None = None) -> dict:
    normalized_title = title.strip()
    if not normalized_title:
        raise DomainInputAdapterError("task title must be non-empty")
    return {
        "id": task_id,
        "title": normalized_title,
        "status": "ready",
        "details": normalized_title,
        "depends_on": list(depends_on or []),
        "working_set": list(working_set or []),
        "acceptance_criteria": list(acceptance or []),
        "action_ids": [],
    }


def _build_interpretation(
    kind: str,
    payload: dict | None = None,
    *,
    confidence: str,
    reason: str,
    resolution: str,
    description: str | None = None,
    difference: str | None = None,
    impact: str | None = None,
) -> dict:
    tasks = (payload or {}).get("tasks", [])
    if description is None:
        if kind == "list":
            description = f"interpret as {len(tasks)} lightweight list item(s)"
        elif kind == "task":
            description = "interpret as one concrete task"
        else:
            description = f"interpret as structured plan with {len(tasks)} task(s)"
    if difference is None:
        if kind == "list":
            difference = "splits the input into independent tasks"
        elif kind == "task":
            difference = "keeps the full input as a single task title"
        else:
            difference = "reads explicit metadata, dependencies, and verification structure"
    if impact is None:
        if kind == "list":
            impact = "would persist multiple lightweight tasks"
        elif kind == "task":
            impact = "would persist one umbrella task with no extra decomposition"
        else:
            impact = "would persist an explicit plan with stronger structure"
    return {
        "kind": kind,
        "confidence": confidence,
        "description": description,
        "difference": difference,
        "reason": reason,
        "resolution": resolution,
        "impact": impact,
    }


def _ambiguous_separator_input(text: str) -> list[dict] | None:
    lines = _non_empty_lines(text)
    if len(lines) != 1 or not any(separator in lines[0] for separator in (",", ";")):
        return None
    split_items = [item.strip() for item in re.split(r"[;,]", lines[0]) if item.strip()]
    if len(split_items) <= 1:
        return None
    if any(_is_invalid_list_fragment(item) for item in split_items):
        raise DomainInputAdapterError("ambiguous multi-item input must use explicit list items or a concrete single task")
    return [
        _build_interpretation(
            "list",
            _parse_list_input(text),
            confidence="medium",
            reason="comma or semicolon separators strongly suggest multiple items",
            resolution="--input-kind list",
        ),
        _build_interpretation(
            "task",
            _parse_task_input(text),
            confidence="low",
            reason="the same line can still be read as one task title when selection is explicit",
            resolution="--input-kind task",
        ),
    ]


def _ambiguous_single_bullet_input(text: str) -> list[dict] | None:
    lines = _non_empty_lines(text)
    if len(lines) != 1 or _LIST_BULLET_PATTERN.match(lines[0]) is None:
        return None
    if _line_has_structured_metadata(lines[0]):
        return None
    return [
        _build_interpretation(
            "task",
            _parse_task_input(text),
            confidence="medium",
            reason="a single bullet often denotes one concrete task",
            resolution="--input-kind task",
        ),
        _build_interpretation(
            "list",
            _parse_list_input(text),
            confidence="medium",
            reason="a single bullet can also be treated as a one-item list when selected explicitly",
            resolution="--input-kind list",
        ),
    ]


def _ambiguous_inline_metadata_input(text: str) -> list[dict] | None:
    lines = _non_empty_lines(text)
    if len(lines) != 1 or _line_has_structured_metadata(lines[0]) is False:
        return None
    if lines[0].casefold().startswith("task:"):
        return None
    match = _LIST_BULLET_PATTERN.match(lines[0])
    candidate = match.group("item").strip() if match is not None else lines[0].strip()
    return [
        _build_interpretation(
            "structured",
            _parse_structured_input(f"task: {candidate}"),
            confidence="medium",
            reason="supported key=value metadata suggests a structured single-task plan",
            resolution="--input-kind structured",
        ),
        _build_interpretation(
            "task",
            _parse_task_input(text),
            confidence="low",
            reason="the same text can be preserved literally as one task title if structure was not intended",
            resolution="--input-kind task",
        ),
    ]


def _ambiguous_mixed_structured_bullet_list(text: str) -> list[dict] | None:
    lines = _non_empty_lines(text)
    if len(lines) <= 1:
        return None
    if not all(_LIST_BULLET_PATTERN.match(line) for line in lines):
        return None

    metadata_flags = [_line_has_structured_metadata(line) for line in lines]
    if not any(metadata_flags) or all(metadata_flags):
        return None

    return [
        _build_interpretation(
            "list",
            _parse_list_input(text),
            confidence="medium",
            reason="some bullet items carry metadata-like text while others still read as plain checklist items",
            resolution="--input-kind list",
            impact="would persist a flat list and keep metadata-like fragments as literal task text",
        ),
        _build_interpretation(
            "structured",
            _parse_structured_input(text),
            confidence="medium",
            reason="mixed bullet metadata can also be read as a structured plan with one explicit task spec and one plain task spec",
            resolution="--input-kind structured",
            impact="would persist structured task fields for the metadata-bearing items",
        ),
    ]


def _ambiguous_compound_instruction(text: str) -> list[dict] | None:
    lines = _non_empty_lines(text)
    if len(lines) != 1:
        return None
    line = lines[0]
    lowered = line.casefold()
    if any(separator in line for separator in (",", ";", "|")):
        return None
    if _LIST_BULLET_PATTERN.match(line) is not None:
        return None
    if lowered.startswith(("goal:", "summary:", "verify:", "task:")):
        return None
    parts = [part.strip() for part in _COORDINATED_CONNECTOR_PATTERN.split(line) if part.strip()]
    if len(parts) <= 1:
        return None
    if any(len(part.split()) > 6 for part in parts):
        return None
    return [
        _build_interpretation(
            "task",
            _parse_task_input(text),
            confidence="low",
            reason="the whole line can still be preserved as one task title when explicitly selected",
            resolution="--input-kind task",
        ),
        {
            "kind": "rewrite-as-list",
            "confidence": "medium",
            "description": f"rewrite as {len(parts)} explicit task(s)",
            "difference": "treats coordinated action phrases as separate tasks instead of one compound title",
            "reason": "short coordinated clauses suggest multiple actions but do not provide deterministic list syntax",
            "resolution": "rewrite the input as bullets, commas, or repeated --task flags",
            "impact": "would persist multiple lightweight tasks after rewrite",
        },
    ]


def _semantic_object_tokens(title: str) -> list[str]:
    normalized = _normalize_phrase(title)
    return [
        token
        for token in normalized.split()
        if token and token not in _SEMANTIC_FILLER_TOKENS
    ]


def _is_semantically_broad_scope(tokens: list[str]) -> bool:
    if len(tokens) < 2:
        return False
    if tokens[0] not in _SEMANTIC_AMBIGUOUS_LEAD_VERBS:
        return False

    scope_tokens = tokens[1:]
    if not scope_tokens:
        return False

    if scope_tokens[0] not in _SEMANTIC_GENERIC_OBJECT_TOKENS:
        return False

    remaining = scope_tokens[1:]
    if not remaining:
        return True

    if scope_tokens[0] in _SEMANTIC_QUALIFIED_BROAD_OBJECT_TOKENS and len(remaining) <= 2:
        return True

    return all(token in _SEMANTIC_GENERIC_OBJECT_TOKENS for token in remaining)


def _ambiguous_semantic_projection_input(text: str) -> list[dict] | None:
    lines = _non_empty_lines(text)
    if len(lines) != 1:
        return None
    line = lines[0]
    lowered = line.casefold()
    if any(separator in line for separator in (",", ";", "|")):
        return None
    if _LIST_BULLET_PATTERN.match(line) is not None:
        return None
    if lowered.startswith(("goal:", "summary:", "verify:", "task:")):
        return None
    tokens = _semantic_object_tokens(line)
    if len(tokens) < 2 or len(tokens) > 6:
        return None
    if not _is_semantically_broad_scope(tokens):
        return None
    return [
        _build_interpretation(
            "task",
            _parse_task_input(text),
            confidence="low",
            reason="the phrase can still be preserved literally as one high-level task",
            resolution="--input-kind task",
            impact="would persist one broad umbrella task and leave decomposition implicit",
        ),
        _build_interpretation(
            "list",
            None,
            confidence="medium",
            reason="the same phrase can denote a flat checklist or set of independent items",
            resolution="rewrite the input as bullets, commas, or repeated --task flags",
            description="interpret as a lightweight checklist or flat task set",
            difference="turns the broad phrase into independent trackable items",
            impact="would persist multiple lightweight tasks after rewrite",
        ),
        _build_interpretation(
            "structured",
            None,
            confidence="medium",
            reason="the same phrase can also denote a multi-step plan with explicit phases or completion criteria",
            resolution="rewrite with goal:/task: lines or explicit metadata",
            description="interpret as a structured plan",
            difference="turns the broad phrase into ordered steps, dependencies, or acceptance criteria",
            impact="would persist a structured-state or governed plan after rewrite",
        ),
    ]


def _detect_ambiguity(text: str) -> list[dict] | None:
    for detector in (
        _ambiguous_separator_input,
        _ambiguous_inline_metadata_input,
        _ambiguous_mixed_structured_bullet_list,
        _ambiguous_single_bullet_input,
        _ambiguous_compound_instruction,
        _ambiguous_semantic_projection_input,
    ):
        interpretations = detector(text)
        if interpretations:
            return interpretations
    return None


def _classify_input_kind(text: str, requested_kind: str) -> str:
    if requested_kind not in VALID_INPUT_KINDS:
        raise DomainInputAdapterError(f"input kind must be one of: {', '.join(sorted(VALID_INPUT_KINDS))}")
    if requested_kind != "auto":
        return requested_kind

    interpretations = _detect_ambiguity(text)
    if interpretations:
        ambiguity_type = "semantic" if len(interpretations) >= 3 else "structural"
        ambiguity_level = "high" if len(interpretations) >= 3 else "medium"
        raise DomainInputAmbiguityError(
            "multiple plausible interpretations exist for this input",
            interpretations=interpretations,
            ambiguity_type=ambiguity_type,
            ambiguity_level=ambiguity_level,
        )

    lines = _non_empty_lines(text)
    lowered = [line.casefold() for line in lines]
    if any(
        line.startswith("goal:")
        or line.startswith("summary:")
        or line.startswith("verify:")
        or line.startswith("task:")
        for line in lowered
    ):
        return "structured"
    if any(_line_has_structured_metadata(line) for line in lines) and all(_LIST_BULLET_PATTERN.match(line) for line in lines):
        return "structured"
    if len(lines) > 1 and all(_LIST_BULLET_PATTERN.match(line) for line in lines):
        return "list"
    if len(lines) == 1 and any(separator in lines[0] for separator in (",", ";")):
        split_items = [item.strip() for item in re.split(r"[;,]", lines[0]) if item.strip()]
        if len(split_items) > 1:
            if any(_is_invalid_list_fragment(item) for item in split_items):
                raise DomainInputAdapterError("ambiguous multi-item input must use explicit list items or a concrete single task")
            return "list"
    return "task"


def _parse_list_input(text: str) -> dict:
    lines = _non_empty_lines(text)
    items: list[str] = []
    if len(lines) > 1:
        for line in lines:
            match = _LIST_BULLET_PATTERN.match(line)
            if match is None:
                raise DomainInputAdapterError("list input with multiple lines must use bullets or numeric list markers")
            items.append(match.group("item").strip())
    else:
        match = _LIST_BULLET_PATTERN.match(lines[0])
        if match is not None:
            items = [match.group("item").strip()]
        else:
            items = [item.strip() for item in re.split(r"[;,]", lines[0]) if item.strip()]
        if len(items) <= 1:
            if match is None:
                raise DomainInputAdapterError("list input must contain at least two items")

    normalized_items = _dedupe_preserve_order(items)
    for item in normalized_items:
        if _is_invalid_list_fragment(item):
            raise DomainInputAdapterError(f"list input contains non-actionable item: {item}")
    tasks = [
        _build_task(f"task-{index:03d}", item)
        for index, item in enumerate(normalized_items, start=1)
    ]
    return {
        "input_kind": "list",
        "goal": "Complete listed items",
        "summary": "Adapted from simple list input.",
        "tasks": tasks,
        "verify_commands": [],
    }


def _parse_task_input(text: str) -> dict:
    lines = _non_empty_lines(text)
    if len(lines) != 1:
        raise DomainInputAdapterError("single-task input must contain exactly one non-empty line")
    match = _LIST_BULLET_PATTERN.match(lines[0])
    title = match.group("item").strip() if match is not None else lines[0].strip()
    _reject_vague_task_title(title)
    task = _build_task("task-001", title)
    return {
        "input_kind": "task",
        "goal": title,
        "summary": "Adapted from single-task input.",
        "tasks": [task],
        "verify_commands": [],
    }


def _parse_task_spec(line: str) -> dict:
    segments = [segment.strip() for segment in line.split("|")]
    title = segments[0].strip()
    if not title:
        raise DomainInputAdapterError("structured task line must start with a task title")
    _reject_vague_task_title(title)

    parsed = {
        "title": title,
        "id": "",
        "depends_on": [],
        "working_set": [],
        "acceptance_criteria": [],
    }
    seen_keys: set[str] = set()
    for segment in segments[1:]:
        if "=" not in segment:
            raise DomainInputAdapterError(f"structured task metadata must use key=value syntax: {segment}")
        key, raw_value = [part.strip() for part in segment.split("=", 1)]
        if key not in _TASK_METADATA_KEYS:
            raise DomainInputAdapterError(f"unsupported structured task metadata key: {key}")
        if key in seen_keys:
            raise DomainInputAdapterError(f"duplicate structured task metadata key: {key}")
        seen_keys.add(key)
        if not raw_value:
            raise DomainInputAdapterError(f"structured task metadata value must be non-empty: {key}")
        if key == "id":
            parsed["id"] = raw_value
        elif key == "depends":
            parsed["depends_on"] = _dedupe_preserve_order([item.strip() for item in raw_value.split(",") if item.strip()])
        elif key == "working_set":
            parsed["working_set"] = _dedupe_preserve_order([item.strip() for item in raw_value.split(",") if item.strip()])
        elif key == "acceptance":
            parsed["acceptance_criteria"] = _dedupe_preserve_order([item.strip() for item in raw_value.split(";") if item.strip()])
    return parsed


def _parse_structured_input(text: str) -> dict:
    lines = _non_empty_lines(text)
    goal = ""
    summary = ""
    verify_commands: list[str] = []
    raw_tasks: list[dict] = []

    for line in lines:
        lowered = line.casefold()
        if lowered.startswith("goal:"):
            if goal:
                raise DomainInputAdapterError("structured input must not repeat goal")
            goal = line.split(":", 1)[1].strip()
            if not goal:
                raise DomainInputAdapterError("structured input goal must be non-empty")
            continue
        if lowered.startswith("summary:"):
            if summary:
                raise DomainInputAdapterError("structured input must not repeat summary")
            summary = line.split(":", 1)[1].strip()
            if not summary:
                raise DomainInputAdapterError("structured input summary must be non-empty")
            continue
        if lowered.startswith("verify:"):
            command = line.split(":", 1)[1].strip()
            if not command:
                raise DomainInputAdapterError("structured input verify command must be non-empty")
            verify_commands.append(command)
            continue
        if lowered.startswith("task:"):
            raw_tasks.append(_parse_task_spec(line.split(":", 1)[1].strip()))
            continue
        match = _LIST_BULLET_PATTERN.match(line)
        if match is not None:
            raw_tasks.append(_parse_task_spec(match.group("item").strip()))
            continue
        raise DomainInputAdapterError(f"unsupported structured input line: {line}")

    if not raw_tasks:
        raise DomainInputAdapterError("structured input must define at least one task")

    assigned_ids: list[str] = []
    for index, task in enumerate(raw_tasks, start=1):
        task_id = task["id"] or f"task-{index:03d}"
        if task_id in assigned_ids:
            raise DomainInputAdapterError(f"duplicate structured task id: {task_id}")
        assigned_ids.append(task_id)
        task["id"] = task_id

    known_task_ids = set(assigned_ids)
    tasks: list[dict] = []
    for task in raw_tasks:
        for dependency in task["depends_on"]:
            if dependency not in known_task_ids:
                raise DomainInputAdapterError(f"structured task dependency is unknown: {dependency}")
            if dependency == task["id"]:
                raise DomainInputAdapterError(f"structured task must not depend on itself: {dependency}")
        tasks.append(
            _build_task(
                task["id"],
                task["title"],
                depends_on=task["depends_on"],
                working_set=task["working_set"],
                acceptance=task["acceptance_criteria"],
            )
        )

    if not goal:
        goal = tasks[0]["title"] if len(tasks) == 1 else "Complete adapted structured plan"
    if not summary:
        summary = "Adapted from structured plan input."
    if verify_commands and not any(task["working_set"] for task in tasks):
        raise DomainInputAdapterError("structured verify commands require at least one task with working_set")

    return {
        "input_kind": "structured",
        "goal": goal,
        "summary": summary,
        "tasks": tasks,
        "verify_commands": deepcopy(verify_commands),
    }


def adapt_domain_input(raw_text: object, *, input_kind: str = "auto") -> dict:
    """Parse, validate, and normalize text input into canonical plan-compatible data."""
    normalized_text = _normalize_text(raw_text)
    effective_kind = _classify_input_kind(normalized_text, input_kind)

    if effective_kind == "list":
        return _parse_list_input(normalized_text)
    if effective_kind == "task":
        return _parse_task_input(normalized_text)
    if effective_kind == "structured":
        return _parse_structured_input(normalized_text)
    raise DomainInputAdapterError(f"unsupported input kind: {effective_kind}")
