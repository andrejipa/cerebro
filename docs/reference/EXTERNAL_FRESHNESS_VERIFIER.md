# External Freshness Verifier

This document defines the first concrete external `analysis` use case that may exist around Cerebro without changing core authority.

Classification: `ACTIVE SURFACE`.
This document is reference-only and non-canonical; canonical authority remains in `docs/operations/*`.

## Canonical Name

The canonical component name is:

- `Verificador de Atualidade Externa`

This component is:

- external
- read-only
- non-canonical
- non-decisory

It is not:

- part of the fixed agent role set
- a runtime gate
- a source of truth
- a replacement for `analyze`, `validate`, explicit evidence review, conditional risk review, or the round's pre-execution approval boundary

## Purpose

The runtime already protects internal continuity and explicit state integrity.
What it does not protect by itself is temporal drift in the outside world.

This component exists to reduce one specific risk:

- a path may be internally coherent but externally stale

It does not search for the "best" path.
It checks whether updated external facts materially challenge or strengthen a path that is already under review.

## Classification

Architectural shape:

- `analysis`

Optional transport shape, if automation is used:

- `integration`

It must remain fully external to the core and outside `.cerebro/`.

## Current Minimum Implementation

The tracked minimum increment is now implemented as a read-only classifier over supplied external evidence, together with one deterministic bundle-normalization step.

Current tracked behavior:

- reads the canonical snapshot through the public core API
- normalizes one supplied external bundle through `Normalizador de Bundle Externo` before classification
- consumes supplied external source metadata and structured finding descriptors
- enforces `search_scope` as a technical domain allowlist over supplied source URLs
- collapses equivalent resource URLs into one canonical bundle source before scoring
- applies deterministic freshness, downgrade, promotion, and conflict rules
- binds the derived report to the canonical snapshot revision and validation result it actually read
- carries citation and provenance metadata such as normalized domain, locator, acquisition method, trace id, a serialized `content_hash` field that uses the empty-string placeholder when unavailable, and report-scoped bundle-source keys
- emits `bundle_identity_scope=report_scoped` in the final report so downstream consumers do not treat `bundle_source_key` as cross-round identity
- publishes versioned serializable request/report contracts under `external_freshness_contract.v1`
- publishes reusable v1 fixture builders and serialized payload fixtures for integration and regression coverage
- emits a structured non-canonical report and optional Markdown rendering

Current tracked limits:

- it does not fetch URLs by itself
- it does not browse the internet by itself
- it does not select sources by itself
- it does not add a new canonical CLI command

Live source acquisition remains external to this package.

## Exact Position In The Flow

The component may run only after the path under review is explicit.

Typical position:

- `path under review -> Verificador de Atualidade Externa -> explicit evidence review against canonical context -> conditional risk review (if needed) -> round-specific pre-execution approval boundary`

If no path exploration was needed because the path is already singular and explicit, it may run here instead:

- `explicit path -> Verificador de Atualidade Externa -> explicit evidence review against canonical context -> conditional risk review (if needed) -> round-specific pre-execution approval boundary`

It never bypasses:

- the round's evidence review against canonical context
- conditional risk review when that review is justified
- the round's pre-execution approval boundary

No decision may be taken directly from its output.
Legacy role labels in this flow are historical aliases only and do not expand the canonical role set.

## Input Contract

Required input:

- `question_or_proposal`: one concrete technical question or one concrete path under review
- `internal_proven_items`: canonical internal references already exposed by the current snapshot and intentionally supplied to the round
- `search_scope`: which external domains are allowed for this run
- `allowed_source_classes`: which kinds of external authority are acceptable for this run
- `trigger_reason`: why external recency matters here
- `sources`: supplied external source metadata already collected outside the package
- `findings`: supplied claim descriptors that point to those sources

`sources` and `findings` are operational payloads, not descriptive placeholders.
In the tracked implementation, both must be non-empty tuples before the component may run.

`search_scope` is not descriptive only.
In the current tracked implementation it is enforced against each supplied source URL after hostname normalization.

Allowed `allowed_source_classes` values:

- `primaria_normativa`
- `primaria_tecnica`
- `secundaria_confiavel`

`allowed_source_classes` constrains what the run may consult.
`descartada` is output-only and may never appear in this input field.

The component may consume canonical context through:

- public CLI commands
- public `core` read APIs
- read-only exports

