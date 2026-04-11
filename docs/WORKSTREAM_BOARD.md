# Workstream Board

This board tracks the current multi-front execution state with explicit stop conditions.

## Extensions Read-Only

- Objective: grow external views without touching core authority
- State: in progress
- Executed:
  - `handoff-export` and `status-export` are active
  - `return-map-export` added as a read-only extension
- Pending:
  - decide whether `alignment-export` can be defined without inventing semantics
- Blockers:
  - the current contract does not define canonical lineage or a canonical alignment artifact
- Risks:
  - inventing alignment semantics would create a second source of truth
- Next step:
  - keep `alignment-export` blocked until a precise derived-only definition exists

## Extension Standardization

- Objective: make the safe extension path easy and the unsafe path hard
- State: in progress
- Executed:
  - extension guidelines, template, and architectural tests already exist
  - package and CLI coverage now include `return-map-export`
- Pending:
  - strengthen enforcement against dynamic bypass patterns
  - require extension package metadata to stay aligned with packaging
- Blockers:
  - none for the current hardening slice
- Risks:
  - future extensions could drift from packaging or bypass AST checks through dynamic reflection
- Next step:
  - expand tests for packaging alignment, documentation alignment, and dynamic evasion patterns

## Governance

- Objective: keep contracts, boundaries, ADRs, and checklists consistent
- State: in progress
- Executed:
  - README clarified between bootstrap flow and daily `analyze` flow
  - public read-only helper usage was documented
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
- Pending:
  - consider whether non-Python executable artifacts under `extensions/` need separate enforcement
- Blockers:
  - none for the current hardening slice
- Risks:
  - static checks that are too shallow can be bypassed without obvious breakage
- Next step:
  - keep hardening test-only unless a new gap can be closed without expanding runtime

## Legacy Mining

- Objective: extract only ideas that fit the new architecture
- State: active, partially consolidated
- Executed:
  - `status-export` and `return-map-export` were identified as low-risk descendants
  - the reuse map now records safe reuse, reinterpretation, and prohibitions
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
