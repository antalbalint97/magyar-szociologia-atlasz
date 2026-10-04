# Data-quality report: fixture-sample

- generated_at: 2026-10-04T14:06:53+00:00
- dataset_kind: **fixture**
- schema_version: 0.1.0
- sources: tk_kisebbsegkutato, tk_recens, tk_szociologia
- parsers: curated=curated/0.1.0, derive.taxonomy=taxonomy_keyword_map/0.1.0, tk.listing=tk/0.1.0, tk.profile=tk/0.1.0, tk.project=tk/0.1.0, tk.unit=tk/0.1.0

| severity | count |
|---|---|
| error | 0 |
| warning | 6 |
| info | 7 |

## [warning] provenance.synthetic_documents

6 documents are reconstructed fixtures; this dataset is NOT a publishable release

## [warning] review.project_label_suspicious

project 'Intersections journal (Editor-in-Chief)' may be a journal/role listed under Projektek

## [warning] seeds.missing

QA seed not in dataset: Ságvári Bence

```yaml
expect: Computational/digital sociology and research-centre affiliations.
```

## [warning] seeds.missing

QA seed not in dataset: Durst Judit

```yaml
expect: Roma mobility, ethnography, project links.
```

## [warning] seeds.missing

QA seed not in dataset: Virág Tünde

```yaml
expect: Spatial inequality, Roma, locality.
```

## [warning] structure.orphan_person

4 people have no affiliation/membership edge

## [info] seeds.present

Koltai Júlia -> per_965aaf3d0d

```yaml
affiliations:
- TK Számítógépes Társadalomtudomány - CSS-RECENS
topics: []
methods: []
```

## [info] seeds.present

Kmetty Zoltán -> per_4d7bee69df

```yaml
affiliations:
- TK Számítógépes Társadalomtudomány - CSS-RECENS
topics: []
methods: []
```

## [info] seeds.present

Kisfalusi Dorottya -> per_ee86a4696a

```yaml
affiliations:
- TK Számítógépes Társadalomtudomány - CSS-RECENS
topics: []
methods: []
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
```

## [info] stats.entities

entity counts

```yaml
Institution: 2
OrganisationalUnit: 18
ResearchGroup: 2
ResearchTopic: 34
Method: 19
Person: 22
Project: 8
```

## [info] stats.epistemic

relations by epistemic status

```yaml
OBSERVED: 58
DERIVED: 23
```

## [info] stats.relations

relation counts

```yaml
AFFILIATED_WITH: 8
BROADER: 2
HOSTED_BY: 1
LEADS: 1
MEMBER_OF: 12
PARTICIPATES_IN: 12
PART_OF: 21
PRINCIPAL_INVESTIGATOR_OF: 1
WORKS_ON_TOPIC: 23
```
