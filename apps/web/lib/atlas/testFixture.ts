// A small synthetic snapshot for unit tests. Every name here is invented test data and never
// reaches the UI: the pages render only the configured release.
import type { Edge, Entity, Mention, Snapshot } from "../graph/types.ts";

function entity(id: string, type: string, label: string, fields: Record<string, unknown> = {}, sourceRefs: string[] = []): Entity {
  return { id, type, label, alternateNames: [], fields, provenance: {}, conflicts: {}, lastVerifiedAt: null, sourceRefs };
}

let seq = 0;
function edge(type: string, source: string, target: string, status: "OBSERVED" | "DERIVED" = "OBSERVED"): Edge {
  seq += 1;
  return {
    id: `rel_${String(seq).padStart(3, "0")}`, type, source, target, status, confidence: 1,
    validFrom: null, validUntil: null, temporalBasis: "SNAPSHOT", firstObserved: null, lastObserved: null,
    qualifiers: {}, derivationMethod: status === "DERIVED" ? "keyword_rule" : null, claimIds: [`clm_${seq}`],
  };
}

function mention(id: string, kind: "person" | "project", statedName: string, status: Mention["status"], extra: Partial<Mention> = {}): Mention {
  return {
    id, kind, statedName, sourceUrl: "https://example.test/page", linkedProfileUrl: null, status,
    resolvedTo: null, observedOnProfileOf: null, activityCues: [], method: null, decisionSource: null,
    signals: [], negativeSignals: [], reason: null, blockedBy: null, candidates: [], context: [], claimIds: [],
    ...extra,
  };
}

export function fixtureSnapshot(): Snapshot {
  seq = 0;
  const entities = [
    entity("org_a", "Institution", "Teszt Intézet A", {}, ["SRC_A|https://a.test"]),
    entity("org_b", "Institution", "Teszt Intézet B", {}, ["SRC_B|https://b.test"]),
    entity("org_r", "Institution", "Csak regiszter"),
    entity("ou_a1", "OrganisationalUnit", "Osztály A1", {}, ["SRC_A|https://a.test/a1"]),
    entity("per_1", "Person", "Alfa Anna", {}, ["SRC_A|https://a.test/p1"]),
    entity("per_2", "Person", "Béta Béla", {}, ["SRC_B|https://b.test/p2"]),
    entity("per_3", "Person", "Gamma Géza", {}, ["SRC_A|https://a.test/p3"]),
    entity("prj_1", "Project", "Közös projekt", { participants: 3 }, ["SRC_A|https://a.test/prj1"]),
    entity("prj_2", "Project", "Kis projekt", {}, ["SRC_A|https://a.test/prj2"]),
    entity("top_1", "ResearchTopic", "Roma studies", { name_hu: "Romakutatás" }),
    entity("met_1", "Method", "Survey", { name_hu: "Kérdőíves felvétel" }),
  ];
  const edges = [
    edge("PART_OF", "ou_a1", "org_a"),
    edge("AFFILIATED_WITH", "per_1", "org_a"),
    edge("MEMBER_OF", "per_1", "ou_a1"),
    edge("AFFILIATED_WITH", "per_2", "org_b"),
    edge("AFFILIATED_WITH", "per_3", "org_a"),
    edge("PRINCIPAL_INVESTIGATOR_OF", "per_1", "prj_1"),
    edge("PARTICIPATES_IN", "per_1", "prj_1"), // parallel to the lead edge: merged into one drawn edge
    edge("PARTICIPATES_IN", "per_2", "prj_1"),
    edge("PARTICIPATES_IN", "per_3", "prj_1"),
    edge("PRINCIPAL_INVESTIGATOR_OF", "per_3", "prj_2"),
    edge("HOSTED_BY", "prj_1", "org_a"),
    edge("HOSTED_BY", "prj_2", "org_a"),
    edge("WORKS_ON_TOPIC", "per_1", "top_1", "DERIVED"),
    edge("USES_METHOD", "per_2", "met_1", "DERIVED"),
    edge("PARTICIPATES_IN", "per_x", "prj_1"), // dangling: per_x is no canonical entity
  ];
  const mentions = [
    mention("pmn_1", "person", "Alfa Anna", "DETERMINISTIC", { resolvedTo: "per_1" }),
    mention("pmn_2", "person", "Delta Dóra", "UNRESOLVED", { reason: "no candidate" }),
    mention("pmn_3", "person", "Delta Dóra", "UNRESOLVED", { reason: "no candidate" }),
    mention("pmn_4", "person", "Alfa A.", "REVIEW_REQUIRED", {
      candidates: [{ targetId: "per_1", match: "INITIAL", signals: [], negativeSignals: [], rejected: false }],
    }),
    mention("pjm_1", "project", "Alfa Anna saját projektje", "UNRESOLVED", { observedOnProfileOf: "per_1" }),
    mention("pjm_2", "project", "Nemzeti adatfelvétel", "UNRESOLVED", {
      observedOnProfileOf: "per_2", method: "manual:project_deferred", blockedBy: "#9",
    }),
  ];
  return {
    info: { releaseId: "test-release", kind: "fixture", generatedAt: "2026-10-01T00:00:00Z", sources: ["SRC_A", "SRC_B"] },
    entities, edges, mentions,
  };
}
