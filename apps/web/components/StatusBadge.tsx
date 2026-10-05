import type { EpistemicStatus } from "@/lib/graph";
import { STATUS_EXPLAIN, STATUS_SHORT } from "@/lib/atlas/vocab";

// Observed and derived never look alike: solid vs dashed, and the word is always printed.
export function StatusBadge({ status }: { status: EpistemicStatus }) {
  const cls = status === "OBSERVED" ? "observed" : "derived";
  return (
    <span className={`badge ${cls}`} title={STATUS_EXPLAIN[status]}>
      {STATUS_SHORT[status]}
    </span>
  );
}

export function OpenBadge({ text = "azonosítatlan említés", title }: { text?: string; title?: string }) {
  return (
    <span className="badge open" title={title ?? "Forrásban szereplő név vagy cím, amelyet a bizonyítékok alapján nem kötöttünk azonosított entitáshoz."}>
      {text}
    </span>
  );
}
