# Operational Insufficiency Suggestions — Tripwire Evaluation

- authority: `derived-advisory-only`
- schema_version: `1`
- non_authoritative: `true`
- read_only: `true`
- rule: `detect_stale_system_state`
- evaluated_at: `2026-04-20T00:00:00Z`

## Metrics

- dataset cases: `13`
- total cases: `13`
- excluded cases: `0`
- true positives: `6`
- false positives: `0`
- true negatives: `7`
- false negatives: `0`
- precision: `1.0000`
- recall: `1.0000`
- F1: `1.0000`
- confidence checks: `6`
- confidence match rate: `1.0000`

## Verdict

- classification: `accept_for_staged_promotion`
- rationale: precision and recall clear the conservative acceptance bar; rule is safe for opt-in derived use pending a second tripwire before any wider adoption

## Per-Case Outcomes

- `pos-001` label=`positive` outcome=`tp` expected_suggestion=`true` actual_suggestion=`true` expected_confidence=`high` actual_confidence=`high`
    - reason: real drift observed in SYSTEM_STATE.md: 730 current vs 550 gate
- `pos-002` label=`positive` outcome=`tp` expected_suggestion=`true` actual_suggestion=`true` expected_confidence=`medium` actual_confidence=`medium`
    - reason: medium drift of 20 tests across sections
- `pos-003` label=`positive` outcome=`tp` expected_suggestion=`true` actual_suggestion=`true` expected_confidence=`medium` actual_confidence=`medium`
    - reason: drift at the medium threshold boundary (diff=10)
- `pos-004` label=`positive` outcome=`tp` expected_suggestion=`true` actual_suggestion=`true` expected_confidence=`high` actual_confidence=`high`
    - reason: reverse drift: gate reports more than current; still stale evidence
- `pos-005` label=`positive` outcome=`tp` expected_suggestion=`true` actual_suggestion=`true` expected_confidence=`high` actual_confidence=`high`
    - reason: extreme drift, classic stale-history signal
- `pos-006` label=`positive` outcome=`tp` expected_suggestion=`true` actual_suggestion=`true` expected_confidence=`low` actual_confidence=`low`
    - reason: borderline low-confidence drift at exactly the MIN threshold (diff=5)
- `neg-001` label=`negative` outcome=`tn` expected_suggestion=`false` actual_suggestion=`false` expected_confidence=`—` actual_confidence=`—`
    - reason: both sections agree exactly
- `neg-002` label=`negative` outcome=`tn` expected_suggestion=`false` actual_suggestion=`false` expected_confidence=`—` actual_confidence=`—`
    - reason: drift below the conservative threshold (diff=1)
- `neg-003` label=`negative` outcome=`tn` expected_suggestion=`false` actual_suggestion=`false` expected_confidence=`—` actual_confidence=`—`
    - reason: drift below the conservative threshold (diff=3)
- `neg-004` label=`negative` outcome=`tn` expected_suggestion=`false` actual_suggestion=`false` expected_confidence=`—` actual_confidence=`—`
    - reason: only Current Snapshot present; no cross-section evidence of drift
- `neg-005` label=`negative` outcome=`tn` expected_suggestion=`false` actual_suggestion=`false` expected_confidence=`—` actual_confidence=`—`
    - reason: only Gate Status present; no cross-section evidence of drift
- `neg-006` label=`negative` outcome=`tn` expected_suggestion=`false` actual_suggestion=`false` expected_confidence=`—` actual_confidence=`—`
    - reason: no recognisable canonical sections; numbers appear in prose only
- `neg-007` label=`negative` outcome=`tn` expected_suggestion=`false` actual_suggestion=`false` expected_confidence=`—` actual_confidence=`—`
    - reason: sections present but no `Last suite result` line anywhere

## Reminder

- Each emitted suggestion is advisory only; `human_review_required` is always `true`.
- This report is derived and non-authoritative; it must never be consumed as canonical runtime state.
