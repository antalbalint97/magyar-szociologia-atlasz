# Changelog

## Unreleased (Milestone 2 branch)

* Codex review follow-ups (#40, #41, #43, #45): four findings of the automated review of PRs #26 and
  #2, each reproduced before it was filed. A replay rebuild of `p31` is identical to it apart from
  timestamps (17 of 22 files byte for byte, 4 once timestamps and the release id are masked, the
  quality report differs only in its `generated_at` line); the review files are unchanged.
  * #40, profile-link following: the fetch decision is per page, not per statement. A page that one
    profile wrote on the canonical host or a verified alias is fetched even if another profile wrote
    it on an inferred alias; a page every profile wrote on an inferred alias is still skipped
    (`alias_unverified`). The decision had a second half: the build never looked at the host a
    project link was written on, so a mention whose link existed only through an inferred alias
    resolved by `PROJECT_URL_EXACT` as soon as the page was anchored (reproduced on the previous
    code). The adapter now keeps the link as written on the project record (`stated_url`), and such a
    mention is no certain decision, as for profile links (ADR-0007): it goes to the evidence rules
    and, if they decide nothing, to the new coverage category `linked_page_alias_unverified`.
    ADR-0009 states the rule; `p31` has no mention that it affects (1 of 208 profile-section project
    links used an inferred alias, `jog.tk.hu`, for a unit that is not an enabled source).
  * #41, release builder: `entities/` is wholly build output, so a rebuild of an existing release id
    removes the entity files of types the new build has no rows for (they used to stay behind and
    contradict `manifest.entities`).
  * #43, fixture scrubber: a phone number is now also recognised after a label in the same text node
    (`Telefon: (1) 224 6700`) and when written with an area code (`1/224-6700`); the scrubber is
    tested on its own, and a test scrubs every committed fixture again and fails if anything
    changes. It remains a safety net: every new capture is still read by eye.
  * #45, TK parser: a period-and-role header that ends a profile's project section (or is followed
    by another one) is kept as unattached metadata, not turned into a project titled with the role.
