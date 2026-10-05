"""Controlled vocabularies for ontology v0.1.

Every enum here is part of the published schema (see docs/ontology.md). Adding a
member is a minor schema change; renaming or removing one is a major change.
"""

from enum import StrEnum


class EntityType(StrEnum):
    PERSON = "Person"
    INSTITUTION = "Institution"
    ORG_UNIT = "OrganisationalUnit"
    RESEARCH_GROUP = "ResearchGroup"
    PROJECT = "Project"
    PUBLICATION = "Publication"
    JOURNAL = "Journal"
    TOPIC = "ResearchTopic"
    METHOD = "Method"
    TRADITION = "IntellectualTradition"
    EVENT = "Event"
    PERSON_MENTION = "PersonMention"  # evidence: a person-like record observed in one page (ADR-0006)
    PROJECT_MENTION = "ProjectMention"  # evidence: a project-like record observed in one page (ADR-0008)


class RelationType(StrEnum):
    # person <-> organisation
    AFFILIATED_WITH = "AFFILIATED_WITH"  # documented affiliation, role in qualifiers
    WORKED_AT = "WORKED_AT"  # historical employment with explicit dates
    LEADS = "LEADS"
    MEMBER_OF = "MEMBER_OF"
    FOUNDED = "FOUNDED"
    STUDIED_AT = "STUDIED_AT"
    EDITOR_OF = "EDITOR_OF"
    # person <-> person
    COAUTHOR_WITH = "COAUTHOR_WITH"
    CO_PROJECT = "CO_PROJECT"
    SUPERVISED_BY = "SUPERVISED_BY"
    SUPERVISES = "SUPERVISES"
    COLLABORATES_WITH = "COLLABORATES_WITH"
    INTELLECTUALLY_INFLUENCED_BY = "INTELLECTUALLY_INFLUENCED_BY"
    # person/project <-> project
    PARTICIPATES_IN = "PARTICIPATES_IN"
    PRINCIPAL_INVESTIGATOR_OF = "PRINCIPAL_INVESTIGATOR_OF"
    # publications
    AUTHORED = "AUTHORED"
    PUBLISHED_IN = "PUBLISHED_IN"
    CITES = "CITES"
    # intellectual classification
    WORKS_ON_TOPIC = "WORKS_ON_TOPIC"
    USES_METHOD = "USES_METHOD"
    PART_OF_TRADITION = "PART_OF_TRADITION"
    # organisational structure and history
    PART_OF = "PART_OF"  # unit -> parent unit / institution
    HOSTED_BY = "HOSTED_BY"  # project / group -> organisation
    FUNDED_BY = "FUNDED_BY"
    PREDECESSOR_OF = "PREDECESSOR_OF"
    SUCCESSOR_OF = "SUCCESSOR_OF"
    INSTITUTIONAL_SUCCESSOR = "INSTITUTIONAL_SUCCESSOR"
    PARTICIPATED_IN_EVENT = "PARTICIPATED_IN_EVENT"
    # taxonomy
    BROADER = "BROADER"  # topic/method hierarchy


class EpistemicStatus(StrEnum):
    """How we know a statement. Drives the observed/inferred split in the UI."""

    OBSERVED = "OBSERVED"  # stated by a source (a page lists X as member of Y)
    DERIVED = "DERIVED"  # deterministic, auditable transformation of observed text
    INFERRED = "INFERRED"  # statistical / similarity / model-based
    INTERPRETIVE = "INTERPRETIVE"  # analyst judgement, always needs review


class AssertionType(StrEnum):
    """Basis of an affiliation or tradition claim. Never collapsed (spec section 2)."""

    SELF_DECLARED = "SELF_DECLARED"
    INSTITUTIONAL = "INSTITUTIONAL"
    BIBLIOMETRIC = "BIBLIOMETRIC"
    TOPIC_SIMILARITY = "TOPIC_SIMILARITY"
    RESEARCH_GROUP_MEMBERSHIP = "RESEARCH_GROUP_MEMBERSHIP"
    GENEALOGICAL = "GENEALOGICAL"
    ANALYST_CODED = "ANALYST_CODED"
    HISTORICAL_LITERATURE = "HISTORICAL_LITERATURE"


