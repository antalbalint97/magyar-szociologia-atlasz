"""Command line interface: ``szocatlas <command>``."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import UTC, datetime
from pathlib import Path

from .registry import REPO_ROOT, load_registry


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="szocatlas", description=__doc__)
    ap.add_argument("-v", "--verbose", action="store_true")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("sources", help="list the source registry")

    p = sub.add_parser("ingest", help="fetch + parse sources into data/raw and data/staged")
    p.add_argument("sources", nargs="*", help="source ids (default: all enabled)")
    p.add_argument("--replay", action="store_true", help="re-parse from raw snapshots only, no network")

    p = sub.add_parser("ingest-fixtures", help="parse test fixtures into data/staged (fixture dataset)")
    p.add_argument("--dir", default=str(REPO_ROOT / "tests" / "fixtures" / "tk"))

    p = sub.add_parser("build", help="resolve, canonicalise, validate -> data/releases/<id>")
    p.add_argument("--release", default=datetime.now(UTC).strftime("%Y-%m-%d"))
    p.add_argument("--sources", nargs="*")
    p.add_argument("--allow-errors", action="store_true")

    p = sub.add_parser("validate", help="print the quality report of a release")
    p.add_argument("release")

    p = sub.add_parser("neo4j-load", help="idempotently load a release into Neo4j")
    p.add_argument("release")
    p.add_argument("--prune", action="store_true", help="remove nodes/edges not in this release")

    p = sub.add_parser("fixtures", help="capture a live page as a parser fixture")
    p.add_argument("action", choices=["capture"])
    p.add_argument("--source", required=True)
    p.add_argument("--url", required=True)
    p.add_argument("--kind", required=True, choices=["person", "unit", "project", "listing", "project_listing"])
    p.add_argument("--name", required=True, help="fixture file name, e.g. recens_koltai_julia.html")
    p.add_argument("--status-label", help="project_listing only: the category's status (futó / lezárt)")

    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO, format="%(levelname)s %(message)s")

    from . import pipeline

    if args.cmd == "sources":
        reg = load_registry()
        for s in reg.sources:
            flag = "on " if s.enabled else "off"
            print(f"[{flag}] {s.source_id:24} {s.adapter or '-':5} verified={str(s.verified):5} {s.base_url or ''}")
        return 0
    if args.cmd == "ingest":
        print(json.dumps(pipeline.ingest(args.sources or None, replay=args.replay), indent=2))
        return 0
    if args.cmd == "ingest-fixtures":
        print(json.dumps(pipeline.ingest_fixtures(Path(args.dir)), indent=2))
        return 0
    if args.cmd == "build":
        out, findings = pipeline.build(args.release, source_ids=args.sources)
        errors = [f for f in findings if f.severity == "error"]
        print(f"release written to {out.relative_to(REPO_ROOT)}")
        print((out / "manifest.json").read_text(encoding="utf-8"))
        if errors:
            print(f"{len(errors)} QA error(s); see quality_report.md", file=sys.stderr)
            return 0 if args.allow_errors else 2
        return 0
    if args.cmd == "validate":
        print((REPO_ROOT / "data" / "releases" / args.release / "quality_report.md").read_text(encoding="utf-8"))
        return 0
    if args.cmd == "neo4j-load":
        from .graph.loader import load_release_from_env
        print(json.dumps(load_release_from_env(REPO_ROOT / "data" / "releases" / args.release,
                                               prune=args.prune), indent=2))
        return 0
    if args.cmd == "fixtures":
        return _capture(args)
    return 1


def _capture(args) -> int:
    import yaml

    from .fetch import PoliteFetcher, RawStore
    from .models.enums import SourceType
    from .scrub import scrub_html

    reg = load_registry()
    entry = reg.source(args.source)
    fetcher = PoliteFetcher(RawStore(REPO_ROOT / "data" / "raw"), reg.policy(entry), reg.host_aliases())
    page = fetcher.get(args.url, source_id=entry.source_id, source_type=SourceType.INSTITUTIONAL_PROFILE)
    fdir = REPO_ROOT / "tests" / "fixtures" / entry.adapter
    # contact details and scripts are stripped; the rest of the markup is kept as served
    (fdir / args.name).write_text(scrub_html(page.text), encoding="utf-8")
    spec_path = fdir / "fixtures.yaml"
    spec = yaml.safe_load(spec_path.read_text(encoding="utf-8")) or {}
    spec[args.name] = {"url": args.url, "source_id": entry.source_id, "kind": args.kind,
                       "observed": page.document.retrieved_at.date().isoformat(), "reconstructed": False,
                       "content_sha256": page.document.content_sha256, "scrubbed": True}
    if args.status_label:
        spec[args.name]["status_label"] = args.status_label
    spec_path.write_text(yaml.safe_dump(spec, allow_unicode=True, sort_keys=True), encoding="utf-8")
    print(f"captured {args.url} -> {fdir / args.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
