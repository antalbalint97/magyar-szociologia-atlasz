// Plain-Hungarian reading of why a mention stays open. The resolver's own reason string is
// kept verbatim next to it (title / mention page); this only translates its leading clause.
import type { Mention } from "../graph/types.ts";

const RULES: [RegExp, string][] = [
  [/^deferred, blocked by/, "Elhalasztva: a tevékenység típusáról előbb dönteni kell"],
  [/not followed \(external_host\)/, "Külső honlapra hivatkozik, amelyet az atlasz nem gyűjt"],
  [/not followed \(source_not_enabled\)/, "Másik TK-egység oldalára hivatkozik (még nem gyűjtött forrás)"],
  [/not followed \(site_not_registered\)/, "Nem nyilvántartott oldalra hivatkozik"],
  [/not on the crawl frontier/, "A hivatkozott oldal nem projektoldal"],
  [/^no anchored Project/, "Nincs hozzá projektoldal vagy egyező pályázati azonosító"],
  [/^title evidence only/, "Csak címegyezés van: ellenőrzésre vár"],
  [/^no canonical Person/, "Nincs ilyen azonosított kutató (pl. volt munkatárs vagy külső partner)"],
  [/^no rule satisfied/, "Van névegyezés, de nincs elég független bizonyíték: ellenőrzésre vár"],
  [/LINK_NAME_MISMATCH/, "A hivatkozott profil és a név ellentmond egymásnak"],
  [/weak name evidence/, "Csak gyenge névegyezés (sorrend vagy kezdőbetű)"],
];

export function whyOpen(m: Mention): string | null {
  if (!m.reason) return null;
  for (const [re, text] of RULES) if (re.test(m.reason)) return text;
  return m.reason;
}
