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
built on the Milestone 2 branch (#4 ADR-0006, #5 ADR-0007); they are previews, not
published releases.

| | `2026-10-tk-r2` (Milestone 1 model) | `2026-10-tk-m2` (#4) | `2026-10-tk-m2-p5` (#5) |
|---|---|---|---|
| Documents / claims | 509 / 9,063 | 509 / 9,063 | 509 / 9,063 |
| Person-like source records | 364 | 364 | 364 |
| Canonical Persons | 364 (161 profiled, 203 name strings) | **161**, all with an institutional profile; 134 with MTMT, 1 with ORCID | 161 |
| Person mentions (outside own profile) | n/a | 1,021: 682 resolved (profile URL), **339 unresolved** | 1,021: **797 resolved** (668 certain, 129 by documented rule), 53 need review, 171 have no candidate |
| Projects | 606 (315 page-backed, 291 profile titles only) | 606 | 606 |
| Relations | 2,209 | 1,969 | 2,043 (`PARTICIPATES_IN` 622 → 670, `PRINCIPAL_INVESTIGATOR_OF` 88 → 112) |
| QA | 0 errors, 46 warnings, 191 orphan persons, 3 "suspicious merges" | 0 errors, 43 warnings, 0 orphan persons, 0 suspicious merges | 0 errors; resolution uneven by source (KI 99%, SZI 81%, PTI 67%) |

**0 QA errors means pipeline correctness, not coverage.** The QA seed Virág Tünde is
absent (#13), and fetch, parse, field and taxonomy coverage are not measured yet (#12).
**The data is not ready for network analysis** (#17): 224 mentions are still outside the
analytical graph (Ságvári Bence: 6 resolved, 10 in review), resolution rates differ by
source, and profile titles do not yet resolve to project pages (#7; 6 title-collision
groups, 1 known edition false merge).

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

- **Identity**: #4 and #5 are implemented on the Milestone 2 branch (not merged). 53
  mentions wait for review (`review/mention_review.yaml`); 171 have no candidate, mostly
  former staff whose profile is gone. Two TK profiles of one person (Stefkovics Ádám)
  stay separate Persons until a reviewer decides.
- **Projects**: profile titles do not resolve to project pages (#7). Pseudo-projects
  from profile metadata lines are fixed in PR #2 (#8, tk/0.2.2); many profile titles
  still carry role or grant suffixes ("… – Kutató"), which #7 must normalise.
- **Unreachable hosts** from the crawl environment: doktori.hu, web.archive.org, tk.hu,
  tk.mta.hu, `*.tk.hun-ren.hu`, socio.mta.hu, rki.krtk.hu. Their aliases are inferred
  (#14).
- **doktori.hu** disallows AI crawlers; access route needs a decision (#22).

## Open high-priority issues

#4 Person mention vs canonical Person and #5 evidence-based person resolution
(implemented, Milestone 2 branch, in review) · #7 ProjectMention vs canonical Project ·
#12 Source coverage QA

## Next

- Implementation: #7 (ProjectMention vs canonical Project), after review of #4/#5.
- Expansion target after Milestone 2: KRTK Regionális Kutatások Intézete, then TÁRKI (#21).

## Future milestones

- Milestone 3: contemporary Hungarian sociology coverage (#21).
- Milestone 4: publications and academic genealogy (#22, #23).
- Milestone 5: historical sociology atlas (#24).
