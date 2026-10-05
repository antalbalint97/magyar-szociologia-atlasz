import type { Metadata } from "next";
import Link from "next/link";
import EntitySearch from "@/components/EntitySearch";
import { Glyph } from "@/components/Glyph";
import { OpenBadge } from "@/components/StatusBadge";
import { searchAtlas } from "@/lib/atlas/search";
import { atlas } from "@/lib/atlas/server";
import { KIND_OF } from "@/lib/atlas/vocab";

export const metadata: Metadata = { title: "Keresés" };

const GROUPS: [string, string[]][] = [
  ["Kutatók", ["Person"]],
  ["Témák és módszerek", ["ResearchTopic", "Method"]],
  ["Intézmények és egységek", ["Institution", "OrganisationalUnit", "ResearchGroup"]],
  ["Projektek", ["Project"]],
];

export default async function Search({ searchParams }: { searchParams: Promise<{ q?: string }> }) {
  const { q = "" } = await searchParams;
  const a = await atlas();
  const hits = q.trim() ? searchAtlas(a, q, 80, 30) : [];
  const canonical = hits.filter((h) => !h.mention);
  const mentions = hits.filter((h) => h.mention);
  return (
    <div className="wrap page">
      <div className="eyebrow">Keresés</div>
      <h1>{q ? <>Találatok: „{q}”</> : "Keresés az atlaszban"}</h1>
      <div style={{ maxWidth: 640, margin: "20px 0" }}><EntitySearch big /></div>
      <p className="muted small">Ékezetek nélkül és kisebb elírással is keres. {q && `${canonical.length} azonosított találat.`}</p>
      {q && canonical.length === 0 && <p className="empty">Nincs azonosított találat a jelenlegi snapshotban.</p>}
      {GROUPS.map(([title, types]) => {
        const g = canonical.filter((h) => types.includes(h.type));
        if (!g.length) return null;
        return (
          <section key={title} className="section" style={{ marginTop: 32 }}>
            <header><h2 style={{ fontSize: "1.2rem" }}>{title}</h2><span className="aside">{g.length}</span></header>
            <ul className="rows compact">
              {g.map((h) => (
                <li key={h.id}>
                  <div className="row-title"><Glyph kind={KIND_OF[h.type]} /><Link href={h.href}>{h.label}</Link></div>
                  <div className="row-meta"><span>{h.typeLabel}</span>{h.sub && <span>{h.sub}</span>}{h.context && <span>{h.context}</span>}</div>
                </li>
              ))}
            </ul>
          </section>
        );
      })}
      {mentions.length > 0 && (
        <section className="section" style={{ marginTop: 32 }}>
          <header><h2 style={{ fontSize: "1.2rem" }}>Azonosítatlan említések</h2><span className="aside">nem kutatók és nem projektek</span></header>
          <p className="muted small">Ezek a nevek és címek szerepelnek egy forrásoldalon, de nem köthetők azonosított entitáshoz.</p>
          <ul className="rows compact">
            {mentions.map((h) => (
              <li key={h.id}>
                <div className="row-title"><Link href={h.href} style={{ fontStyle: "italic", fontWeight: 400 }}>„{h.label}”</Link><OpenBadge text={h.typeLabel.toLowerCase()} /></div>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
