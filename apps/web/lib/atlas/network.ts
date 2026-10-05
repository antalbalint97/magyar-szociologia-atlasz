// Graph slices for the network views. A slice is always a controlled subset of the canonical
// graph (seeds + hops, or one relation family under a filter); the full graph is never the
// default. Parallel relations between the same two nodes become one drawn edge that keeps
// every relation id, type and epistemic status.
import type { EpistemicStatus } from "../graph/types.ts";
import type { Atlas, Node } from "./atlas.ts";
import { REL_GROUP, SOURCE_LABEL, hrefFor, type Kind, type RelGroup } from "./vocab.ts";

export interface GNode {
  id: string;
  kind: Kind;
  type: string;
  label: string;
  sub: string | null;
  href: string;
  group: string | null; // institute (enabled source) the node is observed in, for clustering
  size: number | null; // projects: distinct canonical persons with a lead/participation edge
  seed: boolean;
  hop: number; // 0 = seed
  degree: number; // within the slice
  meta: { units?: string[]; terms?: string[]; status?: string | null; years?: string | null };
}

export interface GEdge {
  id: string;
  source: string;
  target: string;
  group: RelGroup;
  types: string[];
  status: EpistemicStatus; // OBSERVED if any merged relation is observed
  relationIds: string[];
}

export interface GraphSlice {
  nodes: GNode[];
  edges: GEdge[];
  seeds: string[];
}

export interface SliceSpec {
  seeds?: string[];
  steps?: RelGroup[][]; // relation groups allowed on each hop out of the seeds
  relations?: RelGroup[]; // without seeds: every edge of these groups
  unit?: string; // keep edges touching persons/projects observed in this unit (any depth)
  term?: string; // keep edges touching persons/projects linked to this topic/method
  bridge?: [string, string]; // projects with canonical participants in both unit trees
}

export const MODES: Record<string, { label: string; relations: RelGroup[] }> = {
  "person-project": { label: "Kutató ↔ Projekt", relations: ["lead", "participation"] },
  "person-unit": { label: "Kutató ↔ Intézmény", relations: ["affiliation"] },
  "person-topic": { label: "Kutató ↔ Téma / módszer", relations: ["topic", "method"] },
  "unit-project": { label: "Intézmény ↔ Projekt", relations: ["hosting"] },
};

/** The institute (enabled source) a node is observed in: affiliation for persons, host for projects. */
export function groupOf(a: Atlas, n: Node): string | null {
  let src: string | undefined;
  if (n.kind === "person") src = a.unitsOfPerson(n.id).find((u) => u.unit.sources.length)?.unit.sources[0];
  else if (n.kind === "project") src = a.hostsOf(n.id).find((u) => u.sources.length)?.sources[0];
  else if (n.kind === "unit") src = n.sources[0];
  if (!src) src = n.kind === "topic" || n.kind === "method" ? undefined : n.sources[0];
  return src ? SOURCE_LABEL[src]?.short ?? src : null;
}

function toGNode(a: Atlas, n: Node, hop: number, seed: boolean): GNode {
  return {
    id: n.id,
    kind: n.kind,
    type: n.type,
    label: n.label,
    sub: n.altLabel,
    href: hrefFor(n.id, n.type),
    group: groupOf(a, n),
    size: n.kind === "project" ? a.projectSize(n.id) : null,
    seed,
    hop,
    degree: 0,
    meta: metaOf(a, n),
  };
}

function metaOf(a: Atlas, n: Node): GNode["meta"] {
  const terms = a.topicsOf(n.id).map((t) => t.node.label).slice(0, 5);
  if (n.kind === "person") {
    return { units: a.unitsOfPerson(n.id).map((u) => u.unit.label), terms };
  }
  if (n.kind === "project") {
    const s = typeof n.fields.start === "string" ? n.fields.start : null;
    const e = typeof n.fields.end === "string" ? n.fields.end : null;
    return {
      units: a.hostsOf(n.id).map((u) => u.label),
      terms,
      status: typeof n.fields.status_label === "string" ? n.fields.status_label : null,
      years: s || e ? `${s ?? "?"}–${e ?? ""}` : null,
    };
  }
  if (n.kind === "unit") return { units: a.ancestors(n.id).slice(0, 2).map((u) => u.label) };
  return {};
}

function personProjectIdsInUnit(a: Atlas, unitId: string): Set<string> {
  const ids = new Set<string>();
  for (const u of a.unitTree(unitId)) {
    for (const e of a.in(u, ["AFFILIATED_WITH", "MEMBER_OF", "LEADS", "HOSTED_BY"])) ids.add(e.source);
  }
  return ids;
}

