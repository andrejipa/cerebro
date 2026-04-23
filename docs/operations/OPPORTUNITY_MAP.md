# Opportunity Map

## Current Snapshot — 2026-04-23

- Suite gate is currently green in this shell: `840` tests, `0` failures, `6` skips via the exact AGENTS-equivalent workspace-local-temp runner; this is the live source of truth for the shell.
- Architecture gate confirmed green: `51` tests, `0` failures via `python -m unittest tests.test_architecture -v`.
- Derived `recall_eval` validation remains green after the latest slice: `49` tests, `0` failures in `experiments/recall_eval/tests`.
- Derived `operational_signals` base validation is green after the latest overlapping-writer lock hardening: `31` tests, `0` failures in `experiments/operational_signals/tests`.
- Derived `operational_signals/suggestions` validation is green after the latest temp-root hardening: `97` tests, `0` failures in `experiments/operational_signals/suggestions/tests`.
- Current posture: deliberate freeze remains active for speculative canonical-runtime growth; the latest user-directed session closed the narrow P4 workspace-path resolution slice, and one new formal resume trigger is now active for the validation-decomposition campaign only.
- `BUG_REPORT.md` and `PHASE_CLOSURE.md` now open with explicit current snapshots that mark their remaining body as historical evidence by default, reducing residual-intake ambiguity during heartbeat triage.
- Planning-only `StateStore` decomposition prep is now recorded in `docs/operations/STATESTORE_DECOMPOSITION_PLAN.md`; it stays explicitly non-authoritative and does not reopen the freeze.
- `docs/operations/observation_center.toml` now carries the structured unresolved-work queue; the heartbeat should reconcile and consume that center before falling back to the narrative snapshot fields below, and the markdown snapshots should now be treated as projections of that queue rather than as the primary scheduler surface.
- Live heartbeat authority order is now explicit: `AGENTS.md -> active triggers -> observation_center.toml -> SYSTEM_STATE.md -> OPPORTUNITY_MAP.md -> active plans -> code/tests`; if those surfaces diverge, the next round must reconcile first instead of implementing.
- Current executable queue:
  - `the tests-only coverage tranche completed without touching core/ or cli/`
  - `direct P5 coverage now exists for decision_runtime, action_identity, discipline_runtime, state_runtime_lock_service, state_session_artifacts_service, and state_retention_service`
  - `the structural P4 workspace-path resolution drift between action_runtime and discipline_runtime is now resolved through core/workspace_paths.py plus module-local wrappers and proportional regression`
  - `the validation-decomposition trigger is now active with a strict whitelist: core/validation.py plus tests/test_validate_error_ordering.py only`
  - `the characterization-oracle commit is now complete: tests/test_validate_error_ordering.py pins 14 per-block payloads plus 1 mixed aggregate-order case`
  - `slice 1 is now complete: _validate_memory_block was extracted in core/validation.py with the ordering oracle still green`
  - `slice 2 is now complete: _validate_execution_policy_block was extracted in core/validation.py with the ordering oracle still green`
  - `slice 3 is now complete: _validate_batch_registry_block was extracted in core/validation.py with the ordering oracle still green`
  - `experiments/operational_signals/suggestions remains marginal/audit-only by default; do not expand it without new operational evidence`
- Current queue mode: autonomous corrective validation-decomposition slice loop; slice 3 is complete, slices `4-11` should continue automatically one per round while gates stay green, and the campaign must pause again before slice `12`.
- Active heartbeat protocol hardening now uses formal stage-1 scout-renewal controls: exact and structural quiet-signature repetition are banned, weak or paper-only renewal no longer resets exhaustion, and self-stop now requires the full renewal ladder plus a confirmation wakeup.
- Current next item: `execute slice 4 (_validate_command_registry_block) under the active validation-decomposition whitelist`
- The canonical `SCOUT_CONTROL_STATE` now lives only in `SYSTEM_STATE.md`; this map carries only the minimal next-action projection for heartbeat routing.
- Active heartbeat protocol: `docs/operations/codex_prompts/cerebro_heartbeat_loop.md` now explicitly keeps two safe non-growth lanes under freeze, but reclassifies them as secondary fillers; the loop must refresh code-first scout coverage in `experiments/recall_eval`, `experiments/operational_signals`, and cross-cutting artifact parity before treating docs/planning work as a dominant quiet wakeup again.
- Gate authority: `AGENTS.md` and the pinned heartbeat contract are aligned on the same workspace-local equivalent runner; the raw `python -m unittest discover -s tests -v` command is not authoritative in this shell because of the Windows `tempfile.mkdtemp(..., 0o700)` behavior.
- Formal resume trigger consumed: `FORMAL_RESUME_TRIGGER_CORE_PATH_RESOLUTION.md`; that slice ended green with `825` tests, `0` failures, `6` skips plus a green `tests.test_architecture` gate.
- Formal resume trigger active: `FORMAL_RESUME_TRIGGER_VALIDATION_DECOMPOSITION.md`; authorized scope is limited to `core/validation.py`, `tests/test_validate_error_ordering.py`, and closeout updates in `docs/operations/`.
- Future local-first improvement note: the observation center now records a blocked follow-on item for a SQLite ledger promotion, but no trigger is open for that migration today.
- Historical ledger note: the detailed derived-fix chronology and prior queue states remain preserved below under an explicit historical heading; the snapshot above is the only live operational reference.

## NEXT_ACTION

```text
NEXT_ACTION
- next_required_step: execute_validation_slice_4_command_registry_block
- observation_center_head: validation-slice-4-command-registry
- active_renewal_debt: none while the canonical gate stays green
- highest_priority_hypothesis: slices `1-3` stayed green without ordering drift, so the automation should continue with `_validate_command_registry_block` and then advance one slice per round through slice `11/14` unless a halt condition appears; no extra human checkpoint is expected before slice `12/14`
```

## Historical Derived Chronology

