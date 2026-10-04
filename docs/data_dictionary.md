# Data dictionary (schema 0.1.0)

Generated from `src/szocatlas/models` by `python -m szocatlas.datadict`. Do not edit by hand.

## SourceDocument

One retrieval of one URL. Immutable once written.

| field | type | required |
|---|---|---|
| `document_id` | `str` | yes |
| `source_id` | `str` | yes |
| `url` | `str` | yes |
| `final_url` | `str` | yes |
| `canonical_url` | `str` | yes |
| `retrieved_at` | `datetime` | yes |
| `http_status` | `int` | yes |
| `content_type` | `str \| None` |  |
| `content_sha256` | `str` | yes |
| `raw_path` | `str` | yes |
| `page_title` | `str \| None` |  |
| `source_type` | `SourceType` | yes |
| `institution_id` | `str \| None` |  |
| `fetcher_version` | `str` | yes |
| `synthetic` | `bool` |  |

## Evidence



| field | type | required |
|---|---|---|
| `document_id` | `str` | yes |
| `locator` | `str` | yes |
| `snippet` | `str` | yes |

## EntityRef

A reference to an entity, either source-local (pre-resolution) or canonical.

| field | type | required |
|---|---|---|
| `entity_type` | `EntityType` | yes |
| `source_ref` | `str \| None` |  |
| `canonical_id` | `str \| None` |  |

## Claim

A single sourced statement.

| field | type | required |
|---|---|---|
| `claim_id` | `str` |  |
| `subject` | `EntityRef` | yes |
| `predicate` | `str` | yes |
| `value` | `Any` |  |
| `object` | `EntityRef \| None` |  |
| `qualifiers` | `dict[str, Any]` |  |
| `valid_from` | `str \| None` |  |
| `valid_until` | `str \| None` |  |
| `temporal_basis` | `TemporalBasis` |  |
| `observed_at` | `datetime` | yes |
| `evidence` | `Evidence` | yes |
| `extraction_method` | `ExtractionMethod` | yes |
| `parser` | `str` | yes |
| `parser_version` | `str` | yes |
| `epistemic_status` | `EpistemicStatus` | yes |
| `assertion_type` | `AssertionType \| None` |  |
| `derivation_method` | `str \| None` |  |
| `derived_from` | `list[str]` |  |
| `confidence` | `float` | yes |
| `review_status` | `ReviewStatus` |  |

## SourceRecord

A source-local entity stub produced by a parser, before resolution.

| field | type | required |
|---|---|---|
| `ref` | `EntityRef` | yes |
| `label` | `str` | yes |
| `document_id` | `str` | yes |
| `hints` | `dict[str, Any]` |  |
| `identity_anchor` | `str \| None` |  |

## Relation

A canonical edge. Aggregates every claim that asserts the same edge.

| field | type | required |
|---|---|---|
| `relation_id` | `str` | yes |
| `type` | `RelationType` | yes |
| `source_id` | `str` | yes |
| `target_id` | `str` | yes |
| `qualifiers` | `dict[str, Any]` |  |
| `valid_from` | `str \| None` |  |
| `valid_until` | `str \| None` |  |
| `temporal_basis` | `TemporalBasis` |  |
| `first_observed_at` | `datetime \| None` |  |
| `last_observed_at` | `datetime \| None` |  |
| `epistemic_status` | `EpistemicStatus` | yes |
| `assertion_types` | `list[AssertionType]` |  |
| `derivation_method` | `str \| None` |  |
| `confidence` | `float` | yes |
| `claim_ids` | `list[str]` | yes |
| `document_ids` | `list[str]` |  |

## Person (`Person`, id prefix `per_`)

A canonical identity. Exists only with identity evidence (ADR-0006).

