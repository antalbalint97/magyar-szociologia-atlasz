# ADR-0001: Claims are the unit of storage; entities are projections

Status: accepted (2026-10-04)

Context: the brief requires per-statement provenance, preserved conflicts, and
distinguishing observed from inferred relations.

Decision: parsers emit `Claim`s bound to `SourceDocument`s. Canonical entities/relations
are rebuilt from claims on every build. No canonical value without a claim.

Consequences: + provenance and conflicts come for free; + re-parsing is deterministic
(claim ids are content hashes); + manual review is a list of claim ids. − More records
than a plain entity table (≈ 15–30 claims per person); fine at the expected scale
(10³–10⁴ people).
