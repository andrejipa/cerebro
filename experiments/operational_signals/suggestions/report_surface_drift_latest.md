# Operational Insufficiency Suggestions — Tripwire Evaluation

- authority: `derived-advisory-only`
- schema_version: `1`
- non_authoritative: `true`
- read_only: `true`
- rule: `detect_current_surface_drift`
- evaluated_at: `2026-04-20T00:00:00Z`

## Metrics

- dataset cases: `10`
- total cases: `10`
- excluded cases: `0`
- true positives: `2`
- false positives: `0`
- true negatives: `8`
- false negatives: `0`
- precision: `1.0000`
- recall: `1.0000`
- F1: `1.0000`
- confidence checks: `2`
- confidence match rate: `1.0000`
- insufficient_sources cases: `5`
- sources_agree cases: `3`
- drift_detected cases: `2`

## Verdict

- classification: `accept_for_staged_promotion`
- rationale: precision and recall clear the conservative acceptance bar; rule is safe for opt-in derived use pending a second tripwire before any wider adoption

## Per-Case Outcomes

- `surface-pos-001` label=`positive` outcome=`tp` expected_suggestion=`true` actual_suggestion=`true` expected_confidence=`high` actual_confidence=`high` surface_state=`drift_detected`
    - reason: system state and opportunity map declare divergent current suite counts
- `surface-pos-002` label=`positive` outcome=`tp` expected_suggestion=`true` actual_suggestion=`true` expected_confidence=`low` actual_confidence=`low` surface_state=`drift_detected`
    - reason: the two live current-snapshot carriers drift by exactly the low threshold while README stays archival
- `surface-pos-003` label=`negative` outcome=`tn` expected_suggestion=`false` actual_suggestion=`false` expected_confidence=`—` actual_confidence=`—` surface_state=`sources_agree`
    - reason: README and closure are archival, so the two live carriers drift by less than the minimum threshold
- `surface-pos-004` label=`negative` outcome=`tn` expected_suggestion=`false` actual_suggestion=`false` expected_confidence=`—` actual_confidence=`—` surface_state=`insufficient_sources`
    - reason: phase closure is archival, so one live carrier alone must stay silent by the live-authority scope guard
- `surface-neg-001` label=`negative` outcome=`tn` expected_suggestion=`false` actual_suggestion=`false` expected_confidence=`—` actual_confidence=`—` surface_state=`sources_agree`
    - reason: two sources agree exactly on the same current suite count
- `surface-neg-002` label=`negative` outcome=`tn` expected_suggestion=`false` actual_suggestion=`false` expected_confidence=`—` actual_confidence=`—` surface_state=`insufficient_sources`
    - reason: three sources agree after extracting the first suite line from each doc
- `surface-neg-003` label=`negative` outcome=`tn` expected_suggestion=`false` actual_suggestion=`false` expected_confidence=`—` actual_confidence=`—` surface_state=`sources_agree`
    - reason: drift below the conservative absolute threshold
- `surface-neg-004` label=`negative` outcome=`tn` expected_suggestion=`false` actual_suggestion=`false` expected_confidence=`—` actual_confidence=`—` surface_state=`insufficient_sources`
    - reason: two sources present but only one carries an extractable suite count
- `surface-guard-001` label=`negative` outcome=`tn` expected_suggestion=`false` actual_suggestion=`false` expected_confidence=`—` actual_confidence=`—` surface_state=`insufficient_sources`
    - reason: single source present must stay silent by scope guard
- `surface-guard-002` label=`negative` outcome=`tn` expected_suggestion=`false` actual_suggestion=`false` expected_confidence=`—` actual_confidence=`—` surface_state=`insufficient_sources`
    - reason: single phase closure source present must stay silent by scope guard

## Reminder

- Each emitted suggestion is advisory only; `human_review_required` is always `true`.
- This report is derived and non-authoritative; it must never be consumed as canonical runtime state.
