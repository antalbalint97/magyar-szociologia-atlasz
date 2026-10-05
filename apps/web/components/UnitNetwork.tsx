"use client";
// Small force-layout view used inside unit pages (members ↔ projects of one unit).
import { useMemo, useState } from "react";
import type { GraphSlice } from "@/lib/atlas/network";
import { forceLayout } from "@/lib/atlas/layout";
import { GraphTable, Legend, NodePanel } from "./GraphParts";
import NetworkCanvas from "./NetworkCanvas";

export default function UnitNetwork({ slice }: { slice: GraphSlice }) {
  const [selected, setSelected] = useState<string | null>(null);
  const positions = useMemo(() => forceLayout(slice.nodes, slice.edges), [slice]);
  const sel = slice.nodes.find((n) => n.id === selected) ?? null;
  return (
    <div className="net-shell no-left">
      <div className="net-stage">
        <NetworkCanvas nodes={slice.nodes} edges={slice.edges} positions={positions} selected={selected}
          onSelect={setSelected} height={560} ariaLabel="Az egység munkatársai és projektjei" labelBudget={12} />
        <GraphTable nodes={slice.nodes} onSelect={setSelected} selected={selected} />
      </div>
      <aside className="net-panel">
        <NodePanel node={sel} nodes={slice.nodes} edges={slice.edges} onSelect={setSelected} />
        <hr style={{ border: 0, borderTop: "1px solid var(--rule)", margin: "16px 0" }} />
        <Legend kinds={[...new Set(slice.nodes.map((n) => n.kind))]} hasDerived={false} />
      </aside>
    </div>
  );
}