function idsLinkedToTerm(a: Atlas, termId: string): Set<string> {
  return new Set(a.in(termId, ["WORKS_ON_TOPIC", "USES_METHOD"]).map((e) => e.source));
}

/** Merges parallel relations and computes degrees. Exported for tests. */
export function assemble(a: Atlas, nodeHop: Map<string, number>, relIds: Iterable<string>, seeds: string[]): GraphSlice {
  const merged = new Map<string, GEdge>();
  for (const rid of relIds) {
    const e = a.edgeById.get(rid);
    if (!e || !nodeHop.has(e.source) || !nodeHop.has(e.target)) continue;
    const key = `${e.source}>${e.target}`;
    const group = REL_GROUP[e.type] ?? "structure";
    const cur = merged.get(key);
    if (!cur) {
      merged.set(key, {
        id: e.id, source: e.source, target: e.target, group, types: [e.type],
        status: e.status, relationIds: [e.id],
      });
      continue;
    }
    if (!cur.types.includes(e.type)) cur.types.push(e.type);
    cur.relationIds.push(e.id);
    if (e.status === "OBSERVED") cur.status = "OBSERVED";
    if (group === "lead") cur.group = "lead"; // a lead edge outranks a participation edge on the same pair
  }
  const seedSet = new Set(seeds);
  const nodes = new Map<string, GNode>();
  for (const [id, hop] of nodeHop) {
    const n = a.node(id);
    if (n) nodes.set(id, toGNode(a, n, hop, seedSet.has(id)));
  }
  const edges = [...merged.values()].sort((x, y) => x.id.localeCompare(y.id));
  for (const e of edges) {
    nodes.get(e.source)!.degree++;
    nodes.get(e.target)!.degree++;
  }
  return {
    nodes: [...nodes.values()].sort((x, y) => x.id.localeCompare(y.id)),
    edges,
    seeds: seeds.filter((s) => nodes.has(s)),
  };
}

export function buildSlice(a: Atlas, spec: SliceSpec): GraphSlice {
  const nodeHop = new Map<string, number>();
  const rels = new Set<string>();
  const seeds = (spec.seeds ?? []).filter((s) => a.node(s));

  if (spec.bridge) {
    const [ua, ub] = spec.bridge;
    const inA = personProjectIdsInUnit(a, ua);
    const inB = personProjectIdsInUnit(a, ub);
    for (const u of [ua, ub]) nodeHop.set(u, 0);
    for (const p of a.ofKind("project")) {
      const people = a.projectPeople(p.id);
      if (!people.some((x) => inA.has(x)) || !people.some((x) => inB.has(x))) continue;
      nodeHop.set(p.id, 1);
      for (const e of a.in(p.id, ["PRINCIPAL_INVESTIGATOR_OF", "PARTICIPATES_IN"])) {
        nodeHop.set(e.source, Math.min(nodeHop.get(e.source) ?? 2, 2));
        rels.add(e.id);
        for (const u of a.out(e.source, ["AFFILIATED_WITH", "MEMBER_OF"])) {
          const top = [u.target, ...a.ancestors(u.target).map((x) => x.id)];
          if (top.includes(ua) || top.includes(ub)) {
            if (!nodeHop.has(u.target)) nodeHop.set(u.target, 1);
            rels.add(u.id);
          }
        }
      }
    }
    for (const u of [ua, ub]) for (const sub of a.unitTree(u)) {
      if (!nodeHop.has(sub)) continue;
      for (const e of a.out(sub, ["PART_OF"])) if (nodeHop.has(e.target)) rels.add(e.id);
    }
    return assemble(a, nodeHop, rels, [ua, ub]);
  }

  if (seeds.length && spec.steps?.length) {
    for (const s of seeds) nodeHop.set(s, 0);
    let frontier = seeds;
    spec.steps.forEach((groups, i) => {
      const next: string[] = [];
      for (const id of frontier) {
        for (const e of a.edgesOf(id)) {
          if (!groups.includes(REL_GROUP[e.type] ?? "structure")) continue;
          const other = e.source === id ? e.target : e.source;
          rels.add(e.id);
          if (!nodeHop.has(other)) {
            nodeHop.set(other, i + 1);
            next.push(other);
          }
        }
      }
      frontier = next;
    });
    // relations among the reached nodes that belong to the allowed groups (plus hierarchy)
    const allowed = new Set<RelGroup>([...spec.steps.flat(), "structure"]);
    for (const id of nodeHop.keys()) {
      for (const e of a.out(id)) {
        if (nodeHop.has(e.target) && allowed.has(REL_GROUP[e.type] ?? "structure")) rels.add(e.id);
      }
    }
    return assemble(a, nodeHop, rels, seeds);
  }

  const groups = new Set(spec.relations ?? MODES["person-project"].relations);
  const core = spec.unit ? personProjectIdsInUnit(a, spec.unit) : null;
  const termCore = spec.term ? idsLinkedToTerm(a, spec.term) : null;
  for (const e of a.edges) {
    if (!groups.has(REL_GROUP[e.type] ?? "structure")) continue;
    if (core && !core.has(e.source) && !core.has(e.target)) continue;
    if (termCore && !termCore.has(e.source) && !termCore.has(e.target)) continue;
    rels.add(e.id);
    for (const n of [e.source, e.target]) {
      const isCore = (core?.has(n) ?? true) && (termCore?.has(n) ?? true);
      nodeHop.set(n, Math.min(nodeHop.get(n) ?? 9, isCore ? 0 : 1));
    }
  }
  const extraSeeds = [spec.unit, spec.term].filter((x): x is string => Boolean(x));
  return assemble(a, nodeHop, rels, extraSeeds);
}

