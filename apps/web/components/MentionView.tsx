import Link from "next/link";
import type { Evidence, GraphStore, Mention } from "@/lib/graph";

// ADR-0006: a mention page shows what one source page said about a person-like name and
// the identity decision behind it. It never shows a biography or an unestablished identity.

const STATUS_HU: Record<string, string> = {
  DETERMINISTIC: "azonosítva (profil-link vagy azonosító)",
  MANUAL_CONFIRMED: "kézzel megerősítve",
  HIGH_CONFIDENCE_AUTO: "automatikusan azonosítva",
  UNRESOLVED: "azonosítatlan említés",
};

const REL_HU: Record<string, string> = {
  PARTICIPATES_IN: "résztvevő", PRINCIPAL_INVESTIGATOR_OF: "projektvezető", LEADS: "vezető",
  MEMBER_OF: "tag", AFFILIATED_WITH: "munkatárs", EDITOR_OF: "szerkesztő",
};

export function statusLabel(m: Mention) {
  return STATUS_HU[m.status] ?? m.status;
}

export default async function MentionView({ m, g }: { m: Mention; g: GraphStore }) {
  const ids = [...new Set([m.personId, ...m.candidates, ...m.context.map((c) => c.targetId)].filter(Boolean))] as string[];
  const labels = new Map((await Promise.all(ids.map((i) => g.entity(i)))).filter(Boolean).map((e) => [e!.id, e!.label]));
  const evidence: Evidence[] = await g.evidence(m.claimIds);
  const resolved = m.status !== "UNRESOLVED" && m.personId;
  return (
    <>
      <div className="type">Említés a forrásban</div>
      <h1 style={{ margin: "4px 0 2px" }}>„{m.statedName}”</h1>
      <span className={`badge ${resolved ? "OBSERVED" : "UNRESOLVED"}`}>{statusLabel(m)}</span>
      <div className="grid" style={{ marginTop: 16 }}>
        <div>
          <section className="card">
            <h2>Azonosítás</h2>
            {resolved ? (
              <div>Ugyanaz a személy: <Link href={`/entity/${m.personId}`}>{labels.get(m.personId!) ?? m.personId}</Link></div>
            ) : (
              <p className="muted">
                Ez a név egy forrásoldalon szerepel, de nincs olyan bizonyíték (saját profil, MTMT, ORCID vagy kézi
                döntés), amely egy azonosított személyhez kötné. Nem számít személynek a hálózatban.
              </p>
            )}
            {m.method && <div><span className="muted">Módszer:</span> <code>{m.method}</code></div>}
            {m.decisionSource && <div><span className="muted">Döntés forrása:</span> <code>{m.decisionSource}</code></div>}
            {m.candidates.length > 0 && (
              <div style={{ marginTop: 6 }}>
                <span className="muted">Lehetséges egyezések (nem megerősített):</span>
                <ul>{m.candidates.map((c) => <li key={c}><Link href={`/entity/${c}`}>{labels.get(c) ?? c}</Link></li>)}</ul>
              </div>
            )}
          </section>
          <section className="card">
            <h2>Mit mond a forrás</h2>
            <div><span className="muted">Oldal:</span> <a href={m.sourceUrl} rel="noreferrer">{m.sourceUrl}</a></div>
            {m.linkedProfileUrl && (
              <div><span className="muted">Hivatkozott profil:</span> <a href={m.linkedProfileUrl} rel="noreferrer">{m.linkedProfileUrl}</a></div>
            )}
            {m.context.length > 0 && (
              <ul className="edge-list">
                {m.context.map((c, i) => (
                  <li key={i}>
                    {REL_HU[c.relation] ?? c.relation}
                    {c.role && <span className="muted"> ({c.role})</span>}:{" "}
                    {c.targetId ? <Link href={`/entity/${c.targetId}`}>{labels.get(c.targetId) ?? c.targetId}</Link>
                      : <span className="muted">{c.targetRef ?? "?"}</span>}
                    {c.snippet && <div className="muted">„{c.snippet}”</div>}
                  </li>
                ))}
              </ul>
            )}
          </section>
        </div>
        <div>
          <section className="card">
            <h2>Állítások</h2>
            <ul style={{ paddingLeft: 18 }}>
              {evidence.slice(0, 20).map((ev) => (
                <li key={ev.claimId}><code>{ev.predicate}</code>: „{ev.snippet}” <span className="muted">{ev.retrievedAt.slice(0, 10)}</span></li>
              ))}
            </ul>
          </section>
        </div>
      </div>
    </>
  );
}
