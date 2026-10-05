# TK fixtures

**These fixtures are real page snapshots** from the first live crawl (2026-10-04),
captured with

    szocatlas fixtures capture --source tk_recens --url https://recens.tk.elte.hu/kutato/koltai-julia \
        --kind person --name recens_koltai_julia.html

`capture` runs the page through `szocatlas.scrub.scrub_html` before writing it:
e-mail local parts become `xxx@<domain>`, phone and room values become `XXX`, and
scripts, iframes and HTML comments are removed. Everything else is the markup as
served, so the tests exercise the real structure (an `<h2>` page title, `<h5>`
section headings, `<br>`-separated project lines, `<article>` project listings).

`fixtures.yaml` records each file's origin URL, observation date, kind and the
sha256 of the unscrubbed response. The raw responses themselves live only in
`data/raw/` and are never committed.

The fixture dataset (`szocatlas ingest-fixtures`) is still marked synthetic: it is a
handful of hand-picked pages, so it can never pose as a release snapshot.

The earlier hand-reconstructed fixtures were replaced by these snapshots; the
parser differences that the real markup exposed are listed in CHANGELOG.md.

Ten project-page fixtures were added for #16 (captured 2026-10-04/05, kind `project`), each
because it carries markup the parser had not seen: "Támogatási forrás" and "Kutatás időtartama"
labels, month-name periods, a bare funder or period line in a header block, participants given
only as links, and two narrative pages that must produce no funder, period or participants
(`ki_project_kutterv_narrativ.html`, `ki_project_egyhazak_szerepvallalasa.html`). They are real
pages, scrubbed like the rest; the tests read what is on the page and nothing else.
