// Turns the release's coverage report (coverage.json, ADR-0009) into display rows. Numbers
// are read, never recomputed or typed in: every figure keeps its own numerator and denominator.
import type { CoverageData } from "../graph/types.ts";
import { SOURCE_LABEL } from "./vocab.ts";

type Row = Record<string, any>;

export interface Ratio {
  n: number;
  of: number;
}

export interface SourceMetric {
  source: string;
  label: string;
  value: Ratio;
  parts?: { key: string; label: string; n: number }[];
}

export interface CoverageView {
  available: boolean;
  releaseId: string;
  generatedAt: string;
  retrieved: { from: string; until: string } | null;
  documents: { total: number; bySource: { source: string; label: string; total: number; byType: Record<string, number> }[] };
  personMentions: SourceMetric[];
  personMentionsAll: Ratio | null;
  projectMentions: SourceMetric[];
  projectMentionsAll: Ratio | null;
  unresolvedProjectReasons: { key: string; label: string; n: number }[];
  personsWithProjects: SourceMetric[];
  personsWithProjectsAll: Ratio | null;
  fieldRows: { key: string; label: string; cells: { source: string; value: Ratio | null }[] }[];
  coParticipationTies: number | null;
  sentinels: { present: string[]; missing: string[] };
  blindSpots: string[];
  sources: { source: string; label: string; long: string; baseUrl: string | null }[];
}

export const PAGE_TYPE_LABEL: Record<string, string> = {
  listing: "munkatárslista",
  profile: "kutatói profil",
  project: "projektoldal",
  project_listing: "projektlista",
  unit: "egységoldal",
};

export const MENTION_STATUS_LABEL: Record<string, string> = {
  DETERMINISTIC: "Azonosítva profil-linkkel / URL-lel",
  MANUAL_CONFIRMED: "Kézzel megerősítve",
  HIGH_CONFIDENCE_AUTO: "Dokumentált szabállyal azonosítva",
  REVIEW_REQUIRED: "Ellenőrzésre vár",
  UNRESOLVED: "Azonosítatlan",
};

export const UNRESOLVED_REASON_LABEL: Record<string, string> = {
  title_only_no_page_link: "Csak a cím szerepel, projektoldal-link nélkül",
  linked_page_external_site: "Külső honlapra mutat (nem gyűjtött)",
  linked_page_other_unit_site: "Másik TK-egység oldalára mutat (nem gyűjtött)",
  identity_review: "Azonosítás ellenőrzésre vár",
  linked_page_not_project_path: "A link nem projektoldalra mutat",
  linked_page_grant_registry: "Pályázati nyilvántartásra mutat",
  deferred_to_ontology: "Elhalasztva: a tevékenység típusa még nyitott (#9)",
};

export const FIELD_LABEL: Record<string, string> = {
  affiliation: "Intézményi tagság",
  named_unit: "Megnevezett osztály / egység",
  position: "Beosztás",
  mtmt_id: "MTMT-azonosító",
  orcid: "ORCID",
  stated_research_areas: "Saját kutatási területek (szöveg)",
  topics: "Származtatott téma",
  methods: "Származtatott módszer",
  project_edges: "Projektkapcsolat",
};

const STATUS_ORDER = ["DETERMINISTIC", "MANUAL_CONFIRMED", "HIGH_CONFIDENCE_AUTO", "REVIEW_REQUIRED", "UNRESOLVED"];

function ratio(r: Row | undefined): Ratio | null {
  return r && typeof r.n === "number" && typeof r.of === "number" ? { n: r.n, of: r.of } : null;
}

function label(source: string, labels: Row): string {
  return SOURCE_LABEL[source]?.short ?? labels[source] ?? source;
}

function mentionMetrics(bySource: Row | undefined, labels: Row): SourceMetric[] {
  if (!bySource) return [];
  return Object.entries(bySource)
    .filter(([k]) => k !== "all")
    .map(([source, v]: [string, any]) => ({
      source,
      label: label(source, labels),
      value: { n: v.resolved ?? 0, of: v.total ?? 0 },
      parts: STATUS_ORDER.filter((s) => v[s]).map((s) => ({ key: s, label: MENTION_STATUS_LABEL[s], n: v[s] })),
    }))
    .sort((x, y) => x.label.localeCompare(y.label));
}

export function coverageView(data: CoverageData): CoverageView {
  const c = data.coverage ?? {};
  const m = data.manifest ?? {};
  const labels: Row = c.labels ?? {};
  const scope: Row = c.scope?.sources ?? {};
  const bySourceDocs: Row = c.source_set?.by_source ?? {};
  const fields: Row = c.fields?.persons?.by_source ?? {};
  const fieldSources = Object.keys(fields).filter((k) => k !== "all").sort((x, y) => label(x, labels).localeCompare(label(y, labels)));
  const fieldKeys = Object.keys(FIELD_LABEL).filter((k) => fieldSources.some((s) => fields[s]?.[k]));
  const pm = c.canonicalization?.person_mentions?.by_source;
  const jm = c.canonicalization?.project_mentions?.by_source;
  const reasons: Row = c.canonicalization?.project_mentions?.unresolved_by_category?.all ?? {};
  return {
    available: Boolean(data.coverage),
    releaseId: m.release_id ?? "",
    generatedAt: m.generated_at ?? "",
    retrieved: c.source_set?.retrieved ?? null,
    documents: {
      total: c.source_set?.documents ?? m.documents ?? 0,
      bySource: Object.entries(bySourceDocs).map(([source, v]: [string, any]) => ({
        source, label: label(source, labels), total: v.documents, byType: v.by_page_type ?? {},
      })).sort((x, y) => y.total - x.total),
    },
    personMentions: mentionMetrics(pm, labels),
    personMentionsAll: pm?.all ? { n: pm.all.resolved, of: pm.all.total } : null,
    projectMentions: mentionMetrics(jm, labels),
    projectMentionsAll: jm?.all ? { n: jm.all.resolved, of: jm.all.total } : null,
    unresolvedProjectReasons: Object.entries(reasons)
      .map(([key, n]) => ({ key, label: UNRESOLVED_REASON_LABEL[key] ?? key, n: Number(n) }))
      .sort((x, y) => y.n - x.n),
    personsWithProjects: fieldSources
      .map((source) => ({ source, label: label(source, labels), value: ratio(fields[source]?.project_edges) }))
      .filter((x): x is SourceMetric => x.value !== null),
    personsWithProjectsAll: ratio(c.network_bias?.realised?.persons_with_project_edges),
    fieldRows: fieldKeys.map((key) => ({
      key, label: FIELD_LABEL[key],
      cells: fieldSources.map((source) => ({ source, value: ratio(fields[source]?.[key]) })),
    })),
    coParticipationTies: c.network_bias?.realised?.co_participation_ties ?? null,
    sentinels: { present: c.sentinels?.present ?? [], missing: c.sentinels?.missing ?? [] },
    blindSpots: c.blind_spots ?? [],
    sources: (m.sources ?? Object.keys(scope)).map((source: string) => ({
      source,
      label: label(source, labels),
      long: SOURCE_LABEL[source]?.long ?? source,
      baseUrl: scope[source]?.base_url ?? null,
    })),
  };
}

export function fieldSourceLabels(view: CoverageView): { source: string; label: string }[] {
  const first = view.fieldRows[0];
  return first ? first.cells.map((c) => ({ source: c.source, label: SOURCE_LABEL[c.source]?.short ?? c.source })) : [];
}
