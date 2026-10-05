// Example queries for ontology v0.1 (docs/neo4j.md explains each).
// Conventions: relationship.epistemic_status is OBSERVED | DERIVED | INFERRED | INTERPRETIVE;
// from_year / until_year are integer years when a source states them, otherwise null;
// first_observed_year / last_observed_year bound when we saw the relation on a page.

// :param name => 'Koltai Júlia'

// 1. A person's institutional history (explicit intervals first, then observed-at)
MATCH (p:Person {label: $name})-[r:AFFILIATED_WITH|WORKED_AT|MEMBER_OF|LEADS]->(u)
OPTIONAL MATCH path = (u)-[:PART_OF*0..4]->(top:Institution)
RETURN type(r) AS relation, u.label AS unit, top.label AS institution,
       r.from_year AS from_year, r.until_year AS until_year,
       r.first_observed_year AS first_seen, r.last_observed_year AS last_seen,
       r.temporal_basis AS temporal_basis, r.position_title AS positions
ORDER BY coalesce(r.from_year, r.first_observed_year);

// 2. Ego network: people within two hops through shared units/projects/groups (observed only)
MATCH (p:Person {label: $name})-[r1]->(hub)<-[r2]-(other:Person)
WHERE type(r1) IN ['MEMBER_OF','AFFILIATED_WITH','PARTICIPATES_IN','LEADS']
  AND type(r2) IN ['MEMBER_OF','AFFILIATED_WITH','PARTICIPATES_IN','LEADS']
  AND r1.epistemic_status = 'OBSERVED' AND r2.epistemic_status = 'OBSERVED'
RETURN other.label AS person, collect(DISTINCT hub.label) AS via, count(DISTINCT hub) AS shared
ORDER BY shared DESC LIMIT 50;

// 3. Shortest documented path between two researchers
MATCH (a:Person {label: $a}), (b:Person {label: $b})
MATCH path = shortestPath((a)-[*..8]-(b))
WHERE all(r IN relationships(path) WHERE r.epistemic_status = 'OBSERVED')
RETURN [n IN nodes(path) | n.label] AS nodes, [r IN relationships(path) | type(r)] AS relations;

// 4. Researchers working on Roma research AND using computational methods
//    (both edges are DERIVED from stated research areas; show the evidence text)
MATCH (p:Person)-[t:WORKS_ON_TOPIC]->(:Topic {key: 'roma_studies'})
MATCH (p)-[m:USES_METHOD]->(meth:Method)
WHERE meth.key IN ['network_analysis','computational_text_analysis','nlp','machine_learning',
                   'digital_trace_data','agent_based_modelling']
RETURN p.label, collect(DISTINCT meth.label) AS methods, t.stated_text AS topic_evidence;

// 5. Members of one research group / unit (including leaders), with roles
MATCH (u:OrgUnit {label: $unit})<-[r:MEMBER_OF|LEADS|AFFILIATED_WITH]-(p:Person)
RETURN p.label AS person, collect(DISTINCT type(r)) AS relations, r.role AS role
ORDER BY person;

// 6. Institutional migration over time (needs explicit intervals; observed-only edges are excluded)
MATCH (p:Person)-[r1:WORKED_AT|AFFILIATED_WITH]->(a), (p)-[r2:WORKED_AT|AFFILIATED_WITH]->(b)
WHERE a <> b AND r1.until_year IS NOT NULL AND r2.from_year IS NOT NULL AND r1.until_year <= r2.from_year
MATCH (a)-[:PART_OF*0..4]->(ia:Institution), (b)-[:PART_OF*0..4]->(ib:Institution)
WHERE ia <> ib
RETURN ia.label AS from_institution, ib.label AS to_institution, count(DISTINCT p) AS movers
ORDER BY movers DESC;

// 7. Supervisor descendants (academic genealogy)
MATCH path = (root:Person {label: $name})<-[:SUPERVISED_BY*1..6]-(desc:Person)
RETURN desc.label AS descendant, length(path) AS generation,
       [r IN relationships(path) | r.epistemic_status] AS evidence_status
ORDER BY generation, descendant;

// 8. Bridge researchers between two topic communities
MATCH (p:Person)-[:WORKS_ON_TOPIC]->(:Topic {key: $topic_a}),
      (p)-[:WORKS_ON_TOPIC]->(:Topic {key: $topic_b})
OPTIONAL MATCH (p)-[:MEMBER_OF|AFFILIATED_WITH]->(u)
RETURN p.label AS bridge, collect(DISTINCT u.label) AS units;
// For structural brokerage (betweenness), export to the analysis layer: research/analysis.

// 9. Researchers active in year X
//    explicit interval covering X, or (for current pages) observed in year X
MATCH (p:Person)-[r:AFFILIATED_WITH|WORKED_AT|MEMBER_OF]->(u)
WHERE (r.from_year IS NOT NULL AND r.from_year <= $year AND coalesce(r.until_year, 9999) >= $year)
   OR (r.from_year IS NULL AND r.first_observed_year <= $year AND r.last_observed_year >= $year)
RETURN DISTINCT p.label AS person, r.temporal_basis AS basis
ORDER BY person;

// 10. People connecting network science and inequality research
MATCH (p:Person)-[:USES_METHOD]->(:Method {key: 'network_analysis'})
MATCH (p)-[:WORKS_ON_TOPIC]->(t:Topic)
WHERE t.key IN ['inequality','stratification','social_mobility','poverty','spatial_inequality']
RETURN p.label AS person, collect(DISTINCT t.label) AS inequality_topics;

// Provenance: every claim behind one relation
MATCH (a {label: $name})-[r]->(b)
UNWIND r.claim_ids AS cid
MATCH (c:Claim {claim_id: cid})-[:SUPPORTED_BY]->(s:SourceDocument)
RETURN type(r), b.label, c.predicate, c.snippet, c.confidence, s.url, s.retrieved_at;

// --- Person mentions (ADR-0006). Queries above match (:Person) only, so unresolved
// --- name strings never enter structural analysis.

// 11. Why does the Atlas link this person to this project? Page -> claim -> mention -> person
MATCH (p:Person {label: $name})<-[res:RESOLVES_TO]-(m:PersonMention)-[mi:MENTIONED_IN]->(t)
RETURN m.source_url AS page, m.stated_name AS stated_as, mi.relation AS relation, mi.role AS role,
       t.label AS target, res.status AS resolution, res.method AS rule, mi.claim_ids AS claims;

// 12. Unresolved mentions that carry a canonical person's name (review input for #5)
MATCH (m:PersonMention {resolution_status: 'UNRESOLVED'})
MATCH (p:Person) WHERE p.search_text CONTAINS m.search_text
RETURN m.stated_name AS name, m.source_url AS page, collect(DISTINCT p.canonical_id) AS candidates
ORDER BY name;

// 13. Raw vs canonical person counts
MATCH (m:PersonMention)
RETURN count(m) AS mentions, sum(CASE WHEN m.resolved_to IS NULL THEN 1 ELSE 0 END) AS unresolved,
       COUNT { MATCH (:Person) } AS canonical_persons;
