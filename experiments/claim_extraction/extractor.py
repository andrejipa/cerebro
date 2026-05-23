from __future__ import annotations

import re
from collections.abc import Iterable

from .contract import ClaimCandidate, SourceText


OPERATIONAL_MARKERS = (
    "critical",
    "high",
    "blocked",
    "stop condition",
    "approval required",
    "rollback",
    "freeze",
    "forbidden",
    "must not",
    "explicit human go/no-go",
)


def _criticality_for(line: str) -> str:
    lowered = line.lower()
    return "high" if any(marker in lowered for marker in OPERATIONAL_MARKERS) else "unknown"


def _span(line_number: int) -> str:
    return f"L{line_number}"


def _candidate(
    *,
    subject: str,
    predicate: str,
    object: str,
    polarity: str,
    modality: str,
    source: SourceText,
    line_number: int,
    extraction_basis: str = "explicit",
    source_role: str | None = None,
    authority_hint: str = "source-local",
    criticality_hint: str | None = None,
    line_text: str = "",
) -> ClaimCandidate:
    return ClaimCandidate(
        subject=subject,
        predicate=predicate,
        object=object,
        polarity=polarity,
        modality=modality,
        criticality_hint=criticality_hint if criticality_hint is not None else _criticality_for(line_text),
        source_path=source.source_path,
        evidence_span=_span(line_number),
        source_role=source_role or source.source_role,
        authority_hint=authority_hint,
        extraction_basis=extraction_basis,
    )


