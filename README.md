# Magyar Szociológia Atlasz / Hungarian Sociology Knowledge Graph

A longitudinal, provenance-aware knowledge graph of Hungarian sociology: institutions,
units, research groups, projects, people, topics and methods, with every statement
traceable to a public source. Phase 1 targets a defensible snapshot of the field around
2026; the model is built to extend backwards through the history of the discipline.

> **Status (0.1.0):** foundation. The pipeline, ontology, TK adapter, entity resolution,
> QA, Neo4j import and a minimal explorer work end to end and are tested. The only dataset
> in the repository is `data/releases/fixture-sample`, built from **hand-reconstructed
> test pages**: it demonstrates the data model and is not a statement about the field.
> The first real snapshot needs a run with network access to the source sites (see
> "Run ingestion").
>
> Current state, milestone and blockers: [docs/status.md](docs/status.md). Work is
> tracked in GitHub Issues ([CONTRIBUTING.md](CONTRIBUTING.md)).

## Layout

```
config/            sources.yaml (source registry + curated institutions), taxonomy/, qa_seeds.yaml
src/szocatlas/     Python package
  models/          ontology v0.1 (Pydantic): claims, documents, entities, relations, enums
  fetch.py         polite fetcher + raw snapshot store (robots.txt, delay, budget, replay)
  sources/         adapter interface; tk/ = TK institute sites (szociologia, recens, kisebbsegkutato, …)
  canonical/       curated claims, taxonomy derivation, canonical projection
  resolution/      conservative identity matching, manual overrides, persistent ids
  validation/      QA checks + report
  graph/           Neo4j constraints, loader, example queries, NetworkX export
review/            manual decisions (version-controlled), identity map, generated review queue
data/              raw/ staged/ (not committed), releases/<id>/ (canonical datasets)
apps/web/          Next.js explorer (search, profile, ego network, evidence)
research/          analysis notebooks/scripts, independent of the web app
docs/              architecture, ontology, data dictionary, methodology, sources, neo4j, ADRs
tests/             parser fixtures, schema, resolution, pipeline, graph, QA tests
```

## Install

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev,neo4j,analysis]"
pytest                       # 47 tests; the Neo4j round-trip test runs when NEO4J_URI is set
```

## Run ingestion

```bash
szocatlas sources                         # registry overview
szocatlas ingest                          # all enabled sources (live, polite; snapshots in data/raw)
szocatlas ingest tk_recens                # one source
szocatlas ingest --replay                 # re-parse existing snapshots, no network
szocatlas ingest-fixtures                 # parse tests/fixtures/tk instead (fixture dataset)
```

Each run appends to `data/raw/<source>/runs.jsonl` and writes staged records/claims to
`data/staged/<source>/`.

## Build, inspect, validate

```bash
szocatlas build --release 2026-10-snapshot
szocatlas validate 2026-10-snapshot       # prints quality_report.md
```

A release contains `entities/<Type>.jsonl`, `relations.jsonl`, `claims.jsonl`,
`documents.jsonl`, `matches.jsonl`, `manifest.json` (generated_at, sources, parser and
schema versions, counts) and `quality_report.{md,json}`. `build` exits non-zero on QA
errors unless `--allow-errors`. It also rewrites `review/unresolved_people.yaml` (possible
duplicates to decide) and extends `review/identity_map.jsonl` (commit it).

Manual review: record identity decisions in `review/manual_overrides.yaml`, claim
disputes in `review/disputed_claims.yaml`, then rebuild.

Quick look at a release with pandas:

```python
import pandas as pd
people = pd.read_json("data/releases/fixture-sample/entities/Person.jsonl", lines=True)
rels = pd.read_json("data/releases/fixture-sample/relations.jsonl", lines=True)
```

## Load Neo4j

```bash
docker run -d -p 7474:7474 -p 7687:7687 -e NEO4J_AUTH=neo4j/change-me neo4j:5-community
export NEO4J_URI=bolt://localhost:7687 NEO4J_USER=neo4j NEO4J_PASSWORD=change-me
szocatlas neo4j-load fixture-sample --prune     # idempotent; safe to repeat
```

Example queries: `src/szocatlas/graph/cypher/queries.cypher`, explained in docs/neo4j.md.

## Run the frontend

```bash
cd apps/web && npm install && cp .env.example .env.local && npm run dev
```

`GRAPH_BACKEND=file` (default) reads `data/releases/$GRAPH_RELEASE`; `GRAPH_BACKEND=neo4j`
queries Neo4j server-side.

## Principles

Data correctness > provenance > entity identity > reproducibility > temporal modelling >
queryability > usability > polish. Unknown stays unknown; inferred is never shown as
observed; nobody is hand-picked into the graph. See docs/methodology.md (including
ethics) and docs/uncertainties_and_next_steps.md.
