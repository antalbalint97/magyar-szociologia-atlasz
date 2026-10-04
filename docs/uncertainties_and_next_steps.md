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

## Next steps, in order

1. **Run the TK adapter with network access** (a local machine, or a cloud environment
   that allows `*.tk.elte.hu`, `*.tk.hu`, `*.tk.mta.hu`): `szocatlas ingest`, then
   `szocatlas fixtures capture …` for one page of each kind, flip the fixtures to real
   snapshots, re-run `pytest`, fix parsers where real markup differs.
2. Build the first real release (`szocatlas build --release 2026-10-tk`), review
   `quality_report.md` and `review/unresolved_people.yaml`, record decisions.
3. Parser for research-group sites (recens `/en/` group pages, Lendület sites) →
   `ResearchGroup` + `LEADS` / `MEMBER_OF`.
4. Adapters for ELTE TáTK, KRTK, TÁRKI, Corvinus, PTE (sociology + Romology), Debrecen,
   Szeged, Miskolc, PPKE, KSH NKI (see docs/sources.md for observed entry points).
5. MTMT author records (hard identifiers, publications) → co-authorship, method signals.
6. doktori.hu → `SUPERVISED_BY`, doctoral schools (academic genealogy).
7. Wayback snapshots of institutional staff pages → `DERIVED` historical intervals.
8. Events for institutional history (TK succession, ELTE TáTK units, KRTK) with citable
   sources.
9. Frontend: institution tree, topic/method maps, timeline once intervals exist;
   benchmark Sigma.js vs Cytoscape.js before a community overview.
10. Ethics: confirm GDPR basis and a correction procedure with the host institution
    before any public deployment.
