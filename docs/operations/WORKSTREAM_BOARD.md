# Workstream Board

This board tracks the current multi-front execution state with explicit stop conditions.
It is an active operational surface and a derived round ledger.
It records current fronts and historical round evidence, but it does not define canonical protocol, runtime authority, or a separate baseline.

## Latest Round

- Follow-up documentation alignment updated the active onboarding surface to match the current canonical role set and approval-boundary language.
- The legacy labels in the bullets below are preserved as historical round evidence, not as the current canonical role roster.
- Current canonical operational names are the seven roles defined in `AGENT_ROLES.md`; historical labels here should not be read as new baseline authority.
- Orquestrador opened the round by making the context explicit: this was work in `cerebro`, not in a `caso`.
- Mapeador bounded the blast radius to operational docs, one handoff, and documentary architecture tests.
- Quebrador found protocol drift: the published flow still lacked the mandatory context gate, formal evidence classes, the explicit `permitido com aprovacao humana` state, and mandatory tracing as part of closure.
- Organizador grouped that drift into protocol-baseline, approval-gate, and closure-observability cases.
- Comprovador marked the documentary drift as `comprovado` from repository evidence and kept broader historical rewrites outside the approved slice.
- Explorador de Solucoes compared a minimal baseline-sync path with a broader historical rewrite and kept both paths conditional.
- Avaliador de Risco entered because more than one documentation path existed; it found low risk in the minimal sync and unnecessary churn risk in retroactive broad rewrites.
- Guardião permitted only the documentation-and-test slice needed to publish the revised protocol, formalized `aprovacao humana` as an explicit future state, and blocked any move that would let external tools compete with `analyze`.
- Executor updated the protocol docs, the role baseline, the validation handoff, and documentary architecture tests only.
- Testador ran the documentary architecture slice after the edits.
- Auditor confirmed that the revised external protocol is now explicit while the runtime contract and freeze remain unchanged.
- Planejador recorded residual risk as wording drift only and set the next step as disciplined use of the revised checkpoints in future rounds.
- Orquestrador closed the round with tracing of what entered, what was blocked, what was executed, what was proved, the residual risk, and the next step.
- the daily-use baseline was further compressed into one minimum mandatory execution protocol so new operators do not have to infer the order of action.
- Historical round evidence: the round recorded that "The revised external protocol is now the official operational baseline and remains frozen unless a repeated real bottleneck triggers formal reopening." This should be read as historical context for that round, not as the current canonical baseline.
- Team-shape discussion remains closed until a formal role-layer trigger is documented against repeated real rounds.

## Extensions Read-Only

- Objective: grow external views without touching core authority
- State: safe limit reached
- Executed:
  - `handoff-export` and `status-export` are active
  - `return-map-export` added as a read-only extension
  - `impact-export` added as a constrained read-only operational surface view
  - `sources-export` added as a constrained read-only inventory of canonical source paths
  - `validation-export` added as a constrained read-only view of the last persisted canonical validation record
  - `context-index-export` added as a constrained read-only navigation index derived from canonical source paths and canonical checkpoint text
  - export outputs now report local session-file presence explicitly instead of implying independent session validity
  - the seven exporters now share only narrow support code for snapshot loading, timestamps, runtime-path rejection, and safe Markdown writes
  - validation-detail headings are now converged across the export family where detail codes are exposed
  - shared contract coverage now checks wrapper success identifiers instead of only file creation
- Pending:
  - none inside the current low-risk contract slice
- Blockers:
  - `alignment-export` is blocked as a separate front because the current contract does not define a canonical alignment artifact
- Risks:
  - inventing alignment semantics would create a second source of truth
  - pushing further now would drift into analysis-layer semantics or medium-risk graph interpretation
- Next step:
  - stop here until a concrete new export is justified without changing the core or crossing into external analysis

## Extension Standardization

- Objective: make the safe extension path easy and the unsafe path hard
- State: stable baseline
- Executed:
  - extension guidelines, template, and architectural tests already exist
  - package and CLI coverage now include `return-map-export`
  - package and CLI coverage now include `context-index-export`
  - shared safe extension plumbing now covers snapshot loading, timestamp normalization, runtime-path rejection, and explicit Markdown writes
  - shared extension contract tests now verify read-only behavior across all current exporters
  - extension docs now state the current Python-plus-Markdown-only convention for tracked extension packages
- Pending:
  - none without a real extension-shape change
- Blockers:
  - none for the current hardening slice
- Risks:
  - future extensions could drift from packaging or bypass AST checks through dynamic reflection
  - future contributors could still try to widen `extensions/` with new artifact types without first changing the contract
- Next step:
  - reopen this front only if a concrete new extension shape or evasion path appears

## Governance

