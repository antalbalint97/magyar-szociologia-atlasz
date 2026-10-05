# ADR-0007: Evidence-based resolution of person mentions

Status: accepted (2026-10-04) · Issue #5 · Builds on ADR-0006 (mentions vs Persons), ADR-0003 (stable ids)

## Context

ADR-0006 split person-like observations into canonical `Person`s (identity anchor
required) and `PersonMention`s (what one page said). In release `2026-10-tk-m2` only two
rules resolved a mention: an exact profile URL or a stated hard id. 339 of 1,021 mentions
stayed unresolved, and their claims (748 participation claims) were missing from the
analysis graph. The audit of those 339 (#5) found:

| | Count |
|---|---|
| on SZI / PTI / KI pages | 189 / 149 / 1 |
| on project pages / listings / unit pages | 180 / 147 / 12 |
| unlinked names / links to an unfetched profile | 255 / 84 |
| with no same-name Person / exactly one / two | 176 / 162 / 1 (Stefkovics Ádám) |

The audit also found a flaw in #4: about 300 `DETERMINISTIC` decisions came through
profile links written on a historical host (`tk.hun-ren.hu`, `socio.mta.hu`) that the
parser rewrote to the canonical host before the resolver saw them. Some of those aliases
are verified (301 to the same path), others are only inferred (#14). An inferred alias
must not make a link certain.

A false merge is more damaging than an unresolved mention: it invents a collaboration,
inflates a researcher's degree and brokerage, and is silent once projected. An
unresolved mention is visible, counted and reviewable.

## Decision

### Candidates are not decisions

Resolution runs in two separate steps.

1. **Candidate generation** asks which canonical Persons a mention *might* refer to: the
   same name key, the same name in another token order, a name with compatible initials
   (same surname), or the same `/kutato/<slug>` as the linked profile. Being a candidate
   says nothing about identity.
2. **The decision** asks whether the evidence for exactly one candidate satisfies a named
   rule. Every candidate keeps its positive and negative signals in the release
   (`PersonMention.candidates`), whether or not it was chosen.

There is no confidence score. A decision is explained by the rule that fired and the
signals it used; anything else is review.

### Signals

Certain (decided before the resolver, ADR-0006):

| Signal | Meaning |
|---|---|
| `PROFILE_URL_EXACT` | the page links the Person's profile on its canonical host |
| `PROFILE_URL_VERIFIED_ALIAS` | the link was written on a host alias whose 301 to the same path was checked (`verified_host_aliases` in `config/sources.yaml`) |
| `HARD_ID_MATCH` | the page states the Person's MTMT or ORCID id with a compatible name |
| `MANUAL_SAME_AS` | a reviewer decided (`review/manual_overrides.yaml`) |

Name (one full-name match counts as one strong signal):

| Signal | Class |
|---|---|
| `NAME_EXACT` (same characters, titles and spacing aside), `SAME_NORMALIZED_NAME` (accent/case/punctuation-insensitive, same token order), `ALTERNATE_NAME_MATCH` (a name form the Person is already observed under) | strong |
| `NAME_ORDER_VARIANT`, `NAME_INITIALS_COMPATIBLE` | weak: they make a candidate, never a decision |

Context (from certain evidence only, see "No chaining"):

| Signal | Class | Meaning |
|---|---|---|
| `PROFILE_SLUG_INFERRED_ALIAS` | strong | the link was written on an inferred alias of the Person's own profile host |
| `PROFILE_SLUG_FAMILY_HOST` | strong | the link points to the same slug on another host of the Person's institution family (another TK site, `tk.mta.hu`, `tk.hu`) |
| `OWN_PROFILE_LISTS_PROJECT` | strong | the Person's own profile lists the project the mention is attached to (same project id, or the same folded title of at least 15 characters) |
| `SOURCE_UNIT_MEMBER` | strong | the Person is a member of the department the page belongs to or that hosts the project |
| `SAME_INSTITUTE` | strong | the page is on the site of the Person's own institute |
| `UNIQUE_NAME_IN_FAMILY` | strong | no other Person of the institution family has this name |
| `SAME_INSTITUTION_FAMILY` | weak | page and Person belong to the same institution family |

Negative:

| Signal | Effect |
|---|---|
| `LINKS_OTHER_PROFILE` | blocks: the page links a different profile than the name candidate's |
| `LINK_NAME_MISMATCH` | blocks: the linked slug is the candidate's but the stated name is not a full-name match ("Illésy Miklós" → `illessy-miklos`) |
| `MULTIPLE_CANDIDATES`, `SAME_NAME_MULTIPLE_PERSONS` | blocks: more than one viable candidate |
| `CONFLICTING_HARD_ID` | blocks: the page states an id that differs from the candidate's |
| `MANUAL_NOT_SAME_AS` | blocks and rejects the candidate |
| `COMMON_SURNAME` | caution: switches off `institute-unique-name` (list in `config/resolution.yaml`) |
| `DIFFERENT_INSTITUTE` | caution only: cross-institute collaboration is normal |

### Rules

A rule fires only if the mention has exactly one viable candidate, that candidate has a
full-name match, no blocking signal applies, and every signal the rule lists is present.
Each automatic decision therefore rests on at least two strong signals. Rules are tried
in this order; the first that fires is recorded as `method`.

#### slug-inferred-alias

Full name + `PROFILE_SLUG_INFERRED_ALIAS`. The page links the Person's own profile, but
on a host alias nobody could verify from the crawl environment (`*.tk.hun-ren.hu`,
`socio.mta.hu`). The name agreeing with the profile is the second, independent signal.
Without it the link stays in review (`LINK_NAME_MISMATCH`).

#### slug-family-host

Full name + `PROFILE_SLUG_FAMILY_HOST`. Assumes the institution family runs one profile
namespace: one `/kutato/<slug>` names one person on every TK host. Evidence: all TK
institute sites run one CMS; the only slug seen on two sites (`stefkovics-adam`) is one
person (same CMS record, #6). The assumption is declared per family in
`config/resolution.yaml` (`shared_profile_slug_namespace`) and never applied across
families.

#### own-profile-project

Full name + `OWN_PROFILE_LISTS_PROJECT`. The project page names the person and the
person's own profile names the project: two sources agree independently.

#### unit-member-unique

Full name + `SOURCE_UNIT_MEMBER` + `UNIQUE_NAME_IN_FAMILY`.

#### institute-unique-name

Full name + `SAME_INSTITUTE` + `UNIQUE_NAME_IN_FAMILY`, and no `COMMON_SURNAME`. Name
uniqueness is judged among the family's canonical Persons only: a closed world of people
with an institutional profile in that family. It is not "same name + unique Person ⇒
merge": the page must be on the Person's own institute site, and frequent surnames
(Szabó Sára, Kovács Éva) need direct evidence instead.

### Statuses

| Status | Meaning | In the analysis graph |
|---|---|---|
| `DETERMINISTIC` | certain signal | yes |
| `MANUAL_CONFIRMED` | reviewer decision | yes |
| `HIGH_CONFIDENCE_AUTO` | a rule above fired | yes, with `method` and signals on `RESOLVES_TO` |
| `REVIEW_REQUIRED` | at least one candidate, no rule fired or a block applied | no; listed in `review/mention_review.yaml` |
| `UNRESOLVED` | no candidate at all | no |

A rejected candidate is a per-candidate flag (`MentionCandidate.rejected`), not a status.

### No chaining

Contextual signals (units, institutes, projects of a Person) are computed from a first
canonical pass built only from identity-anchored observations and certain mention
decisions. An automatic decision never becomes evidence for another one, so the outcome
does not depend on processing order, and one wrong decision cannot propagate. The second
pass projects the claims of every resolved mention onto its Person.

### Manual decisions are authoritative

`review/manual_overrides.yaml`:

```yaml
mention_decisions:
  - {mention_id: pmn_..., person_id: per_..., decision: same_as | not_same_as,
     reviewer: <name>, date: YYYY-MM-DD, evidence: "..."}
```

`source_ref` instead of `mention_id` decides every page of one source record. `same_as`
gives `MANUAL_CONFIRMED`. `not_same_as` rejects the candidate and overrides any automatic
decision, a certain one included (the mention returns to `REVIEW_REQUIRED`). The older
cluster-level `same_as` / `not_same_as` pairs keep working.

### Provenance and reproducibility

Each resolution stores `status`, `person_id`, `method`, `signals`, `negative_signals`,
`evidence` (matched URLs, alias status, projects, units, uniqueness scope), `reason` (why
not resolved), `decision_source` (this ADR's rule anchor or the override file) and
`resolver_version` (`config/resolution.yaml`). Automatic decisions carry no timestamp, so
two builds from the same staged data are byte-identical; manual ones carry the review
date.

## Consequences

* Release `2026-10-tk-m2-p5`: 797 of 1,021 mentions resolved (668 deterministic,
  129 rule-based), 53 in review, 171 without any candidate. Analysis relations
  `PARTICIPATES_IN` 622 → 670, `PRINCIPAL_INVESTIGATOR_OF` 88 → 112.
* 14 #4 decisions that rested on an inferred alias moved from `DETERMINISTIC` to
  `HIGH_CONFIDENCE_AUTO` (`slug-inferred-alias`).
* Resolution is uneven by source (KI 99%, SZI 81%, PTI 67%): richer markup resolves more.
  QA warns when the spread exceeds 20 points, and the manifest reports rates per source
  and page type, because this shows up later as denser networks.
* MTMT is an identity anchor, not yet a mention signal: TK pages state MTMT ids only on
  own profiles. Once publications are imported (Milestone 3), co-authorship becomes a new
  candidate source and a new strong signal under the same rule framework.
* The 171 no-candidate mentions are mostly former staff whose profile is gone (404) and
  external collaborators. They need a new source, not a looser rule.