- A later proof-of-stop slice on 2026-04-22 then closed the first canonical P1 findings in the runtime itself: execution-policy blocking now normalizes path-qualified command heads like `/bin/rm` and `C:\...\powershell.exe`, approvals are now bound to action kind, fingerprint, task, and target across apply/verify/rollback/validation, and the legacy blank-`task_id` approval path now survives only for the single-executable-task fallback instead of remaining broadly reusable.
- A later proof-of-stop continuation on 2026-04-22 then closed the remaining single-file apply transaction gap in canonical runtime: `cli.commands.apply` now routes the one-action path through `core.action_runtime.execute_apply_cycle()`, which revalidates state and persists the action under the runtime lock before the slice commits, and direct regression now proves that a late `record_agent_action()` rejection rolls the workspace back instead of leaving an unrecorded mutation behind.
- A later proof-of-stop continuation on 2026-04-22 then closed the next reliability slice in canonical runtime: partial `runtime.lock` acquisitions now clean up leaked descriptors and lock files when owner-pid persistence fails, malformed lock payloads are reclaimed only after they age past the acquisition grace window, and `discard_session()` now clears an orphan `session.local.json` residue without a token only when the external claim authority is already gone.
- A later canonical-runtime consolidation on 2026-04-22 then closed the remaining mapped fingerprint drift: `core/action_identity.py` now owns exec-command binding signatures, normalized action fingerprint digests, retry-identity matching, and action-signature extraction, so action, discipline, and decision layers reuse one identity contract instead of carrying subtly separate helpers.
- A later heartbeat wakeup on 2026-04-22 then seeded the first canonical quiet-scout signature in `SCOUT_CONTROL_STATE`, but the mandatory post-edit AGENTS-equivalent gate turned red inside frozen canonical `tests/`: `test_validate_state_recovers_pending_session_refresh_after_crash_before_state_save` failed, and the subsequent focused rerun reproduced the blocker in a different shape as a host-temp `PermissionError` under raw `tempfile.TemporaryDirectory()`, so the queue stayed in blocked-escalation instead of continuing quiet scout rotation.
- A later governance hardening on 2026-04-22 then completed the stage-2 scout-control split: `SYSTEM_STATE.md` now carries the canonical `SCOUT_CONTROL_STATE`, while this map was reduced to a minimal `NEXT_ACTION` projection so heartbeat routing no longer depends on duplicated control prose.
- The same wakeup also corrected the live gate again to the currently verified `730` tests, `0` failures, `8` skips result from the exact AGENTS-equivalent runner; the interim `730/0/6` wording had become documentary drift against the shell-authoritative command.
- A later governance hardening on 2026-04-22 then replaced the loose heartbeat quiet-renewal rules with the formal stage-1 scout-renewal model: quiet repetition is now checked by exact, structural, and functional equivalence; the renewal ladder and minimum-delta requirements are explicit; debate and prompt-hardening can be owed rather than silently skipped; and self-stop now requires both formal exhaustion and a confirmation wakeup.
- A later heartbeat wakeup on 2026-04-22 then closed a remaining overlapping-writer rollback race in the base `experiments/operational_signals/report.py` boundary: partial writers that touched only one artifact of the `report_latest` family now share the same family lock as the paired `md+json` writer, so a failing paired write can no longer roll back stale markdown over a newer successful partial write to the same `signals.md`.
- A later heartbeat wakeup on 2026-04-22 then closed the remaining host-temp harness drift in `experiments/operational_signals/suggestions/tests`: the marginal advisory test layer now uses workspace-local tempdirs instead of raw `tempfile.TemporaryDirectory()`, removing the Windows host-temp `PermissionError` failures from dataset, writer, and outside-`cwd` rule coverage and restoring the focused suggestions suite to `97` tests and `0` failures.
- A later heartbeat wakeup on 2026-04-22 then reduced authority-surface noise in `BUG_REPORT.md` and `PHASE_CLOSURE.md`: both docs now start with an explicit current snapshot that marks their long body as archival evidence unless something is explicitly reopened, so heartbeat triage no longer has to infer that purely from historical wording alone.
- A later heartbeat wakeup on 2026-04-22 then closed the remaining host-temp harness drift in the base `experiments/operational_signals/tests` boundary: those tests now use workspace-local tempdirs instead of raw `tempfile.TemporaryDirectory()`, removing the Windows host-temp `PermissionError` failures from the derived registry/report suites and restoring the focused base suite to `30` tests and `0` failures.
- A later heartbeat wakeup on 2026-04-22 then corrected a gate-authority drift in the live snapshot itself: the exact AGENTS-equivalent runner reconfirmed the shell-authoritative `730` tests with `0` failures and cleared the false blocked-escalation that had been inferred from the non-authoritative raw `python -m unittest discover -s tests -v` command on this Windows shell.
- A later heartbeat wakeup on 2026-04-22 then closed the concurrent latest-writer rollback race in `experiments/recall_eval/report.py` and hardened the entire derived `experiments/recall_eval/tests` harness to use workspace-local tempdirs instead of raw `tempfile.TemporaryDirectory()`, bringing that derived suite to `49` tests and `0` failures; the same wakeup then entered blocked-escalation when the mandatory raw AGENTS gate exposed `730` tests with `558` errors inside frozen canonical `tests/`, dominated by host-temp `PermissionError` failures on this Windows shell.
- A later governance hardening on 2026-04-22 then made the pinned heartbeat contract code-first again: docs/planning filler no longer dominates twice in a row while the active derived boundaries lack fresh executable scout coverage, and exhaustion now requires renewed code-first passes across `experiments/recall_eval`, `experiments/operational_signals`, and cross-cutting artifact parity before auto-stop.
- A later heartbeat rerun on 2026-04-22 had temporarily re-established the live gate as `730` tests, `0` failures, `6` skips; a subsequent exact AGENTS-equivalent rerun superseded that reading and confirmed the current shell truth as `730` tests, `0` failures, `8` skips.
- A later quiet scout on 2026-04-22 then closed the remaining path-hygiene drift in `experiments/operational_signals/suggestions/report_external_validation.md`: external corpus entries now use stable root-relative labels instead of workspace-local absolute roots.
- A later quiet scout on 2026-04-22 then closed a factual governance drift in `docs/operations/IMPLEMENTATION_STATUS.md`: its active `Current Live Gate` header now reflects the verified AGENTS-equivalent runner result for this shell rather than a stale documentary carry-over.
- A later quiet scout on 2026-04-22 then closed the remaining host-path drift in `experiments/operational_signals/suggestions/report_external_validation_surface_drift.md`: the external corpora list now uses stable corpus labels instead of workspace-local absolute roots.
- A later quiet scout on 2026-04-22 then closed a concurrent latest-writer rollback race in `experiments/recall_eval/report.py`: the Round 2 `json/md` pair now serializes write plus rollback under one sibling lock, so a failing writer can no longer restore stale artifacts over a newer successful run.
- A later quiet scout on 2026-04-22 then closed a derived artifact path-hygiene drift in the checked-in external-validation reports: `report_external_validation_broken_refs.md` and `report_external_validation_supersedes.md` no longer expose workspace-local absolute paths in corpus listings, supporting signals, or missing-state reasoning, so those non-authoritative artifacts stay portable across hosts.
- The documented `broken refs` candidate was then executed on 2026-04-21: `detect_broken_canonical_refs` is now implemented in `experiments/operational_signals/suggestions/`, its curated dataset cleared `accept_for_staged_promotion`, and the external-validation result is `narrow-scope-validated`.
- That external result is intentionally narrow and explicit:
  - `docs/operations/`: `28` markdown files scanned, `1` in-scope true positive
  - external corpora (`IRPF e Caixa Rural`, `estoque_pioneira`, `rpg_caminhada`, `Resolução Humaita Codex`): `4478` markdown files scanned, `0` out-of-scope emissions
