"use client";
// Legend, detail panel and table view shared by the explorer and the ego networks.
import Link from "next/link";
import { useEffect, useState } from "react";
import type { GEdge, GNode } from "@/lib/atlas/network";
import { KIND_COLOR, shapePath } from "@/lib/atlas/shapes";
import { KIND_LABEL, REL_LABEL, STATUS_SHORT, type Kind } from "@/lib/atlas/vocab";
import { Glyph } from "./Glyph";

export function Legend({ kinds, hasDerived = true, note }: { kinds: Kind[]; hasDerived?: boolean; note?: string }) {
  const order: Kind[] = ["person", "project", "unit", "topic", "method"];
  return (
    <div className="legend" aria-label="Jelmagyarázat">
      {order.filter((k) => kinds.includes(k)).map((k) => (
        <div className="item" key={k}><Glyph kind={k} size={14} />{KIND_LABEL[k]}{k === "project" ? " (méret = résztvevők)" : ""}</div>
      ))}
      <div className="item">
        <svg width="28" height="10" aria-hidden="true"><line x1="0" y1="5" x2="28" y2="5" stroke="var(--observed)" strokeWidth="1.4" /></svg>
        Megfigyelt kapcsolat
      </div>
      <div className="item">
        <svg width="28" height="10" aria-hidden="true"><line x1="0" y1="5" x2="28" y2="5" stroke="var(--observed)" strokeWidth="2.6" /></svg>
        Projektvezetés (megfigyelt)
      </div>
      {hasDerived && (
        <div className="item">
          <svg width="28" height="10" aria-hidden="true"><line x1="0" y1="5" x2="28" y2="5" stroke="var(--derived)" strokeWidth="1.4" strokeDasharray="4 3" /></svg>
          Származtatott (kulcsszó-szabály)
        </div>
      )}
      {note && <div className="muted" style={{ marginTop: 4 }}>{note}</div>}
    </div>
  );
}

interface EvidenceResponse {
  relations: { id: string; type: string; status: string; derivationMethod: string | null; qualifiers: Record<string, unknown[]> }[];
  evidence: { claimId: string; snippet: string; url: string; retrievedAt: string; predicate: string }[];
}

