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
}
