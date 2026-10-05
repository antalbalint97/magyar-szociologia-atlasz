import type { Metadata } from "next";
import Link from "next/link";
import { KindLabel } from "@/components/Glyph";
import { buildSlice, presets, sliceStats } from "@/lib/atlas/network";
import { termCards } from "@/lib/atlas/overview";
import { atlas } from "@/lib/atlas/server";
import { SOURCE_LABEL, hrefFor } from "@/lib/atlas/vocab";

export const metadata: Metadata = { title: "Felfedezés" };

export default async function Explore() {
  const a = await atlas();
  const institutes = a.ofKind("unit").filter((u) => u.sources.length && a.out(u.id, ["PART_OF"]).some((e) => !a.node(e.target)?.sources.length))
    .filter((u) => u.entity.sourceRefs.some((r) => r.endsWith("|site")));
  const cards = termCards(a, undefined, 3).sort((x, y) => x.node.label.localeCompare(y.node.label, "hu"));
  const ps = presets(a).map((p) => ({ p, s: sliceStats(buildSlice(a, p.spec)) }));
  return (
    <div className="wrap page">
      <div className="eyebrow">Felfedezés</div>
      <h1>Honnan induljunk?</h1>
      <p className="lede" style={{ marginTop: 8 }}>
        Az atlasz kapcsolatokon keresztül olvasható: egy intézettől a kutatóihoz, tőlük a projektjeikhez, onnan a
        témákhoz és vissza. Minden belépési pont a jelenlegi TK-snapshot valós adataira épül.
      </p>

      <section className="section" aria-labelledby="inst">
        <header><h2 id="inst">Intézetek</h2><Link className="aside" href="/institutions">Minden intézmény</Link></header>
        <div className="paths">
          {institutes.map((u) => {
            const tree = a.unitTree(u.id);
            const people = new Set(tree.flatMap((x) => a.in(x, ["AFFILIATED_WITH", "MEMBER_OF"]).map((e) => e.source))).size;
            const projects = tree.flatMap((x) => a.in(x, ["HOSTED_BY"])).length;
            return (
              <Link key={u.id} className="path" href={`/institution/${u.id}`}>
                <KindLabel kind="unit" text={SOURCE_LABEL[u.sources[0]]?.short ?? "Intézet"} />
                <h3>{u.label}</h3>
                <div className="counts">{people} munkatárs · {projects} projekt</div>
              </Link>
            );
          })}
        </div>
      </section>

      <section className="section" aria-labelledby="nets">
        <header><h2 id="nets">Hálózati nézetek</h2><Link className="aside" href="/network">A hálózati felfedező</Link></header>
        <div className="paths">
          {ps.map(({ p, s }) => (
            <Link key={p.key} className="path" href={`/network?preset=${p.key}`}>
              <span className="kind">Hálózati szelet</span>
              <h3>{p.title}</h3>
              <p>{p.description}</p>
              <div className="counts">{s.nodes} csomópont · {s.edges} kapcsolat ({s.derived} származtatott)</div>
            </Link>
          ))}
        </div>
      </section>

      <section className="section" aria-labelledby="terms">
        <header><h2 id="terms">Témák és módszerek</h2><Link className="aside" href="/topics">Teljes lista</Link></header>
        <p className="muted small">Legalább három kutatóhoz vagy projekthez kapcsolt témák, ábécérendben. A kapcsolat származtatott (kulcsszó-szabály).</p>
        <div className="chips">
          {cards.map((c) => (
            <Link key={c.node.id} className="chip derived" href={hrefFor(c.node.id, c.node.type)}>
              {c.node.label} <span className="n">{c.persons}/{c.projects}</span>
            </Link>
          ))}
        </div>
        <p className="muted small" style={{ marginTop: 8 }}>A számok: kapcsolt kutatók / kapcsolt projektek.</p>
      </section>
    </div>
  );
}
