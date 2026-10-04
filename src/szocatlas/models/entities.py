"""Canonical entities and relations (the CANONICAL DATASET layer).

Canonical records are rebuilt from claims on every run. Each populated field is
listed in ``provenance`` with the claim ids that support it; values that sources
disagree on are kept side by side in ``conflicts`` rather than overwritten.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, ClassVar

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .enums import (
    AssertionType,
    EntityType,
    EpistemicStatus,
    InstitutionType,
    RelationType,
    TemporalBasis,
    UnitType,
)
from .provenance import check_partial_date

ID_PREFIX: dict[EntityType, str] = {
    EntityType.PERSON: "per",
    EntityType.INSTITUTION: "ins",
    EntityType.ORG_UNIT: "unit",
    EntityType.RESEARCH_GROUP: "grp",
    EntityType.PROJECT: "prj",
    EntityType.PUBLICATION: "pub",
    EntityType.JOURNAL: "jnl",
    EntityType.TOPIC: "top",
    EntityType.METHOD: "met",
    EntityType.TRADITION: "trd",
    EntityType.EVENT: "evt",
}


class ConflictingValue(BaseModel):
    model_config = ConfigDict(extra="forbid")
    value: Any
    claim_ids: list[str]


class CanonicalEntity(BaseModel):
    model_config = ConfigDict(extra="forbid")
    entity_type: ClassVar[EntityType]

    canonical_id: str
    label: str
    provenance: dict[str, list[str]] = Field(default_factory=dict)
    conflicts: dict[str, list[ConflictingValue]] = Field(default_factory=dict)
    source_refs: list[str] = Field(default_factory=list)
    first_observed_at: datetime | None = None
    last_verified_at: datetime | None = None

    @field_validator("canonical_id")
    @classmethod
    def _prefix(cls, v: str) -> str:
        prefix = ID_PREFIX[cls.entity_type] + "_"
        if not v.startswith(prefix):
            raise ValueError(f"{cls.__name__} id must start with {prefix!r}: {v}")
        return v


class Person(CanonicalEntity):
    entity_type: ClassVar[EntityType] = EntityType.PERSON

    canonical_name: str  # Hungarian order: family name first
    alternate_names: list[str] = Field(default_factory=list)
    titles: list[str] = Field(default_factory=list)  # PhD, habil., DSc as stated
    orcid: str | None = None
    mtmt_id: str | None = None
    google_scholar_id: str | None = None
    profile_urls: list[str] = Field(default_factory=list)
    personal_website: str | None = None
    birth_year: int | None = None
    death_year: int | None = None
    active_from: str | None = None
    active_until: str | None = None
    position_titles: list[str] = Field(default_factory=list)  # as stated, all current sources
    academic_rank: str | None = None
    disciplines: list[str] = Field(default_factory=list)
    biography_summary: str | None = None  # source text excerpt, never generated
    stated_research_areas: list[str] = Field(default_factory=list)  # free text as published


class Institution(CanonicalEntity):
    entity_type: ClassVar[EntityType] = EntityType.INSTITUTION

    canonical_name: str
    english_name: str | None = None
    alternate_names: list[str] = Field(default_factory=list)  # incl. historical names
    institution_type: InstitutionType | None = None
    city: str | None = None
    country: str = "HU"
    active_from: str | None = None
    active_until: str | None = None
    website: str | None = None


class OrganisationalUnit(CanonicalEntity):
    entity_type: ClassVar[EntityType] = EntityType.ORG_UNIT

    canonical_name: str
    english_name: str | None = None
    alternate_names: list[str] = Field(default_factory=list)
    unit_type: UnitType | None = None
    active_from: str | None = None
    active_until: str | None = None
    website: str | None = None
    description: str | None = None


class ResearchGroup(OrganisationalUnit):
    entity_type: ClassVar[EntityType] = EntityType.RESEARCH_GROUP

    funding_programme: str | None = None  # e.g. "MTA Lendület"


class Project(CanonicalEntity):
    entity_type: ClassVar[EntityType] = EntityType.PROJECT

    title: str
    alternate_titles: list[str] = Field(default_factory=list)
    abstract: str | None = None
    start: str | None = None
    end: str | None = None
    funding_body: str | None = None
    grant_id: str | None = None
    website: str | None = None
    status_label: str | None = None  # "futó" / "lezárt" as the source categorises it


class Journal(CanonicalEntity):
    entity_type: ClassVar[EntityType] = EntityType.JOURNAL

    title: str
    issn: list[str] = Field(default_factory=list)
    website: str | None = None
    active_from: str | None = None
    active_until: str | None = None


class Publication(CanonicalEntity):
    entity_type: ClassVar[EntityType] = EntityType.PUBLICATION

    title: str
    year: int | None = None
    doi: str | None = None
    publication_type: str | None = None
    language: str | None = None
    mtmt_id: str | None = None


class Topic(CanonicalEntity):
    entity_type: ClassVar[EntityType] = EntityType.TOPIC

    key: str  # taxonomy key, e.g. "roma_studies"
    name_en: str
    name_hu: str
    scope_note: str | None = None


class Method(Topic):
    entity_type: ClassVar[EntityType] = EntityType.METHOD


class Tradition(CanonicalEntity):
    """An analytical hypothesis, never a fact. Every member edge needs evidence."""

    entity_type: ClassVar[EntityType] = EntityType.TRADITION

    name: str
    description: str | None = None
    hypothesis_status: str = "candidate"  # candidate | supported | contested | rejected


class Event(CanonicalEntity):
    entity_type: ClassVar[EntityType] = EntityType.EVENT

    name: str
    event_type: str  # merger, split, rename, creation, closure, reform, conference
    date: str | None = None
    description: str | None = None

    @field_validator("date")
    @classmethod
    def _date(cls, v: str | None) -> str | None:
        return check_partial_date(v)


ENTITY_CLASSES: dict[EntityType, type[CanonicalEntity]] = {
    cls.entity_type: cls
    for cls in (
        Person,
        Institution,
        OrganisationalUnit,
        ResearchGroup,
        Project,
        Journal,
        Publication,
        Topic,
        Method,
        Tradition,
        Event,
    )
}


class Relation(BaseModel):
    """A canonical edge. Aggregates every claim that asserts the same edge."""

    model_config = ConfigDict(extra="forbid")

    relation_id: str
    type: RelationType
    source_id: str
    target_id: str
    qualifiers: dict[str, Any] = Field(default_factory=dict)  # role, position title, ...
    valid_from: str | None = None
    valid_until: str | None = None
    temporal_basis: TemporalBasis = TemporalBasis.UNKNOWN
    first_observed_at: datetime | None = None
    last_observed_at: datetime | None = None
    epistemic_status: EpistemicStatus
    assertion_types: list[AssertionType] = Field(default_factory=list)
    derivation_method: str | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    claim_ids: list[str]
    document_ids: list[str] = Field(default_factory=list)

    @property
    def observed(self) -> bool:
        return self.epistemic_status is EpistemicStatus.OBSERVED
