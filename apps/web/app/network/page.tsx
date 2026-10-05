import type { Metadata } from "next";
import GraphExplorer from "@/components/GraphExplorer";
import { coveredUnits } from "@/lib/atlas/directory";
import { MODES, buildSlice, focusSpec, presets, type SliceSpec } from "@/lib/atlas/network";
import { atlas, memo } from "@/lib/atlas/server";
import { forceLayout, packPositions } from "@/lib/atlas/layout";
import { KIND_LABEL } from "@/lib/atlas/vocab";

export const metadata: Metadata = { title: "A hálózat" };

type SP = Promise<{ preset?: string; focus?: string; mode?: string; unit?: string; term?: string; sel?: string }>;

export default async function NetworkPage({ searchParams }: { searchParams: SP }) {
  const sp = await searchParams;
  const a = await atlas();
  const ps = presets(a);
  let spec: SliceSpec;
  let title: string;
  let description: string;
  let cluster = true;
  let current: string | null = null;
  const focus = sp.focus ? a.node(sp.focus) : undefined;
  if (focus) {
    spec = focusSpec(a, focus.id)!;
    title = `${focus.label} kapcsolatai`;
    description = `Fókusz egy ${KIND_LABEL[focus.kind].toLowerCase()} körül: közvetlen kapcsolatai és egy további lépés a projekteken vagy egységeken át.`;
    cluster = focus.kind === "topic" || focus.kind === "method";
  } else if (sp.mode && MODES[sp.mode]) {
    const unit = sp.unit ? a.node(sp.unit) : undefined;
    const term = sp.term ? a.node(sp.term) : undefined;
    spec = { relations: MODES[sp.mode].relations, unit: unit?.id, term: term?.id };
    title = MODES[sp.mode].label + [unit?.label, term?.label].filter(Boolean).map((x) => ` · ${x}`).join("");
    description = "Saját szelet: a választott kapcsolattípus minden megfigyelt vagy származtatott kapcsolata, a szűrt intézményhez vagy témához kötött kutatók és projektek körül.";
  } else {
    const p = ps.find((x) => x.key === sp.preset) ?? ps[0];
    spec = p.spec;
    title = p.title;
    description = p.description;
    cluster = p.cluster;
    current = p.key;
  }
  const t0 = performance.now();
  const slice = buildSlice(a, spec);
  const ms = performance.now() - t0;
  // the layout is computed once per slice on the server; filtering in the browser reuses it,
  // so nodes keep their place while the reader narrows the view
  const key = `${a.info.releaseId}:${JSON.stringify(spec)}:${cluster}`;
  const positions = memo(key, () => packPositions(forceLayout(slice.nodes, slice.edges, { cluster })));
  const terms = [...a.ofKind("topic"), ...a.ofKind("method")].sort((x, y) => x.label.localeCompare(y.label, "hu"));
  return (
    <div className="page" style={{ paddingTop: 24 }}>
      <div className="wrap" style={{ maxWidth: 1480 }}>
        <div className="eyebrow">A hálózat</div>
        <h1 style={{ fontSize: "2rem", marginBottom: 6 }}>Hálózati felfedező</h1>
        <p className="muted" style={{ maxWidth: "85ch" }}>
          Mindig egy szeletből indulunk, sosem a teljes gráfból. A pozíciók elrendezési algoritmusból adódnak; közelség és
          kapcsolatszám nem jelent fontosságot. Az SZI projektjeinél a vezetők és résztvevők egy része még hiányzik (#31),
          a CSS-RECENS profiljai ritkán hivatkoznak projektre — ezek a szeletek alakját is befolyásolják.
        </p>
        <GraphExplorer
          slice={slice} positions={positions} presets={ps.map((p) => ({ key: p.key, title: p.title }))} current={current} cluster={cluster}
          title={title} description={description}
          modes={Object.entries(MODES).map(([value, m]) => ({ value, label: m.label }))}
          units={coveredUnits(a).map((u) => ({ value: u.id, label: u.label }))}
          terms={terms.map((t) => ({ value: t.id, label: t.label + (t.kind === "method" ? " (módszer)" : "") }))}
          query={{ mode: sp.mode ?? "person-project", unit: sp.unit ?? "", term: sp.term ?? "" }}
          initialSelected={sp.sel && slice.nodes.some((n) => n.id === sp.sel) ? sp.sel : focus?.id ?? null}
        />
        <p className="muted small" style={{ marginTop: 8 }}>Szelet összeállítása a szerveren: {ms.toFixed(1)} ms · kiadás {a.info.releaseId}</p>
      </div>
    </div>
  );
}
