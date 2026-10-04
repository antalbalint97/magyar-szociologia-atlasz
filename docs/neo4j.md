# Neo4j model

The graph is a projection of one release (`szocatlas neo4j-load <release>`). Rebuild it
whenever you like; the release directory is the source of truth.

## Labels and keys

* Every domain node: `:Entity` + its type label (`:Person`, `:Institution`, `:OrgUnit`,
  `:ResearchGroup:OrgUnit`, `:Project`, `:Topic`, `:Method`, `:Tradition`, `:Event`,
  `:Journal`, `:Publication`). Key: `canonical_id` (unique constraint).
* `:Claim {claim_id}` -[:SUPPORTED_BY]-> `:SourceDocument {document_id}`;
  `:Claim` -[:ABOUT {field}]-> `:Entity`. Relationships carry `claim_ids`.
* `:ReleaseInfo {key:'current'}` holds the loaded manifest.

Constraints and indexes: `src/szocatlas/graph/cypher/constraints.cypher` (unique ids,
MTMT/ORCID/topic-key indexes, a fulltext index `entity_search` over `label` and an
accent-folded `search_text`).

## Properties

Node properties are the entity's scalar fields plus `search_text`, `has_conflicts`,
`provenance_json`, `conflicts_json`, `release_id`. Relationship properties: everything in
`Relation` plus flattened qualifiers (`position_title`, `role`, `stated_text`,
`matched_pattern`) and integer helpers `from_year`, `until_year`, `first_observed_year`,
`last_observed_year`, `observed` (bool).

## Idempotency

Nodes `MERGE` on `canonical_id`, relationships on `relation_id` (hash of type, source,
target), claims on `claim_id`, documents on `document_id`; all writes are `SET +=`.
Loading the same release twice yields the same graph (`test_load_is_merge_only_and_repeatable`;
`test_neo4j_double_load_is_idempotent` runs against a real server when `NEO4J_URI` is set).
`--prune` removes nodes and relationships whose `release_id` is not the loaded release.

Relationship types are interpolated into Cypher only after validation against the
`RelationType` enum; labels only from a constant map.

## Local Neo4j

```bash
docker run -d --name szocatlas-neo4j -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/change-me neo4j:5-community
export NEO4J_URI=bolt://localhost:7687 NEO4J_USER=neo4j NEO4J_PASSWORD=change-me
szocatlas neo4j-load fixture-sample --prune
```

## Example queries

All in `src/szocatlas/graph/cypher/queries.cypher`:

1. person's institutional history (explicit intervals vs observed-at, with the unit's path to its institution)
2. ego network through shared units/projects, observed edges only
3. shortest documented path between two researchers
4. Roma research × computational methods (derived edges, with the stated text as evidence)
5. members of one unit/research group with roles
6. institutional migration over time (explicit intervals only; empty until historical affiliations exist)
7. supervisor descendants (empty until doktori.hu is ingested)
8. bridge researchers between two topic communities (structural brokerage goes to the analysis layer)
9. researchers active in year X (explicit interval or observation window, labelled by basis)
10. people connecting network analysis and inequality research
11. provenance of every edge around a node (claims → source documents)

Queries 6 and 7 are included to prove the model supports them; they return nothing until
the corresponding sources are ingested, rather than returning guesses.


## Person mentions (ADR-0006)

`:PersonMention` nodes are evidence, not entities, and deliberately lack the `:Entity`
label. A mention is one person-like record observed on one page (a linked or unlinked
name on a listing, unit or project page).

* `(:PersonMention)-[:RESOLVES_TO {status, method, decision_source, signals_json}]->(:Person)`
  exists only for resolved mentions (`DETERMINISTIC`, `MANUAL_CONFIRMED`, later
  `HIGH_CONFIDENCE_AUTO`).
* `(:PersonMention)-[:MENTIONED_IN {relation, role, snippet, claim_ids}]->(target)` records
  what the page said about the person (e.g. a participant role in a project).
* Unresolved mentions have `resolution_status = 'UNRESOLVED'` and no `RESOLVES_TO`.

Structural queries match `(:Person)` and never traverse mentions. Provenance queries walk
`SourceDocument ← Claim`, `PersonMention -[:RESOLVES_TO]-> Person` (queries 11–13).
