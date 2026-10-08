# ADR-0008: Project mentions are evidence; canonical Projects need an identity anchor

Status: accepted (2026-10-04) · Issue #7 · Builds on ADR-0003 (stable ids), ADR-0006 (mentions vs
identities), ADR-0007 (evidence-based resolution)

## Context

In release `2026-10-tk-m2-s27` every project-like source record became a canonical `Project`:

| Source records behind the 606 `Project` entities | Records |
|---|---|
| project page fetched (`<site>\|<url>`, the page itself and its listing articles) | 223 |
| a profile or listing links a project URL whose page was never fetched | 93 |
| a title on a researcher profile, no link (`<site>\|project-title:<slug>`) | 294 |

Project records are observed in several kinds of place: the project's own page, an article on
a category listing ("futó" / "lezárt"), a line in a researcher profile's "Projektek" section,
and table rows on some profiles. One project can appear on many of them, and these places mix
very different things:

* page-backed projects with a title, a period, a funder, sometimes a grant id, leads and
  participants;
* profile titles that carry the person's role, the grant id and the period in the title text
  ("OTKA K 143593 - Gyermekvédelem az iskolában: … – Kutatásvezető");
* repeated listings of the same project (listing + page: 223 projects; listing + profile + page);
* one project published on two pages: `Éghajlatváltozás és egészség` has a 2020 and a 2021
  page. `auto:same_site_same_name` merged them into `prj_2c4d005975`, which now carries two
  start dates (2020-04-01, 2021-06-25), two end dates, two websites and two abstracts;
* editions or phases sharing a title;
* activities that are not projects in the usual sense: journals, programmes, networks,
  infrastructures, consortia, newsletters ("Hírlevél (2)");
* metadata lines (role, period, grant id, funder) that the parser detached from their project
  in #8 because the markup does not say which project they belong to.

Two identity mechanisms produced the 606 Projects. A title-only record keyed by
`slugify(title)` per site turns two profiles listing the same string into one Project.
`auto:same_site_same_name` merges same-site records whose folded titles are equal. Four
merges came from the second rule: three page ↔ profile-title pairs and the Éghajlat
2020 ↔ 2021 false merge.

A false project merge creates the same harm as a false person merge, one level up. Every
participant of the two projects becomes a co-participant of every other, so a merge
invents ties, inflates degree and turns ordinary researchers into "hubs". Project identity is
harder than person identity:

* titles repeat across editions;
* titles evolve between funding application, page and profile;
* URLs change;
* funders rename themselves (OTKA → NKFIH);
* periods overlap;
* most records (597 of 610) state no grant id.

## Options

**A. One `Project` type with status fields** (`PAGE_BACKED`, `TITLE_ONLY`, `UNVERIFIED`), the
current records kept as Projects.

* \+ Smallest change. Queries, loader and explorer stay as they are.
* − Every analysis must remember to filter on the status. Forgetting it reproduces today's
  artefacts, and co-participation through a title-only "Project" is exactly a title-only merge.
* − Identity is still keyed to the folded title (`project-title:<slug>`): a title formatting
  change churns the id, and two different projects with one title stay one node.
* − Resolving a profile title to its page later means merging two Projects and retiring an id.
  Splitting a false merge (Éghajlat) means splitting one.
* − It mixes what a page said about a project (a role, a stated period, a grant string in the
  title) with what the project is.

**B. `ProjectMention` (evidence) → `RESOLVES_TO` → `Project` (identity)**, as for people.

* \+ The analytical graph contains only projects with identity evidence, by construction.
* \+ A profile line stays what it is, one person's statement about a project. The person's
  role and stated period stay on the person's edge or on the mention, not on the Project.
* \+ Re-resolution moves a decision, never an id. A wrong decision is undone by a manual
  `not_same_as` and leaves no residue.
* \+ Ambiguity (two editions with one title, a title on five profiles) is representable as a
  mention with several candidates instead of being forced into a merge or a split.
