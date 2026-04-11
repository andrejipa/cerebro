# Workstream Board

This board tracks the current multi-front execution state with explicit stop conditions.

## Extensions Read-Only

- Objective: grow external views without touching core authority
- State: stable baseline
- Executed:
  - `handoff-export` and `status-export` are active
  - `return-map-export` added as a read-only extension
  - `impact-export` added as a constrained read-only operational surface view
  - `sources-export` added as a constrained read-only inventory of canonical source paths
  - `validation-export` added as a constrained read-only view of the last persisted canonical validation record
  - the six exporters now share only narrow support code for snapshot loading, timestamps, runtime-path rejection, and safe Markdown writes
- Pending:
  - add new exporters only when they remain obviously derived and read-only
- Blockers:
  - `alignment-export` is blocked as a separate front because the current contract does not define a canonical alignment artifact
- Risks:
  - inventing alignment semantics would create a second source of truth
- Next step:
  - preserve the existing export pattern and stop until a concrete new export is justified without changing the core

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
- State: active, partially consolidated
- Executed:
  - `status-export` and `return-map-export` were identified as low-risk descendants
  - `impact-export` was implemented as the next low-risk derived consumer from the legacy impact-view idea
  - `sources-export` was implemented as the lowest-risk descendant of source-inventory and source-coverage views
  - `validation-export` was implemented as the lowest-risk descendant of legacy check and status lenses over persisted validation metadata
  - the reuse map now records safe reuse, reinterpretation, and prohibitions
  - `alignment-export` remains explicitly blocked instead of being interpreted into existence
- Pending:
  - continue cataloging medium-risk ideas such as graph views
- Blockers:
  - none
- Risks:
  - legacy language can smuggle old authority patterns back into the product
- Next step:
  - keep all reuse proposals explicitly classified by layer and risk

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
- State: active
- Executed:
  - integration boundary documented
- Pending:
  - decide whether a dedicated integration template adds value beyond the current generic template
- Blockers:
  - adding framework-level integration hooks would exceed the current contract
- Risks:
  - premature hooks can become shadow APIs
- Next step:
  - stop before adding any runtime hook that is not already exposed by the core