/** The neighbourhood used when the explorer is focused on one entity. */
export function focusSpec(a: Atlas, id: string): SliceSpec | null {
  const n = a.node(id);
  if (!n) return null;
  switch (n.kind) {
    case "person":
      return { seeds: [id], steps: [["affiliation", "lead", "participation", "topic", "method"], ["lead", "participation"]] };
    case "project":
      return { seeds: [id], steps: [["lead", "participation", "hosting", "topic", "method"], ["affiliation"]] };
    case "topic":
      return { seeds: [id], steps: [["topic"], ["lead", "participation"]] };
    case "method":
      return { seeds: [id], steps: [["method"], ["lead", "participation"]] };
    case "unit":
      return { seeds: a.unitTree(id), steps: [["affiliation", "hosting"], ["lead", "participation"]] };
  }
}

export interface Preset {
  key: string;
  title: string;
  description: string;
  spec: SliceSpec;
  cluster: boolean;
}

function byLabel(a: Atlas, kind: Kind, labels: string[]): string[] {
  const want = new Set(labels);
  return a.ofKind(kind).filter((n) => want.has(n.entity.label)).map((n) => n.id);
}

// Presets only configure a slice; each is offered only when its seeds exist in the release
// and the slice is non-empty. Seeds are looked up by canonical label, never by coordinates.
export function presets(a: Atlas): Preset[] {
  const out: Preset[] = [];
  const unit = (label: string) => byLabel(a, "unit", [label])[0];
  const recens = unit("TK Számítógépes Társadalomtudomány - CSS-RECENS");
  const szi = unit("TK Szociológiai Intézet");
  const ki = unit("TK Kisebbségkutató Intézet");
  const cssTerms = [
    ...byLabel(a, "topic", ["Computational social science", "Social networks", "Digital sociology"]),
    ...byLabel(a, "method", ["Computational text analysis", "Natural language processing", "Machine learning",
      "Digital trace and behavioural data", "Network analysis", "Agent-based modelling"]),
  ];
  const add = (p: Preset) => {
    const s = buildSlice(a, p.spec);
    if (s.edges.length) out.push(p);
  };
  if (cssTerms.length || recens) {
    add({
      key: "css",
      title: "Számítógépes társadalomtudomány",
      description:
        "A CSS-RECENS kutatói, valamint a számítógépes, hálózati és digitális témákhoz/módszerekhez kulcsszó-szabállyal kapcsolt kutatók és projektek, egy lépéssel tovább a projektjeikig.",
      spec: {
        seeds: [...cssTerms, ...(recens ? [recens] : [])],
        steps: [["topic", "method", "affiliation"], ["lead", "participation"]],
      },
      cluster: true,
    });
  }
  const roma = byLabel(a, "topic", ["Roma studies"]);
  if (roma.length) {
    add({
      key: "roma",
      title: "Romakutatás",
      description:
        "A „Romakutatás” témához kulcsszó-szabállyal kapcsolt kutatók és projektek, valamint a projektek többi résztvevője és a kutatók intézményei.",
      spec: { seeds: roma, steps: [["topic"], ["lead", "participation", "affiliation"]] },
      cluster: true,
    });
  }
  if (recens) {
    add({
      key: "recens",
      title: "CSS-RECENS kapcsolatai",
      description: "A CSS-RECENS munkatársai, projektjeik, témáik és módszereik.",
      spec: { seeds: [recens], steps: [["affiliation"], ["lead", "participation", "topic", "method"]] },
      cluster: false,
    });
  }
  if (ki && szi) {
    add({
      key: "ki-szi",
      title: "Kisebbségkutató ↔ Szociológiai Intézet",
      description:
        "Azok a projektek, amelyeknek mindkét intézetből van azonosított résztvevője, a résztvevőkkel és az egységeikkel.",
      spec: { bridge: [ki, szi] },
      cluster: true,
    });
  }
  if (szi) {
    add({
      key: "szi",
      title: "TK Szociológiai Intézet",
      description: "Az intézet és osztályai, munkatársaik és projektjeik.",
      spec: { seeds: a.unitTree(szi), steps: [["affiliation"], ["lead", "participation"]] },
      cluster: false,
    });
  }
  add({
    key: "projects",
    title: "Projekthálózat",
    description:
      "Minden azonosított kutató és projekt közötti megfigyelt vezetői/résztvevői kapcsolat (kétmódusú háló). A nagy projektek sok kapcsolatot hoznak létre: a projektméret-szűrővel kiemelhetők.",
    spec: { relations: ["lead", "participation"] },
    cluster: true,
  });
  return out;
}

