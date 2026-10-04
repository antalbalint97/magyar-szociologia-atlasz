// File backend: serves a canonical release (JSONL) directly. Used for development,
// static deployments and whenever Neo4j is not running. Server-side only.
import { readFile, readdir } from "node:fs/promises";
import path from "node:path";
import { toMention } from "./mentions.ts";
import { score } from "./search.ts";
import type {
  Edge, Entity, EntitySummary, Evidence, GraphStore, Mention, Neighbourhood, ReleaseInfo,
} from "./types.ts";

type Row = Record<string, any>;

async function jsonl(file: string): Promise<Row[]> {
  try {
    const text = await readFile(file, "utf-8");
    return text.split("\n").filter(Boolean).map((l) => JSON.parse(l));
  } catch {
    return [];
  }
}

const NON_FIELDS = new Set(["canonical_id", "label", "provenance", "conflicts", "source_refs"]);

function toEntity(type: string, r: Row): Entity {
  const fields: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(r)) if (!NON_FIELDS.has(k)) fields[k] = v;
  return {
    id: r.canonical_id,
    type,
    label: r.label,
    alternateNames: r.alternate_names ?? r.alternate_titles ?? [],
    fields,
    provenance: r.provenance ?? {},
    conflicts: r.conflicts ?? {},
    lastVerifiedAt: r.last_verified_at ?? null,
  };
}

function toEdge(r: Row): Edge {
  return {
    id: r.relation_id,
    type: r.type,
    source: r.source_id,
    target: r.target_id,
    status: r.epistemic_status,
    confidence: r.confidence,
    validFrom: r.valid_from ?? null,
    validUntil: r.valid_until ?? null,
    temporalBasis: r.temporal_basis,
    firstObserved: r.first_observed_at ?? null,
    lastObserved: r.last_observed_at ?? null,
    qualifiers: r.qualifiers ?? {},
    derivationMethod: r.derivation_method ?? null,
    claimIds: r.claim_ids ?? [],
  };
}

interface Loaded {
  info: ReleaseInfo;
  entities: Map<string, Entity>;
  edges: Edge[];
  byNode: Map<string, Edge[]>;
  claims: Map<string, Row>;
  docs: Map<string, Row>;
  mentions: Map<string, Mention>;
  mentionsByPerson: Map<string, Mention[]>;
}

export class FileStore implements GraphStore {
  private loaded: Promise<Loaded> | null = null;
  constructor(private dir: string) {}

  private load(): Promise<Loaded> {
    this.loaded ??= (async () => {
      const manifest = JSON.parse(await readFile(path.join(this.dir, "manifest.json"), "utf-8"));
      const entities = new Map<string, Entity>();
      const mentions = new Map<string, Mention>();
      const mentionsByPerson = new Map<string, Mention[]>();
      for (const f of await readdir(path.join(this.dir, "entities"))) {
        const type = f.replace(/\.jsonl$/, "");
        for (const r of await jsonl(path.join(this.dir, "entities", f))) {
          entities.set(r.canonical_id, toEntity(type, r));
          if (type !== "PersonMention") continue;
          const m = toMention(r);
          mentions.set(m.id, m);
          if (m.personId) {
            if (!mentionsByPerson.has(m.personId)) mentionsByPerson.set(m.personId, []);
            mentionsByPerson.get(m.personId)!.push(m);
          }
        }
      }
      const edges = (await jsonl(path.join(this.dir, "relations.jsonl"))).map(toEdge);
      const byNode = new Map<string, Edge[]>();
      for (const e of edges) {
        for (const n of [e.source, e.target]) {
          if (!byNode.has(n)) byNode.set(n, []);
          byNode.get(n)!.push(e);
        }
      }
      const claims = new Map((await jsonl(path.join(this.dir, "claims.jsonl"))).map((c) => [c.claim_id, c]));
      const docs = new Map((await jsonl(path.join(this.dir, "documents.jsonl"))).map((d) => [d.document_id, d]));
      return {
        info: {
          releaseId: manifest.release_id,
          kind: manifest.dataset_kind,
          generatedAt: manifest.generated_at,
          sources: manifest.sources ?? [],
        },
        entities, edges, byNode, claims, docs, mentions, mentionsByPerson,
      };
    })();
    return this.loaded;
  }

  async release() {
    return (await this.load()).info;
  }

  async search(query: string, limit = 25): Promise<EntitySummary[]> {
    const { entities, mentions } = await this.load();
    // unresolved mentions are searchable (ranked below identities); resolved ones are reached via their Person
    const pool: { e: EntitySummary; s: number }[] = [
      ...[...entities.values()].map((e) => ({
        e: { id: e.id, type: e.type, label: e.label, alternateNames: e.alternateNames },
        s: score(query, [e.label, ...e.alternateNames, String(e.fields.name_hu ?? "")]),
      })),
      ...[...mentions.values()].filter((m) => m.status === "UNRESOLVED").map((m) => ({
        e: { id: m.id, type: "PersonMention", label: m.statedName, alternateNames: [] },
        s: score(query, [m.statedName]) * 0.9,
      })),
    ];
    return pool
      .filter((x) => x.s > 0)
      .sort((a, b) => b.s - a.s || a.e.label.localeCompare(b.e.label, "hu"))
      .slice(0, limit)
      .map(({ e }) => e);
  }

  async entity(id: string) {
    return (await this.load()).entities.get(id) ?? null;
  }

  async neighbourhood(id: string, depth: 1 | 2): Promise<Neighbourhood | null> {
    const { entities, byNode } = await this.load();
    const center = entities.get(id);
    if (!center) return null;
    const seen = new Set([id]);
    const edges = new Map<string, Edge>();
    let frontier = [id];
    for (let d = 0; d < depth; d++) {
      const next: string[] = [];
      for (const n of frontier) {
        for (const e of byNode.get(n) ?? []) {
          // second hop only through organisational/project hubs, and never via taxonomy
          if (d > 0 && !["MEMBER_OF", "AFFILIATED_WITH", "LEADS", "PARTICIPATES_IN"].includes(e.type)) continue;
          edges.set(e.id, e);
          const other = e.source === n ? e.target : e.source;
          if (!seen.has(other)) {
            seen.add(other);
            next.push(other);
          }
        }
      }
      frontier = next.filter((n) => entities.get(n)?.type !== "Person" || d === 0);
    }
    const nodes = [...seen].map((n) => entities.get(n)!).filter(Boolean)
      .map((e) => ({ id: e.id, type: e.type, label: e.label, alternateNames: e.alternateNames }));
    return { center, nodes, edges: [...edges.values()] };
  }

  async mention(id: string): Promise<Mention | null> {
    return (await this.load()).mentions.get(id) ?? null;
  }

  async mentionsOf(personId: string): Promise<Mention[]> {
    return (await this.load()).mentionsByPerson.get(personId) ?? [];
  }

  async evidence(claimIds: string[]): Promise<Evidence[]> {
    const { claims, docs } = await this.load();
    return claimIds.flatMap((cid) => {
      const c = claims.get(cid);
      if (!c) return [];
      const d = docs.get(c.evidence.document_id) ?? {};
      return [{
        claimId: cid,
        predicate: c.predicate,
        snippet: c.evidence.snippet,
        confidence: c.confidence,
        status: c.epistemic_status,
        url: d.canonical_url ?? "",
        retrievedAt: d.retrieved_at ?? "",
        synthetic: Boolean(d.synthetic),
      }];
    });
  }
}
