import Link from "next/link";
import { graph } from "@/lib/graph";

const TYPE_HU: Record<string, string> = {
  Person: "személy", Institution: "intézmény", OrganisationalUnit: "szervezeti egység",
  ResearchGroup: "kutatócsoport", Project: "projekt", ResearchTopic: "téma", Method: "módszer",
  IntellectualTradition: "hagyomány", Event: "esemény", Journal: "folyóirat",
};

export default async function Home({ searchParams }: { searchParams: Promise<{ q?: string }> }) {
  const { q = "" } = await searchParams;
  const results = q ? await graph().search(q, 40) : [];
  return (
    <>
      {!q && (
        <section className="card">
          <h2>Explorer</h2>
          <p>
            Keress személyre, intézményre, témára vagy módszerre. Minden adat forráshoz kötött; a megfigyelt
            (forrásban szereplő) és a származtatott kapcsolatok külön jelölést kapnak.
          </p>
          <p className="muted">Search people, institutions, topics or methods. Accents are optional.</p>
        </section>
      )}
      {q && (
        <>
          <p className="muted">{results.length} találat: „{q}”</p>
          <ul className="results">
            {results.map((r) => (
              <li key={r.id}>
                <span className="type">{TYPE_HU[r.type] ?? r.type}</span>
                <br />
                <Link href={`/entity/${r.id}`}>{r.label}</Link>
                {r.alternateNames.length > 0 && <span className="muted"> · {r.alternateNames.join(", ")}</span>}
              </li>
            ))}
          </ul>
        </>
      )}
    </>
  );
}
