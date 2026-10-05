"use client";
// The one network renderer of the atlas: SVG, positions from lib/atlas/layout.ts.
// Zoom/pan (wheel, drag, buttons), click selection, hover/focus highlight with dimming,
// and a label budget so a slice never shows hundreds of labels at once.
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { GEdge, GNode } from "@/lib/atlas/network";
import { nodeRadius, type Pos } from "@/lib/atlas/layout";
import { KIND_COLOR, shapePath } from "@/lib/atlas/shapes";
import { KIND_LABEL } from "@/lib/atlas/vocab";

interface View {
  x: number;
  y: number;
  k: number;
}

function short(s: string, n: number) {
  return s.length > n ? s.slice(0, n - 1) + "…" : s;
}

export default function NetworkCanvas({
  nodes, edges, positions, selected, onSelect, centerId = null, height = 600, labelBudget = 16,
  ariaLabel, tabbableNodes = false, alwaysLabel,
}: {
  nodes: GNode[];
  edges: GEdge[];
  positions: Map<string, Pos>;
  selected: string | null;
  onSelect: (id: string | null) => void;
  centerId?: string | null;
  height?: number;
  labelBudget?: number;
  ariaLabel: string;
  tabbableNodes?: boolean;
  alwaysLabel?: Set<string>;
}) {
  const wrap = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(800);
  const [hover, setHover] = useState<string | null>(null);
  const [view, setView] = useState<View>({ x: 0, y: 0, k: 1 });
  // positions come from floating-point layout code whose last digits differ between the
  // server and the browser engine, so the drawing is client-only (the table view is not)
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);
  const drag = useRef<{ x: number; y: number; vx: number; vy: number; moved: boolean } | null>(null);

  useEffect(() => {
    if (!wrap.current) return;
    const ro = new ResizeObserver(([e]) => setWidth(Math.max(280, Math.round(e.contentRect.width))));
    ro.observe(wrap.current);
    return () => ro.disconnect();
  }, []);

  const fit = useCallback((): View => {
    const pts = nodes.map((n) => positions.get(n.id)).filter((p): p is Pos => Boolean(p));
    if (!pts.length) return { x: width / 2, y: height / 2, k: 1 };
    const xs = pts.map((p) => p.x), ys = pts.map((p) => p.y);
    const minX = Math.min(...xs), maxX = Math.max(...xs), minY = Math.min(...ys), maxY = Math.max(...ys);
    const padX = Math.min(170, width * 0.2), padY = 36; // room for labels
    const k = Math.min(2.2, (width - padX * 2) / Math.max(maxX - minX, 1), (height - padY * 2) / Math.max(maxY - minY, 1));
    const kk = Math.max(0.25, k);
    return { k: kk, x: width / 2 - ((minX + maxX) / 2) * kk, y: height / 2 - ((minY + maxY) / 2) * kk };
  }, [nodes, positions, width, height]);

  useEffect(() => setView(fit()), [fit]);

  const byId = useMemo(() => new Map(nodes.map((n) => [n.id, n])), [nodes]);
  const neighbours = useMemo(() => {
    const m = new Map<string, Set<string>>();
    for (const e of edges) {
      for (const [a, b] of [[e.source, e.target], [e.target, e.source]]) {
        if (!m.has(a)) m.set(a, new Set());
        m.get(a)!.add(b);
      }
    }
    return m;
  }, [edges]);

  const active = hover ?? selected;
  const activeSet = useMemo(() => {
    if (!active) return null;
    return new Set([active, ...(neighbours.get(active) ?? [])]);
  }, [active, neighbours]);

  // dynamic labels: always the centre/seeds/selection, then neighbours of the active node,
  // then the best-connected nodes up to a budget that grows as the user zooms in
  const labelled = useMemo(() => {
    const out = new Set<string>(alwaysLabel ?? []);
    if (centerId) out.add(centerId);
    if (nodes.length <= 28) for (const n of nodes) out.add(n.id);
    for (const n of nodes) if (n.seed && nodes.length <= 120) out.add(n.id);
    if (selected) out.add(selected);
    if (active) {
      out.add(active);
      const nb = [...(neighbours.get(active) ?? [])];
      if (nb.length <= 30) nb.forEach((id) => out.add(id));
    }
    const budget = Math.round(labelBudget * Math.max(1, view.k * view.k));
    const ranked = [...nodes].sort((a, b) => b.degree - a.degree || a.label.localeCompare(b.label, "hu"));
    for (const n of ranked) {
      if (out.size >= budget + (active ? 30 : 0)) break;
      out.add(n.id);
    }
    return out;
  }, [nodes, centerId, selected, active, neighbours, labelBudget, view.k, alwaysLabel]);

  // greedy label placement in screen space: must-show labels first, then by degree;
  // a label that would overlap one already placed is dropped (the node keeps its tooltip/panel)
  const placed = useMemo(() => {
    const must = new Set([centerId, selected, active].filter(Boolean) as string[]);
    const order = nodes.filter((n) => labelled.has(n.id))
      .sort((a, b) => Number(must.has(b.id)) - Number(must.has(a.id)) || Number(b.seed) - Number(a.seed) ||
        b.degree - a.degree || a.label.localeCompare(b.label, "hu"));
    const boxes: [number, number, number, number][] = [];
    const out: { n: GNode; x: number; y: number; anchor: "start" | "end" | "middle"; size: number; big: boolean }[] = [];
    for (const n of order) {
      const p = positions.get(n.id);
      if (!p) continue;
      const big = n.id === centerId || n.id === selected;
      const size = (big ? 14 : 11.5) / view.k;
      const r = nodeRadius(n, centerId) / Math.sqrt(view.k);
      const anchor = p.anchor ?? "start";
      const x = p.x + (anchor === "start" ? r + 4 / view.k : anchor === "end" ? -(r + 4 / view.k) : 0);
      const y = p.y + (anchor === "middle" ? -(r + 6 / view.k) : 4 / view.k);
      const w = Math.min(n.label.length, big ? 48 : 30) * size * 0.56;
      const x0 = anchor === "start" ? x : anchor === "end" ? x - w : x - w / 2;
      const box: [number, number, number, number] = [x0, y - size, x0 + w, y + size * 0.3];
      const hit = boxes.some((b) => box[0] < b[2] && box[2] > b[0] && box[1] < b[3] && box[3] > b[1]);
      if (hit && !must.has(n.id)) continue;
      boxes.push(box);
      out.push({ n, x, y, anchor, size, big });
    }
    return out;
  }, [nodes, labelled, positions, centerId, selected, active, view.k]);

  const zoomBy = (f: number, cx = width / 2, cy = height / 2) =>
    setView((v) => {
      const k = Math.min(8, Math.max(0.2, v.k * f));
      const r = k / v.k;
      return { k, x: cx - (cx - v.x) * r, y: cy - (cy - v.y) * r };
    });

  useEffect(() => {
    const el = wrap.current?.querySelector("svg");
    if (!el) return;
    const onWheel = (e: WheelEvent) => {
      e.preventDefault();
      const rect = el.getBoundingClientRect();
      zoomBy(e.deltaY < 0 ? 1.15 : 1 / 1.15, e.clientX - rect.left, e.clientY - rect.top);
    };
    el.addEventListener("wheel", onWheel, { passive: false });
    return () => el.removeEventListener("wheel", onWheel);
  });

  const nodeOpacity = (id: string) => (activeSet && !activeSet.has(id) ? 0.18 : 1);
  const edgeActive = (e: GEdge) => !active || e.source === active || e.target === active;

  return (
    <div ref={wrap} style={{ position: "relative", height }}>
      {mounted && <svg
        viewBox={`0 0 ${width} ${height}`} width={width} height={height} role="group" aria-label={ariaLabel}
        onPointerDown={(e) => {
          if ((e.target as Element).closest(".g-node")) return;
          drag.current = { x: e.clientX, y: e.clientY, vx: view.x, vy: view.y, moved: false };
          (e.currentTarget as SVGSVGElement).setPointerCapture(e.pointerId);
        }}
        onPointerMove={(e) => {
          const d = drag.current;
          if (!d) return;
          const dx = e.clientX - d.x, dy = e.clientY - d.y;
          if (Math.abs(dx) + Math.abs(dy) > 3) d.moved = true;
          setView((v) => ({ ...v, x: d.vx + dx, y: d.vy + dy }));
        }}
        onPointerUp={() => {
          const d = drag.current;
          drag.current = null;
          if (d && !d.moved) onSelect(null);
        }}
      >
        <g transform={`translate(${view.x},${view.y}) scale(${view.k})`}>
          <g>
            {edges.map((e) => {
              const a = positions.get(e.source), b = positions.get(e.target);
              if (!a || !b) return null;
              const on = edgeActive(e);
              const derived = e.status !== "OBSERVED";
              return (
                <line
                  key={e.id} x1={a.x} y1={a.y} x2={b.x} y2={b.y}
                  stroke={derived ? "var(--derived)" : "var(--observed)"}
                  strokeOpacity={active ? (on ? 0.85 : 0.06) : derived ? 0.45 : 0.3}
                  strokeWidth={e.group === "lead" ? 2 : 1.1}
                  strokeDasharray={derived ? "4 3" : undefined}
                  vectorEffect="non-scaling-stroke"
                />
              );
            })}
          </g>
          <g>
            {nodes.map((n) => {
              const p = positions.get(n.id);
              if (!p) return null;
              const r = nodeRadius(n, centerId);
              const isSel = n.id === selected;
              return (
                <g
                  key={n.id} className="g-node" transform={`translate(${p.x},${p.y})`} opacity={nodeOpacity(n.id)}
                  tabIndex={tabbableNodes ? 0 : -1} role="button" aria-pressed={isSel}
                  aria-label={`${n.label} (${KIND_LABEL[n.kind]})`}
                  onPointerEnter={() => setHover(n.id)} onPointerLeave={() => setHover(null)}
                  onFocus={() => setHover(n.id)} onBlur={() => setHover(null)}
                  onClick={() => onSelect(isSel ? null : n.id)}
                  onKeyDown={(ev) => {
                    if (ev.key === "Enter" || ev.key === " ") {
                      ev.preventDefault();
                      onSelect(isSel ? null : n.id);
                    }
                  }}
                >
                  <g transform={`scale(${1 / Math.sqrt(view.k)})`}>
                    <circle r={r + 8} fill="transparent" />
                    <path
                      className="ring" d={shapePath(n.kind, r)} fill={KIND_COLOR[n.kind]}
                      stroke={isSel ? "var(--ink)" : "var(--surface)"} strokeWidth={isSel ? 2.6 : 1.4}
                    />
                    {n.seed && !isSel && n.id !== centerId && (
                      <path d={shapePath(n.kind, r + 3.5)} fill="none" stroke={KIND_COLOR[n.kind]} strokeWidth={1} />
                    )}
                  </g>
                </g>
              );
            })}
          </g>
          <g aria-hidden="true">
            {placed.map(({ n, x, y, anchor, size, big }) => (
              <text
                key={n.id} className="node-label" x={x} y={y} textAnchor={anchor}
                fontSize={size} fontWeight={big ? 650 : n.seed ? 560 : 420}
                opacity={nodeOpacity(n.id)} strokeWidth={3.5 / view.k}
              >
                {short(n.label, big ? 48 : 30)}
              </text>
            ))}
          </g>
        </g>
      </svg>}
      <div className="tools">
        <button type="button" onClick={() => zoomBy(1.3)} aria-label="Nagyítás">+</button>
        <button type="button" onClick={() => zoomBy(1 / 1.3)} aria-label="Kicsinyítés">−</button>
        <button type="button" onClick={() => setView(fit())} aria-label="Nézet visszaállítása" title="Nézet visszaállítása">⟲</button>
      </div>
      {hover && byId.get(hover) && (
        <div className="summary" aria-hidden="true">{byId.get(hover)!.label} · {KIND_LABEL[byId.get(hover)!.kind]}</div>
      )}
    </div>
  );
}
