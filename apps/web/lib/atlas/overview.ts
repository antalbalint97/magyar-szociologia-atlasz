// Release-level figures for the home and explore pages, computed from the snapshot.
import { RESOLVED_MENTION } from "../graph/mentions.ts";
import type { Atlas, Node } from "./atlas.ts";

export interface Overview {
  persons: number;
  projects: number;
  projectsWithPeople: number;
  coveredUnits: number; // units observed by an enabled source (institutes and departments)
  registryUnits: number; // units and institutions known only from the registry
  topics: number;
  methods: number;
  observedRelations: number;
  derivedRelations: number;
  personMentions: { total: number; resolved: number };
  projectMentions: { total: number; resolved: number };
  personsWithProjects: number;
}

export function overview(a: Atlas): Overview {
  const units = a.ofKind("unit");
  const pm = a.mentions.filter((m) => m.kind === "person");
  const jm = a.mentions.filter((m) => m.kind === "project");
  const persons = a.ofKind("person");
  const projects = a.ofKind("project");
  return {
    persons: persons.length,
    projects: projects.length,
    projectsWithPeople: projects.filter((p) => a.projectSize(p.id) > 0).length,
    coveredUnits: units.filter((u) => u.sources.length).length,
    registryUnits: units.filter((u) => !u.sources.length).length,
    topics: a.ofKind("topic").length,
    methods: a.ofKind("method").length,
    observedRelations: a.edges.filter((e) => e.status === "OBSERVED").length,
    derivedRelations: a.edges.filter((e) => e.status !== "OBSERVED").length,
    personMentions: { total: pm.length, resolved: pm.filter((m) => RESOLVED_MENTION.has(m.status)).length },
    projectMentions: { total: jm.length, resolved: jm.filter((m) => RESOLVED_MENTION.has(m.status)).length },
    personsWithProjects: persons.filter((p) => a.out(p.id, ["PRINCIPAL_INVESTIGATOR_OF", "PARTICIPATES_IN"]).length).length,
  };
}

export interface TermCard {
  node: Node;
  persons: number;
  projects: number;
  related: string[];
}

/** Topics/methods with their linked persons and projects; the order is not an importance ranking. */
export function termCards(a: Atlas, labels?: string[], min = 1): TermCard[] {
  const pool = a.ofKind("topic").concat(a.ofKind("method"));
  const chosen = labels
    ? labels.map((l) => pool.find((n) => n.entity.label === l)).filter((n): n is Node => Boolean(n))
    : pool;
  return chosen.map((node) => {
    const rel = node.kind === "topic" ? "WORKS_ON_TOPIC" : "USES_METHOD";
    const src = a.in(node.id, [rel]).map((e) => a.node(e.source)!);
    const co = new Map<string, number>();
    for (const s of src) for (const t of a.topicsOf(s.id)) if (t.node.id !== node.id && t.node.kind === "topic") {
      co.set(t.node.label, (co.get(t.node.label) ?? 0) + 1);
    }
    return {
      node,
      persons: new Set(src.filter((s) => s.kind === "person").map((s) => s.id)).size,
      projects: new Set(src.filter((s) => s.kind === "project").map((s) => s.id)).size,
      related: [...co.entries()].sort((x, y) => y[1] - x[1] || x[0].localeCompare(y[0], "hu")).slice(0, 3).map(([l]) => l),
    };
  }).filter((c) => c.persons + c.projects >= min);
}

export function findByLabel(a: Atlas, label: string): Node | undefined {
  return [...a.nodes.values()].find((n) => n.entity.label === label);
}
