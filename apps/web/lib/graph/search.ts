// Accent-insensitive, typo-tolerant search over entity labels (no dependencies, so the
// same scoring runs in the file backend and in tests). Neo4j uses its fulltext index.

export function fold(s: string): string {
  return s
    .normalize("NFKD")
    .replace(/\p{Mn}/gu, "")
    .toLowerCase()
    .replace(/[^\p{L}\p{N}\s-]/gu, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function trigrams(s: string): Set<string> {
  const p = `  ${s} `;
  const out = new Set<string>();
  for (let i = 0; i < p.length - 2; i++) out.add(p.slice(i, i + 3));
  return out;
}

function similarity(a: string, b: string): number {
  const ta = trigrams(a);
  const tb = trigrams(b);
  let inter = 0;
  for (const t of ta) if (tb.has(t)) inter++;
  return inter / (ta.size + tb.size - inter || 1);
}

/** 0..1 score; 0 means no match. Every query token must hit some name token. */
export function score(query: string, names: string[]): number {
  const q = fold(query);
  if (!q) return 0;
  const qTokens = q.split(" ");
  let best = 0;
  for (const name of names) {
    const n = fold(name);
    if (!n) continue;
    if (n === q) return 1;
    const nTokens = n.split(" ");
    let total = 0;
    let ok = true;
    for (const qt of qTokens) {
      let tokenBest = 0;
      for (const nt of nTokens) {
        if (nt === qt) tokenBest = Math.max(tokenBest, 1);
        else if (nt.startsWith(qt)) tokenBest = Math.max(tokenBest, 0.85);
        else if (qt.length >= 4) {
          const sim = similarity(qt, nt);
          if (sim >= 0.45) tokenBest = Math.max(tokenBest, sim * 0.8);
        }
      }
      if (tokenBest === 0) {
        ok = false;
        break;
      }
      total += tokenBest;
    }
    if (ok) best = Math.max(best, (total / qTokens.length) * (n.includes(q) ? 1 : 0.9));
  }
  return best;
}
