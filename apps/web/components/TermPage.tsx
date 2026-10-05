import Link from "next/link";
import { notFound } from "next/navigation";
import EgoNetwork from "@/components/EgoNetwork";
import Facts from "@/components/Facts";
import { KindLabel } from "@/components/Glyph";
import ProjectList from "@/components/ProjectList";
import TallyList from "@/components/TallyList";
import { buildSlice, focusSpec } from "@/lib/atlas/network";
import { termProfile } from "@/lib/atlas/profiles";
import { atlas } from "@/lib/atlas/server";
import { STATUS_EXPLAIN } from "@/lib/atlas/vocab";

export default async function TermPage({ id, kind }: { id: string; kind: "topic" | "method" }) {
  const a = await atlas();
  const t = termProfile(a, id);
  if (!t || t.node.kind !== kind) notFound();
  const scope = t.node.fields.scope_note;
  const ego = buildSlice(a, focusSpec(a, id)!);
  const noun = kind === "topic" ? "témához" : "módszerhez";
  return (
    <div className="wrap page">
      <nav className="breadcrumb" aria-label="Morzsamenü"><Link href="/topics">Témák és módszerek</Link></nav>
      <header className="entity-head">
        <div className="eyebrow"><KindLabel kind={kind} /><span className="badge derived">kulcsszó-szabállyal hozzárendelt</span></div>
        <h1>{t.node.label}</h1>
        {t.node.altLabel && <div className="alt">{t.node.altLabel}</div>}
        {typeof scope === "string" && (
          <details className="evidence"><summary>Taxonómiai megjegyzés (a taxonómia eredeti, angol szövege)</summary>
            <div className="evidence-body" lang="en">{scope}</div></details>
        )}
        {(t.broader.length > 0 || t.narrower.length > 0) && (
          <div className="meta-line">
            {t.broader.map((b) => <span key={b.id}>Tágabb: <Link href={`/method/${b.id}`}>{b.label}</Link></span>)}
            {t.narrower.map((b) => <span key={b.id}>Szűkebb: <Link href={`/method/${b.id}`}>{b.label}</Link></span>)}
          </div>
        )}
        <Facts items={[
          { label: "Kapcsolt kutató", value: t.persons.length },
          { label: "Kapcsolt projekt", value: t.projects.length },
          { label: "Intézmény", value: t.units.length, note: "ahol megjelenik" },
        ]} />
        <p className="note" style={{ maxWidth: "80ch", marginTop: 20 }}>
          <strong>Hogyan olvasd:</strong> a jelenlegi snapshotban ehhez a {noun} kapcsolt kutatók és projektek láthatók.
          {" "}{STATUS_EXPLAIN.DERIVED} A lista a TK négy forrására korlátozódik, ezért nem a terület teljes köre, és a
          számok nem fontosságot mérnek.
        </p>
      </header>

      <div className="split" style={{ marginTop: 32 }}>
        <div>
          <section aria-labelledby="people">
            <h2 id="people">Kutatók ({t.persons.length})</h2>
            {t.persons.length ? (
              <ul className="rows">
                {t.persons.map(({ person, link }) => (
                  <li key={person.id}>
                    <div className="row-title"><Link href={`/person/${person.id}`}>{person.label}</Link></div>
                    <div className="row-meta">
                      <span>a profil szövege: „{link.statedText.join("; ")}”</span>
                      <span className="badge derived">származtatott</span>
                    </div>
                  </li>
                ))}
              </ul>
            ) : <p className="empty">A jelenlegi snapshotban egyetlen kutatói profil szövege sem illeszkedik erre a {noun}.</p>}
          </section>
          <section className="section" aria-labelledby="projects">
            <h2 id="projects">Projektek ({t.projects.length})</h2>
            {t.projects.length ? <ProjectList rows={t.projects.map((p) => p.row)} showRole={false} limit={10} evidence={false} />
              : <p className="empty">Egyik projekt leírása sem illeszkedik erre a {noun}.</p>}
          </section>
        </div>
        <aside>
          <section aria-labelledby="units">
            <h2 id="units">Intézmények</h2>
            <p className="muted small">A kapcsolt kutatók intézményi tagsága és a projektek befogadó egysége alapján (aggregálás).</p>
            <TallyList items={t.units} empty="Nincs intézményi kapcsolat." />
          </section>
          <section className="section" aria-labelledby="related">
            <h2 id="related">Együtt előforduló témák</h2>
            <p className="muted small">Ugyanazoknál a kutatóknál vagy projekteknél jelennek meg. Együttes előfordulás, nem szellemi irányzat.</p>
            <TallyList items={t.related} empty="Nincs együtt előforduló téma." />
          </section>
          <section className="section" aria-labelledby="methods">
            <h2 id="methods">Társuló módszerek</h2>
            <TallyList items={t.methods} empty="Ugyanezeknél a kutatóknál és projekteknél nincs módszertani címke." />
          </section>
        </aside>
      </div>

      <section className="section" aria-labelledby="network">
        <header>
          <h2 id="network">Kapcsolatháló</h2>
          <Link className="aside" href={`/network?focus=${id}`}>Megnyitás a hálózati nézetben</Link>
        </header>
        <EgoNetwork slice={ego} centerId={id} secondLabel="A kutatók és projektek további kapcsolatai" />
      </section>
    </div>
  );
}
