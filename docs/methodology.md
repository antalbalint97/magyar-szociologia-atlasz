# Methodology

## 1. What counts as evidence

Only a retrievable public document (a page, a registry record, a publication, an
archival snapshot, a cited book) or a version-controlled curated file with a named
reviewer. Not evidence: LLM output, our own memory of the field, "well known" facts.
LLMs may later help *parse* ambiguous text, but the resulting claim is `INFERRED`, names
the model in `derivation_method`, and points at the source text it read.

## 2. Coverage strategy

Breadth by institution, not by reputation: an adapter enumerates everyone an
institution lists (all `/kutatok` pages, all departments), so who is "important" is a
result, not an input. The QA seed list (`config/qa_seeds.yaml`) only checks that
cross-boundary researchers are not lost; seeds receive no special treatment.

Phase-1 scope: contemporary snapshot, broad institutional coverage, relations limited to
affiliation, unit, research group, project, topic, method. Co-authorship, PhD genealogy,
historical affiliations and publications come next, each from a source that actually
documents them (MTMT, doktori.hu, archives).

**Coverage is measured, and apart from correctness** (ADR-0009, #12). A release with 0 QA
errors is consistent, not complete. Every release carries `coverage.md` / `coverage.json`
with separate layers: the document universe (set digest, by source and page type), discovery
(the pages the sources point at and what became of them), fetch, parse (`ok`, `empty`,
`error`, unmapped labels), canonicalisation by observing source with an explicit reason for
every unresolved mention, optional-field coverage, and the structural consequences for network
analysis (researchers without a project edge; ties missing because a linked page has no
Project). Every figure names its denominator. A missing optional field is a lower rate, never an
error. QA seeds are sentinels, never a sample. Coverage is exposed, not corrected: nothing is
weighted or imputed. Resolution rates are read by source: a high rate where pages were fetched
and a low one where they were not is a coverage gap, not a resolver result. What the graph can
carry for an analysis is a third question, answered separately (§9, `analysis_readiness.md`).

**What the parsers read, and what they leave** (ADR-0004, ADR-0010, #31). A parser reads a field
from where the page states it, never from where it might be. A label is read only if it is an
existing label (`Label: value` line, or a heading whose text is one); a value under a heading is
the blocks that follow it in the heading's own parent, up to the next heading, so a name near a
label elsewhere on the page is nothing. A line under a heading is read as names only if it looks
like names (two to five capitalised tokens, no organisation, country or programme word; reading
stops at the first part that is not a person), and when in doubt the name stays unparsed: a
missed name is a coverage gap that is counted and listed, a wrong name is a wrong edge. A heading
that is a label but whose value cannot be read is reported in `unmapped_labels`, not guessed.
Every claim read this way records the heading and the line (`project.heading.*`), so a reader can
tell a heading-derived value from a label-line one. New labels are added only with a decision on
what they mean ("Koordinátor" is not "Projektvezető", #36).

**What the crawl fetches.** Pages that a configured listing shows, plus the pages that a
profile of an enabled source links from its project section when the link's host belongs to an
enabled source (one hop, project-page path shape, verified host aliases; ADR-0009). Every link
the crawl did not follow is on the release's frontier with its reason. A page's content is never
inferred from its URL.

## 3. Entity resolution

Implemented in `src/szocatlas/resolution/matcher.py`.

| Signal | Use |
|---|---|
| exact / accent-folded name | blocking only |
| order-free name key ("Júlia Koltai" ~ "Koltai Júlia") | blocking only |
| MTMT author id, ORCID | hard identifiers: agree + compatible name → merge; disagree → never merge |
| same institution family, same profile slug, same e-mail domain | soft signals that rank `possible_match`es between anchored records for review (mention rules: below) |
| unlinked name mention (e.g. "Külső szakértő: X") | always review, never auto-merged |
| publication overlap, topic overlap | later; soft signals only |

Decisions: `confirmed_match`, `possible_match`, `rejected_match`, each with method and
signals, written to `matches.jsonl` in every release. Manual decisions in
`review/manual_overrides.yaml` (`same_as`, `not_same_as`) win over every automatic rule,
and a rejection blocks transitive merges through a third record.

### Persons and person mentions (ADR-0006)

A canonical Person needs an identity anchor (own institutional profile, MTMT, ORCID or a
manual decision). Every other person-like observation is a `PersonMention`, and the
question entity resolution answers is whether a mention `RESOLVES_TO` a Person
(`src/szocatlas/resolution/mentions.py`, ADR-0007, #5).

Candidate generation (same name key, token order, compatible initials, same profile
slug) is separate from the decision. A decision is one of:

| Class | Signals | Resolves? |
|---|---|---|
| Certain | profile link on the canonical host or a verified alias; MTMT/ORCID stated on the page + compatible name; manual `same_as` | yes: `DETERMINISTIC` / `MANUAL_CONFIRMED` |
| Strong | full-name match; profile slug on an inferred alias or another host of the institution family; the Person's own profile lists the project; member of the page's department; page on the Person's institute site; name unique in the institution family | only through a named rule that combines at least two of them, with one viable candidate and no contradiction: `HIGH_CONFIDENCE_AUTO` |
| Weak | name order variant, initials, same institution family | never; they make and rank candidates for review |
| Negative | link to another profile, link with another name, several viable candidates, conflicting hard id, manual `not_same_as`; common surname and different institute as cautions | block automatic rules |

The rules (`slug-inferred-alias`, `slug-family-host`, `own-profile-project`,
`unit-member-unique`, `institute-unique-name`) and their domain assumptions are in
ADR-0007 and `config/resolution.yaml`. Context comes only from certain evidence, so
automatic decisions never chain. Mentions with candidates but no decision are
`REVIEW_REQUIRED` and listed with their evidence in `review/mention_review.yaml`;
mentions without any candidate are `UNRESOLVED`. Neither contributes to the analytical
graph. There is no confidence score: each decision names its rule and signals.

An LLM may propose a candidate or summarise evidence, but its output is never an observed
fact and never a resolution decision by itself.

Org units: identical normalised name on the same site = same entity (unit page vs
"Osztály: …" line on a profile). Across sites, never automatic.

### Projects and project mentions (ADR-0008)

Projects follow the same layering, with project-specific evidence (#7). A canonical
`Project` needs an identity anchor: its own page on an institutional site was fetched, or
a reviewer joined its record to another one. Every other project-like observation is a
`ProjectMention` (`pjm_`): a category-listing article, a line in a researcher profile's
"Projektek" section, a link to a project page that was never fetched. A mention keeps
what the page said: the title as written, the profile owner's role, a stated period, and
raw funder and grant strings.

Same title is never the same project, because editions share titles (`Éghajlatváltozás
és egészség` 2020 and 2021 are two Projects). Candidates come from a shared grant number,
an equal title key (grant, role, period and funder affixes removed), or a long title
prefix. A decision is one of:

| Class | Signals | Resolves? |
|---|---|---|
| Certain | the mention links the Project's own page; manual decision | yes: `DETERMINISTIC` / `MANUAL_CONFIRMED` |
| Strong | same grant number (OTKA/NKFI/NKFIH share one numbering; labels ignored); compatible title; the page links or names the profile owner | only through `grant_and_title`, `grant_and_owner` or `title_and_owner`: `HIGH_CONFIDENCE_AUTO` |
| Weak | same site | never |
| Negative | different grant numbers, disjoint periods (year precision), a link to another page, several viable candidates, manual `not_same_as` | block automatic rules |

Whether a page exists to anchor a Project is a crawl question, not an identity question
(ADR-0009): a mention that links a page the crawl never fetched stays unresolved however good
the rules are, so the coverage report says why each unresolved mention is unresolved (no page
stated, external site, other unit's site, fetch failed, review, deferred to #9).

Title evidence never decides alone. Project rules read only certain evidence and the
names written on project pages, never an automatic person decision. Person rules may use
resolved projects (`own-profile-project`), a one-way dependency, so no decision supports
itself. Unresolved project mentions are listed in `review/project_review.yaml`, together
with titles that stay unresolved on several pages. Their participation claims stay on
the mention and are not in the analytical graph.

Metadata lines in a profile's project section that the markup does not tie to one
project (role, period, grant, funder, section labels) are kept as
`unattached_project_metadata` claims and never attached by proximity. Journals, networks,
programmes and other activities listed as projects keep `activity_cues` for #9 and are
not reclassified here.

Host aliases (`szociologia.tk.mta.hu`, `szociologia.tk.hu` → `szociologia.tk.elte.hu`)
are URL normalisation declared in the registry, not entity resolution: they are the same
page under historical hostnames. An alias is *verified* when a 301 to the same path was
checked (`verified_host_aliases`, #14) and *inferred* otherwise. The parser keeps the URL
as written (`stated_url`), so a profile link that exists only through an inferred alias
is never a certain identity decision (ADR-0007).

## 4. Topics and methods

Researchers' stated research areas are stored verbatim (`stated_research_areas`). The
keyword map in `config/taxonomy/` turns them into `WORKS_ON_TOPIC` / `USES_METHOD` edges
that are `DERIVED`, cite the original claim (`derived_from`), record the matched pattern,
and have confidence ≤ 0.75 (≤ 0.6 for project titles). They are shown dashed and labelled
in the UI. Several topics per person are expected; nobody is forced into one discipline.

Known limits of v0.1: keyword matching is lexical; "Romák" maps to `roma_studies`, which
is an umbrella key. Whether there are several Roma-research traditions (e.g. Pécs
Romology vs Budapest poverty/ethnicity research) is a research question to answer from
the network (co-membership, co-project, co-authorship, institutional location), not from
the taxonomy.

## 5. Intellectual traditions

Not created in phase 1. When added, a `Tradition` node is a hypothesis with
`hypothesis_status`, and each `PART_OF_TRADITION` edge needs an assertion type:
`SELF_DECLARED` (the person says so, cite where), `GENEALOGICAL` (documented supervision
chain), `BIBLIOMETRIC` (community detection run id), `HISTORICAL_LITERATURE` (cite the
book/article and page), or `ANALYST_CODED` (reviewer, date, rationale). Different
assertion types for the same person are kept side by side.

## 6. Time

See ontology §2 (temporal basis). Snapshot pages give `OBSERVED_AT` edges; repeated
crawls extend `first/last_observed_at`; archived snapshots (Wayback) will let us derive
intervals (`DERIVED`). "Active in year X" queries use explicit intervals when present and
observation windows otherwise, and say which.

## 7. Ethics and data protection

Collected: names, academic titles, positions, organisational units, public professional
identifiers (MTMT, ORCID, Scholar), professional profile/CV URLs, stated research areas,
project participation, short bio excerpts from institutional pages.

Not collected, by construction: phone numbers, room numbers, e-mail local parts (only the
domain is kept, as a resolution signal, and it is not published in releases), LinkedIn or
other social media, photos, birth dates unless published in a scholarly biography, and
anything about private life, health, religion or political views. The parser drops
contact lines before they become claims (`test_contact_details_never_extracted`).

Network views imply relationships; every edge therefore names its type, its evidence
and whether it is observed or derived. People may ask for corrections; a correction is a
`disputed_claims.yaml` entry and the source stays cited. GDPR basis for processing public
professional data for research (Art. 6(1)(e)/(f), Art. 89) should be confirmed with the
host institution's DPO before a public release.

## 8. Crawl etiquette

robots.txt honoured (unreachable robots.txt = don't crawl), ≥ 3 s per host, ≤ 400 pages
per source per run, snapshot reuse for 30 days, identifying User-Agent, no JavaScript
rendering unless a site requires it, and terms of service reviewed per source before
`enabled: true`.

## 9. Analysis readiness (#17)

`coverage.md` (§2) says how much of the sources a release holds; the QA report says whether the
build is consistent. Neither says **what the graph can carry**. A release with 0 QA errors and
good coverage figures can still produce artefacts in a network analysis: pseudo-nodes from
unresolved names, a few large projects that are most of the ties, edges that rest on an automatic
identity rule. Every release therefore has an `analysis_readiness.json` / `analysis_readiness.md`
section (written by `szocatlas build`, summarised in `manifest.json` under `analysis_readiness`
and in the quality report; `szocatlas readiness <release>` measures any release, old or new).

How the section is built:

* **Diagnostic, not a verdict.** There are no pass/fail thresholds. A threshold would claim to
  know where an analysis breaks; what can be shown instead is how a result moves when the
  decision is varied (`research/analysis/projection_sensitivity.py`).
* **Every indicator states its definition, its denominator and the analysis it threatens**; a
  value without them is not reported. The list below is generated from the code
  (`INDICATORS`), and a test fails if a code indicator is missing from this page.
* **Read from the release directory only**, so earlier releases are measured with the same code
  and two releases can be compared (docs/analysis_readiness.md §8). Nothing is timestamped and
  no person is named or ranked: the report of an unchanged release is byte-identical.
* **Grades are a reviewed judgement**, per analysis type and per release, in
  docs/analysis_readiness.md (READY / READY_WITH_RESTRICTIONS / NOT_READY). They are not
  computed and not inherited by the next release.

### The graph the measures are about

The Person-Project graph (bipartite) is the **observed layer**: what the pages state. The
Person-Person graph is a **derived projection** of it (two persons are tied when they are listed
on the same project) and is never observed. A project of n persons adds n(n-1)/2 ties, so the
projection is a function of project sizes as much as of collaboration. The bipartite graph stays
the primary representation; any projection result is reported with the bipartite structure
beside it and under three weightings (unweighted, shared-project count, size-discounted
1/(n-1), Newman 2001). Large projects are never removed automatically; removal is a sensitivity
check at thresholds of 8, 9 and 10 persons ("the five largest" is ambiguous: fifth place is
tied).

Every project edge is `OBSERVED`, but the **identity of the person** on it is not equally safe.
The indicators read it from the claims behind the edge: *anchored* (the page links the person's
profile), *certain* (a name mention resolved `DETERMINISTIC` or `MANUAL_CONFIRMED`), *automatic*
(`HIGH_CONFIDENCE_AUTO`). Three versions of the project edges are compared and never merged
silently:

* `default`: every project edge in the release;
* `strict_certain_edges_only`: only edges with an anchored or certain claim (drops edges that
  rest only on an automatic rule);
* `complete_projects_only`: only Projects whose stated leads and participants are all in the
  graph (no `REVIEW_REQUIRED` or `UNRESOLVED` mention on the page).

Project nodes are page-backed (a fetched page is their identity), so no `ProjectMention` status
changes a node; project mentions decide which mentions attach to a Project and which
participations have no edge at all (a title without a page).

### Indicators

**A. Person and institution / unit**

- **A1 persons_with_affiliation**: profile-backed Persons with at least one AFFILIATED_WITH
  relation. *Denominator:* profile-backed Persons per source (a person with two profiles counts
  on both sites). *Threatens:* any institutional composition or affiliation network.
- **A2 persons_with_named_unit**: profile-backed Persons with a MEMBER_OF relation to a unit or
  group, not only to the institute. *Denominator:* profile-backed Persons per source.
  *Threatens:* unit-level composition, cross-unit ties and brokerage between units.
- **A3 persons_with_position**: profile-backed Persons with at least one stated position title
  (a raw string, not normalised, #10). *Denominator:* profile-backed Persons per source.
  *Threatens:* any comparison by position, seniority or staff status (external researchers have
  profiles too).
- **A4 units_in_hierarchy**: units and research groups whose PART_OF chain reaches an
  Institution. *Denominator:* OrganisationalUnits and ResearchGroups. *Threatens:* roll-ups from
  unit to institute; unit-level counts that double count a nested unit.

**B. Person and project (bipartite, the observed layer)**

- **B1 persons_with_project_edge**: profile-backed Persons with at least one PARTICIPATES_IN or
  PRINCIPAL_INVESTIGATOR_OF relation. *Denominator:* profile-backed Persons per source.
  *Threatens:* person-level degree and every projection: a person without an edge is an isolate
  by coverage.
- **B2 projects_with_person_edge**: page-backed Projects with at least one / a PI / at least two
  Persons in the graph. *Denominator:* canonical Projects per source of their page (the host
  serving the page URL). *Threatens:* project-level analysis; ties exist only where a project
  has two or more Persons in the graph.
- **B3 project_participant_subjects**: distinct subjects (an anchored profile or a name mention)
  of lead / participant claims about a project page, by whether they are in the graph: anchored,
  certain mention, HIGH_CONFIDENCE_AUTO mention, or outside it (REVIEW_REQUIRED, UNRESOLVED).
  *Denominator:* distinct (project page, subject) pairs asserted in claims. *Threatens:*
  participant counts and ties of any project whose list is partly outside the graph;
  collaborators without a profile (former staff, outside partners) are missing.
- **B4 edge_identity_basis**: project edges by how the Person was identified: only by anchored
  or certain evidence, anchored plus an automatic mention rule, or only by HIGH_CONFIDENCE_AUTO
  mentions (the relation itself is OBSERVED in every case). *Denominator:* PARTICIPATES_IN and
  PRINCIPAL_INVESTIGATOR_OF relations. *Threatens:* any analysis that treats all edges alike:
  edges resting on an automatic identity rule must be switched on and off to see what depends on
  them.

**C. Person and person (co-participation, a derived projection)**

- **C1 co_participation_ties**: person pairs sharing at least one project (unweighted clique
  projection of the bipartite graph; derived, never observed). *Denominator:* Persons with a
  project edge; Projects with at least two Persons. *Threatens:* density, degree and component
  measures: a project of n persons adds n(n-1)/2 ties.
- **C2 large_project_concentration**: for each threshold k: the Projects with k or more Persons,
  the ties that run through at least one of them, the ties that exist only through them, and the
  Persons whose every tie is only through them (they would be isolates without those projects).
  *Denominator:* co-participation ties; Persons with at least one tie. *Threatens:* every
  tie-based measure: a few large projects can produce most of the structure.
- **C3 tie_weights**: ties by the number of shared projects, and the total weight under
  size-discounted weights (each shared project adds 1/(n-1) for n Persons). *Denominator:*
  co-participation ties. *Threatens:* weighted degree and strength: unweighted and discounted
  weights rank Persons differently.
- **C4 cross_institute**: ties between Persons who share no source institute (a Person with
  profiles on two sites belongs to both), the Projects carrying at least one such tie, and the
  share of those ties that run through the one project contributing most of them. *Denominator:*
  co-participation ties; Projects with at least two Persons; cross-institute ties. *Threatens:*
  claims about cross-institute collaboration or brokerage: the sample is four sites, and one
  large project can be most of the cross-institute structure.
- **C5 components**: connected components of the co-participation projection (Persons with at
  least one tie). *Denominator:* Persons with at least one tie. *Threatens:* path-based measures
  (betweenness, closeness) and community detection.

**D. Topics and methods**

- **D1 persons_with_topic_or_method**: profile-backed Persons with a WORKS_ON_TOPIC /
  USES_METHOD relation. *Denominator:* profile-backed Persons per source. *Threatens:* topic or
  method comparisons between persons, units or institutes.
- **D2 topic_basis**: topic and method relations by epistemic status and derivation method;
  topics with a BROADER link; Persons that state a research area at all. *Denominator:*
  WORKS_ON_TOPIC and USES_METHOD relations; ResearchTopics; profile-backed Persons. *Threatens:*
  any substantive topic claim: the relations are keyword-map derivations of free text.

**I. Identity (applies to every layer)**

- **I1 person_mentions**: person mentions by resolution status, and the share of person-like
  nodes that would exist only as an unresolved name (distinct names of UNRESOLVED mentions not
  equal to a canonical Person's name, over canonical Persons plus those names). *Denominator:*
  person mentions per observing source; canonical Persons plus mention-only names. *Threatens:*
  a name-based graph (pseudo-nodes), and every count of 'people' that mixes mentions with
  Persons.
- **I2 duplicate_persons**: names (accent-folded, and order-free) carried by more than one
  canonical Person; confirmed record merges; person mentions waiting for review and the Persons
  they are candidates for. *Denominator:* canonical Persons. *Threatens:* split identities: one
  real person appearing as two nodes halves their degree.
- **I3 project_mentions**: project mentions by resolution status, mentions per canonical
  Project, and candidate duplicate Projects (same grant id, same accent-folded title).
  *Denominator:* project mentions per observing source; canonical Projects. *Threatens:*
  pseudo-projects and merged or split projects; a ratio far from 1 is not an error but a
  statement of how much of the project layer is mentions.
- **I4 activity_classification**: Projects carrying an activity type (research project, survey
  programme, network, journal...). *Denominator:* canonical Projects. *Threatens:* any
  project-level analysis: programmes, journals and networks listed as projects are counted as
  research projects (#9).
- **I5 edge_provenance**: relations by epistemic status per relation type, and the share
  supported by claims from two or more documents. *Denominator:* relations per type.
  *Threatens:* mixing observed and derived relations in one measure; single-source edges.
- **I6 orphans**: profile-backed Persons with no relation besides AFFILIATED_WITH / MEMBER_OF /
  LEADS / PART_OF. *Denominator:* profile-backed Persons. *Threatens:* isolates that are
  coverage gaps, not findings.

**T. Time**

- **T1 temporal_basis**: relations with an explicit start or end (valid_from / valid_until), and
  Projects with a start date, by relation type. *Denominator:* relations per type; canonical
  Projects. *Threatens:* any longitudinal or period-specific claim: most relations are 'observed
  at crawl time'.

### What the indicators cannot see

Stated in every release (`NOT_MEASURED`): who is missing (the Person universe is each site's
current staff listing, so collaborators and former staff are mentions at best); whether a
project's participant list is complete (B3 counts only what pages state); whether a tie is a
collaboration (sharing a project page is co-listing); role semantics ("Projektvezető",
"Kutatásvezető" and "Koordinátor" are not distinguished, #36); anything about other institutions
(four institutes of one research centre); and the grades themselves.

### Comparing releases

Compare indicator by indicator with the same denominator, and treat the comparison as a
statement about the **pipeline**, not about the world: ties went from 243 to 584 over the
Milestone 2 previews because mentions were resolved and pages were fetched, not because
researchers collaborated more. The project universe changes at #7 (606 project strings to 223
page-backed Projects), so project-level shares are not comparable across that line. The table is
in docs/analysis_readiness.md §8.

### Running it

    szocatlas readiness <release> [--json] [--write]
    python research/analysis/projection_sensitivity.py data/releases/<release> [--json] [--seeds 10]

The first measures the indicators A1-T1 of any release; the second runs the sensitivity checks of
docs/analysis_readiness.md §5 (weightings, identity policy, large projects, communities).

The second needs the `analysis` extra (`pip install -e '.[analysis]'`, networkx). Both read a
release directory and nothing else, and both are deterministic (fixed seeds and node order).

### Reference

M. E. J. Newman, "Scientific collaboration networks. II. Shortest paths, weighted networks, and
centrality", *Physical Review E* 64, 016132 (2001): the 1/(n-1) weight, under which a project of
n persons adds a total weight of n/2 to its n(n-1)/2 ties and a person's strength is the number of
projects with two or more persons that person is on.
