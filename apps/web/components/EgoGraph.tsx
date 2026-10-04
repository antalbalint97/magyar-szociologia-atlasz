// Small radial ego network rendered as static SVG on the server. Deliberately not a
// force-directed layout: positions are deterministic and readable at ~50 nodes.
// Observed relations are solid lines; derived/inferred ones are dashed.
import type { Neighbourhood } from "@/lib/graph";

const W = 720, H = 520, CX = W / 2, CY = H / 2, R1 = 150, R2 = 235;
const MAX_RING = 28;

const COLOR: Record<string, string> = {
  Person: "var(--accent)", ResearchTopic: "var(--derived)", Method: "var(--derived)",
};

function short(s: string, n = 26) {
  return s.length > n ? s.slice(0, n - 1) + "…" : s;
}

export default function EgoGraph({ hood }: { hood: Neighbourhood }) {
  const center = hood.center.id;
  const adj = new Map<string, Set<string>>();
  for (const e of hood.edges) {
    for (const [a, b] of [[e.source, e.target], [e.target, e.source]]) {
      if (!adj.has(a)) adj.set(a, new Set());
      adj.get(a)!.add(b);
    }
  }
  const ring1 = [...(adj.get(center) ?? [])].slice(0, MAX_RING);
  const r1set = new Set(ring1);
  const ring2 = [...new Set(ring1.flatMap((n) => [...(adj.get(n) ?? [])]))]
    .filter((n) => n !== center && !r1set.has(n)).slice(0, MAX_RING);
  const byId = new Map(hood.nodes.map((n) => [n.id, n]));
  const pos = new Map<string, [number, number]>([[center, [CX, CY]]]);
  const place = (ids: string[], r: number, offset: number) =>
    ids.forEach((id, i) => {
      const a = (2 * Math.PI * i) / Math.max(ids.length, 1) + offset;
      pos.set(id, [CX + r * Math.cos(a), CY + r * Math.sin(a)]);
    });
  place(ring1, R1, -Math.PI / 2);
  place(ring2, R2, -Math.PI / 2 + Math.PI / Math.max(ring2.length, 1));
  const edges = hood.edges.filter((e) => pos.has(e.source) && pos.has(e.target));
  const hidden = hood.nodes.length - pos.size;

  return (
    <div className="ego">
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`Ego network of ${hood.center.label}`}>
        {edges.map((e) => {
          const [x1, y1] = pos.get(e.source)!, [x2, y2] = pos.get(e.target)!;
          return (
            <line key={e.id} x1={x1} y1={y1} x2={x2} y2={y2}
              stroke={e.status === "OBSERVED" ? "var(--observed)" : "var(--derived)"}
              strokeOpacity={0.55} strokeWidth={e.source === center || e.target === center ? 1.6 : 0.9}
              strokeDasharray={e.status === "OBSERVED" ? undefined : "4 3"}>
              <title>{`${e.type} (${e.status})`}</title>
            </line>
          );
        })}
        {[...pos.entries()].map(([id, [x, y]]) => {
          const n = byId.get(id) ?? hood.center;
          const isCenter = id === center;
          const anchor = isCenter ? "middle" : x < CX - 5 ? "end" : x > CX + 5 ? "start" : "middle";
          const dx = isCenter ? 0 : anchor === "end" ? -8 : anchor === "start" ? 8 : 0;
          return (
            <a key={id} href={`/entity/${id}`}>
              <circle cx={x} cy={y} r={isCenter ? 9 : 5.5} fill={COLOR[n.type] ?? "var(--muted)"}
                stroke="var(--surface)" strokeWidth={1.5}>
                <title>{`${n.label} · ${n.type}`}</title>
              </circle>
              <text x={x + dx} y={isCenter ? y - 14 : y + 4} textAnchor={anchor}
                fontSize={isCenter ? 14 : 11} fontWeight={isCenter ? 650 : 400} fill="var(--text)">
                {short(n.label, isCenter ? 40 : 26)}
              </text>
            </a>
          );
        })}
      </svg>
      <div className="legend">
        <span>— megfigyelt (observed)</span>
        <span>- - származtatott (derived)</span>
        {hidden > 0 && <span>{hidden} további csomópont nincs kirajzolva</span>}
      </div>
    </div>
  );
}
