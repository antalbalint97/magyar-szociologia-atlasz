# Project status

High-level snapshot of the research and engineering state. **GitHub Issues are the source
of truth for actionable work**; this page links to them and does not duplicate them.
Last updated: 2026-10-05.

## Current release

`2026-10-tk-r2` (snapshot, schema 0.1.0, TK parser **tk/0.2.2**, taxonomy keyword map
0.1.0), a deterministic rebuild of the four TK sites (Szociológiai Intézet, CSS-RECENS,
Kisebbségkutató Intézet, Politikatudományi Intézet) from a fresh crawl on 2026-10-04.
The same snapshots replayed with tk/0.2.0 reproduce the original `2026-10-tk` exactly
(509 documents, 9,188 claims, 646 projects). Releases are not in git
(docs/architecture.md); they are shared as tarballs with their quality reports.

Raw and canonical counts, side by side. The Milestone 2 columns are the same snapshot
built on the Milestone 2 branch (#4 ADR-0006, #5 ADR-0007, #27, #7 ADR-0008, #16/#12 ADR-0009);
they are previews, not published releases. `p16` is the first preview built from a larger crawl:
57 project pages that profiles link were fetched, so its source set differs from the others
(`manifest.source_set`).

| | `2026-10-tk-r2` (Milestone 1 model) | `2026-10-tk-m2-p5` (#4, #5) | `2026-10-tk-m2-s27` (#27) | `2026-10-tk-m2-p7r` (#7 closed) | `2026-10-tk-m2-p16` (#16, #12) |
|---|---|---|---|---|---|
| Documents / claims | 509 / 9,063 | 509 / 9,063 | 509 / 9,063 | 509 / 9,119 (tk/0.4.0) | **566 / 10,033** (506 → 563 web pages; tk/0.5.0) |
| Canonical Persons | 364 (161 profiled, 203 name strings) | 161 | **160** (Stefkovics Ádám's two profiles joined) | 160 | 160 |
| Person mentions | n/a | 1,021: 797 resolved, 53 review, 171 no candidate | 1,021: 798 / 52 / 171 | 1,021: 808 resolved (668 certain, 140 by rule) / 42 / 171 | 1,188: **908** resolved (758 certain, 150 by rule) / 48 / 232 (the new pages list collaborators who have no profile) |
| Projects | 606 (315 page-backed, 291 profile titles only) | 606 | 606 | 223, all page-backed | **280**, all page-backed (every p7r id intact) |
| Project mentions | n/a | n/a | n/a | 783: 362 resolved (327 by URL, 28 by rule, 7 manual), 1 review, 420 no candidate | 783: **450** resolved (412 by URL, 31 by rule, 7 manual), 4 review, 329 no candidate |
| Relations | 2,209 | 2,043 | 2,042 | 1,243 (`PARTICIPATES_IN` 231, `PRINCIPAL_INVESTIGATOR_OF` 93) | 1,521 (`PARTICIPATES_IN` **341**, `PRINCIPAL_INVESTIGATOR_OF` **136**) |
| Researchers with a project edge | | | | 94 of 160 (KI 0) | **120 of 160** (KI 25) |
| Co-participation ties (person pairs sharing a project) | | | 491 | 451 | **551** (100 gained, 0 lost) |
| QA | 0 errors, 46 warnings | 0 errors | 0 errors, 43 warnings | 0 errors, 38 warnings | 0 errors, 37 warnings |

**0 QA errors means pipeline correctness, not coverage.** Coverage is now measured apart
from correctness (`coverage.md` in every release, #12; ADR-0009); the QA seed Virág Tünde is
still absent (#13) and is reported as a sentinel, not as a coverage estimate.
**The data is not ready for network analysis** (#17):
* Project resolution is still uneven by institute (project mentions resolved: SZI 298 of
  417, KI 74 of 114, PTI 74 of 186, CSS-RECENS 4 of 66). KI went from 0 to 65% by fetching
  the 47 pages its profiles link; most of what remains has no page to anchor on (profile
  titles with no link) or links an external or other-unit site.
* 280 person mentions (48 in review, 232 with no candidate) and 333 project mentions (4 in
  review, 329 with no candidate) are outside the analytical graph.
* Projects with at least 8 participants (7 of them) produce 68% of all co-participation ties;
  the same share as before the expansion.

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
- **Projects**: #7 is closed on the Milestone 2 branch (ADR-0008, not merged); #16 is
  implemented on it (ADR-0009, not merged).
  * 329 project mentions have no Project. Each has an explicit reason in the coverage
    report: 282 give a title and no page, 32 link an external site, 11 link another TK
    unit's site that is not a source, 1 links a grant record, 3 link an in-scope page that is
    not of project-page shape. 4 await review (`review/project_review.yaml`).
  * Activity classification of journals, networks and programmes listed as projects is
    #9. ESS Magyarország is deferred to it.
- **Unreachable hosts** from the crawl environment: doktori.hu, web.archive.org,
  `*.tk.hun-ren.hu` (egress policy, HTTP 403), socio.mta.hu, rki.krtk.hu. Some `*.tk.hu` and
  `*.tk.mta.hu` hosts answered a one-off probe on 2026-10-05, mostly by redirecting to
  `*.tk.elte.hu` (docs/sources.md). The aliases that were not fetched stay inferred (#14).
- **doktori.hu** disallows AI crawlers; access route needs a decision (#22).

## Open high-priority issues

#12 Source coverage QA (framework implemented; kept open until its metrics are validated) ·
#17 analysis readiness · #9 activity classification · #16 (scoped gap closed; see the issue)

## Next

- The choice is between three issues, after review of #16/#12:
  * analysis readiness (#17), which now has measured coverage and tie concentration to
    work from;
  * activity classification (#9);
  * the remaining identity items (#10, #11).
- Expansion target after Milestone 2: KRTK Regionális Kutatások Intézete, then TÁRKI (#21).
  Not started.

## Future milestones

- Milestone 3: contemporary Hungarian sociology coverage (#21).
- Milestone 4: publications and academic genealogy (#22, #23).
- Milestone 5: historical sociology atlas (#24).
