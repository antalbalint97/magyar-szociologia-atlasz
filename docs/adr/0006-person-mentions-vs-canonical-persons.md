# ADR-0006: Person mentions are evidence; canonical Persons are identities

Status: accepted (2026-10-04) · Issue #4 · Builds on ADR-0001 (claims), ADR-0003 (stable ids)

## Context

In release `2026-10-tk` every person-like source record became a canonical `Person`:

| Source records behind the 364 `Person` entities | Count |
|---|---|
| researcher profile page fetched (identity anchor) | 161 |
| unlinked name on a project/unit page (`name-mention:<slug>@<page>`) | 151 |
| link to a `/kutato/<slug>` profile that was never fetched (404, former staff, legacy host) | 52 |

Counted per observation (person record × document), the release holds **1,021 person
observations outside the person's own profile**: 682 links to a fetched profile, 255
unlinked names, 84 links to an unfetched profile.

The 203 profile-less "people" carry no identity evidence beyond a name string, yet they
behave exactly like researchers: they count as people, get degree and betweenness, and
make up all 191 "orphan person" warnings. A researcher mentioned on several project pages
is split across several nodes (Ságvári Bence: 8 ids, Messing Vera: 7, Kovách Imre: 6).
This biases node counts, degree, brokerage, betweenness, community detection and
cross-institutional bridges. It has to be fixed before any substantive graph analysis.

## Options

**A. One `Person` type with a status** (`VERIFIED_PROFILE`, `RESOLVED_EXTERNAL`,
`MENTION_ONLY`, `HISTORICAL`, `UNRESOLVED`).

* \+ No new type, so queries stay short, and the frontend and Neo4j barely change.
* − The status is a property every query must remember to filter on. Forgetting it
  silently reproduces today's artefacts, which is the failure we are fixing.
* − It still mints a canonical id for every name string. Resolving a mention later means
  merging two `Person`s and retiring an id (ADR-0003 churn); un-resolving means a split.
* − A name observed on ten pages is either ten `Person`s or one guessed `Person`. Neither
  is evidence plus a decision.
* − Mixes two different things in one record: what a page said (stated name, role,
  context) and who someone is (identifiers, profiles, names across sources).

**B. `PersonMention` (evidence) and `Person` (identity), linked by `RESOLVES_TO`.**

* \+ It matches the epistemic layering already in the code: SOURCE → DOCUMENT → CLAIM →
  *source record* → canonical entity. A mention is the canonical, exported form of a
  person record observed in a document, so nothing new is invented between claims and
  entities.
* \+ Re-resolution only adds, moves or removes a `RESOLVES_TO` decision. Canonical
  `Person` ids are untouched, and mention ids are deterministic.
* \+ The analytical graph (`Person`–`Project`–`Person`) contains only identities, by
  construction rather than by filter. The provenance graph
  (`Document → Claim → PersonMention → RESOLVES_TO → Person`) stays fully navigable.
* \+ Unresolved mentions stay queryable as what they are: a name, a page, a role.
* \+ The same pattern serves historical pages, publication author strings, doctoral
  records and project participant lists, which will mostly produce mentions.
* − One more node type and one more file. Counts must always be reported in pairs.
* − Before #5 (evidence-based resolution), most unlinked mentions stay unresolved, so
  some true participation edges are missing from the analytical graph. This is the
  intended conservative behaviour, and it shows up as "unresolved mentions" in QA instead
  of as fake people.

## Decision

**Option B**, confirming the working hypothesis of #4 on the architecture's own terms.

