import Link from "next/link";
import type { Mention } from "@/lib/graph";
import { OpenBadge } from "./StatusBadge";
import { whyOpen } from "@/lib/atlas/mentionText";
import { IssueLink } from "./CoverageNote";

export default function MentionList({ mentions, limit = 8 }: { mentions: Mention[]; limit?: number }) {
  const item = (m: Mention) => (
    <li key={m.id}>
      <div className="row-title" style={{ fontFamily: "var(--serif)" }}>
        <Link href={`/entity/${m.id}`} style={{ fontWeight: 400, fontStyle: "italic" }}>„{m.statedName}”</Link>
        {m.blockedBy || m.method === "manual:project_deferred" ? (
          <OpenBadge text="elhalasztva" title="Kézi döntés: a tevékenység típusáról előbb egy másik feladatnak kell döntenie." />
        ) : <OpenBadge text={m.status === "REVIEW_REQUIRED" ? "ellenőrzésre vár" : "azonosítatlan"} />}
      </div>
      <div className="row-meta">
        {m.blockedBy && <span>vár: <IssueLink n={Number(m.blockedBy.replace("#", ""))} /> (tevékenységtípus)</span>}
        {m.reason && !m.blockedBy && <span title={m.reason}>{whyOpen(m)}</span>}
        {m.linkedProfileUrl && <span>hivatkozott oldal: <a href={m.linkedProfileUrl} rel="noreferrer">{m.linkedProfileUrl.replace(/^https?:\/\//, "").slice(0, 60)}</a></span>}
      </div>
    </li>
  );
  return (
    <>
      <ul className="rows compact">{mentions.slice(0, limit).map(item)}</ul>
      {mentions.length > limit && (
        <details><summary className="small" style={{ cursor: "pointer" }}>További {mentions.length - limit}</summary>
          <ul className="rows compact">{mentions.slice(limit).map(item)}</ul></details>
      )}
    </>
  );
}
