# Broken Refs Tripwire Manual

## Status

- `implemented on 2026-04-21`
- `measured on curated dataset`
- `externally validated as narrow-scope-validated`
- `not promoted`

This document now records the implemented contract for the
`detect_broken_canonical_refs` slice under
`experiments/operational_signals/suggestions/`.
It still does not authorize widening the suggestion layer by itself.

## Why This Candidate Exists

The current suggestion layer learned two different lessons:

- `detect_stale_system_state` validated because it measured an explicit,
  artifact-native contradiction
- `detect_export_surface_gap` materialized but did not validate on the real
  corpus because it depended on inferring operator intent and on structure that
  normal project artifacts do not carry

The resulting heuristic now governing candidate tripwires is:

- prefer signals that are artifact-native
- prefer signals that are binary or near-binary
- prefer signals that are directly observable in the inspected artifact
- avoid rules that depend on inferring operator intent or implicit need

Broken canonical markdown references fit that heuristic.

## Slice Goal

Add one narrow advisory rule that detects broken markdown references inside
`docs/operations/` and suggests `CONTEXT_NOT_FOUND` when a canonical document
points to a local path that does not exist.

This slice is intentionally narrow:

- it is for markdown links only
- it is for `docs/operations/` only
- it checks path existence only
- it is advisory-only and must remain non-authoritative

## Defaults

| Point | Default |
|---|---|
| Ref scope | markdown `[text](path)` |
| Ignored refs | `http://`, `https://`, `mailto:`, fragment-only `#...` |
| Canonical scope | `docs/operations/` only |
| Check | resolved-path existence only |
| `failure_mode` | `CONTEXT_NOT_FOUND` |

## Intended Files

- `experiments/operational_signals/suggestions/rules.py`
- `experiments/operational_signals/suggestions/dataset_broken_refs.toml`
- `experiments/operational_signals/suggestions/evaluate.py`
- `experiments/operational_signals/suggestions/tests/test_rules.py`
- `experiments/operational_signals/suggestions/tests/test_harness.py` if needed
- `docs/operations/OPERATIONAL_INSUFFICIENCY_SIGNALS.md`
- `docs/operations/SYSTEM_STATE.md`
- `docs/operations/OPPORTUNITY_MAP.md`

## Rule Shape

```python
def detect_broken_canonical_refs(
    *, source_artifact: str, text: str,
    project_context: str = "cerebro",
    now: datetime | None = None,
) -> Suggestion | None:
```

The rule should mirror the existing suggestion-rule contract:

- frozen dataclass output
- `FIXED_EVAL_TIMESTAMP` compatible
- `human_review_required = True`
- `authority = AUTHORITY`
- no writes
- no imports from `core/` or `cli/`

## Algorithm

### 1. Scope Guard

```python
CANONICAL_SCOPE = Path("docs/operations")
source_posix = Path(source_artifact).as_posix()
if CANONICAL_SCOPE.as_posix() not in source_posix:
    return None
```

This is an intentional `out_of_scope` silence, not a true negative.

### 2. Extract Markdown Links

Regex:

```text
\[([^\]]+)\]\(([^)]+)\)
```

### 3. Ignore Only These Categories

- `http://...`
- `https://...`
- `mailto:...`
- fragment-only targets beginning with `#`

Everything else goes through normalization.

### 4. Normalize Target

Apply in this fixed order:

1. strip angle brackets: `<path>` -> `path`
2. strip fragment: `path#anchor` -> `path`
3. strip trailing line suffix: `path:\d+$` -> `path`
4. decode `%20` -> literal space
5. if absolute: resolve as-is
6. if relative: resolve against `Path(source_artifact).parent`

### 5. Check Existence

For each normalized target:

- if it exists: ignore
- if it does not exist: collect as broken

### 6. Emit or Stay Silent

- if `len(broken) == 0`: return `None`
- else emit a suggestion with:
  - `suggested_failure_mode = CONTEXT_NOT_FOUND`
  - `reason_flags = ("broken_canonical_ref_detected",)`
  - `supporting_signals = tuple(f"broken_ref={t}" for _, t in broken)`

### 7. Confidence

