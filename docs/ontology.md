# Ontology v0.1

Schema version `0.1.0`. Source of truth: `src/szocatlas/models/` (Pydantic). This document
explains the choices; the data dictionary lists every field.

## 1. Three layers of statements

| Layer | Object | Example |
|---|---|---|
| Evidence | `SourceDocument` | the profile page of Koltai Júlia retrieved 2026-10-04, sha256 … |
| Assertion | `Claim` | "per X — AFFILIATED_WITH → CSS-RECENS, position 'Kutatóprofesszor (TK Recens)'", snippet, parser tk/0.1.0, confidence 0.9 |
| Projection | `CanonicalEntity`, `Relation` | the Person node and the AFFILIATED_WITH edge, carrying every supporting claim id |

A canonical value never exists without at least one claim. Disagreeing claims are
kept (`conflicts`), not overwritten.

## 2. How we know: three independent axes

Every claim and every relation carries all three. They are never collapsed.

**Epistemic status** (`EpistemicStatus`) — drives the observed/inferred split in the UI.

| Value | Meaning | Example |
|---|---|---|
| `OBSERVED` | a source states it | listing page shows X under CSS-RECENS |
| `DERIVED` | deterministic, auditable transformation of observed text | "Romák és … közösségek" → topic `roma_studies` by keyword map v0.1 |
| `INFERRED` | statistical / similarity / model output | bibliometric community, topic similarity, LLM classification |
| `INTERPRETIVE` | analyst judgement | "X belongs to the Kemény tradition" |

Non-observed claims must name a `derivation_method`; LLM-assisted extraction can never be
`OBSERVED` (enforced by the model validator).

**Assertion type** (`AssertionType`) — the basis of an affiliation or tradition claim
(brief §2 and §5): `SELF_DECLARED`, `INSTITUTIONAL`, `BIBLIOMETRIC`, `TOPIC_SIMILARITY`,
`RESEARCH_GROUP_MEMBERSHIP`, `GENEALOGICAL`, `ANALYST_CODED`, `HISTORICAL_LITERATURE`.
Profile pages are recorded as `INSTITUTIONAL` with the qualifier
`authorship: "profile page; author not stated"`, because we cannot tell whether the
researcher or the institution wrote the text.

**Temporal basis** (`TemporalBasis`) — what the dates mean.

| Value | Meaning |
|---|---|
| `EXPLICIT` | the source states the interval ("Időtartam: 2024.01.01-2027.12.31", "(2022-)") |
| `OBSERVED_AT` | only known to hold when the page was retrieved (`first/last_observed_at`) |
| `DERIVED` | computed, e.g. from first/last appearance across archived snapshots |
| `UNKNOWN` | no temporal information (curated structural facts until sourced) |

A current staff page is therefore **not** timeless: the edge says "observed on
2026-10-04", and `valid_from` stays empty until a source gives it.

Dates are ISO prefixes (`YYYY`, `YYYY-MM`, `YYYY-MM-DD`). Unknown parts are omitted, never
padded with `-01-01`.

## 3. Node types

| Type | Id prefix | Node? | Why a node |
|---|---|---|---|
| Person | `per_` | yes | an identity with evidence (`identity_evidence`: institutional profile, MTMT, ORCID or manual); traversal target for every question (ADR-0006) |
| PersonMention | `pmn_` | yes, provenance layer only (`:PersonMention`, not `:Entity`) | one person-like name observed on one source page, with its resolution decision; never counted as a person (ADR-0006) |
| Institution | `ins_` | yes | centrality, mobility, succession |
| OrganisationalUnit | `unit_` | yes | institutes, departments, research centres; hierarchy via `PART_OF` |
| ResearchGroup | `grp_` | yes (also labelled `OrgUnit` in Neo4j) | Lendület groups etc.; has funding programme |
| Project | `prj_` | yes | co-project networks |
| Publication | `pub_` | yes (later) | co-authorship, citation |
| Journal | `jnl_` | yes | editorial boards, publication venues |
| ResearchTopic | `top_` | yes | bipartite person–topic analysis |
| Method | `met_` | yes | separate from topic by design |
| IntellectualTradition | `trd_` | yes | **hypothesis** objects; members need evidence |
| Event | `evt_` | yes | mergers, renames, closures, reforms |
| Claim | — | yes (Neo4j `:Claim`) | provenance traversal |
| SourceDocument | — | yes (Neo4j `:SourceDocument`) | provenance traversal |

Attributes that are *descriptions* stay properties: names, identifiers (MTMT, ORCID),
titles, dates, URLs, position titles (edge qualifier), abstracts. Things people move
*between* or are grouped *by* become nodes. Positions are edge qualifiers, not nodes,
because "Kutatóprofesszor (TK Recens)" only means something on the edge to a unit.

Topic vs method: `ResearchTopic` is *what* is studied (stratification, Roma studies,
social networks as an object), `Method` is *how* (network analysis, NLP, ethnography).
Computational social science is a topic/field; network analysis is a method; they are
separate keys (brief §32). Taxonomies are in `config/taxonomy/` and versioned.

