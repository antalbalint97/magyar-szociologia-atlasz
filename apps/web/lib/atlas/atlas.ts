// In-memory index over one release snapshot. Pure (no I/O, no React) so every view
// computation is unit-testable; lib/atlas/server.ts builds it once per server process.
//
// Epistemic rules this index keeps (ADR-0006/0008): only canonical entities become nodes;
// mentions are kept apart and never turned into people or projects here.
import { RESOLVED_MENTION, isDeferred } from "../graph/mentions.ts";
import type { Edge, Entity, Mention, ReleaseInfo, Snapshot } from "../graph/types.ts";
import { KIND_OF, type Kind } from "./vocab.ts";

export interface Node {
  id: string;
  type: string;
  kind: Kind;
  label: string; // Hungarian-first display name
  altLabel: string | null; // canonical (English) label of a taxonomy term when it differs
  fields: Record<string, unknown>;
  sources: string[]; // enabled sources that observed the entity (manifest scope)
  entity: Entity;
}

function push<K, V>(m: Map<K, V[]>, k: K, v: V) {
  const list = m.get(k);
  if (list) list.push(v);
  else m.set(k, [v]);
}

const PERSON_PROJECT = new Set(["PRINCIPAL_INVESTIGATOR_OF", "PARTICIPATES_IN"]);

export class Atlas {
  readonly info: ReleaseInfo;
  readonly nodes = new Map<string, Node>();
  readonly edges: Edge[];
  readonly edgeById = new Map<string, Edge>();
  private readonly outE = new Map<string, Edge[]>();
  private readonly inE = new Map<string, Edge[]>();
  readonly mentions: Mention[];
  readonly mentionById = new Map<string, Mention>();
  private readonly mentionsByTarget = new Map<string, Mention[]>();
  private readonly mentionsByOwner = new Map<string, Mention[]>();
  private readonly mentionsByContext = new Map<string, Mention[]>();
  private readonly mentionsByCandidate = new Map<string, Mention[]>();

  constructor(snap: Snapshot) {
    this.info = snap.info;
    const enabled = new Set(snap.info.sources);
    for (const e of snap.entities) {
      const kind = KIND_OF[e.type];
      if (!kind) continue;
      const nameHu = typeof e.fields.name_hu === "string" ? e.fields.name_hu : null;
      const taxonomy = kind === "topic" || kind === "method";
      const label = taxonomy && nameHu ? nameHu : e.label;
      this.nodes.set(e.id, {
        id: e.id,
        type: e.type,
        kind,
        label,
        altLabel: taxonomy && nameHu && nameHu !== e.label ? e.label : null,
        fields: e.fields,
        sources: [...new Set(e.sourceRefs.map((r) => r.split("|")[0]))].filter((s) => enabled.has(s)).sort(),
        entity: e,
      });
    }
    // relations only between canonical nodes
    this.edges = snap.edges.filter((e) => this.nodes.has(e.source) && this.nodes.has(e.target));
    for (const e of this.edges) {
      this.edgeById.set(e.id, e);
      push(this.outE, e.source, e);
      push(this.inE, e.target, e);
    }
    this.mentions = snap.mentions;
    for (const m of snap.mentions) {
      this.mentionById.set(m.id, m);
      if (m.resolvedTo && RESOLVED_MENTION.has(m.status)) push(this.mentionsByTarget, m.resolvedTo, m);
      if (m.observedOnProfileOf) push(this.mentionsByOwner, m.observedOnProfileOf, m);
      for (const c of m.context) if (c.targetId) push(this.mentionsByContext, c.targetId, m);
      for (const c of m.candidates) push(this.mentionsByCandidate, c.targetId, m);
    }
  }

  node(id: string): Node | undefined {
    return this.nodes.get(id);
  }

  ofKind(kind: Kind): Node[] {
    return [...this.nodes.values()].filter((n) => n.kind === kind);
  }

  out(id: string, types?: string[]): Edge[] {
    const list = this.outE.get(id) ?? [];
    return types ? list.filter((e) => types.includes(e.type)) : list;
  }

  in(id: string, types?: string[]): Edge[] {
    const list = this.inE.get(id) ?? [];
    return types ? list.filter((e) => types.includes(e.type)) : list;
  }

  edgesOf(id: string): Edge[] {
    return [...this.out(id), ...this.in(id)];
  }

  /** Mentions resolved to this canonical entity (resolved statuses only). */
  resolvedMentionsOf(id: string): Mention[] {
    return this.mentionsByTarget.get(id) ?? [];
  }

  /** Project mentions on a person's own profile. */
  mentionsOnProfileOf(personId: string): Mention[] {
    return this.mentionsByOwner.get(personId) ?? [];
  }

  /** Unresolved mentions whose source context points at this entity (e.g. names on a project page). */
  unresolvedMentionsAround(id: string): Mention[] {
    return (this.mentionsByContext.get(id) ?? []).filter((m) => !RESOLVED_MENTION.has(m.status));
  }

  /** Open mentions that list this entity as a candidate only: never an identity. */
  openCandidateMentions(id: string): Mention[] {
    return (this.mentionsByCandidate.get(id) ?? []).filter((m) => !RESOLVED_MENTION.has(m.status));
  }

  deferredMentions(): Mention[] {
    return this.mentions.filter(isDeferred);
  }

  /** PART_OF chain upward, nearest first. */
  ancestors(id: string): Node[] {
    const chain: Node[] = [];
    const seen = new Set([id]);
    let cur = id;
    for (;;) {
      const up = this.out(cur, ["PART_OF"])[0];
      if (!up || seen.has(up.target)) break;
      seen.add(up.target);
      const n = this.node(up.target);
      if (!n) break;
      chain.push(n);
      cur = up.target;
    }
    return chain;
  }

  /** The unit and every unit below it (PART_OF, any depth). */
  unitTree(id: string): string[] {
    const ids = [id];
    for (let i = 0; i < ids.length; i++) {
      for (const e of this.in(ids[i], ["PART_OF"])) if (!ids.includes(e.source)) ids.push(e.source);
    }
    return ids;
  }

  /** Units a person is observed in: institutional affiliation first, then departments. */
  unitsOfPerson(id: string): { unit: Node; edge: Edge }[] {
    const order = ["AFFILIATED_WITH", "MEMBER_OF", "LEADS"];
    return this.out(id, order)
      .sort((a, b) => order.indexOf(a.type) - order.indexOf(b.type))
      .map((edge) => ({ unit: this.node(edge.target)!, edge }));
  }

  /** Distinct canonical persons with an observed lead or participation edge to the project. */
  projectPeople(projectId: string): string[] {
    return [...new Set(this.in(projectId, [...PERSON_PROJECT]).map((e) => e.source))];
  }

  projectSize(projectId: string): number {
    return this.projectPeople(projectId).length;
  }

  hostsOf(projectId: string): Node[] {
    return this.out(projectId, ["HOSTED_BY"]).map((e) => this.node(e.target)!);
  }

  topicsOf(id: string): { node: Node; edge: Edge }[] {
    return this.out(id, ["WORKS_ON_TOPIC", "USES_METHOD"]).map((edge) => ({ node: this.node(edge.target)!, edge }));
  }

  /** True when the unit is only a registry entry (no enabled source crawled it). */
  isRegistryOnly(unitId: string): boolean {
    const n = this.node(unitId);
    if (!n) return true;
    if (n.sources.length) return false;
    return this.unitTree(unitId).every((u) => !this.node(u)?.sources.length);
  }
}

export function personProjectEdges(): ReadonlySet<string> {
  return PERSON_PROJECT;
}