- A later proof-of-stop continuation on 2026-04-21 then hardened `detect_broken_canonical_refs` against `cwd` drift: local markdown targets are still reported as stable repo-relative paths, but existence is now checked against a repo-root anchor instead of the process working directory, so the curated dataset remains `accept_for_staged_promotion` even when evaluated outside the repository root.
- The documented `surface drift` candidate was then executed on 2026-04-21: `detect_current_surface_drift` is now implemented in `experiments/operational_signals/suggestions/`, its curated dataset cleared `accept_for_staged_promotion`, and the external-validation result is `narrow-Cerebro-specific`.
- That external result is also intentionally narrow and explicit:
  - real Cerebro states checked: working tree plus commits `47802bf`, `65b16e5`, `2e9e95f`, `942756f`
  - observed live pattern: all five cases had the four docs present, but only `1/4` docs exposed an extractable `Last suite result`, so the rule stayed silent in every case
  - external corpora (`IRPF e Caixa Rural`, `estoque_pioneira`, `rpg_caminhada`, `Resolução Humaita Codex`): no comparable four-doc surface, `0` emissions
- A later proof-of-stop continuation on 2026-04-21 narrowed `detect_current_surface_drift` to live current-snapshot carriers only: `README` and `PHASE_CLOSURE` no longer count as current-surface peers, the curated dataset/report were regenerated, and the refreshed boundary now clears `accept_for_staged_promotion` with `2` true positives, `8` true negatives, `0` false positives, and `0` false negatives.
- The documented `supersedes mechanical metadata` candidate was then executed on 2026-04-21: `detect_supersedes_mechanical_metadata` is now implemented in `experiments/operational_signals/suggestions/`, its curated dataset cleared `accept_for_staged_promotion`, and the external-validation result is `narrow-Cerebro-specific`.
- That result remains explicitly narrow:
  - curated dataset: `10` cases total, `8` counted, `2` intentional `out_of_scope` exclusions, `0` false positives, `0` false negatives
  - `docs/operations/`: `29` markdown/text artifacts scanned, `0` emissions
  - external corpora (`IRPF e Caixa Rural`, `estoque_pioneira`, `rpg_caminhada`, `Resolução Humaita Codex`): `5145` markdown/text artifacts scanned, `0` emissions
  - live `status-export` validation in this workspace could not run because `.cerebro/state.json` is absent
