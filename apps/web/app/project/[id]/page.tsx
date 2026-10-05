import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { SourceNotes } from "@/components/CoverageNote";
import EgoNetwork from "@/components/EgoNetwork";
import Facts from "@/components/Facts";
import { KindLabel } from "@/components/Glyph";
import MentionList from "@/components/MentionList";
import SourceEvidence, { EvidenceList } from "@/components/SourceEvidence";
import TermChips from "@/components/TermChips";
import { graph } from "@/lib/graph";
import { buildSlice, focusSpec } from "@/lib/atlas/network";
import { projectProfile, type ProjectPerson } from "@/lib/atlas/profiles";
import { atlas } from "@/lib/atlas/server";
import { PROJECT_STATUS_LABEL, SOURCE_LABEL } from "@/lib/atlas/vocab";

export async function generateMetadata({ params }: { params: Promise<{ id: string }> }): Promise<Metadata> {
  const n = (await atlas()).node((await params).id);
  return { title: n?.label ?? "Projekt" };
}

function People({ people, cols }: { people: ProjectPerson[]; cols?: boolean }) {
  return (
    <ul className={`rows compact${cols ? " cols-list" : ""}`}>
      {people.map((p) => (
        <li key={p.person.id}>
          <div className="row-title"><Link href={`/person/${p.person.id}`}>{p.person.label}</Link></div>
          <div className="row-meta">
            {p.lead && <span className="badge observed">projektvezető</span>}
            {p.roles.length > 0 && <span>„{p.roles.join(" / ")}”</span>}
            {p.units.length > 0 && <span>{p.units.map((u) => u.label).join(", ")}</span>}
          </div>
          <SourceEvidence edges={p.edges} />
        </li>
      ))}
    </ul>
  );
}

