// Converts a PersonMention row (release file or Neo4j node) into the UI shape (ADR-0006).
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
  return {
    id: r.canonical_id,
    statedName: r.stated_name,
    sourceUrl: r.source_url,
    linkedProfileUrl: r.linked_profile_url ?? null,
    status: res.status ?? "UNRESOLVED",
    personId: res.person_id ?? null,
    method: res.method ?? null,
    decisionSource: res.decision_source ?? null,
    signals: res.signals ?? [],
    negativeSignals: res.negative_signals ?? [],
    reason: res.reason ?? null,
    candidates: cands.map((c): MentionCandidate => ({
      personId: c.person_id,
      nameMatch: c.name_match,
      signals: c.signals ?? [],
      negativeSignals: c.negative_signals ?? [],
      rejected: Boolean(c.rejected),
    })),
    context,
    claimIds: [...new Set([...Object.values(prov).flat(), ...context.flatMap((c) => c.claimIds)])],
  };
}
