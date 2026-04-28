from __future__ import annotations

from dataclasses import dataclass, field

from .contract import ClaimCandidate, SourceText
from .extractor import extract_candidates


@dataclass(frozen=True)
class FixtureCase:
    id: str
    purpose: str
    inputs: tuple[SourceText, ...]
    expected: tuple[ClaimCandidate, ...]
    forbidden: tuple[tuple[str, str, str], ...] = ()
    structured_absences: tuple[ClaimCandidate, ...] = ()
    supersession_absences: tuple[ClaimCandidate, ...] = ()
    allow_extra: bool = False
    notes: str = ""

    def extract(self) -> list[ClaimCandidate]:
        return extract_candidates(
            self.inputs,
            structured_absences=self.structured_absences,
            supersession_absences=self.supersession_absences,
        )


def _source(path: str, text: str, role: str = "primary") -> SourceText:
    return SourceText(path, text.strip() + "\n", role)


def _claim(
    subject: str,
    predicate: str,
    object: str,
    polarity: str,
    modality: str,
    criticality_hint: str,
    source_path: str,
    source_role: str,
    extraction_basis: str,
    line: str = "L1",
) -> ClaimCandidate:
    return ClaimCandidate(
        subject=subject,
        predicate=predicate,
        object=object,
        polarity=polarity,
        modality=modality,
        criticality_hint=criticality_hint,
        source_path=source_path,
        evidence_span=line,
        source_role=source_role,
        authority_hint="source-local",
        extraction_basis=extraction_basis,
    )


F1 = FixtureCase(
    id="F1_explicit_runtime_freeze",
    purpose="Extract explicit operational boundary claims.",
    inputs=(
        _source(
            "docs/operations/SYSTEM_STATE.md",
            """
            Current posture: deliberate freeze for canonical-runtime growth remains active.
            Current boundary: no Cerebro runtime boundary is open.
            tests/, core/, cli/, extensions/, and runtime implementation remain closed.
            """,
        ),
    ),
    expected=(
        _claim("canonical-runtime growth", "remains", "deliberate freeze active", "positive", "procedural", "high", "docs/operations/SYSTEM_STATE.md", "primary", "explicit", "L1"),
        _claim("Cerebro runtime boundary", "is", "not open", "negative", "procedural", "unknown", "docs/operations/SYSTEM_STATE.md", "primary", "explicit", "L2"),
        _claim("tests core cli extensions runtime implementation", "remain", "closed", "negative", "procedural", "unknown", "docs/operations/SYSTEM_STATE.md", "primary", "explicit", "L3"),
    ),
    forbidden=(("experiments", "are", "closed"),),
)

F2 = FixtureCase(
    id="F2_silence_is_not_negative",
    purpose="Omission does not create a negative factual claim.",
    inputs=(
        _source(
            "docs/operations/DIAGNOSTIC.md",
            """
            Current diagnostic:
            - Edge Functions still need implementation.
            - Supabase validation is the next operational step.
            """,
        ),
    ),
    expected=(
        _claim("Edge Functions", "need", "implementation", "positive", "factual", "unknown", "docs/operations/DIAGNOSTIC.md", "primary", "explicit", "L2"),
        _claim("Supabase validation", "is", "next operational step", "positive", "procedural", "unknown", "docs/operations/DIAGNOSTIC.md", "primary", "explicit", "L3"),
    ),
    forbidden=(("Supabase schema", "exists", "false"), ("Supabase schema", "does not exist", "true")),
)

F3_ABSENCE = _claim(
    "diagnostic source",
    "does not declare",
    "known schema status",
    "unknown",
    "factual",
    "unknown",
    "docs/operations/DIAGNOSTIC.md",
    "primary",
    "structured_absence",
    "L3",
)
F3 = FixtureCase(
    id="F3_structured_absence_is_unknown",
    purpose="Required-section absence stays unknown, not negative.",
    inputs=(
        _source(
            "docs/operations/DIAGNOSTIC.md",
            """
            Required sections:
            - Current objective
            - Known schema status
            - Next action

            Current objective:
            - Validate Edge Functions.

            Next action:
            - Inspect Supabase functions.
            """,
        ),
    ),
    expected=(F3_ABSENCE,),
    forbidden=(("schema", "does not exist", "true"),),
    structured_absences=(F3_ABSENCE,),
)

