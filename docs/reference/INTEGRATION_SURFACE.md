# Integration Surface

This document defines the safe boundary for future integrations.

Classification: `ACTIVE SURFACE`.
This document is reference-only and non-canonical; canonical authority remains in `docs/operations/*`.

## Purpose

An integration is an external consumer that connects the core to another tool, interface, or transport without gaining authority over state.

## Behavior Taxonomy

Use the same three external shapes everywhere else in the project:

- `export`: read-only rendering of canonical state
- `analysis`: read-only processing of canonical state into a derived output
- `integration`: orchestration outside the runtime that consumes public commands or exports

Separately, the current project also allows a narrower assistive-discovery shape for initial bootstrap only:

- `assistive discovery`: heuristic shortlist generation over project-tree paths and filenames with no authority over runtime state or canonical context

These are consumer shapes only. None of them may change core authority or become a new source of truth.

## Allowed Inputs

Future integrations may consume only:

- CLI commands that already exist
- public `core` API exports
- read-only `StateStore` methods such as `read_snapshot()`, `has_active_session()`, and `read_trace_observability()`
- read models returned by the public API

Current assistive discovery such as `bootstrap-scan` may additionally inspect project-tree paths and filenames outside the canonical snapshot, but only to suggest candidates for explicit human review.

## Forbidden Influence

Future integrations may not:

- write inside `.cerebro/`
- read runtime JSON directly
- change validation semantics
- alter `analyze` behavior
- redefine session policy
- infer missing context
- create a second source of truth

## Safe Shapes

Safe integration shapes include:

- exporters to external files or transports
- dashboards derived from canonical state
- navigation indexes derived from canonical registered sources and canonical checkpoint text
- synchronization of derived outputs to external systems
- local bridges that remain disposable and non-authoritative

## Automation Bridges

An automation bridge is a narrow `integration` shape that reduces mechanical handoff between a human coordinator and an external executor such as Codex.

Safe automation bridges may:

- package an explicit task, context list, and approval mode into a disposable run directory
- invoke external execution through supported public surfaces such as `codex exec`
- capture JSONL events, structured final outputs, and human-readable logs outside `.cerebro/`
- require explicit human approval before any write-capable or core-sensitive step continues

Automation bridges must not:

- persist hidden project memory as a second source of truth
- register `sources` automatically
- call `import-context` automatically
- treat executor logs as canonical project state
- bypass `analyze`, `validate`, or the existing runtime entrypoints

Daily-use rule for automation bridges:

- use them only for mechanical execution, repeated audit runs, and explicit external task packaging
- do not use them to decide canonical context, select `sources`, interpret project truth, or reopen runtime decisions
- after every meaningful round, return to Cerebro through the normal `checkpoint` and `analyze` flow before treating anything as operational continuity
- treat every bridge output as disposable, non-canonical execution residue

Disposable automation-bridge implementations should stay outside tracked product code while the workflow is still evolving. `_local/` is the default incubation area for that kind of bridge.

Allowed future `analysis` outside the runtime may:

- summarize, count, group, compare, or reformat canonical fields
- report on persisted validation metadata
- derive navigation hints from canonical source paths and canonical checkpoint text only
- combine existing public outputs without becoming authority

Forbidden future `analysis` may not:

- infer missing context, intent, or alignment
- inspect source bodies or arbitrary project files
- recommend or decide on behalf of the runtime
- reopen validation or reinterpret canonical failure states

First concrete external `analysis` use case currently implemented as a minimum read-only classifier over supplied external evidence:

- `Verificador de Atualidade Externa`

That component may:

