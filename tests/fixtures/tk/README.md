# TK fixtures

**These fixtures are reconstructed, not raw snapshots.** The build environment that
wrote them had no direct HTTP access to `*.tk.elte.hu`, so each file is hand-written
HTML that reproduces the *fields and link patterns* observed on the live page on
2026-10-04 (via a text rendering of the page), not its markup. Contact details are
replaced with `XXX`.

They exist to test parser behaviour that does not depend on exact markup (labelled
fields, link patterns, host aliases, section headings). The parsers deliberately avoid
CSS-class selectors for this reason.

Replace them with real snapshots as soon as the pipeline runs with network access:

    szocatlas fixtures capture --source tk_recens --url https://recens.tk.elte.hu/kutato/koltai-julia

`fixtures.yaml` records origin URL, observation date and `reconstructed: true` for each
file; the capture command flips that flag. Reconstructed fixtures can never enter a
dataset release (`SourceDocument.synthetic` is set and QA fails the release).
