"use client";
// Global search as an ARIA combobox: type-ahead from /api/search, arrow keys + Enter, Escape
// closes, and the form still works without JavaScript (submits to /search).
import { useRouter } from "next/navigation";
import { Fragment, useEffect, useId, useRef, useState } from "react";
import type { SearchHit } from "@/lib/atlas/search";
import { KIND_OF } from "@/lib/atlas/vocab";
import { Glyph } from "./Glyph";

export default function EntitySearch({ big = false, placeholder, autoFocus = false, onPick }: {
  big?: boolean;
  placeholder?: string;
  autoFocus?: boolean;
  onPick?: (hit: SearchHit) => void; // when set (graph focus), picking does not navigate
}) {
  const router = useRouter();
  const id = useId();
  const [q, setQ] = useState("");
  const [hits, setHits] = useState<SearchHit[]>([]);
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(-1);
  const box = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const term = q.trim();
    if (term.length < 2) {
      setHits([]);
      return;
    }
    const ctl = new AbortController();
    const t = setTimeout(() => {
      fetch(`/api/search?q=${encodeURIComponent(term)}`, { signal: ctl.signal })
        .then((r) => r.json())
        .then((d: { hits: SearchHit[] }) => {
          setHits(d.hits);
          setActive(-1);
          setOpen(true);
        })
        .catch(() => {});
    }, 120);
    return () => {
      clearTimeout(t);
      ctl.abort();
    };
  }, [q]);

  useEffect(() => {
    const close = (e: MouseEvent) => {
      if (box.current && !box.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, []);

  const pick = (h: SearchHit) => {
    setOpen(false);
    if (onPick) {
      onPick(h);
      setQ("");
    } else router.push(h.href);
  };

  const canonical = hits.filter((h) => !h.mention);
  const mentions = hits.filter((h) => h.mention);
  const ordered = [...canonical, ...mentions];
  const showList = open && q.trim().length >= 2;

  return (
    <div className={`search${big ? " big" : ""}`} ref={box}>
      <form action="/search" method="get" role="search" onSubmit={(e) => {
        if (active >= 0 && ordered[active]) {
          e.preventDefault();
          pick(ordered[active]);
        } else if (onPick) e.preventDefault();
      }}>
        <svg className="icon" width="16" height="16" viewBox="0 0 16 16" aria-hidden="true">
          <circle cx="7" cy="7" r="5" fill="none" stroke="currentColor" strokeWidth="1.6" />
          <path d="M11 11 L14.5 14.5" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
        </svg>
        <input
          name="q" value={q} autoComplete="off" autoFocus={autoFocus}
          placeholder={placeholder ?? "Kutató, intézmény, projekt, téma…"}
          aria-label="Keresés az atlaszban" role="combobox" aria-expanded={showList}
          aria-controls={`${id}-list`} aria-autocomplete="list"
          aria-activedescendant={active >= 0 ? `${id}-o${active}` : undefined}
          onChange={(e) => setQ(e.target.value)}
          onFocus={() => hits.length && setOpen(true)}
          onKeyDown={(e) => {
            if (e.key === "ArrowDown") {
              e.preventDefault();
              setOpen(true);
              setActive((a) => Math.min(a + 1, ordered.length - 1));
            } else if (e.key === "ArrowUp") {
              e.preventDefault();
              setActive((a) => Math.max(a - 1, -1));
            } else if (e.key === "Escape") setOpen(false);
          }}
        />
      </form>
      {showList && (
        <div className="search-pop">
          <ul id={`${id}-list`} role="listbox" aria-label="Találatok">
            {ordered.length === 0 && <li className="sep" role="presentation">Nincs találat a jelenlegi snapshotban.</li>}
            {ordered.map((h, i) => {
              const kind = KIND_OF[h.type];
              return (
                <Fragment key={h.id}>
                  {i === canonical.length && (
                    <li className="sep" role="presentation">Azonosítatlan említések — nem kutatók és nem projektek</li>
                  )}
                  <li id={`${id}-o${i}`} role="option" aria-selected={i === active}
                    onMouseEnter={() => setActive(i)} onMouseDown={(e) => { e.preventDefault(); pick(h); }}>
                    {kind ? <Glyph kind={kind} /> : <span aria-hidden="true" style={{ width: 12, flex: "none", borderBottom: "1px dotted var(--open)" }} />}
                    <span className="lbl">{h.label}{h.sub ? <span className="muted"> · {h.sub}</span> : null}</span>
                    <span className={h.mention ? "badge open" : "kind"} style={h.mention ? undefined : { textTransform: "none", letterSpacing: 0 }}>
                      {h.typeLabel}{h.context ? ` · ${h.context}` : ""}
                    </span>
                  </li>
                </Fragment>
              );
            })}
          </ul>
          {!onPick && (
            <div className="all"><a href={`/search?q=${encodeURIComponent(q)}`}>Összes találat: „{q}”</a></div>
          )}
        </div>
      )}
    </div>
  );
}
