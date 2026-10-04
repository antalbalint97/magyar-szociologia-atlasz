# Architecture

Status: proposal + phase-1 implementation (schema 0.1.0, October 2026).

## 1. Shape of the system

```
                      config/sources.yaml          config/taxonomy/*.yaml      review/*.yaml
                      (source registry,            (topics, methods)           (manual decisions,
                       curated institutions)                                     identity map)
                               │                           │                         │
 PUBLIC SOURCES ──► FETCH ──► RAW SNAPSHOT ──► PARSE ──► STAGED ──► DERIVE ──► RESOLVE ──► CANONICAL ──► QA
  (TK sites,        polite     data/raw/        source     records     taxonomy    identity     release dir
   later ELTE,      fetcher:   <source>/pages   adapters   + claims    mapping     matching     (JSONL +
   TÁRKI, MTMT…)    robots,    + documents.     (one per   data/       (DERIVED    + overrides  manifest +
                    delay,     jsonl            site       staged/     claims)     + stable     quality report)
                    budget                      family)                            canonical ids      │
                                                                                                     ├──► Neo4j (projection, idempotent upsert)
                                                                                                     │        └──► Next.js server components ──► browser
                                                                                                     ├──► file backend for the web app (no DB needed)
                                                                                                     └──► analysis layer (NetworkX/igraph, notebooks)
```

The hypothesis in the brief (section 33) holds up; this design keeps it and changes three
things:

1. **The claim is the unit of storage, not the entity.** Parsers emit *claims*
   (subject, predicate, value/object, time, evidence, method, confidence). Entities and
   edges in the canonical dataset are *projections* of claims, rebuilt on every run.
   This is what makes "never silently overwrite", conflict preservation and per-field
   provenance cheap instead of an afterthought.
2. **Curated knowledge is also a source.** The registry's institution seeds and the
   topic/method taxonomies are version-controlled files that become `SourceDocument`s
   with a content hash. A curated fact is as traceable as a scraped one (which commit
   asserted it).
3. **The web app does not require Neo4j.** It talks to a `GraphStore` interface with a
   file backend (reads a release directory) and a Neo4j backend. Neo4j becomes worth
   running once path/genealogy queries over thousands of nodes matter; until then a
   release directory is enough, and the frontend works on any machine.

Nothing here is distributed: one Python package, one Next.js app, files on disk, an
optional Neo4j.

## 2. Layers and their contracts

| Layer | Location | Format | Contract |
|---|---|---|---|
| Source registry | `config/sources.yaml` | YAML, validated by `registry.py` | The only place URLs live. Enabled sources need an adapter. |
| Raw snapshots | `data/raw/<source>/pages/<sha[:2]>/<sha>.html`, `documents.jsonl`, `runs.jsonl` | bytes + `SourceDocument` JSONL | Byte-exact body, written before parsing. Content-addressed. Never edited. |
| Staged | `data/staged/<source>/{records,claims,documents,errors}.jsonl` | JSONL | Source-local: refs like `tk_recens\|https://…/kutato/koltai-julia`. No identity decisions. |
| Curated | `config/`, `review/` | YAML / JSONL in git | Human decisions with reviewer + date. |
| Canonical release | `data/releases/<id>/` | `entities/<Type>.jsonl`, `relations.jsonl`, `claims.jsonl`, `documents.jsonl`, `matches.jsonl`, `manifest.json`, `quality_report.{md,json}` | Self-contained and portable: everything needed to audit any value. |
| Graph | Neo4j 5 | nodes/relationships + `:Claim` / `:SourceDocument` | Disposable projection of one release; reloadable at any time. |
| Serving | `apps/web` | Next.js server components | Read-only; no credentials in the browser. |
| Analysis | `research/` | notebooks / scripts | Reads releases (or `szocatlas.graph.export.to_networkx`), never the live site. |

