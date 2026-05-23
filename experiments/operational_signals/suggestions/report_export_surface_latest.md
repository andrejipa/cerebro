# Operational Insufficiency Suggestions — Tripwire Evaluation

- authority: `derived-advisory-only`
- schema_version: `1`
- non_authoritative: `true`
- read_only: `true`
- rule: `detect_export_surface_gap`
- evaluated_at: `2026-04-20T00:00:00Z`

## Metrics

- dataset cases: `11`
- total cases: `11`
- excluded cases: `0`
- true positives: `4`
- false positives: `0`
- true negatives: `7`
- false negatives: `0`
- precision: `1.0000`
- recall: `1.0000`
- F1: `1.0000`
- confidence checks: `4`
- confidence match rate: `1.0000`

## Verdict

- classification: `accept_for_staged_promotion`
- rationale: precision and recall clear the conservative acceptance bar; rule is safe for opt-in derived use pending a second tripwire before any wider adoption

## Per-Case Outcomes

- `pos-exp-001` label=`positive` outcome=`tp` expected_suggestion=`true` actual_suggestion=`true` expected_confidence=`medium` actual_confidence=`medium`
    - reason: two required anchors declared; neither appears anywhere in captured exports
- `pos-exp-002` label=`positive` outcome=`tp` expected_suggestion=`true` actual_suggestion=`true` expected_confidence=`high` actual_confidence=`high`
    - reason: three required anchors declared; no export carries any of them
- `pos-exp-003` label=`positive` outcome=`tp` expected_suggestion=`true` actual_suggestion=`true` expected_confidence=`medium` actual_confidence=`medium`
    - reason: non-empty exports exist, but they omit all explicitly required anchors
- `pos-exp-004` label=`positive` outcome=`tp` expected_suggestion=`true` actual_suggestion=`true` expected_confidence=`high` actual_confidence=`high`
    - reason: multiple export blocks still omit every required anchor
- `neg-exp-001` label=`negative` outcome=`tn` expected_suggestion=`false` actual_suggestion=`false` expected_confidence=`—` actual_confidence=`—`
    - reason: one required anchor is present in the exports, so the rule must stay silent
- `neg-exp-002` label=`negative` outcome=`tn` expected_suggestion=`false` actual_suggestion=`false` expected_confidence=`—` actual_confidence=`—`
    - reason: all required anchors are present
- `neg-exp-003` label=`negative` outcome=`tn` expected_suggestion=`false` actual_suggestion=`false` expected_confidence=`—` actual_confidence=`—`
    - reason: missing anchor section; prose-only expectation is too weak
- `neg-exp-004` label=`negative` outcome=`tn` expected_suggestion=`false` actual_suggestion=`false` expected_confidence=`—` actual_confidence=`—`
    - reason: empty exports_text means no captured surface was supplied; rule must stay silent
- `neg-exp-005` label=`negative` outcome=`tn` expected_suggestion=`false` actual_suggestion=`false` expected_confidence=`—` actual_confidence=`—`
    - reason: single-anchor declaration is too weak and would be noisy
- `neg-exp-006` label=`negative` outcome=`tn` expected_suggestion=`false` actual_suggestion=`false` expected_confidence=`—` actual_confidence=`—`
    - reason: free-form comma list is intentionally ignored to avoid optimistic parsing
- `neg-exp-007` label=`negative` outcome=`tn` expected_suggestion=`false` actual_suggestion=`false` expected_confidence=`—` actual_confidence=`—`
    - reason: anchor appears with punctuation differences, so normalized matching should prevent a false positive

## Reminder

- Each emitted suggestion is advisory only; `human_review_required` is always `true`.
- This report is derived and non-authoritative; it must never be consumed as canonical runtime state.
