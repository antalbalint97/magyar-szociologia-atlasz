// Converts a PersonMention / ProjectMention row (release file or Neo4j node) into the UI shape
// (ADR-0006, ADR-0008).
import type { Mention, MentionCandidate, MentionContext, MentionStatus } from "./types.ts";

export const RESOLVED_MENTION: ReadonlySet<MentionStatus> = new Set([
  "DETERMINISTIC", "MANUAL_CONFIRMED", "HIGH_CONFIDENCE_AUTO",
]);

type Row = Record<string, any>;

export function toMention(r: Row): Mention {
  const res: Row = r.resolution ?? JSON.parse(r.resolution_json ?? "{}");
  const ctx: Row[] = r.context ?? JSON.parse(r.context_json ?? "[]");
  const cands: Row[] = r.candidates ?? JSON.parse(r.candidates_json ?? "[]");
  const prov: Record<string, string[]> = r.provenance ?? JSON.parse(r.provenance_json ?? "{}");
  const context: MentionContext[] = ctx.map((c) => ({
    relation: c.relation,
    direction: c.direction ?? "out",
    targetId: c.target_id ?? null,
    targetRef: c.target_ref ?? null,
    role: (c.qualifiers?.role ?? []).join(" / ") || null,
    snippet: c.snippet ?? "",
    claimIds: c.claim_ids ?? [],
  }));
  const project = String(r.canonical_id).startsWith("pjm_");
  return {
    id: r.canonical_id,
    kind: project ? "project" : "person",
    statedName: project ? r.stated_title : r.stated_name,
    sourceUrl: r.source_url,
    linkedProfileUrl: (project ? r.linked_url : r.linked_profile_url) ?? null,
    status: res.status ?? "UNRESOLVED",
    resolvedTo: (project ? res.project_id : res.person_id) ?? null,
    observedOnProfileOf: r.observed_on_profile_of ?? null,
    activityCues: r.activity_cues ?? [],
    method: res.method ?? null,
    decisionSource: res.decision_source ?? null,
    signals: res.signals ?? [],
    negativeSignals: res.negative_signals ?? [],
    reason: res.reason ?? null,
    candidates: cands.map((c): MentionCandidate => ({
      targetId: c.person_id ?? c.project_id,
      match: c.name_match ?? c.title_match ?? null,
      signals: c.signals ?? [],
      negativeSignals: c.negative_signals ?? [],
      rejected: Boolean(c.rejected),
    })),
    context,
    claimIds: [...new Set([...Object.values(prov).flat(), ...context.flatMap((c) => c.claimIds)])],
  };
}
