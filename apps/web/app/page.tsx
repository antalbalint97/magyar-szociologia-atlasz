import Link from "next/link";
import EntitySearch from "@/components/EntitySearch";
import { KindLabel } from "@/components/Glyph";
import StaticGraph from "@/components/StaticGraph";
import { coverageView } from "@/lib/atlas/coverage";
import { buildSlice, filterSlice, presets } from "@/lib/atlas/network";
import { findByLabel, overview, termCards } from "@/lib/atlas/overview";
import { atlas, coverageData } from "@/lib/atlas/server";
import { hrefFor, hu, percent } from "@/lib/atlas/vocab";

// Candidate entry points; each is shown only if the current release links it to real entities.
const FEATURED = ["Computational social science", "Roma studies", "Inequality", "Social networks",
  "Sociology of education", "Migration", "Solidarity and civil society", "Health sociology"];

export default async function Home() {
  const a = await atlas();
  const o = overview(a);
  const cov = coverageView(await coverageData());
  const css = presets(a).find((p) => p.key === "css");
  const hero = css ? filterSlice(buildSlice(a, css.spec), { minDegree: 2 }) : null;
  const heroLabels = new Set(hero?.nodes.filter((n) => n.kind === "unit" || n.kind === "topic").map((n) => n.id) ?? []);
  const cards = termCards(a, FEATURED, 3);
  const route = ["Koltai Júlia", "TK Számítógépes Társadalomtudomány - CSS-RECENS", "Computational social science", "Kmetty Zoltán"]
    .map((l) => findByLabel(a, l));
  return (
    <>
      <section className="hero">
        <div className="wrap grid">
          <div>
            <div className="eyebrow">Pilot · TK-snapshot · {a.info.generatedAt.slice(0, 10)}</div>
            <h1>Magyar Szociológia Atlasz</h1>
            <p className="lede">
              A magyar szociológia intézményeinek, kutatóinak, projektjeinek és tudáskapcsolatainak interaktív térképe —
              minden kapcsolat mögött egy megnevezett forrásoldallal.
            </p>
            <EntitySearch big placeholder="Kutatót, témát vagy projektet keresek… (pl. Koltai, romakutatás)" />
            <div className="actions">
              <Link className="btn primary" href="/network">Felfedezem a hálózatot</Link>
              <Link className="btn ghost" href="/people">Kutatót keresek</Link>
            </div>
          </div>
          {hero && hero.nodes.length > 0 && (
            <figure className="hero-figure" style={{ margin: 0 }}>
              <Link href="/network?preset=css" aria-label="A számítógépes társadalomtudományi szelet megnyitása a hálózati nézetben">
                <StaticGraph slice={hero} labels={heroLabels} title="A számítógépes társadalomtudományi szelet valós adatokból" cluster />
              </Link>
              <figcaption>
                Valós adat: a számítógépes társadalomtudományi szelet ({hero.nodes.filter((n) => n.kind === "person").length} kutató,{" "}
                {hero.nodes.filter((n) => n.kind === "project").length} projekt, legalább két kapcsolattal). Szaggatott vonal: kulcsszó
                alapján származtatott kapcsolat.
              </figcaption>
            </figure>
          )}
        </div>
      </section>

      <div className="wrap">
        <section className="section" aria-labelledby="scope">
          <header>
            <h2 id="scope">Mit tartalmaz most az atlasz?</h2>
            <span className="aside">TK / kortárs pilot snapshot — nem a teljes magyar szociológia</span>
          </header>
          <div className="stats">
            <div><div className="v">{hu(o.persons)}</div><div className="l">azonosított kutató</div><div className="d">intézményi profiloldal alapján</div></div>
            <div><div className="v">{hu(o.projects)}</div><div className="l">projekt saját projektoldallal</div><div className="d">ebből {hu(o.projectsWithPeople)} projektnek van azonosított résztvevője</div></div>
            <div><div className="v">{hu(o.coveredUnits)}</div><div className="l">feldolgozott intézet és osztály</div><div className="d">további {hu(o.registryUnits)} csak nyilvántartásban</div></div>
            <div><div className="v">{hu(o.topics + o.methods)}</div><div className="l">téma és módszer</div><div className="d">{o.topics} téma, {o.methods} módszer, kulcsszó-szabállyal hozzárendelve</div></div>
            <div><div className="v">{hu(cov.documents.total)}</div><div className="l">letöltött forrásoldal</div><div className="d">{cov.retrieved ? `${cov.retrieved.from.slice(0, 10)} – ${cov.retrieved.until.slice(0, 10)}` : a.info.generatedAt.slice(0, 10)}</div></div>
          </div>
          <p className="muted small" style={{ marginTop: 12 }}>
            A forrásoldalakon {hu(o.personMentions.total)} személyemlítés szerepel; ebből {hu(o.personMentions.resolved)} ({percent(o.personMentions.resolved, o.personMentions.total)})
            köthető bizonyítékkal azonosított kutatóhoz. A többi név a forrásban megmarad, de nem számít kutatónak. <Link href="/about/data">Részletek a lefedettségről</Link>
          </p>
        </section>

        {cards.length > 0 && (
          <section className="section" aria-labelledby="paths">
            <header>
              <h2 id="paths">Felfedezési útvonalak</h2>
              <Link className="aside" href="/topics">Minden téma és módszer</Link>
            </header>
            <div className="paths">
              {cards.map((c) => (
                <Link key={c.node.id} className="path" href={hrefFor(c.node.id, c.node.type)}>
                  <KindLabel kind={c.node.kind} />
                  <h3>{c.node.label}</h3>
                  {c.related.length > 0 && <p>Gyakran együtt: {c.related.join(", ")}</p>}
                  <div className="counts">{c.persons} kutató · {c.projects} projekt kapcsolódik (kulcsszó alapján)</div>
                </Link>
              ))}
            </div>
          </section>
        )}

        <section className="section" aria-labelledby="read">
          <header><h2 id="read">Hogyan olvasd a hálót?</h2></header>
          <div className="legend-rows">
            <div>
              <div><span className="badge observed">megfigyelt</span></div>
              <div>
                <strong>A forrás kimondja.</strong> Intézményi tagság, osztálytagság, projektvezetés, projektrészvétel: egy letöltött
                intézeti oldal állítja. Folytonos vonal. Jelenleg {hu(o.observedRelations)} ilyen kapcsolat.
              </div>
            </div>
            <div>
              <div><span className="badge derived">származtatott</span></div>
              <div>
                <strong>Mi rendeltük hozzá, szabállyal.</strong> A témák és módszerek a profilok és projektleírások szövegéből
                kulcsszó-szabállyal kerülnek egy kutatóhoz vagy projekthez; a szabály és az eredeti szöveg mindig látható.
                Szaggatott vonal. Jelenleg {hu(o.derivedRelations)} ilyen kapcsolat.
              </div>
            </div>
            <div>
              <div><span className="badge open">azonosítatlan</span></div>
              <div>
                <strong>Nyitott kérdés.</strong> Egy név vagy projektcím szerepel a forrásban, de nincs elég bizonyíték, hogy egy
                azonosított kutatóhoz vagy projekthez kössük. Ezek nem csomópontok a hálóban; a forrásoldalukon megtekinthetők.
                Jelenleg {hu(o.personMentions.total - o.personMentions.resolved)} személy- és {hu(o.projectMentions.total - o.projectMentions.resolved)} projektemlítés ilyen.
              </div>
            </div>
          </div>
        </section>

        {route.every(Boolean) && (
          <section className="section" aria-labelledby="route">
            <header><h2 id="route">Egy lehetséges útvonal hallgatóknak</h2></header>
            <ol className="rows" style={{ counterReset: "step" }}>
              <li><Link href={`/person/${route[0]!.id}`}>{route[0]!.label}</Link> profilja: hol dolgozik, milyen projektekben vett részt, és melyik projektemlítése maradt azonosítatlan.</li>
              <li>Tovább az egységére: <Link href={`/institution/${route[1]!.id}`}>{route[1]!.label}</Link> — kik a munkatársak, milyen témák jelennek meg náluk (aggregálva).</li>
              <li>Egy téma: <Link href={`/topic/${route[2]!.id}`}>{route[2]!.label}</Link> — kik kapcsolódnak hozzá a jelenlegi snapshotban.</li>
              <li>Egy másik kutató: <Link href={`/person/${route[3]!.id}`}>{route[3]!.label}</Link>, a projektjei és a kapcsolatháló.</li>
              <li>Végül a teljes szelet: <Link href="/network?preset=css">a számítógépes társadalomtudományi hálózat</Link>.</li>
            </ol>
          </section>
        )}
      </div>
      <div style={{ height: 64 }} />
    </>
  );
}