- Objective: keep contracts, boundaries, ADRs, and checklists consistent
- State: baselined for continuous operational use
- Executed:
  - README clarified between bootstrap flow and daily `analyze` flow
  - public read-only helper usage was documented
  - canonical CLI command names are now explicitly documented as alias-free unless an architecture decision says otherwise
  - the alignment block remains recorded in the workstream board, handoff, and reuse map
  - adversarial robustness is now recorded as a permanent baseline and evolution policy
  - external agent roles now have an explicit operational protocol for future rounds without opening the next product layer
  - the protocol now treats context gating, formal human approval states, and tracing as part of the flow instead of optional documentation
  - daily execution is now documented as one minimum flow, and deviations are explicitly treated as protocol mismatch in records
  - the operational baseline now documents runtime entry mode for bootstrap and continuous work, separately documents the external round intent labels used around Cerebro, and records the rule to operate rather than evolve by default
  - the active documentary surfaces were recertified after focused breaking passes; residual is limited to legacy-compatible, test-anchored wording debt in `AGENT_ROLES.md` and historical phrasing explicitly fenced in `WORKSTREAM_BOARD.md`
  - the repository surface is now frozen as the official visual baseline for human navigation, with a minimal root and purpose-grouped `docs/`
- Pending:
  - none beyond factual maintenance
- Blockers:
  - none in the current cycle
- Risks:
  - wording drift can reintroduce mental-model ambiguity without changing code
  - visual drift can slowly reintroduce root clutter or mixed-purpose documentation without changing runtime behavior
- Next step:
  - keep the surface stable and allow repository-structure changes only for demonstrated navigation gain

## Bootstrap Assistive Entry

- Objective: reduce bootstrap friction without giving discovery authority over runtime truth
- State: stable assistive baseline, safe slice exhausted
- Executed:
  - `bootstrap-scan` exists as an assistive-only CLI command outside runtime authority
  - shortlist classification remains limited to project-tree paths and filenames
  - real-project validation confirmed the command reduces manual pointing before `import-context`
  - docs and architecture tests now make the heuristic boundary explicit
  - noisy-tree hardening now covers historical/acervo paths, false memory signals, and common local environment directories
  - CLI output now reports heuristic basis, total matched candidates, and returned shortlist size separately
  - CLI output now labels candidate classes as `suggested_type` instead of presenting them as authoritative type
  - subprocess coverage now includes invalid-limit and missing-root bootstrap-scan failures
  - automated subprocess coverage now includes the assisted protocol `bootstrap-scan -> import-context -> checkpoint -> analyze`
  - architecture tests now also block `Path.open()` and `io.open()` style content reads inside `bootstrap-scan`
- Pending:
  - none inside the current assistive-only slice
- Blockers:
  - reading file contents, ranking by semantic interpretation, or treating the shortlist as truth would cross into a new layer
- Risks:
  - further optimization pressure can turn assistive discovery into hidden authority
- Next step:
  - stop here until a concrete repeated unmet need justifies opening external analysis explicitly

## Real Use

- Objective: validate real operational flow without changing behavior
- State: adversarially revalidated baseline
- Executed:
  - regression suite covers `analyze`, `handoff-export`, `context-index-export`, `impact-export`, `sources-export`, `status-export`, `validation-export`, and `return-map-export`
  - clean flow executed on April 11, 2026 with `init -> import-context -> checkpoint -> analyze`
  - after changing `tracked.txt`, a second `analyze` blocked with `analysis_blocked` and `source_hash_mismatch`
  - clean installed flow executed on April 12, 2026 with `analyze -> handoff-export -> context-index-export -> impact-export -> sources-export -> status-export -> validation-export -> return-map-export`
  - `impact-export` joined the same read-only export family and inherits the same failure semantics
  - `sources-export` joins the same read-only export family without adding new runtime semantics
  - `validation-export` joins the same read-only export family without reopening runtime validation
  - `context-index-export` joins the same read-only export family without reading source bodies or competing with `analyze`
  - contract tests now confirm that exports still reflect canonical failed validation after a real `analyze` block
  - contract tests now confirm that all current exports fail explicitly when the state becomes invalid JSON
  - automated subprocess coverage now proves the assisted entry protocol `bootstrap-scan -> import-context -> checkpoint -> analyze`
  - adversarial revalidation completed without critical or moderate failures
  - three real projects were operated through `bootstrap-scan`, explicit source selection, `import-context`, `checkpoint`, `analyze`, and the full export family
  - a second operational cycle confirmed stable interruption and resumed analysis across project switches
- Pending:
  - rerun proportionally whenever the public surface changes
- Blockers:
  - none
- Risks:
  - documentation can drift away from real CLI behavior if not revalidated regularly
- Next step:
  - keep the same adversarial slice tied to future surface changes instead of running abstract hardening loops

## Regression Protection