* Analysis readiness (#17): every release has `analysis_readiness.json` / `analysis_readiness.md`,
  written by `szocatlas build`, summarised in `manifest.analysis_readiness` and in a section of
  the quality report. `szocatlas readiness <release> [--json] [--write]` measures any release, old
  or new, from its directory alone. 22 diagnostic indicators in six families (Person-institution,
  Person-project, the Person-Person projection, topics and methods, identity, time), each with its
  definition, denominator and the analysis it threatens; no pass/fail thresholds, no timestamps,
  no person named or ranked, byte-identical for an unchanged release. The Person-Project graph is
  the observed layer and the Person-Person projection a derived one; the identity basis of every
  project edge (anchored, certain, automatic) is read from the claims behind it, each joined to
  the mention that carries it (never from the form of the subject's reference: a profile or
  external link can be unresolved or automatic too), and the projection is measured under three
  versions of the edges (`default`, `strict_certain_edges_only`, `complete_projects_only`, never
  merged) and for large-project thresholds of 8, 9 and 10 persons. The recall side is a labelled
  upper bound, not a version of the data: every statement still in review that has exactly one
  candidate Person accepted, in total and one kind at a time. `research/analysis/projection_sensitivity.py` (networkx, the
  `analysis` extra) compares unweighted, shared-project-count and size-discounted (Newman 2001)
  weightings, degree and betweenness rankings, the identity policies, the removal of large
  projects and seeded community detection, as aggregate output. The assessment, with a grade per
  analysis type, is `docs/analysis_readiness.md` (proposed grades: no analysis type is `READY`);
  definitions are in `docs/methodology.md` §9. 24 new tests. `research/analysis/identity_basis_recount.py`
  recounts the identity-basis figures (B3, B4 and the three versions of the edges) from the files of
  a release with separate code and no import from `szocatlas`; it is the oracle for the join in the
  readiness module (5 more tests) and agrees with it on all five compared releases. The `p31`
  rebuild changed only `analysis_readiness.*` and the quality report.
* TK parser 0.6.0, SZI heading template (#31, ADR-0010): 86 of the 193 SZI project pages write
  "Projektvezető" / "Kutatásvezető (MTA SZKI)" / "Résztvevők" as headings and the value in the
  blocks below; the parser only read `Label: value` lines and found no lead or participant on
  them. A heading (h2-h6, never the title) now counts as a lead or participants label when it
  matches an existing label (at most three words, one trailing parenthetical and a colon
  removed); its section is what follows it in its own parent up to the next heading of any level
  (or a table, rule, form, figure, iframe) or the first block that holds no name. A line is read
  as names only if it looks like names from its start (two to five capitalised tokens, no
  organisation, country or programme word, no colon or link; reading stops at the first part
  that is not a person); the short label "Résztvevő" keeps the profile-links-only rule. A heading
  with no readable value produces no field and is listed in `unmapped_labels`. Field semantics
  are the label-line ones, so leads and participants without a profile become PersonMentions;
  claims carry the locator `project.heading.*`, the heading and the line as snippet, and the
  label as role. Whole-page search, proximity and new label words ("Koordinátor") were left out
  on purpose. 16 real, scrubbed fixtures; 64 new tests.
* **Behaviour change** in the same release: a project description under an explicit `A kutatás`
  heading takes precedence over "the first long `<p>`" (locator `project.heading.description`).
  On the 86 pages 30 projects gained an abstract that sat in a `<div>`, and 11 abstracts that
  were participant or coordinator lists were replaced by the description (37 abstract claims
  re-issued under a new locator and so a new claim id). No other claim changed: the other 107 SZI
  pages and every KI, PTI and CSS-RECENS page have the same claim ids as in `p16`.
* Preview `2026-10-tk-m2-p31` (same 563 web documents as `p16`, source-set digest
  `6e7fd8757ffc5c44`, replayed from the stored snapshots): SZI project pages with a lead 60 → 138
  of 193, with participants 17 → 75; person mentions 1,188 → 1,435 (247 new, all plain text),
  resolved 908 → 1,006 (HIGH_CONFIDENCE_AUTO 150 → 248), review 48 → 67, no candidate 232 → 362;
  `PRINCIPAL_INVESTIGATOR_OF` 136 → 178, `PARTICIPATES_IN` 341 → 423, co-participation ties
  551 → 584 (all within SZI; no cross-institute change). No Person or Project id and no earlier
  resolution changed; three rebuilds are byte-identical apart from the generated timestamp.
  Edge growth is a better observation of pages already crawled, not new knowledge.
* Source coverage (#16, ADR-0009): a link in a profile's project section is discovery evidence.
  The crawl follows it one hop when the link's host belongs to an enabled source with an adapter
  that opted in (`follow_profile_project_links` for SZI, CSS-RECENS, KI, PTI), the path has the
  shape of a project page (one segment, no query, not a menu/staff/category/news segment, not a
  unit page) and the host is not an inferred-only alias. Links to other TK units' sites, external
  sites and grant records are not fetched; each gets a **frontier row** (`frontier.jsonl` in staged
  data and in the release: scope, decision, reason, host status, what the fetch returned,
  `discovered_via: {type: profile_project_link, source_document, project_ref, ...}`). First run:
  57 linked pages fetched (KI 47, PTI 7, CSS-RECENS 3), 0 errors; 90 of 90 in-scope linked URLs are
  now in the crawl. Project mentions resolved 362 → 450 of 783 (KI 0 → 74 of 114), Projects 223 →
  280 with every old id intact, no earlier decision changed. Unresolved link reasons now come from
  the frontier ("linked project page not followed (external_host)").
* TK parser 0.5.0: labels seen on the newly fetched pages ("Támogatási forrás", "Kutatás
  időtartama", "Részvevők"), month-name periods at month precision, bare funder/period lines in a
  header block, `unmapped_labels` for labelled lines no field took. Only explicit labels are read;
  narrative pages yield no funder, period or participants. 10 real, scrubbed fixtures.
* Canonical build: a coarser ISO date agrees with the single finer date it prefixes
  (`PARTIAL_DATE_FIELDS`: `start`, `end`), so "2021-06" and "2021-06-25" are not a conflict.
* Coverage QA (#12): every release has `coverage.json` / `coverage.md`, `parse_report.jsonl`,
  `frontier.jsonl` and `manifest.source_set` (document count, digest, by source and page type).
  Layers: document universe, discovery, fetch, parse, canonicalisation by observing source with an
  explicit category for every unresolved project mention, field coverage, network consequences
  (researchers without a project edge, upper bound of ties missing because a linked page has no
  Project), sentinels. Every figure carries its denominator; coverage findings are warnings or
  info, never errors; QA seeds stay sentinels.
* Fetcher: a refused host says why. `robots.txt disallows <url>` is now only used when the site
  disallows the page; a robots.txt that answered HTTP 5xx or could not be reached reads
  `robots.txt answered HTTP 500, host not crawled: <url>` / `robots.txt unreachable (ConnectError), ...`.
  The three are different facts for coverage (#12). Behaviour is unchanged: the host is refused in
  all three cases. First fetcher tests (mock transport).
* `ingest` runs every adapter first, then the discovery step, so a page linked from one site and
  served by another is fetched by its owner; `--replay` re-derives frontier and diagnostics.
  Preview `2026-10-tk-m2-p16`.
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
