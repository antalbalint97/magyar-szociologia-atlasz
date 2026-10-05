import type { Metadata } from "next";
import Link from "next/link";
import { IssueLink } from "@/components/CoverageNote";
import ProjectList from "@/components/ProjectList";
import { coveredUnits, filterProjects } from "@/lib/atlas/directory";
import { byRecency, projectRow } from "@/lib/atlas/profiles";
import { atlas } from "@/lib/atlas/server";
import { hu } from "@/lib/atlas/vocab";
import { RESOLVED_MENTION } from "@/lib/graph/mentions";

export const metadata: Metadata = { title: "Projektek" };

type SP = Promise<{ q?: string; unit?: string; status?: string; size?: string; term?: string }>;

const STATUS_GROUPS: [string, string][] = [["futó", "Futó projektek"], ["lezárt", "Lezárt projektek"], ["none", "Státusz a projektoldalon nincs megadva"]];

export default async function Projects({ searchParams }: { searchParams: SP }) {
  const sp = await searchParams;
  const a = await atlas();
  const rows = filterProjects(a, sp).map((p) => projectRow(a, p, [])).sort(byRecency);
  const units = coveredUnits(a).filter((u) => a.in(u.id, ["HOSTED_BY"]).length || a.unitTree(u.id).some((x) => a.in(x, ["HOSTED_BY"]).length));
  const terms = [...a.ofKind("topic"), ...a.ofKind("method")].sort((x, y) => x.label.localeCompare(y.label, "hu"));
  const mentions = a.mentions.filter((m) => m.kind === "project");
  const open = mentions.filter((m) => !RESOLVED_MENTION.has(m.status)).length;
  const filtered = Boolean(sp.q || sp.unit || sp.status || sp.size || sp.term);
  return (
    <div className="wrap page">
      <div className="eyebrow">Projektek</div>
      <h1>Projektek</h1>
      <p className="lede" style={{ marginTop: 8 }}>
        {hu(a.ofKind("project").length)} projekt, amelynek saját projektoldala van a feldolgozott forrásokban. A profilokon
        további {hu(open)} projektcím szerepel projektoldal vagy elég bizonyíték nélkül; ezek azonosítatlan említések, és a
        kutatók adatlapján láthatók. Hogy egy felsorolt tevékenység valóban projekt-e, azt a <IssueLink n={9} /> dönti el.
      </p>
      <form className="filters" method="get" action="/projects" role="search" aria-label="Projektek szűrése">
        <label>Cím<input type="search" name="q" defaultValue={sp.q ?? ""} placeholder="pl. szolidaritás" /></label>
        <label>Befogadó egység
          <select name="unit" defaultValue={sp.unit ?? ""}>
            <option value="">Mind</option>
            {units.map((u) => <option key={u.id} value={u.id}>{u.label}</option>)}
          </select>
        </label>
        <label>Státusz
          <select name="status" defaultValue={sp.status ?? ""}>
            <option value="">Mind</option>
            <option value="futó">Futó</option>
            <option value="lezárt">Lezárt</option>
            <option value="none">Nincs megadva</option>
          </select>
        </label>
        <label>Projektméret
          <select name="size" defaultValue={sp.size ?? ""}>
            <option value="">Mind</option>
            <option value="1">Legalább 1 azonosított résztvevő</option>
            <option value="5">Legalább 5</option>
            <option value="10">Legalább 10</option>
          </select>
        </label>
        <label>Téma vagy módszer
          <select name="term" defaultValue={sp.term ?? ""}>
            <option value="">Mind</option>
            {terms.map((t) => <option key={t.id} value={t.id}>{t.label}</option>)}
          </select>
        </label>
        <button className="btn small primary" type="submit">Szűrés</button>
        {filtered && <Link href="/projects" className="small">Szűrők törlése</Link>}
      </form>
      <p className="muted small" aria-live="polite">{rows.length} projekt{filtered ? " a szűrés szerint" : ""}.</p>
      {rows.length === 0 && <p className="empty">Nincs a feltételeknek megfelelő projekt a jelenlegi snapshotban.</p>}
      {STATUS_GROUPS.map(([key, title]) => {
        const g = rows.filter((r) => (r.status ?? "none") === key);
        if (!g.length) return null;
        return (
          <section key={key} className="section" style={{ marginTop: 32 }}>
            <header><h2 style={{ fontSize: "1.2rem" }}>{title}</h2><span className="aside">{g.length}</span></header>
            <ProjectList rows={g} showRole={false} limit={15} evidence={false} />
          </section>
        );
      })}
    </div>
  );
}
