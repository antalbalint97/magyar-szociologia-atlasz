# Contributing: issue-driven workflow

GitHub Issues are the operational record for engineering work, data quality, research
methodology decisions, source coverage, ontology changes and technical debt. Do not keep
a separate TODO list in the repository; `docs/status.md` is a high-level snapshot that
links to issues.

## Before, during, after

- **Before starting**, name the issue you are addressing. Substantial work without an
  issue gets one first (templates: engineering/data-quality, research question).
- **While working**, a new independent problem gets its own issue, linked from the
  current one. A minor subtask is added to the current issue as a checkbox.
- **PRs** reference issues: `Closes #n` only when every acceptance criterion is met,
  otherwise `Refs #n` with what remains.
- **Closing** an issue requires: acceptance criteria verified, docs updated, tests where
  appropriate, remaining limitations noted in a comment. If the research-validity
  problem remains, keep the issue open or split it; running code is not completion.

## Labels

| Group | Labels |
|---|---|
| Type (one) | `type: bug`, `type: feature`, `type: research`, `type: data-quality`, `type: infrastructure`, `type: documentation` |
| Area (one or more) | `area: ingestion`, `area: parser`, `area: entity-resolution`, `area: ontology`, `area: canonical-data`, `area: graph`, `area: frontend`, `area: qa`, `area: sources`, `area: analysis` |
| Research relevance | `research-methodology` (affects validity of conclusions), `source-coverage`, `needs-review` (needs an owner decision) |
| Priority (one) | `priority: critical` (rare: blocks correctness of everything downstream), `priority: high`, `priority: normal`, `priority: low` |
| Structure | `epic` (tracking issue with sub-issues) |

## Milestones

1. Foundation & first TK crawl (PRs #1, #2)
2. Canonicalization & Coverage (current; tracking issue #3)
3. Contemporary Hungarian sociology coverage
4. Publications & academic genealogy
5. Historical sociology atlas

Milestone 3 crawling waits for Milestone 2, apart from small targeted tests that validate
the architecture.

## Dependencies

Use GitHub's issue relationships (blocked by / blocking, sub-issues under the milestone
epic) and also name them in the issue's Dependencies section.

## Releases

Release data stays outside git. Each release records the schema version, parser versions,
source set, retrieval window, entity and claim counts, QA results, unresolved identity
counts, coverage metrics and analysis-readiness diagnostics (#18). Report **raw/observed**
and **canonical/resolved** counts side by side; never cite a raw count as the size of the
field. When comparing releases, separate substantive changes from parser, schema and
entity-resolution changes.

## Epistemic model

PUBLIC SOURCE → DOCUMENT → CLAIM → RAW/STAGED MENTION → CANONICAL ENTITY → OBSERVED
RELATION → DERIVED/INFERRED RELATION → ANALYSIS → INTERPRETATION. Do not bypass a layer
to make the graph look richer. LLM output is never `OBSERVED`, and an LLM is never the
sole, untraceable basis of an identity decision.
