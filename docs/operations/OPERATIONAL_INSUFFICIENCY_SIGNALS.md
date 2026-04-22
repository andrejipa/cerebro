# Operational Insufficiency Signals

## Purpose

`experiments/operational_signals/` is an experimental, derived, non-authoritative, opt-in, observability-only layer for recording when the current approved operational surface was not sufficient cleanly.

It exists to improve the quality of evidence used in freeze review and future `Formal Resume Trigger` discussions.

It does **not**:

- alter runtime behavior
- alter `analyze`, `validate`, `apply`, `verify`, or `checkpoint`
- write inside `.cerebro/`
- create canonical state
- decide whether growth is authorized
- act as project truth

## What Counts As An Insufficiency Signal

Signals should be recorded only when the insufficiency is operationally relevant, for example:

- continuity could not be recovered cleanly through `analyze` plus approved exports
- multiple extra files had to be opened manually to answer one need
- the wrong source was selected first and had to be replaced
- stale or ambiguous information forced explicit manual arbitration
- the current export surface was not sufficient for the task without repeated workaround

Generic friction or casual exploration is not enough by itself.

## Registry

The default registry lives at:

- `experiments/operational_signals/unmet_use_cases.toml`

That registry is:

- derived
- non-authoritative
- append-only by intent
- outside `.cerebro/`
- prohibited from being consumed as canonical state

## Closed Vocabularies

### failure_mode

- `CONTEXT_NOT_FOUND`
- `CONTEXT_AMBIGUOUS`
- `EXCESSIVE_MANUAL_SEARCH`
- `WRONG_SOURCE_SELECTED`
- `STALE_INFORMATION`
- `INSUFFICIENT_EXPORT_SURFACE`
- `DISCOVERY_COST_TOO_HIGH`

### confidence

- `low`
- `medium`
- `high`

## Candidate Trigger Rule

`candidate_trigger=true` is derived automatically only when all of the following are true:

- `repeat_count >= 2`
- `confidence != low`
- `trigger_score >= 0.55`

`trigger_score` is computed from:

- severity of `failure_mode`
- operational cost:
  - `minutes_spent`
  - `extra_files_opened`
  - `manual_search_rounds`
- recurrence signal from `repeat_count`
- declared confidence

This flag is not a growth authorization. It is only a review signal.

## Manual Logging

Example:

```bash
python -m experiments.operational_signals.cli log ^
  --project-context demo-project ^
  --task-description "recover current approved path" ^
  --query-or-need "where is the approved entrypoint" ^
  --surface-used analyze status-export ^
  --failure-mode EXCESSIVE_MANUAL_SEARCH ^
  --manual-workaround "opened README and CHECKLIST manually" ^
  --minutes-spent 12 ^
  --extra-files-opened 5 ^
  --manual-search-rounds 3 ^
  --repeat-count 2 ^
  --evidence README.md CHECKLIST.md ^
  --confidence medium
```

## Reading Reports

Available derived views:

- `python -m experiments.operational_signals.cli view --format md`
- `python -m experiments.operational_signals.cli report --format json`
- `python -m experiments.operational_signals.cli stats --by failure_mode --format json`

Use them to inspect:

- counts by project
- counts by `failure_mode`
- top repeated events
- candidate trigger signals
- aggregate cost

Do not read these reports as proof that the runtime is wrong. Read them as evidence that an operational review may be needed.

## Freeze Review Use

This layer may support a future freeze review only when:

- signals are repeated
- the workaround is explicit
- the operational cost is non-trivial
- the insufficiency is clearly against the current approved operational surface

Even then, the review must still follow the existing Resume Protocol in `docs/operations/FREEZE_POLICY.md`.

## Advisory Tripwires (derived suggestions)

A separate sub-layer lives at `experiments/operational_signals/suggestions/`. It hosts derived tripwire rules that inspect static artifacts and propose insufficiency records; it never writes those records on its own.

What the sub-layer is:

- derived, read-only, non-authoritative, opt-in, advisory-only
- a generator of `Suggestion` objects, each carrying `human_review_required = true`
- evaluated rule-by-rule against hand-labelled datasets with explicit checked-in verdict reports; `detect_stale_system_state` keeps the original `dataset.toml` / `report_latest.md`, while later slices use rule-specific `dataset_*` / `report_*_latest` pairs

What the sub-layer is not:

- canonical runtime state
- a substitute for manual logging described above
- a gate on any runtime operation
- a decision to register an insufficiency record
- a growth authorization

A suggestion only becomes a registered record when a human reviews it and deliberately invokes the manual logging path. Rejection is equally valid and leaves the registry untouched. Suggestions and registered records must be reported separately and never merged implicitly.