The decision is not generalised to every entity type. Projects show the same need (#7)
and will get their own decision there. Units, topics and methods do not need mentions
on current evidence.

### PersonMention: one observation of a person-like record in one source page

Identity of a mention: (source record ref, observing page URL). Its id is
`pmn_` + hash of both, which is deterministic and stable across re-crawls of the same
page. A mention carries only what the page said:

| Field | Meaning |
|---|---|
| `stated_name`, `normalized_name` | the name string as observed, and its accent-folded key |
| `source_ref`, `source_id` | the staged source record and the source that produced it |
| `source_url`, `document_ids` | the observing page and every retrieval of it |
| `linked_profile_url` | the `/kutato/<slug>` the page linked to, if any |
| `context` | relations the page asserts for this person (type, target, role, snippet, claim ids) |
| `stated_identifiers` | hard ids the page itself states (rare outside profiles) |
| `resolution` | the identity decision (below) |
| `candidate_person_ids` | possible targets from the review queue, never treated as resolved |
| `provenance`, `first_observed_at`, `last_verified_at` | as for every canonical record |

A mention is not a copy of `Person`. It has no titles, positions, biography or profile
fields.

### Resolution decision (`resolution`, projected as `RESOLVES_TO`)

| `status` | Rule (#4 implements the first two; #5 adds evidence-based rules) |
|---|---|
| `DETERMINISTIC` | the mention links to the exact canonical profile URL of a Person, or states the Person's MTMT/ORCID with a compatible name |
| `MANUAL_CONFIRMED` | `same_as` in `review/manual_overrides.yaml` |
| `HIGH_CONFIDENCE_AUTO` | reserved for #5; requires a documented rule and an evidence record |
| `UNRESOLVED` | none of the above; `candidate_person_ids` may list review candidates |

Each decision records `method`, `signals` (the evidence actually used), `decision_source`
(rule id or override) and `decided_at` (build time). There is no free-floating numeric
confidence: a status plus a named rule is what a reader can audit.

### Person: an identity with evidence

A `Person` exists only when at least one **identity anchor** supports it:

* `institutional_profile`: the person's own profile page was fetched;
* `mtmt` / `orcid`: a hard identifier is stated;
* `manual`: a reviewer created or confirmed the identity (future: historical persons,
  external collaborators).

The anchors are listed in `Person.identity_evidence`. Having an institutional profile is
one kind of evidence, not a requirement. Historical, deceased or external researchers can
be Persons through other anchors.

### Projection rules

* A claim about a resolved mention contributes to its Person exactly as before: names
  become alternate names, relations become Person relations. The mention lists those
  claims in its `context`, so the path from edge to page stays visible.
* A claim about an **unresolved** mention does not create a Person or a canonical
  relation. It is kept in the mention's `context` only.
* Canonical `relations.jsonl` therefore contains only identity-to-entity edges.
  `RESOLVES_TO` is exported in the mention record and projected into Neo4j.

### Migration (deterministic rebuild, no edited release files)

1. Adapters mark the record that comes from an entity's own page
   (`SourceRecord.identity_anchor`).
2. Resolution still clusters records with the existing rules. Only clusters that contain
   an anchor (profile, hard id, or manual override) get a `per_` id. Their ids are the
   ones already in `review/identity_map.jsonl`.
3. Every person record observed in a page other than its own profile becomes a
   `PersonMention`. Its resolution comes from its cluster: a cluster with an anchor gives
   `DETERMINISTIC` or `MANUAL_CONFIRMED`, a cluster without one gives `UNRESOLVED`.
4. Identity-map rows for records that no longer map to a Person are dropped. ADR-0003
   still holds for every surviving Person.

### Reporting convention (project-wide)

Person counts are always reported in pairs: canonical Persons, split into profile-backed,
externally resolved and historical; and PersonMentions, split into resolved and
unresolved. "364 people" is never reported again without its breakdown.

### Graph and frontend

* Neo4j: `(:PersonMention)-[:RESOLVES_TO {status, method, …}]->(:Person)` and
  `(:PersonMention)-[:MENTIONED_IN {relation, role}]->(target)`. Analytical queries match
  `(:Person)` and never see mentions. Release files remain the source of truth
  (ADR-0002).
* Explorer: a mention page shows the stated name, the page, the context, the resolution
  status and any candidates. It never shows a biography or an identity that has not been
  established. Unresolved mentions are styled and labelled differently from researchers.

### QA

New checks: Person without identity evidence (error); mention resolved to a missing
Person (error); mention carrying profile-only fields (prevented by the schema); several
deterministic targets for one mention (error); unresolved mention whose linked profile
URL equals a Person's profile URL (error: a URL normalisation bug); duplicate mention ids
(error). The orphan check counts canonical Persons only. Label variants within one
profile (Nyírő Zsanna / Nyírő Zsanna Jozefa) remain one identity and are reported as
such (#6).

## Consequences

* \+ Person counts, orphan rates and network measures describe identities, not strings.
* \+ #5 can add rules that only change `resolution`, without re-minting ids.
* − Until #5, participation edges stated only through unlinked names are absent from the
  analytical graph. The unresolved-mention count measures that gap, and the analysis
  readiness report (#17) must show it.
* − Consumers must read two files (`Person.jsonl`, `PersonMention.jsonl`) to see all
  person-like observations.
