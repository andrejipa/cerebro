# Workstream Board

This board tracks the current multi-front execution state with explicit stop conditions.

## Extensions Read-Only

- Objective: grow external views without touching core authority
- State: in progress
- Executed:
  - `handoff-export` and `status-export` are active
  - `return-map-export` added as a read-only extension
  - the three exporters now share only narrow support code for snapshot loading, timestamps, and runtime-path rejection
- Pending:
  - keep output conventions, write-safety, and test coverage convergent across the existing exporters
- Blockers:
  - `alignment-export` is blocked as a separate front because the current contract does not define a canonical alignment artifact
- Risks:
  - inventing alignment semantics would create a second source of truth
- Next step:
  - harden the existing read-only exporters and preserve the separate alignment block unchanged

## Extension Standardization

- Objective: make the safe extension path easy and the unsafe path hard
- State: in progress
- Executed:
  - extension guidelines, template, and architectural tests already exist
  - package and CLI coverage now include `return-map-export`
  - shared safe extension plumbing now covers snapshot loading, timestamp normalization, and runtime-path rejection
  - shared extension contract tests now verify read-only behavior across all current exporters
  - extension docs now state the current Python-plus-Markdown-only convention for tracked extension packages
- Pending:
  - keep the shared support layer narrow and resist turning it into a framework
- Blockers:
  - none for the current hardening slice
- Risks:
  - future extensions could drift from packaging or bypass AST checks through dynamic reflection
  - future contributors could still try to widen `extensions/` with new artifact types without first changing the contract
- Next step:
  - keep shared support utility-only and require any wider extension shape to go through explicit architecture review

## Governance

- Objective: keep contracts, boundaries, ADRs, and checklists consistent
- State: in progress
- Executed:
  - README clarified between bootstrap flow and daily `analyze` flow
  - public read-only helper usage was documented
  - the alignment block remains recorded in the workstream board, handoff, and reuse map
- Pending:
  - keep future entrypoint and extension docs convergent
- Blockers:
  - none in the current cycle
- Risks:
  - wording drift can reintroduce mental-model ambiguity without changing code
- Next step:
  - enforce the clarified wording in tests

## Real Use

- Objective: validate real operational flow without changing behavior
- State: validated for the current slice
- Executed:
  - regression suite covers `analyze`, `handoff-export`, `status-export`, and `return-map-export`
  - clean flow executed on April 11, 2026 with `init -> import-context -> checkpoint -> analyze`
  - after changing `tracked.txt`, a second `analyze` blocked with `analysis_blocked` and `source_hash_mismatch`
  - clean installed flow executed on April 11, 2026 with `analyze -> handoff-export -> status-export -> return-map-export`
  - contract tests now confirm that exports still reflect canonical failed validation after a real `analyze` block
  - contract tests now confirm that all current exports fail explicitly when the state becomes invalid JSON
- Pending:
  - repeat the same flow whenever the public CLI protocol changes
- Blockers:
  - none
- Risks:
  - documentation can drift away from real CLI behavior if not revalidated regularly
- Next step:
  - keep the flow in periodic release validation

## Regression Protection

- Objective: stop forbidden patterns before they land
- State: in progress
- Executed:
  - current architecture tests protect the core-extension boundary
  - architecture tests now cover package alignment, extension READMEs, bootstrap-vs-daily-flow wording, and dynamic bypass primitives
  - next hardening slice targets shared extension contracts and more dynamic bypass routes
  - shared contract tests now verify that all current exporters reject runtime paths and remain read-only in sequence
  - tracked-file checks now fail if `extensions/` gains forbidden artifact types or non-Python shebang entrypoints
  - Git metadata checks now fail if tracked files in `extensions/` become symlinks or executable entries
- Pending:
  - stop here unless a concrete new evasion path appears outside the current test net
- Blockers:
  - none for the current hardening slice
- Risks:
  - static checks that are too shallow can be bypassed without obvious breakage
- Next step:
  - keep hardening test-only and wait for a concrete new gap before adding more structural rules

## Legacy Mining

- Objective: extract only ideas that fit the new architecture
- State: active, partially consolidated
- Executed:
  - `status-export` and `return-map-export` were identified as low-risk descendants
  - the reuse map now records safe reuse, reinterpretation, and prohibitions
  - `alignment-export` remains explicitly blocked instead of being interpreted into existence
- Pending:
  - continue cataloging medium-risk ideas such as graph and impact views
- Blockers:
  - none
- Risks:
  - legacy language can smuggle old authority patterns back into the product
- Next step:
  - keep all reuse proposals explicitly classified by layer and risk

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