Tradition: `hypothesis_status` is `candidate | supported | contested | rejected`.
`PART_OF_TRADITION` edges must carry an assertion type and evidence; none are created
in phase 1.

## 4. Edge types

All edges carry: `epistemic_status`, `assertion_types`, `confidence`, `claim_ids`,
`document_ids`, `valid_from`, `valid_until`, `temporal_basis`, `first_observed_at`,
`last_observed_at`, `derivation_method` (if not observed) and `qualifiers`.

| Edge | From → To | Phase-1 source | Notes |
|---|---|---|---|
| AFFILIATED_WITH | Person → OrgUnit/Institution | listing + profile | `position_title` qualifier |
| WORKED_AT | Person → OrgUnit/Institution | (historical) | for explicit past employment |
| MEMBER_OF | Person → OrgUnit/ResearchGroup | unit page, profile | |
| LEADS | Person → OrgUnit/ResearchGroup/Project | unit page | `role` qualifier ("Osztályvezető") |
| PRINCIPAL_INVESTIGATOR_OF | Person → Project | project page | |
| PARTICIPATES_IN | Person → Project | profile, project page | |
| PART_OF | OrgUnit → OrgUnit/Institution; Institution → Institution | registry, unit page | hierarchy; temporal |
| HOSTED_BY | Project/ResearchGroup → OrgUnit | project page | |
| FUNDED_BY | Project/ResearchGroup → Institution (funder) | later | |
| WORKS_ON_TOPIC | Person/Project → ResearchTopic | DERIVED | evidence: stated text + matched pattern |
| USES_METHOD | Person/Project → Method | DERIVED | |
| BROADER | Topic/Method → Topic/Method | taxonomy | |
| STUDIED_AT, SUPERVISED_BY, SUPERVISES | Person → Institution / Person | later (doktori.hu) | genealogy; never inferred silently |
| EDITOR_OF | Person → Journal | later | |
| AUTHORED, PUBLISHED_IN, CITES, COAUTHOR_WITH | | later (MTMT/OpenAlex) | `COAUTHOR_WITH` is a derived projection of `AUTHORED` |
| CO_PROJECT, COLLABORATES_WITH | Person → Person | derived projections | stored only in analysis exports |
| PART_OF_TRADITION, INTELLECTUALLY_INFLUENCED_BY | Person → Tradition / Person | later | INTERPRETIVE or HISTORICAL_LITERATURE only |
| PREDECESSOR_OF, SUCCESSOR_OF, INSTITUTIONAL_SUCCESSOR | Institution/Unit → Institution/Unit | later (Events) | institutional history |
| PARTICIPATED_IN_EVENT | any → Event | later | |

| RESOLVES_TO | PersonMention → Person | identity decision | `status` (DETERMINISTIC / MANUAL_CONFIRMED / HIGH_CONFIDENCE_AUTO), `method` (rule), `signals`, `negative_signals`, `decision_source`, `resolver_version` (ADR-0007); stored in the mention record, projected in Neo4j. Candidates of unresolved mentions are stored on the mention, never as edges |
| MENTIONED_IN | PersonMention → any | what the observing page said | `relation`, `role`; claims about unresolved mentions live only here, never as canonical relations |

Generic `CONNECTED_TO` does not exist.

## 5. Provenance model

```
SourceDocument {document_id, source_id, url, final_url, canonical_url, retrieved_at,
                http_status, content_sha256, raw_path, page_title, source_type,
                fetcher_version, synthetic}
Claim {claim_id, subject, predicate, value | object, qualifiers,
       valid_from, valid_until, temporal_basis, observed_at,
       evidence {document_id, locator, snippet},
       extraction_method, parser, parser_version,
       epistemic_status, assertion_type, derivation_method, derived_from[],
       confidence, review_status}
```

* `claim_id` is a deterministic hash of subject, predicate, value/object, qualifiers,
  document and locator: re-parsing the same snapshot yields the same ids.
* `snippet` is the exact text from the page (≤ 600 chars).
* `review_status` is `UNREVIEWED | CONFIRMED | DISPUTED | REJECTED`; decisions live in
  `review/disputed_claims.yaml`. REJECTED claims drop out of the projection but stay in
  git history.
* `synthetic: true` marks hand-reconstructed fixtures; a release containing any is
  labelled `dataset_kind: fixture` and the UI shows a banner.

## 6. Conflicts

Single-valued fields with disagreeing claims keep every value in
`entity.conflicts[field]` with its claim ids; the displayed value is the one with the
best (locator rank, number of documents, confidence, recency). Name and title variants
are treated as `alternate_names` / `alternate_titles`, not conflicts. The QA report lists
every conflict.

## 7. Versioning

* Adding a node type, edge type, enum member or optional field: minor (0.x.0).
* Renaming/removing any of those, or changing id prefixes: major.
* Every release manifest records `schema_version`, software version and parser versions.