class SourceType(StrEnum):
    INSTITUTIONAL_PROFILE = "institutional_profile"
    INSTITUTIONAL_LISTING = "institutional_listing"
    UNIT_PAGE = "unit_page"
    PROJECT_PAGE = "project_page"
    REGISTRY = "registry"  # MTMT, ORCID, doktori.hu
    ARCHIVE_SNAPSHOT = "archive_snapshot"  # Wayback etc.
    PUBLICATION = "publication"
    CV = "cv"
    LITERATURE = "literature"  # histories, obituaries, memoirs
    MANUAL = "manual"  # decision recorded in review/ by a named reviewer
    TAXONOMY = "taxonomy"  # our own controlled vocabulary files


class ExtractionMethod(StrEnum):
    HTML_PARSER = "html_parser"
    STRUCTURED_API = "structured_api"
    TAXONOMY_KEYWORD_MAP = "taxonomy_keyword_map"
    MANUAL_ENTRY = "manual_entry"
    LLM_ASSISTED = "llm_assisted"  # never OBSERVED; see validation rules


class TemporalBasis(StrEnum):
    EXPLICIT = "EXPLICIT"  # source states the interval
    OBSERVED_AT = "OBSERVED_AT"  # only known to hold when the page was retrieved
    DERIVED = "DERIVED"  # e.g. from first/last appearance across snapshots
    UNKNOWN = "UNKNOWN"


class ReviewStatus(StrEnum):
    UNREVIEWED = "UNREVIEWED"
    CONFIRMED = "CONFIRMED"
    DISPUTED = "DISPUTED"
    REJECTED = "REJECTED"


class IdentityAnchor(StrEnum):
    """Evidence that makes a Person or Project an identity rather than a string (ADR-0006, ADR-0008)."""

    INSTITUTIONAL_PROFILE = "institutional_profile"  # the person's own profile page was fetched
    MTMT = "mtmt"
    ORCID = "orcid"
    PROJECT_PAGE = "project_page"  # the project's own page on an institutional site was fetched
    MANUAL = "manual"  # a reviewer established the identity


class MentionResolutionStatus(StrEnum):
    """How a PersonMention / ProjectMention is tied to its canonical entity (ADR-0006, ADR-0008)."""

    DETERMINISTIC = "DETERMINISTIC"  # exact profile / project URL (canonical or verified alias host), or hard id + name
    MANUAL_CONFIRMED = "MANUAL_CONFIRMED"  # mention_decisions / same_as in review/manual_overrides.yaml
    HIGH_CONFIDENCE_AUTO = "HIGH_CONFIDENCE_AUTO"  # a documented rule of >=2 strong signals (#5)
    REVIEW_REQUIRED = "REVIEW_REQUIRED"  # candidates exist, evidence is insufficient or contradictory
    UNRESOLVED = "UNRESOLVED"  # no candidate identity at all

    @property
    def resolved(self) -> bool:
        return self in (MentionResolutionStatus.DETERMINISTIC, MentionResolutionStatus.MANUAL_CONFIRMED,
                        MentionResolutionStatus.HIGH_CONFIDENCE_AUTO)


class MatchStatus(StrEnum):
    POSSIBLE = "possible_match"
    CONFIRMED = "confirmed_match"
    REJECTED = "rejected_match"


class InstitutionType(StrEnum):
    UNIVERSITY = "university"
    FACULTY = "faculty"
    RESEARCH_CENTRE = "research_centre"
    RESEARCH_INSTITUTE = "research_institute"
    ACADEMY = "academy"
    RESEARCH_NETWORK = "research_network"
    INDEPENDENT_ORG = "independent_organisation"
    ASSOCIATION = "association"
    GOVERNMENT_AGENCY = "government_agency"
    FUNDER = "funder"


class UnitType(StrEnum):
    INSTITUTE = "institute"
    DEPARTMENT = "department"
    RESEARCH_DEPARTMENT = "research_department"  # "kutatási osztály"
    RESEARCH_CENTRE = "research_centre"
    LABORATORY = "laboratory"
    RESEARCH_GROUP = "research_group"
    PROGRAMME = "programme"
    DOCTORAL_SCHOOL = "doctoral_school"
    INFRASTRUCTURE = "infrastructure"
