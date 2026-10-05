import type { Metadata } from "next";
import Link from "next/link";
import { coveredUnits, filterPeople } from "@/lib/atlas/directory";
import { atlas } from "@/lib/atlas/server";
import { openPersonMentions } from "@/lib/atlas/notices";
import { hu } from "@/lib/atlas/vocab";
import { IssueLink } from "@/components/CoverageNote";

export const metadata: Metadata = { title: "Kutatók" };

type SP = Promise<{ q?: string; unit?: string; term?: string }>;

export default async function People({ searchParams }: { searchParams: SP }) {
  const sp = await searchParams;
  const a = await atlas();
  const people = filterPeople(a, sp);
  const units = coveredUnits(a);
  const terms = [...a.ofKind("topic"), ...a.ofKind("method")].sort((x, y) => x.label.localeCompare(y.label, "hu"));
  const open = openPersonMentions(a);
  // grouped by institutional affiliation (the institute-level unit), not one alphabetical dump
  const groups = new Map<string, { label: string; href: string | null; people: typeof people }>();
  for (const p of people) {
    const aff = a.unitsOfPerson(p.id).find((u) => u.edge.type === "AFFILIATED_WITH")?.unit;
    const key = aff?.id ?? "none";
    if (!groups.has(key)) groups.set(key, { label: aff?.label ?? "Intézményi tagság nélkül", href: aff ? `/institution/${aff.id}` : null, people: [] });
    groups.get(key)!.people.push(p);
  }
  const filtered = Boolean(sp.q || sp.unit || sp.term);
  return (
    <div className="wrap page">
      <div className="eyebrow">Kutatók</div>
      <h1>Kutatók</h1>
      <p className="lede" style={{ marginTop: 8 }}>
        {hu(a.ofKind("person").length)} azonosított kutató, akiknek saját profiloldaluk van a feldolgozott TK-forrásokban.
        A forrásokban ennél több név szerepel: {hu(open.n)} személyemlítés (a {hu(open.of)}-ból/-ből) nem köthető azonosított
        kutatóhoz — például korábbi munkatársak és külső partnerek (<IssueLink n={28} />). Ezek nem szerepelnek ebben a listában.
      </p>
      <form className="filters" method="get" action="/people" role="search" aria-label="Kutatók szűrése">
        <label>Név<input type="search" name="q" defaultValue={sp.q ?? ""} placeholder="pl. Ságvári" /></label>
        <label>Intézmény / egység
          <select name="unit" defaultValue={sp.unit ?? ""}>
            <option value="">Mind</option>
            {units.map((u) => <option key={u.id} value={u.id}>{u.label}</option>)}
          </select>
        </label>
        <label>Téma vagy módszer (származtatott)
          <select name="term" defaultValue={sp.term ?? ""}>
            <option value="">Mind</option>
            {terms.map((t) => <option key={t.id} value={t.id}>{t.label}{t.kind === "method" ? " (módszer)" : ""}</option>)}
          </select>
        </label>
        <button className="btn small primary" type="submit">Szűrés</button>
        {filtered && <Link href="/people" className="small">Szűrők törlése</Link>}
      </form>
      <p className="muted small" aria-live="polite">{people.length} kutató{filtered ? " a szűrés szerint" : ""}.</p>
      {people.length === 0 && <p className="empty">Nincs a feltételeknek megfelelő azonosított kutató a jelenlegi snapshotban.</p>}
      {[...groups.values()].sort((x, y) => y.people.length - x.people.length).map((g) => (
        <section key={g.label} className="section" style={{ marginTop: 32 }}>
          <header>
            <h2 style={{ fontSize: "1.2rem" }}>{g.href ? <Link href={g.href} style={{ color: "inherit" }}>{g.label}</Link> : g.label}</h2>
            <span className="aside">{g.people.length} kutató</span>
          </header>
          <div className="dir-grid">
            {g.people.map((p) => {
              const terms = a.topicsOf(p.id).map((t) => t.node.label);
              const dept = a.unitsOfPerson(p.id).find((u) => u.edge.type === "MEMBER_OF")?.unit;
              const projects = a.out(p.id, ["PRINCIPAL_INVESTIGATOR_OF", "PARTICIPATES_IN"]).map((e) => e.target);
              return (
                <div key={p.id} className="dir-item">
                  <Link className="name" href={`/person/${p.id}`}>{p.label}</Link>
                  <div className="sub">{[dept?.label, `${new Set(projects).size} projekt`].filter(Boolean).join(" · ")}</div>
                  {terms.length > 0 && <div className="sub" style={{ fontStyle: "italic" }}>{terms.slice(0, 3).join(", ")}{terms.length > 3 ? "…" : ""}</div>}
                </div>
              );
            })}
          </div>
        </section>
      ))}
    </div>
  );
}
