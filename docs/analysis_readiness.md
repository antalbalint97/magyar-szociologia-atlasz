# Analysis readiness (#17)

**Assessed release:** preview `2026-10-tk-m2-p31` (TK parser tk/0.6.0, source-set digest
`6e7fd8757ffc5c44`, 563 web documents, retrieved 2026-10-04/05), compared with `2026-10-tk-m2`,
`-p5`, `-p7r` and `-p16`. **Status: proposed grades, for review in PR #26.** The numbers
are computed; the grades are a judgement made from them. A grade belongs to one analysis type on
one release, and a new release is read again, never inherited.

Where the numbers come from (both read a release directory and nothing else, so any release can be
measured and two can be compared):

    szocatlas readiness <release>                                     # indicators A1-T1, also written by `build`
    python research/analysis/projection_sensitivity.py data/releases/<release>   # weightings, identity policy, large projects, communities

Indicator definitions, denominators and the analysis each one threatens: docs/methodology.md §9
and the generated `analysis_readiness.md` of every release. Percentages are whole percents from
the counts, half up, each with its denominator.

## 1. Decision

**The dataset is not declared ready.** Exploratory, descriptive work on the bipartite
Person-Project layer and on its derived Person-Person projection is `READY_WITH_RESTRICTIONS`.
Everything that ranks persons, compares institutes, reads roles, positions, project types, topics
or methods, or follows anything over time is `NOT_READY`. No analysis type is `READY`.