| field | type | required |
|---|---|---|
| `canonical_id` | `str` | yes |
| `label` | `str` | yes |
| `provenance` | `dict[str, list[str]]` |  |
| `conflicts` | `dict[str, list[ConflictingValue]]` |  |
| `source_refs` | `list[str]` |  |
| `first_observed_at` | `datetime \| None` |  |
| `last_verified_at` | `datetime \| None` |  |
| `canonical_name` | `str` | yes |
| `identity_evidence` | `list[IdentityAnchor]` |  |
| `alternate_names` | `list[str]` |  |
| `titles` | `list[str]` |  |
| `orcid` | `str \| None` |  |
| `mtmt_id` | `str \| None` |  |
| `google_scholar_id` | `str \| None` |  |
| `profile_urls` | `list[str]` |  |
| `personal_website` | `str \| None` |  |
| `birth_year` | `int \| None` |  |
| `death_year` | `int \| None` |  |
| `active_from` | `str \| None` |  |
| `active_until` | `str \| None` |  |
| `position_titles` | `list[str]` |  |
| `academic_rank` | `str \| None` |  |
| `disciplines` | `list[str]` |  |
| `biography_summary` | `str \| None` |  |
| `stated_research_areas` | `list[str]` |  |

## Institution (`Institution`, id prefix `ins_`)



| field | type | required |
|---|---|---|
| `canonical_id` | `str` | yes |
| `label` | `str` | yes |
| `provenance` | `dict[str, list[str]]` |  |
| `conflicts` | `dict[str, list[ConflictingValue]]` |  |
| `source_refs` | `list[str]` |  |
| `first_observed_at` | `datetime \| None` |  |
| `last_verified_at` | `datetime \| None` |  |
| `canonical_name` | `str` | yes |
| `english_name` | `str \| None` |  |
| `alternate_names` | `list[str]` |  |
| `institution_type` | `InstitutionType \| None` |  |
| `city` | `str \| None` |  |
| `country` | `str` |  |
| `active_from` | `str \| None` |  |
| `active_until` | `str \| None` |  |
| `website` | `str \| None` |  |

## OrganisationalUnit (`OrganisationalUnit`, id prefix `unit_`)



| field | type | required |
|---|---|---|
| `canonical_id` | `str` | yes |
| `label` | `str` | yes |
| `provenance` | `dict[str, list[str]]` |  |
| `conflicts` | `dict[str, list[ConflictingValue]]` |  |
| `source_refs` | `list[str]` |  |
| `first_observed_at` | `datetime \| None` |  |
| `last_verified_at` | `datetime \| None` |  |
| `canonical_name` | `str` | yes |
| `english_name` | `str \| None` |  |
| `alternate_names` | `list[str]` |  |
| `unit_type` | `UnitType \| None` |  |
| `active_from` | `str \| None` |  |
| `active_until` | `str \| None` |  |
| `website` | `str \| None` |  |
| `description` | `str \| None` |  |

## ResearchGroup (`ResearchGroup`, id prefix `grp_`)



| field | type | required |
|---|---|---|
| `canonical_id` | `str` | yes |
| `label` | `str` | yes |
| `provenance` | `dict[str, list[str]]` |  |
| `conflicts` | `dict[str, list[ConflictingValue]]` |  |
| `source_refs` | `list[str]` |  |
| `first_observed_at` | `datetime \| None` |  |
| `last_verified_at` | `datetime \| None` |  |
| `canonical_name` | `str` | yes |
| `english_name` | `str \| None` |  |
| `alternate_names` | `list[str]` |  |
| `unit_type` | `UnitType \| None` |  |
| `active_from` | `str \| None` |  |
| `active_until` | `str \| None` |  |
| `website` | `str \| None` |  |
| `description` | `str \| None` |  |
| `funding_programme` | `str \| None` |  |

## Project (`Project`, id prefix `prj_`)



| field | type | required |
|---|---|---|
| `canonical_id` | `str` | yes |
| `label` | `str` | yes |
| `provenance` | `dict[str, list[str]]` |  |
| `conflicts` | `dict[str, list[ConflictingValue]]` |  |
| `source_refs` | `list[str]` |  |
| `first_observed_at` | `datetime \| None` |  |
| `last_verified_at` | `datetime \| None` |  |
| `title` | `str` | yes |
| `alternate_titles` | `list[str]` |  |
| `abstract` | `str \| None` |  |
| `start` | `str \| None` |  |
| `end` | `str \| None` |  |
| `funding_body` | `str \| None` |  |
| `grant_id` | `str \| None` |  |
| `website` | `str \| None` |  |
| `status_label` | `str \| None` |  |

