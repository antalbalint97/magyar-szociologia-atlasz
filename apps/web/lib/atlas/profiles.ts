// View models for the profile pages. Each one only regroups what the release states;
// aggregations (a unit's or a topic's profile) are labelled as such by the pages.
import { RESOLVED_MENTION, isDeferred } from "../graph/mentions.ts";
import type { Edge, Mention } from "../graph/types.ts";
import type { Atlas, Node } from "./atlas.ts";

export interface TermLink {
  node: Node;
  edges: Edge[];
  statedText: string[]; // the source text the keyword rule matched (DERIVED relations)
  patterns: string[];
  derivation: string | null;
}

export interface ProjectRow {
  project: Node;
  lead: boolean; // an observed PRINCIPAL_INVESTIGATOR_OF edge
  roles: string[]; // roles as written on the source page
  edges: Edge[];
  status: string | null; // "futó" / "lezárt" as the project page states it
  start: string | null;
  end: string | null;
  hosts: Node[];
  size: number;
}

export interface PersonProfile {
  node: Node;
  units: { unit: Node; edge: Edge; positions: string[] }[];
  positions: string[];
  statedAreas: string[];
  topics: TermLink[];
  methods: TermLink[];
  led: ProjectRow[];
  participated: ProjectRow[];
  unresolvedProjects: Mention[]; // listed on the person's own profile, no canonical Project
  deferredProjects: Mention[]; // held back by a manual decision until another issue decides
  resolvedMentions: Mention[];
  coParticipants: { person: Node; projects: Node[] }[];
}

function q(e: Edge, key: string): string[] {
  return ((e.qualifiers[key] as string[] | undefined) ?? []).map(String);
}

function uniq<T>(xs: T[]): T[] {
  return [...new Set(xs)];
}

/** Drops a stated text that is fully contained in another stated text (display only). */
export function dedupeContained(xs: string[]): string[] {
  const u = uniq(xs.map((x) => x.trim()).filter(Boolean));
  return u.filter((x) => !u.some((y) => y !== x && y.includes(x)));
}

function termLinks(a: Atlas, edges: Edge[]): TermLink[] {
  const by = new Map<string, Edge[]>();
  for (const e of edges) by.set(e.target, [...(by.get(e.target) ?? []), e]);
  return [...by.entries()]
    .map(([id, es]) => ({
      node: a.node(id)!,
      edges: es,
      statedText: uniq(es.flatMap((e) => q(e, "stated_text"))),
      patterns: uniq(es.flatMap((e) => q(e, "matched_pattern"))),
      derivation: es.find((e) => e.derivationMethod)?.derivationMethod ?? null,
    }))
    .sort((x, y) => x.node.label.localeCompare(y.node.label, "hu"));
}

function str(v: unknown): string | null {
  return typeof v === "string" && v ? v : null;
}

export function projectRow(a: Atlas, project: Node, edges: Edge[]): ProjectRow {
  return {
    project,
    lead: edges.some((e) => e.type === "PRINCIPAL_INVESTIGATOR_OF"),
    roles: uniq(edges.flatMap((e) => q(e, "role"))),
    edges,
    status: str(project.fields.status_label),
    start: str(project.fields.start),
    end: str(project.fields.end),
    hosts: a.hostsOf(project.id),
    size: a.projectSize(project.id),
  };
}

// Running projects first, then by start year (latest first), then by title.
export function byRecency(x: ProjectRow, y: ProjectRow): number {
  const run = (r: ProjectRow) => (r.status === "futó" ? 0 : 1);
  return run(x) - run(y) || (y.start ?? "").localeCompare(x.start ?? "") ||
    x.project.label.localeCompare(y.project.label, "hu");
}

