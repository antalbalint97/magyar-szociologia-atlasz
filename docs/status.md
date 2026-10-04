# Project status

High-level snapshot of the research and engineering state. **GitHub Issues are the source
of truth for actionable work**; this page links to them and does not duplicate them.
Last updated: 2026-10-04.

## Current release

`2026-10-tk-r2` (snapshot, schema 0.1.0, TK parser **tk/0.2.2**, taxonomy keyword map
0.1.0), a deterministic rebuild of the four TK sites (Szociológiai Intézet, CSS-RECENS,
Kisebbségkutató Intézet, Politikatudományi Intézet) from a fresh crawl on 2026-10-04.
The same snapshots replayed with tk/0.2.0 reproduce the original `2026-10-tk` exactly
(509 documents, 9,188 claims, 646 projects). Releases are not in git
(docs/architecture.md); they are shared as tarballs with their quality reports.

Raw and canonical counts, side by side. The "PersonMention model" column is the same
snapshot built on the Milestone 2 branch (#4, ADR-0006); it is not a published release yet.

| | `2026-10-tk-r2` (Milestone 1 model) | PersonMention model (#4) |
|---|---|---|
| Documents / claims | 509 / 9,063 | 509 / 9,063 |
| Person-like source records | 364 | 364 |
| Canonical Persons | 364 (161 profiled, 203 name strings) | **161**, all with an institutional profile; 134 with MTMT, 1 with ORCID |
| Person mentions (outside own profile) | n/a | 1,021: 682 resolved (profile URL), **339 unresolved** (203 records, 132 distinct names) |
| Projects | 606 (315 page-backed, 291 profile titles only) | 606 |
| Relations | 2,209 | 1,969; 748 claims about unresolved mentions wait for #5 |
| QA | 0 errors, 46 warnings, 191 orphan persons, 3 "suspicious merges" | 0 errors, 43 warnings, 0 orphan persons, 0 suspicious merges (3 name-variant infos) |

**0 QA errors means pipeline correctness, not coverage.** The QA seed Virág Tünde is
absent (#13), and fetch, parse, field and taxonomy coverage are not measured yet (#12).
**The data is not ready for network analysis** (#17): until #5, participation stated
only through unlinked names or links to unfetched profiles is missing from the analytical
graph (Ságvári Bence: 2 resolved, 14 unresolved mentions), and profile titles do not yet
resolve to project pages (#7; 6 title-collision groups, 1 known edition false merge).

## Current milestone

**Milestone 2: Canonicalization & Coverage** (tracking issue #3). It turns the TK
crawl into a trustworthy canonical graph before more institutions are added.

## Completed capabilities (Milestone 1, PRs #1 and #2, not merged yet; #8 fixed inside #2)

- Claims as the unit of storage, with provenance to content-addressed raw snapshots.
- Polite fetcher (robots.txt, delays, retries/backoff, replay).
- TK shared-CMS adapter fitted to the real markup (profiles, listings, units, projects).
- Conservative person resolution: MTMT/ORCID merges, same-name pairs go to review,
  manual overrides, persistent canonical ids.
- Release builder with a manifest and QA report; idempotent Neo4j loader; Next.js
  explorer that separates observed from derived edges.
- Source inventory for 13 more institutions (docs/sources.md), all disabled.

## Known blockers

- **Identity**: #4 separates mentions from Persons (Milestone 2 branch, not merged);
  evidence-based mention resolution is missing (#5). Two TK profiles of the same person
  on different TK sites (Stefkovics Ádám) stay separate Persons until #5.
- **Projects**: profile titles do not resolve to project pages (#7). Pseudo-projects
  from profile metadata lines are fixed in PR #2 (#8, tk/0.2.2); many profile titles
  still carry role or grant suffixes ("… – Kutató"), which #7 must normalise.
- **Unreachable hosts** from the crawl environment: doktori.hu, web.archive.org, tk.hu,
  tk.mta.hu, `*.tk.hun-ren.hu`, socio.mta.hu, rki.krtk.hu. Their aliases are inferred
  (#14).
- **doktori.hu** disallows AI crawlers; access route needs a decision (#22).

## Open high-priority issues

#4 Person mention vs canonical Person (in progress, Milestone 2 branch) ·
#5 Evidence-based person resolution (next) · #7 ProjectMention vs canonical Project ·
#12 Source coverage QA

## Next

- Implementation: #5 (evidence-based mention resolution; signal classes documented in
  docs/methodology.md §3), after review of #4.
- Expansion target after Milestone 2: KRTK Regionális Kutatások Intézete, then TÁRKI (#21).

## Future milestones

- Milestone 3: contemporary Hungarian sociology coverage (#21).
- Milestone 4: publications and academic genealogy (#22, #23).
- Milestone 5: historical sociology atlas (#24).
