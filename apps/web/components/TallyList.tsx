import Link from "next/link";
import type { Tally } from "@/lib/atlas/profiles";
import { hrefFor } from "@/lib/atlas/vocab";

// Counts of co-occurrence, shown as plain numbers with what they count. Not a ranking.
export default function TallyList({ items, limit = 10, empty }: { items: Tally[]; limit?: number; empty: string }) {
  if (!items.length) return <p className="empty">{empty}</p>;
  return (
    <ul className="rows compact">
      {items.slice(0, limit).map((t) => (
        <li key={t.node.id} style={{ display: "flex", justifyContent: "space-between", gap: 12 }}>
          <Link href={hrefFor(t.node.id, t.node.type)}>{t.node.label}</Link>
          <span className="muted small num" style={{ whiteSpace: "nowrap" }}>
            {t.persons > 0 && `${t.persons} kutató`}{t.persons > 0 && t.projects > 0 && " · "}{t.projects > 0 && `${t.projects} projekt`}
          </span>
        </li>
      ))}
    </ul>
  );
}