## Journal (`Journal`, id prefix `jnl_`)



| field | type | required |
|---|---|---|
| `canonical_id` | `str` | yes |
| `label` | `str` | yes |
| `provenance` | `dict[str, list[str]]` |  |
| `conflicts` | `dict[str, list[ConflictingValue]]` |  |
| `source_refs` | `list[str]` |  |
| `first_observed_at` | `datetime \| None` |  |
| `last_verified_at` | `datetime \| None` |  |
| `title` | `str` | yes |
| `issn` | `list[str]` |  |
| `website` | `str \| None` |  |
| `active_from` | `str \| None` |  |
| `active_until` | `str \| None` |  |

## Publication (`Publication`, id prefix `pub_`)



| field | type | required |
|---|---|---|
| `canonical_id` | `str` | yes |
| `label` | `str` | yes |
| `provenance` | `dict[str, list[str]]` |  |
| `conflicts` | `dict[str, list[ConflictingValue]]` |  |
| `source_refs` | `list[str]` |  |
| `first_observed_at` | `datetime \| None` |  |
| `last_verified_at` | `datetime \| None` |  |
| `title` | `str` | yes |
| `year` | `int \| None` |  |
| `doi` | `str \| None` |  |
| `publication_type` | `str \| None` |  |
| `language` | `str \| None` |  |
| `mtmt_id` | `str \| None` |  |

## Topic (`ResearchTopic`, id prefix `top_`)



| field | type | required |
|---|---|---|
| `canonical_id` | `str` | yes |
| `label` | `str` | yes |
| `provenance` | `dict[str, list[str]]` |  |
| `conflicts` | `dict[str, list[ConflictingValue]]` |  |
| `source_refs` | `list[str]` |  |
| `first_observed_at` | `datetime \| None` |  |
| `last_verified_at` | `datetime \| None` |  |
| `key` | `str` | yes |
| `name_en` | `str` | yes |
| `name_hu` | `str` | yes |
| `scope_note` | `str \| None` |  |

## Method (`Method`, id prefix `met_`)



| field | type | required |
|---|---|---|
| `canonical_id` | `str` | yes |
| `label` | `str` | yes |
| `provenance` | `dict[str, list[str]]` |  |
| `conflicts` | `dict[str, list[ConflictingValue]]` |  |
| `source_refs` | `list[str]` |  |
| `first_observed_at` | `datetime \| None` |  |
| `last_verified_at` | `datetime \| None` |  |
| `key` | `str` | yes |
| `name_en` | `str` | yes |
| `name_hu` | `str` | yes |
| `scope_note` | `str \| None` |  |

## Tradition (`IntellectualTradition`, id prefix `trd_`)

An analytical hypothesis, never a fact. Every member edge needs evidence.

| field | type | required |
|---|---|---|
| `canonical_id` | `str` | yes |
| `label` | `str` | yes |
| `provenance` | `dict[str, list[str]]` |  |
| `conflicts` | `dict[str, list[ConflictingValue]]` |  |
| `source_refs` | `list[str]` |  |
| `first_observed_at` | `datetime \| None` |  |
| `last_verified_at` | `datetime \| None` |  |
| `name` | `str` | yes |
| `description` | `str \| None` |  |
| `hypothesis_status` | `str` |  |

## Event (`Event`, id prefix `evt_`)



| field | type | required |
|---|---|---|
| `canonical_id` | `str` | yes |
| `label` | `str` | yes |
| `provenance` | `dict[str, list[str]]` |  |
| `conflicts` | `dict[str, list[ConflictingValue]]` |  |
| `source_refs` | `list[str]` |  |
| `first_observed_at` | `datetime \| None` |  |
| `last_verified_at` | `datetime \| None` |  |
| `name` | `str` | yes |
| `event_type` | `str` | yes |
| `date` | `str \| None` |  |
| `description` | `str \| None` |  |

