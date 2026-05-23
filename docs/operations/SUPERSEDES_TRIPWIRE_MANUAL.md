# Supersedes Mechanical Metadata Tripwire Manual

## Status

- `implemented on 2026-04-21`
- `measured on curated dataset`
- `externally validated as narrow-Cerebro-specific`
- `not promoted`

This document now records the implemented v1 contract for the slice under
`experiments/operational_signals/suggestions/`.
It still does not authorize any widening of the suggestion layer by itself.

## Why This Candidate Exists

The current consolidation surface already exposes the right mechanical facts:

- repeated consolidation must explicitly supersede the current head
- stale or replayed valid consolidation records must be treated as history
- read-only consumers may surface lineage markers such as `supersedes=...` and
  `stale_parallel_approach_consolidation_record`

Those facts are operationally correct, but some artifacts can still become too
mechanical for fast human use if they expose lineage tokens without nearby
decision context.

This candidate exists to measure that narrow failure shape:

- mechanical supersession metadata is present
- human-readable decision context is absent or too thin
- the operator would still need manual lineage chasing to understand the state

That shape is artifact-native, binary enough to measure conservatively, and
stays within the advisory-only boundary.

## Slice Goal

Add one narrow advisory rule that detects operator-facing artifacts which expose
supersession lineage mechanically without the nearby human context needed to
understand the decision cleanly.

The rule should suggest `CONTEXT_AMBIGUOUS` only when:

- a supersession token is present in an operator-facing artifact
- the artifact does not also expose nearby decision context such as winner,
  compared set, or decision rationale

This slice is intentionally narrow:

- it is for operator-facing text artifacts only
- it is for consolidation-lineage metadata only
- it is advisory-only and must remain non-authoritative
- it does not judge whether the underlying runtime behavior is correct

## Defaults

| Point | Default |
|---|---|
| Artifact scope | operator-facing text only |
| Primary tokens | `supersedes=`, `stale_parallel_approach_consolidation_record` |
| Required context | `winner=...` plus either `decision:` or `basis:` nearby |
| Ignored mentions | conceptual prose about superseding, code/test fixtures, derived reports/datasets, core/runtime field names in implementation files |
| `failure_mode` | `CONTEXT_AMBIGUOUS` |

## Intended Files

- `experiments/operational_signals/suggestions/rules.py`
- `experiments/operational_signals/suggestions/dataset_supersedes.toml`
- `experiments/operational_signals/suggestions/evaluate.py`
- `experiments/operational_signals/suggestions/tests/test_rules.py`
- `experiments/operational_signals/suggestions/tests/test_harness.py` if needed
- `docs/operations/OPERATIONAL_INSUFFICIENCY_SIGNALS.md`
- `docs/operations/SYSTEM_STATE.md`
- `docs/operations/OPPORTUNITY_MAP.md`

## Rule Shape

