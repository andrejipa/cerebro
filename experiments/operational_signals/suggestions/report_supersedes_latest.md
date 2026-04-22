# Operational Insufficiency Suggestions — Tripwire Evaluation

- authority: `derived-advisory-only`
- schema_version: `1`
- non_authoritative: `true`
- read_only: `true`
- rule: `detect_supersedes_mechanical_metadata`
- evaluated_at: `2026-04-20T00:00:00Z`

## Metrics

- dataset cases: `10`
- total cases: `8`
- excluded cases: `2`
- true positives: `5`
- false positives: `0`
- true negatives: `3`
- false negatives: `0`
- precision: `1.0000`
- recall: `1.0000`
- F1: `1.0000`
- confidence checks: `5`
- confidence match rate: `1.0000`
- supersedes out_of_scope cases: `2`
- supersedes in_scope_contextualized cases: `3`
- supersedes in_scope_mechanical_only cases: `5`

## Verdict

- classification: `accept_for_staged_promotion`
- rationale: precision and recall clear the conservative acceptance bar; rule is safe for opt-in derived use pending a second tripwire before any wider adoption

## Per-Case Outcomes

- `supersedes-pos-001` label=`positive` outcome=`tp` expected_suggestion=`true` actual_suggestion=`true` expected_confidence=`low` actual_confidence=`low` supersedes_state=`in_scope_mechanical_only`
    - reason: mechanical supersedes token without nearby rationale should emit low confidence
- `supersedes-pos-002` label=`positive` outcome=`tp` expected_suggestion=`true` actual_suggestion=`true` expected_confidence=`medium` actual_confidence=`medium` supersedes_state=`in_scope_mechanical_only`
    - reason: stale replay with decision but no winner remains ambiguous and should emit medium confidence
- `supersedes-pos-003` label=`positive` outcome=`tp` expected_suggestion=`true` actual_suggestion=`true` expected_confidence=`medium` actual_confidence=`medium` supersedes_state=`in_scope_mechanical_only`
    - reason: two ambiguous supersedes tokens in one operator-facing artifact should emit medium confidence
- `supersedes-pos-004` label=`positive` outcome=`tp` expected_suggestion=`true` actual_suggestion=`true` expected_confidence=`high` actual_confidence=`high` supersedes_state=`in_scope_mechanical_only`
    - reason: stale replay without winner or rationale should emit high confidence
- `supersedes-pos-005` label=`positive` outcome=`tp` expected_suggestion=`true` actual_suggestion=`true` expected_confidence=`high` actual_confidence=`high` supersedes_state=`in_scope_mechanical_only`
    - reason: three ambiguous supersedes hits should emit high confidence
- `supersedes-neg-001` label=`negative` outcome=`tn` expected_suggestion=`false` actual_suggestion=`false` expected_confidence=`—` actual_confidence=`—` supersedes_state=`in_scope_contextualized`
    - reason: contextualized status-export fragment already exposes winner and rationale nearby
- `supersedes-neg-002` label=`negative` outcome=`tn` expected_suggestion=`false` actual_suggestion=`false` expected_confidence=`—` actual_confidence=`—` supersedes_state=`in_scope_contextualized`
    - reason: conceptual prose about superseding does not contain a mechanical token and must stay silent
- `supersedes-neg-003` label=`negative` outcome=`excluded` expected_suggestion=`false` actual_suggestion=`false` expected_confidence=`—` actual_confidence=`—` supersedes_state=`out_of_scope`
    - reason: test fixtures mentioning supersedes metadata are intentional out_of_scope silence
- `supersedes-neg-004` label=`negative` outcome=`excluded` expected_suggestion=`false` actual_suggestion=`false` expected_confidence=`—` actual_confidence=`—` supersedes_state=`out_of_scope`
    - reason: derived reports stay out of scope even if they mention stale diagnostics
- `supersedes-neg-005` label=`negative` outcome=`tn` expected_suggestion=`false` actual_suggestion=`false` expected_confidence=`—` actual_confidence=`—` supersedes_state=`in_scope_contextualized`
    - reason: winner plus a nearby decision line is enough to keep the artifact contextualized

## Reminder

- Each emitted suggestion is advisory only; `human_review_required` is always `true`.
- This report is derived and non-authoritative; it must never be consumed as canonical runtime state.
