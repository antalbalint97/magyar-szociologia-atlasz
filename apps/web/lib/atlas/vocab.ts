// Public (Hungarian-first) vocabulary for the atlas views. Identifiers stay English; only
// what a reader sees is translated. Nothing here is data: counts and names come from the release.
import type { EpistemicStatus } from "../graph/types.ts";

export type Kind = "person" | "project" | "unit" | "topic" | "method";

export const KIND_OF: Record<string, Kind> = {
  Person: "person",
  Project: "project",
  Institution: "unit",
  OrganisationalUnit: "unit",
  ResearchGroup: "unit",
  ResearchTopic: "topic",
  Method: "method",
};

export const KIND_LABEL: Record<Kind, string> = {
  person: "Kutató",
  project: "Projekt",
  unit: "Intézmény",
  topic: "Kutatási téma",
  method: "Módszer",
};

export const KIND_PLURAL: Record<Kind, string> = {
  person: "Kutatók",
  project: "Projektek",
  unit: "Intézmények",
  topic: "Témák",
  method: "Módszerek",
};

export const TYPE_LABEL: Record<string, string> = {
  Person: "Kutató",
  Project: "Projekt",
  Institution: "Intézmény",
  OrganisationalUnit: "Szervezeti egység",
  ResearchGroup: "Kutatócsoport",
  ResearchTopic: "Kutatási téma",
  Method: "Módszer",
  PersonMention: "Azonosítatlan említés",
  ProjectMention: "Azonosítatlan projektemlítés",
};

export const UNIT_TYPE_LABEL: Record<string, string> = {
  institute: "Kutatóintézet",
  research_department: "Kutatási osztály",
  research_centre: "Kutatóközpont",
  department: "Egyetemi tanszék",
  laboratory: "Nemzeti laboratórium",
  programme: "Program",
  infrastructure: "Kutatási infrastruktúra",
  research_group: "Kutatócsoport",
  university: "Egyetem",
  faculty: "Egyetemi kar",
  academy: "Akadémia",
  association: "Szakmai egyesület",
  research_institute: "Kutatóintézet",
  independent_organisation: "Független kutatóintézet",
};

const ROUTE: Record<Kind, string> = {
  person: "/person/",
  project: "/project/",
  unit: "/institution/",
  topic: "/topic/",
  method: "/method/",
};

export function hrefFor(id: string, type: string): string {
  if (type === "PersonMention" || type === "ProjectMention") return `/entity/${id}`;
  const kind = KIND_OF[type];
  return kind ? ROUTE[kind] + id : `/entity/${id}`;
}

// Relation groups drive graph styling and filters; the relation type stays visible in the UI.
export type RelGroup = "affiliation" | "lead" | "participation" | "hosting" | "topic" | "method" | "structure";

export const REL_GROUP: Record<string, RelGroup> = {
  AFFILIATED_WITH: "affiliation",
  MEMBER_OF: "affiliation",
  LEADS: "affiliation",
  PRINCIPAL_INVESTIGATOR_OF: "lead",
  PARTICIPATES_IN: "participation",
  HOSTED_BY: "hosting",
  WORKS_ON_TOPIC: "topic",
  USES_METHOD: "method",
  PART_OF: "structure",
  BROADER: "structure",
};

export const REL_GROUP_LABEL: Record<RelGroup, string> = {
  affiliation: "Intézményi tagság",
  lead: "Projektvezetés",
  participation: "Projektrészvétel",
  hosting: "Befogadó egység",
  topic: "Téma",
  method: "Módszer",
  structure: "Szervezeti hierarchia",
};

export const REL_LABEL: Record<string, string> = {
  AFFILIATED_WITH: "Intézményi munkatárs",
  MEMBER_OF: "Osztály tagja",
  LEADS: "Egységet vezet",
  PRINCIPAL_INVESTIGATOR_OF: "Projektvezető",
  PARTICIPATES_IN: "Projektrésztvevő",
  HOSTED_BY: "Befogadó egység",
  WORKS_ON_TOPIC: "Téma",
  USES_METHOD: "Módszer",
  PART_OF: "Része",
  BROADER: "Tágabb fogalom",
};

export const STATUS_LABEL: Record<EpistemicStatus, string> = {
  OBSERVED: "Megfigyelt kapcsolat",
  DERIVED: "Származtatott kapcsolat",
  INFERRED: "Következtetett kapcsolat",
  INTERPRETIVE: "Értelmező kapcsolat",
};

export const STATUS_SHORT: Record<EpistemicStatus, string> = {
  OBSERVED: "megfigyelt",
  DERIVED: "származtatott",
  INFERRED: "következtetett",
  INTERPRETIVE: "értelmező",
};

export const STATUS_EXPLAIN: Record<EpistemicStatus, string> = {
  OBSERVED: "A forrásoldal kifejezetten kimondja (pl. munkatárs, projektvezető, résztvevő).",
  DERIVED:
    "Nem a forrás mondja ki: a profil vagy projekt szövegéből kulcsszó-szabály rendelte hozzá. A szabály és az eredeti szöveg látható.",
  INFERRED: "Következtetés, nem közvetlen forrásállítás.",
  INTERPRETIVE: "Értelmező állítás, nem közvetlen forrásállítás.",
};

// Enabled TK sources of the current pilot. Labels only; scope itself comes from the manifest.
export const SOURCE_LABEL: Record<string, { short: string; long: string }> = {
  tk_szociologia: { short: "SZI", long: "TK Szociológiai Intézet" },
  tk_recens: { short: "CSS-RECENS", long: "TK Számítógépes Társadalomtudomány (CSS-RECENS)" },
  tk_kisebbsegkutato: { short: "KI", long: "TK Kisebbségkutató Intézet" },
  tk_politikatudomany: { short: "PTI", long: "TK Politikatudományi Intézet" },
};

export function sourceShort(id: string, fallback?: Record<string, string>): string {
  return SOURCE_LABEL[id]?.short ?? fallback?.[id] ?? id;
}

export const PROJECT_STATUS_LABEL: Record<string, string> = {
  futó: "Futó",
  lezárt: "Lezárt",
};

export function hu(n: number): string {
  return n.toLocaleString("hu-HU");
}

// Percent from the counts (half up), always shown with its denominator by the caller.
export function percent(n: number, of: number): string {
  if (!of) return "–";
  return `${Math.floor((n * 100) / of + 0.5)}%`;
}
