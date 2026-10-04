# ADR-0003: Canonical ids are minted once and persisted in git

Status: accepted (2026-10-04)

Decision: ids are `<prefix>_<10 hex>` from a hash of the first source ref, recorded in
`review/identity_map.jsonl` (committed). Later builds reuse recorded ids; merges keep the
oldest id; splits mint a new id for the separated part and record `previous_id`.

Consequences: + ids survive new sources and parser changes, so external citations and
manual overrides stay valid; + reproducible on a fresh checkout. − The map must be
committed with every build that adds entities.
