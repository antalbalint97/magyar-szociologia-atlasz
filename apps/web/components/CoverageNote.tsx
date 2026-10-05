import type { Atlas } from "@/lib/atlas/atlas";
import { recensProjectLinks, sziLeadGap } from "@/lib/atlas/notices";
import { hu, percent } from "@/lib/atlas/vocab";

export const ISSUE = (n: number) => `https://github.com/antalbalint97/magyar-szociologia-atlasz/issues/${n}`;

export function IssueLink({ n }: { n: number }) {
  return <a href={ISSUE(n)} rel="noreferrer">#{n}</a>;
}

// Small, contextual: shown only where a source's known asymmetry changes how a page reads.
export function SourceNotes({ a, sources, topic = "projects" }: { a: Atlas; sources: string[]; topic?: "projects" }) {
  const notes: React.ReactNode[] = [];
  if (topic === "projects" && sources.includes("tk_szociologia")) {
    const g = sziLeadGap(a);
    if (g) notes.push(
      <p key="szi" className="note coverage">
        <strong>Ismert hiány (SZI):</strong> ebben a kiadásban az SZI{" "}
        {hu(g.of)} projektjéből {hu(g.n)} ({percent(g.n, g.of)}) megfigyelt projektvezető nélkül szerepel, így az SZI
        projektkapcsolatai alulreprezentáltak. Az SZI projektoldalai a neveket részben címsorok alatt sorolják; ezek
        feldolgozását a <IssueLink n={31} /> tárgyalja.
      </p>,
    );
  }
  if (topic === "projects" && sources.includes("tk_recens")) {
    const r = recensProjectLinks(a);
    if (r) notes.push(
      <p key="recens" className="note coverage">
        <strong>Ismert hiány (CSS-RECENS):</strong> a CSS-RECENS profiljai ritkán hivatkoznak projektoldalra. {" "}
        {hu(r.of)} CSS-RECENS-kutatóból {hu(r.n)} ({percent(r.n, r.of)}) kapcsolódik megfigyelten projekthez; a
        hiányzó kapcsolat nem jelenti, hogy nincs projekt.
      </p>,
    );
  }
  return <>{notes}</>;
}
