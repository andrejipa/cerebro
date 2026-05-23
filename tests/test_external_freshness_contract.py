from __future__ import annotations

import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

import extensions.external_freshness_verifier as external_freshness_module
import extensions.external_freshness_verifier.contract as external_freshness_contract
from cli.commands.init import run_init
from core.state_store import StateStore
from extensions.external_freshness_verifier import (
    EXTERNAL_BUNDLE_NORMALIZATION_REPORT_SCHEMA_V1,
    EXTERNAL_FRESHNESS_CONTRACT_VERSION,
    EXTERNAL_FRESHNESS_REPORT_SCHEMA_V1,
    EXTERNAL_FRESHNESS_REQUEST_SCHEMA_V1,
    ExternalFindingInput,
    ExternalFreshnessRequest,
    ExternalFreshnessVerifierError,
    ExternalSourceInput,
    build_external_bundle_normalization_report_fixture_v1,
    build_external_freshness_report_fixture_v1,
    build_external_freshness_request_fixture_v1,
    get_external_freshness_contract_schemas,
    get_external_freshness_contract_fixture_payloads_v1,
    normalize_external_bundle,
    serialize_external_bundle_normalization_report,
    serialize_external_freshness_report,
    serialize_external_freshness_request,
    validate_external_bundle_normalization_report_payload,
    validate_external_freshness_report_payload,
    validate_external_freshness_request_payload,
    verify_external_freshness,
)
from tests.runtime_fixtures import seed_checkpointed_runtime


SUPPORTED_SCHEMA_NODE_KEYS = {
    "$id",
    "$schema",
    "title",
    "type",
    "enum",
    "const",
    "required",
    "additionalProperties",
    "properties",
    "items",
}


def _seed_runtime(root: Path) -> StateStore:
    run_init(root, None)
    store, _ = seed_checkpointed_runtime(root)
    store.validate_state()
    return store


def _build_request() -> ExternalFreshnessRequest:
    return ExternalFreshnessRequest(
        question_or_proposal="Podemos seguir com a mudanca?",
        trigger_reason="precisa confirmar regra externa atual",
        paths_under_review=("seguir",),
        search_scope=("receita.economia.gov.br",),
        allowed_source_classes=("primaria_normativa", "primaria_tecnica"),
        internal_proven_items=("source:tracked.txt",),
        sources=(
            ExternalSourceInput(
                source_id="s1",
                url="https://normas.receita.economia.gov.br/norma",
                source_authority="Receita",
                source_class="primaria_normativa",
                source_date="2026-03-15",
                collected_at="2026-04-11T12:00:00+00:00",
                source_title="Norma oficial",
                citation_locator="section-4",
                content_hash="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                acquisition_method="web_search",
                acquisition_query="norma receita abril 2026",
                acquisition_trace_id="ws_123",
            ),
        ),
        findings=(
            ExternalFindingInput(
                claim_id="c1",
                topic_id="topic-1",
                summary="A regra normativa segue valida para a execucao proposta.",
                source_ids=("s1",),
                claim_time_sensitivity_context="alta",
                path_effect="supports_path",
                depends_on_current_validity=True,
                requires_normative_force=True,
                internal_confirmation_reference="source:tracked.txt",
            ),
        ),
    )


