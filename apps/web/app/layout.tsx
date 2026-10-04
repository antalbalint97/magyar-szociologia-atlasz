import type { Metadata } from "next";
import Link from "next/link";
import { graph } from "@/lib/graph";
import "./globals.css";

export const metadata: Metadata = {
  title: "Magyar Szociológia Atlasz",
  description: "A provenance-aware knowledge graph of Hungarian sociology",
};

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  const release = await graph().release();
  return (
    <html lang="hu">
      <body>
        <header className="site">
          <div className="inner">
            <Link href="/" className="brand">Magyar Szociológia Atlasz</Link>
            <form className="search" action="/" method="get">
              <input name="q" placeholder="Személy, intézmény, téma, módszer… (pl. koltai, hálózatelemzés)" aria-label="Keresés" />
              <button type="submit">Keresés</button>
            </form>
            <span className="muted" style={{ fontSize: 13 }}>release {release.releaseId}</span>
          </div>
        </header>
        {release.kind === "fixture" && (
          <div className="banner">
            Fixture dataset: built from hand-reconstructed test pages, not from a live crawl. It demonstrates the
            data model only and is not a statement about the field.
          </div>
        )}
        <main>{children}</main>
      </body>
    </html>
  );
}
