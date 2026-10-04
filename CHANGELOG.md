# Changelog

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