export function personProfile(a: Atlas, id: string): PersonProfile | null {
  const node = a.node(id);
  if (!node || node.kind !== "person") return null;
  const units = a.unitsOfPerson(id).map(({ unit, edge }) => ({
    unit, edge, positions: dedupeContained(q(edge, "position_title")),
  }));
  const projEdges = new Map<string, Edge[]>();
  for (const e of a.out(id, ["PRINCIPAL_INVESTIGATOR_OF", "PARTICIPATES_IN"])) {
    projEdges.set(e.target, [...(projEdges.get(e.target) ?? []), e]);
  }
  const rows = [...projEdges.entries()].map(([pid, es]) => projectRow(a, a.node(pid)!, es)).sort(byRecency);
  const own = a.mentionsOnProfileOf(id);
  const co = new Map<string, Set<string>>();
  for (const pid of projEdges.keys()) {
    for (const other of a.projectPeople(pid)) {
      if (other === id) continue;
      if (!co.has(other)) co.set(other, new Set());
      co.get(other)!.add(pid);
    }
  }
  return {
    node,
    units,
    positions: dedupeContained((node.fields.position_titles as string[]) ?? []),
    statedAreas: (node.fields.stated_research_areas as string[]) ?? [],
    topics: termLinks(a, a.out(id, ["WORKS_ON_TOPIC"])),
    methods: termLinks(a, a.out(id, ["USES_METHOD"])),
    led: rows.filter((r) => r.lead),
    participated: rows.filter((r) => !r.lead),
    unresolvedProjects: own.filter((m) => !RESOLVED_MENTION.has(m.status) && !isDeferred(m)),
    deferredProjects: own.filter(isDeferred),
    resolvedMentions: a.resolvedMentionsOf(id),
    coParticipants: [...co.entries()]
      .map(([pid, ps]) => ({ person: a.node(pid)!, projects: [...ps].map((p) => a.node(p)!) }))
      .sort((x, y) => x.person.label.localeCompare(y.person.label, "hu")),
  };
}

export interface ProjectPerson {
  person: Node;
  lead: boolean;
  roles: string[];
  edges: Edge[];
  units: Node[];
}

export interface ProjectProfile {
  node: Node;
  hosts: Node[];
  people: ProjectPerson[];
  leads: ProjectPerson[];
  participants: ProjectPerson[];
  unresolvedNames: Mention[]; // names on source pages that did not resolve to a canonical Person
  topics: TermLink[];
  methods: TermLink[];
  resolvedMentions: Mention[];
  openMentions: Mention[]; // mentions that list this project as a candidate only (incl. deferred)
  size: number;
}

export function projectProfile(a: Atlas, id: string): ProjectProfile | null {
  const node = a.node(id);
  if (!node || node.kind !== "project") return null;
  const by = new Map<string, Edge[]>();
  for (const e of a.in(id, ["PRINCIPAL_INVESTIGATOR_OF", "PARTICIPATES_IN"])) {
    by.set(e.source, [...(by.get(e.source) ?? []), e]);
  }
  const people = [...by.entries()].map(([pid, es]) => ({
    person: a.node(pid)!,
    lead: es.some((e) => e.type === "PRINCIPAL_INVESTIGATOR_OF"),
    roles: uniq(es.flatMap((e) => q(e, "role"))),
    edges: es,
    units: a.unitsOfPerson(pid).filter((u) => u.edge.type === "AFFILIATED_WITH").map((u) => u.unit),
  })).sort((x, y) => x.person.label.localeCompare(y.person.label, "hu"));
  const unresolvedNames = a.unresolvedMentionsAround(id).filter((m) => m.kind === "person");
  return {
    node,
    hosts: a.hostsOf(id),
    people,
    leads: people.filter((p) => p.lead),
    participants: people.filter((p) => !p.lead),
    unresolvedNames: [...new Map(unresolvedNames.map((m) => [m.id, m])).values()]
      .sort((x, y) => x.statedName.localeCompare(y.statedName, "hu")),
    topics: termLinks(a, a.out(id, ["WORKS_ON_TOPIC"])),
    methods: termLinks(a, a.out(id, ["USES_METHOD"])),
    resolvedMentions: a.resolvedMentionsOf(id),
    openMentions: a.openCandidateMentions(id).filter((m) => m.kind === "project"),
    size: people.length,
  };
}

export interface Tally {
  node: Node;
  persons: number;
  projects: number;
}

export interface TermProfile {
  node: Node;
  persons: { person: Node; link: TermLink }[];
  projects: { row: ProjectRow; link: TermLink }[];
  related: Tally[]; // other topics on the same persons/projects (co-occurrence, not a claim)
  methods: Tally[];
  units: Tally[]; // affiliation of the persons, hosting unit of the projects
  broader: Node[];
  narrower: Node[];
}

function tallies(map: Map<string, { persons: Set<string>; projects: Set<string> }>, a: Atlas): Tally[] {
  return [...map.entries()]
    .map(([id, v]) => ({ node: a.node(id)!, persons: v.persons.size, projects: v.projects.size }))
    .sort((x, y) => y.persons + y.projects - (x.persons + x.projects) || x.node.label.localeCompare(y.node.label, "hu"));
}

function bump(map: Map<string, { persons: Set<string>; projects: Set<string> }>, key: string, who: Node) {
  if (!map.has(key)) map.set(key, { persons: new Set(), projects: new Set() });
  (who.kind === "person" ? map.get(key)!.persons : map.get(key)!.projects).add(who.id);
}

