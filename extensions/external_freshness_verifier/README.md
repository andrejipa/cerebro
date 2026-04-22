# external_freshness_verifier

Read-only extension that classifies supplied external evidence against the current canonical context.

It:

- reads the current snapshot through the public core API
- normalizes equivalent resource URLs before classification
- enforces `search_scope` against supplied source domains
- applies deterministic freshness, downgrade, promotion, and conflict rules
- binds derived reports to the snapshot revision and validation result it actually read
- publishes `external_freshness_contract.v1` for strict serializable request/report payloads
- publishes reusable v1 fixture builders and serialized payload fixtures for integration and regression coverage
- carries citation and provenance metadata such as report-scoped bundle keys, explicit `bundle_identity_scope`, locators, acquisition method, trace id, and a serialized `content_hash` field that uses the empty-string placeholder when unavailable
- renders a derived non-canonical report from supplied external source metadata

Public contract rule:

- prefer `get_external_freshness_contract_schemas()` for public schemas
- prefer `get_external_freshness_contract_fixture_payloads_v1()` for integration-facing fixture payloads
- prefer `serialize_*` and `validate_*` for integration-facing wire payloads
- treat serialized `content_hash` as a structurally required string field and use the empty-string placeholder when no semantic hash is available
- treat `validate_external_freshness_request_payload()` and `validate_external_freshness_report_payload()` as minimum operational-semantic checks, not shape-only validators; they enforce non-empty runtime-required fields, host-normalized `search_scope`, runtime-valid source temporal/hash fields, non-empty claim explanations, promotion basis/status coherence, promotion candidates anchored by at least one `primaria_normativa` source, resolvable source/citation attribution, report claims anchored by at least one non-`descartada` source, and canonical alias/conflict references inside the report
- treat `internal_proven_items` canonicality as a runtime snapshot-aware check; the standalone request validator only proves payload-local binding between `internal_confirmation_reference` and the supplied handles
- treat `validate_external_bundle_normalization_report_payload()` as a structural wire-contract check only; semantic coherence between `source_aliases` and `normalized_request` remains producer/test responsibility
- treat `build_external_*_fixture_v1()` as Python convenience helpers, not canonical integration payloads
- treat serialized fixture payloads as contract-valid reusable samples, not a guaranteed transcript of one specific verifier run
- treat exported `External*` dataclasses as Python convenience types, not canonical wire payloads
- treat exported `Verified*` dataclasses as Python output/composition types, not canonical wire payloads

Public API inventory at package root:

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

It does not:

- fetch the internet by itself
- read runtime JSON directly
- reopen `validate`
- decide runtime truth
- write inside `.cerebro/`