- A later proof-of-stop rerun on 2026-04-21 found and closed a derived-layer correctness bug in the same slice: `detect_supersedes_mechanical_metadata` could emit colliding `suggestion.id` values when two source paths shared the same truncated artifact fragment; the rule now adds stable entropy from the full `source_artifact`, the supersedes dataset regained unique ids, and `report_supersedes_latest.json` was regenerated.
- The same continuation then closed three follow-on proof items in the same derived/documentary boundary: `P3 report write atomicity` (report pairs now roll back together on second-write failure), `P5 latest-report parity` (checked-in `report_*_latest` files now match the current renderer and are guarded by test), and `P4 tripwire manual normalization` (the `broken refs` and `surface drift` manuals no longer pretend those slices are only documented).
- A later derived continuation on 2026-04-21 closed the `P1 lexical query precompute` hotspot in `experiments/recall_eval`: query-side weighting/norm preparation now happens once per `retrieve_lexical()` call and is reused across chunks, while the legacy scorer entrypoint remains as a compatibility wrapper.
- The same continuation then closed the next proof findings in the same derived boundary: `recall_eval` benchmark reports now write `.json` and `.md` as one rollback-safe pair, persisted Round 2 JSON omits the host-specific `temp_root`, persisted `dataset_path` is now normalized to the stable relative reference `recall_eval/eval_dataset.yaml`, duplicate `query.id` values within one project now fail closed during dataset loading, and the Round 2 failure-analysis/cache path no longer aliases results by raw `query.id` alone.
- Another proof-of-stop fix in the sibling derived boundary `experiments/operational_signals/` made `report_latest.md` and `report_latest.json` rollback-safe as one pair as well, so an interrupted second write no longer leaves split-brain `latest` artifacts there.
- A later proof-of-stop continuation hardened the rollback path itself in both derived report writers: `recall_eval` and `operational_signals` now restore previous sibling artifacts with atomic writes, attempt both restores even if the first restore fails, and raise loudly instead of silently leaving one `latest` artifact advanced while the other stays stale.
- The same continuation also closed the next derived performance hotspot in `experiments/recall_eval`: semantic chunk vectors are now precomputed in the index and reused by `retrieve_semantic()`, so the benchmark no longer rebuilds chunk-side sparse embeddings inside the per-query hot path.
- A later proof-of-stop continuation closed the remaining rollback-path gap in `experiments/operational_signals/suggestions/`: its report writer now attempts both restores even when the first restore fails, raises loudly with `ExceptionGroup` if rollback stays incomplete, and the focused `suggestions/tests` suite now covers that exact split-brain path.
- The same continuation also serialized the `operational_signals` registry append cycle itself: `record_unmet_use_case()` now holds a sibling lock across `load -> append -> write`, so concurrent writers no longer lose entries or fail mid-append against the same derived registry file.
- The regression surface for those boundaries now covers both correctness and artifact integrity: `experiments/recall_eval/tests` passes with `26` tests and `0` failures, `experiments/operational_signals/tests` passes with `18` tests and `0` failures, `experiments/operational_signals/suggestions/tests` passes with `87` tests and `0` failures, and the snapshots/docs no longer expose live-sounding headings inside the preserved historical documenter-only appendix.
- A full rerun of `python -m experiments.recall_eval.evaluate` now completes inside the old `304s` shell window in this workspace again, refreshed `report_round2_latest.*`, and preserved the stable `dataset_path` / `temp_root` fields in the checked-in JSON artifact.
- A later proof-of-stop continuation on 2026-04-21 then closed the remaining rerun rebuild hotspot in `experiments/recall_eval`: project indexes now persist as reusable derived caches outside project roots, keyed by content-derived source signatures plus a builder fingerprint, cached payloads omit raw project/cache roots, and semantic vector buckets are now deterministic across process hash seeds so persisted vectors stay valid across reruns.
- The live path is now explicitly proven in this workspace: the first full `python -m experiments.recall_eval.evaluate` run after the slice took `324s`, the immediate rerun with the same corpus completed in `37s`, both runs produced the same aggregate metrics, and `report_round2_latest.*` was refreshed through the cache-backed path.
- The regression surface for that boundary now covers cache correctness as well: `experiments/recall_eval/tests` passes with `33` tests and `0` failures, including direct coverage for cache hit reuse, source invalidation, builder-fingerprint invalidation, host-path hygiene, `evaluate_dataset()` cache reuse, and deterministic semantic buckets across different `PYTHONHASHSEED` values.
- A later proof-of-stop continuation on 2026-04-21 then closed the remaining legacy artifact drift in `experiments/recall_eval`: the old `report_latest.md/json` pair no longer looks live, now acts only as an explicit historical tombstone that points to `report_round2_latest.*`, and regression coverage now fails if a legacy `latest` payload grows live metrics or omits the supersession marker.
- The drift mattered because the legacy JSON still exposed absolute `dataset_path` and host-specific `temp_root`, while the live Round 2 artifact had already normalized both; that mismatch is now removed from the visible legacy pair instead of being left side-by-side as a human-facing false signal.
- The regression surface for that boundary now passes with `34` tests and `0` failures, including the explicit guard that any preserved `report_latest.*` pair must be historical-only and must point at the Round 2 outputs.
- A later proof-of-stop continuation on 2026-04-21 then closed the remaining focused regression gap in `experiments/recall_eval/analysis/failure_report.py`: direct coverage now proves that same `query.id` values in different projects do not alias each other inside failure analysis, so the earlier keyed-by-`(project_name, query_id)` hardening is no longer only indirectly covered.
- The regression surface for that boundary now passes with `35` tests and `0` failures, including a dedicated `failure_report` test that would have gone false-green under the older raw-`query.id` keying.
- A later proof-of-stop continuation on 2026-04-21 then closed a derived recovery gap in `experiments/operational_signals/logger.py`: the registry lock now writes owner metadata, reclaims stale `.lock` files from dead processes before timing out, and direct regression proves that a persisted orphaned lock no longer blocks the next writer indefinitely.
- The regression surface for that sibling boundary now passes with `19` tests and `0` failures, including a dedicated stale-lock recovery test in `experiments/operational_signals/tests/test_logger.py`.
- A later proof-of-stop continuation on 2026-04-21 then hardened that same derived lock recovery against PID reuse: lock metadata now carries process identity when available, recovery distinguishes a recycled PID from the original owner instead of trusting `pid alive` alone, and direct regression proves that a mismatched live identity is reclaimed while a matching live identity still blocks.
- The regression surface for that sibling boundary now passes with `21` tests and `0` failures in `experiments/operational_signals/tests`, including dedicated guards for stale-lock recovery after PID reuse and for preserving a truly live matching owner.
- A later proof-of-stop continuation on 2026-04-21 then closed a derived reporting bug in `experiments/operational_signals/suggestions/evaluate.py`: broken-ref scope annotation now derives `scope_state` from `source_path`, which is the real artifact boundary already normalized by the harness, and direct regression proves that synthetic case ids no longer misclassify in-scope docs artifacts as out-of-scope.
- The regression surface for that sibling boundary now passes with `88` tests and `0` failures in `experiments/operational_signals/suggestions/tests`, including a dedicated `source_path` vs `id` scope-annotation guard.
- A later proof-of-stop continuation on 2026-04-21 then closed the remaining direct rollback-coverage gap in the same boundary: `write_reports()` now has explicit regression coverage for the `previous_text is None` cleanup path, proving that a second-write failure removes freshly created `report.md/json` outputs instead of leaving orphaned partial artifacts behind.
- The regression surface for that boundary now passes with `89` tests and `0` failures in `experiments/operational_signals/suggestions/tests`, including a dedicated fresh-output cleanup guard for the rollback delete path.
- A later proof-of-stop continuation on 2026-04-21 then closed the remaining cache-hit pre-signature reread hotspot in `experiments/recall_eval`: reusable index-cache hits now resolve from a metadata inventory signature before source recollection, cached payloads persist that inventory for fail-closed reuse checks, and the builder fingerprint is cached in-process so the helper modules are not reread on every project build.
- The live path stayed proven in this workspace after that slice: an isolated cold-cache `evaluate_dataset()` run took `292.324s`, and the immediate hot rerun against the same temporary cache completed in `33.429s`.
- The regression surface for that boundary now passes with `37` tests and `0` failures in `experiments/recall_eval/tests`, including direct guards that a warm cache hit skips `_collect_source_artifacts()` and that `_builder_fingerprint()` rereads its builder inputs only once per process.
- A later fresh proof-of-stop cycle on 2026-04-21 then closed the remaining warm-hit tree-scan hotspot in the same boundary: cached project indexes are now loaded through a stable per-project cache entry, validate file and directory metadata from the persisted inventories before reuse, and skip both `_iter_candidate_files()` and `_build_source_inventory()` on a clean warm hit.
- The isolated index-build path stayed proven in this workspace after that slice: the real-project cold pass took `285.137s`, and the immediate hot pass against the same temporary cache completed in `25.573s`; the full `evaluate_dataset()` rerun for the same cache measured `292.913s` cold and `33.082s` hot, showing that query evaluation now dominates most of the remaining rerun wall time after index reuse.
- The regression surface for that boundary now passes with `38` tests and `0` failures in `experiments/recall_eval/tests`, including direct guards that a warm cache hit skips tree rescans and that adding a new file inside a previously empty tracked directory invalidates the cache fail-closed.
- A later proof-of-stop continuation on 2026-04-21 then closed the remaining live-artifact host-root drift in `experiments/recall_eval`: persisted `projects[*].root` now keeps only a stable root label instead of an absolute host path, direct regression covers the writer path, and `report_round2_latest.json` was regenerated through the report writer without rerunning the full benchmark.
- The regression surface for that boundary now passes with `39` tests and `0` failures in `experiments/recall_eval/tests`, including a dedicated guard that `write_reports()` strips host-specific `projects[*].root` values from the persisted Round 2 JSON artifact.
- A later proof-of-stop continuation on 2026-04-21 then closed a derived hybrid-ranking bug in `experiments/recall_eval/query_runner.py`: variant `D` now requests semantic candidates with `_semantic_candidate_limit(top_k)` instead of the narrower lexical limit, so the hybrid path no longer silently trims semantic breadth before reranking.
- The regression surface for that boundary now passes with `40` tests and `0` failures in `experiments/recall_eval/tests`, including a dedicated guard that variant `D` passes the semantic candidate limit to `retrieve_semantic()`.
- A later corrective rerun on 2026-04-21 then closed the remaining semantic-breadth truncation inside that same slice: variant `D` had started requesting `_semantic_candidate_limit(top_k)` from `retrieve_semantic()`, but it still sliced the returned list back to `lexical_limit` before `merge_candidates()`, which kept the best semantic-only hits beyond the lexical cap out of the hybrid reranker. `_rank_variant()` now passes the full bounded semantic candidate list into the merge step, and the focused regression asserts the broader semantic funnel instead of the old truncated call shape.
- A later proof-of-stop continuation on 2026-04-21 then closed a derived canonical-scope bug in `detect_broken_canonical_refs`: in-scope matching now uses path-segment boundaries instead of a raw substring check, so sibling paths like `docs/operationsX/...` no longer count as canonical operations docs.
- The regression surface for that sibling boundary now passes with `90` tests and `0` failures in `experiments/operational_signals/suggestions/tests`, including a dedicated guard that prefix-sharing sibling paths stay out of scope.
- A later fresh proof-of-stop cycle on 2026-04-21 then closed a derived first-use race in `experiments/operational_signals/logger.py`: `initialize_registry()` now rechecks existence under the same sibling lock already used by `record_unmet_use_case()`, so a concurrent first `log` call can no longer append a real record and then lose it to a delayed empty-registry initializer.
- The regression surface for that sibling boundary now passes with `22` tests and `0` failures in `experiments/operational_signals/tests`, including a dedicated guard that a blocked first empty write keeps the concurrent record write out until initialization finishes and preserves the first recorded signal.
- A later fresh proof-of-stop cycle on 2026-04-21 then closed a derived validation-report false-green in `experiments/operational_signals/suggestions/evaluate.py`: broken-ref scope annotation now reuses the same canonical-scope boundary as the rule, so prefix-sharing siblings like `docs/operationsX/...` no longer inflate `in_scope_clean` metrics or undercount `out_of_scope`.
- The regression surface for that sibling boundary now passes with `91` tests and `0` failures in `experiments/operational_signals/suggestions/tests`, including a dedicated guard that prefix-sharing sibling paths stay `out_of_scope` in the report metrics as well as in the rule itself.
- A later fresh proof-of-stop cycle on 2026-04-21 then closed the remaining direct rollback-coverage gap in `experiments/operational_signals/report.py`: the sibling boundary already deleted fresh outputs on rollback, and it now has an explicit regression proving that a second-write failure with no previous `signals.md/json` leaves no orphan artifacts behind.
- The regression surface for that sibling boundary now passes with `23` tests and `0` failures in `experiments/operational_signals/tests`, including a dedicated guard that freshly created `signals.md/json` are removed when the second report write fails before either artifact had a previous version.
- A later fresh proof-of-stop cycle on 2026-04-21 then closed two more derived registry gaps in `experiments/operational_signals/schema.py`: forbidden-path detection now rejects case variants of `.cerebro` on case-insensitive filesystems, and `atomic_write_registry()` now cleans its `*.tmp` sibling artifact both when the final replace fails and when the temporary-file write itself fails before replace, so the advisory layer no longer writes under a case-aliased canonical directory or leaks orphan temp files on failed writes.
- The regression surface for that sibling boundary now passes with `26` tests and `0` failures in `experiments/operational_signals/tests`, including dedicated guards for `.CEREBRO` alias rejection, failed-replace temp cleanup, and failed-temp-write cleanup.
- A later fresh proof-of-stop cycle on 2026-04-21 then closed the remaining direct rollback-coverage gap in `experiments/recall_eval/report.py`: the rollback branch for freshly created `report.md/json` outputs is now exercised directly, proving that a second-write failure on a first run removes both fresh artifacts instead of leaving a partial pair behind.
- The regression surface for that boundary now passes with `41` tests and `0` failures in `experiments/recall_eval/tests`, including a dedicated fresh-output cleanup guard in `test_benchmark.py`.
- A later fresh proof-of-stop cycle on 2026-04-21 then closed the remaining bounded-ranking hotspot in `experiments/recall_eval/retrievers/`: lexical and semantic retrieval now keep only a bounded top-k heap before the final sort, so reruns no longer full-sort every positive hit just to discard most of them at `candidate_k`.
- The regression surface for that boundary now passes with `42` tests and `0` failures in `experiments/recall_eval/tests`, including a direct semantic tie/candidate-limit guard alongside the existing lexical one.
- A later fresh proof-of-stop cycle on 2026-04-21 then closed a derived path-hygiene false-green in `experiments/recall_eval/report.py`: persisted Round 2 artifacts now redact host-specific absolute paths that appear inside nested result excerpts, including truncated backticked paths that run to end-of-string and angle-bracketed markdown link targets like `[spec](<D:/...>)`, so `report_round2_latest.json` no longer leaks local filesystem roots through corpus-derived evidence text.
- The regression surface for that boundary now passes with `43` tests and `0` failures in `experiments/recall_eval/tests`, including a dedicated nested-excerpt redaction guard in `test_benchmark.py` that now covers both raw absolute paths and angle-bracketed link targets; the checked-in `report_round2_latest.json` was regenerated through the report writer and no longer contains raw `D:\\...` or `/home/...` excerpts.
- A later proof-of-stop continuation on 2026-04-21 then closed the remaining batch-latest integrity gap in `experiments/operational_signals/suggestions`: all-rules evaluation now computes every rule before persistence and batch-rolls back earlier `*_latest` report pairs if a later write fails, so one failing rule can no longer leave the suggestions latest set in a mixed state.
- The regression surface for that sibling boundary now passes with `92` tests and `0` failures in `experiments/operational_signals/suggestions/tests`, including a dedicated guard that `main([])` restores earlier per-rule latest reports when a later batch write fails.
- A later proof-of-stop continuation on 2026-04-21 then closed the remaining concurrent-rollback race across the derived `latest` writers: `experiments/operational_signals/report.py` now holds a pair-scoped sibling lock across write plus rollback, while `experiments/operational_signals/suggestions/evaluate.py` now shares one family lock between single-rule writes and all-rules batch writes, so a stale rollback snapshot can no longer overwrite a newer successful `latest` artifact from another writer in flight.
- The regression surface for those sibling boundaries now passes with `27` tests and `0` failures in `experiments/operational_signals/tests` and `96` tests and `0` failures in `experiments/operational_signals/suggestions/tests`, including direct guards that the base report writer blocks a concurrent replacement until rollback finishes and that the suggestions batch writer shares the same lock domain as a concurrent single-rule writer.
- A later corrective slice on 2026-04-21 then closed a derived observability bug in `experiments/operational_signals/cli.py`: read-only `view`, `stats`, and `report` commands no longer create `signals.toml` as a filesystem side effect when the registry does not exist, so the advisory CLI now respects its read-only boundary and relies on the existing empty-registry fallback in `schema.py` instead of materializing state during observation.
- The regression surface for that sibling boundary now passes with `28` tests and `0` failures in `experiments/operational_signals/tests`, including a dedicated guard that `operational-signals report --format json` against a missing registry returns an empty report without creating the registry file.
- A later web-assisted debate plus corrective slice on 2026-04-21 then closed a stronger derived boundary bug in `experiments/operational_signals`: derived report outputs are now rejected if they resolve anywhere under `.cerebro/`, so neither `report.py` nor `suggestions/evaluate.py` can materialize advisory artifacts inside the canonical runtime directory.
- That prioritization beat two weaker candidates in the same round: a docs-only drift cleanup and a `recall_eval` metric false-green. The winning slice enforced a stricter freeze boundary with lower blast radius, and the external rationale matched the same read-only/no-side-effects semantics described by RFC 9110 and the Azure MCP `readOnlyHint` guidance.
- The regression surface for that sibling boundary now passes with `29` tests and `0` failures in `experiments/operational_signals/tests` and `97` tests and `0` failures in `experiments/operational_signals/suggestions/tests`, including dedicated guards that both report writers fail closed on `.cerebro/` output targets without creating artifacts.
- A later bounded proof-of-stop continuation on 2026-04-21 then closed the deferred derived `recall_eval` metric false-green in `experiments/recall_eval/evaluate.py`: path-fragment matching now respects segment/identifier boundaries so substring siblings like `docs/not_readme.md` no longer satisfy `README.md`, and `recall_at_3` now counts only matches that land inside the top three instead of reporting success from a first hit at rank `4+`.
- The regression surface for that boundary now passes with `46` tests and `0` failures in `experiments/recall_eval/tests`, including dedicated guards for substring-sibling path false positives and for keeping `recall_at_3` at `0.0` when the first hit lands after the top-three cutoff.
- The same bounded proof-of-stop continuation on 2026-04-21 then closed a sibling derived view/reporting false-green in `experiments/operational_signals`: `operational-signals view` now recomputes `totals`, grouped aggregates, `candidate_triggers`, and `top_repeaters` from the already filtered record subset instead of mixing one filtered `records` list with global metrics.
- The regression surface for that sibling boundary now passes with `30` tests and `0` failures in `experiments/operational_signals/tests`, including a dedicated guard that `view --project alpha --format json` emits only `alpha` records and `alpha` aggregates.
- A later heartbeat scout on 2026-04-22 then closed a derived shell-local temp-root failure in `experiments/recall_eval`: the benchmark helpers now choose a safe derived temp/cache base first and create per-run temp roots without raw `tempfile.mkdtemp()`, so `evaluate_dataset()` no longer dies early with `PermissionError` in this Windows sandbox before it can write index manifests.
- The regression surface for that boundary now passes with `48` tests and `0` failures in `experiments/recall_eval/tests`, including direct guards that `build_experiment_temp_root()` no longer calls raw `tempfile.mkdtemp()` and that the reusable cache-root chooser skips a tempdir candidate that would fall inside a project root.
- Current next derived item: `none by default — the known derived queue is clean again; the loop should stay in quiet iterative scout/stress/renew mode across approved derived boundaries until the next bounded defect is reproduced or repeated renewed passes prove there is nothing left worth keeping the automation alive for`
- The manual stop is now resolved and the slice is closed with evidence; that does not reopen suggestion-layer expansion by itself.
- The same proof-of-stop rerun also closed a documentary drift in the suggestion-layer summary; the current snapshot is now internally aligned again.
- The separate experimental track `experiments/recall_eval/` has now been executed against real corpora and benchmarked in multiple variants; it remains derived, read-only, non-authoritative, and not accepted as product surface.
- Current weakness posture:
  - `CRÍTICO`: `0` open, `0` Group 6
  - `ALTO`: `0` open, `0` Group 6