- classify supplied official or otherwise pre-authorized external source metadata when the question depends on temporally unstable outside facts
- normalize one supplied external bundle before classification so equivalent URLs do not inflate evidence count
- enforce `search_scope` as a domain allowlist over supplied source URLs
- bind its output to the snapshot revision and validation result it actually read
- publish versioned serializable request/report contracts with strict top-level payload validation
- treat `get_external_freshness_contract_schemas()` as the canonical integration surface for public schemas
- treat `get_external_freshness_contract_fixture_payloads_v1()` as the canonical integration surface for public fixture payloads
- treat `serialize_*` and `validate_*` as the canonical integration surface for wire payloads
- keep serialized `content_hash` structurally present and use the empty-string placeholder when no semantic hash is available
- treat `validate_external_freshness_request_payload()` and `validate_external_freshness_report_payload()` as minimum operational-semantic checks, not shape-only validators; they enforce host-normalized `search_scope`, runtime-valid source temporal/hash fields, non-empty claim explanations, promotion basis/status coherence, promotion candidates anchored by at least one `primaria_normativa` source, resolvable source/citation attribution, report claims anchored by at least one non-`descartada` source, and canonical alias/conflict references that stay attributable inside the report
- treat `internal_proven_items` canonicality as runtime snapshot-aware validation; the standalone request validator only proves payload-local binding between `internal_confirmation_reference` and the supplied handles
- treat `validate_external_bundle_normalization_report_payload()` as structural contract validation only; alias coherence remains producer/test responsibility
- treat exported `EXTERNAL_*_SCHEMA_V1` values as compatibility snapshots only, not validation authority
- treat exported `build_external_*_fixture_v1()` helpers as Python convenience fixtures, not canonical integration payloads
- treat exported `External*` dataclasses as Python composition helpers, not canonical wire payloads
- treat exported `Verified*` dataclasses as Python composition/output helpers, not canonical wire payloads
- return defensive public schema snapshots so callers cannot mutate later validation state through a shared reference
- publish reusable versioned fixture payloads for integration and regression coverage without expanding runtime authority
- treat those fixture payloads as contract-valid reusable samples, not a guaranteed transcript of one specific verifier run
- keep `v1` within the locally validated schema subset and block schema-keyword growth until an explicit contract decision exists
- mark `bundle_identity_scope=report_scoped` explicitly so bundle keys are not treated as cross-round identifiers
- produce structured `provavel`, `hipotese`, `conflitos`, `source_date`, `collected_at`, `freshness_status`, `time_sensitivity_context`, `source_strength`, `temporal_risk`, `promotion_status`, `resolution_status`, `source_aliases`, `bundle_source_key`, `bundle_identity_scope`, and citation/provenance metadata for later internal review
- downweight stale, undated, or temporally superseded findings automatically and reclassify them to `hipotese` when `temporal_risk` is `alto`
- follow a formal output schema, temporal sensitivity matrix, and objective downgrade rules instead of operator interpretation
- challenge or strengthen a path already under review without becoming authority
- leave live source acquisition and web querying outside the tracked package
- preserve query strings in canonical resource URLs unless a stronger equivalence proof is supplied
- collapse query variants only when stronger equivalence evidence such as matching `content_hash` is already available
- treat the external freshness verifier as downstream handling only; it does not widen the canonical role set or replace runtime gates
- treat the downstream role names referenced by that verifier as historical compatibility labels only; they do not create a separate authority chain

That component may not:

- decide whether a path is correct
- bypass the explicit downstream evidence review, conditional risk review, or pre-execution approval boundary referenced by that verifier
- promote external evidence directly into runtime truth
- treat caller-supplied arbitrary text as canonical internal proof
- accept free-form `canonical_context_relevant` blobs as if they were part of the payload contract
- resolve internal-versus-external conflicts automatically

`has_active_session()` reports session-file presence only. It does not validate session contents and must not be treated as a second runtime gate.
`read_trace_observability()` is the supported structured read path for trace health and integrity, but it remains a bounded recent-tail diagnostic rather than a whole-log completeness proof.
Derived handoff/export surfaces are one-way outputs in the current system. They do not provide a supported import path that rehydrates procedural blocked-round records back into canonical state automatically.
That later reconciliation is manual procedural restatement in a new analyze-led round, not import, replay, or hydration through a supported integration surface.
Derived Markdown exports such as `status-export` are human-first presentation surfaces. They do not carry a stable contract for headings, sections, or counter horizons unless a specific integration surface says otherwise explicitly.

Current repository convention:

- tracked code under `extensions/` stays limited to Python modules and Markdown documentation
- wrappers, launchers, and executable helpers stay outside `extensions/` unless the architecture changes explicitly
- CLI command names stay canonical unless an explicit architecture decision authorizes aliases

## Unsafe Shapes

Unsafe integration shapes include:

- webhooks or daemons that mutate runtime state outside `StateStore`
- adapters that treat external acknowledgements as core truth
- tools that reopen validation logic or checkpoint semantics
- integrations that read arbitrary project files outside registered sources

## Failsafe

If an integration design needs new authority over state, validation, `analyze`, session policy, or schema, stop and resolve that at the architecture level before implementation.

Any new or changed integration must add proportional adversarial and regression coverage for the public behavior it introduces.
