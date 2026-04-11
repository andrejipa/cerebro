# Workstream Board

This board tracks the current multi-front execution state with explicit stop conditions.

## Extensions Read-Only

- Objective: grow external views without touching core authority
- State: safe limit reached
- Executed:
  - `handoff-export` and `status-export` are active
  - `return-map-export` added as a read-only extension
  - `impact-export` added as a constrained read-only operational surface view
  - `sources-export` added as a constrained read-only inventory of canonical source paths
  - `validation-export` added as a constrained read-only view of the last persisted canonical validation record
  - export outputs now report local session-file presence explicitly instead of implying independent session validity
  - the six exporters now share only narrow support code for snapshot loading, timestamps, runtime-path rejection, and safe Markdown writes
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
- State: baselined
- Executed:
  - README clarified between bootstrap flow and daily `analyze` flow
  - public read-only helper usage was documented
  - canonical CLI command names are now explicitly documented as alias-free unless an architecture decision says otherwise
  - the alignment block remains recorded in the workstream board, handoff, and reuse map
  - adversarial robustness is now recorded as a permanent baseline and evolution policy
- Pending:
  - keep future surface-growth docs convergent with the robustness baseline
- Blockers:
  - none in the current cycle
- Risks:
  - wording drift can reintroduce mental-model ambiguity without changing code
- Next step:
  - enforce the baseline wording in tests and ADRs

## Real Use

- Objective: validate real operational flow without changing behavior
- State: adversarially revalidated baseline
- Executed:
  - regression suite covers `analyze`, `handoff-export`, `impact-export`, `sources-export`, `status-export`, `validation-export`, and `return-map-export`
  - clean flow executed on April 11, 2026 with `init -> import-context -> checkpoint -> analyze`
  - after changing `tracked.txt`, a second `analyze` blocked with `analysis_blocked` and `source_hash_mismatch`
  - clean installed flow executed on April 11, 2026 with `analyze -> handoff-export -> impact-export -> sources-export -> status-export -> validation-export -> return-map-export`
  - `impact-export` joined the same read-only export family and inherits the same failure semantics
  - `sources-export` joins the same read-only export family without adding new runtime semantics
  - `validation-export` joins the same read-only export family without reopening runtime validation
  - contract tests now confirm that exports still reflect canonical failed validation after a real `analyze` block
  - contract tests now confirm that all current exports fail explicitly when the state becomes invalid JSON
  - adversarial revalidation completed without critical or moderate failures
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

- Objective: define the safe future analysis layer without implementing it
- State: safe boundary baselined
- Executed:
  - extension and integration docs now distinguish allowed read-only analysis from prohibited inference, decision, and runtime reopening
- Pending:
  - choose a first concrete analysis use case only when a simple export is no longer enough
- Blockers:
  - implementing analysis now would require picking semantics and output scope that are still optional
- Risks:
  - analysis language can drift into inference or pseudo-authority if not bounded tightly
- Next step:
  - stop here until a concrete external analysis use case is justified against the documented boundary

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

## Next Layer Transition

- Objective: leave the project ready for the next layer only by explicit decision
- State: deliberate freeze baselined
- Executed:
  - the low-risk read-only export slice is exhausted
  - the core-extension boundary is hardened and adversarially revalidated
  - the external-analysis boundary is documented up to the safe conceptual limit
  - `alignment-export` remains explicitly blocked because the contract still has no canonical alignment artifact
-  the deliberate freeze policy, resume trigger, and resume protocol are now documented as the default operational state
- Pending:
  - none while the deliberate freeze remains in effect
- Blockers:
  - opening the next layer now would require an explicit semantic choice rather than more autonomous hardening
- Risks:
  - automatic continuation from here would create pressure to invent semantics instead of selecting them consciously
- Next step:
  - keep corrective maintenance only, and break the freeze only through the formal trigger and resume protocol
