"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import EntitySearch from "./EntitySearch";

export const NAV: { href: string; label: string; match: string[] }[] = [
  { href: "/explore", label: "Felfedezés", match: ["/explore"] },
  { href: "/people", label: "Kutatók", match: ["/people", "/person"] },
  { href: "/institutions", label: "Intézmények", match: ["/institutions", "/institution"] },
  { href: "/projects", label: "Projektek", match: ["/projects", "/project"] },
  { href: "/topics", label: "Témák és módszerek", match: ["/topics", "/topic", "/method"] },
  { href: "/network", label: "A hálózat", match: ["/network"] },
  { href: "/about/data", label: "Az adatokról", match: ["/about"] },
];

export function Wordmark() {
  return (
    <Link href="/" className="wordmark" aria-label="Magyar Szociológia Atlasz — kezdőlap">
      <svg width="34" height="34" viewBox="0 0 34 34" aria-hidden="true">
        <circle cx="17" cy="17" r="15.5" fill="none" stroke="var(--ink)" strokeWidth="1.2" />
        <path d="M17 1.5 V32.5 M1.5 17 H32.5" stroke="var(--rule-strong)" strokeWidth="0.8" />
        <path d="M10 12 L22 9 L24 21 L13 24 Z" fill="none" stroke="var(--ink-2)" strokeWidth="1" />
        <circle cx="10" cy="12" r="2.6" fill="var(--n-person)" />
        <rect x="19.6" y="6.6" width="4.8" height="4.8" fill="var(--n-project)" />
        <circle cx="24" cy="21" r="2.6" fill="var(--n-person)" />
        <path d="M13 20.6 L16.2 24 L13 27.4 L9.8 24 Z" fill="var(--n-topic)" />
      </svg>
      <span className="name">Magyar Szociológia Atlasz<small>pilot · TK snapshot</small></span>
    </Link>
  );
}

export default function SiteHeader() {
  const path = usePathname() ?? "/";
  const links = NAV.map((n) => (
    <Link key={n.href} href={n.href} aria-current={n.match.some((m) => path === m || path.startsWith(m + "/")) ? "page" : undefined}>
      {n.label}
    </Link>
  ));
  return (
    <header className="site-header">
      <div className="wrap bar">
        <Wordmark />
        <nav className="primary-nav" aria-label="Fő navigáció">{links}</nav>
        <details className="menu-toggle">
          <summary aria-label="Menü megnyitása">Menü</summary>
          <nav className="mobile-nav" aria-label="Fő navigáció (mobil)">{NAV.map((n) => <Link key={n.href} href={n.href}>{n.label}</Link>)}</nav>
        </details>
        <div className="header-search"><EntitySearch /></div>
      </div>
    </header>
  );
}