- Latest hardening result:
  - `DÉBITO 3` (`verify` host-trusting) foi fechado com regressão explícita para leak de env, leak por segmento de `PATH`, helper chain mínima por comando resolvido e preservação de `C:` legítimo
  - `DÉBITO 2` (`check-state` sintético) foi fechado: `verification.state_check` ficou separado, `verification.checks` voltou a ser command-only e a migração legada ficou centralizada na canonicalização
  - `DÉBITO 1` (`approval` por efeito em `overwrite=true`) foi fechado: overwrite destrutivo real ou projetado agora exige approval explícito, sem fatigue nova para `create` benigno
  - a auditoria pós-hardening também fechou o bypass direto no boundary `apply_action()` e o escape em que `verify` conseguia mutar o live workspace fora do sandbox e ainda reportar verde
  - a prova de parada `P1-P5` terminou limpa; `P2` confirmou ausência de regressão nova, `P1` confirmou os três débitos não reproduzíveis e a varredura pós-hardening não deixou novo `CRÍTICO` ou `ALTO`
  - o drift entre `WEAKNESS_REPORT.md`, `SYSTEM_STATE.md` e `OPPORTUNITY_MAP.md` agora fica ancorado neste snapshot atual, que substitui as seções históricas documenter-only abaixo; essas seções permanecem apenas como trilha histórica, não como descrição do estado vivo do repositório

