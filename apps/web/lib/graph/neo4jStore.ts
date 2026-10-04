// Neo4j backend. Runs only on the server (route handlers / server components);
// credentials come from env vars and are never sent to the browser.
import neo4j, { type Driver } from "neo4j-driver";
import { fold } from "./search.ts";
import type {
  Edge, Entity, EntitySummary, Evidence, GraphStore, Neighbourhood, ReleaseInfo,
} from "./types.ts";

const NON_FIELDS = new Set(["canonical_id", "label", "provenance_json", "conflicts_json", "search_text",
  "release_id", "entity_type", "has_conflicts", "source_refs"]);

function plain(v: any): any {
  if (neo4j.isInt(v)) return v.toNumber();
  if (Array.isArray(v)) return v.map(plain);
  return v;
}

function nodeToEntity(props: Record<string, any>): Entity {
  const fields: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(props)) if (!NON_FIELDS.has(k)) fields[k] = plain(v);
  return {
    id: props.canonical_id,
    type: props.entity_type,
    label: props.label,
    alternateNames: props.alternate_names ?? props.alternate_titles ?? [],
    fields,
    provenance: JSON.parse(props.provenance_json ?? "{}"),
    conflicts: JSON.parse(props.conflicts_json ?? "{}"),
    lastVerifiedAt: props.last_verified_at ?? null,
  };
}

const EDGE_SKIP = new Set(["relation_id", "epistemic_status", "confidence", "valid_from", "valid_until",
  "temporal_basis", "first_observed_at", "last_observed_at", "derivation_method", "claim_ids", "release_id",
  "observed", "from_year", "until_year", "first_observed_year", "last_observed_year", "assertion_types",
  "document_ids"]);

function relToEdge(type: string, s: string, t: string, p: Record<string, any>): Edge {
  const qualifiers: Record<string, unknown[]> = {};
  for (const [k, v] of Object.entries(p)) if (!EDGE_SKIP.has(k)) qualifiers[k] = Array.isArray(v) ? v : [v];
  return {
    id: p.relation_id, type, source: s, target: t, status: p.epistemic_status, confidence: p.confidence,
    validFrom: p.valid_from ?? null, validUntil: p.valid_until ?? null, temporalBasis: p.temporal_basis,
    firstObserved: p.first_observed_at ?? null, lastObserved: p.last_observed_at ?? null,
    qualifiers, derivationMethod: p.derivation_method ?? null, claimIds: p.claim_ids ?? [],
  };
}

export class Neo4jStore implements GraphStore {
  private driver: Driver;
  constructor() {
    this.driver = neo4j.driver(
      process.env.NEO4J_URI ?? "bolt://localhost:7687",
      neo4j.auth.basic(process.env.NEO4J_USER ?? "neo4j", process.env.NEO4J_PASSWORD ?? ""),
    );
  }

  private async q(cypher: string, params: Record<string, unknown> = {}) {
    const res = await this.driver.executeQuery(cypher, params, {
      database: process.env.NEO4J_DATABASE ?? "neo4j",
      routing: neo4j.routing.READ,
    });
    return res.records;
  }

  async release(): Promise<ReleaseInfo> {
    const [r] = await this.q("MATCH (m:ReleaseInfo {key: 'current'}) RETURN m");
    const m = r?.get("m").properties ?? {};
    return { releaseId: m.release_id ?? "?", kind: m.dataset_kind ?? "snapshot",
             generatedAt: m.generated_at ?? "", sources: m.sources ?? [] };
  }

  async search(query: string, limit = 25): Promise<EntitySummary[]> {
    const terms = fold(query).split(" ").filter(Boolean).map((t) => `${t}~ OR ${t}*`).join(" AND ");
    if (!terms) return [];
    const rows = await this.q(
      "CALL db.index.fulltext.queryNodes('entity_search', $terms) YIELD node, score " +
      "RETURN node LIMIT $limit", { terms, limit: neo4j.int(limit) });
    return rows.map((r) => {
      const p = r.get("node").properties;
      return { id: p.canonical_id, type: p.entity_type, label: p.label, alternateNames: p.alternate_names ?? [] };
    });
  }

  async entity(id: string) {
    const [r] = await this.q("MATCH (n:Entity {canonical_id: $id}) RETURN n", { id });
    return r ? nodeToEntity(r.get("n").properties) : null;
  }

  async neighbourhood(id: string, depth: 1 | 2): Promise<Neighbourhood | null> {
    const center = await this.entity(id);
    if (!center) return null;
    const hop2 = depth === 2
      ? "UNION MATCH (c:Entity {canonical_id: $id})-[:MEMBER_OF|AFFILIATED_WITH|LEADS|PARTICIPATES_IN]->(h)" +
        "<-[r:MEMBER_OF|AFFILIATED_WITH|LEADS|PARTICIPATES_IN]-(o:Person) RETURN o AS a, r, h AS b, startNode(r) = o AS fwd"
      : "";
    const rows = await this.q(
      "MATCH (c:Entity {canonical_id: $id})-[r]-(o:Entity) RETURN c AS a, r, o AS b, startNode(r) = c AS fwd " + hop2,
      { id });
    const nodes = new Map<string, EntitySummary>([[id, center]]);
    const edges = new Map<string, Edge>();
    for (const row of rows) {
      const a = row.get("a").properties, b = row.get("b").properties, r = row.get("r");
      for (const p of [a, b]) nodes.set(p.canonical_id, { id: p.canonical_id, type: p.entity_type, label: p.label, alternateNames: [] });
      const [s, t] = row.get("fwd") ? [a.canonical_id, b.canonical_id] : [b.canonical_id, a.canonical_id];
      edges.set(r.properties.relation_id, relToEdge(r.type, s, t, r.properties));
    }
    return { center, nodes: [...nodes.values()], edges: [...edges.values()] };
  }

  async evidence(claimIds: string[]): Promise<Evidence[]> {
    const rows = await this.q(
      "UNWIND $ids AS cid MATCH (c:Claim {claim_id: cid})-[:SUPPORTED_BY]->(s:SourceDocument) RETURN c, s",
      { ids: claimIds });
    return rows.map((r) => {
      const c = r.get("c").properties, s = r.get("s").properties;
      return { claimId: c.claim_id, predicate: c.predicate, snippet: c.snippet, confidence: c.confidence,
               status: c.epistemic_status, url: s.canonical_url, retrievedAt: s.retrieved_at,
               synthetic: Boolean(s.synthetic) };
    });
  }
}
