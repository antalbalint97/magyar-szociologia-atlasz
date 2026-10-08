# ADR-0009: Profile project links are discovery evidence; coverage is measured apart from correctness

Status: accepted (2026-10-05) · Issues #16, #12 · Builds on ADR-0001 (claims), ADR-0004
(markup-agnostic parsers), ADR-0008 (project mentions vs canonical Projects)

## Context

After #7 (release `2026-10-tk-m2-p7r`), project identity resolution looked uneven by
institute: 0% of the Kisebbségkutató Intézet (KI) project mentions resolved, 71% at the
Szociológiai Intézet (SZI). The cause was not the identity rules. The crawl only fetched
project pages that a configured category listing shows. SZI and PTI have such listings; KI
does not (its research sits on thematic pages), CSS-RECENS has none. KI researchers' profiles
nevertheless **link their project pages** (47 distinct pages, 75 mentions), and none of those
pages was ever fetched. A project mention that links a page the crawl never fetched can never
resolve to a page-backed Project, whatever the resolver does: no KI researcher had a project edge
or a co-participation tie.

That is a coverage problem, and the build could not see it. QA said "0 errors" while one
institute's project layer was missing. Two things were needed:

1. a general rule that turns an explicit link in a profile into a crawl decision, without
   turning the crawler into a general link follower;
2. measurement of coverage as a separate layer, so "consistent" is never read as "complete".

## Decision 1: a link in a profile's project section is discovery evidence

A researcher's profile states "my project is this page". That is a claim about a page, with
the profile as its provenance. It is not a proof that the page is a project page, and it is not
permission to crawl the host. The crawl follows such a link **one hop**, when all of these hold:

* the link was written in the **project section** of a profile (the adapter collects it while
  parsing the profile; links elsewhere on a page are never candidates);
* the link's host belongs to a source that is **enabled** in `config/sources.yaml` and has an
  adapter, and that adapter's profiles opted in (`follow_profile_project_links`). The source
  registry still defines the allowed hosts; the profile only supplies the path;
* the URL has the **path shape** of one of that source's project pages (TK CMS: one path
  segment, no query, not a menu/staff/category/news segment, not a configured unit page);
