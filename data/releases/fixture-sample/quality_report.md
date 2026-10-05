# Data-quality report: fixture-sample

- generated_at: 2026-10-04T21:54:21+00:00
- dataset_kind: **fixture**
- schema_version: 0.1.0
- sources: tk_kisebbsegkutato, tk_politikatudomany, tk_recens, tk_szociologia
- parsers: curated=curated/0.1.0, derive.taxonomy=taxonomy_keyword_map/0.1.0, tk.listing=tk/0.4.0, tk.profile=tk/0.4.0, tk.project=tk/0.4.0, tk.project_listing=tk/0.4.0, tk.unit=tk/0.4.0

| severity | count |
|---|---|
| error | 0 |
| warning | 9 |
| info | 11 |

## [warning] provenance.synthetic_documents

18 documents are reconstructed fixtures; this dataset is NOT a publishable release

## [warning] seeds.missing

QA seed not in dataset as a person: Ságvári Bence

```yaml
expect: Computational/digital sociology and research-centre affiliations.
mentioned_on:
- https://szociologia.tk.elte.hu/kategoria/futo-kutatasok
```

## [warning] seeds.missing

QA seed not in dataset as a person: Kisfalusi Dorottya

```yaml
expect: Social networks, education and discrimination overlap.
mentioned_on:
- https://recens.tk.elte.hu/kutatok
- https://recens.tk.elte.hu/kutatok/k
```

## [warning] seeds.missing

QA seed not in dataset as a person: Durst Judit

```yaml
expect: Roma mobility, ethnography, project links.
mentioned_on:
- https://kisebbsegkutato.tk.elte.hu/kisebbsegszociologiai-es-antropologiai-osztaly
```

## [warning] seeds.missing

QA seed not in dataset as a person: Virág Tünde

```yaml
expect: Spatial inequality, Roma, locality.
mentioned_on: []
```

## [warning] seeds.missing

QA seed not in dataset as a person: Messing Vera

```yaml
expect: Many project mentions across SZI pages; resolution must restore them only with evidence.
mentioned_on:
- https://szociologia.tk.elte.hu/kategoria/futo-kutatasok
```

## [warning] seeds.missing

QA seed not in dataset as a person: Kovách Imre

```yaml
expect: Project lead on SZI pages; resolution must restore observed PI edges.
mentioned_on: []
```

## [warning] seeds.missing

QA seed not in dataset as a person: Gerő Márton

```yaml
expect: No MTMT id; identity rests on the institutional profile only.
mentioned_on:
- https://szociologia.tk.elte.hu/kategoria/futo-kutatasok
```

## [warning] seeds.missing

QA seed not in dataset as a person: Papp Z. Attila

```yaml
expect: Middle initial in the name; initials alone must never resolve a mention.
mentioned_on: []
```

## [info] identity.mention_resolution

7 of 57 person mentions resolved (12.3%); 0 need review, 50 have no candidate Person

```yaml
by_status:
  DETERMINISTIC: 6
  HIGH_CONFIDENCE_AUTO: 1
  UNRESOLVED: 50
resolved_by_method:
  own_profile_project: 1
  profile_url: 6
by_source:
  tk_kisebbsegkutato:
    DETERMINISTIC: 1
    UNRESOLVED: 13
    resolved: 1
    total: 14
    resolution_rate: 0.071
  tk_recens:
    DETERMINISTIC: 4
    UNRESOLVED: 12
    resolved: 4
    total: 16
    resolution_rate: 0.25
  tk_szociologia:
    DETERMINISTIC: 1
    HIGH_CONFIDENCE_AUTO: 1
    UNRESOLVED: 25
    resolved: 2
    total: 27
    resolution_rate: 0.074
by_page_type:
  institutional_listing:
    DETERMINISTIC: 4
    UNRESOLVED: 23
    resolved: 4
    total: 27
    resolution_rate: 0.148
  project_page:
    HIGH_CONFIDENCE_AUTO: 1
    UNRESOLVED: 4
    resolved: 1
    total: 5
    resolution_rate: 0.2
  unit_page:
    DETERMINISTIC: 2
    UNRESOLVED: 23
    resolved: 2
    total: 25
    resolution_rate: 0.08
not_resolved_reasons:
  no canonical Person with a compatible name or the linked profile slug: 50
```

