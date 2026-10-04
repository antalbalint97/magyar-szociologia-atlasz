import Link from "next/link";
import { notFound } from "next/navigation";
import EgoGraph from "@/components/EgoGraph";
import { graph, type Edge, type EntitySummary } from "@/lib/graph";

const OUT: Record<string, string> = {
  AFFILIATED_WITH: "Affiliáció", MEMBER_OF: "Szervezeti egység", LEADS: "Vezeti",
  PRINCIPAL_INVESTIGATOR_OF: "Projektvezető", PARTICIPATES_IN: "Projektek", WORKS_ON_TOPIC: "Témák",
  USES_METHOD: "Módszerek", PART_OF: "Része", HOSTED_BY: "Befogadó egység", BROADER: "Tágabb fogalom",
  EDITOR_OF: "Szerkesztő", SUPERVISED_BY: "Témavezető", PART_OF_TRADITION: "Hagyomány (hipotézis)",
};
const IN: Record<string, string> = {
  AFFILIATED_WITH: "Munkatársak", MEMBER_OF: "Tagok", LEADS: "Vezető", PRINCIPAL_INVESTIGATOR_OF: "Projektvezető",
  PARTICIPATES_IN: "Résztvevők", WORKS_ON_TOPIC: "Kutatók", USES_METHOD: "Kutatók", PART_OF: "Alegységek",
  HOSTED_BY: "Projektek", BROADER: "Szűkebb fogalmak", SUPERVISED_BY: "Doktoranduszok",
};
const ORDER = ["AFFILIATED_WITH", "LEADS", "MEMBER_OF", "PRINCIPAL_INVESTIGATOR_OF", "PARTICIPATES_IN",
  "PART_OF", "HOSTED_BY", "WORKS_ON_TOPIC", "USES_METHOD", "BROADER"];

const FIELD_LABELS: [string, string][] = [
  ["titles", "Fokozat"], ["position_titles", "Beosztás (forrás szerint)"], ["english_name", "Angol név"],
  ["institution_type", "Típus"], ["unit_type", "Egység típusa"], ["city", "Város"], ["grant_id", "Azonosító"],
  ["funding_body", "Finanszírozó"], ["start", "Kezdet"], ["end", "Vég"], ["status_label", "Státusz"],
  ["mtmt_id", "MTMT"], ["orcid", "ORCID"], ["name_hu", "Magyar név"], ["scope_note", "Megjegyzés"],
];

function when(e: Edge) {
  if (e.validFrom || e.validUntil) return `${e.validFrom ?? "?"}–${e.validUntil ?? ""}`;
  if (e.temporalBasis === "OBSERVED_AT" && e.lastObserved) return `megfigyelve ${e.lastObserved.slice(0, 10)}`;
  return "";
}

function q(e: Edge, key: string): string | null {
  const v = e.qualifiers[key];
  return v && v.length ? v.join(" / ") : null;
}

function EdgeRow({ e, other }: { e: Edge; other?: EntitySummary }) {
  const extra = q(e, "position_title") ?? q(e, "role");
  const stated = e.status !== "OBSERVED" ? q(e, "stated_text") : null;
  return (
    <li>
      {other ? <Link href={`/entity/${other.id}`}>{other.label}</Link> : <span className="muted">?</span>}
      <span className={`badge ${e.status}`}>{e.status === "OBSERVED" ? "megfigyelt" : "származtatott"}</span>
      {extra && <div className="muted">{extra}</div>}
      {stated && <div className="muted">forrás szöveg: „{stated}” ({e.derivationMethod})</div>}
      {when(e) && <div className="muted" style={{ fontSize: 13 }}>{when(e)}</div>}
    </li>
  );
}

