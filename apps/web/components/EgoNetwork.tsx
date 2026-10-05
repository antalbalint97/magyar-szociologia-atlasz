"use client";
// Ego network: the entity in the centre, first-order relations in one sector per kind,
// second-order nodes only on request (a toggle, or "show participants" on one project).
import { useMemo, useState } from "react";
import type { GraphSlice } from "@/lib/atlas/network";
import { radialLayout } from "@/lib/atlas/layout";
import { KIND_PLURAL, type Kind } from "@/lib/atlas/vocab";
import { Glyph } from "./Glyph";
import { GraphTable, Legend, NodePanel } from "./GraphParts";
import NetworkCanvas from "./NetworkCanvas";

export default function EgoNetwork({ slice, centerId, secondLabel, height: maxHeight = 600 }: {
  slice: GraphSlice;
  centerId: string;
  secondLabel: string; // what the second hop means for this kind of centre
  height?: number;
}) {
  const firstKinds = useMemo(() => {
    const order: Kind[] = ["unit", "project", "topic", "method", "person"];
    const ks = new Set(slice.nodes.filter((n) => n.hop === 1).map((n) => n.kind));
    return order.filter((k) => ks.has(k));
  }, [slice]);
  const hasSecond = slice.nodes.some((n) => n.hop >= 2);
  const hasDerived = slice.edges.some((e) => e.status !== "OBSERVED");
  const [kinds, setKinds] = useState<Set<Kind>>(new Set(firstKinds));
  const [second, setSecond] = useState(false);
  const [derived, setDerived] = useState(true);
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [selected, setSelected] = useState<string | null>(null);

  const view = useMemo(() => {
    const first = new Set(slice.nodes.filter((n) => n.hop === 1 && kinds.has(n.kind)).map((n) => n.id));
    const edgeOk = (e: GraphSlice["edges"][number]) => derived || e.status === "OBSERVED";
    const visible = new Set([centerId, ...first]);
    for (const n of slice.nodes) {
      if (n.hop < 2) continue;
      const links = slice.edges.filter((e) => edgeOk(e) && (e.source === n.id || e.target === n.id))
        .map((e) => (e.source === n.id ? e.target : e.source)).filter((x) => first.has(x));
      if (links.length && (second || links.some((x) => expanded.has(x)))) visible.add(n.id);
    }
    const edges = slice.edges.filter((e) => edgeOk(e) && visible.has(e.source) && visible.has(e.target) &&
      // second-hop nodes attach only to first-hop nodes, never to each other
      !(slice.nodes.find((n) => n.id === e.source)!.hop >= 2 && slice.nodes.find((n) => n.id === e.target)!.hop >= 2));
    const linked = new Set(edges.flatMap((e) => [e.source, e.target]));
    const nodes = slice.nodes.filter((n) => visible.has(n.id) && (n.id === centerId || linked.has(n.id)))
      .map((n) => ({ ...n, degree: edges.filter((e) => e.source === n.id || e.target === n.id).length }));
    return { nodes, edges, positions: radialLayout(nodes, edges, centerId) };
  }, [slice, kinds, second, derived, expanded, centerId]);

  const height = Math.min(maxHeight, 320 + view.nodes.length * 9);
  const sel = view.nodes.find((n) => n.id === selected) ?? null;
  const toggleKind = (k: Kind) => setKinds((s) => {
    const n = new Set(s);
    if (n.has(k)) n.delete(k); else n.add(k);
    return n;
  });

  if (slice.nodes.length <= 1) {
    return <p className="empty">Ehhez az entitáshoz a jelenlegi snapshotban nincs megjeleníthető kapcsolat.</p>;
  }

  return (
    <div className="net-shell no-left">
      <div className="net-stage" style={{ display: "flex", flexDirection: "column" }}>
        <div className="ego-toggles" role="group" aria-label="Megjelenített kapcsolattípusok">
          {firstKinds.map((k) => (
            <button key={k} type="button" className="toggle" aria-pressed={kinds.has(k)} onClick={() => toggleKind(k)}>
              <Glyph kind={k} />{KIND_PLURAL[k]} ({slice.nodes.filter((n) => n.hop === 1 && n.kind === k).length})
            </button>
          ))}
          {hasSecond && (
            <button type="button" className="toggle" aria-pressed={second} onClick={() => setSecond((v) => !v)}>
              {secondLabel} ({slice.nodes.filter((n) => n.hop >= 2).length})
            </button>
          )}
          {hasDerived && (
            <button type="button" className="toggle" aria-pressed={derived} onClick={() => setDerived((v) => !v)}>
              Származtatott kapcsolatok
            </button>
          )}
        </div>
        <NetworkCanvas
          nodes={view.nodes} edges={view.edges} positions={view.positions} selected={selected}
          onSelect={setSelected} centerId={centerId} height={height} tabbableNodes={view.nodes.length <= 60}
          labelBudget={40} ariaLabel="Kapcsolatháló a középpontban álló entitás körül"
        />
        <GraphTable nodes={view.nodes} onSelect={setSelected} selected={selected} />
      </div>
      <aside className="net-panel" aria-label="Kiválasztott elem">
        <NodePanel
          node={sel} nodes={view.nodes} edges={view.edges} centerId={centerId} onSelect={setSelected}
          expanded={sel ? expanded.has(sel.id) : false}
          onExpand={hasSecond ? (id) => setExpanded((s) => {
            const n = new Set(s);
            if (n.has(id)) n.delete(id); else n.add(id);
            return n;
          }) : undefined}
        />
        <hr style={{ border: 0, borderTop: "1px solid var(--rule)", margin: "16px 0" }} />
        <Legend kinds={[...new Set(view.nodes.map((n) => n.kind))]} hasDerived={hasDerived} />
      </aside>
    </div>
  );
}
