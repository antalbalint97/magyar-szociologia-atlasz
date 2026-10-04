// Ontology v0.1 schema for Neo4j 5.x. Idempotent (IF NOT EXISTS).
// Every domain node carries :Entity plus its type label; canonical_id is the key.
CREATE CONSTRAINT entity_id IF NOT EXISTS FOR (n:Entity) REQUIRE n.canonical_id IS UNIQUE;
CREATE CONSTRAINT person_id IF NOT EXISTS FOR (n:Person) REQUIRE n.canonical_id IS UNIQUE;
CREATE CONSTRAINT institution_id IF NOT EXISTS FOR (n:Institution) REQUIRE n.canonical_id IS UNIQUE;
CREATE CONSTRAINT unit_id IF NOT EXISTS FOR (n:OrgUnit) REQUIRE n.canonical_id IS UNIQUE;
CREATE CONSTRAINT project_id IF NOT EXISTS FOR (n:Project) REQUIRE n.canonical_id IS UNIQUE;
CREATE CONSTRAINT topic_id IF NOT EXISTS FOR (n:Topic) REQUIRE n.canonical_id IS UNIQUE;
CREATE CONSTRAINT method_id IF NOT EXISTS FOR (n:Method) REQUIRE n.canonical_id IS UNIQUE;
CREATE CONSTRAINT tradition_id IF NOT EXISTS FOR (n:Tradition) REQUIRE n.canonical_id IS UNIQUE;
CREATE CONSTRAINT claim_id IF NOT EXISTS FOR (c:Claim) REQUIRE c.claim_id IS UNIQUE;
CREATE CONSTRAINT source_doc_id IF NOT EXISTS FOR (s:SourceDocument) REQUIRE s.document_id IS UNIQUE;
CREATE INDEX person_mtmt IF NOT EXISTS FOR (n:Person) ON (n.mtmt_id);
CREATE INDEX person_orcid IF NOT EXISTS FOR (n:Person) ON (n.orcid);
CREATE INDEX topic_key IF NOT EXISTS FOR (n:Topic) ON (n.key);
CREATE INDEX method_key IF NOT EXISTS FOR (n:Method) ON (n.key);
CREATE INDEX entity_release IF NOT EXISTS FOR (n:Entity) ON (n.release_id);
// Accent-insensitive search uses the precomputed search_text property (folded, lower-case).
CREATE FULLTEXT INDEX entity_search IF NOT EXISTS FOR (n:Entity) ON EACH [n.label, n.search_text];
