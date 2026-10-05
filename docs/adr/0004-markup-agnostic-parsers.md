# ADR-0004: Parsers rely on labels, headings and URL patterns, not CSS classes

Status: accepted (2026-10-04)

Context: TK sites have moved hosts at least twice (tk.mta.hu → tk.hu → tk.elte.hu) and
the build environment could not capture raw HTML, only text renderings.

Decision: parse by `<h1>`, labelled fields, section headings and URL patterns; keep
fixtures marked `reconstructed` until replaced by captured snapshots
(`szocatlas fixtures capture`).

Consequences: + robust to redesigns; + testable now. − Some fields that exist only as
styled spans may be missed; the first live run must be followed by capturing real
fixtures and re-running the tests.