Bootstrap document created on 2026-04-16 for the autonomous loop.

## Historical Entry Gate

- Suite gate confirmed green: `550` tests, `0` failures, `6` skips via `python -m unittest discover -s tests -v`
- `docs/operations/SYSTEM_STATE.md` did not exist before this bootstrap
- `docs/operations/OPPORTUNITY_MAP.md` did not exist before this bootstrap
- `.cerebro/state.json` is absent in this workspace, so the current loop is documentary/bootstrap-oriented rather than an active runtime continuity round

## Historical Bootstrap Posture

- Freeze remains active: corrective maintenance and factual documentation are allowed; growth work stays blocked without a formal resume trigger
- No new mutating core slice is eligible right now under the current freeze posture
- The executable queue in this map is therefore limited to documentary reconciliation and formal closure work
- `WEAKNESS_REPORT.md` now carries one confirmed `CRÍTICO`, three confirmed `ALTO`, and multiple `MÉDIO`, but every mutating fix still requires `core/`, `cli/`, and `tests/` changes that are outside this documenter-only loop

## Historical Documentary Queue

### DOC-001 — Reconcile Documentary Drift

- Status: `done`
- Priority: `HIGH`
- Level: `1`
- Why it exists:
  - `BUG_REPORT.md` says the remaining corrective backlog is "dois residuos explicitos" but does not enumerate both, leaving residual intake ambiguous
  - `PHASE_CLOSURE.md` still closes the prior phase at `534` tests even though the current suite is `548`
  - `AGENTS.md` still shows a Unix-style `tail -5` snippet even though this repo runs under PowerShell
- Scope:
  - `docs/operations/BUG_REPORT.md`
  - `docs/operations/PHASE_CLOSURE.md`
  - `AGENTS.md`