Raw HTML and staged files are not committed (they are reproducible from the registry,
and some sites' terms may not allow redistribution). Releases are published separately;
only the small `fixture-sample` release is in git so the app runs out of the box.

## 3. Source adapters

`sources/base.py` defines the interface every source family implements:

```python
discover_people() / discover_units() / discover_projects()   # -> URLs
parse_person(page) / parse_unit(page) / parse_project(page)  # -> ParseResult(records, claims)
run()                                                        # orchestrates via the shared Fetcher
```

Adapters fetch only through the shared `Fetcher` (so every page lands in the raw
store), never resolve identities, and never write canonical data. `ClaimFactory` binds
every claim to the document it came from, so a parser cannot emit an unsourced claim.

The TK adapter serves all TK institute sites (one CMS): researcher listings at
`/kutatok` with pagination and letter filters, profiles at `/kutato/<slug>`, unit and
project pages configured per site. Parsers avoid CSS classes and rely on `<h1>`,
labelled fields ("Osztályvezető:", "Időtartam:"), section headings ("Kutatási
területek", "Projektek") and URL patterns. See ADR-0004.

## 4. Fetching etiquette

`PoliteFetcher`: robots.txt checked per origin (an unreachable robots.txt means *do not
crawl*), at least 3 s between requests to a host, a per-run page budget (400), a
descriptive User-Agent, and snapshot reuse for 30 days (`max_age_days`) so re-runs do not
re-hit sites. `--replay` re-parses from snapshots with no network. Playwright is not
used; none of the TK pages need JavaScript.

## 5. Identity

Canonical ids (`per_…`, `ins_…`, `unit_…`, `prj_…`, `top_…`, `met_…`) are minted once
from a hash of the first source ref and persisted in `review/identity_map.jsonl`, which is
committed. Later runs reuse them, so ids survive new sources, parser changes and merges.
Matching rules are in `resolution/matcher.py` and docs/methodology.md: hard identifiers
(MTMT, ORCID) plus compatible names merge automatically; everything else that looks
alike becomes a `possible_match` in `review/unresolved_people.yaml` for a human.

## 6. Serving

`apps/web` (Next.js 16, App Router, TypeScript). Pages are server components that call
`graph()` from `lib/graph`, which returns either backend. Default UX is search → profile →
2-step ego network (deterministic radial SVG, at most ~56 nodes), never a whole-graph
hairball. Observed edges are solid, derived ones dashed and labelled "származtatott",
and every profile lists the source documents and snippets behind it.

A separate API service (FastAPI) is not justified yet. Revisit when one of these
appears: a public research API with its own consumers, heavy analytical endpoints,
authenticated editing, or scheduled jobs that the CLI + cron cannot cover.

## 7. Visualisation choices (to benchmark, not yet committed)

| Need | Candidate | Note |
|---|---|---|
| Ego network ≤ 100 nodes | inline SVG (current) | deterministic, SSR, accessible, no JS |
| Community overview, 1–10k nodes | Sigma.js + Graphology | WebGL; precompute layout offline (ForceAtlas2 in the analysis layer) |
| Institutional trees, genealogy | D3 hierarchy / Cytoscape.js (dagre) | trees are small; layout clarity matters more than scale |
| Institutional flows over time | D3 Sankey | needs explicit-interval affiliations first |

Benchmark plan: generate a synthetic 5k-node / 20k-edge graph with the release's degree
distribution and measure first render, pan/zoom FPS and memory on a mid-range laptop and
phone for Sigma vs Cytoscape before adding a community view.

## 8. Extending backwards in time

Nothing in the model assumes "now": affiliations are edges with `valid_from/valid_until`
plus `first/last_observed_at`; institutions have alternate historical names and
`PART_OF` edges with their own intervals; `Event` nodes carry mergers and renames;
archived pages are `SourceDocument`s with `source_type = archive_snapshot`. Historical
adapters (Wayback snapshots, doktori.hu, MTMT, journal archives, obituaries) plug into the
same interface. See docs/ontology.md §4.
