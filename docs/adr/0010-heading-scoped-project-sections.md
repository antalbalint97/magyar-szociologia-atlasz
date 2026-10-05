# ADR-0010: Lead and participant headings on SZI project pages are read as bounded sections

Status: accepted (2026-10-05) · Issue #31 · Builds on ADR-0001 (claims), ADR-0004
(markup-agnostic parsers), ADR-0006 (person mentions), ADR-0009 (coverage measured apart from
correctness)

## Context

The coverage report (#12) showed that 86 of the 193 Szociológiai Intézet (SZI) project pages
(45%) produced no project lead and no participant. The parser was correct on what it read; it
read the wrong shape. A project page of the old SZI template writes a field's label as a
heading and its value in the blocks below it:

```html
<h3>Résztvevők (MTA SZKI)</h3>
<p>Kovács Szilvia</p>
<p>Váradi Zsuzsanna</p>
```

The parser only knew `Label: value` lines inside a leaf `<p>`/`<li>`/`<dd>`/`<tr>`, so none of
these pages had a lead or a participant claim. Nothing in the build could see that: the pages
parsed "ok" (title, abstract) and QA reported 0 errors. This is exactly the kind of gap #12
exists to expose, and it sat on the institute that holds most of the project layer (193 of the
280 project pages in the release).

A second defect lived on the same pages. Without a lead or participants line, the old description
rule ("the first `<p>` of 80 characters or more with no label colon") stored the participants
list or the coordinator's address as the project's abstract on 11 of the 86 pages.

## Decision 1: a heading is a label only if it is an existing label

A heading (`h2`–`h6`, never the page title) is read as a **lead** or **participants** label only
when its whole text, minus one trailing parenthetical (`(MTA SZKI)`) and a colon, is at most
three words and matches a label the `Label: value` reader already knows
(`PROJECT_LEAD_LABEL_RE`, `PARTICIPANTS_LABEL_RE`, `PARTICIPANTS_LINKS_ONLY_RE`), with at most
two letters of inflection left over ("Projektvezetők" yes, "Kutatóközpont bemutatása" no). No
label was added: "Koordinátor(ok)", "Partnerek" and "Konzorciumi tagok" are not read (see
*Not read, on purpose*).

## Decision 2: the section is local and structurally bounded

The value is what follows the heading **inside the heading's own parent**, up to the first of:

* the next heading of any level (also a container that holds one), or a `table`, `hr`, `form`,
  `figure`, `iframe` or `svg`;
* the first non-blank block that has no accepted name or profile link (a `<p>` used as a heading
  ends the section of the heading before it).

Blocks are leaf `<p>`/`<div>`/`<li>`/`<dd>`..., or a run of bare text and `<br>` between two
blocks (the Word-pasted pages). Comments, `<script>` and `<style>` are skipped. A block that is
only a placeholder (`...`, `-`) is transparent but counted: the page states the heading and
leaves the value out, which is a fact about the page, so the heading goes to `unmapped_labels`
("Résztvevők (heading without a readable name)") and no field is produced. There is no search
outside the section and no proximity evidence: a name near a heading, on the page or in a
sibling container, is nothing.

## Decision 3: a line is a name only if it looks like names from its start

A `Label: value` line is already filtered by the label; a bare line under a heading is not, so it
is held to a stricter test (`_name_line`, `_not_a_person`):

* a line with a colon, `@`, `/`, braces, `<>`, `|`, `http`, `www.` or more than 150 characters is
  prose or a link;
* parentheticals and `[...]` (affiliations, "dékán, BGF", "[FMUP]") are removed before reading;
* each name has two to five tokens, each starting with a capital letter (a particle such as
  *von*, *van*, *de* may be lower case), none an acronym, none of the organisation, country or
  programme vocabulary (`NON_PERSON_RE`: university, institute, ministry, foundation, network,
  "Great Britain", ...);
* reading **stops at the first part that is not a person**: what follows a name that is not one is
  its affiliation, city or country ("Ingrid Sharp, University of Leeds, Great Britain" yields
  Ingrid Sharp);
* the short labels "Résztvevő" / "Részvevők" keep the rule they have on a label line: profile
  links only (#16), so plain-text names under them are reported as rejected, not read.

When in doubt the name stays unparsed. A missed name is a coverage gap, visible in
`unmapped_labels` and in this ADR's table; a wrong name is a wrong edge.

## Decision 4: the same semantics as a label line

What a heading read is fed through the same `_apply_project_lines` a `Label: names` line uses, so
a heading and a label line cannot disagree on field meaning: a lead with a profile link becomes
`PRINCIPAL_INVESTIGATOR_OF` + `PARTICIPATES_IN` to a Person; a lead or participant without one is
a plain-text name and becomes a **PersonMention** (ADR-0006), with `PARTICIPATES_IN` carrying
`role = <label as stated>`. A person already stated on the page (by a label line, by an earlier
heading, as a lead and as a participant) is not added twice; the key is the profile URL or the
stated name on that page, never the name alone across pages.

## Decision 5: provenance for every heading-derived claim

Locators `project.heading.vezeto[.unlinked]` and `project.heading.resztvevok[.unlinked]`; the
snippet is the heading as stated and the line the name was read from (`Kutatásvezető (MTA SZKI):
Erőss Gábor`); the role qualifier is the label as stated; the parser version is `tk/0.6.0`. A
reader can tell from the claim alone that the value came from a heading section and which one.
Relations still need claims (ADR-0001); nothing is derived from layout without one.

## Decision 6: an explicit "A kutatás" heading beats "the first long paragraph"

The description of a project page is the first block of 80 characters or more (no label colon in
its first 40) **under an `A kutatás` heading, up to the next heading**, when the page has one.
Otherwise the old rule applies unchanged. This is a behaviour change, and it is visible:
on the 86 pages 30 projects gained an abstract that sat in a `<div>`, and 11 abstracts that were
participant or coordinator lists were replaced by the research description (locator
`project.heading.description`, 37 abstract claims re-issued). Pages without an `A kutatás` heading
keep the old rule. It still stores a header line (funder, period and lead in one paragraph), a
list of names or organisations, or a bibliographic reference as the abstract on 14 of the 187
abstracts the legacy rule wrote (12 SZI, 2 KI; a hand check of a heuristic candidate list, so a
lower bound). That is a defect of a different extractor, filed as #35.

## Consequences

Measured on the same 563 web documents (source-set digest `6e7fd8757ffc5c44`, no page fetched):

| SZI project pages, n = 193 | before (`p16`) | after (`p31`) |
|---|---|---|
| with a lead | 60 | 138 |
| with participants | 17 | 75 |
| with a lead and participants | 13 | 65 |
| parsed "empty" | 48 | 8 |

Every claim that differs between the two builds (37 removed, 645 added) is on the 86 pages; the
claims of the 107 other SZI pages and of every KI, PTI and CSS-RECENS page have the same ids. Of
the 86: 80 have a lead heading (78 read, 2 org-first lines left unread), 71 a participants heading
(58 read; 5 are placeholders only, 5 use the singular label, 3 have lines that are not
person-like), 84 yield a lead or a participant, 2 yield neither. No Person or Project id, and no
earlier resolution (0 of 1,188 person mentions, 0 of 783 project mentions), changed.

The 247 new person mentions (112 distinct names) are all plain text: none has a profile anchor.
98 resolve (97 by `institute_unique_name`, 1 by `own_profile_project`), 19 wait for review, 130
have no candidate (collaborators and former staff, #28). New edges are an improved observation of
pages that were already crawled, not new knowledge about the world: `PRINCIPAL_INVESTIGATOR_OF`
136 → 178, `PARTICIPATES_IN` 341 → 423, co-participation ties 551 → 584 (all within SZI), no
cross-institute change.

## Not read, on purpose

* `Koordinátor`, `Koordinátorok` (5 of the 86 pages): a consortium coordinator is not necessarily
  the principal investigator. Which role a label carries is project-role semantics (#36).
* `Partnerek`, `Konzorciumi tagok`: organisations.
* A misspelt heading outside the vocabulary (`Résztevevők`, 1 page).
* A `<p>` or `<strong>` that looks like a heading (2 pages): without a heading element the
  section has no bound.
* Org-first lines ("MTA SZKI - Széman Zsuzsa"), `Family, Given` ("Acsády, Judit"), a lower-case
  typo ("Kovács éva"), a list of foreign scholars with `Family, Given (Institution)`.
* Descriptions that are not under an `A kutatás` heading.

Each is a coverage gap with a name in this list, not a silent loss.

## Alternatives rejected

* **Search the page for names near a label.** Proximity is not evidence; it is how a coordinator's
  address becomes a participant.
* **Any capitalised two-word line is a name.** It reads "Great Britain", "Moszkvai Egyetem" and
  "MTA SZKI Budapest" as people. The vocabulary list is a precision device, and it is short enough
  to read.
* **Extend the label vocabulary** ("Koordinátor", "Közreműködők") to raise coverage. Adds roles
  whose meaning is undecided (#36); leaving them out costs a measured, listed gap.
* **Resolve unlinked names by the name alone.** The resolver is unchanged: a name with no anchor
  resolves only by a rule that already existed (ADR-0007), a common surname goes to review.

## Known limits

The resolver does not use an affiliation the page states for a plain-text name ("Kovács János
Mátyás (IWM, Bécs)"). In this release none of the 43 heading mentions with a parenthetical
(41 unresolved, 2 in review) resolved automatically, so no false merge exists, but the protection
is incidental. Tracked as #34; the resolver is not changed here.

The wider set of label forms that no field takes is not a parsing question. 51 of the 193 SZI
project pages (26%) state people under a label outside the vocabulary or under a heading with no
readable name ("További résztvevők", "Részt vevő kutatók", "Konzorciumvezető", ...). Which role each
means, and which relation it makes, is a decision for the reviewer: #36.
