# Project status

High-level snapshot of the research and engineering state. **GitHub Issues are the source
of truth for actionable work**; this page links to them and does not duplicate them.
Last updated: 2026-10-04.

## Current release

`2026-10-tk` (snapshot, schema 0.1.0, TK parser tk/0.2.0, taxonomy keyword map 0.1.0),
retrieved 2026-10-04 from four TK sites: Szociológiai Intézet, CSS-RECENS,
Kisebbségkutató Intézet, Politikatudományi Intézet. Not in git (docs/architecture.md);
shared with the project as a tarball plus its quality report.

Raw and canonical counts are reported side by side. Until #4 lands, the release only has
raw counts, so the "canonical" column below is what we can say today, not a measured
canonical count.

| | Raw / observed | What is canonical today |
|---|---|---|
| Documents | 509 | |
| Claims | 9,188 | |
| Person-like records | 364 | 161 profiled researchers; 203 records without a profile (name mentions), many of them duplicates of profiled people |
| Project-like records | 646 | 318 backed by a project page; 325 only a title on a profile (≥24 are headings, roles or years, #8); 9 duplicate-title groups; 1 known false merge |
| Units | 39 | |
| Topics / methods | 34 / 19 | 602 topic and 85 method edges, all keyword-derived (DERIVED) |
| Relations | 1,559 OBSERVED, 687 DERIVED | |
| QA | 0 errors, 46 warnings | 242 same-name pairs await review; 76 names carry more than one id |

**0 QA errors means pipeline correctness, not coverage.** The QA seed Virág Tünde is
absent (#13), and fetch, parse, field and taxonomy coverage are not measured yet (#12).
**The release is not ready for network analysis** (#17): person and project duplicates
would bias centrality, brokerage and community results.

## Current milestone

**Milestone 2: Canonicalization & Coverage** (tracking issue #3). It turns the TK
crawl into a trustworthy canonical graph before more institutions are added.

## Completed capabilities (Milestone 1, PRs #1 and #2, not merged yet)

- Claims as the unit of storage, with provenance to content-addressed raw snapshots.
- Polite fetcher (robots.txt, delays, retries/backoff, replay).
- TK shared-CMS adapter fitted to the real markup (profiles, listings, units, projects).
- Conservative person resolution: MTMT/ORCID merges, same-name pairs go to review,
  manual overrides, persistent canonical ids.
- Release builder with a manifest and QA report; idempotent Neo4j loader; Next.js
  explorer that separates observed from derived edges.
- Source inventory for 13 more institutions (docs/sources.md), all disabled.

## Known blockers

- **Identity**: mentions and researchers share the `Person` type (#4); evidence-based
  resolution is missing (#5).
- **Projects**: profile titles do not resolve to project pages (#7); the parser emits
  pseudo-projects (#8).
- **Unreachable hosts** from the crawl environment: doktori.hu, web.archive.org, tk.hu,
  tk.mta.hu, `*.tk.hun-ren.hu`, socio.mta.hu, rki.krtk.hu. Their aliases are inferred
  (#14).
- **doktori.hu** disallows AI crawlers; access route needs a decision (#22).

## Open high-priority issues

#4 Person mention vs canonical Person · #5 Evidence-based person resolution ·
#7 ProjectMention vs canonical Project · #8 Pseudo-projects from profile parser ·
#12 Source coverage QA

## Next

- Implementation: #4 (person mention model ADR and migration), then #5.
- Expansion target after Milestone 2: KRTK Regionális Kutatások Intézete, then TÁRKI (#21).

## Future milestones

- Milestone 3: contemporary Hungarian sociology coverage (#21).
- Milestone 4: publications and academic genealogy (#22, #23).
- Milestone 5: historical sociology atlas (#24).