export default async function EntityPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const g = graph();
  const hood = await g.neighbourhood(id, 2);
  if (!hood) notFound();
  const e = hood.center;
  const nodes = new Map(hood.nodes.map((n) => [n.id, n]));
  const direct = hood.edges.filter((x) => x.source === id || x.target === id);
  const groups = new Map<string, { label: string; edges: Edge[]; out: boolean }>();
  for (const x of direct) {
    const out = x.source === id;
    const key = `${out ? "out" : "in"}:${x.type}`;
    const label = (out ? OUT : IN)[x.type] ?? x.type;
    if (!groups.has(key)) groups.set(key, { label, edges: [], out });
    groups.get(key)!.edges.push(x);
  }
  const sortedGroups = [...groups.entries()].sort(
    ([a], [b]) => ORDER.indexOf(a.split(":")[1]) - ORDER.indexOf(b.split(":")[1]));
  const claimIds = [...new Set([...Object.values(e.provenance).flat(), ...direct.flatMap((x) => x.claimIds)])];
  const evidence = await g.evidence(claimIds);
  const bySource = new Map<string, typeof evidence>();
  for (const ev of evidence) {
    if (!bySource.has(ev.url)) bySource.set(ev.url, []);
    bySource.get(ev.url)!.push(ev);
  }
  const f = e.fields;
  const urls = [...((f.profile_urls as string[]) ?? []), ...(f.website ? [f.website as string] : [])];
  const areas = (f.stated_research_areas as string[]) ?? [];

  return (
    <>
      <div className="type">{e.type}</div>
      <h1 style={{ margin: "4px 0 2px" }}>{e.label}</h1>
      {e.alternateNames.length > 0 && <div className="muted">Más alakok: {e.alternateNames.join(", ")}</div>}
      {e.lastVerifiedAt && <div className="muted" style={{ fontSize: 13 }}>Utoljára ellenőrizve: {e.lastVerifiedAt.slice(0, 10)}</div>}

      <div className="grid" style={{ marginTop: 16 }}>
        <div>
          <section className="card">
            <h2>Adatok</h2>
            {FIELD_LABELS.filter(([k]) => f[k] != null && !(Array.isArray(f[k]) && !(f[k] as unknown[]).length)).map(([k, label]) => (
              <div key={k}><span className="muted">{label}:</span> {Array.isArray(f[k]) ? (f[k] as string[]).join("; ") : String(f[k])}</div>
            ))}
            {typeof f.description === "string" && <p>{f.description}</p>}
            {typeof f.abstract === "string" && <p>{f.abstract}</p>}
            {typeof f.biography_summary === "string" && (
              <p><span className="muted">Bemutatkozás (forrásszöveg): </span>{f.biography_summary}</p>
            )}
            {urls.length > 0 && (
              <div style={{ marginTop: 6 }}>{urls.map((u) => <div key={u}><a href={u} rel="noreferrer">{u}</a></div>)}</div>
            )}
          </section>
          {areas.length > 0 && (
            <section className="card">
              <h2>Kutatási területek (a profil szövege szerint)</h2>
              {areas.map((a) => <span className="chip" key={a}>{a}</span>)}
            </section>
          )}
          {Object.keys(e.conflicts).length > 0 && (
            <section className="card" style={{ borderColor: "var(--derived)" }}>
              <h2>Eltérő források</h2>
              {Object.entries(e.conflicts).map(([k, vals]) => (
                <div key={k}><span className="muted">{k}:</span> {vals.map((v) => String(v.value)).join(" | ")}</div>
              ))}
            </section>
          )}
          {sortedGroups.map(([key, grp]) => (
            <section className="card" key={key}>
              <h2>{grp.label} <span className="muted">({grp.edges.length})</span></h2>
              <ul className="edge-list">
                {grp.edges
                  .map((x) => ({ x, other: nodes.get(grp.out ? x.target : x.source) }))
                  .sort((a, b) => (a.other?.label ?? "").localeCompare(b.other?.label ?? "", "hu"))
                  .map(({ x, other }) => <EdgeRow key={x.id} e={x} other={other} />)}
              </ul>
            </section>
          ))}
        </div>
        <div>
          <section className="card">
            <h2>Kapcsolatháló (2 lépés)</h2>
            <EgoGraph hood={hood} />
          </section>
          <section className="card">
            <h2>Források</h2>
            <table className="evidence">
              <tbody>
                {[...bySource.entries()].map(([url, evs]) => (
                  <tr key={url}>
                    <td>
                      {url.startsWith("repo://") ? <code>{url.slice(7)}</code> : <a href={url} rel="noreferrer">{url}</a>}
                      {evs[0]?.synthetic && <span className="badge DERIVED">fixture</span>}
                      <div className="muted">{evs[0]?.retrievedAt.slice(0, 10)} · {evs.length} állítás</div>
                      <ul style={{ margin: "4px 0 0", paddingLeft: 18 }}>
                        {evs.slice(0, 8).map((ev) => (
                          <li key={ev.claimId}><code>{ev.predicate}</code>: „{ev.snippet}”</li>
                        ))}
                      </ul>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
        </div>
      </div>
    </>
  );
}
