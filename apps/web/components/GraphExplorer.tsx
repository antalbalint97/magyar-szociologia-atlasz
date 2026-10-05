"use client";
// Network explorer. The server sends one controlled slice (preset, mode + filter, or focus);
// everything here filters that slice further in the browser and never loads the full release.
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { filterSlice, sliceStats, type GraphSlice } from "@/lib/atlas/network";
import { forceLayout, unpackPositions } from "@/lib/atlas/layout";
import { KIND_PLURAL, REL_GROUP_LABEL, type Kind, type RelGroup } from "@/lib/atlas/vocab";
import EntitySearch from "./EntitySearch";
import { Glyph } from "./Glyph";
import { GraphTable, Legend, NodePanel } from "./GraphParts";
import NetworkCanvas from "./NetworkCanvas";

export interface ExplorerOption {
  value: string;
  label: string;
}

export default function GraphExplorer({
  slice, positions: serverPositions, presets, current, cluster: clusterDefault, title, description, modes, units, terms, query, initialSelected,
}: {
  slice: GraphSlice;
  positions: Record<string, [number, number]>;
  presets: { key: string; title: string }[];
  current: string | null;
  cluster: boolean;
  title: string;
  description: string;
  modes: ExplorerOption[];
  units: ExplorerOption[];
  terms: ExplorerOption[];
  query: { mode: string; unit: string; term: string };
  initialSelected: string | null;
}) {
  const router = useRouter();
  const allKinds = useMemo(() => {
    const order: Kind[] = ["person", "project", "unit", "topic", "method"];
    const ks = new Set(slice.nodes.map((n) => n.kind));
    return order.filter((k) => ks.has(k));
  }, [slice]);
  const allGroups = useMemo(() => [...new Set(slice.edges.map((e) => e.group))] as RelGroup[], [slice]);
  const institutes = useMemo(
    () => [...new Set(slice.nodes.filter((n) => n.kind === "person" || n.kind === "project").map((n) => n.group).filter((g): g is string => Boolean(g)))].sort(),
    [slice]);
  const maxSize = useMemo(() => Math.max(0, ...slice.nodes.map((n) => n.size ?? 0)), [slice]);

  const [kinds, setKinds] = useState<Kind[]>(allKinds);
  const [groups, setGroups] = useState<RelGroup[]>(allGroups);
  const [observedOnly, setObservedOnly] = useState(false);
  const [minDegree, setMinDegree] = useState(1);
  const [sizeCap, setSizeCap] = useState<number | null>(null);
  const [inst, setInst] = useState<string[]>(institutes);
  const [cluster, setCluster] = useState(clusterDefault);
  const [selected, setSelected] = useState<string | null>(initialSelected);
  // on a phone the filters would push the graph far below the fold: start them collapsed there
  const [filtersOpen, setFiltersOpen] = useState(true);
  useEffect(() => {
    if (window.matchMedia("(max-width: 760px)").matches) setFiltersOpen(false);
  }, []);

  useEffect(() => {
    setKinds(allKinds);
    setGroups(allGroups);
    setInst(institutes);
    setCluster(clusterDefault);
    setMinDegree(1);
    setSizeCap(null);
    setObservedOnly(false);
  }, [allKinds, allGroups, institutes, clusterDefault]);

  useEffect(() => setSelected(initialSelected), [initialSelected, slice]);

  const view = useMemo(() => filterSlice(slice, {
    kinds, groups, minDegree, maxProjectSize: sizeCap,
    statuses: observedOnly ? ["OBSERVED"] : ["OBSERVED", "DERIVED"],
    institutes: inst.length === institutes.length ? null : inst,
  }), [slice, kinds, groups, minDegree, sizeCap, observedOnly, inst, institutes.length]);
  const base = useMemo(() => unpackPositions(serverPositions), [serverPositions]);
  // the server layout matches the initial clustering; toggling it lays out the current view anew
  const positions = useMemo(
    () => (cluster === clusterDefault ? base : forceLayout(view.nodes, view.edges, { cluster })),
    [base, cluster, clusterDefault, view]);
  const stats = sliceStats(view);
  const sel = view.nodes.find((n) => n.id === selected) ?? null;
  const centerId = slice.seeds.length === 1 ? slice.seeds[0] : null;

  const select = (id: string | null) => {
    setSelected(id);
    try {
      const u = new URL(window.location.href);
      if (id) u.searchParams.set("sel", id); else u.searchParams.delete("sel");
      window.history.replaceState(null, "", u.toString());
    } catch { /* URL sync is a convenience only */ }
  };

  const flip = <T,>(xs: T[], x: T) => (xs.includes(x) ? xs.filter((y) => y !== x) : [...xs, x]);

  return (
    <div className="net-shell">
      <div className="net-controls">
        <div>
          <div className="legend-title kind" style={{ marginBottom: 6 }}>Kiinduló nézetek</div>
          <nav className="presets" aria-label="Előre beállított nézetek">
            {presets.map((p) => (
              <Link key={p.key} href={`/network?preset=${p.key}`} aria-current={current === p.key ? "true" : undefined}>{p.title}</Link>
            ))}
          </nav>
        </div>
        <div>
          <div className="kind" style={{ marginBottom: 6 }}>Fókusz egy entitásra</div>
          <EntitySearch placeholder="Keresés a hálóban…" onPick={(h) => {
            if (h.mention) return router.push(h.href);
            if (view.nodes.some((n) => n.id === h.id)) select(h.id);
            else router.push(`/network?focus=${h.id}`);
          }} />
        </div>
        <details className="net-filters" open={filtersOpen} onToggle={(e) => setFiltersOpen(e.currentTarget.open)}>
        <summary>Szűrők és saját szelet</summary>
        <div className="net-filters-body">
        <form method="get" action="/network" style={{ display: "grid", gap: 8 }}>
          <div className="kind">Saját szelet</div>
          <label className="vh" htmlFor="mode">Kapcsolattípus</label>
          <select id="mode" name="mode" defaultValue={query.mode}>
            {modes.map((m) => <option key={m.value} value={m.value}>{m.label}</option>)}
          </select>
          <label className="vh" htmlFor="unit">Intézmény</label>
          <select id="unit" name="unit" defaultValue={query.unit}>
            <option value="">Minden intézmény</option>
            {units.map((m) => <option key={m.value} value={m.value}>{m.label}</option>)}
          </select>
          <label className="vh" htmlFor="term">Téma vagy módszer</label>
          <select id="term" name="term" defaultValue={query.term}>
            <option value="">Minden téma és módszer</option>
            {terms.map((m) => <option key={m.value} value={m.value}>{m.label}</option>)}
          </select>
          <button className="btn small ghost" type="submit">Szelet betöltése</button>
        </form>
        <fieldset>
          <legend>Csomópontok</legend>
          {allKinds.map((k) => (
            <label key={k}><input type="checkbox" checked={kinds.includes(k)} onChange={() => setKinds(flip(kinds, k))} /><Glyph kind={k} />{KIND_PLURAL[k]}</label>
          ))}
        </fieldset>
        <fieldset>
          <legend>Kapcsolatok</legend>
          {allGroups.map((g) => (
            <label key={g}><input type="checkbox" checked={groups.includes(g)} onChange={() => setGroups(flip(groups, g))} />{REL_GROUP_LABEL[g]}</label>
          ))}
          {slice.edges.some((e) => e.status !== "OBSERVED") && (
            <label><input type="checkbox" checked={observedOnly} onChange={() => setObservedOnly(!observedOnly)} />Csak megfigyelt kapcsolatok</label>
          )}
        </fieldset>
        {institutes.length > 1 && (
          <fieldset>
            <legend>Intézet (kutatók, projektek)</legend>
            {institutes.map((g) => (
              <label key={g}><input type="checkbox" checked={inst.includes(g)} onChange={() => setInst(flip(inst, g))} />{g}</label>
            ))}
            <label><input type="checkbox" checked={cluster} onChange={() => setCluster(!cluster)} />Csoportosítás intézet szerint</label>
          </fieldset>
        )}
        <fieldset>
          <legend>Szűrők</legend>
          <label style={{ display: "grid", gap: 2 }}>
            <span>Legalább {minDegree} kapcsolat a nézetben</span>
            <input type="range" min={1} max={5} value={minDegree} onChange={(e) => setMinDegree(Number(e.target.value))} aria-label="Minimális kapcsolatszám" />
          </label>
          {maxSize > 5 && (
            <label style={{ display: "grid", gap: 2 }}>
              <span>Projektméret</span>
              <select value={sizeCap ?? ""} onChange={(e) => setSizeCap(e.target.value ? Number(e.target.value) : null)}>
                <option value="">Minden projekt (legnagyobb: {maxSize} fő)</option>
                {[10, 5, 3].filter((x) => x < maxSize).map((x) => <option key={x} value={x}>Legfeljebb {x} résztvevő</option>)}
              </select>
            </label>
          )}
        </fieldset>
        </div>
        </details>
      </div>
      <div className="net-stage" style={{ display: "flex", flexDirection: "column" }}>
        <div style={{ padding: "12px 14px 0" }}>
          <h2 style={{ fontSize: "1.25rem", marginBottom: 4 }}>{title}</h2>
          <p className="muted small" style={{ maxWidth: "70ch", marginBottom: 0 }}>{description}</p>
        </div>
        {view.nodes.length ? (
          <NetworkCanvas
            nodes={view.nodes} edges={view.edges} positions={positions} selected={selected} onSelect={select}
            centerId={centerId} height={620} ariaLabel={`Hálózati nézet: ${title}`} labelBudget={14}
            alwaysLabel={new Set(view.nodes.filter((n) => n.kind === "unit" || (n.seed && view.nodes.length < 140)).map((n) => n.id))}
          />
        ) : (
          <p className="empty" style={{ padding: 16 }}>A szűrők minden csomópontot kizártak. Lazíts a szűrőkön.</p>
        )}
        <p className="muted small" style={{ padding: "0 14px", margin: "4px 0" }}>
          {stats.nodes} csomópont ({allKinds.filter((k) => stats.byKind[k]).map((k) => `${stats.byKind[k]} ${KIND_PLURAL[k].toLowerCase()}`).join(", ")}) · {stats.edges} kapcsolat
          ({stats.observed} megfigyelt{stats.derived ? `, ${stats.derived} származtatott` : ""}). A csomópontok helyzete
          elrendezési algoritmus eredménye, nem földrajzi vagy rangsor-információ; a méret csak projekteknél jelent valamit (résztvevők száma).
        </p>
        <GraphTable nodes={view.nodes} onSelect={select} selected={selected} />
      </div>
      <aside className="net-panel" aria-label="Kiválasztott elem és jelmagyarázat">
        <NodePanel node={sel} nodes={view.nodes} edges={view.edges} centerId={centerId} onSelect={select} />
        <hr style={{ border: 0, borderTop: "1px solid var(--rule)", margin: "16px 0" }} />
        <Legend kinds={allKinds.filter((k) => kinds.includes(k))} hasDerived={view.edges.some((e) => e.status !== "OBSERVED")} />
      </aside>
    </div>
  );
}
