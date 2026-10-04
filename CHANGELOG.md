# Changelog

## 0.2.2 (2026-10-04) — remaining section labels from the #8 rebuild

* TK parser 0.2.2. Found by re-measuring release `2026-10-tk` with 0.2.1: the section
  label pattern read `projektek?` as "projekte" + optional "k", so singular labels
  ("Futó kutatási projekt:", "Lezárult kutatási projekt:") slipped through, and stacked
  qualifiers ("Jelenleg futó projektek") did not match. Link text "Fejezetszerző"
  (chapter author) is a role, not a project.

## 0.2.1 (2026-10-04) — profile project lists without pseudo-projects (#8)

* TK parser 0.2.1. A profile's "Projektek" section no longer turns metadata lines into
  projects: section labels ("Korábbi projektek:", "Aktuális kutatások:"), column
  headers ("Cím / téma", "Intézmény", "Időtartam"), role lines ("Kutatásvezető",
  "Vezető kutató, WP vezető"), period-only lines ("2022-2024", "2003-"), bare grant
  ids ("NKFIH. K147329", "119603 jelű", "TÁMOP 5.4.1-12") and bare funder names.
  The rule is whole-line and high precision; uncertain activities ("ELKH Zászlóshajó
  projekt", "MTA Kutatócsoport") are kept for activity classification (#9).
* A table row in a profile's project section is one project: the first non-metadata
  cell is the title and the row's period, grant and role cells qualify it (observed
  column orders: title-institution-period, period-title, grant-role-title). Outside
  tables, metadata lines are dropped rather than attached, because the markup does not
  say which neighbouring title they belong to.
* A link whose text is a URL is not a project title; a stray one-letter link joined to
  the next link ("D" + "onáció …") is repaired as for names.
* Rejected lines are kept on the parsed profile for parser QA (never stored as claims).

## 0.2.0 (2026-10-04) — first live TK crawl

* First live crawl of the four enabled TK sites (szociologia, recens, kisebbsegkutato,
  politikatudomany); release `2026-10-tk` built from real snapshots.
* TK parser 0.2.0, rewritten against the real markup. Differences from the
  reconstructed fixtures: the page title is an `<h2>` (no `<h1>`); profile sections
  use `<h5>`; the staff category is an `<h4>` and the position is a bare text node
  (sometimes only "(TK SZI)"); several SZI profiles put a narrative bio under
  "Kutatási területek"; PTI lists areas comma-separated; project pages put funder,
  period and lead on one `<p>` separated by `<br>`; category listings are `<article>`
  lists that carry funder / period / lead / participants; footer links had leaked
  into profile project lists.
* New: project-listing parser (claims attributed to the listing page), project
  roles and "stated lead" qualifiers on profile project mentions, unlinked project
  leads as name-only PI claims, staff category on affiliations, unit leaders named
  on the line after the link (KI).
* Fetcher retries transport errors and 429/5xx with backoff instead of aborting a source.
* Fixtures are now scrubbed real snapshots (`szocatlas.scrub`); reconstructed ones removed.
* Registry: KI and PTI department URLs and the PTI project listing confirmed.

## 0.1.0 (2026-10-04)

* Ontology v0.1: claims/documents provenance layer, 11 entity types, 29 relation types,
  epistemic status / assertion type / temporal basis axes.
* Source registry with TK ecosystem (5 adapter-backed sites, 14 more catalogued).
* Polite fetcher with content-addressed raw snapshots and offline replay.
* TK adapter: listings (pagination, letter filters), profiles, unit pages, project pages.
* Taxonomy v0.1 (34 topics, 19 methods) and derived topic/method edges.
* Entity resolution: hard-id merges, review queue, manual overrides, persistent ids.
* Canonical release builder with conflict preservation and QA report.
* Idempotent Neo4j loader, constraints, 11 example queries; NetworkX export.
* Next.js explorer: search, profiles, observed/derived edges, ego network, evidence.
* Fixture-sample release (reconstructed fixtures; not real data).