## [info] project.activity_cues

0 Projects and 4 project mentions carry words suggesting a journal, network, programme, infrastructure, consortium or newsletter (left for #9)

```yaml
mentions:
  journal: 1
  research_group: 2
  programme: 1
  network: 1
projects: {}
```

## [info] project.mention_resolution

1 of 78 project mentions resolved (1.3%); 0 need review, 77 have no candidate Project

```yaml
by_status:
  DETERMINISTIC: 1
  UNRESOLVED: 77
resolved_by_method:
  project_url: 1
by_source:
  tk_kisebbsegkutato:
    UNRESOLVED: 15
    resolved: 0
    total: 15
    resolution_rate: 0.0
  tk_politikatudomany:
    UNRESOLVED: 17
    resolved: 0
    total: 17
    resolution_rate: 0.0
  tk_recens:
    UNRESOLVED: 22
    resolved: 0
    total: 22
    resolution_rate: 0.0
  tk_szociologia:
    DETERMINISTIC: 1
    UNRESOLVED: 23
    resolved: 1
    total: 24
    resolution_rate: 0.042
by_observation:
  profile_list:
    DETERMINISTIC: 1
    UNRESOLVED: 67
    resolved: 1
    total: 68
    resolution_rate: 0.015
  project_listing:
    UNRESOLVED: 10
    resolved: 0
    total: 10
    resolution_rate: 0.0
not_resolved_reasons:
  no anchored Project with a compatible title or grant id: 45
  linked project page not fetched: 32
```

## [info] project.unattached_metadata

27 project-section metadata lines are kept unattached (no structural evidence ties them to one project)

```yaml
section_label: 2
table_row: 1
grant: 9
role: 13
funder: 1
other: 1
```

## [info] seeds.present

Koltai Júlia -> per_965aaf3d0d

```yaml
affiliations:
- TK Számítógépes Társadalomtudomány - CSS-RECENS
topics: []
methods: []
resolved_mentions: 1
resolved_by_method:
  profile_url: 1
```

## [info] seeds.present

Kmetty Zoltán -> per_4d7bee69df

```yaml
affiliations:
- TK Számítógépes Társadalomtudomány - CSS-RECENS
topics:
- Computational social science
- Political sociology
- Social networks
methods:
- Computational text analysis
- Quantitative methods
resolved_mentions: 2
resolved_by_method:
  profile_url: 2
```

## [info] seeds.present

Feischmidt Margit -> per_6af5f051a0

```yaml
affiliations:
- Kisebbségszociológiai és Antropológiai Osztály
- TK Kisebbségkutató Intézet
topics:
- Collective memory
- Ethnicity and interethnic relations
- Migration
- Minorities
- Multiculturalism and recognition politics
- Nationalism and national identity
- Political sociology
- Racism and discrimination
- Roma studies
- Solidarity and civil society
methods: []
resolved_mentions: 1
resolved_by_method:
  profile_url: 1
```

## [info] stats.entities

entity counts

```yaml
Institution: 15
OrganisationalUnit: 37
ResearchGroup: 2
ResearchTopic: 34
Method: 19
Person: 11
Project: 2
```

## [info] stats.epistemic

relations by epistemic status

```yaml
OBSERVED: 68
DERIVED: 26
```

## [info] stats.person_mentions

person mentions by resolution status

```yaml
UNRESOLVED: 50
DETERMINISTIC: 6
HIGH_CONFIDENCE_AUTO: 1
```

## [info] stats.relations

relation counts

```yaml
AFFILIATED_WITH: 11
BROADER: 2
HOSTED_BY: 2
MEMBER_OF: 8
PARTICIPATES_IN: 1
PART_OF: 43
PRINCIPAL_INVESTIGATOR_OF: 1
USES_METHOD: 4
WORKS_ON_TOPIC: 22
```
