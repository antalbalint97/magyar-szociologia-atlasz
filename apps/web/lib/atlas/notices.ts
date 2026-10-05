// Contextual coverage notes, computed from the release so they stay true when the data
// changes. Each returns null when its condition no longer holds.
import { RESOLVED_MENTION } from "../graph/mentions.ts";
import type { Atlas } from "./atlas.ts";

export interface CountNote {
  n: number;
  of: number;
}

function unitByLabel(a: Atlas, label: string) {
  return a.ofKind("unit").find((u) => u.entity.label === label);
}

/** Projects hosted in the SZI tree without an observed lead (#31 explains part of it). */
export function sziLeadGap(a: Atlas): CountNote | null {
  const szi = unitByLabel(a, "TK Szociológiai Intézet");
  if (!szi) return null;
  const tree = new Set(a.unitTree(szi.id));
  const projects = a.ofKind("project").filter((p) => a.hostsOf(p.id).some((h) => tree.has(h.id)));
  const n = projects.filter((p) => !a.in(p.id, ["PRINCIPAL_INVESTIGATOR_OF"]).length).length;
  return projects.length && n ? { n, of: projects.length } : null;
}

/** CSS-RECENS researchers with at least one observed project relation. */
export function recensProjectLinks(a: Atlas): CountNote | null {
  const u = unitByLabel(a, "TK Számítógépes Társadalomtudomány - CSS-RECENS");
  if (!u) return null;
  const people = [...new Set(a.in(u.id, ["AFFILIATED_WITH"]).map((e) => e.source))];
  const n = people.filter((p) => a.out(p, ["PRINCIPAL_INVESTIGATOR_OF", "PARTICIPATES_IN"]).length).length;
  return people.length ? { n, of: people.length } : null;
}

/** Person mentions that did not resolve: former staff and outside collaborators live here (#28). */
export function openPersonMentions(a: Atlas): CountNote {
  const persons = a.mentions.filter((m) => m.kind === "person");
  return { n: persons.filter((m) => !RESOLVED_MENTION.has(m.status)).length, of: persons.length };
}

export function sourceKey(a: Atlas, unitLabel: string): string | null {
  return unitByLabel(a, unitLabel)?.sources[0] ?? null;
}
