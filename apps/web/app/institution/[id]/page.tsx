import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { SourceNotes } from "@/components/CoverageNote";
import Facts from "@/components/Facts";
import { KindLabel } from "@/components/Glyph";
import UnitNetwork from "@/components/UnitNetwork";
import ProjectList from "@/components/ProjectList";
import TallyList from "@/components/TallyList";
import { buildSlice, restrictSlice } from "@/lib/atlas/network";
import { unitProfile } from "@/lib/atlas/profiles";
import { atlas } from "@/lib/atlas/server";
import { REL_LABEL, SOURCE_LABEL, TYPE_LABEL, UNIT_TYPE_LABEL } from "@/lib/atlas/vocab";

export async function generateMetadata({ params }: { params: Promise<{ id: string }> }): Promise<Metadata> {
  const n = (await atlas()).node((await params).id);
  return { title: n?.label ?? "Intézmény" };
}

export default async function InstitutionPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const a = await atlas();
  const u = unitProfile(a, id);
  if (!u) notFound();
  const f = u.node.fields;
  const typeKey = (f.unit_type ?? f.institution_type) as string | undefined;
  const tree = new Set(a.unitTree(id));
  // internal network: members of this unit (any depth) and projects hosted in it
  const internal = buildSlice(a, { seeds: [...tree], steps: [["affiliation", "hosting"], ["lead", "participation"]] });
  const inside = new Set([...tree, ...u.members.map((m) => m.person.id), ...u.projects.map((p) => p.project.id)]);
  const internalSlice = restrictSlice(internal, inside);
  const sources = [...new Set([...u.node.sources, ...[...tree].flatMap((t) => a.node(t)?.sources ?? [])])];
  return (
    <div className="wrap page">
      <nav className="breadcrumb" aria-label="Morzsamenü">
        <Link href="/institutions">Intézmények</Link>
        {[...u.ancestors].reverse().map((x) => (
          <span key={x.id} style={{ display: "contents" }}><span aria-hidden="true">/</span><Link href={`/institution/${x.id}`}>{x.label}</Link></span>
        ))}
      </nav>
      <header className="entity-head">
        <div className="eyebrow">
          <KindLabel kind="unit" text={TYPE_LABEL[u.node.type]} />
          {typeKey && <span className="badge neutral">{UNIT_TYPE_LABEL[typeKey] ?? typeKey}</span>}
          {u.node.sources.map((s) => <span key={s} className="badge neutral">forrás: {SOURCE_LABEL[s]?.short ?? s}</span>)}
        </div>
        <h1>{u.node.label}</h1>
        {typeof f.english_name === "string" && <div className="alt">{f.english_name}</div>}
        {u.registryOnly ? (
          <p className="note" style={{ maxWidth: "75ch", marginTop: 16 }}>
            <strong>Csak nyilvántartásban.</strong> Ez az egység szerepel az atlasz intézményi törzsében, de a forrásait
            még nem dolgoztuk fel, ezért nincsenek hozzá kutatók vagy projektek. A hiány a gyűjtés állapotát tükrözi, nem az
            egység tevékenységét.
          </p>
        ) : (
          <Facts items={[
            { label: "Megfigyelt munkatárs", value: u.members.length, note: tree.size > 1 ? "az alegységekkel" : undefined },
            { label: "Befogadott projekt", value: u.projects.length },
            { label: "Alegység", value: u.children.length },
          ]} />
        )}
      </header>

      {u.children.length > 0 && (
        <section className="section" aria-labelledby="children">
          <header><h2 id="children">Alegységek</h2></header>
          <div className="dir-grid">
            {u.children.map((c) => (
              <div key={c.node.id} className="dir-item">
                <Link className="name" href={`/institution/${c.node.id}`}>{c.node.label}</Link>
                <div className="sub">{c.registryOnly ? "csak nyilvántartásban" : `${c.members} munkatárs · ${c.projects} projekt`}</div>
              </div>
            ))}
          </div>
        </section>
      )}

      {!u.registryOnly && (
        <>
          <div className="split" style={{ marginTop: 40 }}>
            <section aria-labelledby="members">
              <h2 id="members">Munkatársak ({u.members.length})</h2>
              <p className="muted small">A jelenlegi munkatárslisták szerint; a korábbi munkatársak csak említésként szerepelnek.</p>
              <ul className="rows compact cols-list">
                {u.members.map((m) => (
                  <li key={m.person.id}>
                    <div className="row-title"><Link href={`/person/${m.person.id}`}>{m.person.label}</Link></div>
                    <div className="row-meta">
                      <span>{m.edges.map((e) => REL_LABEL[e.type]).join(", ")}{m.via.id !== id ? ` · ${m.via.label}` : ""}</span>
                    </div>
                  </li>
                ))}
              </ul>
            </section>
            <aside>
              <section aria-labelledby="profile">
                <h2 id="profile">Tematikus profil</h2>
                <p className="note">
                  <strong>Származtatott aggregálás.</strong> A munkatársak és projektek kulcsszó-szabállyal hozzárendelt
                  témáiból összesítve; nem az egység saját meghatározása.
                </p>
                <TallyList items={u.topics} empty="A munkatársak és projektek szövegeiből nem származtattunk témát." />
                <h3 style={{ marginTop: 16 }}>Módszerek</h3>
                <TallyList items={u.methods} limit={6} empty="Nincs módszertani címke." />
              </section>
            </aside>
          </div>

          <section className="section" aria-labelledby="projects">
            <header><h2 id="projects">Projektek ({u.projects.length})</h2><span className="aside">futó projektek elöl, majd kezdés szerint</span></header>
            <SourceNotes a={a} sources={sources} />
            {u.projects.length ? <ProjectList rows={u.projects} showRole={false} limit={12} evidence={false} />
              : <p className="empty">Ehhez az egységhez a forrás nem rendel projektoldalt.</p>}
          </section>

          {internalSlice.edges.length > 0 && (
            <section className="section" aria-labelledby="internal">
              <header>
                <h2 id="internal">Belső háló: munkatársak ↔ projektek</h2>
                <Link className="aside" href={`/network?focus=${id}`}>Tágabb nézet a hálózatban</Link>
              </header>
              <UnitNetwork slice={internalSlice} />
            </section>
          )}
        </>
      )}
    </div>
  );
}