It must not read runtime JSON directly.
`canonical_context_relevant` is not a payload field in the tracked contract.
The package reads canonical context through the public API and only accepts explicit `internal_proven_items` handles inside the request payload.

`internal_proven_items` is not free text.
In the tracked implementation it must bind to explicit canonical snapshot references such as:

- `source:<registered-path>`
- `checkpoint.goal`
- `checkpoint.summary`
- `checkpoint.next_step`
- `checkpoint.constraint:<index>`

The standalone public request validator can only prove payload-local binding for these handles.
Canonical snapshot membership for `internal_proven_items` remains a runtime, snapshot-aware check performed by the verifier itself.

## Processing Rules

The component may:

- assess supplied updated external sources
- compare external facts against the path under review
- classify every external finding initially as `provavel` and only reclassify it downward under the documented downgrade rules
- mark whether an item has a valid promotion basis for later internal review
- assess temporal relevance and staleness risk per source and per finding
- mark unresolved conflict explicitly
- record source authority and observed date
- emit alias metadata when multiple raw sources collapse to the same canonical resource
- preserve the query string in the current canonical resource URL when no stronger equivalence proof exists
- allow query variants to collapse only when a stronger equivalence proof such as matching `content_hash` is already present
- keep `content_hash`-based collapse scoped to the same normalized resource family; cross-resource or cross-domain mirrors remain distinct even when their content matches
- keep non-empty canonical audit fields authoritative; alias data may backfill only fields that the canonical source leaves empty

The component must:

- prefer primary normative, regulatory, legal, fiscal, standards, or official technical documentation first
- reject supplied source URLs outside the normalized `search_scope`
- reject duplicate `source_ids` inside a single finding
- record source date when available
- record collection date for every source consulted
- record temporal freshness status for every source consulted
- record citation and provenance metadata when it is available from the external acquisition step
- keep `internal_proven_items` bound to canonical snapshot references instead of caller-defined arbitrary strings
- keep source attribution explicit per finding
- treat time sensitivity as part of source weighting when the topic is externally unstable

The component must not:

- decide whether the path should be executed
- validate the runtime
- reopen `validate`
- inspect arbitrary project files outside the allowed canonical context
- mutate state
- create a new canonical artifact

## Public Contract

The tracked package now exposes one versioned serializable contract:

- `external_freshness_contract.v1`

That contract currently publishes:

- request schema v1
- normalization-report schema v1
- final-report schema v1
- reusable request/report fixture builders and serialized payload fixtures for v1

Contract shape rules:

- schemas use JSON Schema draft `2020-12`
- each payload carries `schema_version`
- contract payloads are strict and reject unsupported top-level keys
- `get_external_freshness_contract_schemas()` is the canonical public schema surface for integrations
- `get_external_freshness_contract_fixture_payloads_v1()` is the canonical public fixture-payload surface for integrations
- `serialize_*` and `validate_*` define the canonical programmatic wire-contract surface for integrations
- serialized request/report payloads keep `content_hash` structurally present as a string field; when no semantic hash exists, the contract uses the empty-string placeholder instead of omitting the key
- `validate_external_freshness_request_payload()` and `validate_external_freshness_report_payload()` enforce minimum operational semantics beyond raw shape; they reject empty runtime-required fields and broken source/claim attribution
- `validate_external_bundle_normalization_report_payload()` is intentionally shape-only; it validates the serialized contract shape but does not prove semantic coherence between `source_aliases` and `normalized_request`
- exported `EXTERNAL_*_SCHEMA_V1` values are compatibility snapshots only and do not define validation authority
- exported `build_external_*_fixture_v1()` helpers are Python convenience fixtures and do not define canonical integration payloads
- exported `External*` dataclasses are Python composition types and do not define canonical wire payloads
- exported `Verified*` dataclasses are Python composition/output types and do not define canonical wire payloads
- public schema accessors return defensive snapshots so callers cannot mutate validation state through a shared reference
- contract validation must stay outside the core and outside `.cerebro/`
- the final report carries `bundle_identity_scope=report_scoped`
- the local validator for this package intentionally supports only the subset used by `v1`:
  - `$id`
  - `$schema`
  - `title`
  - `type`
  - `enum`
  - `const`
  - `required`
  - `additionalProperties`
  - `properties`
  - `items`
- schema growth beyond that subset stays blocked until an explicit architecture decision opens it

## Public API Inventory

The package-root public API is intentionally grouped into four categories:

- Canonical integration surface:
  - `get_external_freshness_contract_schemas()`
  - `get_external_freshness_contract_fixture_payloads_v1()`
  - `serialize_external_freshness_request()`
  - `serialize_external_bundle_normalization_report()`
  - `serialize_external_freshness_report()`
  - `validate_external_freshness_request_payload()`
  - `validate_external_bundle_normalization_report_payload()`
  - `validate_external_freshness_report_payload()`
- Compatibility snapshots and Python fixture helpers:
  - `EXTERNAL_FRESHNESS_CONTRACT_VERSION`
  - `EXTERNAL_FRESHNESS_REQUEST_SCHEMA_V1`
  - `EXTERNAL_BUNDLE_NORMALIZATION_REPORT_SCHEMA_V1`
  - `EXTERNAL_FRESHNESS_REPORT_SCHEMA_V1`
  - `build_external_freshness_request_fixture_v1()`
  - `build_external_bundle_normalization_report_fixture_v1()`
  - `build_external_freshness_report_fixture_v1()`
- Python composition/output types:
  - `ExternalBundleNormalizationReport`
  - `ExternalBundleSourceAlias`
  - `ExternalFindingInput`
  - `ExternalFreshnessReport`
  - `ExternalFreshnessRequest`
  - `ExternalGap`
  - `ExternalSourceInput`
  - `VerifiedClaim`
  - `VerifiedConflict`
  - `VerifiedSourceRecord`
- Operational read-only helpers:
  - `ExternalFreshnessVerifierError`
  - `normalize_external_bundle()`
  - `verify_external_freshness()`
  - `render_external_freshness_markdown()`
  - `write_external_freshness_markdown()`

Only the canonical integration surface defines wire payload semantics for integrations.

The validator split is deliberate:

`validate_external_freshness_request_payload()` and `validate_external_freshness_report_payload()` are not shape-only.
they enforce the minimum operational semantics already required by the shipping runtime, including:
  - non-empty runtime-required text and array fields
  - unique `source_id`, `claim_id`, and `bundle_source_key` where applicable
  - normalized `search_scope` entries that remain runtime-valid and non-duplicated, with host-based matching even when callers include explicit ports
  - source metadata whose `source_date`, `collected_at`, and `content_hash` remain runtime-valid in both request and report payloads
  - source references that resolve inside the same payload
  - `citation_refs` that resolve to known `bundle_source_key` values
  - citation chains that stay attributable to the same claim `source_ids`
  - claim explanations whose `why_classified` and `temporal_basis` remain non-empty
  - `internal_confirmation_reference` values that resolve to declared canonical internal refs
  - report claims whose attributed `source_ids` still include at least one non-`descartada` source in `source_register`
This also includes `citation_refs` with no duplicates and no empty trailing locator after `@`.
This also includes `promotion_candidate` claims whose `promotion_basis` is explicit, not `nenhuma`, and still backed by at least one attributed `primaria_normativa` source.
This also includes non-promotable claims whose `promotion_basis` remains `nenhuma`.
The same validator split also requires report-only coherence:
This includes `source_aliases` whose `canonical_source_id` and `canonical_resource_url` resolve to the same canonical source emitted in `source_register`.
This includes `conflitos[].claim_id` values that resolve to claims emitted in `provavel` or `hipotese`.
source aliases must resolve to a canonical source emitted in `source_register`, and `conflitos[].claim_id` must resolve to a claim emitted in `provavel` or `hipotese`.
`validate_external_bundle_normalization_report_payload()` remains structural only because the coherence between alias mapping and normalized request is producer/test responsibility.
The compatibility snapshots, Python fixture helpers, composition types, and operational helpers do not redefine the wire contract.
Serialized fixture payloads remain contract-valid reusable samples, not a guaranteed one-to-one transcript of a single runtime emission path.

Markdown rendering is a derived operational summary, not a second wire contract.
In the tracked implementation, it must still preserve audit-critical fields such as `url`, `citation_locator`, `why_classified`, `temporal_basis`, `downgrade_reasons`, and citation chains.
Embedded newlines in free-text fields must be normalized to escaped `\n` so the Markdown structure remains stable.

## Output Contract

The output must be structured and non-canonical.

Required top-level fields:

- `component`: `Verificador de Atualidade Externa`
- `queried_at`
- `question_or_proposal`
- `trigger_reason`
- `paths_under_review`
- `snapshot_revision`
- `snapshot_validation_result`
- `time_sensitivity_context`
- `bundle_identity_scope`
- `source_aliases`
- `source_register`
- `provavel`
- `hipotese`
- `conflitos`
- `lacunas`
- `operational_note`

