# Changelog

## Unreleased (Milestone 2 branch)

* Review of the 8 project mentions left for a decision (#7): seven manual `same_as` entries in
  `review/manual_overrides.yaml` (two ReproSoc profile items, three of Tibori Tímea's, Kmetty
  Zoltán's and Acsády Judit's), each with the evidence that decided it. A manual `same_as` keeps
  the signals the rules saw, including the blocking one it overruled. New `defer` decision
  (`blocked_by`): ESS Magyarország stays unresolved until #9 decides its activity type; the
  review file lists it under `deferred`. Preview `2026-10-tk-m2-p7r`: no automatic or certain
  decision changed, project ids unchanged, `PARTICIPATES_IN` 225 → 231.

* Project mentions vs canonical Projects (#7, ADR-0008): a Project needs an identity
  anchor (its own page, or a manual decision). Every other project-like observation
  (listing article, profile line, link to an unfetched page) is a `ProjectMention` that
  may `RESOLVES_TO` one. `auto:same_site_same_name` no longer merges projects; this
  splits the `Éghajlatváltozás és egészség` 2020/2021 false merge into two Projects (the
  2021 page gets a new id, `previous_id: prj_2c4d005975`).
* Conservative project resolution: candidates from grant numbers and title keys (grant,
  role, period and funder affixes removed); rules `grant_and_title`, `grant_and_owner`,
  `title_and_owner`; title evidence never decides alone; blocking on conflicting grant
  numbers, disjoint periods, links to another page, several candidates, manual
  rejection. Links to the NKFIH public grant registry count as grant statements. Manual
  `project_decisions` and project `same_as` / `not_same_as`. Review queue
  `review/project_review.yaml`; resolver version in `config/resolution.yaml`.
* Person rule `own-profile-project` also uses projects resolved by the project rules
  (one-way dependency) and the titles of unresolved project mentions on the person's own
  profile.
* TK parser 0.4.0: project pages mark their record as the project's identity
  (`identity_anchor: project_page`); project-section metadata lines that the markup does
  not tie to one project are kept as `unattached_project_metadata` claims (kind, position,
  `attachment: unresolved`) instead of being dropped (moved from #8).
* QA and manifest: project counts next to project-mention counts, resolution by source
  and observation, errors for title-only or contradicted automatic decisions and for
  Projects without evidence; same-title distinct Projects, duplicate unresolved titles,
  activity cues (#9) and unattached metadata reported. Neo4j loader and explorer show
  project mentions, and a person page lists the projects on their own profile that did
  not resolve.
* Manual canonicalisation of one person's two profiles (#27): a `same_as` entry may name
  the `survivor` id; otherwise the oldest id survives, then the one with the stronger
  anchor (ADR-0003 addendum).

* Person mentions vs canonical Persons (#4, ADR-0006): a Person needs an identity anchor;
  every other person-like observation is a `PersonMention` that may `RESOLVES_TO` one.
* Evidence-based mention resolution (#5, ADR-0007): candidate generation separate from
  the decision; named rules that need a full-name match plus another strong signal
  (`slug-inferred-alias`, `slug-family-host`, `own-profile-project`,
  `unit-member-unique`, `institute-unique-name`); blocking negative evidence; new status
  `REVIEW_REQUIRED`; candidates stored with their positive and negative signals;
  `review/mention_review.yaml`; manual `mention_decisions` (`same_as`, `not_same_as`)
  that outrank every automatic decision. Resolver config in `config/resolution.yaml`.
* TK parser 0.3.0: person links keep the URL as written (`stated_url`) next to the
  alias-normalised one, so a link that exists only through an inferred host alias is no
  longer a certain identity decision. Verified host aliases (301 checked) are declared
  in `config/sources.yaml` (#14).
* Manifest and QA: per-source and per-page-type resolution rates, a warning when rates
  differ by more than 20 points, errors for unexplained or contradicted automatic
  decisions. `review/unresolved_people.yaml` lists only pairs of identity-anchored records.

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
