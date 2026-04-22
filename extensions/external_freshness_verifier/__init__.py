"""Read-only external freshness verifier extension.

Public contract rule:
- use ``get_external_freshness_contract_schemas()`` as the canonical schema surface
- use ``get_external_freshness_contract_fixture_payloads_v1()`` as the canonical fixture payload surface
- use ``serialize_*`` and ``validate_*`` as the canonical wire-contract surface
- treat ``EXTERNAL_*_SCHEMA_V1`` as compatibility snapshots only
- treat ``build_external_*_fixture_v1()`` as Python convenience helpers, not canonical integration payloads
- treat exported ``External*`` dataclasses as Python composition helpers, not canonical wire payloads
- treat exported ``Verified*`` dataclasses as Python composition/output helpers, not canonical wire payloads
- do not treat mutable exported schema dicts as validation authority
"""

from extensions.external_freshness_verifier.contract import (
    EXTERNAL_BUNDLE_NORMALIZATION_REPORT_SCHEMA_V1,
    EXTERNAL_FRESHNESS_CONTRACT_VERSION,
    EXTERNAL_FRESHNESS_REPORT_SCHEMA_V1,
    EXTERNAL_FRESHNESS_REQUEST_SCHEMA_V1,
    get_external_freshness_contract_schemas,
    serialize_external_bundle_normalization_report,
    serialize_external_freshness_report,
    serialize_external_freshness_request,
    validate_external_bundle_normalization_report_payload,
    validate_external_freshness_report_payload,
    validate_external_freshness_request_payload,
)
from extensions.external_freshness_verifier.fixtures import (
    build_external_bundle_normalization_report_fixture_v1,
    build_external_freshness_report_fixture_v1,
    build_external_freshness_request_fixture_v1,
    get_external_freshness_contract_fixture_payloads_v1,
)
from extensions.external_freshness_verifier.verifier import (
    ExternalBundleNormalizationReport,
    ExternalBundleSourceAlias,
    ExternalFindingInput,
    ExternalFreshnessReport,
    ExternalFreshnessRequest,
    ExternalFreshnessVerifierError,
    ExternalGap,
    ExternalSourceInput,
    VerifiedClaim,
    VerifiedConflict,
    VerifiedSourceRecord,
    normalize_external_bundle,
    render_external_freshness_markdown,
    verify_external_freshness,
    write_external_freshness_markdown,
)

__all__ = [
    "EXTERNAL_BUNDLE_NORMALIZATION_REPORT_SCHEMA_V1",
    "EXTERNAL_FRESHNESS_CONTRACT_VERSION",
    "EXTERNAL_FRESHNESS_REPORT_SCHEMA_V1",
    "EXTERNAL_FRESHNESS_REQUEST_SCHEMA_V1",
    "ExternalBundleNormalizationReport",
    "ExternalBundleSourceAlias",
    "ExternalFindingInput",
    "ExternalFreshnessReport",
    "ExternalFreshnessRequest",
    "ExternalFreshnessVerifierError",
    "ExternalGap",
    "ExternalSourceInput",
    "VerifiedClaim",
    "VerifiedConflict",
    "VerifiedSourceRecord",
    "build_external_bundle_normalization_report_fixture_v1",
    "build_external_freshness_report_fixture_v1",
    "build_external_freshness_request_fixture_v1",
    "get_external_freshness_contract_schemas",
    "get_external_freshness_contract_fixture_payloads_v1",
    "normalize_external_bundle",
    "render_external_freshness_markdown",
    "serialize_external_bundle_normalization_report",
    "serialize_external_freshness_report",
    "serialize_external_freshness_request",
    "validate_external_bundle_normalization_report_payload",
    "validate_external_freshness_report_payload",
    "validate_external_freshness_request_payload",
    "verify_external_freshness",
    "write_external_freshness_markdown",
]