Required output shape:

- `source_register[]` entries must include:
  - `source_id`
  - `bundle_source_key`
  - `bundle_identity_scope`
  - `url`
  - `normalized_domain`
  - `source_title`
  - `source_authority`
  - `source_strength`
  - `source_date`
  - `collected_at`
  - `freshness_status`
  - `temporal_risk`
  - `citation_locator`
  - `content_hash`
  - `acquisition_method`
  - `acquisition_query`
  - `acquisition_trace_id`
  - `notes`
- `provavel[]` and `hipotese[]` entries must include:
  - `claim_id`
  - `summary`
  - `source_ids`
  - `citation_refs` derived from `bundle_source_key`
  - `claim_time_sensitivity_context`
  - `why_classified`
  - `promotion_status`
  - `promotion_basis`
  - `temporal_basis`
  - `downgrade_reasons`
- `conflitos[]` entries must include:
  - `claim_id`
  - `conflict_type`
  - `conflicting_source_ids`
  - `resolution_status`
  - `why_not_resolved_automatically`
- `lacunas[]` entries must include:
  - `gap_id`
  - `missing_fact`
  - `why_it_matters`
  - `required_source_class`
- `source_aliases[]` entries must include:
  - `original_source_id`
  - `canonical_source_id`
  - `canonical_resource_url`
  - `reason`

Required rules for `source_register`:

- each source must include:
  - `url`
  - `source_authority`
  - `source_strength`
  - `source_date`
  - `collected_at`
  - `freshness_status`
- `bundle_identity_scope`
- in the serialized payload, these keys are structurally required even when the source does not provide a semantic value
- when a semantic value is unavailable, the serialized field remains present and carries the empty-string placeholder used by the contract
- `source_register` is the normalized inventory of sources supplied for the run, not only the subset referenced by surviving claims
- claims, `conflitos`, and `lacunas` must remain attributable into `source_register`, but normalized orphan sources may still appear there when they were supplied in the bundle
- when equivalent sources collapse into one canonical bundle source, the normalized entry may retain richer audit metadata such as `citation_locator`, `source_title`, `acquisition_query`, `acquisition_trace_id`, and `notes` from any surviving alias in the same equivalence group
- Markdown exports may mark source entries as `usage=referenced` or `usage=orphan` for readability, but this does not change payload semantics
- Markdown `usage=referenced` must be derived from all normalized findings for the round, including findings that later become `lacunas`
- Markdown exports must state that `source_register.freshness_status` and `source_register.temporal_risk` are aggregated per source, while claim sections remain claim-local

Allowed `bundle_identity_scope` values:

- `report_scoped`

Allowed `time_sensitivity_context` values:

- `alta`
- `media`
- `baixa`

Each claim-level `claim_time_sensitivity_context` must use the same value set.
The runtime computes the top-level `time_sensitivity_context` from the highest sensitivity present across all finding items in the round.
The public validator enforces the minimum externally checkable subset of that rule: the top-level value may not be lower than any emitted `claim_time_sensitivity_context`.

Allowed `freshness_status` values:

- `recente`
- `intermediaria`
- `possivelmente_desatualizada`

Allowed `temporal_risk` values:

- `baixo`
- `medio`
- `alto`

Allowed `source_strength` values:

- `primaria_normativa`
- `primaria_tecnica`
- `secundaria_confiavel`
- `descartada`

Allowed `acquisition_method` values:

- `manual`
- `web_search`
- `deep_research`
- `mcp`
- `other`

Allowed `promotion_status` values:

- `promotion_candidate`
- `not_eligible_for_promotion`

Allowed `promotion_basis` values:

- `fonte_normativa_primaria`
- `fonte_normativa_primaria_e_confirmacao_interna_disponivel`
- `nenhuma`

Allowed `conflict_type` values:

- `externo_mais_recente`
- `autoridade_divergente`

In the shipping `v1`, `autoridade_divergente` is also the fallback bucket for unresolved contradictory claims when attribution collapses to the same canonical source. That is a documented semantic limit of the current conflict model, not a second conflict shape.

Allowed `resolution_status` values:

- `nao_resolvido`
- `encaminhado_ao_comprovador`

Current runtime subset:

- the shipping verifier currently emits only `encaminhado_ao_comprovador`
- `nao_resolvido` remains schema-allowed in `external_freshness_contract.v1`, but no runtime path emits it today

Allowed `required_source_class` values:

- `primaria_normativa`
- `primaria_tecnica`
- `secundaria_confiavel`

Current runtime subset:

- the shipping verifier currently emits only `primaria_normativa` or `primaria_tecnica` in `lacunas`
- `secundaria_confiavel` remains schema-allowed in `external_freshness_contract.v1`, but no runtime path emits it today

Required rule for every finding item:

- every claim must point to one or more source-register entries
- every claim must carry `citation_refs` that make the claim-to-source chain auditable inside the derived report and any export that references that same report
- every claim that uses `bundle_source_key` must stay subordinate to the report-level `bundle_identity_scope`
- every claim must state why it belongs to `provavel` or `hipotese`
- every claim must declare whether it is:
  - `promotion_candidate`
  - `not_eligible_for_promotion`
- every `promotion_candidate` must state its promotion basis explicitly
- every claim must state its temporal freshness basis when recency is relevant

`operational_note` must state explicitly:

- `external read-only analysis output; non-canonical; not a runtime decision`

## Evidence Rule

External information never becomes operational truth by itself.

Two layers must stay distinct:

- external finding strength
- internal operational evidence status

Inside this component, every external finding starts as `provavel`.
It may be reclassified downward to `hipotese` when source trust, attribution, or date quality is weak.
It may never be emitted by this component as `comprovado`.

Temporal controls are mandatory:

- missing `source_date` must reduce confidence in time-sensitive contexts
- older information in a high-sensitivity context must lose weight automatically
- conflict with a more recent trustworthy source must reduce the older item's weight automatically
- older information is not discarded only because it is old, but it must be reclassified to `hipotese` when `temporal_risk` is `alto`

An external finding becomes only a `promotion_candidate` when at least one of the following is true:

- it comes from a clearly identified official primary normative source
- it comes from a clearly identified official primary normative source and also points to a canonical internal reference already available to the round

Internal confirmation alone is not enough for `promotion_candidate` inside this component.
That avoids caller-supplied internal text from becoming a second source of truth.

Even a `promotion_candidate` remains externally classified as `provavel` until additional internal validation is performed against the canonical context.
A finding reclassified to `hipotese` must leave this component as `not_eligible_for_promotion`.

No external finding may automatically promote a path to `permitido`.

Temporal weighting must follow the context:

- in `alta` sensitivity contexts, recency must be treated as a first-order relevance factor
- in `media` sensitivity contexts, recency must be weighed alongside source authority
- in `baixa` sensitivity contexts, older authoritative material may remain useful, but it must still carry explicit freshness status

`temporal_risk` must be assigned as follows:

- `alto`: `source_date` is unavailable in an `alta` context, or the source is `possivelmente_desatualizada` for a present-day claim, or a more recent trustworthy source conflicts and the conflict remains unresolved
- `medio`: the source is `intermediaria`, the claim depends on current validity, and no stronger recent conflict has been identified
- `baixo`: the source is `recente`, or the claim is in `baixa` sensitivity context with explicit freshness status and no stronger recent conflict

## Temporal Sensitivity Matrix

Use the following matrix before assigning `time_sensitivity_context`:

- `alta`: laws, regulations, fiscal rules, vendor policies, pricing, security advisories, API behavior, official product documentation, or any domain where a recent change can invalidate execution quickly
- `media`: standards guidance, implementation guides, platform recommendations, operational documentation, or technical references that may change but not at high daily volatility
- `baixa`: conceptual architecture, foundational references, historical records, or stable explanatory material where age alone does not destroy usefulness

Temporal interpretation must follow this matrix:

- `alta`: missing date or stale dating triggers the downgrade rules below whenever the claim depends on current validity
- `media`: an older source may remain `provavel` only when freshness is explicit and no newer trustworthy conflict exists
- `baixa`: age is disclosed and weighted, but does not force downgrade by itself unless the claim depends on present-day validity or a newer trustworthy conflict exists
- when one present-day claim mixes recent and stale or undated sources, the temporal basis must say that the claim is mixed instead of saying it is simply anchored by recent evidence

## Current Threshold Windows

The current tracked implementation classifies freshness with the following date windows:

