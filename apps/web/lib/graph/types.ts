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

// ADR-0006: a person-like record observed on one page. Evidence, not an identity.
export type MentionStatus = "DETERMINISTIC" | "MANUAL_CONFIRMED" | "HIGH_CONFIDENCE_AUTO" | "UNRESOLVED";

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
  statedName: string;
  sourceUrl: string;
  linkedProfileUrl: string | null;
  status: MentionStatus;
  personId: string | null;
  method: string | null;
  decisionSource: string | null;
  candidates: string[];
  context: MentionContext[];
  claimIds: string[];
}

export interface ReleaseInfo {
  releaseId: string;
  kind: "fixture" | "snapshot";
  generatedAt: string;
  sources: string[];
}

export interface GraphStore {
  release(): Promise<ReleaseInfo>;
  search(query: string, limit?: number): Promise<EntitySummary[]>;
  entity(id: string): Promise<Entity | null>;
  neighbourhood(id: string, depth: 1 | 2): Promise<Neighbourhood | null>;
  evidence(claimIds: string[]): Promise<Evidence[]>;
  mention(id: string): Promise<Mention | null>;
  mentionsOf(personId: string): Promise<Mention[]>; // mentions resolved to this person
}