## PersonMention (`PersonMention`, id prefix `pmn_`)

Evidence: a person-like record observed in one source page (ADR-0006).

| field | type | required |
|---|---|---|
| `canonical_id` | `str` | yes |
| `label` | `str` | yes |
| `provenance` | `dict[str, list[str]]` |  |
| `conflicts` | `dict[str, list[ConflictingValue]]` |  |
| `source_refs` | `list[str]` |  |
| `first_observed_at` | `datetime \| None` |  |
| `last_verified_at` | `datetime \| None` |  |
| `stated_name` | `str` | yes |
| `normalized_name` | `str` | yes |
| `source_ref` | `str` | yes |
| `source_id` | `str` | yes |
| `source_url` | `str` | yes |
| `document_ids` | `list[str]` |  |
| `linked_profile_url` | `str \| None` |  |
| `stated_identifiers` | `dict[str, str]` |  |
| `context` | `list[MentionContext]` |  |
| `resolution` | `MentionResolution` | yes |
| `candidate_person_ids` | `list[str]` |  |

## Enumerations

* **AssertionType**: `SELF_DECLARED`, `INSTITUTIONAL`, `BIBLIOMETRIC`, `TOPIC_SIMILARITY`, `RESEARCH_GROUP_MEMBERSHIP`, `GENEALOGICAL`, `ANALYST_CODED`, `HISTORICAL_LITERATURE`
* **EntityType**: `Person`, `Institution`, `OrganisationalUnit`, `ResearchGroup`, `Project`, `Publication`, `Journal`, `ResearchTopic`, `Method`, `IntellectualTradition`, `Event`, `PersonMention`
* **EpistemicStatus**: `OBSERVED`, `DERIVED`, `INFERRED`, `INTERPRETIVE`
* **ExtractionMethod**: `html_parser`, `structured_api`, `taxonomy_keyword_map`, `manual_entry`, `llm_assisted`
* **IdentityAnchor**: `institutional_profile`, `mtmt`, `orcid`, `manual`
* **InstitutionType**: `university`, `faculty`, `research_centre`, `research_institute`, `academy`, `research_network`, `independent_organisation`, `association`, `government_agency`, `funder`
* **MatchStatus**: `possible_match`, `confirmed_match`, `rejected_match`
* **MentionResolutionStatus**: `DETERMINISTIC`, `MANUAL_CONFIRMED`, `HIGH_CONFIDENCE_AUTO`, `UNRESOLVED`
* **RelationType**: `AFFILIATED_WITH`, `WORKED_AT`, `LEADS`, `MEMBER_OF`, `FOUNDED`, `STUDIED_AT`, `EDITOR_OF`, `COAUTHOR_WITH`, `CO_PROJECT`, `SUPERVISED_BY`, `SUPERVISES`, `COLLABORATES_WITH`, `INTELLECTUALLY_INFLUENCED_BY`, `PARTICIPATES_IN`, `PRINCIPAL_INVESTIGATOR_OF`, `AUTHORED`, `PUBLISHED_IN`, `CITES`, `WORKS_ON_TOPIC`, `USES_METHOD`, `PART_OF_TRADITION`, `PART_OF`, `HOSTED_BY`, `FUNDED_BY`, `PREDECESSOR_OF`, `SUCCESSOR_OF`, `INSTITUTIONAL_SUCCESSOR`, `PARTICIPATED_IN_EVENT`, `BROADER`
* **ReviewStatus**: `UNREVIEWED`, `CONFIRMED`, `DISPUTED`, `REJECTED`
* **SourceType**: `institutional_profile`, `institutional_listing`, `unit_page`, `project_page`, `registry`, `archive_snapshot`, `publication`, `cv`, `literature`, `manual`, `taxonomy`
* **TemporalBasis**: `EXPLICIT`, `OBSERVED_AT`, `DERIVED`, `UNKNOWN`
* **UnitType**: `institute`, `department`, `research_department`, `research_centre`, `laboratory`, `research_group`, `programme`, `doctoral_school`, `infrastructure`
