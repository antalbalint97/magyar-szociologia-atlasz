// One row per source: a bar for n/of with the numbers printed next to it (never the bar alone).
import type { SourceMetric } from "@/lib/atlas/coverage";
import { hu, percent } from "@/lib/atlas/vocab";

const SEG_CLASS: Record<string, string> = {
  DETERMINISTIC: "s-det", MANUAL_CONFIRMED: "s-man", HIGH_CONFIDENCE_AUTO: "s-auto", REVIEW_REQUIRED: "s-rev", UNRESOLVED: "s-un",
};

export function Ratio({ n, of }: { n: number; of: number }) {
  return <span className="num">{hu(n)} / {hu(of)} <small>({percent(n, of)})</small></span>;
}

export default function CoverageMeter({ rows, segmented = false, caption }: { rows: SourceMetric[]; segmented?: boolean; caption: string }) {
  const keys = segmented ? [...new Set(rows.flatMap((r) => (r.parts ?? []).map((p) => p.key)))] : [];
  return (
    <figure style={{ margin: 0 }}>
      <figcaption className="small muted" style={{ marginBottom: 6 }}>{caption}</figcaption>
      {rows.map((r) => (
        <div key={r.source} className="meter" role="img"
          aria-label={`${r.label}: ${r.value.n} a ${r.value.of}-ból/-ből (${percent(r.value.n, r.value.of)})`}>
          <span>{r.label}</span>
          <span className="track" aria-hidden="true">
            {segmented && r.parts
              ? r.parts.filter((p) => p.key !== "UNRESOLVED").map((p) => (
                  <span key={p.key} className={`seg ${SEG_CLASS[p.key] ?? ""}`} style={{ width: `${(100 * p.n) / Math.max(r.value.of, 1)}%` }} title={`${p.label}: ${p.n}`} />
                ))
              : <span className="fill" style={{ width: `${(100 * r.value.n) / Math.max(r.value.of, 1)}%` }} />}
          </span>
          <span className="val"><Ratio n={r.value.n} of={r.value.of} /></span>
        </div>
      ))}
      {segmented && (
        <div className="seg-legend">
          {keys.map((k) => {
            const label = rows.flatMap((r) => r.parts ?? []).find((p) => p.key === k)?.label ?? k;
            return <span key={k}><i className={`swatch ${SEG_CLASS[k] ?? ""}`} aria-hidden="true" />{label}</span>;
          })}
        </div>
      )}
      {segmented && (
        <details className="evidence">
          <summary>Táblázatként</summary>
          <div className="table-scroll">
            <table className="data">
              <thead><tr><th>Forrás</th>{keys.map((k) => <th key={k} className="r">{rows.flatMap((r) => r.parts ?? []).find((p) => p.key === k)?.label}</th>)}<th className="r">Összesen</th></tr></thead>
              <tbody>{rows.map((r) => (
                <tr key={r.source}><td>{r.label}</td>{keys.map((k) => <td key={k} className="r">{r.parts?.find((p) => p.key === k)?.n ?? 0}</td>)}<td className="r">{r.value.of}</td></tr>
              ))}</tbody>
            </table>
          </div>
        </details>
      )}
    </figure>
  );
}