function WhyButton({ edge }: { edge: GEdge }) {
  const [data, setData] = useState<EvidenceResponse | null>(null);
  const [open, setOpen] = useState(false);
  useEffect(() => {
    setData(null);
    setOpen(false);
  }, [edge.id]);
  return (
    <>
      <button type="button" className="toggle" style={{ padding: "1px 8px", fontSize: "0.78rem" }} aria-expanded={open}
        onClick={() => {
          setOpen((o) => !o);
          if (!data) fetch(`/api/evidence?rel=${edge.relationIds.join(",")}`).then((r) => r.json()).then(setData).catch(() => {});
        }}>
        Miért?
      </button>
      {open && (
        <div className="evidence-body" style={{ marginTop: 6 }}>
          {!data && <span className="muted">Forrás betöltése…</span>}
          {data && data.relations.some((r) => r.status !== "OBSERVED") && (
            <p className="small muted">
              Kulcsszó-szabály (<code>{data.relations.find((r) => r.derivationMethod)?.derivationMethod}</code>) a forrás szövegéből:
              {" "}„{[...new Set(data.relations.flatMap((r) => (r.qualifiers.stated_text as string[]) ?? []))].join("; ")}”
            </p>
          )}
          {data && [...new Map(data.evidence.map((e) => [e.url, e])).values()].slice(0, 3).map((ev) => (
            <div key={ev.claimId} style={{ marginBottom: 6 }}>
              {ev.url.startsWith("http") ? <a href={ev.url} rel="noreferrer" className="src">{ev.url.replace(/^https?:\/\//, "")}</a> : <code>{ev.url}</code>}
              <div className="muted small">letöltve {ev.retrievedAt.slice(0, 10)}</div>
              {ev.snippet && <blockquote>„{ev.snippet.length > 220 ? ev.snippet.slice(0, 219) + "…" : ev.snippet}”</blockquote>}
            </div>
          ))}
        </div>
      )}
    </>
  );
}

export function NodePanel({ node, nodes, edges, centerId, onSelect, onExpand, expanded }: {
  node: GNode | null;
  nodes: GNode[];
  edges: GEdge[];
  centerId?: string | null;
  onSelect: (id: string | null) => void;
  onExpand?: (id: string) => void;
  expanded?: boolean;
}) {
  if (!node) {
    return (
      <div className="muted small">
        <p>Válassz ki egy csomópontot kattintással, vagy a lenti táblázatos nézetből billentyűzettel.</p>
        <p>A kiválasztott elem kapcsolatai kiemelődnek, a többi elhalványul. Minden kapcsolatnál megnézheted, melyik forrásoldal állítja.</p>
      </div>
    );
  }
  const byId = new Map(nodes.map((n) => [n.id, n]));
  const rel = edges.filter((e) => e.source === node.id || e.target === node.id);
  const toCenter = centerId && centerId !== node.id ? rel.filter((e) => e.source === centerId || e.target === centerId) : [];
  const others = rel.filter((e) => !toCenter.includes(e));
  const m = node.meta;
  return (
    <div>
      <span className="kind"><Glyph kind={node.kind} />{KIND_LABEL[node.kind]}{node.group ? ` · ${node.group}` : ""}</span>
      <h3>{node.label}</h3>
      {node.sub && <div className="muted small" style={{ marginTop: -4, marginBottom: 6 }}>{node.sub}</div>}
      <dl className="kv small" style={{ marginBottom: 12 }}>
        {m.units && m.units.length > 0 && (<><dt>{node.kind === "project" ? "Befogadó" : node.kind === "unit" ? "Része" : "Egység"}</dt><dd>{m.units.join("; ")}</dd></>)}
        {node.kind === "project" && (<><dt>Méret</dt><dd>{node.size} azonosított kutató</dd></>)}
        {m.years && (<><dt>Időszak</dt><dd>{m.years}</dd></>)}
        {m.status && (<><dt>Státusz</dt><dd>{m.status}</dd></>)}
        {m.terms && m.terms.length > 0 && (<><dt>Témák</dt><dd>{m.terms.join(", ")} <span className="badge derived">származtatott</span></dd></>)}
        <dt>Kapcsolat a nézetben</dt><dd>{rel.length}</dd>
      </dl>
      <p style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
        <Link className="btn small primary" href={node.href}>Teljes oldal</Link>
        {onExpand && node.kind === "project" && (
          <button type="button" className="btn small ghost" onClick={() => onExpand(node.id)} aria-pressed={expanded}>
            {expanded ? "Résztvevők elrejtése" : "Résztvevők megjelenítése"}
          </button>
        )}
      </p>
      {toCenter.length > 0 && (
        <>
          <h4 className="small" style={{ margin: "12px 0 4px" }}>Kapcsolat a középponttal</h4>
          <RelList edges={toCenter} self={node.id} byId={byId} onSelect={onSelect} />
        </>
      )}
      {others.length > 0 && (
        <>
          <h4 className="small" style={{ margin: "12px 0 4px" }}>Kapcsolatok ebben a nézetben ({others.length})</h4>
          <RelList edges={others.slice(0, 40)} self={node.id} byId={byId} onSelect={onSelect} />
          {others.length > 40 && <p className="muted small">…és további {others.length - 40}. A teljes lista az oldalán.</p>}
        </>
      )}
    </div>
  );
}

function RelList({ edges, self, byId, onSelect }: {
  edges: GEdge[]; self: string; byId: Map<string, GNode>; onSelect: (id: string) => void;
}) {
  return (
    <ul className="rows compact">
      {edges.map((e) => {
        const other = byId.get(e.source === self ? e.target : e.source);
        if (!other) return null;
        return (
          <li key={e.id}>
            <div className="row-title" style={{ gap: 6 }}>
              <Glyph kind={other.kind} />
              <button type="button" onClick={() => onSelect(other.id)}
                style={{ all: "unset", cursor: "pointer", fontWeight: 500, textDecoration: "underline", textDecorationColor: "var(--rule-strong)", overflowWrap: "anywhere" }}>
                {other.label}
              </button>
            </div>
            <div className="row-meta">
              <span>{e.types.map((t) => REL_LABEL[t] ?? t).join(" + ")}</span>
              <span className={`badge ${e.status === "OBSERVED" ? "observed" : "derived"}`}>{STATUS_SHORT[e.status]}</span>
              <WhyButton edge={e} />
            </div>
          </li>
        );
      })}
    </ul>
  );
}

export function GraphTable({ nodes, onSelect, selected }: { nodes: GNode[]; onSelect: (id: string) => void; selected: string | null }) {
  const sorted = [...nodes].sort((a, b) => a.kind.localeCompare(b.kind) || a.label.localeCompare(b.label, "hu"));
  return (
    <details className="graph-table">
      <summary>Táblázatos nézet ({nodes.length} csomópont) — billentyűzettel is kiválasztható</summary>
      <div className="table-scroll">
        <table className="data">
          <thead><tr><th>Név</th><th>Típus</th><th className="r">Kapcsolat</th></tr></thead>
          <tbody>
            {sorted.map((n) => (
              <tr key={n.id}>
                <td>
                  <button type="button" onClick={() => onSelect(n.id)} aria-pressed={n.id === selected}
                    style={{ all: "unset", cursor: "pointer", textDecoration: "underline", textDecorationColor: "var(--rule-strong)" }}>
                    {n.label}
                  </button>
                </td>
                <td><span className="kind" style={{ textTransform: "none", letterSpacing: 0 }}><Glyph kind={n.kind} />{KIND_LABEL[n.kind]}</span></td>
                <td className="r">{n.degree}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </details>
  );
}

export function MiniShape({ kind, r = 5 }: { kind: Kind; r?: number }) {
  return <path d={shapePath(kind, r)} fill={KIND_COLOR[kind]} />;
}