* − Profile participation in a project that has no page drops out of the analytical graph
  until something anchors that project. That is the conservative behaviour: those edges are
  visible as unresolved mentions, not lost.
* − One more node type, one more review file, counts always in pairs.

### Why the Person model is not copied blindly

Option B reuses the mention/identity layering and the decision vocabulary of ADR-0006/0007.
The signals and rules are project-specific, and three differences matter:

1. **Anchor.** A Person's anchor is the person's own profile page or a hard id. A Project's
   anchor is its own page on an institutional site. A grant id is a strong signal but not an
   anchor yet: it is stated on only 13 records, and the same number can be written several
   ways ("NKFIH K 128965", "K-128965", "128965 jelű"). Anchoring a Project by grant id alone
   (e.g. from the NKFIH registry) is a later extension under the same model (#12/#16).
2. **No name-uniqueness rule.** "This title is unique on this site" says nothing: projects with
   unique titles are still observed under variant titles, and editions share titles. The
   closed-world uniqueness assumption that `institute-unique-name` uses for people is not
   transferred.
3. **Editions.** Two pages with the same title can be different projects. Same title is never
   the same Project. Edition, phase and succession relations (`EDITION_OF`, `PHASE_OF`,
   `PREDECESSOR_OF`, `SUCCESSOR_OF`) need explicit evidence such as a page saying "the 2021
   continuation of …". No such statement exists in the current snapshot, so none is created.
   Same-title distinct Projects are listed for review (QA `project.same_title_distinct`).

## Decision

**Option B.**

### Project: an identity with an anchor

A canonical `Project` exists only when a source record carries project identity evidence
(`identity_evidence`):

| Anchor | Meaning |
|---|---|
| `project_page` | the project's own page on an institutional site was fetched (TK parser 0.4.0 marks the record) |
| `manual` | a reviewer joined records with `same_as` in `review/manual_overrides.yaml` |

`auto:same_site_same_name` no longer applies to projects; it stays for organisational units.
Two anchored project records are joined only by a manual `same_as`. Canonical ids keep
coming from `review/identity_map.jsonl` (ADR-0003). A page-backed Project's id is the one
first assigned to its page record, so a title edit does not change it. When a split moves a
record to a new id, the old id is kept as `previous_id`.

### ProjectMention: one observation of a project-like record in one page

The identity of a mention is the pair (source record ref, observing page URL). Its id is
`pjm_` + a hash of both. Observations on the project's own page are the identity itself,
not mentions. A mention is evidence, not a mini-Project, and carries only what the page
said:

| Field | Meaning |
|---|---|
| `stated_title`, `title_key` | title as written; folded key with grant, role, period and funder affixes removed (matching only) |
| `observation` | `profile_list` (researcher profile section), `project_listing` (category listing article), `other` |
| `source_ref`, `source_id`, `source_url`, `document_ids` | the record, the observing page, every retrieval |
| `linked_url` | the project URL the page linked, if any |
| `observed_on_profile_of` | the Person whose own profile lists it |
| `stated_period_from`, `stated_period_until` | the period as written (year or date, never widened) |
| `stated_funders`, `stated_grant_ids` | raw labels and raw grant strings; never normalised into the Project |
| `grant_keys` | matching keys (`nkfih:143593`) extracted from the grant field or the title |
| `stated_roles`, `stated_leads`, `stated_status` | the profile owner's role, a lead named in the line, the listing category |
| `context` | the relations the page asserts (participants, hosts) with their claim ids |
| `activity_cues` | words such as journal, network, programme, infrastructure, consortium, newsletter: a hint for #9, never a classification |
| `resolution`, `candidates` | the decision and every candidate's signals |

Field-level `provenance` lists the claim ids behind each field.

When a mention resolves, its claims (title variant, period, participants) are projected onto
the Project. Their values become alternate titles or field conflicts, with provenance. When
it does not resolve, its claims stay on the mention. The profile owner's participation is
then visible as an unresolved mention, not as a `PARTICIPATES_IN` edge.

### Candidates are not decisions

**Candidate generation** asks which anchored Projects a mention *might* be. A Project is a
candidate when one of these holds:

* it shares a grant key with the mention;
* its title key equals the mention's;
* one title key is a prefix of the other and the shorter one is at least 20 characters.

The **decision** names a rule and lists the signals it used. There is no score.

| Signal | Class | Meaning |
|---|---|---|
| `PROJECT_URL_EXACT` | certain | the mention links the Project's own page (the canonical URL, after host aliasing), and its page wrote the link on the canonical host or a verified alias (a link only through an inferred alias is not certain, #40, ADR-0009) |
| `MANUAL_SAME_AS` | certain | `project_decisions` or `same_as` in `review/manual_overrides.yaml` |
| `GRANT_ID_MATCH` | strong | same grant key (programme letters and funder label ignored, see "Funders") |
| `TITLE_EXACT` | strong (title) | same title up to case, accents and punctuation |
| `TITLE_EQUAL_AFTER_AFFIXES` | strong (title) | same title once grant, role, period and funder affixes are removed |
| `TITLE_PREFIX` | strong (title) | one title key is a prefix of the other, shorter one at least 20 characters |
| `PAGE_LINKS_OWNER` | strong | the Project's page links the profile owner's own profile |
| `PAGE_NAMES_OWNER` | strong | the Project's page names the profile owner by full name (name key) |
| `SAME_SITE` | weak | mention and Project are on the same institute site |
| `GRANT_ID_CONFLICT` | blocking | both state grant keys and none agree |
| `PERIOD_CONFLICT` | blocking | stated periods do not overlap (year precision; see "Temporal precision") |
| `LINKS_OTHER_PAGE` | blocking | the mention links a different URL (a research group's site, an old host). A link to a grant record in the NKFIH public registry (`nyilvanos.otka-palyazat.hu`, `num=`) is not "another page": it states the grant number |
| `MULTIPLE_CANDIDATES` | blocking | more than one viable candidate |
| `MANUAL_NOT_SAME_AS` | blocking | rejected by a reviewer |
| `ACTIVITY_CUE` | caution | `activity_cues` is non-empty (recorded, does not block) |

The three title signals are one kind of evidence. **No rule fires on title evidence alone.**
Weak or "similar" titles (a shared topic, word overlap, nearby appearance) do not even make a
candidate.

### Rules

A rule fires only when all of these hold:

* the mention has exactly one viable candidate (a candidate without a blocking signal);
* that candidate has a title signal or `GRANT_ID_MATCH`;
* no blocking signal applies;
* every listed signal is present.

| Rule | Requires |
|---|---|
| `grant_and_title` | `GRANT_ID_MATCH` + a title signal |
| `grant_and_owner` | `GRANT_ID_MATCH` + `PAGE_LINKS_OWNER` or `PAGE_NAMES_OWNER` |
| `title_and_owner` | a title signal + `PAGE_LINKS_OWNER` or `PAGE_NAMES_OWNER` |

`title_and_owner` is the profile case: the person's own profile lists a title compatible with
the page, and the page names the same person. The two observations are independent and
agree. A same-title page that does not name the profile owner stays in review.

Statuses are those of ADR-0007:

* `DETERMINISTIC`
* `MANUAL_CONFIRMED`
* `HIGH_CONFIDENCE_AUTO` (one of the rules above)
* `REVIEW_REQUIRED` (at least one candidate)
* `UNRESOLVED` (no candidate)

The reason is recorded either way. "linked project page not followed (external_host)" or
"...fetch failed (...)" (taken from the crawl frontier, ADR-0009) and "title on a profile, no
anchored project with a compatible title or grant id" are coverage findings (#12/#16), not
resolver failures.

### Order of decisions, and the one-way dependency on people

1. Certain project decisions (own page, exact URL, manual).
2. Pass 1a: canonical build from certain person and project decisions.
3. **Project rules.** They use anchored Projects from pass 1a and the *name observations* on
   project pages (strings and profile links), never an automatic person decision.
4. Pass 1b: canonical build with every resolved project.
5. **Person rules** (ADR-0007). `OWN_PROFILE_LISTS_PROJECT` may now use a profile project
   that a project rule resolved.
6. Pass 2: every resolved mention of both kinds.

Person rules may read project decisions, but project rules never read person decisions, so
no decision can support itself. `title_and_owner` followed by the person rule
`own-profile-project` is one joint hypothesis: "the project on X's profile is page P, and
the X named on P is X". It rests on two independent observations, the profile title and the
name on the page. That is the evidence standard ADR-0007 already applied to equal titles.

### Editions and the Éghajlat case

`Éghajlatváltozás és egészség` 2020 and 2021 are two pages, so they are two anchored records
and two Projects. The previous id stays with one of them and the other gets a new id with
`previous_id`. Each keeps its own start, end, website and abstract, so the conflict is not
"solved" by choosing a value. A profile that lists the bare title without a period would have
two viable candidates (`MULTIPLE_CANDIDATES`) and stays in review. No `EDITION_OF` edge is
created: the pages do not state the relation. QA lists the pair as same-title distinct
Projects for a reviewer.

### Temporal precision

A stated `2023` and a stated `2023-01-01` are not contradictory. Period compatibility is
checked at year precision, and only non-overlap blocks. Values are stored as written. Partial
dates, open intervals and precision flags are #11.

### Funders

Funder labels ("OTKA", "NKFIH", "NKFI", "Nemzeti Kutatási, Fejlesztési és Innovációs Hivatal")
are kept raw on mentions and Projects. They neither split nor merge projects.

Grant keys normalise only the number. The Hungarian OTKA/NKFI/NKFIH programmes share one
numbering, so `OTKA K 143593`, `NKFIH K_143593` and `K-143593` give the same key
`nkfih:143593`. A number counts as a grant number only when a funder or programme label or
"jelű" accompanies it. Funder normalisation and funder entities are #11.

### Non-table metadata (moved from #8)

Metadata lines in a profile's project section that the markup does not tie to a project
(role, period, grant, funder, section label, header row) are preserved as claims
`unattached_project_metadata` on the profile owner's record. Each carries:

* `kind`;
* `attachment: unresolved`;
* the line's position in the section.

They are never attached to a project by DOM proximity: role lines follow the title on some
profiles and precede it on others. They are counted in the manifest and stay in
`claims.jsonl` with full evidence. They are not projected onto the Person or onto any Project.
Table rows remain the one structural attachment: a cell of the same `<tr>` qualifies that
row's title (#8).

### Boundary with #9 (activity classification)

Journals, programmes, networks, infrastructures and consortia listed under "Projektek" stay as
project mentions or Projects exactly as observed. `activity_cues` records the words that
suggest a different activity type, for #9 to classify. #7 does not classify them, and the cues
do not change resolution.

### Manual decisions are authoritative

`review/manual_overrides.yaml`:

```yaml
project_decisions:
  - {mention_id: pjm_..., project_id: prj_..., decision: same_as | not_same_as,
     reviewer: <name>, date: YYYY-MM-DD, evidence: "..."}
  - {mention_id: pjm_..., decision: defer, blocked_by: "#9",     # identity plausible, entity type undecided
     reviewer: <name>, date: YYYY-MM-DD, evidence: "..."}
same_as:        # two anchored project records are one project (e.g. a moved page)
  - {refs: [<ref>, <ref>], reviewer: ..., date: ..., evidence: ...}
not_same_as:    # keep records apart even if a later rule would join them
  - {refs: [<ref>, <ref>], reviewer: ..., date: ..., evidence: ...}
```

`source_ref` can replace `mention_id` to decide a record on every page. `not_same_as`
overrides every automatic decision, a certain one included. The review queue is
`review/project_review.yaml`.

A manual `same_as` is an identity decision about the mention and may overrule a blocking
signal (for example a link to the activity's own site). The resolution keeps what the rules
saw (`evidence.signals_seen`, positive and negative), so the overruled signal stays visible.
It says nothing about the activity's type; `activity_cues` stay untouched (#9).

`defer` is for a mention whose textual identity is plausible but whose canonical entity class
is not decided (a recurring survey programme is not obviously a one-off Project). It
resolves nothing, creates no relation and stops every automatic rule from firing on that
mention. The status stays `REVIEW_REQUIRED` (the candidate stays visible), the method is
`manual:project_deferred` and the review file lists it under `deferred`, not under
`review_required`. It never overrules a certain (URL) link. The blocking issue (`blocked_by`)
is expected to replace it with a `same_as` or `not_same_as` once decided.

### QA

| Check | Severity |
|---|---|
| `project.without_evidence` (a Project with no anchor) | error |
| `project.title_only_auto` (an automatic decision without a grant or owner signal) | error |
| `project.auto_unexplained` (an automatic decision without rule, two signals or resolver version) | error |
| `project.auto_despite_contradiction` (an automatic decision carrying a blocking signal) | error |
| `temporal.project_interval` (start after end) | error |
| `project.conflicting_grant_ids` | warning |
| `project.multiple_urls` | warning |
| `project.same_title_distinct` | info |
| `project.duplicate_title_groups` (one unresolved title on several pages) | info |
| `project.mention_resolution` (counts by status, method, source and observation) | info |

## Consequences

Release `2026-10-tk-m2-p7`: the same 509 documents as `2026-10-tk-m2-s27`, re-parsed with TK
parser 0.4.0. The re-parse changes only the 56 new `unattached_project_metadata` claims and
the project-page anchors.

| | s27 | p7 |
|---|---|---|
| Projects | 606 (291 title-only, 93 unfetched URL, 222 page-backed incl. the Éghajlat merge) | 223, all page-backed |
| Project mentions | n/a | 783 |
| Resolved by URL / by rule | | 327 / 28 (26 `title_and_owner`, 2 `grant_and_title`) |
| Review required / no candidate | | 8 / 420 (131 link an unfetched page, 289 profile titles only); after the reviewer's decisions (`2026-10-tk-m2-p7r`): 1 deferred to #9 / 420 |
| `PARTICIPATES_IN` / `PRINCIPAL_INVESTIGATOR_OF` | 671 / 112 | 225 / 93 |
| Persons with a project edge | 140 | 92 |
| Co-participation ties | 491 | 446 (52 lost, 7 gained) |
| Person mentions resolved | 798 | 808 (10 more through `own-profile-project`) |

Consequences for analysis:

* **Page-backed only.** Canonical Projects are page-backed only. Profile participation in a
  project without an anchored page is visible as an unresolved mention, not as an edge.
* **Lost ties are a coverage gap, not removed artefacts.** 49 of the 52 lost ties ran
  through Kisebbségkutató Intézet project URLs that profiles link but the crawl never
  fetched, so they are probably real collaborations. Crawling those pages restores them as
  anchored Projects. That is coverage work (#12/#16), not a looser rule.
* **Uneven by institute.** Project resolution by source:

  | Source | Resolved |
  |---|---|
  | SZI | 70% |
  | PTI | 33% |
  | CSS-RECENS | 2% |
  | KI | 0% |

  25 KI researchers lost every project edge. QA warns about the spread.
* **No identity artefacts among the hubs.** No top-15 co-participation hub lost a tie. Hub
  degree comes from a few page-backed projects with long participant lists: the five
  largest produce 297 of the 446 ties on their own. That is a projection question for
  #19, not a resolution question.
* **The Éghajlat false merge had no network effect.** Neither page lists participants, but
  the two editions now keep their own dates, websites and abstracts.
