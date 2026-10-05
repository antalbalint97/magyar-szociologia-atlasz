// "Why does this relation exist?" — the claims behind one or more relations, collapsed by
// default. Source pages, retrieval dates and snippets come from the release's claims.
import { graph, type Edge, type Evidence } from "@/lib/graph";
import { REL_LABEL, STATUS_EXPLAIN } from "@/lib/atlas/vocab";
import { StatusBadge } from "./StatusBadge";

function SourceLink({ url }: { url: string }) {
  if (!url) return <span className="muted">ismeretlen forrás</span>;
  if (url.startsWith("repo://")) return <code>{url.slice(7)}</code>;
  return <a href={url} rel="noreferrer" className="src">{url.replace(/^https?:\/\//, "")}</a>;
}

export function EvidenceList({ evidence, max = 4 }: { evidence: Evidence[]; max?: number }) {
  const bySource = new Map<string, Evidence[]>();
  for (const ev of evidence) bySource.set(ev.url, [...(bySource.get(ev.url) ?? []), ev]);
  if (!bySource.size) return <p className="empty">Ehhez a kapcsolathoz nincs betöltött forrásállítás.</p>;
  return (
    <>
      {[...bySource.entries()].map(([url, evs]) => (
        <div key={url} style={{ marginBottom: 8 }}>
          <div><SourceLink url={url} /></div>
          <div className="muted small">
            letöltve {evs[0].retrievedAt.slice(0, 10) || "?"}{evs[0].synthetic ? " · teszt-fixture" : ""}
          </div>
          {evs.slice(0, max).filter((e) => e.snippet).map((e) => (
            <blockquote key={e.claimId}>„{e.snippet}”</blockquote>
          ))}
        </div>
      ))}
    </>
  );
}

export default async function SourceEvidence({ edges, label = "Forrás" }: { edges: Edge[]; label?: string }) {
  const evidence = await graph().evidence([...new Set(edges.flatMap((e) => e.claimIds))]);
  const derived = edges.filter((e) => e.status !== "OBSERVED");
  return (
    <details className="evidence">
      <summary>{label}</summary>
      <div className="evidence-body">
        <div className="small" style={{ marginBottom: 6 }}>
          {[...new Set(edges.map((e) => e.type))].map((t) => REL_LABEL[t] ?? t).join(", ")}{" "}
          {[...new Set(edges.map((e) => e.status))].map((s) => <StatusBadge key={s} status={s} />)}
        </div>
        {derived.length > 0 && (
          <p className="small muted">
            {STATUS_EXPLAIN.DERIVED} Szabály: <code>{derived[0].derivationMethod ?? "?"}</code>
            {derived.flatMap((e) => (e.qualifiers.matched_pattern as string[]) ?? []).length > 0 && (
              <> · minta: {[...new Set(derived.flatMap((e) => (e.qualifiers.matched_pattern as string[]) ?? []))].map((p) => <code key={p} style={{ marginRight: 4 }}>{p}</code>)}</>
            )}
          </p>
        )}
        <EvidenceList evidence={evidence} />
      </div>
    </details>
  );
}
