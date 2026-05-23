# Operational Insufficiency Suggestions — Tripwire Evaluation

- authority: `derived-advisory-only`
- schema_version: `1`
- non_authoritative: `true`
- read_only: `true`
- rule: `detect_broken_canonical_refs`
- evaluated_at: `2026-04-20T00:00:00Z`

## Metrics

- dataset cases: `11`
- total cases: `11`
- excluded cases: `0`
- true positives: `5`
- false positives: `0`
- true negatives: `6`
- false negatives: `0`
- precision: `1.0000`
- recall: `1.0000`
- F1: `1.0000`
- confidence checks: `5`
- confidence match rate: `1.0000`
- out_of_scope cases: `1`
- in_scope_clean cases: `5`
- in_scope_broken cases: `5`

## Verdict

- classification: `accept_for_staged_promotion`
- rationale: precision and recall clear the conservative acceptance bar; rule is safe for opt-in derived use pending a second tripwire before any wider adoption

## Per-Case Outcomes

- `docs/operations/synthetic-broken-001.md` label=`positive` outcome=`tp` expected_suggestion=`true` actual_suggestion=`true` expected_confidence=`low` actual_confidence=`low` scope_state=`in_scope_broken`
    - reason: one broken relative ref inside canonical scope should emit low confidence
- `docs/operations/synthetic-broken-002.md` label=`positive` outcome=`tp` expected_suggestion=`true` actual_suggestion=`true` expected_confidence=`medium` actual_confidence=`medium` scope_state=`in_scope_broken`
    - reason: two broken relative refs should emit medium confidence
- `docs/operations/synthetic-broken-003.md` label=`positive` outcome=`tp` expected_suggestion=`true` actual_suggestion=`true` expected_confidence=`high` actual_confidence=`high` scope_state=`in_scope_broken`
    - reason: four broken refs should emit high confidence
- `docs/operations/synthetic-broken-004.md` label=`positive` outcome=`tp` expected_suggestion=`true` actual_suggestion=`true` expected_confidence=`low` actual_confidence=`low` scope_state=`in_scope_broken`
    - reason: broken absolute path should emit
- `docs/operations/synthetic-broken-005.md` label=`positive` outcome=`tp` expected_suggestion=`true` actual_suggestion=`true` expected_confidence=`medium` actual_confidence=`medium` scope_state=`in_scope_broken`
    - reason: mixed link set still emits when two local refs remain broken
- `docs/operations/synthetic-clean-001.md` label=`negative` outcome=`tn` expected_suggestion=`false` actual_suggestion=`false` expected_confidence=`—` actual_confidence=`—` scope_state=`in_scope_clean`
    - reason: valid relative refs inside canonical scope should stay silent
- `docs/operations/synthetic-clean-002.md` label=`negative` outcome=`tn` expected_suggestion=`false` actual_suggestion=`false` expected_confidence=`—` actual_confidence=`—` scope_state=`in_scope_clean`
    - reason: line suffix is normalized away before existence check
- `docs/operations/synthetic-clean-003.md` label=`negative` outcome=`tn` expected_suggestion=`false` actual_suggestion=`false` expected_confidence=`—` actual_confidence=`—` scope_state=`in_scope_clean`
    - reason: anchor fragment is normalized away before existence check
- `docs/operations/synthetic-clean-004.md` label=`negative` outcome=`tn` expected_suggestion=`false` actual_suggestion=`false` expected_confidence=`—` actual_confidence=`—` scope_state=`in_scope_clean`
    - reason: external URLs, mailto, and fragment-only refs are ignored
- `docs/operations/synthetic-clean-005.md` label=`negative` outcome=`tn` expected_suggestion=`false` actual_suggestion=`false` expected_confidence=`—` actual_confidence=`—` scope_state=`in_scope_clean`
    - reason: artifacts without markdown links stay silent
- `docs/reference/synthetic-out-of-scope-001.md` label=`negative` outcome=`tn` expected_suggestion=`false` actual_suggestion=`false` expected_confidence=`—` actual_confidence=`—` scope_state=`out_of_scope`
    - reason: source outside docs/operations is intentional out_of_scope silence

## Reminder

- Each emitted suggestion is advisory only; `human_review_required` is always `true`.
- This report is derived and non-authoritative; it must never be consumed as canonical runtime state.
