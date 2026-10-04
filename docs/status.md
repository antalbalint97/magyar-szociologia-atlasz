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

Raw and canonical counts, side by side. The Milestone 2 columns are the same snapshot
built on the Milestone 2 branch (#4 ADR-0006, #5 ADR-0007, #27, #7 ADR-0008); they are
previews, not published releases.

| | `2026-10-tk-r2` (Milestone 1 model) | `2026-10-tk-m2-p5` (#4, #5) | `2026-10-tk-m2-s27` (#27) | `2026-10-tk-m2-p7` (#7) |
|---|---|---|---|---|
| Documents / claims | 509 / 9,063 | 509 / 9,063 | 509 / 9,063 | 509 / 9,119 (+56 unattached project metadata, tk/0.4.0) |
| Canonical Persons | 364 (161 profiled, 203 name strings) | 161 | **160** (Stefkovics Ádám's two profiles joined) | 160 |
| Person mentions | n/a | 1,021: 797 resolved, 53 review, 171 no candidate | 1,021: 798 / 52 / 171 | 1,021: **808** resolved (668 certain, 140 by rule) / **42** / 171 |
| Projects | 606 (315 page-backed, 291 profile titles only) | 606 | 606 | **223**, all page-backed |
| Project mentions | n/a | n/a | n/a | 783: 355 resolved (327 by URL, 28 by rule), 8 review, 420 no candidate |
| Relations | 2,209 | 2,043 | 2,042 | 1,237 (`PARTICIPATES_IN` 671 → 225, `PRINCIPAL_INVESTIGATOR_OF` 112 → 93) |
| Co-participation ties (person pairs sharing a project) | | | 491 | 446 (52 lost, 7 gained) |
| QA | 0 errors, 46 warnings | 0 errors | 0 errors, 43 warnings | 0 errors, 38 warnings |

**0 QA errors means pipeline correctness, not coverage.** The QA seed Virág Tünde is
absent (#13), and fetch, parse, field and taxonomy coverage are not measured yet (#12).
**The data is not ready for network analysis** (#17):
* Project resolution is very uneven by institute. 25 KI researchers had project edges,
  and none do now, because KI project pages were never crawled: their profiles link
  them, but no page anchors a Project (#12/#16).
* 213 person mentions and 428 project mentions are outside the analytical graph.
* Five page-backed projects with long participant lists produce two thirds of all
  co-participation ties.

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

- **Identity**: #4, #5 and #27 are done on the Milestone 2 branch (not merged). 42 person
  mentions wait for review (`review/mention_review.yaml`). 171 have no candidate, mostly
  former staff whose profile is gone (#28).
- **Projects**: #7 is implemented on the Milestone 2 branch (ADR-0008, not merged).
  * 8 project mentions wait for review (`review/project_review.yaml`).
  * 420 have no candidate: 131 link a project page the crawl never fetched (mostly
    KI), 289 are profile titles with no page.
  * Activity classification of journals, networks and programmes listed as projects is
    #9.
- **Unreachable hosts** from the crawl environment: doktori.hu, web.archive.org, tk.hu,
  tk.mta.hu, `*.tk.hun-ren.hu`, socio.mta.hu, rki.krtk.hu. Their aliases are inferred
  (#14).
- **doktori.hu** disallows AI crawlers; access route needs a decision (#22).

## Open high-priority issues

#7 ProjectMention vs canonical Project (implemented, Milestone 2 branch, in review) ·
#12 Source coverage QA · #17 analysis readiness · #9 activity classification

## Next

- After review of #7, the choice is between three issues:
  * coverage QA (#12), including crawling the project pages that profiles link but the
    crawl never fetched;
  * analysis readiness (#17);
  * activity classification (#9).
- Expansion target after Milestone 2: KRTK Regionális Kutatások Intézete, then TÁRKI (#21).

## Future milestones

- Milestone 3: contemporary Hungarian sociology coverage (#21).
- Milestone 4: publications and academic genealogy (#22, #23).
- Milestone 5: historical sociology atlas (#24).