Current scope (round 2a):

- one tripwire: `detect_stale_system_state` — emits `STALE_INFORMATION` when a `SYSTEM_STATE.md`-shaped artifact carries divergent `Last suite result` counts across its canonical sections
- conservative thresholds: no suggestion under an absolute drift of 5; low/medium/high confidence tied to drift magnitude
- verdict on the 13-case evaluation dataset: `accept_for_staged_promotion`

Current scope (round 2b):

- second tripwire: `detect_export_surface_gap` — emits `INSUFFICIENT_EXPORT_SURFACE` only when a source artifact declares a structured `## Required Export Anchors` section with at least two bullet anchors and none of those anchors appear in captured export outputs
- conservative thresholds: the rule stays silent when the anchor section is absent, when exports were not captured, when only one anchor was declared, or when any required anchor is already present in the exports
- verdict on the 11-case evaluation dataset: `accept_for_staged_promotion`

Current scope (round 2c):

- third tripwire: `detect_broken_canonical_refs` — emits `CONTEXT_NOT_FOUND` only when a markdown source artifact inside `docs/operations/` points to a local path that does not exist
- conservative thresholds: the rule stays silent outside `docs/operations/`, ignores `http://`, `https://`, `mailto:`, and fragment-only links, and normalizes angle-bracket targets, fragments, line suffixes, `%20`, and slash-prefixed Windows absolute paths before checking existence
- verdict on the 11-case evaluation dataset: `accept_for_staged_promotion`

Current scope (round 2d):

- fourth tripwire: `detect_current_surface_drift` — emits `CONTEXT_AMBIGUOUS` only when the current four-doc canonical surface (`README.md`, `SYSTEM_STATE.md`, `OPPORTUNITY_MAP.md`, `PHASE_CLOSURE.md`) exposes at least two extractable `Last suite result` counts and those counts drift by at least `5`
- conservative thresholds: the rule stays silent when fewer than two docs are present, when fewer than two docs expose an extractable `Last suite result`, or when the max pairwise drift stays below `5`
- verdict on the 10-case evaluation dataset: `accept_for_staged_promotion`

Current scope (round 2e):

- fifth tripwire: `detect_supersedes_mechanical_metadata` — emits `CONTEXT_AMBIGUOUS` only when an operator-facing markdown/text artifact exposes `supersedes=...` or `stale_parallel_approach_consolidation_record` without nearby `winner=` plus `decision:` or `basis:`
- conservative thresholds: the rule strips inline-code and fenced-code examples before scanning, stays silent outside operator-facing markdown/text scope, and excludes intentional `out_of_scope` cases from confusion-matrix metrics instead of treating them as true negatives
- verdict on the 10-case evaluation dataset: `accept_for_staged_promotion`

The five tripwires remain a measured sanity check, not a claim of generalisation. Their datasets are author-curated and exist to prove that the tripwires can be built conservatively without creating automatic authority.

The third tripwire stays inside the same discipline: it is advisory-only, human-reviewed, and intentionally narrow to one canonical documentation surface.

Available derived reports now include:

- `experiments/operational_signals/suggestions/report_latest.md` / `.json` for `detect_stale_system_state`
- `experiments/operational_signals/suggestions/report_broken_refs_latest.md` / `.json` for `detect_broken_canonical_refs`
- `experiments/operational_signals/suggestions/report_export_surface_latest.md` / `.json` for `detect_export_surface_gap`
- `experiments/operational_signals/suggestions/report_surface_drift_latest.md` / `.json` for `detect_current_surface_drift`
- `experiments/operational_signals/suggestions/report_supersedes_latest.md` / `.json` for `detect_supersedes_mechanical_metadata`

Promotion to wider use still requires:

- one tripwire at a time
- an explicit labelled dataset per tripwire
- precision and recall that clear the conservative harness thresholds
- separate human review before any suggestion is converted into a manual record

## External Validation Status

The five measured rules in the suggestion layer were later checked against real, non-curated artifacts from:

- the Cerebro docs themselves
- `estoque_pioneira`
- `rpg_caminhada`
- `Resolução Humaita Codex`
- `IRPF e Caixa Rural`

That external validation produced a mixed five-rule result:

- `detect_stale_system_state` stayed valid, but only for a narrow structural pattern
- `detect_broken_canonical_refs` validated narrowly on `docs/operations/`
- `detect_export_surface_gap` did not validate on the real corpus; it stayed silent because the required-anchor structure used by the rule is not present in normal project documentation
- `detect_current_surface_drift` stayed conservative and narrow/Cerebro-specific
- `detect_supersedes_mechanical_metadata` stayed conservative and narrow/Cerebro-specific

