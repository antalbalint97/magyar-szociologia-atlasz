# ADR-0002: Release files are the source of truth; Neo4j is a projection

Status: accepted (2026-10-04)

Decision: each build writes a self-contained release directory (JSONL + manifest +
quality report). Neo4j is loaded from a release idempotently and can be dropped at any
time. The web app reads either a release (file backend) or Neo4j through one interface.

Consequences: + portable dataset (JSONL works with pandas/Polars/R, citable by release
id); + no vendor lock-in; + the app runs without a database. − Two read paths in the web
app to keep in sync (covered by a shared `GraphStore` interface).
