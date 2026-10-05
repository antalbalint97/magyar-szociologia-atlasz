// Global search over canonical entities and, separately, open mentions. A mention hit is
// returned with `mention: true` and is always ranked after every canonical hit of the same
// query: an unresolved name is evidence that something was written, not a researcher.
import { RESOLVED_MENTION } from "../graph/mentions.ts";
import { score } from "../graph/search.ts";
import type { Atlas } from "./atlas.ts";
import { groupOf } from "./network.ts";
import { TYPE_LABEL, hrefFor } from "./vocab.ts";

export interface SearchHit {
  id: string;
  type: string;
  typeLabel: string;
  label: string;
  sub: string | null;
  context: string | null;
  href: string;
  mention: boolean;
  score: number;
}

const PRIORITY: Record<string, number> = {
  ResearchTopic: 0, Method: 0, Institution: 1, OrganisationalUnit: 1, ResearchGroup: 1, Person: 2, Project: 3,
};

export function searchAtlas(a: Atlas, query: string, limit = 20, mentionLimit = 6): SearchHit[] {
  const hits: SearchHit[] = [];
  for (const n of a.nodes.values()) {
    const names = [n.label, n.entity.label, ...n.entity.alternateNames, n.altLabel ?? ""];
    const s = score(query, names);
    if (s <= 0) continue;
    hits.push({
      id: n.id, type: n.type, typeLabel: TYPE_LABEL[n.type] ?? n.type, label: n.label, sub: n.altLabel,
      context: n.kind === "person" || n.kind === "project" ? groupOf(a, n) : null,
      href: hrefFor(n.id, n.type), mention: false, score: s,
    });
  }
  // equal scores: taxonomy terms and units before people, people before (long) project titles
  hits.sort((x, y) => y.score - x.score || PRIORITY[x.type] - PRIORITY[y.type] || x.label.length - y.label.length ||
    x.label.localeCompare(y.label, "hu"));
  const mentionHits: SearchHit[] = [];
  const seen = new Set<string>();
  for (const m of a.mentions) {
    if (RESOLVED_MENTION.has(m.status)) continue;
    const s = score(query, [m.statedName]);
    if (s <= 0) continue;
    const key = `${m.kind}:${m.statedName}`;
    if (seen.has(key)) continue;
    seen.add(key);
    const type = m.kind === "project" ? "ProjectMention" : "PersonMention";
    mentionHits.push({
      id: m.id, type, typeLabel: TYPE_LABEL[type], label: m.statedName, sub: null, context: null,
      href: hrefFor(m.id, type), mention: true, score: s,
    });
  }
  mentionHits.sort((x, y) => y.score - x.score || x.label.localeCompare(y.label, "hu"));
  return [...hits.slice(0, limit), ...mentionHits.slice(0, mentionLimit)];
}
