import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { SourceNotes } from "@/components/CoverageNote";
import EgoNetwork from "@/components/EgoNetwork";
import Facts from "@/components/Facts";
import { KindLabel } from "@/components/Glyph";
import MentionList from "@/components/MentionList";
import ProjectList from "@/components/ProjectList";
import SourceEvidence, { EvidenceList } from "@/components/SourceEvidence";
import TermChips from "@/components/TermChips";
import { graph } from "@/lib/graph";
import { buildSlice, focusSpec } from "@/lib/atlas/network";
import { personProfile } from "@/lib/atlas/profiles";
import { atlas } from "@/lib/atlas/server";
import { REL_LABEL, SOURCE_LABEL } from "@/lib/atlas/vocab";

export async function generateMetadata({ params }: { params: Promise<{ id: string }> }): Promise<Metadata> {
  const n = (await atlas()).node((await params).id);
  return { title: n?.label ?? "Kutató" };
}

export default async function PersonPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const a = await atlas();
  const p = personProfile(a, id);
  if (!p) notFound();
  const f = p.node.fields;
  const titles = (f.titles as string[] | undefined) ?? [];
  const urls = (f.profile_urls as string[] | undefined) ?? [];
  const main = p.units.find((u) => u.edge.type === "AFFILIATED_WITH")?.unit;
  const ego = buildSlice(a, focusSpec(a, id)!);
  const fieldClaims = [...new Set(Object.values(p.node.entity.provenance).flat())];
  const fieldEvidence = await graph().evidence(fieldClaims);
  const projectCount = p.led.length + p.participated.length;

  return (
    <div className="wrap page">
      <nav className="breadcrumb" aria-label="Morzsamenü">
        <Link href="/people">Kutatók</Link><span aria-hidden="true">/</span>
        {main ? <Link href={`/institution/${main.id}`}>{main.label}</Link> : <span>egység nélkül</span>}
      </nav>
      <header className="entity-head">
        <div className="eyebrow">
          <KindLabel kind="person" />
          {p.node.sources.map((s) => <span key={s} className="badge neutral">{SOURCE_LABEL[s]?.short ?? s} profil</span>)}
        </div>
        <h1>{p.node.label}{titles.length > 0 && <span className="muted" style={{ fontSize: "0.45em", fontFamily: "var(--sans)", fontWeight: 400, marginLeft: 12 }}>{titles.join(", ")}</span>}</h1>
        {p.node.entity.alternateNames.length > 0 && <div className="alt">más névalak: {p.node.entity.alternateNames.join(", ")}</div>}
        <div className="meta-line">
          {p.units.map((u) => (
            <span key={u.edge.id}>
              <Link href={`/institution/${u.unit.id}`}>{u.unit.label}</Link>
              <span className="muted"> · {REL_LABEL[u.edge.type]}</span>
            </span>
          ))}
        </div>
        {p.positions.length > 0 && <div className="meta-line"><span className="muted">Beosztás a forrás szerint:</span> {p.positions.join(" · ")}</div>}
        <div className="meta-line small muted">
          {typeof f.mtmt_id === "string" && <span>MTMT-azonosító: {f.mtmt_id}</span>}
          {typeof f.orcid === "string" && <span>ORCID: {f.orcid}</span>}
          {p.node.entity.lastVerifiedAt && <span>Forrás utoljára ellenőrizve: {p.node.entity.lastVerifiedAt.slice(0, 10)}</span>}
        </div>
        <Facts items={[
          { label: "Projekt", value: projectCount, note: p.led.length ? `ebből ${p.led.length} vezetett` : undefined },
          { label: "Szervezeti egység", value: p.units.length },
          { label: "Téma", value: p.topics.length, note: "származtatott" },
          { label: "Módszer", value: p.methods.length, note: "származtatott" },
          { label: "Említés a forrásokban", value: p.resolvedMentions.length, note: "azonosítva ide" },
        ]} />
      </header>

      <div className="split" style={{ marginTop: 32 }}>
        <div>
          <section aria-labelledby="topics">
            <h2 id="topics">Kutatási témák és módszerek</h2>
            {p.statedAreas.length > 0 ? (
              <>
                <h3 className="small muted" style={{ fontFamily: "var(--sans)", fontWeight: 500 }}>A profil szövege szerint (forrás)</h3>
                <div className="chips" style={{ marginBottom: 14 }}>
                  {p.statedAreas.map((s) => <span key={s} className="chip stated">{s}</span>)}
                </div>
              </>
            ) : (
              <p className="empty">A profil nem sorol fel kutatási területeket.</p>
            )}
            <h3 className="small muted" style={{ fontFamily: "var(--sans)", fontWeight: 500 }}>
              Atlasz-témák <span className="badge derived">származtatott</span>
            </h3>
            {p.topics.length ? <TermChips links={p.topics} showText={false} /> : (
              <p className="empty">A jelenlegi források alapján nem rendeltünk témát ehhez a kutatóhoz{p.statedAreas.length ? " (a fenti szöveg egyik kulcsszó-szabályra sem illeszkedik)" : ""}.</p>
            )}
            <h3 className="small muted" style={{ fontFamily: "var(--sans)", fontWeight: 500, marginTop: 14 }}>
              Módszerek <span className="badge derived">származtatott</span>
            </h3>
            {p.methods.length ? <TermChips links={p.methods} showText={false} /> : (
              <p className="empty">Ehhez a kutatóhoz a jelenlegi források nem tartalmaznak módszertani címkét.</p>
            )}
            {(p.topics.length > 0 || p.methods.length > 0) && <TermChips links={[...p.topics, ...p.methods]} chips={false} />}
          </section>

          <section className="section" aria-labelledby="projects">
            <header>
              <h2 id="projects">Projektek</h2>
              <span className="aside">megfigyelt vezetői és résztvevői kapcsolatok</span>
            </header>
            <SourceNotes a={a} sources={p.node.sources} />
            {projectCount === 0 && (
              <p className="empty">A jelenlegi snapshotban ehhez a kutatóhoz nem tartozik azonosított projekt.</p>
            )}
            {p.led.length > 0 && (<>
              <h3>Vezetett projektek ({p.led.length})</h3>
              <ProjectList rows={p.led} limit={8} />
            </>)}
            {p.participated.length > 0 && (<>
              <h3 style={{ marginTop: 20 }}>Résztvevőként ({p.participated.length})</h3>
              <ProjectList rows={p.participated} limit={8} />
            </>)}
            {(p.unresolvedProjects.length > 0 || p.deferredProjects.length > 0) && (
              <div style={{ marginTop: 24 }}>
                <h3>A profilon felsorolt, nem azonosított projektek ({p.unresolvedProjects.length + p.deferredProjects.length})</h3>
                <p className="muted small">
                  Ezek a címek szerepelnek a kutató saját profilján, de nincs hozzájuk projektoldal vagy elég bizonyíték az
                  azonosításhoz. Nem részei a projekthálónak, és nem számítanak bele a fenti számokba.
                </p>
                <MentionList mentions={[...p.deferredProjects, ...p.unresolvedProjects]} />
              </div>
            )}
          </section>
        </div>

        <aside>
          <section aria-labelledby="units">
            <h2 id="units">Intézményi kapcsolatok</h2>
            <ul className="rows">
              {p.units.map((u) => (
                <li key={u.edge.id}>
                  <div className="row-title"><Link href={`/institution/${u.unit.id}`}>{u.unit.label}</Link></div>
                  <div className="row-meta">
                    <span>{REL_LABEL[u.edge.type]}</span>
                    <span className="badge observed">megfigyelt</span>
                    {u.positions.length > 0 && <span>„{u.positions.join(" / ")}”</span>}
                  </div>
                  <SourceEvidence edges={[u.edge]} />
                </li>
              ))}
            </ul>
            {p.units.length === 0 && <p className="empty">Nincs megfigyelt intézményi kapcsolat.</p>}
          </section>
          {typeof f.biography_summary === "string" && (
            <section className="section" aria-labelledby="bio">
              <h2 id="bio">Bemutatkozás</h2>
              <p className="muted small">A profiloldal szövege, változtatás nélkül.</p>
              <blockquote style={{ margin: 0, fontFamily: "var(--serif)", fontSize: "1.02rem", color: "var(--ink-2)" }}>{f.biography_summary}</blockquote>
            </section>
          )}
          <section className="section" aria-labelledby="links">
            <h2 id="links">Profiloldalak</h2>
            <ul className="rows compact">
              {urls.map((u) => <li key={u}><a href={u} rel="noreferrer" style={{ overflowWrap: "anywhere" }}>{u.replace(/^https?:\/\//, "")}</a></li>)}
            </ul>
          </section>
        </aside>
      </div>

      <section className="section" aria-labelledby="network">
        <header>
          <h2 id="network">Kapcsolatháló</h2>
          <Link className="aside" href={`/network?focus=${id}`}>Megnyitás a hálózati nézetben</Link>
        </header>
        <p className="muted small" style={{ maxWidth: "75ch" }}>
          Középen a kutató, körülötte szektoronként az egységek, projektek, témák és módszerek. A közös projektek többi
          kutatója csak kérésre jelenik meg (gomb fent, vagy egy projekt kiválasztása után). A kapcsolatok száma nem rangsor.
        </p>
        <EgoNetwork slice={ego} centerId={id} secondLabel="Közös projektek kutatói" />
      </section>

      <section className="section" aria-labelledby="sources">
        <header><h2 id="sources">Források és bizonyítékok</h2></header>
        <details className="evidence">
          <summary>A profil adatai mögötti forrásállítások ({fieldEvidence.length})</summary>
          <div className="evidence-body"><EvidenceList evidence={fieldEvidence} max={6} /></div>
        </details>
        {p.resolvedMentions.length > 0 && (
          <details className="evidence">
            <summary>Ahol a források megemlítik ({p.resolvedMentions.length} említés, azonosítva ehhez a kutatóhoz)</summary>
            <div className="evidence-body">
              <ul className="rows compact">
                {p.resolvedMentions.map((m) => (
                  <li key={m.id}>
                    <Link href={`/entity/${m.id}`}>„{m.statedName}”</Link>
                    <span className="muted small"> · {m.sourceUrl.replace(/^https?:\/\//, "")} · {m.method ?? m.status}</span>
                  </li>
                ))}
              </ul>
            </div>
          </details>
        )}
      </section>
    </div>
  );
}
