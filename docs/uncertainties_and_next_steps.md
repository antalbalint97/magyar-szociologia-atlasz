# Uncertainties and next steps

## What is not known yet (and is therefore not in the data)

1. **No live crawl has run.** The build environment's egress policy blocked every source
   host. TK site structure was inspected through a text-rendering web reader; fixtures are
   reconstructions of the observed fields, not raw HTML. Until a live run:
   * parsers are untested on real markup (they avoid class selectors to reduce that risk);
   * the only release is `fixture-sample`, flagged `dataset_kind: fixture`.
2. **TK listing pagination.** Pages expose both `?page=N` and letter filters
   (`/kutatok/<letter>`). The adapter crawls both and de-duplicates, so either scheme is
   enough; whether `?page=` is honoured server-side is unconfirmed.
3. **Unverified TK paths:** `politikatudomany.tk.elte.hu/kutatok` and `jog…/kutatok` are
   assumed from the shared CMS (`verified: false`). Kisebbségkutató department page URLs
   are unknown.
4. **Research groups on separate sites** (Lendület DS4 on recens `/en/…`, reprosoc, hpops,
   ENL, MILAB, ESS, Mobilitás Kutatási Centrum) are catalogued but have no parser. Until
   then, group membership appears only as `PARTICIPATES_IN` a project-like entity taken
   from profiles, e.g. Koltai Júlia → "MTA–TK Lendület … Kutatócsoport". Promoting such
   entities to `ResearchGroup` needs the group page as evidence.
5. **TK institutional succession** (MTA → ELKH → HUN-REN → ELTE): sequence visible from
   hostnames, dates not sourced. Not encoded (`review/unresolved.yaml#tk_succession`).
6. **Stale or conflicting page content**: e.g. a profile biography calling someone head
   of a department whose page names a different head. Both claims are kept; biographies are
   stored as text and not parsed into relations.
7. **Profile authorship** is unknown (researcher vs institution), so profile statements
   are `INSTITUTIONAL` with an authorship qualifier, not `SELF_DECLARED`.
8. **Topic/method derivation is lexical** (keyword map v0.1). It under-detects methods,
   because TK profiles mostly list topics. Method edges will improve with publication
   data (MTMT keywords, abstracts) and project descriptions, each labelled `DERIVED` or
   `INFERRED`.
9. **Seeds not yet covered by fixtures:** Ságvári Bence, Durst Judit, Virág Tünde.
   Their home units must come from the live crawl (ELTE TáTK, KRTK, TK), not be assumed.

## Next steps

Tracked as GitHub Issues, not here. See `docs/status.md` for the current snapshot and the
Milestone 2 tracking issue (#3) for the ordered workstreams. Step 1 of the original list
(the live TK crawl) is done in PR #2 (release `2026-10-tk`). The remaining items map to
issues: research-group pages #16, other institutions #21, MTMT #23, doktori.hu #22,
historical sources #24, ethics #25.
