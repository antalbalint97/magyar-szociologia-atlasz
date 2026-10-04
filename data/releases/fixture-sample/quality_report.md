# Data-quality report: fixture-sample

- generated_at: 2026-10-04T16:26:28+00:00
- dataset_kind: **fixture**
- schema_version: 0.1.0
- sources: tk_kisebbsegkutato, tk_politikatudomany, tk_recens, tk_szociologia
- parsers: curated=curated/0.1.0, derive.taxonomy=taxonomy_keyword_map/0.1.0, tk.listing=tk/0.2.1, tk.profile=tk/0.2.1, tk.project=tk/0.2.1, tk.project_listing=tk/0.2.1, tk.unit=tk/0.2.1

| severity | count |
|---|---|
| error | 0 |
| warning | 8 |
| info | 7 |

## [warning] identity.possible_duplicates

1 possible person matches await review (review/unresolved_people.yaml)

```yaml
pairs:
- - Albert Fruzsina
  - Albert Fruzsina
  - auto:same_name
```

## [warning] identity.unresolved_mentions

51 of 57 person mentions are not resolved to an identity (1 distinct names also carried by a canonical person; see #5)

```yaml
by_status:
  UNRESOLVED: 51
  DETERMINISTIC: 6
same_name_as_a_person:
  albert fruzsina: 1
```

## [warning] provenance.synthetic_documents

18 documents are reconstructed fixtures; this dataset is NOT a publishable release

## [warning] review.project_label_suspicious

project 'Intersections.East European Journal of Society and Politics' may be a journal/role listed under Projektek

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

## [info] seeds.present

Koltai Júlia -> per_965aaf3d0d

```yaml
affiliations:
- TK Számítógépes Társadalomtudomány - CSS-RECENS
topics: []
methods: []
resolved_mentions: 1
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
Project: 79
```

## [info] stats.epistemic

relations by epistemic status

```yaml
OBSERVED: 151
DERIVED: 101
```

## [info] stats.person_mentions

person mentions by resolution status

```yaml
UNRESOLVED: 51
DETERMINISTIC: 6
```

## [info] stats.relations

relation counts

```yaml
AFFILIATED_WITH: 11
BROADER: 2
HOSTED_BY: 2
MEMBER_OF: 8
PARTICIPATES_IN: 68
PART_OF: 43
PRINCIPAL_INVESTIGATOR_OF: 17
USES_METHOD: 16
WORKS_ON_TOPIC: 85
```