F4_SUPERSESSION = _claim(
    "OLD_DIAGNOSTIC.md",
    "is insufficient for",
    "schema-creation decisions",
    "unknown",
    "meta",
    "unknown",
    "docs/operations/OLD_DIAGNOSTIC.md",
    "derived",
    "supersession_absence",
    "L1",
)
F4 = FixtureCase(
    id="F4_supersession_absence_is_unknown",
    purpose="Supersession creates insufficiency, not opposition.",
    inputs=(
        _source("docs/operations/OLD_DIAGNOSTIC.md", "Current diagnostic:\n- Edge Functions still need implementation."),
        _source(
            "docs/operations/MEMORIA_CONTINUIDADE_ATUAL.md",
            """
            Current continuity:
            - The Supabase schema already exists.
            - Edge Functions must be validated against the existing schema.
            """,
        ),
    ),
    expected=(
        _claim("Edge Functions", "need", "implementation", "positive", "factual", "unknown", "docs/operations/OLD_DIAGNOSTIC.md", "primary", "explicit", "L2"),
        _claim("Supabase schema", "already exists", "true", "positive", "factual", "unknown", "docs/operations/MEMORIA_CONTINUIDADE_ATUAL.md", "primary", "explicit", "L2"),
        _claim("Edge Functions", "should be validated against", "existing schema", "positive", "procedural", "unknown", "docs/operations/MEMORIA_CONTINUIDADE_ATUAL.md", "primary", "explicit", "L3"),
        F4_SUPERSESSION,
    ),
    forbidden=(("OLD_DIAGNOSTIC.md", "says", "schema does not exist"),),
    supersession_absences=(F4_SUPERSESSION,),
)

F5 = FixtureCase(
    id="F5_citation_does_not_upgrade_authority",
    purpose="Keep assertion source and citation source separate.",
    inputs=(
        _source("docs/operations/OPPORTUNITY_MAP.md", "Next item: build a combined context report."),
        _source(
            "docs/operations/SYSTEM_STATE.md",
            'The current snapshot quotes OPPORTUNITY_MAP.md:\n"Next item: build a combined context report."',
        ),
    ),
    expected=(
        _claim("next item", "is", "build a combined context report", "positive", "procedural", "unknown", "docs/operations/OPPORTUNITY_MAP.md", "primary", "explicit", "L1"),
        _claim("SYSTEM_STATE.md", "cites", "OPPORTUNITY_MAP.md next item", "positive", "meta", "unknown", "docs/operations/SYSTEM_STATE.md", "citation", "explicit", "L1"),
    ),
    forbidden=(("next item", "is authoritatively set by", "SYSTEM_STATE.md quote"),),
)

F6 = FixtureCase(
    id="F6_meta_claim_is_first_class",
    purpose="Extract interpretation-governing claims.",
    inputs=(
        _source(
            "AGENTS.md",
            """
            Authority order: AGENTS.md -> active triggers -> observation_center.toml ->
            SYSTEM_STATE.md -> OPPORTUNITY_MAP.md -> active plans -> code/tests.
            Divergence forces docs-only reconciliation before implementation.
            """,
        ),
    ),
    expected=(
        _claim("authority order", "is", "AGENTS.md -> active triggers -> observation_center.toml -> SYSTEM_STATE.md -> OPPORTUNITY_MAP.md -> active plans -> code/tests", "positive", "meta", "unknown", "AGENTS.md", "primary", "explicit", "L1"),
        _claim("divergence", "forces", "docs-only reconciliation before implementation", "required", "meta", "high", "AGENTS.md", "primary", "explicit", "L3"),
    ),
    forbidden=(("code/tests", "have highest authority", "true"),),
)

F7 = FixtureCase(
    id="F7_temporal_status_preserved",
    purpose="Preserve consumed/waiting status.",
    inputs=(
        _source(
            "docs/operations/SYSTEM_STATE.md",
            """
            Formal resume trigger consumed on 2026-04-24:
            FORMAL_RESUME_TRIGGER_CONTEXT_VECTORS_SLICE_1.
            Third-party pilot remains waiting for explicit human go/no-go.
            """,
        ),
    ),
    expected=(
        _claim("FORMAL_RESUME_TRIGGER_CONTEXT_VECTORS_SLICE_1", "consumed_on", "2026-04-24", "positive", "temporal", "unknown", "docs/operations/SYSTEM_STATE.md", "primary", "explicit", "L1"),
        _claim("third-party pilot", "remains", "waiting for explicit human go/no-go", "unknown", "temporal", "high", "docs/operations/SYSTEM_STATE.md", "primary", "explicit", "L3"),
    ),
    forbidden=(("context vectors trigger", "is active", "true"), ("third-party pilot", "is approved", "true")),
)

F8 = FixtureCase(
    id="F8_criticality_unknown_by_default",
    purpose="Criticality is not inferred from apparent importance.",
    inputs=(
        _source(
            "docs/operations/PLAN.md",
            "The schema status determines whether the agent should create a database schema or validate Edge Functions against an existing schema.",
        ),
    ),
    expected=(
        _claim("schema status", "determines", "whether to create schema or validate Edge Functions against existing schema", "positive", "procedural", "unknown", "docs/operations/PLAN.md", "primary", "explicit", "L1"),
    ),
    forbidden=(("schema status", "has criticality", "critical"),),
)