* a page that **every** profile linking it wrote on an **inferred** alias is not fetched (the
  alias's path mapping was never verified, #14); verified aliases are followed, and so is a page
  that at least one profile wrote on the canonical host or a verified alias, whatever other
  profiles wrote (#40: the decision is per page, not per statement);
* the page is **not already fetched** (the frontier row says `already_discovered`).

A followed page goes through the owner source's ordinary fetcher (robots.txt, per-host delay,
snapshot reuse) and its ordinary project-page parser, and lands in the owner's staged output
like a listing-discovered page. It becomes a canonical Project because it is a project page
that was fetched (ADR-0008), never because a profile named it. There is no recursion: a newly
fetched page's own links are not followed.

What is **not** followed, by decision rather than by omission:

| Linked page | Scope | Decision |
|---|---|---|
| on an enabled source's host, project-page shape | `in_scope` | fetch |
| on an enabled source's host, another shape (profile, news, category) | `in_scope` | skip, `not_project_path` / `unit_page` |
| a registered unit of the same institution that is not an enabled source (e.g. `jog.tk.elte.hu`) | `other_unit_site` | skip, `source_not_enabled` |
| another site of the same institution's hosts, not in the registry | `other_unit_site` | skip, `site_not_registered` |
| any other host (EU project sites, journals, other universities) | `external` | skip, `external_host` |
| a public grant record (NKFIH registry) | `grant_registry` | skip, `grant_registry_link`; the grant id is still read as a grant statement (ADR-0008) |

Enabling another unit, or an external site, is a scope decision for the project owner, made in
`config/sources.yaml`; this ADR does not make it.

### Frontier rows

Every candidate, followed or not, gets a row in `data/staged/<source>/frontier.jsonl`
and in the release's `frontier.jsonl` (merged across sources, one row per URL):

```
url, kind: profile_project_link, host, stated_urls (as written, before alias normalisation),
scope, owner_source, decision (enqueued | already_discovered | skipped), reason,
host_status (canonical | verified | inferred | unknown),
fetch: {attempted, document_id, http_status, final_url, redirected, retrieved_at, error},
discovered_via: [{type: profile_project_link, source_id, source_document, source_url,
                  project_ref, title}]
```

`discovered_via` lists every profile that stated the link, so a page linked from three profiles
is one row with three provenance entries. Nothing is inferred from a URL: a page that was not
fetched stays "not fetched", with the decision and its reason, and its content is never
guessed from its address. A historical or unreachable host is recorded as it was written
(`stated_urls`), with the registry's `host_status`, which is the **least certain** of the hosts
the profiles used (the row says how weak the weakest statement was; the fetch decision looks at
the strongest); a fetch is recorded only if it was attempted.

`ProjectMention.resolution.reason` takes its explanation for an unresolved linked page from the
frontier ("linked project page not followed (external_host)", "…fetch failed (HTTP 404)",
"linked page was not on the crawl frontier"). The frontier explains; it never resolves.
Resolution of a mention to a newly fetched page is `PROJECT_URL_EXACT` as before: a title is
never used to stand in for a missing page anchor.

### A link written on an inferred alias (#40)

Which pages are fetched and which mentions are certain are two questions about the same
statements, answered separately:

| Question | Unit | Rule |
|---|---|---|
| Is the page fetched? | the page (normalised URL) | refuse (`alias_unverified`) only if no profile wrote it on the canonical host or a verified alias |
| What does the frontier row say? | the page | `stated_urls`: every written form; `host_status`: the least certain of them; `discovered_via`: every profile |
| Does a mention resolve by `PROJECT_URL_EXACT`? | the mention (one profile page) | only if that page wrote the link on the canonical host or a verified alias; one such statement among its own is enough |
| How is the coverage counted? | the distinct URL, as before | the page counts as fetched once; a mention that its own link does not tie to the page is counted by its own resolution |

A profile whose link exists only through an inferred alias is still unverified about *which page it
meant*, even when another profile's trusted link got the page fetched. Its mention is therefore not
a certain decision, the same rule as for profile links (ADR-0007): it stays pending for the
evidence rules of ADR-0008 (a title or a grant id plus an independent observation, such as the page
linking the profile owner), and its reason starts "project link only through an inferred host
alias". If the evidence rules decide nothing, coverage counts it as `linked_page_alias_unverified`,
which is not "fetched, no Project anchored": the Project exists, this mention's link does not reach
it with certainty. Before #40 the build did not look at the written host of a project link, so a
page anchored by a listing would have resolved such a mention by URL.

In release `p31` the rule changes nothing: of 208 observations of a project link in a profile's project section,
84 use a canonical host, 83 a verified alias, 40 a host outside the registry (those pages are never
anchored) and 1 an inferred alias (`jog.tk.hu`, a unit that is not an enabled source, so its page was
never fetched). The replay rebuild is identical to `p31` apart from timestamps and the parser
version string (`tk/0.6.1`).

## Decision 2: parsers read explicit labels only (tk/0.5.0)

The 57 new pages carried markup the parser had not seen: "Támogatási forrás", "Kutatás
időtartama", month-name periods ("2021. június – 2022. május"), a bare funder or period line in a
header block, "Résztvevők" lists that are only links. The parser gained these, with one rule:
a field is taken only when the page labels it. Consequences:

* narrative pages (a numbered "3.1. Levéltári források" heading, an "1918–1945" line in a
  paragraph, a sentence ending in a colon) never produce a funder, a period or participants;
* a lead or participant list is read only when its lines are links to profiles or names under an
  explicit "Résztvevők"/"Kutatásvezető" label; a prose line with a colon is not a label;
* a label no field takes is reported as `unmapped_labels` in the parse report. It is not
  guessed at;
* month-name periods yield dates at month precision ("2021-06"). Day precision is never invented.

Each novel markup is covered by a real, scrubbed page fixture (10 added) and a regression test.

### Canonical dates: precision is not disagreement

Month-precision dates made `conflict.field` warnings jump from 5 to 62: a page's "2021-06" and a
listing's "2021-06-25" are one date at two precisions. `canonical.build._choose` now treats a
coarser ISO date as agreeing with the single finer date it prefixes (`PARTIAL_DATE_FIELDS`:
`start`, `end`). When two different finer dates both extend it (a bare "2021" next to "2021-06"
and "2021-12"), it stays apart, because it cannot be said to agree with either. Real conflicts
still surface (4 remain).

## Decision 3: coverage is a QA layer of its own (#12)

`quality_report` answers "is what we built consistent?". The new `coverage.json` / `coverage.md`
in every release answer "how much of what the sources state did we get?". A release with 0 QA
errors can be far from complete, and the two must never be one number.

Rules of the measurement:

* **Every figure carries its denominator**: `{"n", "of", "rate"}` in the JSON, "n of m" in the
  report; a rate without a denominator is not reported. Missing data has `rate: null`.
* **Layers stay separate**:

| Layer | Question | Denominator |
|---|---|---|
| Document universe | which documents was this release built from? | web documents, per source and page type; set digest |
| Discovery | were the pages the sources point at put on the frontier? | distinct URLs linked from project sections, by scope and owner |
| Fetch | did requested pages come back? | distinct canonical URLs with a retrieval, per source and page type |
| Parse | did the parser find anything in them? | retrieved documents (HTTP < 400); status `ok`, `empty` (only a title), `error`, plus pages with unmapped labels |
| Canonicalisation | did mentions resolve, and if not, why? | person mentions and project mentions, by observing source, by explicit category |
| Fields | how many canonical entities carry each optional field? | profile-backed Persons; canonical Projects by the source of their page |
| Network consequences | what do the gaps do to the graph? | researchers without a project edge, by source |

* **Parse diagnostics are not claims.** Every adapter writes one row per parsed page to
  `diagnostics.jsonl` (release: `parse_report.jsonl`): `document_id, url, source_id, page_type`
  (`profile`, `unit`, `project`, `project_listing`, `listing`), `parser`, `status` (`ok`: at least
  one field beyond the title; `empty`: only a title; `error`: the parser raised, the page was
  skipped and the source went on), `fields` (what the page offered), `unmapped_labels`, `error`.
* **Missing optional fields are coverage, never errors.** QA severities for coverage are
  `warning` or `info`; a coverage finding never fails a build.
* **Unresolved project mentions carry an explicit category**, derived from the mention and the
  frontier (never from the URL's text): `identity_review`, `deferred_to_ontology`,
  `title_only_no_page_link`, `linked_page_external_site`, `linked_page_grant_registry`,
  `linked_page_other_unit_site`, `linked_page_not_project_path`, `linked_page_fetch_failed`,
  `linked_page_alias_unverified` (#40), `linked_page_fetched_no_project`, `linked_page_no_discovery_record`.
* **QA seeds are sentinels, not a sample.** "Present"/"Missing" is reported apart; a seed is
  never in a denominator and passing says nothing about the people not listed (#13).
* **Network consequences are exposed, not corrected**: researchers with no project edge and
  why; the upper bound of ties missing because two researchers' profiles link the same page that
  has no anchored Project; the ties realised, for scale. No weighting or imputation.
* **The source set is part of the release metadata** (`manifest.source_set`: document count,
  digest, by source and page type, retrieval window; `manifest.coverage`). Two releases with
  different digests were built from different crawls, whatever the code did.

This ADR does not decide whether the data is ready for network analysis (#17).

## Consequences

* The listing crawl and profile-link discovery share one fetcher, one parser and one release; a
  page found twice is fetched once. Replays (`ingest --replay`) re-derive the frontier from the
  stored snapshots and reproduce the release byte for byte (apart from `generated_at`).
* Adding a source's `follow_profile_project_links` is one line of configuration; adding a host to
  the crawl is still a registry change reviewed by the owner.
* Coverage numbers now move with the crawl, not only with the code. A release compares to
  another release only through its `source_set`.
* Remaining uncertainty is categorised, not hidden: pages that no profile links (title-only
  mentions) are a different gap from pages that exist elsewhere (external, other unit).

## Not decided here

* Whether a canonical activity is a project, a journal, a network, a newsletter (#9).
* Whether other TK units (`tk_jog`, ReproSoc, Klímacentrum, Családtudomány, Mobilitás) or any
  external site become sources (Milestone 3); and whether the observed redirects of historical
  hosts promote an alias from `inferred` to `verified` (#14 evidence is in the #16 report).
* How to treat sources that disallow automated access (#22).
* The analysis-readiness decision (#17) and substantive network analysis (#19).

## Rejected alternatives

* **Add the 47 KI URLs to the configuration.** Fixes one site's symptom; the next profile edit
  breaks it. The discovery rule fixes the mechanism.
* **Crawl every link on a profile.** Not a bounded crawl, and most links are not projects.
* **Create a Project from a profile's title and link without fetching the page.** That is the
  606-Project problem of ADR-0008 again.
* **Match unfetched pages by title to simulate the missing anchor.** A title is evidence, not an
  anchor; a false merge is worse than an unresolved mention.
* **Report one coverage percentage.** It would hide which layer fails.

## Evidence

Release `2026-10-tk-m2-p7r` (before) and `2026-10-tk-m2-p16` (after; 57 pages added, parser
tk/0.5.0). Both are previews built from the same raw snapshots plus the 57 new ones.

| | p7r | p16 |
|---|---|---|
| Web documents (crawl) | 506 | 563 (KI 52 → 99, PTI 112 → 119, Recens 41 → 44, SZI 301) |
| In-scope project URLs linked from profiles, fetched | 33 of 90 | 90 of 90 |
| Fetch / parse errors on the 57 new pages | | 0 / 0 (no redirects, no HTTP errors) |
| Projects | 223 | 280 (every old id intact) |
| Project mentions resolved | 362 of 783 (46%) | 450 of 783 (57%) |
| KI project mentions resolved | 0 of 114 | 74 of 114 (65%) |
| Mentions resolved before that resolve to another Project now | | 0 of 362 |
| `PARTICIPATES_IN` / `PRINCIPAL_INVESTIGATOR_OF` | 231 / 93 | 341 / 136 |
| Researchers with a project edge | 94 of 160 | 120 of 160 (KI 0 → 25) |
| Co-participation ties | 451 | 551 (100 gained, 0 lost) |
| Person mentions | 1,021: 808 resolved | 1,188: 908 resolved (the new pages list collaborators with no profile) |
| QA | 0 errors, 38 warnings | 0 errors, 37 warnings |
