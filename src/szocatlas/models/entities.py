"""Canonical entities and relations (the CANONICAL DATASET layer).

Canonical records are rebuilt from claims on every run. Each populated field is
listed in ``provenance`` with the claim ids that support it; values that sources
disagree on are kept side by side in ``conflicts`` rather than overwritten.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, ClassVar

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .enums import (
    AssertionType,
    EntityType,
    EpistemicStatus,
    IdentityAnchor,
    InstitutionType,
    MentionResolutionStatus,
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
    EntityType.PERSON_MENTION: "pmn",
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
    """A canonical identity. Exists only with identity evidence (ADR-0006)."""

    entity_type: ClassVar[EntityType] = EntityType.PERSON

    canonical_name: str  # Hungarian order: family name first
    identity_evidence: list[IdentityAnchor] = Field(default_factory=list)
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


class MentionContext(BaseModel):
    """A relation the observing page asserts for the mentioned person."""

    model_config = ConfigDict(extra="forbid")
    relation: RelationType
    direction: str = "out"  # "out": mention is the subject; "in": the object
    target_id: str | None = None  # canonical id of the other side, if it resolved
    target_ref: str | None = None  # source ref of the other side when it did not
    qualifiers: dict[str, Any] = Field(default_factory=dict)
    valid_from: str | None = None  # only when the page states an interval
    valid_until: str | None = None
    snippet: str = ""
    claim_ids: list[str] = Field(default_factory=list)


class MentionResolution(BaseModel):
    """The identity decision for a mention; projected as (:PersonMention)-[:RESOLVES_TO]->(:Person).

    ``signals`` names the evidence the decision used (signal codes, docs/methodology.md §3);
    ``evidence`` carries the details a reviewer needs to check them (urls, alias status,
    matched project or unit). There is no free-floating confidence number.
    """

    model_config = ConfigDict(extra="forbid")
    status: MentionResolutionStatus
    person_id: str | None = None
    method: str | None = None  # rule that fired, e.g. "profile_url", "unit_member_unique", "manual:same_as"
    signals: list[str] = Field(default_factory=list)
    negative_signals: list[str] = Field(default_factory=list)  # contradictions seen (block auto rules)
    evidence: dict[str, Any] = Field(default_factory=dict)
    reason: str | None = None  # why it is not resolved (REVIEW_REQUIRED / UNRESOLVED)
    decision_source: str | None = None  # rule document / override file
    resolver_version: str | None = None
    decided_at: datetime | None = None  # set for manual decisions only; automatic ones are build-independent

    @model_validator(mode="after")
    def _target(self) -> MentionResolution:
        if self.status.resolved != (self.person_id is not None):
            raise ValueError("a resolved mention needs person_id; an unresolved one must not have it")
        return self


class MentionCandidate(BaseModel):
    """A canonical Person this mention might refer to, with the evidence for and against."""

    model_config = ConfigDict(extra="forbid")
    person_id: str
    name_match: str  # NAME_EXACT | SAME_NORMALIZED_NAME | ALTERNATE_NAME_MATCH | NAME_ORDER_VARIANT
    #                  | NAME_INITIALS_COMPATIBLE | SLUG_ONLY
    signals: list[str] = Field(default_factory=list)
    negative_signals: list[str] = Field(default_factory=list)
    rejected: bool = False  # manual not_same_as


class PersonMention(CanonicalEntity):
    """Evidence: a person-like record observed in one source page (ADR-0006).

    Not a mini-Person: it carries only what the page said and the identity decision.
    """

    entity_type: ClassVar[EntityType] = EntityType.PERSON_MENTION

    stated_name: str
    normalized_name: str
    source_ref: str  # the staged source record
    source_id: str
    source_url: str  # the observing page
    document_ids: list[str] = Field(default_factory=list)
    linked_profile_url: str | None = None
    stated_identifiers: dict[str, str] = Field(default_factory=dict)
    context: list[MentionContext] = Field(default_factory=list)
    stated_profile_urls: list[str] = Field(default_factory=list)  # link targets as written (before host aliasing)
    resolution: MentionResolution
    candidates: list[MentionCandidate] = Field(default_factory=list)  # never a resolution by themselves


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
        PersonMention,
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