- Done when:
  - residuals are explicit instead of implicit
  - the current documentary closure matches the post-Round-10 test count and status
  - the preflight suite command is portable to the declared shell
- Verify:
  - `python -m unittest discover -s tests -v`
- Result:
  - `BUG_REPORT.md` now names the accepted residuals explicitly
  - `PHASE_CLOSURE.md` now reflects the post-Round-10 `548`-test closure state
  - `AGENTS.md` now uses a PowerShell-portable preflight snippet

### DOC-002 — Proof Of Stop And Formal Re-Closure

- Status: `done`
- Priority: `MEDIUM`
- Level: `1`
- Depends on: `DOC-001`
- Why it exists:
  - after documentary reconciliation, the loop still needs an explicit stop-proof pass and refreshed closure record for the current frozen state
- Scope:
  - `docs/operations/PHASE_CLOSURE.md`
  - `docs/operations/SYSTEM_STATE.md`
  - `docs/operations/OPPORTUNITY_MAP.md`
- Done when:
  - the queue distinguishes executable items from blocked items cleanly
  - accepted residuals are named explicitly
  - the phase closure reflects the current green suite and current blocked items
- Verify:
  - `python -m unittest discover -s tests -v`
  - `python -m unittest tests.test_architecture -v`
- Result:
  - `P1`: no new eligible performance hotspot
  - `P2`: no new bypass surface beyond accepted residuals and freeze-blocked items
  - `P3`: no new recovery/failure scenario outside the accepted residual set
  - one subagent reported a red suite locally, but the focal rerun of `tests.test_state_store.StateStoreTests.test_open_session_restores_registry_and_external_artifacts_when_session_file_write_fails` passed in the main workspace
  - `P5` gap closed: `PHASE_CLOSURE.md` now sits inside the automated documentary proof perimeter through explicit guards in `tests/test_doc_governance.py` and `tests/test_architecture.py`
  - formal re-closure is no longer blocked by the proof-perimeter gap

### DOC-003 — Reconcile Helper Alias Drift

- Status: `done`
- Priority: `LOW`
- Level: `1`
- Depends on: `DOC-002`
- Why it exists:
  - the proof-of-stop `P4` pass found that `AGENTS.md` used helper label `architect` as if it were a canonical role, which drifted from the seven-role canonical set
  - the live documentary gate had moved to `550` tests after proof-hardening, while the active map/state snapshot still showed `548`
- Scope:
  - `AGENTS.md`
  - `docs/operations/SYSTEM_STATE.md`
  - `docs/operations/OPPORTUNITY_MAP.md`
  - `docs/operations/PHASE_CLOSURE.md`
- Done when:
  - helper aliases are explicitly non-canonical
  - the documenter-only track boundary is explicit in the repo operating note
  - the live documentary gate is refreshed to `550` tests without rewriting the historical closure count inside `PHASE_CLOSURE.md`
- Verify:
  - `python -m unittest tests.test_doc_governance tests.test_architecture -v`
  - `python -m unittest discover -s tests -v`
- Result:
  - helper aliases are now explicit non-canonical tooling labels in `AGENTS.md`
  - the documenter-only track boundary is explicit again in the repo operating note
  - the live documentary gate in `OPPORTUNITY_MAP.md` and `SYSTEM_STATE.md` now reflects the `550`-test suite state
  - `PHASE_CLOSURE.md` now states that the `548`-test count remains the historical closure count, while later documentary proof-hardening lifted only the live suite gate

### DOC-004 — Reconcile New Weakness Intake From The 2026-04-17 Audit

- Status: `done`
- Priority: `HIGH`
- Level: `1`
- Depends on: `DOC-003`
- Why it exists:
  - the direct 2026-04-17 audit reproduced a policy gap where `fs.create_file` with `overwrite=true` still mutates an existing file without approval because the gate is keyed by `kind`
  - the same audit reproduced a rollback residual where `create-new` removes the file but leaves an empty directory
  - `BUG_REPORT.md`, `WEAKNESS_REPORT.md`, and `SYSTEM_STATE.md` did not yet reflect those findings, so the canonical queue understated the live blocked set
- Scope:
  - `docs/operations/WEAKNESS_REPORT.md`
  - `docs/operations/BUG_REPORT.md`
  - `docs/operations/OPPORTUNITY_MAP.md`
  - `docs/operations/SYSTEM_STATE.md`
- Done when:
  - the effect-level approval gap is explicitly named as open
  - the rollback empty-directory residual is explicitly named as open
  - the blocked set and weakness intake reflect the current confirmed queue instead of the pre-audit queue
- Verify:
  - `python -m unittest discover -s tests -v`
  - `python -m unittest tests.test_architecture -v`
- Result:
  - the live weakness queue now includes the new effect-level approval gap and the rollback empty-directory residual
  - `BUG_REPORT.md` no longer claims that no approval residual remains open
  - `OPPORTUNITY_MAP.md` and `SYSTEM_STATE.md` now expose the fuller blocked set for the current documentary freeze track

### DOC-005 — Harden Preflight Gate Summary Against Noisy Test Output

- Status: `done`
- Priority: `MEDIUM`
- Level: `1`
- Depends on: `DOC-004`
- Why it exists:
  - the mandatory preflight snippet in `AGENTS.md` still relied on `Select-Object -Last 5`
  - in this workspace, `python -m unittest discover -s tests -v` can emit trailing operational lines after the suite summary, so the tail can hide the actual verdict
- Scope:
  - `AGENTS.md`
  - `docs/operations/OPPORTUNITY_MAP.md`
  - `docs/operations/SYSTEM_STATE.md`
- Done when:
  - the preflight command still runs in PowerShell
  - the preflight surfaces a stable suite verdict even when test output is noisy
  - the documentary snapshot records why the old tail-based check was insufficient
- Verify:
  - `python -m unittest discover -s tests -v`
  - `python -m unittest tests.test_architecture -v`
- Result:
  - `AGENTS.md` now captures the suite output in a temporary file and prints the final `Ran ... tests` line plus a stable pass/fail summary instead of trusting the raw tail
  - the documentary state now records that the previous tail-based preflight could hide the true verdict in this workspace

## Blocked By Freeze Or Architecture

### BLOCKED-102 — External session ownership residual

- Source: `docs/operations/PROJECT_OS_BACKLOG.md`
- Status: `blocked`
- Reason: touches session hardening beyond the current frozen corrective envelope

### BLOCKED-103 — Verify isolation residual

- Source: `docs/operations/PROJECT_OS_BACKLOG.md`
- Status: `blocked`
- Reason: touches residual verify authority/isolation boundaries that are accepted but not currently approved for growth