- `1` broken ref -> `low`
- `2` to `3` broken refs -> `medium`
- `4+` broken refs -> `high`

Minimum threshold:

- `MIN_ABSOLUTE_BROKEN = 1`

## Reporting Semantics

Reports must distinguish three states:

- `out_of_scope`
- `in_scope_clean`
- `in_scope_broken`

Interpretation:

- `out_of_scope` silence is intentional and must not be counted as a true negative
- `in_scope_clean` silence is a true negative
- `in_scope_broken` emission is a true positive or false positive depending on the label

## Dataset

Minimum:

- `10` cases
- balanced
- same TOML schema shape already used by the suggestion harness

Per-case fields:

- `id`
- `label`
- `label_reason`
- `text`
- `expected_confidence` for positives
- optional `source_path` for realistic relative resolution

Mandatory guard cases:

- valid link with `:12` suffix -> silence after normalization
- valid link with `#anchor` -> silence after normalization
- broken absolute path -> emit
- source outside `docs/operations/` -> `out_of_scope` silence

## Tests Required

- detects a real broken markdown link inside `docs/operations/`
- stays silent on a valid link
- stays silent on external URL and `mailto:`
- stays silent when no markdown links exist
- confidence tier follows broken-ref count
- contract guards:
  - no imports from `core/` or `cli/`
  - no writes in `.cerebro/`

## Validation Expectations

### Local Harness

Thresholds should inherit the current conservative harness defaults:

- `ACCEPT_PRECISION = 0.70`
- `ACCEPT_RECALL = 0.60`
- `ITERATE_PRECISION = 0.60`

Expected target verdict:

- `accept_for_staged_promotion`

### External Validation

External validation must still run, but its purpose is narrower here.

Run against:

- `docs/operations/` in this repository
- at least two external real corpora already used by the repo:
  - `IRPF e Caixa Rural`
  - `estoque_pioneira`
  - `rpg_caminhada`
  - `Resolução Humaita Codex`

Required reports:

- `report_broken_refs_latest.md`
- `report_broken_refs_latest.json`
- `report_external_validation_broken_refs.md`

Interpretation:

- this rule is intentionally narrow by scope
- external validation mainly measures:
  - real precision
  - absence of out-of-scope emissions
- it does **not** primarily measure broad corpus coverage outside `docs/operations/`

If external validation fails:

- classify as `marginal` or `not validated`
- do not promote
- do not expand

That is a valid result of the protocol, not a debt.

## Invariants

- `authority = "derived-advisory-only"`
- `human_review_required = True`
- never write in `.cerebro/`
- never import `core/` or `cli/`
- keep `FIXED_EVAL_TIMESTAMP` compatibility

## Sequencing Rule

If this slice is executed, the agreed priority order remains:

1. `#4 broken refs`
2. `#1 schema drift`
3. `#3 supersedes mechanical metadata`
4. `#2 hypothesis ledger`

## Stop Criterion

This slice is only complete when all are true:

- code and tests implemented
- suite gate green
- architecture gate green
- external validation executed and reported
- verdict recorded in canonical docs
- operator explicitly accepts the result

If validation fails:

- close as non-validated
- keep the evidence
- do not expand the layer

## Implemented Result

Implemented files:

- `experiments/operational_signals/suggestions/rules.py`
- `experiments/operational_signals/suggestions/dataset_broken_refs.toml`
- `experiments/operational_signals/suggestions/evaluate.py`
- `experiments/operational_signals/suggestions/tests/test_rules.py`
- `experiments/operational_signals/suggestions/tests/test_harness.py`

Measured result on 2026-04-21:

- curated dataset verdict: `accept_for_staged_promotion`
- dataset size: `11`
- evaluated cases: `11`
- precision / recall / F1: `1.0 / 1.0 / 1.0`

External validation result on 2026-04-21:

- classification: `narrow-scope-validated`
- `docs/operations/`: `28` markdown files scanned, `1` in-scope true positive
- external corpora (`estoque_pioneira`, `rpg_caminhada`, `IRPF e Caixa Rural`, `Resolução Humaita Codex`): `4478` markdown files scanned, `0` out-of-scope emissions
