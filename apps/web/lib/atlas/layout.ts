// Deterministic layouts for graph slices. Coordinates are computed from the slice every time
// (never stored): d3-force with its built-in seeded random source, and a radial sector layout
// for ego networks. Pure functions, so they are unit-testable and identical on every render.
import { forceCollide, forceLink, forceManyBody, forceSimulation, forceX, forceY, type SimulationNodeDatum } from "d3-force";
import type { GEdge, GNode } from "./network.ts";
import type { Kind } from "./vocab.ts";

export interface Pos {
  x: number;
  y: number;
  anchor?: "start" | "end" | "middle";
}

export function nodeRadius(n: GNode, centerId?: string | null): number {
  if (n.id === centerId) return 11;
  switch (n.kind) {
    case "project":
      return 4 + 1.5 * Math.sqrt(Math.max(1, n.size ?? 1));
    case "unit":
      return n.seed ? 9 : 7;
    case "topic":
    case "method":
      return n.seed ? 8 : 6;
    default:
      return n.seed ? 7 : 5.5;
  }
}

interface SimNode extends SimulationNodeDatum {
  id: string;
  r: number;
  group: string | null;
}

export function forceLayout(nodes: GNode[], edges: GEdge[], opts: { cluster?: boolean; ticks?: number } = {}): Map<string, Pos> {
  const sim: SimNode[] = [...nodes]
    .sort((a, b) => a.id.localeCompare(b.id))
    .map((n) => ({ id: n.id, r: nodeRadius(n), group: n.group }));
  const links = edges.map((e) => ({ source: e.source, target: e.target }));
  const groups = [...new Set(sim.map((n) => n.group).filter((g): g is string => g !== null))].sort();
  const R = 60 + 22 * Math.sqrt(sim.length);
  const centers = new Map(groups.map((g, i) => {
    const a = (2 * Math.PI * i) / Math.max(groups.length, 1) - Math.PI / 2;
    return [g, groups.length > 1 ? { x: R * Math.cos(a), y: R * Math.sin(a) } : { x: 0, y: 0 }];
  }));
  const clustered = Boolean(opts.cluster && groups.length > 1);
  const s = forceSimulation(sim)
    .force("link", forceLink(links).id((d) => (d as SimNode).id).distance(34).strength(0.5))
    .force("charge", forceManyBody().strength(-55).distanceMax(320))
    .force("collide", forceCollide<SimNode>((d) => d.r + 3))
    .force("x", forceX<SimNode>((d) => (clustered && d.group ? centers.get(d.group)!.x : 0)).strength(clustered ? 0.12 : 0.05))
    .force("y", forceY<SimNode>((d) => (clustered && d.group ? centers.get(d.group)!.y : 0)).strength(clustered ? 0.12 : 0.05))
    .stop();
  // fewer ticks on large slices, with the decay scaled so the simulation still cools fully
  const ticks = opts.ticks ?? (sim.length > 150 ? 170 : 280);
  s.alphaDecay(1 - Math.pow(0.001, 1 / ticks));
  for (let i = 0; i < ticks; i++) s.tick();
  return new Map(sim.map((n) => [n.id, { x: n.x ?? 0, y: n.y ?? 0 }]));
}

/** Compact, serialisable form (server → client props), rounded to 0.1 px. */
export function packPositions(m: Map<string, Pos>): Record<string, [number, number]> {
  const out: Record<string, [number, number]> = {};
  for (const [id, p] of m) out[id] = [Math.round(p.x * 10) / 10, Math.round(p.y * 10) / 10];
  return out;
}

export function unpackPositions(r: Record<string, [number, number]>): Map<string, Pos> {
  return new Map(Object.entries(r).map(([id, [x, y]]) => [id, { x, y }]));
}

export function clusterCenters(nodes: GNode[]): Map<string, number> {
  const count = new Map<string, number>();
  for (const n of nodes) if (n.group) count.set(n.group, (count.get(n.group) ?? 0) + 1);
  return count;
}

const RING_ORDER: Kind[] = ["unit", "project", "topic", "method", "person"];

/**
 * Ego layout: the centre, first-order neighbours on a ring in one sector per kind, and
 * second-order nodes on an outer ring next to the first-order nodes that bring them in.
 */
export function radialLayout(nodes: GNode[], edges: GEdge[], centerId: string): Map<string, Pos> {
  const pos = new Map<string, Pos>([[centerId, { x: 0, y: 0, anchor: "middle" }]]);
  const adj = new Map<string, Set<string>>();
  for (const e of edges) {
    for (const [a, b] of [[e.source, e.target], [e.target, e.source]]) {
      if (!adj.has(a)) adj.set(a, new Set());
      adj.get(a)!.add(b);
    }
  }
  const first = nodes.filter((n) => n.id !== centerId && adj.get(centerId)?.has(n.id));
  const firstIds = new Set(first.map((n) => n.id));
  const second = nodes.filter((n) => n.id !== centerId && !firstIds.has(n.id));
  first.sort((a, b) => RING_ORDER.indexOf(a.kind) - RING_ORDER.indexOf(b.kind) || a.label.localeCompare(b.label, "hu"));
  const R1 = Math.max(150, (first.length * 26) / (2 * Math.PI));
  const angle = new Map<string, number>();
  // a small gap between kind sectors makes the categories readable as groups
  const kinds = [...new Set(first.map((n) => n.kind))];
  const gap = kinds.length > 1 ? 0.6 : 0;
  const slots = first.length + gap * kinds.length;
  let cursor = 0;
  let prevKind: Kind | null = null;
  for (const n of first) {
    if (prevKind !== null && n.kind !== prevKind) cursor += gap;
    const a = -Math.PI / 2 + (2 * Math.PI * (cursor + 0.5)) / Math.max(slots, 1);
    angle.set(n.id, a);
    pos.set(n.id, place(R1, a));
    cursor += 1;
    prevKind = n.kind;
  }
  const R2 = R1 + 120;
  const want = second.map((n) => {
    const parents = [...(adj.get(n.id) ?? [])].filter((p) => angle.has(p));
    const a = parents.length ? circularMean(parents.map((p) => angle.get(p)!)) : 0;
    return { n, a };
  }).sort((x, y) => x.a - y.a || x.n.label.localeCompare(y.n.label, "hu"));
  const minStep = Math.min((2 * Math.PI) / Math.max(want.length, 1), 22 / R2);
  for (let i = 1; i < want.length; i++) {
    if (want[i].a - want[i - 1].a < minStep) want[i].a = want[i - 1].a + minStep;
  }
  for (const { n, a } of want) {
    angle.set(n.id, a);
    pos.set(n.id, place(R2, a));
  }
  return pos;
}

function place(r: number, a: number): Pos {
  const c = Math.cos(a);
  return { x: r * c, y: r * Math.sin(a), anchor: c > 0.2 ? "start" : c < -0.2 ? "end" : "middle" };
}

function circularMean(as: number[]): number {
  const x = as.reduce((s, a) => s + Math.cos(a), 0);
  const y = as.reduce((s, a) => s + Math.sin(a), 0);
  return Math.atan2(y, x);
}
