// Directory filtering (people, projects). Pure: the pages pass URL parameters straight in.
import { score } from "../graph/search.ts";
import type { Atlas, Node } from "./atlas.ts";

export interface PeopleQuery {
  q?: string;
  unit?: string;
  term?: string;
}

export function filterPeople(a: Atlas, query: PeopleQuery): Node[] {
  const tree = query.unit ? new Set(a.unitTree(query.unit)) : null;
  return a.ofKind("person").filter((p) => {
    if (query.q && score(query.q, [p.label, ...p.entity.alternateNames]) <= 0) return false;
    if (tree && !a.unitsOfPerson(p.id).some((u) => tree.has(u.unit.id))) return false;
    if (query.term && !a.topicsOf(p.id).some((t) => t.node.id === query.term)) return false;
    return true;
  }).sort((x, y) => x.label.localeCompare(y.label, "hu"));
}

export interface ProjectQuery {
  q?: string;
  unit?: string;
  status?: string; // "futó" | "lezárt" | "none"
  size?: string; // minimum number of identified participants
  term?: string;
}

export function filterProjects(a: Atlas, query: ProjectQuery): Node[] {
  const tree = query.unit ? new Set(a.unitTree(query.unit)) : null;
  const min = query.size ? Number(query.size) : 0;
  return a.ofKind("project").filter((p) => {
    if (query.q && score(query.q, [p.label, ...p.entity.alternateNames]) <= 0) return false;
    if (tree && !a.hostsOf(p.id).some((h) => tree.has(h.id))) return false;
    const st = typeof p.fields.status_label === "string" ? p.fields.status_label : "none";
    if (query.status && st !== query.status) return false;
    if (min && a.projectSize(p.id) < min) return false;
    if (query.term && !a.topicsOf(p.id).some((t) => t.node.id === query.term)) return false;
    return true;
  });
}

/** Units that observed people or projects: the useful filter options. */
export function coveredUnits(a: Atlas): Node[] {
  return a.ofKind("unit").filter((u) => u.sources.length && (a.in(u.id, ["AFFILIATED_WITH", "MEMBER_OF", "HOSTED_BY"]).length > 0))
    .sort((x, y) => x.label.localeCompare(y.label, "hu"));
}
