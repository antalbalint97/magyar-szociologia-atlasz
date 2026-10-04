"""Provenance layer: source documents, evidence and claims.

The claim is the atomic unit of the dataset. Canonical entities and relations are
*projections* of claims; they never carry a value that no claim supports.

    SourceDocument  (one fetched page, stored as a raw snapshot)
        ^
        | evidence.document_id
    Claim  (subject, predicate, object, time, evidence, method, confidence)
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .enums import (
    AssertionType,
    EntityType,
    EpistemicStatus,
    ExtractionMethod,
    ReviewStatus,
    SourceType,
    TemporalBasis,
)

PARTIAL_DATE_RE = re.compile(r"^\d{4}(-\d{2}(-\d{2})?)?$")
MAX_SNIPPET = 600


def stable_hash(*parts: Any, length: int = 16) -> str:
    payload = json.dumps(parts, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:length]


def check_partial_date(v: str | None) -> str | None:
    """Dates are ISO prefixes (YYYY, YYYY-MM, YYYY-MM-DD). We never pad unknown parts."""
    if v is None:
        return v
    if not PARTIAL_DATE_RE.match(v):
        raise ValueError(f"not a partial ISO date: {v!r}")
    return v


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=False, use_enum_values=False)


class SourceDocument(Strict):
    """One retrieval of one URL. Immutable once written."""

    document_id: str
    source_id: str  # key in config/sources.yaml
    url: str  # as requested
    final_url: str  # after redirects
    canonical_url: str  # after host-alias normalisation, used for identity
    retrieved_at: datetime
    http_status: int
    content_type: str | None = None
    content_sha256: str
    raw_path: str  # relative to data/raw
    page_title: str | None = None
    source_type: SourceType
    institution_id: str | None = None  # canonical id of the publishing institution
    fetcher_version: str
    synthetic: bool = False  # True only for hand-reconstructed test fixtures

    @staticmethod
    def make_id(canonical_url: str, content_sha256: str) -> str:
        return "doc_" + stable_hash(canonical_url, content_sha256)


class Evidence(Strict):
    document_id: str
    locator: str  # parser-level field path, e.g. "profile.position" or a CSS path
    snippet: str  # exact supporting text as it appears in the source

    @field_validator("snippet")
    @classmethod
    def _trim(cls, v: str) -> str:
        v = " ".join(v.split())
        return v if len(v) <= MAX_SNIPPET else v[: MAX_SNIPPET - 1] + "…"


class EntityRef(Strict):
    """A reference to an entity, either source-local (pre-resolution) or canonical."""

    entity_type: EntityType
    source_ref: str | None = None  # "<source_id>|<canonical_url or local key>"
    canonical_id: str | None = None

    @model_validator(mode="after")
    def _one_of(self) -> EntityRef:
        if not (self.source_ref or self.canonical_id):
            raise ValueError("EntityRef needs source_ref or canonical_id")
        return self

    @property
    def key(self) -> str:
        return self.canonical_id or f"{self.entity_type.value}:{self.source_ref}"


class Claim(Strict):
    """A single sourced statement.

    Literal claims set ``value`` (predicate is a property name, e.g. ``name``).
    Relational claims set ``object`` (predicate is a RelationType value).
    """

    claim_id: str = ""
    subject: EntityRef
    predicate: str
    value: Any = None
    object: EntityRef | None = None
    qualifiers: dict[str, Any] = Field(default_factory=dict)

    valid_from: str | None = None
    valid_until: str | None = None
    temporal_basis: TemporalBasis = TemporalBasis.UNKNOWN
    observed_at: datetime

    evidence: Evidence
    extraction_method: ExtractionMethod
    parser: str  # e.g. "tk.profile"
    parser_version: str
    epistemic_status: EpistemicStatus
    assertion_type: AssertionType | None = None
    derivation_method: str | None = None  # required unless OBSERVED
    derived_from: list[str] = Field(default_factory=list)  # claim ids
    confidence: float = Field(ge=0.0, le=1.0)
    review_status: ReviewStatus = ReviewStatus.UNREVIEWED

    @field_validator("valid_from", "valid_until")
    @classmethod
    def _dates(cls, v: str | None) -> str | None:
        return check_partial_date(v)

    @model_validator(mode="after")
    def _consistency(self) -> Claim:
        if (self.value is None) == (self.object is None):
            raise ValueError("a claim has exactly one of value / object")
        if self.epistemic_status is not EpistemicStatus.OBSERVED and not self.derivation_method:
            raise ValueError("non-observed claims must name their derivation_method")
        if (
            self.extraction_method is ExtractionMethod.LLM_ASSISTED
            and self.epistemic_status is EpistemicStatus.OBSERVED
        ):
            raise ValueError("LLM-assisted extraction can never be OBSERVED (spec section 32)")
        if self.valid_from and self.valid_until and self.valid_from[:4] > self.valid_until[:4]:
            raise ValueError("valid_from after valid_until")
        if not self.claim_id:
            self.claim_id = "clm_" + stable_hash(
                self.subject.key,
                self.predicate,
                self.value,
                self.object.key if self.object else None,
                self.qualifiers,
                self.evidence.document_id,
                self.evidence.locator,
            )
        return self


class SourceRecord(Strict):
    """A source-local entity stub produced by a parser, before resolution.

    It carries the minimal descriptive fields resolution needs; everything else
    about the entity is expressed as claims whose subject is this record's ref.
    """

    ref: EntityRef
    label: str
    document_id: str
    hints: dict[str, Any] = Field(default_factory=dict)  # e.g. mtmt_id, orcid, email_domain