class ExternalFreshnessContractTests(unittest.TestCase):
    def _assert_schema_uses_only_supported_keywords(self, schema: dict) -> None:
        unknown_keys = sorted(set(schema) - SUPPORTED_SCHEMA_NODE_KEYS)
        self.assertEqual(unknown_keys, [], f"unsupported schema keywords: {', '.join(unknown_keys)}")

        for nested_schema in schema.get("properties", {}).values():
            self._assert_schema_uses_only_supported_keywords(nested_schema)

        items_schema = schema.get("items")
        if isinstance(items_schema, dict):
            self._assert_schema_uses_only_supported_keywords(items_schema)

    def test_request_payload_is_versioned_and_validated(self) -> None:
        payload = serialize_external_freshness_request(_build_request())

        self.assertEqual(payload["schema_version"], EXTERNAL_FRESHNESS_CONTRACT_VERSION)
        self.assertNotIn("canonical_context_relevant", payload)
        validate_external_freshness_request_payload(payload)

    def test_normalization_report_payload_is_versioned_and_validated(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            _seed_runtime(root)

            report = normalize_external_bundle(root, _build_request(), normalized_at="2026-04-11T12:00:00+00:00")
            payload = serialize_external_bundle_normalization_report(report)

            self.assertEqual(payload["schema_version"], EXTERNAL_FRESHNESS_CONTRACT_VERSION)
            self.assertEqual(payload["component"], "Normalizador de Bundle Externo")
            validate_external_bundle_normalization_report_payload(payload)

    def test_final_report_payload_is_versioned_and_validated(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            _seed_runtime(root)

            report = verify_external_freshness(root, _build_request(), queried_at="2026-04-11T12:00:00+00:00")
            payload = serialize_external_freshness_report(report)

            self.assertEqual(payload["schema_version"], EXTERNAL_FRESHNESS_CONTRACT_VERSION)
            self.assertEqual(payload["component"], "Verificador de Atualidade Externa")
            validate_external_freshness_report_payload(payload)

    def test_contract_validator_rejects_extra_key_and_wrong_version(self) -> None:
        payload = serialize_external_freshness_request(_build_request())
        payload["unexpected"] = "nope"

        with self.assertRaises(ExternalFreshnessVerifierError):
            validate_external_freshness_request_payload(payload)

        payload = serialize_external_freshness_request(_build_request())
        payload["schema_version"] = "external_freshness_contract.v2"

        with self.assertRaises(ExternalFreshnessVerifierError):
            validate_external_freshness_request_payload(payload)

    def test_contract_schemas_are_strict_and_public(self) -> None:
        schemas = get_external_freshness_contract_schemas()

        self.assertEqual(set(schemas), {"request", "normalization_report", "report"})
        self.assertEqual(EXTERNAL_FRESHNESS_REQUEST_SCHEMA_V1["$schema"], "https://json-schema.org/draft/2020-12/schema")
        self.assertEqual(EXTERNAL_BUNDLE_NORMALIZATION_REPORT_SCHEMA_V1["properties"]["schema_version"]["const"], EXTERNAL_FRESHNESS_CONTRACT_VERSION)
        self.assertEqual(EXTERNAL_FRESHNESS_REPORT_SCHEMA_V1["properties"]["schema_version"]["const"], EXTERNAL_FRESHNESS_CONTRACT_VERSION)
        self.assertEqual(EXTERNAL_FRESHNESS_REPORT_SCHEMA_V1["properties"]["bundle_identity_scope"]["enum"], ["report_scoped"])
        self.assertEqual(
            EXTERNAL_FRESHNESS_REPORT_SCHEMA_V1["properties"]["source_register"]["items"]["properties"]["bundle_identity_scope"]["enum"],
            ["report_scoped"],
        )
        self.assertFalse(EXTERNAL_FRESHNESS_REQUEST_SCHEMA_V1["additionalProperties"])
        self.assertFalse(EXTERNAL_BUNDLE_NORMALIZATION_REPORT_SCHEMA_V1["additionalProperties"])
        self.assertFalse(EXTERNAL_FRESHNESS_REPORT_SCHEMA_V1["additionalProperties"])

    def test_contract_schema_getter_returns_defensive_snapshots(self) -> None:
        schemas = get_external_freshness_contract_schemas()
        schemas["request"]["properties"]["schema_version"]["const"] = "mutated"
        schemas["report"]["properties"]["schema_version"]["const"] = "mutated"

        fresh_schemas = get_external_freshness_contract_schemas()
        self.assertEqual(
            fresh_schemas["request"]["properties"]["schema_version"]["const"],
            EXTERNAL_FRESHNESS_CONTRACT_VERSION,
        )
        self.assertEqual(
            fresh_schemas["report"]["properties"]["schema_version"]["const"],
            EXTERNAL_FRESHNESS_CONTRACT_VERSION,
        )

        payload = serialize_external_freshness_request(_build_request())
        validate_external_freshness_request_payload(payload)

    def test_public_schemas_use_only_validator_supported_keywords(self) -> None:
        for schema in get_external_freshness_contract_schemas().values():
            self._assert_schema_uses_only_supported_keywords(schema)

    def test_schema_getter_returns_defensive_copies(self) -> None:
        schemas = get_external_freshness_contract_schemas()
        schemas["request"]["properties"]["schema_version"]["const"] = "mutated"

        fresh_schemas = get_external_freshness_contract_schemas()

        self.assertEqual(
            fresh_schemas["request"]["properties"]["schema_version"]["const"],
            EXTERNAL_FRESHNESS_CONTRACT_VERSION,
        )
        validate_external_freshness_request_payload(serialize_external_freshness_request(_build_request()))

    def test_public_schema_constant_mutation_does_not_change_validation_snapshots(self) -> None:
        original_request_schema = deepcopy(external_freshness_contract.EXTERNAL_FRESHNESS_REQUEST_SCHEMA_V1)
        original_normalization_schema = deepcopy(external_freshness_contract.EXTERNAL_BUNDLE_NORMALIZATION_REPORT_SCHEMA_V1)
        original_report_schema = deepcopy(external_freshness_contract.EXTERNAL_FRESHNESS_REPORT_SCHEMA_V1)

        try:
            external_freshness_contract.EXTERNAL_FRESHNESS_REQUEST_SCHEMA_V1["properties"]["schema_version"]["const"] = (
                "mutated-request"
            )
            external_freshness_contract.EXTERNAL_BUNDLE_NORMALIZATION_REPORT_SCHEMA_V1["properties"]["schema_version"][
                "const"
            ] = "mutated-normalization"
            external_freshness_contract.EXTERNAL_FRESHNESS_REPORT_SCHEMA_V1["properties"]["schema_version"]["const"] = (
                "mutated-report"
            )

            validate_external_freshness_request_payload(serialize_external_freshness_request(_build_request()))
            validate_external_bundle_normalization_report_payload(
                serialize_external_bundle_normalization_report(build_external_bundle_normalization_report_fixture_v1())
            )
            validate_external_freshness_report_payload(
                serialize_external_freshness_report(build_external_freshness_report_fixture_v1())
            )

            fresh_schemas = get_external_freshness_contract_schemas()
            self.assertEqual(
                fresh_schemas["request"]["properties"]["schema_version"]["const"],
                EXTERNAL_FRESHNESS_CONTRACT_VERSION,
            )
            self.assertEqual(
                fresh_schemas["normalization_report"]["properties"]["schema_version"]["const"],
                EXTERNAL_FRESHNESS_CONTRACT_VERSION,
            )
            self.assertEqual(
                fresh_schemas["report"]["properties"]["schema_version"]["const"],
                EXTERNAL_FRESHNESS_CONTRACT_VERSION,
            )
        finally:
            external_freshness_contract.EXTERNAL_FRESHNESS_REQUEST_SCHEMA_V1.clear()
            external_freshness_contract.EXTERNAL_FRESHNESS_REQUEST_SCHEMA_V1.update(original_request_schema)
            external_freshness_contract.EXTERNAL_BUNDLE_NORMALIZATION_REPORT_SCHEMA_V1.clear()
            external_freshness_contract.EXTERNAL_BUNDLE_NORMALIZATION_REPORT_SCHEMA_V1.update(original_normalization_schema)
            external_freshness_contract.EXTERNAL_FRESHNESS_REPORT_SCHEMA_V1.clear()
            external_freshness_contract.EXTERNAL_FRESHNESS_REPORT_SCHEMA_V1.update(original_report_schema)

    def test_contract_getter_is_canonical_and_public_constants_are_compatibility_snapshots(self) -> None:
        self.assertEqual(
            external_freshness_contract.get_external_freshness_contract_schemas()["request"],
            external_freshness_contract._EXTERNAL_FRESHNESS_REQUEST_SCHEMA_V1_SNAPSHOT,
        )
        self.assertEqual(
            EXTERNAL_FRESHNESS_REQUEST_SCHEMA_V1,
            get_external_freshness_contract_schemas()["request"],
        )

    def test_fixture_payload_getter_is_canonical_and_matches_builder_serialization(self) -> None:
        payloads = get_external_freshness_contract_fixture_payloads_v1()

        self.assertEqual(
            payloads["request"],
            serialize_external_freshness_request(build_external_freshness_request_fixture_v1()),
        )
        self.assertEqual(
            payloads["normalization_report"],
            serialize_external_bundle_normalization_report(build_external_bundle_normalization_report_fixture_v1()),
        )
        self.assertEqual(
            payloads["report"],
            serialize_external_freshness_report(build_external_freshness_report_fixture_v1()),
        )

    def test_fixture_payload_getter_returns_fresh_payloads(self) -> None:
        payloads = get_external_freshness_contract_fixture_payloads_v1()
        payloads["request"]["schema_version"] = "mutated"
        payloads["report"]["schema_version"] = "mutated"

        fresh_payloads = get_external_freshness_contract_fixture_payloads_v1()

        self.assertEqual(fresh_payloads["request"]["schema_version"], EXTERNAL_FRESHNESS_CONTRACT_VERSION)
        self.assertEqual(fresh_payloads["report"]["schema_version"], EXTERNAL_FRESHNESS_CONTRACT_VERSION)

    def test_python_dataclass_fixture_is_not_the_wire_contract(self) -> None:
        request_fixture = build_external_freshness_request_fixture_v1()
        serialized_request = serialize_external_freshness_request(request_fixture)

        self.assertFalse(hasattr(request_fixture, "schema_version"))
        self.assertIsInstance(request_fixture.paths_under_review, tuple)
        self.assertEqual(serialized_request["schema_version"], EXTERNAL_FRESHNESS_CONTRACT_VERSION)
        self.assertIsInstance(serialized_request["paths_under_review"], list)

        with self.assertRaises(ExternalFreshnessVerifierError):
            validate_external_freshness_request_payload(request_fixture)

    def test_python_report_dataclass_is_not_the_wire_contract(self) -> None:
        report_fixture = build_external_freshness_report_fixture_v1()
        serialized_report = serialize_external_freshness_report(report_fixture)

        self.assertFalse(hasattr(report_fixture, "schema_version"))
        self.assertIsInstance(report_fixture.provavel, tuple)
        self.assertEqual(serialized_report["schema_version"], EXTERNAL_FRESHNESS_CONTRACT_VERSION)
        self.assertIsInstance(serialized_report["provavel"], list)

        with self.assertRaises(ExternalFreshnessVerifierError):
            validate_external_freshness_report_payload(report_fixture)

    def test_public_fixture_objects_serialize_and_validate(self) -> None:
        request_payload = serialize_external_freshness_request(build_external_freshness_request_fixture_v1())
        normalization_payload = serialize_external_bundle_normalization_report(
            build_external_bundle_normalization_report_fixture_v1()
        )
        report_payload = serialize_external_freshness_report(build_external_freshness_report_fixture_v1())

        validate_external_freshness_request_payload(request_payload)
        validate_external_bundle_normalization_report_payload(normalization_payload)
        validate_external_freshness_report_payload(report_payload)

    def test_public_fixture_payloads_are_versioned_and_strict(self) -> None:
        payloads = get_external_freshness_contract_fixture_payloads_v1()

        self.assertEqual(set(payloads), {"request", "normalization_report", "report"})
        self.assertEqual(payloads["request"]["schema_version"], EXTERNAL_FRESHNESS_CONTRACT_VERSION)
        self.assertEqual(payloads["normalization_report"]["schema_version"], EXTERNAL_FRESHNESS_CONTRACT_VERSION)
        self.assertEqual(payloads["report"]["schema_version"], EXTERNAL_FRESHNESS_CONTRACT_VERSION)
        self.assertEqual(payloads["report"]["bundle_identity_scope"], "report_scoped")
        self.assertIn("source_aliases", payloads["normalization_report"])
        self.assertIn("source_register", payloads["report"])
        self.assertEqual(payloads["report"]["source_register"][0]["bundle_identity_scope"], "report_scoped")
        validate_external_freshness_request_payload(payloads["request"])
        validate_external_bundle_normalization_report_payload(payloads["normalization_report"])
        validate_external_freshness_report_payload(payloads["report"])

    def test_report_validator_requires_bundle_identity_scope_at_top_level_and_in_source_register(self) -> None:
        payload = get_external_freshness_contract_fixture_payloads_v1()["report"]
        payload.pop("bundle_identity_scope")

        with self.assertRaises(ExternalFreshnessVerifierError):
            validate_external_freshness_report_payload(payload)

    def test_request_validator_rejects_empty_runtime_required_fields(self) -> None:
        payload = get_external_freshness_contract_fixture_payloads_v1()["request"]
        payload["question_or_proposal"] = ""
        payload["trigger_reason"] = ""
        payload["paths_under_review"] = []
        payload["search_scope"] = []
        payload["allowed_source_classes"] = []
        payload["sources"] = []
        payload["findings"] = []

        with self.assertRaises(ExternalFreshnessVerifierError):
            validate_external_freshness_request_payload(payload)

    def test_request_validator_rejects_unknown_source_refs_and_missing_internal_ref_binding(self) -> None:
        payload = get_external_freshness_contract_fixture_payloads_v1()["request"]
        payload["findings"][0]["source_ids"] = ["missing-source"]
        payload["findings"][0]["internal_confirmation_reference"] = "source:missing"

        with self.assertRaises(ExternalFreshnessVerifierError):
            validate_external_freshness_request_payload(payload)

    def test_request_validator_rejects_duplicate_source_and_claim_ids(self) -> None:
        payload = get_external_freshness_contract_fixture_payloads_v1()["request"]
        duplicate_source = deepcopy(payload["sources"][0])
        payload["sources"].append(duplicate_source)

        with self.assertRaises(ExternalFreshnessVerifierError):
            validate_external_freshness_request_payload(payload)

        payload = get_external_freshness_contract_fixture_payloads_v1()["request"]
        duplicate_claim = deepcopy(payload["findings"][0])
        duplicate_claim["source_ids"] = list(duplicate_claim["source_ids"])
        payload["findings"].append(duplicate_claim)

        with self.assertRaises(ExternalFreshnessVerifierError):
            validate_external_freshness_request_payload(payload)

    def test_request_validator_rejects_duplicate_source_ids_inside_one_finding(self) -> None:
        payload = get_external_freshness_contract_fixture_payloads_v1()["request"]
        payload["findings"][0]["source_ids"] = ["s1", "s1"]

        with self.assertRaises(ExternalFreshnessVerifierError):
            validate_external_freshness_request_payload(payload)

    def test_request_validator_rejects_invalid_allowed_source_classes_and_search_scope_entries(self) -> None:
        payload = get_external_freshness_contract_fixture_payloads_v1()["request"]
        payload["allowed_source_classes"] = ["bogus"]

        with self.assertRaises(ExternalFreshnessVerifierError):
            validate_external_freshness_request_payload(payload)

        payload = get_external_freshness_contract_fixture_payloads_v1()["request"]
        payload["search_scope"] = ["docs.example", "https://docs.example/path"]

        with self.assertRaises(ExternalFreshnessVerifierError):
            validate_external_freshness_request_payload(payload)

        payload = get_external_freshness_contract_fixture_payloads_v1()["request"]
        payload["search_scope"] = [""]

        with self.assertRaises(ExternalFreshnessVerifierError):
            validate_external_freshness_request_payload(payload)

        payload = get_external_freshness_contract_fixture_payloads_v1()["request"]
        payload["search_scope"] = ["docs.example:8443"]
        payload["sources"][0]["url"] = "https://docs.example:8443/policy"
        payload["sources"][1]["url"] = "https://docs.example:8443/policy#section-4"

        validate_external_freshness_request_payload(payload)

    def test_request_validator_rejects_invalid_source_temporal_fields_and_hash(self) -> None:
        payload = get_external_freshness_contract_fixture_payloads_v1()["request"]
        payload["sources"][0]["source_date"] = "2026-05-01"

        with self.assertRaises(ExternalFreshnessVerifierError):
            validate_external_freshness_request_payload(payload)

        payload = get_external_freshness_contract_fixture_payloads_v1()["request"]
        payload["sources"][0]["content_hash"] = "not-a-hash"

        with self.assertRaises(ExternalFreshnessVerifierError):
            validate_external_freshness_request_payload(payload)

    def test_report_validator_rejects_non_attributable_claims_and_conflicts(self) -> None:
        payload = get_external_freshness_contract_fixture_payloads_v1()["report"]
        payload["provavel"][0]["source_ids"] = ["missing-source"]
        payload["provavel"][0]["citation_refs"] = ["bundle_missing@section-1"]

        with self.assertRaises(ExternalFreshnessVerifierError):
            validate_external_freshness_report_payload(payload)

        payload = get_external_freshness_contract_fixture_payloads_v1()["report"]
        payload["source_register"][0]["source_strength"] = "descartada"
        payload["provavel"][0]["source_ids"] = ["s2"]
        payload["provavel"][0]["citation_refs"] = ["bundle_fixture_policy@section-4"]

        with self.assertRaises(ExternalFreshnessVerifierError):
            validate_external_freshness_report_payload(payload)

        payload = get_external_freshness_contract_fixture_payloads_v1()["report"]
        payload["conflitos"][0]["conflicting_source_ids"] = ["ghost-a", "ghost-b"]

        with self.assertRaises(ExternalFreshnessVerifierError):
            validate_external_freshness_report_payload(payload)

        payload = get_external_freshness_contract_fixture_payloads_v1()["report"]
        payload["source_register"][0].pop("bundle_identity_scope")

        with self.assertRaises(ExternalFreshnessVerifierError):
            validate_external_freshness_report_payload(payload)

    def test_report_validator_rejects_duplicate_bundle_keys_and_invalid_citation_refs(self) -> None:
        payload = get_external_freshness_contract_fixture_payloads_v1()["report"]
        payload["source_register"][1]["bundle_source_key"] = payload["source_register"][0]["bundle_source_key"]

        with self.assertRaises(ExternalFreshnessVerifierError):
            validate_external_freshness_report_payload(payload)

        payload = get_external_freshness_contract_fixture_payloads_v1()["report"]
        payload["provavel"][0]["citation_refs"] = ["unknown_bundle@section-4"]

        with self.assertRaises(ExternalFreshnessVerifierError):
            validate_external_freshness_report_payload(payload)

    def test_report_validator_rejects_duplicate_claim_ids_and_cross_claim_citation_keys(self) -> None:
        payload = get_external_freshness_contract_fixture_payloads_v1()["report"]
        duplicate_claim = deepcopy(payload["provavel"][0])
        payload["hipotese"].append(duplicate_claim)

        with self.assertRaises(ExternalFreshnessVerifierError):
            validate_external_freshness_report_payload(payload)

    def test_report_validator_rejects_conflicts_without_emitted_claims(self) -> None:
        payload = get_external_freshness_contract_fixture_payloads_v1()["report"]
        payload["conflitos"][0]["claim_id"] = "ghost-claim"

        with self.assertRaises(ExternalFreshnessVerifierError):
            validate_external_freshness_report_payload(payload)

    def test_report_validator_rejects_aliases_without_resolvable_canonical_target(self) -> None:
        payload = get_external_freshness_contract_fixture_payloads_v1()["report"]
        payload["source_aliases"][0]["canonical_source_id"] = "ghost-source"

        with self.assertRaises(ExternalFreshnessVerifierError):
            validate_external_freshness_report_payload(payload)

        payload = get_external_freshness_contract_fixture_payloads_v1()["report"]
        payload["source_aliases"][0]["canonical_resource_url"] = "https://docs.example/other"

        with self.assertRaises(ExternalFreshnessVerifierError):
            validate_external_freshness_report_payload(payload)

        payload = get_external_freshness_contract_fixture_payloads_v1()["report"]
        payload["source_aliases"][0]["original_source_id"] = "s3"

        with self.assertRaises(ExternalFreshnessVerifierError):
            validate_external_freshness_report_payload(payload)

    def test_report_validator_rejects_invalid_source_register_temporal_fields_and_hash(self) -> None:
        payload = get_external_freshness_contract_fixture_payloads_v1()["report"]
        payload["source_register"][0]["source_date"] = "2026-05-01"

        with self.assertRaises(ExternalFreshnessVerifierError):
            validate_external_freshness_report_payload(payload)

        payload = get_external_freshness_contract_fixture_payloads_v1()["report"]
        payload["source_register"][0]["content_hash"] = "bad"

        with self.assertRaises(ExternalFreshnessVerifierError):
            validate_external_freshness_report_payload(payload)

    def test_report_validator_rejects_duplicate_or_empty_locator_citation_refs(self) -> None:
        payload = get_external_freshness_contract_fixture_payloads_v1()["report"]
        citation_ref = payload["provavel"][0]["citation_refs"][0]
        payload["provavel"][0]["citation_refs"] = [citation_ref, citation_ref]

        with self.assertRaises(ExternalFreshnessVerifierError):
            validate_external_freshness_report_payload(payload)

        payload = get_external_freshness_contract_fixture_payloads_v1()["report"]
        payload["provavel"][0]["citation_refs"] = [payload["source_register"][0]["bundle_source_key"] + "@"]

        with self.assertRaises(ExternalFreshnessVerifierError):
            validate_external_freshness_report_payload(payload)

    def test_report_validator_rejects_empty_claim_explanations_and_invalid_promotion_basis(self) -> None:
        payload = get_external_freshness_contract_fixture_payloads_v1()["report"]
        payload["provavel"][0]["why_classified"] = ""

        with self.assertRaises(ExternalFreshnessVerifierError):
            validate_external_freshness_report_payload(payload)

        payload = get_external_freshness_contract_fixture_payloads_v1()["report"]
        payload["provavel"][0]["temporal_basis"] = ""

        with self.assertRaises(ExternalFreshnessVerifierError):
            validate_external_freshness_report_payload(payload)

        payload = get_external_freshness_contract_fixture_payloads_v1()["report"]
        payload["provavel"][0]["promotion_status"] = "promotion_candidate"
        payload["provavel"][0]["promotion_basis"] = "nenhuma"

        with self.assertRaises(ExternalFreshnessVerifierError):
            validate_external_freshness_report_payload(payload)

        payload = get_external_freshness_contract_fixture_payloads_v1()["report"]
        payload["provavel"][0]["promotion_status"] = "not_eligible_for_promotion"
        payload["provavel"][0]["promotion_basis"] = "fonte_normativa_primaria"

        with self.assertRaises(ExternalFreshnessVerifierError):
            validate_external_freshness_report_payload(payload)

        payload = get_external_freshness_contract_fixture_payloads_v1()["report"]
        payload["provavel"][0]["promotion_status"] = "promotion_candidate"
        payload["provavel"][0]["promotion_basis"] = "fonte_normativa_primaria"

        with self.assertRaises(ExternalFreshnessVerifierError):
            validate_external_freshness_report_payload(payload)

    def test_report_validator_rejects_top_level_sensitivity_below_emitted_claims(self) -> None:
        payload = get_external_freshness_contract_fixture_payloads_v1()["report"]
        payload["time_sensitivity_context"] = "baixa"

        with self.assertRaises(ExternalFreshnessVerifierError):
            validate_external_freshness_report_payload(payload)

        payload = get_external_freshness_contract_fixture_payloads_v1()["report"]
        payload["provavel"][0]["citation_refs"] = ["bundle_fixture_policy_older@article"]

        with self.assertRaises(ExternalFreshnessVerifierError):
            validate_external_freshness_report_payload(payload)

    def test_serialized_payload_keeps_content_hash_key_with_empty_placeholder(self) -> None:
        request_payload = serialize_external_freshness_request(build_external_freshness_request_fixture_v1())
        normalization_payload = get_external_freshness_contract_fixture_payloads_v1()["normalization_report"]
        report_payload = get_external_freshness_contract_fixture_payloads_v1()["report"]

        self.assertIn("content_hash", request_payload["sources"][0])
        self.assertEqual(request_payload["sources"][0]["content_hash"], "")
        self.assertIn("content_hash", normalization_payload["normalized_request"]["sources"][0])
        self.assertEqual(normalization_payload["normalized_request"]["sources"][0]["content_hash"], "")
        self.assertIn("content_hash", report_payload["source_register"][0])
        self.assertEqual(report_payload["source_register"][0]["content_hash"], "")

    def test_normalization_report_validator_is_shape_only(self) -> None:
        payload = get_external_freshness_contract_fixture_payloads_v1()["normalization_report"]
        payload["source_aliases"][0]["canonical_source_id"] = "missing-source"
        payload["source_aliases"][0]["canonical_resource_url"] = "https://docs.example/unrelated"

        validate_external_bundle_normalization_report_payload(payload)

    def test_package_root_public_api_is_explicit_and_frozen_by_category(self) -> None:
        canonical_integration_surface = {
            "get_external_freshness_contract_schemas",
            "get_external_freshness_contract_fixture_payloads_v1",
            "serialize_external_freshness_request",
            "serialize_external_bundle_normalization_report",
            "serialize_external_freshness_report",
            "validate_external_freshness_request_payload",
            "validate_external_bundle_normalization_report_payload",
            "validate_external_freshness_report_payload",
        }
        compatibility_and_fixture_helpers = {
            "EXTERNAL_FRESHNESS_CONTRACT_VERSION",
            "EXTERNAL_FRESHNESS_REQUEST_SCHEMA_V1",
            "EXTERNAL_BUNDLE_NORMALIZATION_REPORT_SCHEMA_V1",
            "EXTERNAL_FRESHNESS_REPORT_SCHEMA_V1",
            "build_external_freshness_request_fixture_v1",
            "build_external_bundle_normalization_report_fixture_v1",
            "build_external_freshness_report_fixture_v1",
        }
        python_composition_types = {
            "ExternalBundleNormalizationReport",
            "ExternalBundleSourceAlias",
            "ExternalFindingInput",
            "ExternalFreshnessReport",
            "ExternalFreshnessRequest",
            "ExternalGap",
            "ExternalSourceInput",
            "VerifiedClaim",
            "VerifiedConflict",
            "VerifiedSourceRecord",
        }
        operational_read_only_helpers = {
            "ExternalFreshnessVerifierError",
            "normalize_external_bundle",
            "verify_external_freshness",
            "render_external_freshness_markdown",
            "write_external_freshness_markdown",
        }

        expected_public_api = (
            canonical_integration_surface
            | compatibility_and_fixture_helpers
            | python_composition_types
            | operational_read_only_helpers
        )

        self.assertEqual(set(external_freshness_module.__all__), expected_public_api)
        self.assertEqual(len(external_freshness_module.__all__), len(expected_public_api))

    def test_normalization_report_roundtrip_freezes_query_policy(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            _seed_runtime(root)

            request = ExternalFreshnessRequest(
                question_or_proposal="Pergunta",
                trigger_reason="Motivo",
                paths_under_review=("seguir",),
                search_scope=("docs.example",),
                allowed_source_classes=("primaria_tecnica",),
                internal_proven_items=(),
                sources=(
                    ExternalSourceInput(
                        source_id="s1",
                        url="https://docs.example/policy?view=full",
                        source_authority="Docs",
                        source_class="primaria_tecnica",
                        source_date="2026-04-01",
                        collected_at="2026-04-11T12:00:00+00:00",
                        content_hash="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                    ),
                    ExternalSourceInput(
                        source_id="s2",
                        url="https://docs.example/policy?view=compact#section-2",
                        source_authority="Docs",
                        source_class="primaria_tecnica",
                        source_date="2026-04-01",
                        collected_at="2026-04-11T12:00:00+00:00",
                        content_hash="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                    ),
                ),
                findings=(
                    ExternalFindingInput(
                        claim_id="c1",
                        topic_id="topic-1",
                        summary="Resumo",
                        source_ids=("s1", "s2"),
                        claim_time_sensitivity_context="media",
                        path_effect="supports_path",
                        depends_on_current_validity=True,
                        requires_normative_force=False,
                    ),
                ),
            )

            report = normalize_external_bundle(root, request, normalized_at="2026-04-11T12:00:00+00:00")
            payload = serialize_external_bundle_normalization_report(report)

            self.assertEqual(payload["normalized_request"]["sources"][0]["url"], "https://docs.example/policy?view=compact")
            self.assertEqual(payload["normalized_request"]["findings"][0]["source_ids"], ["s2"])
            self.assertEqual(
                payload["source_aliases"],
                [
                    {
                        "original_source_id": "s1",
                        "canonical_source_id": "s2",
                        "canonical_resource_url": "https://docs.example/policy?view=compact",
                        "reason": "matching_content_hash",
                    }
                ],
            )
            validate_external_bundle_normalization_report_payload(payload)