export function termProfile(a: Atlas, id: string): TermProfile | null {
  const node = a.node(id);
  if (!node || (node.kind !== "topic" && node.kind !== "method")) return null;
  const rel = node.kind === "topic" ? "WORKS_ON_TOPIC" : "USES_METHOD";
  const bySource = new Map<string, Edge[]>();
  for (const e of a.in(id, [rel])) bySource.set(e.source, [...(bySource.get(e.source) ?? []), e]);
  const persons: TermProfile["persons"] = [];
  const projects: TermProfile["projects"] = [];
  const related = new Map<string, { persons: Set<string>; projects: Set<string> }>();
  const methods = new Map<string, { persons: Set<string>; projects: Set<string> }>();
  const units = new Map<string, { persons: Set<string>; projects: Set<string> }>();
  for (const [sid, es] of bySource) {
    const who = a.node(sid)!;
    const link = termLinks(a, es)[0];
    if (who.kind === "person") persons.push({ person: who, link });
    else if (who.kind === "project") {
      projects.push({ row: projectRow(a, who, []), link });
    }
    for (const t of a.topicsOf(sid)) {
      if (t.node.id === id) continue;
      bump(t.node.kind === "topic" ? related : methods, t.node.id, who);
    }
    const homes = who.kind === "person"
      ? a.unitsOfPerson(sid).filter((u) => u.edge.type === "AFFILIATED_WITH").map((u) => u.unit)
      : a.hostsOf(sid);
    for (const u of homes) bump(units, u.id, who);
  }
  persons.sort((x, y) => x.person.label.localeCompare(y.person.label, "hu"));
  projects.sort((x, y) => byRecency(x.row, y.row));
  return {
    node,
    persons,
    projects,
    related: tallies(related, a),
    methods: tallies(methods, a),
    units: tallies(units, a),
    broader: a.out(id, ["BROADER"]).map((e) => a.node(e.target)!),
    narrower: a.in(id, ["BROADER"]).map((e) => a.node(e.source)!),
  };
}

export interface UnitProfile {
  node: Node;
  ancestors: Node[];
  children: { node: Node; members: number; projects: number; registryOnly: boolean }[];
  members: { person: Node; via: Node; edges: Edge[]; positions: string[] }[];
  projects: ProjectRow[];
  topics: Tally[]; // derived aggregation over members' and projects' derived topics
  methods: Tally[];
  registryOnly: boolean;
}

export function unitProfile(a: Atlas, id: string): UnitProfile | null {
  const node = a.node(id);
  if (!node || node.kind !== "unit") return null;
  const tree = a.unitTree(id);
  const memberEdges = new Map<string, { via: Node; edges: Edge[] }>();
  for (const uid of tree) {
    for (const e of a.in(uid, ["AFFILIATED_WITH", "MEMBER_OF", "LEADS"])) {
      const cur = memberEdges.get(e.source);
      if (cur) cur.edges.push(e);
      else memberEdges.set(e.source, { via: a.node(uid)!, edges: [e] });
    }
  }
  const projects = tree.flatMap((uid) => a.in(uid, ["HOSTED_BY"]).map((e) => a.node(e.source)!));
  const topics = new Map<string, { persons: Set<string>; projects: Set<string> }>();
  const methods = new Map<string, { persons: Set<string>; projects: Set<string> }>();
  const members = [...memberEdges.entries()].map(([pid, v]) => ({
    person: a.node(pid)!,
    via: v.via,
    edges: v.edges,
    positions: dedupeContained(v.edges.flatMap((e) => q(e, "position_title"))),
  })).sort((x, y) => x.person.label.localeCompare(y.person.label, "hu"));
  for (const who of [...members.map((m) => m.person), ...projects]) {
    for (const t of a.topicsOf(who.id)) bump(t.node.kind === "topic" ? topics : methods, t.node.id, who);
  }
  return {
    node,
    ancestors: a.ancestors(id),
    children: a.in(id, ["PART_OF"]).map((e) => {
      const sub = a.unitTree(e.source);
      return {
        node: a.node(e.source)!,
        members: new Set(sub.flatMap((u) => a.in(u, ["AFFILIATED_WITH", "MEMBER_OF", "LEADS"]).map((x) => x.source))).size,
        projects: sub.flatMap((u) => a.in(u, ["HOSTED_BY"])).length,
        registryOnly: a.isRegistryOnly(e.source),
      };
    }).sort((x, y) => Number(x.registryOnly) - Number(y.registryOnly) || x.node.label.localeCompare(y.node.label, "hu")),
    members,
    projects: [...new Map(projects.map((p) => [p.id, p])).values()].map((p) => projectRow(a, p, [])).sort(byRecency),
    topics: tallies(topics, a),
    methods: tallies(methods, a),
    registryOnly: a.isRegistryOnly(id),
  };
}