def _extract_from_line(source: SourceText, line: str, line_number: int, next_line: str | None) -> list[ClaimCandidate]:
    raw = line.strip()
    stripped = raw.strip('"')
    lowered = stripped.lower()
    out: list[ClaimCandidate] = []

    if "deliberate freeze for canonical-runtime growth remains active" in lowered:
        out.append(
            _candidate(
                subject="canonical-runtime growth",
                predicate="remains",
                object="deliberate freeze active",
                polarity="positive",
                modality="procedural",
                source=source,
                line_number=line_number,
                line_text=stripped,
            )
        )

    if "no cerebro runtime boundary is open" in lowered:
        out.append(
            _candidate(
                subject="Cerebro runtime boundary",
                predicate="is",
                object="not open",
                polarity="negative",
                modality="procedural",
                source=source,
                line_number=line_number,
                line_text=stripped,
            )
        )

    if "tests/, core/, cli/, extensions/, and runtime implementation remain closed" in lowered:
        out.append(
            _candidate(
                subject="tests core cli extensions runtime implementation",
                predicate="remain",
                object="closed",
                polarity="negative",
                modality="procedural",
                source=source,
                line_number=line_number,
                line_text=stripped,
            )
        )

    if "edge functions still need implementation" in lowered:
        out.append(
            _candidate(
                subject="Edge Functions",
                predicate="need",
                object="implementation",
                polarity="positive",
                modality="factual",
                source=source,
                line_number=line_number,
                criticality_hint="unknown",
            )
        )

    if "supabase validation is the next operational step" in lowered:
        out.append(
            _candidate(
                subject="Supabase validation",
                predicate="is",
                object="next operational step",
                polarity="positive",
                modality="procedural",
                source=source,
                line_number=line_number,
                criticality_hint="unknown",
            )
        )

    if "the supabase schema already exists" in lowered:
        out.append(
            _candidate(
                subject="Supabase schema",
                predicate="already exists",
                object="true",
                polarity="positive",
                modality="factual",
                source=source,
                line_number=line_number,
                criticality_hint="unknown",
            )
        )

    if "edge functions must be validated against the existing schema" in lowered or (
        "validating edge functions against the existing schema" in lowered
    ):
        out.append(
            _candidate(
                subject="Edge Functions",
                predicate="should be validated against",
                object="existing schema",
                polarity="positive",
                modality="procedural",
                source=source,
                line_number=line_number,
                criticality_hint="unknown",
            )
        )

    if raw == "Next item: build a combined context report.":
        out.append(
            _candidate(
                subject="next item",
                predicate="is",
                object="build a combined context report",
                polarity="positive",
                modality="procedural",
                source=source,
                line_number=line_number,
                criticality_hint="unknown",
            )
        )

    if "quotes opportunity_map.md" in lowered and next_line and "next item: build a combined context report" in next_line.lower():
        out.append(
            _candidate(
                subject="SYSTEM_STATE.md",
                predicate="cites",
                object="OPPORTUNITY_MAP.md next item",
                polarity="positive",
                modality="meta",
                source=source,
                line_number=line_number,
                source_role="citation",
                criticality_hint="unknown",
            )
        )

    if lowered.startswith("authority order:"):
        chain = stripped.split(":", 1)[1].strip()
        if next_line and next_line.strip().startswith("SYSTEM_STATE.md"):
            chain = f"{chain} {next_line.strip()}"
        out.append(
            _candidate(
                subject="authority order",
                predicate="is",
                object=chain.rstrip("."),
                polarity="positive",
                modality="meta",
                source=source,
                line_number=line_number,
                criticality_hint="unknown",
            )
        )

    if "divergence forces docs-only reconciliation before implementation" in lowered:
        out.append(
            _candidate(
                subject="divergence",
                predicate="forces",
                object="docs-only reconciliation before implementation",
                polarity="required",
                modality="meta",
                source=source,
                line_number=line_number,
                criticality_hint="high",
            )
        )

    consumed = re.search(
        r"formal resume trigger consumed on (\d{4}-\d{2}-\d{2})(?::\s*`?([A-Za-z0-9_./-]+)`?)?",
        stripped,
        re.IGNORECASE,
    )
    if consumed:
        trigger = consumed.group(2)
        if not trigger and next_line:
            trigger = next_line.strip().strip("`.")
        if not trigger:
            trigger = "formal resume trigger"
        out.append(
            _candidate(
                subject=trigger,
                predicate="consumed_on",
                object=consumed.group(1),
                polarity="positive",
                modality="temporal",
                source=source,
                line_number=line_number,
                criticality_hint="unknown",
            )
        )

    if "third-party pilot remains waiting for explicit human go/no-go" in lowered:
        out.append(
            _candidate(
                subject="third-party pilot",
                predicate="remains",
                object="waiting for explicit human go/no-go",
                polarity="unknown",
                modality="temporal",
                source=source,
                line_number=line_number,
                criticality_hint="high",
            )
        )

    if "schema status determines whether" in lowered:
        out.append(
            _candidate(
                subject="schema status",
                predicate="determines",
                object="whether to create schema or validate Edge Functions against existing schema",
                polarity="positive",
                modality="procedural",
                source=source,
                line_number=line_number,
                criticality_hint="unknown",
            )
        )

    if "stop condition:" in lowered and "negative claim inferred from silence" in lowered and "halt the slice" in lowered:
        out.append(
            _candidate(
                subject="negative claim inferred from silence",
                predicate="must halt",
                object="slice",
                polarity="required",
                modality="procedural",
                source=source,
                line_number=line_number,
                criticality_hint="high",
            )
        )

    if "approval required before third-party mutation" in lowered:
        out.append(
            _candidate(
                subject="third-party mutation",
                predicate="requires",
                object="approval",
                polarity="required",
                modality="procedural",
                source=source,
                line_number=line_number,
                criticality_hint="high",
            )
        )

    if "formal_resume_trigger_claim_extraction_slice_1" in lowered and "when implementation is authorized" in lowered:
        out.append(
            _candidate(
                subject="FORMAL_RESUME_TRIGGER_CLAIM_EXTRACTION_SLICE_1",
                predicate="is",
                object="proposed future trigger text",
                polarity="unknown",
                modality="meta",
                source=source,
                line_number=line_number,
                source_role="derived",
                criticality_hint="unknown",
            )
        )

    return out


def extract_candidates(
    sources: Iterable[SourceText],
    *,
    structured_absences: Iterable[ClaimCandidate] = (),
    supersession_absences: Iterable[ClaimCandidate] = (),
) -> list[ClaimCandidate]:
    candidates: list[ClaimCandidate] = []
    for source in sources:
        lines = source.text.splitlines()
        for index, line in enumerate(lines, start=1):
            next_line = lines[index].strip() if index < len(lines) else None
            candidates.extend(_extract_from_line(source, line, index, next_line))

    candidates.extend(structured_absences)
    candidates.extend(supersession_absences)
    return sorted(candidates, key=lambda candidate: (candidate.source_path, candidate.evidence_span, candidate.claim_id))