- `alta`: `recente` up to 90 days; `intermediaria` up to 365 days; after that `possivelmente_desatualizada`
- `media`: `recente` up to 365 days; `intermediaria` up to 1095 days; after that `possivelmente_desatualizada`
- `baixa`: `recente` up to 1095 days; `intermediaria` up to 3650 days; after that `possivelmente_desatualizada`

## Objective Downgrade Rules

Every external finding enters the component as `provavel`.
It must be downgraded to `hipotese` when at least one of the following is true:

- `source_date` is missing and the claim depends on current validity in an `alta` sensitivity context
- the finding relies on a `possivelmente_desatualizada` source and the claim depends on present-day correctness
- a more recent trustworthy source reaches an incompatible operational conclusion about the same claim and the conflict remains unresolved
- the claim depends on normative force, but no trusted source is `primaria_normativa`
- the claim cannot identify at least one attributable source entry in `source_register`
- the temporal basis cannot explain why an older source is still operationally relevant

A finding may remain `provavel` only when all of the following are true:

- the claim identifies one or more attributable `source_register` entries
- the freshness status is explicit
- no stronger and more recent trustworthy source reaches an incompatible operational conclusion about the same claim
- none of the mandatory downgrade conditions above applies

A finding must be discarded instead of downgraded when:

- the source is untrusted for that run
- the source URL is outside the enforced `search_scope`
- the claim cannot be attributed clearly enough to any source entry
- the output cannot explain why the item belongs even as `hipotese`

## Activation Rules

The component may be activated only when at least one of the following is true:

- the path depends on a temporally unstable external fact
- the path depends on law, regulation, fiscal rule, standard, vendor documentation, or official technical documentation that may have changed
- more than one plausible path exists and the difference depends on current external facts
- there is a concrete risk that an internally coherent decision is being made on stale outside information

The component must not be activated when:

- the internal evidence is already sufficient and stable
- the question is purely local to the repository or runtime behavior
- the operator is using it only to confirm a preferred conclusion
- the round can already close safely with internal evidence alone

## Blocking Rules

Discard an external item immediately when:

- the source is not official, primary, or otherwise pre-authorized as trustworthy for that run
- the source cannot be attributed clearly
- the source date is missing in a temporally sensitive claim and the claim cannot populate the required output fields even as `hipotese`

If external and internal evidence conflict:

- record the item under `conflitos`
- describe the conflict explicitly
- do not resolve it automatically
- send it forward to the round's evidence-review step

If no trustworthy external source is available:

- the component must report the gap explicitly
- the round must not use the component output as a certainty upgrade

If an external item lacks a valid promotion basis:

- it must remain `provavel`, or
- be reclassified as `hipotese` when one or more mandatory downgrade conditions applies

If an external item has temporal risk, it must lose weight automatically when:

- `source_date` is unavailable
- the source is old relative to an `alta` sensitivity context
- a more recent trustworthy source materially conflicts with it

If `temporal_risk` is `alto`:

- the item must be reclassified as `hipotese`

No item may leave this component as `comprovado`.

No direct decision is permitted from this component under any condition.

## Required Downstream Handling

Its output must always pass through:

1. explicit evidence review against canonical context
2. conditional risk review, when multiple paths, material risk, or chain effects justify it
3. the round's pre-execution decision authority

The evidence-review step must decide how the external findings interact with already-proven internal evidence.
The conditional risk-review step must measure what external change would do to the path risk if that review is justified.
The round's pre-execution decision authority remains outside this component; this downstream handling does not create a new gate or authority.
This downstream handling applies only when the component was explicitly activated for the round; it does not make the component a permanent mandatory gate.

## Limits Of Action

The component never:

- joins the fixed role roster
- becomes a permanent mandatory round step
- executes commands against the core
- updates `.cerebro/`
- updates `state.json`
- selects canonical `sources`
- closes a round
- approves a path

## Misuse Risks

Primary misuse risks:

- treating internet output as authority
- laundering weak outside evidence into apparent certainty
- treating old but correct historical data as if it were current operational guidance
- turning source lookup into a second source of truth
- using it to confirm an opinion instead of challenge a path
- over-activating it until the protocol becomes bureaucratic
- leaking sensitive context into external search unnecessarily

Operational misuse signal:

- if operators start saying "the external verifier decided" or "the internet said so", the component is being misused and the round must be corrected

## Implementation Posture

This document specifies the component and the current tracked implementation boundary.

Any future increment must:

- stay outside the core
- remain read-only
- remain non-canonical
- add proportional adversarial and regression coverage
- stay within one minimum safe external increment