- Objective: stop forbidden patterns before they land
- State: stable baseline
- Executed:
  - current architecture tests protect the core-extension boundary
  - architecture tests now cover package alignment, extension READMEs, bootstrap-vs-daily-flow wording, dynamic bypass primitives, and direct filesystem reads from extensions
  - architecture tests now also block process-spawning primitives inside tracked extension packages
  - CLI tests now reject unapproved human aliases and keep the command surface canonical
  - shared contract tests now verify that all current exporters reject runtime paths and remain read-only in sequence
  - a duplicate contract-test method that silently overrode subprocess blocked-state coverage was removed
  - shared contract tests now verify wrapper failure identifiers as well as wrapper success identifiers
  - tracked-file checks now fail if `extensions/` gains forbidden artifact types or non-Python shebang entrypoints
  - Git metadata checks now fail if tracked files in `extensions/` become symlinks or executable entries
  - adversarial runtime tests now cover state corruption, session corruption, blocked `analyze`, and repeated runtime cycles
- Pending:
  - none without a concrete new evasion path or surface change
- Blockers:
  - none for the current hardening slice
- Risks:
  - static checks that are too shallow can be bypassed without obvious breakage
- Next step:
  - stop here and reopen only for a concrete new gap or a real public-surface change

## Legacy Mining

- Objective: extract only ideas that fit the new architecture
- State: low-risk slice exhausted
- Executed:
  - `status-export` and `return-map-export` were identified as low-risk descendants
  - `impact-export` was implemented as the next low-risk derived consumer from the legacy impact-view idea
  - `sources-export` was implemented as the lowest-risk descendant of source-inventory and source-coverage views
  - `validation-export` was implemented as the lowest-risk descendant of legacy check and status lenses over persisted validation metadata
  - `context-index-export` was implemented as a low-risk derived navigation view over canonical source paths and canonical checkpoint text
  - the reuse map now records safe reuse, reinterpretation, and prohibitions
  - `alignment-export` remains explicitly blocked instead of being interpreted into existence
- Pending:
  - none inside the current low-risk export slice
- Blockers:
  - none
- Risks:
  - legacy language can smuggle old authority patterns back into the product
  - remaining candidates now tend to require medium-risk derivation rules or analysis-layer choices
- Next step:
  - stop here until a specific medium-risk candidate is promoted for explicit review

## External Analysis Preparation

- Objective: implement one minimum safe external-analysis increment without contaminating the runtime
- State: minimum read-only external analysis classifier implemented; live source acquisition still blocked
- Executed:
  - extension and integration docs now distinguish allowed read-only analysis from prohibited inference, decision, and runtime reopening
  - the first concrete external-analysis use case is now implemented as `Verificador de Atualidade Externa`
  - the tracked increment classifies supplied external evidence with deterministic temporal and downgrade rules
  - the classifier now enforces `search_scope` technically and carries citation/provenance metadata without opening live acquisition
  - the package now normalizes equivalent resource URLs into one canonical bundle source before scoring
  - the derived report is now bound to the snapshot revision it actually read and uses report-scoped bundle-source citation keys
  - the final report now marks `bundle_identity_scope=report_scoped` explicitly for downstream consumers
  - internal proof handles are now restricted to canonical snapshot refs instead of caller-defined arbitrary strings
  - the extension now publishes `external_freshness_contract.v1` with strict serializable request/report payload validation
  - the extension now publishes reusable v1 fixture builders and serialized payload fixtures for integration and regression coverage
- Pending:
  - decide whether live source acquisition is justified as a second external increment
- Blockers:
  - live acquisition would still introduce public behavior, source-selection policy, and external-trust handling
- Risks:
  - analysis language can drift into inference or pseudo-authority if not bounded tightly
- Next step:
  - stop at the current classifier-only increment unless explicit approval is granted for live source acquisition

## Integration Preparation

- Objective: define safe future integration surface without implementing integrations
- State: safe limit reached
- Executed:
  - integration boundary documented
  - the generic extension template remains sufficient; no dedicated integration template is justified yet
- Pending:
  - none without a concrete integration shape
- Blockers:
  - adding framework-level integration hooks would exceed the current contract
- Risks:
  - premature hooks can become shadow APIs
- Next step:
  - stop before adding any runtime hook or template that is not justified by a concrete integration use case

## Automation Bridge

