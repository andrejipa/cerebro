from __future__ import annotations

from dataclasses import dataclass
import hashlib


VALID_POLARITIES = {"positive", "negative", "unknown", "prohibited", "required"}
VALID_MODALITIES = {"factual", "normative", "procedural", "temporal", "meta"}
VALID_CRITICALITY_HINTS = {"unknown", "low", "medium", "high", "critical"}
VALID_SOURCE_ROLES = {"primary", "projection", "citation", "derived", "historical"}
VALID_EXTRACTION_BASES = {"explicit", "structured_absence", "supersession_absence"}


@dataclass(frozen=True)
class SourceText:
    source_path: str
    text: str
    source_role: str = "primary"

    def __post_init__(self) -> None:
        if self.source_role not in VALID_SOURCE_ROLES:
            raise ValueError(f"invalid source_role: {self.source_role}")


@dataclass(frozen=True)
class ClaimCandidate:
    subject: str
    predicate: str
    object: str
    polarity: str
    modality: str
    criticality_hint: str
    source_path: str
    evidence_span: str
    source_role: str
    authority_hint: str
    extraction_basis: str
    claim_id: str = ""
    semantic_id: str = ""
    evidence_id: str = ""

    def __post_init__(self) -> None:
        if self.polarity not in VALID_POLARITIES:
            raise ValueError(f"invalid polarity: {self.polarity}")
        if self.modality not in VALID_MODALITIES:
            raise ValueError(f"invalid modality: {self.modality}")
        if self.criticality_hint not in VALID_CRITICALITY_HINTS:
            raise ValueError(f"invalid criticality_hint: {self.criticality_hint}")
        if self.source_role not in VALID_SOURCE_ROLES:
            raise ValueError(f"invalid source_role: {self.source_role}")
        if self.extraction_basis not in VALID_EXTRACTION_BASES:
            raise ValueError(f"invalid extraction_basis: {self.extraction_basis}")
        if not self.source_path:
            raise ValueError("source_path is required")
        if not self.evidence_span:
            raise ValueError("evidence_span is required")
        if not self.claim_id:
            object.__setattr__(self, "claim_id", self._derive_id())
        if not self.semantic_id:
            object.__setattr__(self, "semantic_id", self._derive_semantic_id())
        if not self.evidence_id:
            object.__setattr__(self, "evidence_id", self._derive_evidence_id())

    def _derive_id(self) -> str:
        payload = "|".join(
            (
                self.source_path,
                self.evidence_span,
                self.modality,
                self.subject,
                self.predicate,
                self.object,
                self.polarity,
                self.extraction_basis,
            )
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]

    def _derive_semantic_id(self) -> str:
        payload = "|".join(
            (
                self.source_path,
                self.modality,
                self.subject,
                self.predicate,
                self.object,
                self.polarity,
                self.extraction_basis,
            )
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]

    def _derive_evidence_id(self) -> str:
        payload = "|".join((self.semantic_id, self.source_path, self.evidence_span))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]

    def normalized(self) -> tuple[str, str, str, str, str, str, str, str, str]:
        return (
            self.subject,
            self.predicate,
            self.object,
            self.polarity,
            self.modality,
            self.criticality_hint,
            self.source_path,
            self.source_role,
            self.extraction_basis,
        )
