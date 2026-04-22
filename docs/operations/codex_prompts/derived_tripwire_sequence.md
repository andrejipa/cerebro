# CODEX PROMPT — derived-tripwire sequence executor

## CTX
WD: `d:\projetos_cli\cerebro`
ROOT := CWD for all path ops
READ-ONLY to you: `core/`, `cli/`, `tests/` (except `experiments/*/tests/`)
OPEN to you: `experiments/`, `docs/operations/`

## SYMBOLS
- `MNL` := `docs/operations/<SLICE>_TRIPWIRE_MANUAL.md`
- `SIG` := `docs/operations/OPERATIONAL_INSUFFICIENCY_SIGNALS.md`
- `STS` := `docs/operations/SYSTEM_STATE.md`
- `OMP` := `docs/operations/OPPORTUNITY_MAP.md`

## ORDER
- s1 = broken-refs → `BROKEN_REFS_TRIPWIRE_MANUAL.md`
- s2 = surface-drift → `SURFACE_DRIFT_TRIPWIRE_MANUAL.md` [if exists else STOP]
- s3 = supersedes → `SUPERSEDES_TRIPWIRE_MANUAL.md` [if exists else STOP]

## PARTIAL STATE (s1, hint; always verify via idempotency scan)
- `rules.py`: `detect_broken_canonical_refs` + `_normalize_markdown_target` + `_resolve_markdown_target` + `_is_in_canonical_scope` + `_broken_ref_confidence` DONE; `FAILURE_MODES` includes `CONTEXT_NOT_FOUND`
- `dataset_broken_refs.toml`: DONE (11 cases)
- REMAINING: `evaluate.py` registry, tests, reports, doc updates, suite, commit
- RESUME AT: step (c) — finish impl (evaluate + tests) then continue

## PER-SLICE PROTOCOL

(a) read MNL

(b) idempotency scan — if rule in `rules.py` AND dataset present AND reports present → skip to (e); else continue from earliest missing artifact

(c) impl ONLY files listed in MNL `Arquivos` — touching any other file → STOP

(d) gates (all green before proceeding):
```
python -m unittest discover -s experiments/operational_signals/suggestions/tests -v
python -m unittest discover -s tests -v
python -m unittest tests.test_architecture -v
```

(e) harness:
```
python -m experiments.operational_signals.suggestions.evaluate --rule <rule-name>
```
expected verdict on curated dataset: `accept_for_staged_promotion`
write `report_<slice>_latest.{md,json}` at path from MNL

(f) external validation (if MNL prescribes) — run against real corpora listed in MNL; write `report_external_validation_<slice>.md`
`marginal` | `narrow-scope-validated` = VALID outcomes, NOT failures

(g) canonical doc updates: `SIG` (new round section) + `STS` + `OMP`

(h) full suite:
```
python -m unittest discover -s tests -v
```
record delta; no regression

(i) commit (local only):
- tag := `derived-tripwire-<slice>`
- msg := `<tag>: <descr> — N testes`

(j) report block; then next slice

## REPORT BLOCK
```
ITERAÇÃO [<tag>] — <descr> — NÍVEL [1]
MODO: [EXECUÇÃO]
AGENTES: [Orchestrator / Reviewer / Verifier]
RESULTADO: [concluído | parcial | bloqueado]
EVIDÊNCIA: [<paths>]
SUÍTE: [<before> → <after>, 0 falhas]
VERDICT: [accept_for_staged_promotion | narrow-scope-validated | marginal | reject]
VALIDAÇÃO EXTERNA: [executada | n/a | falhou]
ROLLBACK: [não]
OPPORTUNITY_MAP: [<1-line note>]
```

## AUTHORIZATION

WRITE allowed:
- files listed in each MNL
- `STS`, `OMP`, `SIG`
- local commits in tag pattern above

WRITE PROHIBITED:
- any file outside MNL + canonical docs above
- `core/`, `cli/`, `tests/` (except `experiments/*/tests/`)
- any path inside `.cerebro/`
- git: `amend`, `force-push`, `rebase -i`, `push` to remote
- rule expansion beyond MNL-declared scope
- skipping external validation when MNL requires it
- promoting a slice with verdict=`reject`

ON PROHIBITED HIT → STOP + report + await operator

## INVARIANTS (every new rule)
- `authority = "derived-advisory-only"`
- `human_review_required = True`
- no import from `core/` or `cli/`
- no write to `.cerebro/`
- `FIXED_EVAL_TIMESTAMP` in harness
- reuse existing helpers: `SUITE_RESULT_RE`, `classify_confidence`, `_id_fragment`, `Suggestion`
- zero duplication

## STOP CONDITIONS (global)
- 3 slices done + committed + reported
- next MNL missing
- irrecoverable gate failure
- out-of-scope decision needed

## TOKEN ECONOMY
- no prose between steps
- one report block per slice (no intermediate narrative)
- ask only on PROHIBITED hit
