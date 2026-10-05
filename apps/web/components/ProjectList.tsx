import Link from "next/link";
import type { ProjectRow } from "@/lib/atlas/profiles";
import { PROJECT_STATUS_LABEL, sourceShort } from "@/lib/atlas/vocab";
import SourceEvidence from "./SourceEvidence";

function years(r: ProjectRow) {
  if (!r.start && !r.end) return null;
  return `${r.start ?? "?"}–${r.end ?? ""}`;
}

export default function ProjectList({ rows, showRole = true, limit, evidence = true }: {
  rows: ProjectRow[]; showRole?: boolean; limit?: number; evidence?: boolean;
}) {
  const shown = limit ? rows.slice(0, limit) : rows;
  const rest = limit ? rows.slice(limit) : [];
  const item = (r: ProjectRow) => (
    <li key={r.project.id}>
      <div className="row-title">
        <Link href={`/project/${r.project.id}`}>{r.project.label}</Link>
      </div>
      <div className="row-meta">
        {showRole && r.lead && <span className="badge observed">projektvezető</span>}
        {showRole && r.roles.length > 0 && <span>szerep a forrásban: „{r.roles.join(" / ")}”</span>}
        {years(r) && <span className="num">{years(r)}</span>}
        {r.status && <span>{PROJECT_STATUS_LABEL[r.status] ?? r.status}</span>}
        {r.hosts.length > 0 && <span>{r.hosts.map((h) => h.sources.length ? sourceShort(h.sources[0]) : h.label).join(", ")}</span>}
        <span>{r.size} azonosított résztvevő</span>
      </div>
      {evidence && showRole && r.edges.length > 0 && <SourceEvidence edges={r.edges} label="Miért kapcsolódik? Forrás" />}
    </li>
  );
  return (
    <>
      <ul className="rows">{shown.map(item)}</ul>
      {rest.length > 0 && (
        <details style={{ marginTop: 8 }}>
          <summary className="small" style={{ cursor: "pointer" }}>További {rest.length} projekt</summary>
          <ul className="rows">{rest.map(item)}</ul>
        </details>
      )}
    </>
  );
}
