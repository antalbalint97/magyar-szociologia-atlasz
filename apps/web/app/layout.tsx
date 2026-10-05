import type { Metadata, Viewport } from "next";
import Link from "next/link";
import "@fontsource-variable/inter";
import "@fontsource-variable/source-serif-4";
import SiteHeader from "@/components/SiteHeader";
import { atlas } from "@/lib/atlas/server";
import { SOURCE_LABEL } from "@/lib/atlas/vocab";
import "./globals.css";

export const metadata: Metadata = {
  title: { default: "Magyar Szociológia Atlasz", template: "%s · Magyar Szociológia Atlasz" },
  description:
    "A magyar szociológia intézményeinek, kutatóinak, projektjeinek és tudáskapcsolatainak interaktív, forrásokhoz kötött térképe (pilot).",
};

export const viewport: Viewport = { width: "device-width", initialScale: 1 };
// every page reads the configured release at request time (GRAPH_RELEASE), never at build time
export const dynamic = "force-dynamic";

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  const a = await atlas();
  const { info } = a;
  const labels = info.sources.map((s) => SOURCE_LABEL[s]?.short ?? s);
  return (
    <html lang="hu">
      <body>
        <a href="#main" className="skip">Ugrás a tartalomra</a>
        <SiteHeader />
        {info.kind === "fixture" ? (
          <div className="pilot" role="note"><div className="wrap">
            <strong>Teszt-adatkészlet:</strong> kézzel rekonstruált tesztoldalakból épült, nem élő gyűjtésből. Csak az
            adatmodellt mutatja be, a szakterületről nem állít semmit.
          </div></div>
        ) : (
          <div className="pilot" role="note"><div className="wrap">
            <strong>Pilot adatbázis</strong>
            <span>— jelenleg a TK {info.sources.length} intézményi forrásának ({labels.join(", ")}) snapshotja ({info.generatedAt.slice(0, 10)}), nem a teljes magyar szociológia.</span>
            <Link href="/about/data">Mit tartalmaz?</Link>
          </div></div>
        )}
        <main id="main">{children}</main>
        <footer className="site-footer">
          <div className="wrap cols">
            <div>
              <div style={{ fontFamily: "var(--serif)", color: "var(--ink)", fontSize: "1.05rem" }}>Magyar Szociológia Atlasz</div>
              <div>Forrásokhoz kötött, időben bővíthető tudásgráf. Minden állítás egy letöltött forrásoldalra vezethető vissza.</div>
            </div>
            <div>
              <div>Kiadás: <code>{info.releaseId}</code> · készült {info.generatedAt.slice(0, 10)}</div>
              <div><Link href="/about/data">Módszertan és lefedettség</Link> · <a href="https://github.com/antalbalint97/magyar-szociologia-atlasz" rel="noreferrer">Forráskód</a></div>
            </div>
          </div>
        </footer>
      </body>
    </html>
  );
}