| layer | analysis type | grade | the reason in one line |
|---|---|---|---|
| A | A-1 headcount and composition by institute (a snapshot of current staff listings) | READY_WITH_RESTRICTIONS | four institutes of one centre; current staff only |
| A | A-2 composition by unit | READY_WITH_RESTRICTIONS (KI, PTI, SZI); NOT_READY (CSS-RECENS) | a named unit: CSS-RECENS 1 of 24 (4%), the others 86-98% |
| A | A-3 position, rank, seniority | NOT_READY | position titles are raw strings (#10) |
| A | A-4 who joined or left | NOT_READY | none of 289 affiliation relations has a date; one snapshot |
| B | B-1 bipartite description within a source: projects per person, persons per project | READY_WITH_RESTRICTIONS | 36% of stated participants are outside the graph (B3) |
| B | B-2 comparing institutes' participation | NOT_READY | researchers with a project edge range from 21% to 90% by template, not by behaviour |
| B | B-3 roles (lead, participant, coordinator) | NOT_READY | label semantics undecided (#10) |
| B | B-4 project attributes (funder, grant, duration) | NOT_READY | funder on 40%, grant id on 11%, period on 60% of Projects; field conflicts (#11) |
| B | B-5 project types (research project, programme, network, journal) | NOT_READY | no activity type is modelled: 0 of 280 (#9) |
| B | B-6 participation over time | NOT_READY | dates partial (#11); most edges are "observed at crawl time" |
| C | C-1 structure of the projection: ties, components, size and degree distributions | READY_WITH_RESTRICTIONS | with the checks of §3; 55% of ties exist only through 7 projects |
| C | C-2 weighted ties and strength as distributions | READY_WITH_RESTRICTIONS | prefer size-discounted weights; strength then equals the bipartite degree |
| C | C-3 person-level centrality, as a ranking or as importance | NOT_READY | degree and discounted strength agree at rho 0.715; remove 7 projects and the top decile changes almost entirely (§5) |
| C | C-4 community detection | READY_WITH_RESTRICTIONS | exploratory only; communities partly restate institutes (NMI 0.572-0.674) |
| C | C-5 cross-institute collaboration, brokerage, integration | NOT_READY | 68 of 83 cross-institute ties run through one project of 20 persons |
| C | C-6 network statistics of two releases read as change | NOT_READY | releases differ by pipeline (§8), not by the world |
| D | D-1 topic or method prevalence by person, unit, institute | NOT_READY | keyword-derived; coverage 16% (SZI) to 93% (KI); false positives measured (#15) |
| D | D-2 person-topic or topic co-occurrence networks | NOT_READY | same |
| I | I-1 analysis on canonical Persons with mention statuses reported | READY_WITH_RESTRICTIONS | 30% of person mentions are outside the graph |
| I | I-2 graphs with nodes for unresolved mentions or name strings | NOT_READY | 187 of 347 person-like nodes (54%) would be names |
| T | T-1 snapshot "as of the crawl" | READY_WITH_RESTRICTIONS | state it as "as of the crawl" |
| T | T-2 longitudinal analysis | NOT_READY | see A-4, B-6 |

**What this permits.**

* **#19 (first network-analysis notebook)** may start, **only as exploratory description** of B-1,
  C-1, C-2 and C-4, with every check in §3 reported next to every result. It may not produce a
  ranking, a cross-institute claim, an institute comparison, a topic or method result or a trend.
  Nothing of #19 has been started.
* **The public interface (#32)** may show person and project pages, the bipartite graph, and the
  Person-Person projection as an opt-in derived view labelled "listed on the same project page"
  with large projects flagged. It may not show a ranking, a "top researcher" list, node size or
  colour by centrality, "bridge" or "influential" labels, community names, cross-institute
  integration figures, institute density comparisons, topic profiles read as findings, or a node
  for an unresolved mention. Every percentage keeps its denominator.

## 2. What the grades mean

* `READY`: the indicators show no known artefact that can change the result of this analysis type,
  and the sensitivity checks agree. **Not reached by any type on p31**: the person universe is
  incomplete, activity types and role semantics are not modelled, and the topic layer is derived.
* `READY_WITH_RESTRICTIONS`: it may be run and reported if every restriction listed for it is
  applied and the required checks (§3) are shown with the result. The result then describes what
  the four sites' pages state, not Hungarian sociology.
* `NOT_READY`: a known artefact can produce the result by itself, or the analysis rests on
  something that is not modelled. Exploring the data to see the artefact is fine; presenting the
  result as a finding is not.

## 3. Required sensitivity checks (for every network result)

* **S1 Bipartite first.** Report the Person-Project structure (project sizes, projects per person)
  beside any projection result. The bipartite graph is the observed layer; the projection is derived.
* **S2 Weighting.** Report unweighted, shared-project count and size-discounted (1/(n-1), Newman
  2001) weights, or say which one and why. Size-discounted strength equals the number of projects
  with two or more persons, so a "weighted degree" under it is the bipartite degree.
* **S3 Large projects.** Report the result with and without the projects of 8, 9 and 10 or more
  persons (thresholds, not "the five largest": fifth place is tied), with the share of ties that
  exist only through them and the persons who become isolates. Removal is a check, not a
  correction: a large project is data.
* **S4 Identity policy.** Report `default`, `strict_certain_edges_only` and `complete_projects_only`
  (docs/methodology.md §9) side by side. Never merge them silently, and never mix `OBSERVED` with
  `DERIVED` (topic, method) edges in one measure.
* **S5 Communities.** Run at least 10 seeds, report the lowest agreement between them, the NMI with
  the institute and unit partitions and the modularity of the institute partition itself.
* **S6 The release.** Name the release id, source-set digest and parser version in the result. A
  claim about change needs two releases and the explanation of what changed in the pipeline (§8).

## 4. The layers

### A. Person - institution / unit

*Evidence (p31).* All 160 canonical Persons are profile-backed and have an `AFFILIATED_WITH`
relation (A1). A named unit: KI 27 of 28 (96%), PTI 50 of 51 (98%), SZI 50 of 58 (86%),
CSS-RECENS 1 of 24 (4%) (A2); all 128 of 160 (80%). A position title is stated for 160 of 160 (A3),
as a raw string. All 41 units and research groups reach an Institution through `PART_OF` (A4).
None of the 161 `AFFILIATED_WITH` or 128 `MEMBER_OF` relations carries a date (T1). The universe is
each site's current staff listing at crawl time; one person has profiles on two sites and counts
once among the 160 and on both sites in per-source rows.

*Limits.* Four institutes of one research centre. Former staff and outside collaborators are
mentions, not Persons. CSS-RECENS has no unit pages in the crawl, so unit-level comparisons cover
KI, PTI and SZI only.

*May:* counts and shares per institute and, for KI, PTI and SZI, per unit, each with its
denominator and the label "current staff listed on the site at crawl". *Must not:* read the counts
as the size of the discipline or of an institute's research community; compare unit structure
including CSS-RECENS; read a position string as a rank. *Blockers:* #10 (positions), Milestone 3
(more institutions), #24 (history).

### B. Person - project (bipartite)

*Evidence (p31).* 120 of 160 researchers (75%) have a project edge: SZI 52 of 58 (90%), KI 25 of 28
(89%), PTI 39 of 51 (76%), CSS-RECENS 5 of 24 (21%) (B1). 208 of 280 Projects (74%) have a Person in
the graph, 175 (63%) a PI, 92 (33%) two or more Persons (B2); with two or more: KI 14 of 47 (30%),
PTI 19 of 37 (51%), SZI 59 of 193 (31%), CSS-RECENS 0 of 3. The pages state 825 distinct
(project, participant) pairs; 529 (64%) are in the graph (361 anchored by a profile link, 168 by an
automatic name rule) and **296 (36%) are not** (249 with no candidate Person, 47 in review) (B3).
Of 601 project edges, 167 (28%) rest only on an automatic identity rule (B4). Project nodes are
page-backed; 282 project mentions are titles without a page and produce no edge (SZI 103, PTI 86,
CSS-RECENS 59, KI 34). No activity type is modelled (0 of 280, #9). Explicit dates: 238 of 423
`PARTICIPATES_IN` (56%), 104 of 178 `PRINCIPAL_INVESTIGATOR_OF` (58%); a start date on 167 of 280
Projects (60%) (T1).

*Limits.* A person without an edge is an isolate by coverage, not a finding. A project list that is
partly outside the graph yields fewer ties than the page implies. The lead label is read as stated:
"Koordinátor" is not read at all (5 SZI pages) and the singular "Résztvevő" reads profile links
only (5 pages), both undecided (#10).

*May:* distributions of projects per person and persons per project within one source, with B1-B3
beside them; the bipartite graph. *Must not:* compare institutes' participation rates or degrees
(the templates differ, §7); read a missing edge as a missing participation; treat every Project as a
research project; read "PI" as the grant's formal principal investigator. *Blockers:* #10, #11, #9,
#28, #16 (remaining pages).

### C. Person - person (a derived projection)

Detail in §5. *Evidence (p31).* 584 ties among 113 persons (of 120 with a project edge) over 92
projects with two or more persons; 4 components, the largest holding 107 of 113 (95%). Median degree
8, maximum 29. Ties inside one institute: SZI 295, PTI 118, KI 87, CSS-RECENS 1; **across
institutes 83** (14%). **7 projects of 8 or more persons (sizes 8, 8, 8, 9, 10, 13, 20) carry 376
ties (64%); 322 (55%) exist only through them**, and 10 persons have no tie outside them. 3 projects
of 10 or more carry 298 (51%); 235 (40%) exist only through them.

*Limits.* A tie is co-listing on a project page: it can mean working together, belonging to the same
grant or sitting in the same consortium. A project of n persons adds n(n-1)/2 ties (190 for the
project of 20). The graph is incomplete by the 36% of participants outside it.

*May:* C-1, C-2 and C-4 with S1-S6. *Must not:* rank persons; call a degree "importance" or
"influence"; call a community a school or a tradition; report cross-institute ties as integration;
read the projection as the collaboration network. *Blockers:* #28 and Milestone 3 (who is missing),
#9 and #10 (what a project and a role are).

### D. Topics and methods

*Evidence (p31).* 70 of 160 Persons (44%) have a topic relation and 13 (8%) a method relation. By
site, topic relations: KI 26 of 28 (93%), CSS-RECENS 14 of 24 (58%), PTI 22 of 51 (43%), SZI 9 of 58
(16%); persons that state a research area at all: KI 93%, PTI 90%, CSS-RECENS 67%, SZI 21% (D1, D2).
All 420 topic and method relations are `DERIVED` by `taxonomy_keyword_map/0.1.0` from free text; 2
of 34 topics have a `BROADER` link. A precision datapoint from the frontend work (#15, release
`p16`): 7 of the 22 edges into Romakutatás match "román/Románia", not Roma. Recall is not measured.

*Grade:* `NOT_READY` for D-1 and D-2. Differences between institutes would measure which profile
template has a research-area field. *Allowed:* inspecting a derived relation together with the
stated text behind it, labelled derived. *Blockers:* #15 (evidence classes, recall, false positives).

### Identity (applies to every layer)

*Evidence (p31).* 160 canonical Persons; no name is carried by two of them (I2); 9 confirmed record
merges. 1,435 person mentions: 758 certain (53%), 248 by an automatic rule (17%), 67 in review (5%),
362 with no candidate (25%); **429 (30%) are outside the graph** (I1). If the 187 distinct
unresolved names were nodes they would be 54% of 347 person-like nodes. Project nodes are page-backed,
so no project-mention status changes a node; 333 of 783 project mentions (43%) have no Project, each
with a stated reason in `coverage.md` (I3).

*May:* analyses on canonical Persons, with the mention statuses reported. *Must not:* a name-based
graph, nodes for unresolved mentions, merging mentions by name across pages. A false merge is worse
than an unresolved mention (docs/methodology.md §3), so the sensitivity runs only ever remove
automatic identifications, never add any.

### Time

*Evidence (p31).* Affiliations carry no dates. Explicit dates on 56-58% of project edges and a start
on 60% of Projects (T1); partial dates are an interim rule (#11). The release is a snapshot of pages
retrieved on 2026-10-04/05.

*Grade:* snapshot description `READY_WITH_RESTRICTIONS`; anything longitudinal `NOT_READY`.

## 5. The projection: what moves when a decision moves

`research/analysis/projection_sensitivity.py`, release `p31`, 120 persons with a project edge on 208
Projects with a person. Seeds and node order are fixed; the output is aggregate and names no person.
The same script on `p16` and `p7r` gives the same picture with different numbers (published with
the reports).

**Project sizes** (persons per project: projects): 1: 116, 2: 41, 3: 18, 4: 13, 5: 8, 6: 1, 7: 4,
8: 3, 9: 1, 10: 1, 13: 1, 20: 1. Projects per person (number of projects: persons): 1: 26, 2: 26,
3: 20, 4: 11, 5: 14, 6: 6, 7: 3, 8: 4, 9: 4, 11: 1, 12: 1, 13: 2, 14: 2.

**Weightings of the same 584 ties**

| weighting | total weight | share from projects of 8+ / 9+ / 10+ persons | weight across institutes |
|---|---|---|---|
| unweighted (1 per pair) | 584 | (a tie can come from several projects) | 14% |
| shared-project count | 785 | 55% / 44% / 40% | 11% |
| size-discounted 1/(n-1) | 169 | 22% / 15% / 13% | 5% |

**Do two scorings of the same persons agree?** (Spearman rho; overlap = Jaccard of the top decile,
12-15 persons)

| scorings | rho | top-decile overlap |
|---|---|---|
| degree vs strength (shared-project count) | 0.965 | 0.600 |
| degree vs strength (size-discounted) | 0.715 | 0.350 |
| degree vs projects per person | 0.560 | 0.368 |
| betweenness: hops vs 1/shared-project count | 0.970 | 0.500 |
| betweenness: hops vs 1/size-discounted | 0.909 | 0.412 |

**Identity policy and large projects, each against the default edges** (unweighted)

| version | persons with edge | ties | across institutes | components (largest) | rho degree | top-decile overlap | rho discounted strength | community NMI with default |
|---|---|---|---|---|---|---|---|---|
| default (every edge) | 120 | 584 | 83 | 4 (107) | | | | |
| strict (anchored or certain edges only) | 113 | 473 | 79 | 6 (93) | 0.877 | 0.524 | 0.723 | 0.834 |
| complete projects only | 99 | 216 | 12 | 6 (58) | 0.442 | 0.182 | 0.540 | 0.716 |
| projects of 8+ persons removed (7) | 120 | 262 | 8 | 6 (76) | 0.515 | 0.087 | 0.901 | 0.650 |
| projects of 9+ removed (4) | 120 | 323 | 15 | 5 (98) | 0.560 | 0.036 | 0.954 | 0.738 |
| projects of 10+ removed (3) | 120 | 349 | 15 | 5 (99) | 0.614 | 0.091 | 0.959 | 0.751 |

**Communities** (Louvain, seed 0; 113 persons in ties; seed stability is the lowest NMI between
seed 0 and nine other seeds)

| graph | communities | modularity | modularity of the institute partition | NMI with institute | NMI with unit | seed stability |
|---|---|---|---|---|---|---|
| default, unweighted | 8 | 0.547 | 0.445 | 0.674 | 0.637 | 0.927 |
| default, shared-project count | 9 | 0.555 | 0.482 | 0.671 | 0.618 | 0.795 |
| default, size-discounted | 10 | 0.675 | 0.518 | 0.597 | 0.581 | 0.872 |
| strict, unweighted | 10 | 0.599 | 0.477 | 0.593 | 0.579 | 0.939 |
| complete projects only, unweighted | 10 | 0.663 | 0.537 | 0.598 | 0.654 | 0.940 |
| 8+ removed, unweighted | 11 | 0.661 | 0.573 | 0.572 | 0.608 | 0.798 |

*What follows.*

1. **Who looks central depends on the weighting and on seven projects.** Degree and discounted
   strength agree at rho 0.715 (top-decile overlap 0.350). Remove the seven projects of 8 or more
   persons and degree keeps rho 0.515 but its top decile is almost entirely different (overlap
   0.087), while discounted strength keeps rho 0.901. A degree ranking of persons is a ranking of
   who sits on a large project. That is why C-3 is `NOT_READY`.
2. **The discounted weight adds nothing to the bipartite degree.** Under 1/(n-1) each project adds
   exactly 1 to the strength of each of its persons (checked on every person). The size-discounted
   graph is useful for ties, not as a second measure of persons.
3. **Cross-institute structure is one project.** Of the 83 ties across institutes, 68 (82%) run
   through the project of 20 persons ("Integrációs és dezintegrációs folyamatok a magyar
   társadalomban", an SZI page that lists persons of PTI and CSS-RECENS), 7 through a project of 8
   (KI-SZI), and 8 through four projects of 2 to 5 persons. 75 (90%) exist only through projects of
   8 or more; remove them and 8 remain. It is not an identity artefact (79 of the 83 survive the
   strict policy) but a concentration artefact, which is why C-5 is `NOT_READY` and why the
   complete-projects variant (which drops that project, since part of its list is outside the
   graph) keeps only 12.
4. **The edges that rest on an automatic rule move the top decile.** The strict policy keeps rho 0.877
   for degree but a top-decile overlap of 0.524, down from 0.870 on `p16`: #31 added 33 ties, all
   through SZI participants resolved by an automatic rule (they vanish under the strict policy, which
   has 473 ties on both releases). The rule is precise on what was audited (§6) but the structure
   depends on it, so S4 is a requirement.
5. **Communities are not just institutes, and not independent of them.** Louvain beats the institute
   partition on modularity (0.547 against 0.445; 0.675 against 0.518 discounted), so there is structure
   inside institutes; but NMI with the institute is 0.572-0.674 and the structure changes when large
   projects go (NMI 0.650-0.751 with the default partition). Partitions are stable across seeds
   (lowest NMI 0.795-0.940). Treat them as an exploratory picture.
6. **Small numbers.** The top decile is 12-15 persons and a Spearman rho on 120 persons moves by a
   few hundredths with one project; read the tables for what is large (0.087 against 0.901), not for
   the second decimal.

## 6. Identity sensitivity (what the person mentions do to the graph)

Three versions of the project edges, never merged (S4):

| version | what is in | persons with edge | ties |
|---|---|---|---|
| default | every project edge: anchored profile links, certain mentions, `HIGH_CONFIDENCE_AUTO` mentions | 120 | 584 |
| strict | only edges with an anchored or certain claim (drops 167 edges that rest only on an automatic rule; 7 persons then have no edge) | 113 | 473 |
| complete projects | only the 120 Projects whose stated participants are all in the graph (86 with one person, 34 with two or more) | 99 | 216 |

Person mentions (1,435), reported separately for each status: `DETERMINISTIC` 758 (53%),
`HIGH_CONFIDENCE_AUTO` 248 (17%), `REVIEW_REQUIRED` 67 (5%), `UNRESOLVED` 362 (25%). Certain evidence
alone resolves 53%; with the automatic rule 70%; 30% are outside the graph. By source (resolved
including the automatic rule): CSS-RECENS 58 of 58 (100%), KI 179 of 247 (72%), PTI 314 of 448 (70%),
SZI 455 of 682 (67%). Edges that rest only on an automatic rule: SZI 163 of 349 (47%), PTI 3 of 116
(3%), KI 1 of 133 (1%), CSS-RECENS 0 of 3.

*Precision of the automatic rule on what #31 added* (an audit of plausibility, not a ground truth).
Of the 247 new heading-derived person mentions (112 distinct names) all 112 strings read as person
names. 98 mentions (26 distinct persons) were resolved by `institute_unique_name` (97) or
`own_profile_project` (1): each has an exact or normalised name match, the same institute and a name
unique in the institution family, and none has a negative signal. 43 of the 247 mentions are followed
by a parenthetical (an affiliation or a placeholder): 41 have no candidate and 2 are in review, none
resolved. No false merge was found. The residual risk the data cannot show is a namesake outside the
staff universe. 19 mentions (7 distinct names: common surnames, or a namesake at another institute)
went to review; 130 (79 names) have no candidate.

## 7. Source bias

Differences between the four sites in what their templates show and what the parser reads. A
comparison between institutes measures these before it measures anything else.

| | SZI | KI | PTI | CSS-RECENS |
|---|---|---|---|---|
| researchers (profile-backed; one person on two sites counts on both) | 58 | 28 | 51 | 24 |
| unit pages; researchers with a named unit | 3; 50 (86%) | 2; 27 (96%) | 3; 50 (98%) | 0; 1 (4%) |
| researchers stating a research area; with a topic relation | 12 (21%); 9 (16%) | 26 (93%); 26 (93%) | 46 (90%); 22 (43%) | 16 (67%); 14 (58%) |
| project pages (share of the 280) | 193 (69%) | 47 (17%) | 37 (13%) | 3 (1%) |
| project mentions resolved; titles with no page | 298 of 417 (71%); 103 | 74 of 114 (65%); 34 | 74 of 186 (40%); 86 | 4 of 66 (6%); 59 |
| project pages with a PI; participants; period; funder | 56%; 53%; 52%; 28% | 83%; 100%; 70%; 55% | 76%; 92%; 86%; 76% | 0%; 100%; 33%; 100% (3 pages) |
| researchers with a project edge | 52 (90%) | 25 (89%) | 39 (76%) | 5 (21%) |
| stated participants outside the graph | 194 of 507 (38%) | 57 of 163 (35%) | 45 of 152 (30%) | 0 of 3 |
| edges resting only on an automatic identity rule | 163 of 349 (47%) | 1 of 133 (1%) | 3 of 116 (3%) | 0 of 3 |
| person mentions with no candidate (former staff or outside collaborators, #28) | 180 of 682 (26%) | 62 of 247 (25%) | 120 of 448 (27%) | 0 of 58 |
| project pages parsed empty; with a labelled line no field took | 8; 78 of 193 | 0; 42 of 47 | 1; 31 of 37 | 0; 2 of 3 |

*Direction of the bias.* **SZI** is most of the project layer (193 of 280 Projects, 295 of 584 ties
are SZI-SZI); its participants are mostly plain-text names, so its ties are the most sensitive to
the identity rule (S4); its profile template rarely states a research area, so any topic result
about SZI is about the template. **KI** has the fullest project template; a third of its stated
participants are outside the graph (former staff or outside partners) and 34 titles have no page;
KI thematic research pages are not read (#16). **PTI** has period and funder on most projects, and
86 titles with no page. **CSS-RECENS** is structurally under-observed: profiles give titles without
links, 3 project pages exist, no unit pages; one tie inside it and 37 to other sites, 36 of them
through the 20-person project. Treat it as outside any institute comparison. Known SZI template
gaps, listed rather than silent: 2 pages with a `<p>` used as a heading, 5 pages with
"Koordinátor", 5 with the singular "Résztvevő", 2 of the 86 heading pages that yield no name
(ADR-0010).

## 8. Releases compared (before and after #5, and since)

| indicator | `m2` (#4) | `p5` (#5) | `p7r` (#7) | `p16` (#16) | `p31` (#31) |
|---|---|---|---|---|---|
| Canonical Persons | 161 | 161 | 160 | 160 | 160 |
| Canonical Projects | 606 | 606 | 223 | 280 | 280 |
| Person mentions | 1,021 | 1,021 | 1,021 | 1,188 | 1,435 |
| Project mentions | - | - | 783 | 783 | 783 |
| B1 researchers with a project edge | 137/161 (85%) | 141/161 (88%) | 94/160 (59%) | 120/160 (75%) | 120/160 (75%) |
| B2 Projects with two or more Persons | 87/606 (14%) | 92/606 (15%) | 48/223 (22%) | 65/280 (23%) | 92/280 (33%) |
| B3 stated participants outside the graph | 151/829 (18%) | 95/829 (11%) | 90/393 (23%) | 147/578 (25%) | 296/825 (36%) |
| B4 edges resting only on automatic rules | 0/710 (0%) | 40/782 (5%) | 39/324 (12%) | 43/477 (9%) | 167/601 (28%) |
| C1 co-participation ties | 243 | 488 | 451 | 551 | 584 |
| C2 ties only through projects of 8+ Persons | 44/243 (18%) | 270/488 (55%) | 278/451 (62%) | 333/551 (60%) | 322/584 (55%) |
| C4 cross-institute ties | 8/243 (3%) | 79/488 (16%) | 76/451 (17%) | 83/551 (15%) | 83/584 (14%) |
| C5 components (largest) | 11 (43) | 9 (91) | 5 (78) | 5 (101) | 4 (107) |
| I1 person mentions resolved by certain evidence | 682/1021 (67%) | 668/1021 (65%) | 668/1021 (65%) | 758/1188 (64%) | 758/1435 (53%) |
| I1 person mentions outside the graph | 339/1021 (33%) | 224/1021 (22%) | 213/1021 (21%) | 280/1188 (24%) | 429/1435 (30%) |
| I1 mention-only share of person-like nodes | 70/231 (30%) | 67/228 (29%) | 67/227 (30%) | 119/279 (43%) | 187/347 (54%) |
| I2 confirmed merges / mentions waiting for review | 12 / 0 | 12 / 53 | 9 / 42 | 9 / 48 | 9 / 67 |
| I3 project mentions resolved | - | - | 362/783 (46%) | 450/783 (57%) | 450/783 (57%) |
| I6 orphans | 13/161 (8%) | 9/161 (6%) | 21/160 (13%) | 19/160 (12%) | 19/160 (12%) |

*Reading it.* These are changes in the pipeline, not in the world. **#5** (`m2` to `p5`): ties 243
to 488 and cross-institute ties 8 to 79 on the same pages. The identity layer attached 62 more
(Person, Project) pairs (622 to 684, none lost; 40 project edges now rest only on an automatic
rule), and a person added to a project of n adds up to n-1 ties: 29 of the 62 pairs sit on two
projects that grew from 1 to 20 and from 3 to 13 persons, and 226 of the 245 new ties exist only
through those two. Stated participants outside the graph fell from 18% to 11%. **#7**: 606 project
strings became 223 page-backed Projects, so project-level shares are not comparable across that
line; ties fell 488 to 451. **#16**: 57 linked project pages were fetched, ties 451 to 551.
**#31**: 247 new heading-derived person mentions, ties 551 to 584, stated participants outside the
graph 25% to 36% (more participants were *seen*, and most of the new ones are not Persons of the
graph), and the share of edges resting only on an automatic rule 9% to 28%. The concentration
through projects of 8 or more persons stays between 55% and 62% from `p5` on, and the share of
person-like nodes that would be mention-only names rose from 29% to 54% as more pages were read.
A network statistic is therefore a statement about *this release*; S6 applies, and #18
(release-to-release diffs separating substantive from pipeline changes) would make the distinction
mechanical.

## 9. Exploratory metrics

| metric | allowed as | not as |
|---|---|---|
| degree (distinct co-participants) | a distribution; a check against S3 | a ranking; importance, influence, prominence |
| weighted degree (strength) | a distribution, under the named weighting (S2) | a second measure of persons beside the bipartite degree (under 1/(n-1) it is the same number) |
| bipartite degree (projects per person, persons per project) | the primary descriptive measure of the observed layer | a measure of productivity or output |
| betweenness | a distribution; the structural position inside this sample | brokerage between institutes (§5, point 3); a ranking |
| connected components | counts and sizes, with S3 | evidence that the field is "integrated" |
| cross-institute participation | a descriptive count with its single-project concentration shown | collaboration between institutes; integration |
| brokerage, cross-unit ties | descriptive, with S3 | a finding about units or persons |
| exploratory community detection | a picture with S5 | schools, traditions, groups of colleagues |

Not allowed in any output: a list of "the most important", "most influential" or "most central"
sociologists, a ranking of persons, units or institutes by a network measure, or a substantive
conclusion about Hungarian sociology.

## 10. What would change a grade

| not ready | blocker | what would show it is lifted |
|---|---|---|
| C-3 person-level centrality | #28, Milestone 3 (who is missing), a decision on large projects | a ranking that survives S2, S3 and S4 (today rho 0.515 and a top-decile overlap of 0.087 when 7 projects go) |
| C-5 cross-institute claims | Milestone 3, #28 | cross-institute ties that do not depend on one project |
| B-2 institute comparisons | #31 follow-ups, #16, #28 | comparison on fields all four templates offer, with equal observation |
| A-3, B-3 positions and roles | #10 | roles and positions modelled, not strings |
| B-4, B-6, T-2 dates and attributes | #11, #24 | typed date comparison; dated affiliations |
| B-5 project types | #9 | `activity_type` on Projects |
| D-1, D-2 topics and methods | #15 | recall and false-positive rates per evidence class |
| C-6 change between releases | #18 | release diffs that separate pipeline from substance |

## 11. Limits of this assessment

* **A sample of four institutes of one centre, 160 persons.** Everything above describes it.
* **Plausibility, not ground truth,** for identity: the 98 automatic resolutions of #31 were read
  one by one, and the rule's residual risk (a namesake outside the staff universe) is not
  observable here. There is no estimate of recall.
* **Thresholds 8, 9 and 10** come from the size distribution (there is a gap after 10: 13 and 20),
  not from theory. Louvain is the only community method tried; no null model was run.
* **The `complete projects` policy is conservative:** it also drops projects whose absent
  participants are real outside collaborators, not errors. It shows how little of the graph is fully
  observed (34 projects with two or more persons), not what the truth is.
* **The grades are one reviewer's judgement** and are open to change on review of PR #26.
