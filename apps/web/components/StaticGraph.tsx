// A non-interactive rendering of a real graph slice (server-side, same layout code as the
// explorer). Used as a figure; the interactive version is always one click away.
import type { GraphSlice } from "@/lib/atlas/network";
import { forceLayout, nodeRadius } from "@/lib/atlas/layout";
import { KIND_COLOR, shapePath } from "@/lib/atlas/shapes";

export default function StaticGraph({ slice, labels, width = 560, height = 420, title, cluster = false }: {
  slice: GraphSlice; labels: Set<string>; width?: number; height?: number; title: string; cluster?: boolean;
}) {
  const pos = forceLayout(slice.nodes, slice.edges, { cluster });
  const pts = [...pos.values()];
  const minX = Math.min(...pts.map((p) => p.x)), maxX = Math.max(...pts.map((p) => p.x));
  const minY = Math.min(...pts.map((p) => p.y)), maxY = Math.max(...pts.map((p) => p.y));
  const k = Math.min((width - 160) / Math.max(maxX - minX, 1), (height - 40) / Math.max(maxY - minY, 1));
  const tx = (x: number) => width / 2 + (x - (minX + maxX) / 2) * k;
  const ty = (y: number) => height / 2 + (y - (minY + maxY) / 2) * k;
  const taken: [number, number, number, number][] = [];
  return (
    <svg viewBox={`0 0 ${width} ${height}`} width="100%" role="img" aria-label={title} style={{ display: "block", height: "auto" }}>
      {slice.edges.map((e) => {
        const a = pos.get(e.source), b = pos.get(e.target);
        if (!a || !b) return null;
        const d = e.status !== "OBSERVED";
        return <line key={e.id} x1={tx(a.x)} y1={ty(a.y)} x2={tx(b.x)} y2={ty(b.y)} stroke={d ? "var(--derived)" : "var(--observed)"}
          strokeOpacity={d ? 0.5 : 0.28} strokeWidth={e.group === "lead" ? 1.8 : 1} strokeDasharray={d ? "4 3" : undefined} />;
      })}
      {slice.nodes.map((n) => {
        const p = pos.get(n.id)!;
        return (
          <g key={n.id} transform={`translate(${tx(p.x)},${ty(p.y)})`}>
            <path d={shapePath(n.kind, nodeRadius(n) * 0.9)} fill={KIND_COLOR[n.kind]} stroke="var(--surface)" strokeWidth={1.2} />
          </g>
        );
      })}
      {slice.nodes.filter((n) => labels.has(n.id)).filter((n) => {
        // drop a label that would overlap one already placed
        const p = pos.get(n.id)!;
        const x = tx(p.x) + nodeRadius(n) + 3, y = ty(p.y);
        const w = Math.min(n.label.length, 32) * 6.4;
        const hit = taken.some((b) => x < b[2] && x + w > b[0] && y - 12 < b[3] && y + 4 > b[1]);
        if (!hit) taken.push([x, y - 12, x + w, y + 4]);
        return !hit;
      }).map((n) => {
        const p = pos.get(n.id)!;
        return (
          <text key={n.id} className="node-label" x={tx(p.x) + nodeRadius(n) + 3} y={ty(p.y) + 4} fontSize={11.5} fontWeight={560}>
            {n.label.length > 32 ? n.label.slice(0, 31) + "…" : n.label}
          </text>
        );
      })}
    </svg>
  );
}