export interface SliceFilter {
  kinds?: Kind[];
  groups?: RelGroup[];
  statuses?: ("OBSERVED" | "DERIVED")[];
  minDegree?: number;
  maxProjectSize?: number | null;
  institutes?: string[] | null; // keep persons/projects of these institutes (others: unchanged)
}

/** Client-side filtering of an already-loaded slice. Seeds always stay; isolated nodes go. */
export function filterSlice(s: GraphSlice, f: SliceFilter): GraphSlice {
  const kinds = f.kinds ? new Set(f.kinds) : null;
  const groups = f.groups ? new Set(f.groups) : null;
  const statuses = f.statuses ? new Set<string>(f.statuses) : null;
  const inst = f.institutes ? new Set(f.institutes) : null;
  const seeds = new Set(s.seeds);
  const keepNode = (n: GNode) =>
    seeds.has(n.id) || (
      (!kinds || kinds.has(n.kind)) &&
      (f.maxProjectSize == null || n.kind !== "project" || (n.size ?? 0) <= f.maxProjectSize) &&
      (!inst || (n.kind !== "person" && n.kind !== "project") || (n.group !== null && inst.has(n.group)))
    );
  let nodes = new Map(s.nodes.filter(keepNode).map((n) => [n.id, { ...n, degree: 0 }]));
  let edges = s.edges.filter((e) =>
    nodes.has(e.source) && nodes.has(e.target) &&
    (!groups || groups.has(e.group)) &&
    (!statuses || statuses.has(e.status === "OBSERVED" ? "OBSERVED" : "DERIVED")));
  const min = Math.max(1, f.minDegree ?? 1);
  // iterate: dropping a low-degree node can lower a neighbour's degree
  for (let round = 0; round < 5; round++) {
    for (const n of nodes.values()) n.degree = 0;
    for (const e of edges) {
      nodes.get(e.source)!.degree++;
      nodes.get(e.target)!.degree++;
    }
    const drop = [...nodes.values()].filter((n) => !seeds.has(n.id) && n.degree < min).map((n) => n.id);
    if (!drop.length) break;
    for (const id of drop) nodes.delete(id);
    edges = edges.filter((e) => nodes.has(e.source) && nodes.has(e.target));
    nodes = new Map(nodes);
  }
  return { nodes: [...nodes.values()], edges, seeds: s.seeds.filter((x) => nodes.has(x)) };
}

/** Facts about a slice that the legend and the summary line show. */
export function sliceStats(s: GraphSlice) {
  const byKind: Partial<Record<Kind, number>> = {};
  for (const n of s.nodes) byKind[n.kind] = (byKind[n.kind] ?? 0) + 1;
  const observed = s.edges.filter((e) => e.status === "OBSERVED").length;
  return { nodes: s.nodes.length, edges: s.edges.length, observed, derived: s.edges.length - observed, byKind };
}

/** Keeps only the given nodes (and edges between them), recomputing degrees. */
export function restrictSlice(s: GraphSlice, keep: Set<string>): GraphSlice {
  const edges = s.edges.filter((e) => keep.has(e.source) && keep.has(e.target));
  const deg = new Map<string, number>();
  for (const e of edges) for (const n of [e.source, e.target]) deg.set(n, (deg.get(n) ?? 0) + 1);
  const nodes = s.nodes.filter((n) => keep.has(n.id) && deg.has(n.id)).map((n) => ({ ...n, degree: deg.get(n.id)! }));
  return { nodes, edges, seeds: s.seeds.filter((x) => deg.has(x)) };
}