Current external-validation interpretation:

- keep `detect_stale_system_state` as a narrow advisory rule
- keep `detect_broken_canonical_refs` as a narrow `docs/operations/` advisory rule
- do not treat `detect_export_surface_gap` as externally validated
- keep `detect_current_surface_drift` as a narrow Cerebro-specific advisory rule
- keep `detect_supersedes_mechanical_metadata` as a narrow Cerebro-specific advisory rule, with JSON deferred until the harness can evaluate structured objects instead of raw text serialization
- do not expand the suggestion layer further until a new rule can prove value on non-curated artifacts without depending on author-invented structure

For `detect_broken_canonical_refs`, the external-validation result on 2026-04-21 is intentionally scoped:

- curated dataset verdict: `accept_for_staged_promotion`
- external validation verdict: `narrow-scope-validated`
- in-scope corpus (`docs/operations/`): `28` markdown files scanned, `1` true positive found
- out-of-scope corpora (`IRPF e Caixa Rural`, `estoque_pioneira`, `rpg_caminhada`, `Resolução Humaita Codex`): `4478` markdown files scanned, `0` emissions

That result validates the rule as a canonical-docs guardrail, not as a broad corpus detector.

For `detect_current_surface_drift`, the external-validation result on 2026-04-21 is intentionally narrower:

- curated dataset verdict: `accept_for_staged_promotion`
- external validation verdict: `narrow-Cerebro-specific`
- real Cerebro cases checked: working tree plus commits `47802bf`, `65b16e5`, `2e9e95f`, `942756f`
- observed live pattern: all five cases had the four docs present, but only `1/4` docs exposed an extractable `Last suite result`, so the rule stayed silent in every case
- external corpora (`IRPF e Caixa Rural`, `estoque_pioneira`, `rpg_caminhada`, `Resolução Humaita Codex`): no comparable four-doc surface, `0` emissions

That result keeps the slice as a measured inter-file detector, but shows that the live canonical surface does not yet expose the comparable field broadly enough for frequent real use.

- external report: `experiments/operational_signals/suggestions/report_external_validation_surface_drift.md`

For `detect_supersedes_mechanical_metadata`, the external-validation result on 2026-04-21 is likewise intentionally narrow:

- curated dataset verdict: `accept_for_staged_promotion`
- external validation verdict: `narrow-Cerebro-specific`
- `docs/operations/`: `29` markdown/text artifacts scanned, `0` emissions
- external corpora (`IRPF e Caixa Rural`, `estoque_pioneira`, `rpg_caminhada`, `Resolução Humaita Codex`): `5145` markdown/text artifacts scanned, `0` emissions
- live `status-export` validation in this workspace could not run because `.cerebro/state.json` is absent

That result keeps the slice as a measured detector for a very specific Cerebro export style, but not as evidence of broad corpus coverage.

- external report: `experiments/operational_signals/suggestions/report_external_validation_supersedes.md`

## Rule Design Heuristic

For measured tripwires in `experiments/`, prefer signals that are:

- artifact-native
- binary or near-binary
- directly observable in the inspected artifact

Avoid rules that depend on:

- inferring operator intent
- inferring a need that is only implicit
- author-invented structure that does not appear in normal project artifacts

Why this heuristic exists:

- `detect_stale_system_state` held up because it measured an explicit contradiction inside one artifact
- `detect_export_surface_gap` did not validate on the real corpus because it depended on a structured anchor section and on inferring what the operator "should" have needed from exports

How to apply it:

- use it only for rule and dataset design in derived experiments
- do not generalize it into `core/` or `cli/`
- if a candidate tripwire cannot be expressed in artifact-native, directly observable terms, treat that as a design warning and re-evaluate before measuring it

A subsequent directory-wide read-only scan across those same four real-project roots inspected `6163` text-like files and produced:

- `0` `STALE_INFORMATION` hits
- `0` `INSUFFICIENT_EXPORT_SURFACE` hits

That wider scan does not falsify the earlier narrow true positive on Cerebro's own `SYSTEM_STATE.md`; it does reinforce that the current rules have negligible coverage on the four external corpora and therefore remain insufficient as a broader suggestion layer.

The external-validation report is recorded in:

- `experiments/operational_signals/suggestions/report_external_validation.md`
- `experiments/operational_signals/suggestions/report_external_validation_broken_refs.md`

The closure decision for the current suggestion layer is recorded in:

- [OPERATIONAL_SIGNALS_SUGGESTIONS_CLOSURE.md](/d:/projetos_cli/cerebro/docs/operations/OPERATIONAL_SIGNALS_SUGGESTIONS_CLOSURE.md)
