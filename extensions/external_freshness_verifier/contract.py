"""Versioned serializable contract for the external freshness verifier."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, is_dataclass
from datetime import date, datetime
from urllib.parse import urlsplit

from extensions.external_freshness_verifier.verifier import (
    ExternalBundleNormalizationReport,
    ExternalFreshnessReport,
    ExternalFreshnessRequest,
    ExternalFreshnessVerifierError,
)


EXTERNAL_FRESHNESS_CONTRACT_VERSION = "external_freshness_contract.v1"
_JSON_SCHEMA_DRAFT = "https://json-schema.org/draft/2020-12/schema"
_ALLOWED_SOURCE_CLASSES = ("primaria_normativa", "primaria_tecnica", "secundaria_confiavel")


def serialize_external_freshness_request(request: ExternalFreshnessRequest) -> dict:
    """Return the public request payload under the versioned contract."""
    return {
        "schema_version": EXTERNAL_FRESHNESS_CONTRACT_VERSION,
        "question_or_proposal": request.question_or_proposal,
        "trigger_reason": request.trigger_reason,
        "paths_under_review": list(request.paths_under_review),
        "search_scope": list(request.search_scope),
        "allowed_source_classes": list(request.allowed_source_classes),
        "internal_proven_items": list(request.internal_proven_items),
        "sources": [_serialize_value(source) for source in request.sources],
        "findings": [_serialize_value(finding) for finding in request.findings],
    }


def serialize_external_bundle_normalization_report(report: ExternalBundleNormalizationReport) -> dict:
    """Return the public normalization-report payload under the versioned contract."""
    return {
        "schema_version": EXTERNAL_FRESHNESS_CONTRACT_VERSION,
        "component": report.component,
        "normalized_at": report.normalized_at,
        "snapshot_revision": report.snapshot_revision,
        "snapshot_validation_result": report.snapshot_validation_result,
        "canonical_internal_refs": list(report.canonical_internal_refs),
        "source_aliases": [_serialize_value(alias) for alias in report.source_aliases],
        "normalized_request": serialize_external_freshness_request(report.normalized_request),
    }


def serialize_external_freshness_report(report: ExternalFreshnessReport) -> dict:
    """Return the public report payload under the versioned contract."""
    return {
        "schema_version": EXTERNAL_FRESHNESS_CONTRACT_VERSION,
        "component": report.component,
        "queried_at": report.queried_at,
        "question_or_proposal": report.question_or_proposal,
        "trigger_reason": report.trigger_reason,
        "paths_under_review": list(report.paths_under_review),
        "snapshot_revision": report.snapshot_revision,
        "snapshot_validation_result": report.snapshot_validation_result,
        "time_sensitivity_context": report.time_sensitivity_context,
        "source_aliases": [_serialize_value(alias) for alias in report.source_aliases],
        "source_register": [_serialize_value(source) for source in report.source_register],
        "provavel": [_serialize_value(claim) for claim in report.provavel],
        "hipotese": [_serialize_value(claim) for claim in report.hipotese],
        "conflitos": [_serialize_value(conflict) for conflict in report.conflitos],
        "lacunas": [_serialize_value(gap) for gap in report.lacunas],
        "operational_note": report.operational_note,
        "bundle_identity_scope": report.bundle_identity_scope,
    }


def validate_external_freshness_request_payload(payload: object) -> None:
    """Validate one serialized request payload."""
    _validate_against_schema(payload, _EXTERNAL_FRESHNESS_REQUEST_SCHEMA_V1_SNAPSHOT, "$")
    assert isinstance(payload, dict)
    _validate_request_payload_semantics(payload)


def validate_external_bundle_normalization_report_payload(payload: object) -> None:
    """Validate one serialized normalization report payload."""
    _validate_against_schema(payload, _EXTERNAL_BUNDLE_NORMALIZATION_REPORT_SCHEMA_V1_SNAPSHOT, "$")


def validate_external_freshness_report_payload(payload: object) -> None:
    """Validate one serialized final report payload."""
    _validate_against_schema(payload, _EXTERNAL_FRESHNESS_REPORT_SCHEMA_V1_SNAPSHOT, "$")
    assert isinstance(payload, dict)
    _validate_report_payload_semantics(payload)


def get_external_freshness_contract_schemas() -> dict[str, dict]:
    """Return the canonical public schema snapshots exposed by this package."""
    return {
        "request": deepcopy(_EXTERNAL_FRESHNESS_REQUEST_SCHEMA_V1_SNAPSHOT),
        "normalization_report": deepcopy(_EXTERNAL_BUNDLE_NORMALIZATION_REPORT_SCHEMA_V1_SNAPSHOT),
        "report": deepcopy(_EXTERNAL_FRESHNESS_REPORT_SCHEMA_V1_SNAPSHOT),
    }


def _serialize_value(value: object) -> object:
    if is_dataclass(value):
        return {key: _serialize_value(item) for key, item in asdict(value).items()}
    if isinstance(value, tuple):
        return [_serialize_value(item) for item in value]
    if isinstance(value, list):
        return [_serialize_value(item) for item in value]
    return value


def _require_non_empty_string(value: object, path: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ExternalFreshnessVerifierError(f"{path} must be a non-empty string")


def _require_non_empty_array(value: object, path: str) -> None:
    if not isinstance(value, list) or not value:
        raise ExternalFreshnessVerifierError(f"{path} must be a non-empty array")


def _parse_iso_date(raw: str, field_name: str) -> date:
    text = raw.strip()
    if not text:
        raise ExternalFreshnessVerifierError(f"{field_name} must be a non-empty ISO date or datetime string")
    if "T" in text or text.endswith("Z") or "+" in text:
        try:
            return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
        except ValueError as exc:
            raise ExternalFreshnessVerifierError(f"invalid {field_name}: {text}") from exc
    try:
        return date.fromisoformat(text)
    except ValueError as exc:
        raise ExternalFreshnessVerifierError(f"invalid {field_name}: {text}") from exc


def _normalize_search_scope_entry(entry: str) -> str:
    text = entry.strip().lower()
    if not text:
        raise ExternalFreshnessVerifierError("search_scope entries must be non-empty strings")
    if "://" in text:
        parts = urlsplit(text)
        host = parts.hostname or ""
    else:
        parts = urlsplit(f"//{text}")
        host = parts.hostname or ""
    normalized = host.strip(".")
    if not normalized:
        raise ExternalFreshnessVerifierError(f"invalid search_scope entry: {entry}")
    return normalized


def _normalize_url_domain(url: str, source_id: str) -> str:
    parts = urlsplit(url)
    if parts.scheme.lower() != "https":
        raise ExternalFreshnessVerifierError(f"url must use https for source {source_id}")
    host = (parts.hostname or "").strip(".").lower()
    if not host:
        raise ExternalFreshnessVerifierError(f"url must include a hostname for source {source_id}")
    return host


def _domain_allowed(domain: str, search_scope: tuple[str, ...]) -> bool:
    return any(domain == allowed or domain.endswith(f".{allowed}") for allowed in search_scope)


def _is_sha256_hex(value: str) -> bool:
    return len(value) == 64 and all(character in "0123456789abcdef" for character in value)


def _validate_request_payload_semantics(payload: dict) -> None:
    _require_non_empty_string(payload["question_or_proposal"], "$.question_or_proposal")
    _require_non_empty_string(payload["trigger_reason"], "$.trigger_reason")
    _require_non_empty_array(payload["paths_under_review"], "$.paths_under_review")
    _require_non_empty_array(payload["search_scope"], "$.search_scope")
    _require_non_empty_array(payload["allowed_source_classes"], "$.allowed_source_classes")
    _require_non_empty_array(payload["sources"], "$.sources")
    _require_non_empty_array(payload["findings"], "$.findings")

    normalized_scope: list[str] = []
    for index, entry in enumerate(payload["search_scope"]):
        _require_non_empty_string(entry, f"$.search_scope[{index}]")
        normalized_scope.append(_normalize_search_scope_entry(entry))
    if len(set(normalized_scope)) != len(normalized_scope):
        raise ExternalFreshnessVerifierError("$.search_scope contains duplicate normalized domains")

    for index, source_class in enumerate(payload["allowed_source_classes"]):
        _require_non_empty_string(source_class, f"$.allowed_source_classes[{index}]")
        if source_class not in _ALLOWED_SOURCE_CLASSES:
            raise ExternalFreshnessVerifierError(
                f"$.allowed_source_classes[{index}] is not one of the allowed source classes"
            )

    source_ids: set[str] = set()
    for index, source in enumerate(payload["sources"]):
        assert isinstance(source, dict)
        _require_non_empty_string(source["source_id"], f"$.sources[{index}].source_id")
        _require_non_empty_string(source["url"], f"$.sources[{index}].url")
        _require_non_empty_string(source["source_authority"], f"$.sources[{index}].source_authority")
        _require_non_empty_string(source["collected_at"], f"$.sources[{index}].collected_at")
        if source["source_id"] in source_ids:
            raise ExternalFreshnessVerifierError(f"duplicate source_id in request payload: {source['source_id']}")
        source_ids.add(source["source_id"])
        normalized_domain = _normalize_url_domain(source["url"], source["source_id"])
        if not _domain_allowed(normalized_domain, tuple(normalized_scope)):
            raise ExternalFreshnessVerifierError(
                f"$.sources[{index}].url domain is outside $.search_scope: {normalized_domain}"
            )
        collected_at_value = _parse_iso_date(source["collected_at"], f"$.sources[{index}].collected_at")
        source_date = source.get("source_date", "")
        if isinstance(source_date, str) and source_date.strip():
            source_date_value = _parse_iso_date(source_date, f"$.sources[{index}].source_date")
            if source_date_value > collected_at_value:
                raise ExternalFreshnessVerifierError(
                    f"$.sources[{index}].source_date cannot be after $.sources[{index}].collected_at"
                )
        content_hash = source.get("content_hash", "")
        if isinstance(content_hash, str) and content_hash and not _is_sha256_hex(content_hash):
            raise ExternalFreshnessVerifierError(
                f"$.sources[{index}].content_hash must be a 64-char lowercase hex sha256"
            )

    internal_refs = set(payload["internal_proven_items"])
    claim_ids: set[str] = set()
    for index, finding in enumerate(payload["findings"]):
        assert isinstance(finding, dict)
        _require_non_empty_string(finding["claim_id"], f"$.findings[{index}].claim_id")
        _require_non_empty_string(finding["topic_id"], f"$.findings[{index}].topic_id")
        _require_non_empty_string(finding["summary"], f"$.findings[{index}].summary")
        _require_non_empty_array(finding["source_ids"], f"$.findings[{index}].source_ids")
        if finding["claim_id"] in claim_ids:
            raise ExternalFreshnessVerifierError(f"duplicate claim_id in request payload: {finding['claim_id']}")
        claim_ids.add(finding["claim_id"])
        if len(set(finding["source_ids"])) != len(finding["source_ids"]):
            raise ExternalFreshnessVerifierError(f"$.findings[{index}].source_ids contains duplicates")
        unknown_sources = sorted(set(finding["source_ids"]) - source_ids)
        if unknown_sources:
            raise ExternalFreshnessVerifierError(
                f"$.findings[{index}].source_ids references unknown source ids: {', '.join(unknown_sources)}"
            )
        internal_ref = finding.get("internal_confirmation_reference", "")
        if internal_ref and internal_ref not in internal_refs:
            raise ExternalFreshnessVerifierError(
                f"$.findings[{index}].internal_confirmation_reference must be present in $.internal_proven_items"
            )


def _validate_report_payload_semantics(payload: dict) -> None:
    _require_non_empty_string(payload["question_or_proposal"], "$.question_or_proposal")
    _require_non_empty_string(payload["trigger_reason"], "$.trigger_reason")
    _require_non_empty_array(payload["paths_under_review"], "$.paths_under_review")
    _require_non_empty_array(payload["source_register"], "$.source_register")

    source_ids: set[str] = set()
    bundle_keys: set[str] = set()
    source_id_to_bundle_key: dict[str, str] = {}
    source_id_to_strength: dict[str, str] = {}
    for index, source in enumerate(payload["source_register"]):
        assert isinstance(source, dict)
        _require_non_empty_string(source["source_id"], f"$.source_register[{index}].source_id")
        _require_non_empty_string(source["bundle_source_key"], f"$.source_register[{index}].bundle_source_key")
        _require_non_empty_string(source["url"], f"$.source_register[{index}].url")
        _require_non_empty_string(source["source_authority"], f"$.source_register[{index}].source_authority")
        _require_non_empty_string(source["collected_at"], f"$.source_register[{index}].collected_at")
        if source["source_id"] in source_ids:
            raise ExternalFreshnessVerifierError(f"duplicate source_id in report payload: {source['source_id']}")
        if source["bundle_source_key"] in bundle_keys:
            raise ExternalFreshnessVerifierError(
                f"duplicate bundle_source_key in report payload: {source['bundle_source_key']}"
            )
        source_ids.add(source["source_id"])
        bundle_keys.add(source["bundle_source_key"])
        source_id_to_bundle_key[source["source_id"]] = source["bundle_source_key"]
        source_id_to_strength[source["source_id"]] = source["source_strength"]
        _normalize_url_domain(source["url"], source["source_id"])
        collected_at_value = _parse_iso_date(source["collected_at"], f"$.source_register[{index}].collected_at")
        source_date = source.get("source_date", "")
        if isinstance(source_date, str) and source_date.strip():
            source_date_value = _parse_iso_date(source_date, f"$.source_register[{index}].source_date")
            if source_date_value > collected_at_value:
                raise ExternalFreshnessVerifierError(
                    f"$.source_register[{index}].source_date cannot be after $.source_register[{index}].collected_at"
                )
        content_hash = source.get("content_hash", "")
        if isinstance(content_hash, str) and content_hash and not _is_sha256_hex(content_hash):
            raise ExternalFreshnessVerifierError(
                f"$.source_register[{index}].content_hash must be a 64-char lowercase hex sha256"
            )

    claim_ids: set[str] = set()
    highest_claim_sensitivity_rank = 0
    for section in ("provavel", "hipotese"):
        for index, claim in enumerate(payload[section]):
            assert isinstance(claim, dict)
            _require_non_empty_string(claim["claim_id"], f"$.{section}[{index}].claim_id")
            _require_non_empty_string(claim["summary"], f"$.{section}[{index}].summary")
            _require_non_empty_string(claim["why_classified"], f"$.{section}[{index}].why_classified")
            _require_non_empty_string(claim["temporal_basis"], f"$.{section}[{index}].temporal_basis")
            _require_non_empty_array(claim["source_ids"], f"$.{section}[{index}].source_ids")
            _require_non_empty_array(claim["citation_refs"], f"$.{section}[{index}].citation_refs")
            claim_id = claim["claim_id"]
            if claim_id in claim_ids:
                raise ExternalFreshnessVerifierError(f"duplicate claim_id in report payload: {claim_id}")
            claim_ids.add(claim_id)
            highest_claim_sensitivity_rank = max(
                highest_claim_sensitivity_rank,
                {"baixa": 1, "media": 2, "alta": 3}[claim["claim_time_sensitivity_context"]],
            )
            if len(set(claim["source_ids"])) != len(claim["source_ids"]):
                raise ExternalFreshnessVerifierError(f"$.{section}[{index}].source_ids contains duplicates")
            unknown_sources = sorted(set(claim["source_ids"]) - source_ids)
            if unknown_sources:
                raise ExternalFreshnessVerifierError(
                    f"$.{section}[{index}].source_ids references unknown source ids: {', '.join(unknown_sources)}"
                )
            if all(source_id_to_strength[source_id] == "descartada" for source_id in claim["source_ids"]):
                raise ExternalFreshnessVerifierError(
                    f"$.{section}[{index}].source_ids must include at least one non-descartada source"
                )
            has_primary_normative = any(
                source_id_to_strength[source_id] == "primaria_normativa" for source_id in claim["source_ids"]
            )
            if claim["promotion_status"] == "promotion_candidate":
                if claim["promotion_basis"] == "nenhuma":
                    raise ExternalFreshnessVerifierError(
                        f"$.{section}[{index}] promotion_candidate must declare a non-empty promotion basis"
                    )
                if not has_primary_normative:
                    raise ExternalFreshnessVerifierError(
                        f"$.{section}[{index}] promotion_candidate requires at least one primaria_normativa source"
                    )
            elif claim["promotion_basis"] != "nenhuma":
                raise ExternalFreshnessVerifierError(
                    f"$.{section}[{index}] non-promotable claims must use promotion_basis='nenhuma'"
                )
            allowed_citation_keys = {source_id_to_bundle_key[source_id] for source_id in claim["source_ids"]}
            seen_citation_refs: set[str] = set()
            for citation_ref in claim["citation_refs"]:
                _require_non_empty_string(citation_ref, f"$.{section}[{index}].citation_refs[]")
                if citation_ref in seen_citation_refs:
                    raise ExternalFreshnessVerifierError(
                        f"$.{section}[{index}].citation_refs contains duplicates"
                    )
                seen_citation_refs.add(citation_ref)
                citation_key = citation_ref.split("@", maxsplit=1)[0]
                if citation_key not in bundle_keys:
                    raise ExternalFreshnessVerifierError(
                        f"$.{section}[{index}].citation_refs references unknown bundle_source_key: {citation_key}"
                    )
                if citation_ref.endswith("@"):
                    raise ExternalFreshnessVerifierError(
                        f"$.{section}[{index}].citation_refs must not end with an empty locator"
                    )
                if citation_key not in allowed_citation_keys:
                    raise ExternalFreshnessVerifierError(
                        f"$.{section}[{index}].citation_refs must resolve inside the claim source_ids"
                    )

    top_rank = {"baixa": 1, "media": 2, "alta": 3}[payload["time_sensitivity_context"]]
    if top_rank < highest_claim_sensitivity_rank:
        raise ExternalFreshnessVerifierError(
            "$.time_sensitivity_context cannot be lower than the highest emitted claim_time_sensitivity_context"
        )

    alias_original_ids: set[str] = set()
    for index, alias in enumerate(payload["source_aliases"]):
        assert isinstance(alias, dict)
        _require_non_empty_string(alias["original_source_id"], f"$.source_aliases[{index}].original_source_id")
        _require_non_empty_string(alias["canonical_source_id"], f"$.source_aliases[{index}].canonical_source_id")
        _require_non_empty_string(alias["canonical_resource_url"], f"$.source_aliases[{index}].canonical_resource_url")
        if alias["original_source_id"] in alias_original_ids:
            raise ExternalFreshnessVerifierError(
                f"duplicate original_source_id in report payload aliases: {alias['original_source_id']}"
            )
        alias_original_ids.add(alias["original_source_id"])
        if alias["original_source_id"] == alias["canonical_source_id"]:
            raise ExternalFreshnessVerifierError(
                f"$.source_aliases[{index}] cannot alias a source id to itself"
            )
        if alias["original_source_id"] in source_id_to_bundle_key:
            raise ExternalFreshnessVerifierError(
                f"$.source_aliases[{index}].original_source_id must not reference an emitted canonical source"
            )
        if alias["canonical_source_id"] not in source_id_to_bundle_key:
            raise ExternalFreshnessVerifierError(
                f"$.source_aliases[{index}].canonical_source_id references unknown source id: {alias['canonical_source_id']}"
            )
        canonical_source = next(
            source for source in payload["source_register"] if source["source_id"] == alias["canonical_source_id"]
        )
        if alias["canonical_resource_url"] != canonical_source["url"]:
            raise ExternalFreshnessVerifierError(
                f"$.source_aliases[{index}].canonical_resource_url must match the canonical source url"
            )

    for index, conflict in enumerate(payload["conflitos"]):
        assert isinstance(conflict, dict)
        _require_non_empty_string(conflict["claim_id"], f"$.conflitos[{index}].claim_id")
        _require_non_empty_array(conflict["conflicting_source_ids"], f"$.conflitos[{index}].conflicting_source_ids")
        if conflict["claim_id"] not in claim_ids:
            raise ExternalFreshnessVerifierError(
                f"$.conflitos[{index}].claim_id must reference a claim emitted in $.provavel or $.hipotese"
            )
        if len(set(conflict["conflicting_source_ids"])) != len(conflict["conflicting_source_ids"]):
            raise ExternalFreshnessVerifierError(
                f"$.conflitos[{index}].conflicting_source_ids contains duplicates"
            )
        unknown_sources = sorted(set(conflict["conflicting_source_ids"]) - source_ids)
        if unknown_sources:
            raise ExternalFreshnessVerifierError(
                f"$.conflitos[{index}].conflicting_source_ids references unknown source ids: {', '.join(unknown_sources)}"
            )

    for index, gap in enumerate(payload["lacunas"]):
        assert isinstance(gap, dict)
        _require_non_empty_string(gap["gap_id"], f"$.lacunas[{index}].gap_id")
        _require_non_empty_string(gap["missing_fact"], f"$.lacunas[{index}].missing_fact")
        _require_non_empty_string(gap["why_it_matters"], f"$.lacunas[{index}].why_it_matters")


def _schema_type(expected: str | list[str]) -> tuple[str, ...]:
    if isinstance(expected, list):
        return tuple(expected)
    return (expected,)


def _validate_against_schema(value: object, schema: dict, path: str) -> None:
    schema_types = schema.get("type")
    if schema_types is not None and not _value_matches_types(value, _schema_type(schema_types)):
        raise ExternalFreshnessVerifierError(f"{path} does not match schema type {schema_types}")

    if "enum" in schema and value not in schema["enum"]:
        raise ExternalFreshnessVerifierError(f"{path} is not one of the allowed enum values")

    if "const" in schema and value != schema["const"]:
        raise ExternalFreshnessVerifierError(f"{path} must equal {schema['const']}")

    if schema.get("type") == "object":
        assert isinstance(value, dict)
        required = schema.get("required", [])
        for key in required:
            if key not in value:
                raise ExternalFreshnessVerifierError(f"{path}.{key} is required")
        if schema.get("additionalProperties") is False:
            unknown = sorted(set(value) - set(schema.get("properties", {})))
            if unknown:
                raise ExternalFreshnessVerifierError(f"{path} contains unsupported keys: {', '.join(unknown)}")
        for key, item in value.items():
            property_schema = schema.get("properties", {}).get(key)
            if property_schema is None:
                continue
            _validate_against_schema(item, property_schema, f"{path}.{key}")
        return

    if schema.get("type") == "array":
        assert isinstance(value, list)
        item_schema = schema.get("items")
        if item_schema is None:
            return
        for index, item in enumerate(value):
            _validate_against_schema(item, item_schema, f"{path}[{index}]")


def _value_matches_types(value: object, allowed_types: tuple[str, ...]) -> bool:
    for allowed in allowed_types:
        if allowed == "object" and isinstance(value, dict):
            return True
        if allowed == "array" and isinstance(value, list):
            return True
        if allowed == "string" and isinstance(value, str):
            return True
        if allowed == "integer" and isinstance(value, int) and not isinstance(value, bool):
            return True
        if allowed == "boolean" and isinstance(value, bool):
            return True
    return False


def _string_schema() -> dict:
    return {"type": "string"}


def _string_array_schema() -> dict:
    return {"type": "array", "items": _string_schema()}


def _object_schema(properties: dict, required: tuple[str, ...] | None = None) -> dict:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": list(required if required is not None else tuple(properties)),
        "properties": properties,
    }


def _source_input_schema() -> dict:
    return _object_schema(
        {
            "source_id": _string_schema(),
            "url": _string_schema(),
            "source_authority": _string_schema(),
            "source_class": {"type": "string", "enum": ["primaria_normativa", "primaria_tecnica", "secundaria_confiavel"]},
            "source_date": _string_schema(),
            "collected_at": _string_schema(),
            "source_title": _string_schema(),
            "citation_locator": _string_schema(),
            "content_hash": _string_schema(),
            "acquisition_method": {"type": "string", "enum": ["manual", "web_search", "deep_research", "mcp", "other"]},
            "acquisition_query": _string_schema(),
            "acquisition_trace_id": _string_schema(),
            "notes": _string_schema(),
        }
    )


def _finding_input_schema() -> dict:
    return _object_schema(
        {
            "claim_id": _string_schema(),
            "topic_id": _string_schema(),
            "summary": _string_schema(),
            "source_ids": _string_array_schema(),
            "claim_time_sensitivity_context": {"type": "string", "enum": ["alta", "media", "baixa"]},
            "path_effect": {"type": "string", "enum": ["supports_path", "challenges_path"]},
            "depends_on_current_validity": {"type": "boolean"},
            "requires_normative_force": {"type": "boolean"},
            "internal_confirmation_reference": _string_schema(),
        }
    )


def _source_alias_schema() -> dict:
    return _object_schema(
        {
            "original_source_id": _string_schema(),
            "canonical_source_id": _string_schema(),
            "canonical_resource_url": _string_schema(),
            "reason": {"type": "string", "enum": ["matching_content_hash", "equivalent_resource_url"]},
        }
    )


def _verified_source_schema() -> dict:
    properties = {
        "source_id": _string_schema(),
        "bundle_source_key": _string_schema(),
        "bundle_identity_scope": {"type": "string", "enum": ["report_scoped"]},
        "url": _string_schema(),
        "normalized_domain": _string_schema(),
        "source_title": _string_schema(),
        "source_authority": _string_schema(),
        "source_strength": {"type": "string", "enum": ["primaria_normativa", "primaria_tecnica", "secundaria_confiavel", "descartada"]},
        "source_date": _string_schema(),
        "collected_at": _string_schema(),
        "freshness_status": {"type": "string", "enum": ["recente", "intermediaria", "possivelmente_desatualizada"]},
        "temporal_risk": {"type": "string", "enum": ["baixo", "medio", "alto"]},
        "citation_locator": _string_schema(),
        "content_hash": _string_schema(),
        "acquisition_method": {"type": "string", "enum": ["manual", "web_search", "deep_research", "mcp", "other"]},
        "acquisition_query": _string_schema(),
        "acquisition_trace_id": _string_schema(),
        "notes": _string_schema(),
    }
    return _object_schema(
        properties,
        required=(
            "source_id",
            "bundle_source_key",
            "bundle_identity_scope",
            "url",
            "normalized_domain",
            "source_title",
            "source_authority",
            "source_strength",
            "source_date",
            "collected_at",
            "freshness_status",
            "temporal_risk",
            "citation_locator",
            "content_hash",
            "acquisition_method",
            "acquisition_query",
            "acquisition_trace_id",
            "notes",
        ),
    )


def _verified_claim_schema() -> dict:
    return _object_schema(
        {
            "claim_id": _string_schema(),
            "summary": _string_schema(),
            "source_ids": _string_array_schema(),
            "citation_refs": _string_array_schema(),
            "claim_time_sensitivity_context": {"type": "string", "enum": ["alta", "media", "baixa"]},
            "why_classified": _string_schema(),
            "promotion_status": {"type": "string", "enum": ["promotion_candidate", "not_eligible_for_promotion"]},
            "promotion_basis": {"type": "string", "enum": ["fonte_normativa_primaria", "fonte_normativa_primaria_e_confirmacao_interna_disponivel", "nenhuma"]},
            "temporal_basis": _string_schema(),
            "downgrade_reasons": _string_array_schema(),
        }
    )


def _verified_conflict_schema() -> dict:
    return _object_schema(
        {
            "claim_id": _string_schema(),
            "conflict_type": {"type": "string", "enum": ["externo_mais_recente", "autoridade_divergente"]},
            "conflicting_source_ids": _string_array_schema(),
            "resolution_status": {"type": "string", "enum": ["nao_resolvido", "encaminhado_ao_comprovador"]},
            "why_not_resolved_automatically": _string_schema(),
        }
    )


def _gap_schema() -> dict:
    return _object_schema(
        {
            "gap_id": _string_schema(),
            "missing_fact": _string_schema(),
            "why_it_matters": _string_schema(),
            "required_source_class": {"type": "string", "enum": ["primaria_normativa", "primaria_tecnica", "secundaria_confiavel"]},
        }
    )


EXTERNAL_FRESHNESS_REQUEST_SCHEMA_V1 = {
    "$id": "https://cerebro.local/contracts/external-freshness/request/v1",
    "$schema": _JSON_SCHEMA_DRAFT,
    "title": "External Freshness Request V1",
    **_object_schema(
        {
            "schema_version": {"type": "string", "const": EXTERNAL_FRESHNESS_CONTRACT_VERSION},
            "question_or_proposal": _string_schema(),
            "trigger_reason": _string_schema(),
            "paths_under_review": _string_array_schema(),
            "search_scope": _string_array_schema(),
            "allowed_source_classes": _string_array_schema(),
            "internal_proven_items": _string_array_schema(),
            "sources": {"type": "array", "items": _source_input_schema()},
            "findings": {"type": "array", "items": _finding_input_schema()},
        }
    ),
}

_EXTERNAL_FRESHNESS_REQUEST_SCHEMA_V1_SNAPSHOT = deepcopy(EXTERNAL_FRESHNESS_REQUEST_SCHEMA_V1)


EXTERNAL_BUNDLE_NORMALIZATION_REPORT_SCHEMA_V1 = {
    "$id": "https://cerebro.local/contracts/external-freshness/normalization-report/v1",
    "$schema": _JSON_SCHEMA_DRAFT,
    "title": "External Bundle Normalization Report V1",
    **_object_schema(
        {
            "schema_version": {"type": "string", "const": EXTERNAL_FRESHNESS_CONTRACT_VERSION},
            "component": {"type": "string", "const": "Normalizador de Bundle Externo"},
            "normalized_at": _string_schema(),
            "snapshot_revision": {"type": "integer"},
            "snapshot_validation_result": {"type": "string", "enum": ["ok", "fail"]},
            "canonical_internal_refs": _string_array_schema(),
            "source_aliases": {"type": "array", "items": _source_alias_schema()},
            "normalized_request": EXTERNAL_FRESHNESS_REQUEST_SCHEMA_V1,
        }
    ),
}

_EXTERNAL_BUNDLE_NORMALIZATION_REPORT_SCHEMA_V1_SNAPSHOT = deepcopy(EXTERNAL_BUNDLE_NORMALIZATION_REPORT_SCHEMA_V1)


_REPORT_PROPERTIES_V1 = {
    "schema_version": {"type": "string", "const": EXTERNAL_FRESHNESS_CONTRACT_VERSION},
    "component": {"type": "string", "const": "Verificador de Atualidade Externa"},
    "queried_at": _string_schema(),
    "question_or_proposal": _string_schema(),
    "trigger_reason": _string_schema(),
    "paths_under_review": _string_array_schema(),
    "snapshot_revision": {"type": "integer"},
    "snapshot_validation_result": {"type": "string", "enum": ["ok", "fail"]},
    "time_sensitivity_context": {"type": "string", "enum": ["alta", "media", "baixa"]},
    "bundle_identity_scope": {"type": "string", "enum": ["report_scoped"]},
    "source_aliases": {"type": "array", "items": _source_alias_schema()},
    "source_register": {"type": "array", "items": _verified_source_schema()},
    "provavel": {"type": "array", "items": _verified_claim_schema()},
    "hipotese": {"type": "array", "items": _verified_claim_schema()},
    "conflitos": {"type": "array", "items": _verified_conflict_schema()},
    "lacunas": {"type": "array", "items": _gap_schema()},
    "operational_note": {"type": "string", "const": "external read-only analysis output; non-canonical; not a runtime decision"},
}


EXTERNAL_FRESHNESS_REPORT_SCHEMA_V1 = {
    "$id": "https://cerebro.local/contracts/external-freshness/report/v1",
    "$schema": _JSON_SCHEMA_DRAFT,
    "title": "External Freshness Report V1",
    **_object_schema(
        _REPORT_PROPERTIES_V1,
        required=(
            "schema_version",
            "component",
            "queried_at",
            "question_or_proposal",
            "trigger_reason",
            "paths_under_review",
            "snapshot_revision",
            "snapshot_validation_result",
            "time_sensitivity_context",
            "bundle_identity_scope",
            "source_aliases",
            "source_register",
            "provavel",
            "hipotese",
            "conflitos",
            "lacunas",
            "operational_note",
        ),
    ),
}

_EXTERNAL_FRESHNESS_REPORT_SCHEMA_V1_SNAPSHOT = deepcopy(EXTERNAL_FRESHNESS_REPORT_SCHEMA_V1)

EXTERNAL_FRESHNESS_REQUEST_SCHEMA_V1 = deepcopy(_EXTERNAL_FRESHNESS_REQUEST_SCHEMA_V1_SNAPSHOT)
EXTERNAL_BUNDLE_NORMALIZATION_REPORT_SCHEMA_V1 = deepcopy(_EXTERNAL_BUNDLE_NORMALIZATION_REPORT_SCHEMA_V1_SNAPSHOT)
EXTERNAL_FRESHNESS_REPORT_SCHEMA_V1 = deepcopy(_EXTERNAL_FRESHNESS_REPORT_SCHEMA_V1_SNAPSHOT)

# Compatibility-only public snapshots.
# Canonical contract consumers must prefer get_external_freshness_contract_schemas().
