import type { Metadata } from "next";
import Link from "next/link";
import { KindLabel } from "@/components/Glyph";
import { termCards, type TermCard } from "@/lib/atlas/overview";
import { atlas } from "@/lib/atlas/server";
import { hrefFor } from "@/lib/atlas/vocab";

export const metadata: Metadata = { title: "Témák és módszerek" };

function List({ cards }: { cards: TermCard[] }) {
  return (
    <ul className="rows compact">
      {cards.map((c) => (
        <li key={c.node.id} style={{ display: "grid", gridTemplateColumns: "minmax(0,1fr) auto", gap: 12, alignItems: "baseline" }}>
          <div>
            <Link href={hrefFor(c.node.id, c.node.type)} style={{ fontFamily: "var(--serif)", fontWeight: 600, fontSize: "1.05rem" }}>{c.node.label}</Link>
            {c.node.altLabel && <span className="muted small"> · {c.node.altLabel}</span>}
          </div>
          <span className="muted small num" style={{ whiteSpace: "nowrap" }}>
            {c.persons + c.projects === 0 ? "nincs kapcsolat" : `${c.persons} kutató · ${c.projects} projekt`}
          </span>
        </li>
      ))}
    </ul>
  );
}

export default async function Topics() {
  const a = await atlas();
  const sortCards = (cs: TermCard[]) => cs.sort((x, y) => y.persons + y.projects - (x.persons + x.projects) || x.node.label.localeCompare(y.node.label, "hu"));
  const all = termCards(a, undefined, 0);
  const topics = sortCards(all.filter((c) => c.node.kind === "topic"));
  const methods = sortCards(all.filter((c) => c.node.kind === "method"));
  return (
    <div className="wrap page">
      <div className="eyebrow">Témák és módszerek</div>
      <h1>Témák és módszerek</h1>
      <p className="lede" style={{ marginTop: 8 }}>
        Az atlasz egy rögzített, verziózott taxonómiát használ. Egy kutató vagy projekt akkor kapcsolódik egy témához, ha a
        profil vagy a projektleírás szövege illeszkedik a téma kulcsszó-szabályára — ez <strong>származtatott</strong>{" "}
        kapcsolat, nem a kutató saját besorolása.
      </p>
      <p className="note" style={{ maxWidth: "80ch" }}>
        A listák a kapcsolt kutatók és projektek száma szerint rendezettek. Ez a jelenlegi forrásokban való előfordulást
        mutatja, nem a téma fontosságát: egy téma, amelyről a profilok nem írnak, itt kicsinek látszik.
      </p>
      <div className="split even" style={{ marginTop: 32 }}>
        <section><h2><KindLabel kind="topic" text="" /> Kutatási témák ({topics.length})</h2><List cards={topics} /></section>
        <section><h2><KindLabel kind="method" text="" /> Módszerek ({methods.length})</h2><List cards={methods} /></section>
      </div>
    </div>
  );
}