F9 = FixtureCase(
    id="F9_criticality_marker_promotion",
    purpose="Promote criticality only from explicit operational markers.",
    inputs=(
        _source(
            "docs/operations/TRIGGER.md",
            """
            Stop condition: any negative claim inferred from silence must halt the slice.
            Approval required before third-party mutation.
            """,
        ),
    ),
    expected=(
        _claim("negative claim inferred from silence", "must halt", "slice", "required", "procedural", "high", "docs/operations/TRIGGER.md", "primary", "explicit", "L1"),
        _claim("third-party mutation", "requires", "approval", "required", "procedural", "high", "docs/operations/TRIGGER.md", "primary", "explicit", "L2"),
    ),
    forbidden=(("third-party mutation", "is approved", "true"),),
)

F10_STRUCTURED = _claim(
    "cerebro_base/04_DIAGNOSTICO_INICIAL_ATUAL.md",
    "does not declare",
    "schema status",
    "unknown",
    "factual",
    "unknown",
    "cerebro_base/04_DIAGNOSTICO_INICIAL_ATUAL.md",
    "primary",
    "structured_absence",
    "L1",
)
F10_SUPERSESSION = _claim(
    "cerebro_base/04_DIAGNOSTICO_INICIAL_ATUAL.md",
    "is insufficient for",
    "schema-creation decisions",
    "unknown",
    "meta",
    "unknown",
    "cerebro_base/04_DIAGNOSTICO_INICIAL_ATUAL.md",
    "derived",
    "supersession_absence",
    "L1",
)
F10 = FixtureCase(
    id="F10_fixture_9_full_schema_omission_oracle",
    purpose="Lock the rpg_caminhada schema omission failure class.",
    inputs=(
        _source(
            "cerebro_base/04_DIAGNOSTICO_INICIAL_ATUAL.md",
            """
            Current diagnostic:
            - Edge Functions still need implementation.
            - Supabase validation is the next operational step.
            """,
        ),
        _source(
            "cerebro_base/04_MEMORIA_CONTINUIDADE_ATUAL.md",
            """
            Current continuity:
            - The Supabase schema already exists.
            - The next step is validating Edge Functions against the existing schema.
            """,
        ),
    ),
    expected=(
        _claim("Edge Functions", "need", "implementation", "positive", "factual", "unknown", "cerebro_base/04_DIAGNOSTICO_INICIAL_ATUAL.md", "primary", "explicit", "L2"),
        _claim("Supabase validation", "is", "next operational step", "positive", "procedural", "unknown", "cerebro_base/04_DIAGNOSTICO_INICIAL_ATUAL.md", "primary", "explicit", "L3"),
        _claim("Supabase schema", "already exists", "true", "positive", "factual", "unknown", "cerebro_base/04_MEMORIA_CONTINUIDADE_ATUAL.md", "primary", "explicit", "L2"),
        _claim("Edge Functions", "should be validated against", "existing schema", "positive", "procedural", "unknown", "cerebro_base/04_MEMORIA_CONTINUIDADE_ATUAL.md", "primary", "explicit", "L3"),
        F10_STRUCTURED,
        F10_SUPERSESSION,
    ),
    forbidden=(
        ("cerebro_base/04_DIAGNOSTICO_INICIAL_ATUAL.md", "says", "schema does not exist"),
        ("Supabase schema", "does not exist", "true"),
        ("schema creation", "is next action", "true"),
    ),
    structured_absences=(F10_STRUCTURED,),
    supersession_absences=(F10_SUPERSESSION,),
)

F11 = FixtureCase(
    id="F11_over_extraction_guard",
    purpose="Do not convert evaluation prose into operational candidates.",
    inputs=(
        _source(
            "docs/operations/NOTES.md",
            "The operator said the document is solid, surprisingly precise, and likely valuable when the moment arrives.",
        ),
    ),
    expected=(),
    forbidden=(("document", "is", "solid"), ("document", "is", "surprisingly precise"), ("document", "is", "valuable")),
)

F12 = FixtureCase(
    id="F12_trigger_text_is_not_authorization",
    purpose="Future trigger drafts are not active authorization.",
    inputs=(
        _source(
            "docs/operations/CLAIM_EXTRACTION_IMPLEMENTATION_READINESS.md",
            """
            When implementation is authorized, the formal trigger should contain: FORMAL_RESUME_TRIGGER_CLAIM_EXTRACTION_SLICE_1
            Boundary:
            - experiments/claim_extraction/**
            """,
        ),
    ),
    expected=(
        _claim("FORMAL_RESUME_TRIGGER_CLAIM_EXTRACTION_SLICE_1", "is", "proposed future trigger text", "unknown", "meta", "unknown", "docs/operations/CLAIM_EXTRACTION_IMPLEMENTATION_READINESS.md", "derived", "explicit", "L1"),
    ),
    forbidden=(
        ("FORMAL_RESUME_TRIGGER_CLAIM_EXTRACTION_SLICE_1", "is active", "true"),
        ("experiments/claim_extraction", "is authorized now", "true"),
    ),
)

FIXTURES: tuple[FixtureCase, ...] = (F1, F2, F3, F4, F5, F6, F7, F8, F9, F10, F11, F12)