- Objective: reduce manual copy-paste between human coordination and Codex execution without creating runtime authority
- State: read-only MVP externally validated and still kept outside tracked product code
- Executed:
  - compared three candidate architectures for the bridge: Agents SDK plus Codex over MCP, deep app-server integration, and a minimal local orchestrator using `codex exec`
  - selected the minimal local orchestrator as the primary path because it is the smallest auditable replacement for the current manual loop
  - documented the bridge as an `integration` shape only, not a runtime extension and not a new source of truth
  - disposable MVP initialized outside tracked product code
  - initialized a disposable local MVP under `_local/automation_bridge/` that uses `codex exec --ephemeral --json --output-schema`
  - stress-tested the bridge against invalid roots, invalid schema JSON, run-dir collisions, missing executors, missing/invalid final output, repeated rounds, and real-project usage
  - hardened the local tool with explicit collision handling, schema/output validation, command logging, and optional explicit `--skip-git-repo-check` passthrough
  - compared a direct manual `codex exec` run with the bridge flow and confirmed lower operator friction plus better per-run audit artifacts
  - formalized daily-use discipline, non-authority rules, run-dir hygiene, and the required return path back to Cerebro through `checkpoint` and `analyze`
- Pending:
  - keep the bridge local/disposable until a separate explicit decision defines whether it should be promoted outside the product
- Blockers:
  - any write-capable or core-sensitive automation still needs explicit human approval and must not be promoted silently
- Risks:
  - convenience pressure can turn orchestration logs into hidden memory or hidden authority
  - deeper app-server or SDK coupling can arrive too early and create an unnecessary second coordination runtime
- Next step:
  - keep the first bridge disposable, read-only by default, and explicitly subordinate to the current brain contract until a separate promotion decision is approved

## Installer Evolution

- Objective: evolve Cerebro installation in the correct order without introducing premature packaging complexity
- State: Phase 1 - Script PowerShell (in progress)
- Direction:
  - treat this as an evolution sequence, not as a rigid rule
  - keep functionality and validation ahead of distribution polish
- Phases:
  - Phase 1 - Script PowerShell
    - create a simple, reliable, validated installer script
    - focus on functional installation flow rather than distribution format
    - validate the script across multiple real projects
  - Phase 2 - Stabilization
    - reduce errors
    - improve messages
    - increase predictability
    - validate failure scenarios explicitly
  - Phase 3 - Packaging
    - transform the installer flow into `.exe`
    - improve usage ergonomics
    - make distribution easier
- Principles:
  - do not build the `.exe` before the script is solid
  - do not optimize distribution before functionality is resolved
  - do not hide real installation problems behind premature packaging
- Pending:
  - validate the PowerShell installer flow across multiple real projects before considering packaging
- Blockers:
  - packaging too early would freeze a weak installer surface into a friendlier wrapper
- Risks:
  - premature `.exe` work can consume effort while installation behavior is still under-defined
  - distribution polish can mask the need for clearer functional validation and failure handling
- Next step:
  - keep the current focus on a PowerShell installer path until the underlying install flow is stable enough to justify packaging

## Next Layer Transition

- Objective: leave the project ready for the next layer only by explicit decision
- State: deliberate freeze baselined, current layer consciously closed
- Executed:
  - the low-risk read-only export slice was reopened for one concrete justified navigation export and is now exhausted again
  - the core-extension boundary is hardened and adversarially revalidated
  - the external-analysis boundary is documented and implemented up to the current classifier-only limit
  - `alignment-export` remains explicitly blocked because the contract still has no canonical alignment artifact
  - the deliberate freeze policy, conservatism assessment, minimum safe advance rule, and resume protocol are now documented as the default operational state
  - `bootstrap-scan` was approved and implemented as one assistive-only minimum safe advance that suggests candidates without touching runtime state
  - residual triage confirmed that no additional clearly safe block remains in the current layer
  - a final multi-role closure review closed the remaining safe external gaps and confirmed that the rest is limited to point correction, real architecture blocks, or explicit next-layer decisions
- Pending:
  - none while the deliberate freeze remains in effect
- Blockers:
  - opening the next layer now would require an explicit semantic choice rather than more autonomous hardening
- Risks:
  - automatic continuation from here would create pressure to invent semantics instead of selecting them consciously
  - false urgency could reopen growth without a concrete repeated unmet use case
- Next step:
  - keep corrective maintenance only, break the freeze only through the formal trigger and resume protocol, and authorize at most one minimum safe external increment if the trigger is met

## Operating Posture

- Objective: use the system as stable infrastructure
- State: active
- Executed:
  - the daily operational protocol is now explicit and unified across bootstrap, continuous work, and external round intent handling
  - the daily protocol now also records the order for context, evidence, risk, approval boundary, execution, verification, audit, and tracing
  - bridge usage is explicitly subordinate to Cerebro continuity
  - agent usage is explicitly constrained to external protocol rounds under the documented round intent labels
  - the rule of `do not tinker without a repeated unmet use case` is now visible in primary docs
- Pending:
  - none beyond day-to-day use and corrective maintenance
- Blockers:
  - none
- Risks:
  - operator habit can still drift back into treating the system as a project instead of infrastructure
- Next step:
  - operate it through the approved baseline and reopen engineering only through the formal freeze-break protocol
