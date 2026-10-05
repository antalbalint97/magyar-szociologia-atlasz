// Shapes served to the UI. They mirror the canonical release (docs/data_dictionary.md)
// but only carry what the pages render.

export type EpistemicStatus = "OBSERVED" | "DERIVED" | "INFERRED" | "INTERPRETIVE";

export interface EntitySummary {
  id: string;
  type: string; // ontology entity type, e.g. "Person"
  label: string;
  alternateNames: string[];
}

export interface Entity extends EntitySummary {
  fields: Record<string, unknown>; // typed entity fields except provenance/conflicts
  provenance: Record<string, string[]>; // field -> claim ids
  conflicts: Record<string, { value: unknown; claim_ids: string[] }[]>;
  lastVerifiedAt: string | null;
  sourceRefs: string[]; // "<source_id>|<url or key>": which enabled source observed the entity
}

export interface Edge {
  id: string;
  type: string;
  source: string;
  target: string;
  status: EpistemicStatus;
  confidence: number;
  validFrom: string | null;
  validUntil: string | null;
  temporalBasis: string;
  firstObserved: string | null;
  lastObserved: string | null;
  qualifiers: Record<string, unknown[]>;
  derivationMethod: string | null;
  claimIds: string[];
}

export interface Evidence {
  claimId: string;
  predicate: string;
  snippet: string;
  confidence: number;
  status: EpistemicStatus;
  url: string;
  retrievedAt: string;
  synthetic: boolean;
}

export interface Neighbourhood {
  center: Entity;
  nodes: EntitySummary[];
  edges: Edge[];
}

// ADR-0006 / ADR-0008: a person- or project-like record observed on one page. Evidence, not an identity.
export type MentionKind = "person" | "project";
export type MentionStatus =
  | "DETERMINISTIC" | "MANUAL_CONFIRMED" | "HIGH_CONFIDENCE_AUTO" | "REVIEW_REQUIRED" | "UNRESOLVED";

// A canonical Person / Project a mention might refer to, with the evidence for and against (ADR-0007/0008).
export interface MentionCandidate {
  targetId: string;
  match: string | null; // name match (persons) or title match (projects)
  signals: string[];
  negativeSignals: string[];
  rejected: boolean;
}

export interface MentionContext {
  relation: string;
  direction: "out" | "in";
  targetId: string | null;
  targetRef: string | null;
  role: string | null;
  snippet: string;
  claimIds: string[];
}

export interface Mention {
  id: string;
  kind: MentionKind;
  statedName: string; // the name (person) or title (project) as written
  sourceUrl: string;
  linkedProfileUrl: string | null; // the profile or project URL the page linked
  status: MentionStatus;
  resolvedTo: string | null; // Person or Project id
  observedOnProfileOf: string | null; // project mentions: the Person whose own profile lists it
  activityCues: string[]; // project mentions: hints for activity classification (#9)
  method: string | null;
  decisionSource: string | null;
  signals: string[];
  negativeSignals: string[];
  reason: string | null; // why it is not resolved
  blockedBy: string | null; // a manual deferral names the issue that must decide first (e.g. "#9")
  candidates: MentionCandidate[];
  context: MentionContext[];
  claimIds: string[];
}

export interface ReleaseInfo {
  releaseId: string;
  kind: "fixture" | "snapshot";
  generatedAt: string;
  sources: string[];
}

// Everything the atlas views aggregate over: canonical entities, their relations and the
// mentions. Claims and documents are not part of it (they are fetched per relation).
// The canonical release is small (hundreds of entities), so views aggregate in memory.
export interface Snapshot {
  info: ReleaseInfo;
  entities: Entity[]; // canonical entities only (no PersonMention / ProjectMention)
  edges: Edge[];
  mentions: Mention[];
}

// The release's own coverage report (coverage.json, ADR-0009) and manifest counts, passed
// through unchanged: the UI renders these numbers, it never recomputes or restates them.
export interface CoverageData {
  coverage: Record<string, any> | null;
  manifest: Record<string, any>;
}

export interface GraphStore {
  release(): Promise<ReleaseInfo>;
  search(query: string, limit?: number): Promise<EntitySummary[]>;
  entity(id: string): Promise<Entity | null>;
  neighbourhood(id: string, depth: 1 | 2): Promise<Neighbourhood | null>;
  evidence(claimIds: string[]): Promise<Evidence[]>;
  mention(id: string): Promise<Mention | null>;
  mentionsOf(id: string): Promise<Mention[]>; // mentions resolved to this Person or Project
  statedProjectsOf(personId: string): Promise<Mention[]>; // project mentions on the person's own profile
  snapshot(): Promise<Snapshot>;
  coverage(): Promise<CoverageData>;
}
