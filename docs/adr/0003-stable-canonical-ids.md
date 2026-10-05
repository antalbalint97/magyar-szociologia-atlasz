# ADR-0003: Canonical ids are minted once and persisted in git

Status: accepted (2026-10-04)

Decision: ids are `<prefix>_<10 hex>` from a hash of the first source ref, recorded in
`review/identity_map.jsonl` (committed). Later builds reuse recorded ids; merges keep the
oldest id; splits mint a new id for the separated part and record `previous_id`.

Consequences: + ids survive new sources and parser changes, so external citations and
manual overrides stay valid; + reproducible on a fresh checkout. − The map must be
committed with every build that adds entities.

## Addendum (2026-10-04, #27): which id survives a merge

When a merge (hard id or manual `same_as`) joins records that already carry different
ids, one id survives and the moved rows record `previous_id`. The survivor is, in order:

1. the id a reviewer names as `survivor` on the `same_as` entry in
   `review/manual_overrides.yaml`, with the reason in its `evidence`;
2. the oldest `assigned_at`;
3. the id whose records carry the stronger identity anchor (MTMT/ORCID over a profile alone);
4. the lowest id.

The rule depends only on the identity map and the evidence, never on input order. A
manual `same_as` between two identity records is a canonicalisation decision: the release
contains one Person with both records' claims and profile URLs, never a `SAME_AS` edge
between two Persons. First case: Stefkovics Ádám, `per_405c6c90b1` → `per_07c6bb757b`.
