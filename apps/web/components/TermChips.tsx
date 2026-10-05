import Link from "next/link";
import type { TermLink } from "@/lib/atlas/profiles";
import { hrefFor } from "@/lib/atlas/vocab";

// Derived taxonomy links: dashed chips; the source text the rule matched is in the tooltip
// and in the list below the chips, so a derived topic never looks like a stated one.
export default function TermChips({ links, showText = true, chips = true }: { links: TermLink[]; showText?: boolean; chips?: boolean }) {
  return (
    <>
      {chips && <div className="chips">
        {links.map((l) => (
          <Link key={l.node.id} className="chip derived" href={hrefFor(l.node.id, l.node.type)}
            title={`Származtatott: „${l.statedText.join("; ")}” (${l.derivation ?? "szabály"})`}>
            {l.node.label}
          </Link>
        ))}
      </div>}
      {showText && links.length > 0 && (
        <details className="evidence">
          <summary>Miből származtattuk?</summary>
          <div className="evidence-body">
            <ul className="rows compact">
              {links.map((l) => (
                <li key={l.node.id}>
                  <strong>{l.node.label}</strong> ← „{l.statedText.join("; ")}”
                  <span className="muted small"> · minta: {l.patterns.map((p) => <code key={p} style={{ marginRight: 4 }}>{p}</code>)} · {l.derivation}</span>
                </li>
              ))}
            </ul>
          </div>
        </details>
      )}
    </>
  );
}
