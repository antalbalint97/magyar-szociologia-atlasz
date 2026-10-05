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
built on the Milestone 2 branch (#4 ADR-0006, #5 ADR-0007, #27, #7 ADR-0008, #16/#12 ADR-0009,
#31 ADR-0010); they are previews, not published releases. `p16` is the first preview built from a
larger crawl: 57 project pages that profiles link were fetched, so its source set differs from the
others (`manifest.source_set`). `p31` re-parses the same 563 web pages as `p16` (same source-set
digest `6e7fd8757ffc5c44`) with parser tk/0.6.0, so what changes between them is what the parser
reads, not what was crawled.

| | `2026-10-tk-r2` (Milestone 1 model) | `2026-10-tk-m2-p5` (#4, #5) | `2026-10-tk-m2-s27` (#27) | `2026-10-tk-m2-p7r` (#7 closed) | `2026-10-tk-m2-p16` (#16, #12) | `2026-10-tk-m2-p31` (#31, #17) |
|---|---|---|---|---|---|---|
| Documents / claims | 509 / 9,063 | 509 / 9,063 | 509 / 9,063 | 509 / 9,119 (tk/0.4.0) | 566 / 10,033 (506 → 563 web pages; tk/0.5.0) | **566 / 10,641** (the same 563 web pages; tk/0.6.0) |
| Canonical Persons | 364 (161 profiled, 203 name strings) | 161 | **160** (Stefkovics Ádám's two profiles joined) | 160 | 160 | 160 |
| Person mentions | n/a | 1,021: 797 resolved, 53 review, 171 no candidate | 1,021: 798 / 52 / 171 | 1,021: 808 resolved (668 certain, 140 by rule) / 42 / 171 | 1,188: **908** resolved (758 certain, 150 by rule) / 48 / 232 (the new pages list collaborators who have no profile) | 1,435: **1,006** resolved (758 certain, 248 by rule) / 67 / 362 (247 new: the participants and leads that the SZI heading template states in plain text) |
| Projects | 606 (315 page-backed, 291 profile titles only) | 606 | 606 | 223, all page-backed | **280**, all page-backed (every p7r id intact) | 280 (every p16 id intact) |
| Project mentions | n/a | n/a | n/a | 783: 362 resolved (327 by URL, 28 by rule, 7 manual), 1 review, 420 no candidate | 783: **450** resolved (412 by URL, 31 by rule, 7 manual), 4 review, 329 no candidate | 783: 450 resolved (unchanged) |
| Relations | 2,209 | 2,043 | 2,042 | 1,243 (`PARTICIPATES_IN` 231, `PRINCIPAL_INVESTIGATOR_OF` 93) | 1,521 (`PARTICIPATES_IN` **341**, `PRINCIPAL_INVESTIGATOR_OF` **136**) | 1,645 (`PARTICIPATES_IN` **423**, `PRINCIPAL_INVESTIGATOR_OF` **178**) |
| SZI project pages (of 193) with a lead / with participants | | | | | 60 / 17 | **138 / 75** |
| Researchers with a project edge | | | | 94 of 160 (KI 0) | **120 of 160** (KI 25) | 120 of 160 (the new edges are on researchers who already had one) |
| Co-participation ties (person pairs sharing a project) | | | 491 | 451 | **551** (100 gained, 0 lost) | **584** (33 gained, 0 lost; all inside SZI) |
| QA | 0 errors, 46 warnings | 0 errors | 0 errors, 43 warnings | 0 errors, 38 warnings | 0 errors, 37 warnings | 0 errors, 37 warnings |

**0 QA errors means pipeline correctness, not coverage.** Coverage is now measured apart
from correctness (`coverage.md` in every release, #12; ADR-0009); the QA seed Virág Tünde is
still absent (#13) and is reported as a sentinel, not as a coverage estimate.

**Analysis readiness (#17; `docs/analysis_readiness.md`, grades proposed for review): the dataset
is not declared ready.** Exploratory description of the Person-Project graph and of its derived
Person-Person projection is `READY_WITH_RESTRICTIONS`; person rankings, institute comparisons,
roles, positions, project types, topics and methods, and anything over time are `NOT_READY`; no
analysis type is `READY`. Every release now carries its own `analysis_readiness.md`. What the
grades rest on (p31, each figure with its denominator in the document):
* 296 of 825 stated project participants (36%) are outside the graph (no candidate Person, or in
  review). The Person universe is each site's current staff listing; former staff and outside
  collaborators are mentions (#28). 429 of 1,435 person mentions (30%) are outside the graph.
* 7 projects of 8 or more persons carry 376 of 584 ties (64%); 322 (55%) exist only through them,
  and 68 of the 83 cross-institute ties run through one project of 20 persons.
* 167 of 601 project edges (28%) rest only on an automatic identity rule (SZI 163 of 349);
  the strict policy keeps 473 of the 584 ties.
* Degree rankings are not stable: with the 7 projects removed the top decile overlaps the original
  by 0.087 (Jaccard), so no ranking of persons is authorised.
* Project resolution is uneven by institute (project mentions resolved: SZI 298 of 417, KI 74 of
  114, PTI 74 of 186, CSS-RECENS 4 of 66); most of what remains has no page to anchor on.

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

- **Identity**: #4, #5 and #27 are done on the Milestone 2 branch (not merged). 67 person
  mentions wait for review (`review/mention_review.yaml`). 362 have no candidate, mostly
  former staff whose profile is gone and outside collaborators (#28); 130 of them were made
  visible by #31. A stated affiliation is not used as resolver evidence (#34), and the identity
  basis of a project edge is only derivable from claims, not stored (#37).
- **Projects**: #7 is closed on the Milestone 2 branch (ADR-0008, not merged). #16 stays open:
  its first sub-problem (project pages that profiles link) is implemented there (ADR-0009, not
  merged); research-group pages, KI thematic research pages and CSS-RECENS former members are not.
  #31 (ADR-0010) reads the SZI heading template. 51 of the 193 SZI project pages still state
  people under a label no field takes; what those labels mean is a decision (#36). A wrong
  abstract is stored on 14 pages by the legacy description rule (#35).
  * 329 project mentions have no Project. Each has an explicit reason in the coverage
    report: 282 give a title and no page, 32 link an external site, 11 link another TK
    unit's site that is not a source, 1 links a grant record, 3 link an in-scope page that is
    not of project-page shape. Besides those, 3 await review and 1 (ESS Magyarország) is
    deferred to #9 (`review/project_review.yaml`).
  * Activity classification of journals, networks and programmes listed as projects is
    #9. ESS Magyarország is deferred to it.
- **Unreachable hosts** from the crawl environment: doktori.hu, web.archive.org,
  `*.tk.hun-ren.hu` (egress policy, HTTP 403), socio.mta.hu, rki.krtk.hu. Some `*.tk.hu` and
  `*.tk.mta.hu` hosts answered a one-off probe on 2026-10-05, mostly by redirecting to
  `*.tk.elte.hu` (docs/sources.md). The aliases that were not fetched stay inferred (#14).
- **doktori.hu** disallows AI crawlers; access route needs a decision (#22).

## Open high-priority issues

#16 TK coverage gaps (one sub-problem done, original criteria not complete) · #9 activity
classification. Done on the Milestone 2 branch since the last update: #12 (closed), #31 (SZI
heading template, ADR-0010) and #17 (the readiness report and its assessment).

## Next

- Nothing is started. The readiness result says which issue to take (docs/analysis_readiness.md
  §10): #9 first, because whether the few large "projects" that carry most of the ties are research
  projects or programmes decides how the Person-Person projection may be read; then #28 (who is
  missing), #10 and #11 (roles, positions, dates). #19 only as the restricted exploratory
  description of docs/analysis_readiness.md §1, and only on Bálint's go.
- Expansion target after Milestone 2: KRTK Regionális Kutatások Intézete, then TÁRKI (#21).
  Not started.

## Future milestones

- Milestone 3: contemporary Hungarian sociology coverage (#21).
- Milestone 4: publications and academic genealogy (#22, #23).
- Milestone 5: historical sociology atlas (#24).