export default async function ProjectPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const a = await atlas();
  const p = projectProfile(a, id);
  if (!p) notFound();
  const f = p.node.fields;
  const s = (k: string) => (typeof f[k] === "string" && f[k] ? (f[k] as string) : null);
  const period = s("start") || s("end") ? `${s("start") ?? "?"}–${s("end") ?? ""}` : null;
  const description = s("abstract") ?? s("description");
  const ego = buildSlice(a, focusSpec(a, id)!);
  const fieldEvidence = await graph().evidence([...new Set(Object.values(p.node.entity.provenance).flat())]);
  const hostSources = [...new Set(p.hosts.flatMap((h) => h.sources))];
  const big = p.size >= 10;

  return (
    <div className="wrap page">
      <nav className="breadcrumb" aria-label="Morzsamenü">
        <Link href="/projects">Projektek</Link><span aria-hidden="true">/</span>
        {p.hosts[0] ? <Link href={`/institution/${p.hosts[0].id}`}>{p.hosts[0].label}</Link> : <span>befogadó nélkül</span>}
      </nav>
      <header className="entity-head">
        <div className="eyebrow">
          <KindLabel kind="project" />
          {s("status_label") && <span className="badge neutral">{PROJECT_STATUS_LABEL[s("status_label")!] ?? s("status_label")}</span>}
          {p.node.sources.map((x) => <span key={x} className="badge neutral">{SOURCE_LABEL[x]?.short ?? x} projektoldal</span>)}
        </div>
        <h1 style={{ fontSize: "clamp(1.7rem, 1.2rem + 1.8vw, 2.6rem)", maxWidth: "30ch" }}>{p.node.label}</h1>
        {p.node.entity.alternateNames.length > 0 && <div className="alt">más címváltozat: {p.node.entity.alternateNames.slice(0, 3).join(" · ")}</div>}
        <dl className="kv" style={{ marginTop: 16, maxWidth: 820 }}>
          <dt>Időszak</dt><dd>{period ?? <span className="muted">a projektoldal nem adja meg</span>}</dd>
          <dt>Finanszírozó</dt><dd>{s("funding_body") ?? <span className="muted">a projektoldal nem adja meg</span>}</dd>
          {s("grant_id") && (<><dt>Azonosító</dt><dd>{s("grant_id")}</dd></>)}
          <dt>Befogadó egység</dt><dd>{p.hosts.length ? p.hosts.map((h, i) => <span key={h.id}>{i > 0 && ", "}<Link href={`/institution/${h.id}`}>{h.label}</Link></span>) : <span className="muted">nincs megadva</span>}</dd>
          {s("website") && (<><dt>Projektoldal</dt><dd><a href={s("website")!} rel="noreferrer">{s("website")!.replace(/^https?:\/\//, "")}</a></dd></>)}
          {Object.keys(p.node.entity.conflicts).length > 0 && (<><dt>Eltérő forrásadat</dt><dd>{Object.entries(p.node.entity.conflicts).map(([k, v]) => `${k}: ${v.map((x) => String(x.value)).join(" | ")}`).join("; ")}</dd></>)}
        </dl>
        <Facts items={[
          { label: "Projektméret", value: p.size, note: "azonosított kutató" },
          { label: "Vezető (megfigyelt)", value: p.leads.length },
          { label: "Nem azonosított név a forrásban", value: p.unresolvedNames.length },
          { label: "Téma / módszer", value: p.topics.length + p.methods.length, note: "származtatott" },
        ]} />
      </header>

      <div className="split" style={{ marginTop: 32 }}>
        <div>
          <section aria-labelledby="people">
            <h2 id="people">Résztvevők</h2>
            {big && (
              <p className="note">
                <strong>Nagy projekt:</strong> {p.size} azonosított résztvevő. Egy kutató–kutató hálóban egy ekkora projekt
                egymagában {p.size * (p.size - 1) / 2} párkapcsolatot hozna létre, ezért a naiv „együttműködési” hálókban
                túlsúlyba kerül. Az atlasz a projektet csomópontként mutatja, nem kutatópárokként.
              </p>
            )}
            <SourceNotes a={a} sources={hostSources} />
            {p.leads.length > 0 && (<><h3>Projektvezetés</h3><People people={p.leads} /></>)}
            {p.participants.length > 0 && (<><h3 style={{ marginTop: 20 }}>Résztvevők ({p.participants.length})</h3><People people={p.participants} cols={p.participants.length > 8} /></>)}
            {p.size === 0 && <p className="empty">A projektoldalból nem olvastunk ki azonosított résztvevőt.</p>}
            {p.unresolvedNames.length > 0 && (
              <div style={{ marginTop: 24 }}>
                <h3>A forrásban szereplő, nem azonosított nevek ({p.unresolvedNames.length})</h3>
                <p className="muted small">Ezek a nevek a projekttel kapcsolatban szerepelnek, de nem köthetők azonosított kutatóhoz (pl. külső partnerek, volt munkatársak). Nem kutatói adatlapok.</p>
                <MentionList mentions={p.unresolvedNames} limit={12} />
              </div>
            )}
          </section>
          {description && (
            <section className="section" aria-labelledby="desc">
              <h2 id="desc">Leírás</h2>
              <p className="muted small">A projektoldal szövege, változtatás nélkül.</p>
              <div style={{ fontFamily: "var(--serif)", fontSize: "1.05rem", color: "var(--ink-2)", maxWidth: "70ch", whiteSpace: "pre-line" }}>{description}</div>
            </section>
          )}
        </div>
        <aside>
          <section aria-labelledby="terms">
            <h2 id="terms">Témák és módszerek</h2>
            {p.topics.length + p.methods.length > 0
              ? <TermChips links={[...p.topics, ...p.methods]} />
              : <p className="empty">A projekt szövegéből egyik kulcsszó-szabály sem rendelt hozzá témát vagy módszert.</p>}
          </section>
          {p.openMentions.length > 0 && (
            <section className="section" aria-labelledby="open">
              <h2 id="open">Nyitott említések</h2>
              <p className="muted small">Más oldalak ilyen című projektet említenek, de az azonosítás nyitott vagy kézi döntéssel el van halasztva. Ezek nem résztvevők.</p>
              <MentionList mentions={p.openMentions} />
            </section>
          )}
          <section className="section" aria-labelledby="mentions">
            <h2 id="mentions">Hol említik?</h2>
            {p.resolvedMentions.length ? (
              <ul className="rows compact">
                {p.resolvedMentions.slice(0, 12).map((m) => (
                  <li key={m.id}><Link href={`/entity/${m.id}`}>{m.sourceUrl.replace(/^https?:\/\//, "")}</Link> <span className="muted small">· {m.method}</span></li>
                ))}
              </ul>
            ) : <p className="empty">Más forrásoldal nem hivatkozik erre a projektre.</p>}
          </section>
        </aside>
      </div>

      <section className="section" aria-labelledby="network">
        <header>
          <h2 id="network">Hálózati helyzet</h2>
          <Link className="aside" href={`/network?focus=${id}`}>Megnyitás a hálózati nézetben</Link>
        </header>
        <EgoNetwork slice={ego} centerId={id} secondLabel="A résztvevők egységei" />
      </section>

      <section className="section" aria-labelledby="sources">
        <header><h2 id="sources">Források és bizonyítékok</h2></header>
        <details className="evidence">
          <summary>A projekt adatai mögötti forrásállítások ({fieldEvidence.length})</summary>
          <div className="evidence-body"><EvidenceList evidence={fieldEvidence} max={6} /></div>
        </details>
      </section>
    </div>
  );
}
