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

## 3. Entity resolution

Implemented in `src/szocatlas/resolution/matcher.py`.

| Signal | Use |
|---|---|
| exact / accent-folded name | blocking only |
| order-free name key ("Júlia Koltai" ~ "Koltai Júlia") | blocking only |
| MTMT author id, ORCID | hard identifiers: agree + compatible name → merge; disagree → never merge |
| same institution family, same profile slug, same e-mail domain | soft signals that rank `possible_match`es for review |
| unlinked name mention (e.g. "Külső szakértő: X") | always review, never auto-merged |
| publication overlap, topic overlap | later; soft signals only |

Decisions: `confirmed_match`, `possible_match`, `rejected_match`, each with method and
signals, written to `matches.jsonl` in every release. Manual decisions in
`review/manual_overrides.yaml` (`same_as`, `not_same_as`) win over every automatic rule,
and a rejection blocks transitive merges through a third record.

Org units and projects: identical normalised name/title on the same site = same entity
(unit page vs "Osztály: …" line on a profile). Across sites, never automatic.

Host aliases (`szociologia.tk.mta.hu`, `szociologia.tk.hu` → `szociologia.tk.elte.hu`)
are URL normalisation declared in the registry, not entity resolution: they are the same
page under historical hostnames.

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
