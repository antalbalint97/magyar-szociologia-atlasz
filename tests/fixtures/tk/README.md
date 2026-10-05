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

Sixteen SZI project-page fixtures (`szi_heading_*.html`) were added for #31. They are real pages
of the old SZI project template, **written from the stored raw snapshots of the 2026-10-04 crawl
(no page was fetched again)**: the page body is the snapshot's markup, scrubbed like the rest, and
the file's `content_sha256` in `fixtures.yaml` is that of the unscrubbed snapshot. Each is there
for the markup it carries: a heading with `<p>`/`<br>` lines, with `<div>` blocks, with bare text,
with a Word-pasted wrapper (conditional comments and styles), with `<ul>`/`<li>`, a placeholder
value ("..."), a duplicate name, an organisation or country after the names, org-first and
`Family, Given` lines, a `<p>` used as a heading, and old-site profile links. In five of them a
heading must yield nothing (its value is a placeholder, or organisations and countries, or
org-prefixed lines); `szi_heading_placeholder_dots.html` yields no lead and no participant at
all. The tests read what is on the page and nothing else.