### BLOCKED-105 — Apply/Rollback external-writer atomicity

- Source: `docs/operations/PROJECT_OS_BACKLOG.md`
- Status: `blocked`
- Reason: would require deeper runtime hardening on critical execution paths

### BLOCKED-106 — Project/protocol anchoring

- Source: `docs/operations/PROJECT_OS_BACKLOG.md`
- Status: `blocked`
- Reason: remains procedural and would require architecture-level authorization before canonical promotion

### BLOCKED-GAP-02 — Canonical intention entity

- Source: `docs/operations/adr/GAP-02-intencao-canonica.md`
- Status: `blocked`
- Reason: explicit ADR block under freeze; no schema/state expansion is authorized

### BLOCKED-ALIGNMENT-EXPORT

- Source: `docs/operations/FREEZE_POLICY.md`
- Status: `blocked`
- Reason: no canonical alignment artifact exists

### BLOCKED-P5-STRUCTURE — `PHASE_CLOSURE.md` structural proof hardening

- Source: proof-of-stop `P5`
- Status: `blocked`
- Reason: targeted literal guards already cover the current closure claim; deeper structural hardening would require a separate test-surface slice outside the active documenter-only queue

### BLOCKED-WEAK-CRIT-LEGACY-EXEC — `exec.command` post-mutation artifact persistence gap

- Source: `docs/operations/WEAKNESS_REPORT.md`
- Status: `blocked in documenter track`
- Reason: the confirmed critical fix requires mutating `core/action_runtime.py`, `cli/commands/apply.py`, and proportional regression tests, which this loop may not touch under `AGENTS.md`

### BLOCKED-WEAK-HIGH-001 — session refresh crash window

- Source: `docs/operations/WEAKNESS_REPORT.md`
- Status: `blocked in documenter track`
- Reason: the confirmed high-severity fix requires mutating `core/state_store.py` and proportional regression tests, which this loop may not touch under `AGENTS.md`

### BLOCKED-WEAK-HIGH-002 — open-session crash split

- Source: `docs/operations/WEAKNESS_REPORT.md`
- Status: `blocked in documenter track`
- Reason: the confirmed high-severity fix requires mutating `core/state_store.py` and proportional regression tests to close the `session_registry_mismatch` window, which this loop may not touch under `AGENTS.md`

### CLOSED-WEAK-MED-004 — rollback agora poda tree recém-criada no caso `create-new`

- Source: `docs/operations/WEAKNESS_REPORT.md`
- Status: `closed (recorded 2026-04-22)`
- Resolution: `_prune_empty_workspace_dirs` em `core/action_runtime.py` já poda `created_target_dirs` no `rollback` de `fs.create_file` (linha 1025) e de `fs.move` sem `target_preimage_ref` (linha 1066); regressão em `tests/test_alpha_runtime.py` confirma que `notes/archive/` e `notes/` saem ausentes após rollback de `notes/archive/draft.txt`.

### CLOSED-DOC-DRIFT-002 — `AGENT_ARCHITECTURE.md` realinhado com o contrato do runtime

- Source: `docs/operations/WEAKNESS_REPORT.md`
- Status: `closed 2026-04-22`
- Resolution: `## Canonical Flow` → `## Operational Flow (Agent Protocol Only)` com disclaimer explícito; `## Canonical Roles` → `## Canonical Roles (External Labels Only)` com nota de ausência de role scheduler no runtime; `test_tracked_root_surface_is_minimal_and_docs_are_grouped` atualizado para `.codex` e `AGENTS.md`; 51 testes arquiteturais verdes.

## Accepted Residuals That Are Not Queue Items By Default

- file-backed session ownership does not yet close same-user tamper/restore of the external authority files
- verify still has residual bypass limits for perfectly restored transient tamper, out-of-root effects, or fully concealed drift
- apply/rollback still do not claim perfect atomicity against arbitrary external writers during execution
- performance has no currently eligible hotspot; the remaining event-log scaling risk is future-facing and measurement-gated

## Historical Next Item

- `none — hardening do Grupo 6 concluído`
- Historical closure note preserved for the documentary perimeter: `documenter queue exhausted; await Formal Resume Trigger`
- blocked residuals:
  - deeper architectural residuals still require mutating runtime code and proportional regression coverage
  - `PHASE_CLOSURE.md` structural proof hardening remains outside the active documenter-only queue
- latest revalidation:
  - the weakness queue was re-read and reconciled on 2026-04-17
  - `WEAKNESS_REPORT.md` now exposes `0` `CRÍTICO` aberto, `0` `ALTO` aberto, and multiple `MÉDIO`
  - the deep audit gap on effect-level approval (`fs.create_file overwrite=true` without approval) is now closed; the rollback residual (`create-new` leaves empty directory residue) remains tracked as `MÉDIO`
  - the final Grupo 6 proof pass ended clean: `P1` reproduced no original debt, `P2` found no new regression, and the live gate stayed green at `700` tests plus `51` architecture tests
  - the deep audit also preserved newer `MÉDIO` items (`close_session()` crash split) plus a stronger coverage gap (`session + plan + apply + verify + rollback` end-to-end still fragmented)
  - undocumented runtime behaviors (`plan_generation_id` fallback, auto-filled `consolidation_id`) were added to `WEAKNESS_REPORT.md`
  - the transient red gate seen in a prior `discover` tail did not reproduce on the next serial rerun; the live gate returned `550` tests, `0` failures, `6` skips, and `tests.test_architecture` stayed green
  - a later docs-only revalidation also stayed green (`550` tests, `0` failures, `6` skips; `tests.test_architecture` green) and still did not produce any new executable documentary slice
  - another full memory reread plus green gate revalidation (`550` tests, `0` failures, `6` skips; `tests.test_architecture` green) again confirmed that the current blocked set still yields no executable documentary-only slice
  - a subsequent full external-memory reread plus green gate revalidation (`550` tests, `0` failures, `6` skips; `tests.test_architecture` green) again produced no executable documentary-only slice
  - the latest iteration also closed a documentary drift in the mandatory preflight itself: the raw `tail`-style summary could be hidden by trailing test output, so `AGENTS.md` now prints a stable verdict from a temporary capture while the live gate stayed green (`550` tests, `0` failures, `6` skips; `tests.test_architecture` green)
  - the first exact rerun of that hardened preflight also stayed stable (`Ran 550 tests in 26.018s` / `OK (skipped=6)`) and still produced no new documentary-only slice; `tests.test_architecture` remained green
  - the next exact rerun of that same hardened preflight also stayed stable (`Ran 550 tests in 25.856s` / `OK`), `tests.test_architecture` remained green (`Ran 50 tests in 0.544s` / `OK`), and no new documentary-only slice became executable
  - no documentary slice became executable from that intake alone