```python
def detect_supersedes_mechanical_metadata(
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

Only inspect operator-facing text artifacts.

Conservative v1 guard:

- allow `.md`, `.txt`
- reject paths containing `/core/`, `/cli/`, `/tests/`, `__pycache__/`, or `experiments/operational_signals/suggestions/`
- reject empty text

This is intentional `out_of_scope` silence, not a true negative.

`.json` is deferred in v1. The repo does expose operator-facing JSON, but this
derived layer still evaluates plain text only; widening to JSON requires a
structured per-object harness instead of line-window heuristics over raw
serialization.

### 2. Detect Mechanical Supersession Tokens

Look for at least one of these patterns:

- ``supersedes=<id>``
- ``stale_parallel_approach_consolidation_record``

Conceptual prose such as "must explicitly supersede the current head" is not a
mechanical token and must stay silent.
Inline code spans and fenced code blocks must be stripped before scanning so
that manuals and backlogs do not self-trigger on documented examples.

### 3. Detect Nearby Human Context

Within a small local window around each token hit (same line plus the next two
non-empty lines), look for:

- `winner=`
- `decision:`
- `basis:`
- optionally `compared=` or `rejected=`

Required minimum for clean context:

- one winner signal
- one rationale signal (`decision:` or `basis:`)

### 4. Emit Or Stay Silent

- if no mechanical token is found: `None`
- if a token is found and clean nearby context is also found: `None`
- if a token is found and nearby context is missing: emit

Emit with:

- `suggested_failure_mode = CONTEXT_AMBIGUOUS`
- `reason_flags = ("mechanical_supersedes_metadata",)`
- `supporting_signals` including the matched token and which context fields were
  missing

### 5. Confidence

- one ambiguous token -> `low`
- two ambiguous tokens or one stale-record token -> `medium`
- three or more ambiguous tokens, or stale-record token plus missing winner and
  rationale -> `high`

Minimum threshold:

- `MIN_ABSOLUTE_MECHANICAL_SUPERSEDES = 1`

## Reporting Semantics

Reports must distinguish three states:

- `out_of_scope`
- `in_scope_contextualized`
- `in_scope_mechanical_only`

Interpretation:

- `out_of_scope` silence is intentional and must not be counted as a true
  negative
- `in_scope_contextualized` silence is a true negative
- `in_scope_mechanical_only` emission is a true positive or false positive
  depending on the label

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
- `source_path`
- `expected_confidence` for positives
- `count_in_metrics = false` for intentional `out_of_scope` guard cases

Mandatory guard cases:

- status-export style line with `winner=...; supersedes=...; compared=...` plus
  following `decision:` -> silence
- stale diagnostic line without winner or rationale -> emit
- prose sentence "must explicitly supersede the current head" -> silence
- implementation or test path containing `supersedes_consolidation_id` ->
  `out_of_scope` silence
- derived report path containing stale diagnostics -> `out_of_scope` silence

## Tests Required

- emits on a mechanical `supersedes=` token with no nearby human context
- emits on stale-record diagnostics with no nearby winner/rationale
- stays silent on a fully contextualized status-export fragment
- stays silent on conceptual prose about superseding
- stays silent outside operator-facing artifact scope
- confidence tier follows ambiguous-token count
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

External validation must still run, but its purpose is narrow here.

Run against:

- `docs/operations/` in this repository
- operator-facing markdown/text artifacts already exported by the repo when available
- at least two external real corpora already used by the repo:
  - `IRPF e Caixa Rural`
  - `estoque_pioneira`
  - `rpg_caminhada`
  - `Resolução Humaita Codex`

Required reports:

- `report_supersedes_latest.md`
- `report_supersedes_latest.json`
- `report_external_validation_supersedes.md`

Interpretation:

- this rule is intentionally Cerebro-leaning
- external validation mainly measures:
  - absence of out-of-scope emissions
  - whether the mechanical-without-context pattern appears at all in real
    artifacts
- a result of `narrow-Cerebro-specific`, `marginal`, or `not validated` is a
  valid outcome, not a debt

If external validation fails:

- keep the evidence
- classify it explicitly
- do not promote
- do not expand

## Implemented Result

Implemented files:

- `experiments/operational_signals/suggestions/rules.py`
- `experiments/operational_signals/suggestions/harness.py`
- `experiments/operational_signals/suggestions/evaluate.py`
- `experiments/operational_signals/suggestions/dataset_supersedes.toml`
- `experiments/operational_signals/suggestions/tests/test_rules.py`
- `experiments/operational_signals/suggestions/tests/test_harness.py`
- `experiments/operational_signals/suggestions/tests/test_contract_boundaries.py`

Measured result on 2026-04-21:

- curated dataset verdict: `accept_for_staged_promotion`
- dataset size: `10`
- evaluated cases: `8`
- excluded `out_of_scope` cases: `2`
- precision / recall / F1: `1.0 / 1.0 / 1.0`

External validation result on 2026-04-21:

- classification: `narrow-Cerebro-specific`
- `docs/operations/`: `29` text artifacts scanned, `0` emissions
- external corpora (`estoque_pioneira`, `rpg_caminhada`, `IRPF e Caixa Rural`, `Resolução Humaita Codex`): `5145` text artifacts scanned, `0` emissions
- live `status-export` validation in this workspace could not run because `.cerebro/state.json` is absent

## Invariants

- `authority = "derived-advisory-only"`
- `human_review_required = True`
- never write in `.cerebro/`
- never import `core/` or `cli/`
- keep `FIXED_EVAL_TIMESTAMP` compatibility

## Sequencing Rule

If this slice is executed, it remains one narrow candidate only.
Do not bundle it with any additional tripwire.

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
