"""Pipeline orchestration: ingest (fetch+parse) and build (resolve+canonicalise+QA).

    ingest:  sources.yaml -> adapters -> data/raw (snapshots) + data/staged (records, claims)
    build:   data/staged + curated files -> derive -> resolve -> canonical -> QA -> data/releases/<id>
"""

from __future__ import annotations

import json
import logging
from collections import Counter
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

import yaml

from . import SCHEMA_VERSION, __version__
from .canonical.build import build_canonical
from .canonical.curated import Taxonomy, derive_classifications, registry_claims
from .fetch import FixtureFetcher, PoliteFetcher, RawStore, ReplayFetcher, dump_jsonl
from .models.enums import ReviewStatus
from .models.provenance import Claim, SourceDocument, SourceRecord
from .registry import DEFAULT_REGISTRY, REPO_ROOT, Registry, load_registry
from .resolution.matcher import IdentityMap, Overrides, resolve, write_review_queue
from .sources.base import ParseResult, SourceAdapter
from .sources.tk.adapter import TKAdapter
from .validation.qa import render_markdown, run_checks

log = logging.getLogger(__name__)

ADAPTERS: dict[str, type[SourceAdapter]] = {"tk": TKAdapter}

DATA = REPO_ROOT / "data"
REVIEW = REPO_ROOT / "review"
CONFIG = REPO_ROOT / "config"


class Paths:
    def __init__(self, root: Path = REPO_ROOT):
        self.root = root
        self.raw = root / "data" / "raw"
        self.staged = root / "data" / "staged"
        self.releases = root / "data" / "releases"
        self.review = root / "review"
        self.config = root / "config"


def write_staged(paths: Paths, source_id: str, res: ParseResult) -> dict[str, int]:
    d = paths.staged / source_id
    docs = {doc.document_id: doc for doc in res.documents}
    out = {
        "records": dump_jsonl(d / "records.jsonl", res.records),
        "claims": dump_jsonl(d / "claims.jsonl", {c.claim_id: c for c in res.claims}.values()),
        "documents": dump_jsonl(d / "documents.jsonl", docs.values()),
        "errors": dump_jsonl(d / "errors.jsonl", res.errors),
    }
    return out


def read_staged(paths: Paths, source_id: str) -> ParseResult:
    d = paths.staged / source_id
    res = ParseResult()
    if not d.exists():
        return res

    def rows(name):
        p = d / name
        return [line for line in p.read_text(encoding="utf-8").splitlines() if line.strip()] if p.exists() else []

    res.records = [SourceRecord.model_validate_json(x) for x in rows("records.jsonl")]
    res.claims = [Claim.model_validate_json(x) for x in rows("claims.jsonl")]
    res.documents = [SourceDocument.model_validate_json(x) for x in rows("documents.jsonl")]
    return res


def ingest(source_ids: list[str] | None, *, replay: bool = False, paths: Paths | None = None,
           registry: Registry | None = None) -> dict[str, dict]:
    paths = paths or Paths()
    registry = registry or load_registry()
    store = RawStore(paths.raw)
    report = {}
    for entry in registry.sources:
        if source_ids and entry.source_id not in source_ids:
            continue
        if not source_ids and not entry.enabled:
            continue
        if entry.adapter not in ADAPTERS:
            log.warning("%s: no adapter %r", entry.source_id, entry.adapter)
            continue
        policy = registry.policy(entry)
        fetcher = ReplayFetcher(store, registry.host_aliases()) if replay else \
            PoliteFetcher(store, policy, registry.host_aliases())
        adapter = ADAPTERS[entry.adapter](entry, registry, fetcher)
        res = adapter.run()
        report[entry.source_id] = write_staged(paths, entry.source_id, res)
        with open(paths.raw / entry.source_id / "runs.jsonl", "a", encoding="utf-8") as fh:
            fh.write(json.dumps({
                "finished_at": datetime.now(UTC).isoformat(timespec="seconds"),
                "mode": "replay" if replay else "live",
                "adapter": f"{adapter.name}/{adapter.parser_version}",
                **report[entry.source_id],
            }) + "\n")
    return report


def ingest_fixtures(fixture_dir: Path, paths: Paths | None = None,
                    registry: Registry | None = None) -> dict[str, dict]:
    """Parse reconstructed fixtures as if fetched. Produces a *fixture* dataset only."""
    paths = paths or Paths()
    registry = registry or load_registry()
    spec = yaml.safe_load((fixture_dir / "fixtures.yaml").read_text(encoding="utf-8"))
    aliases = registry.host_aliases()
    by_source: dict[str, ParseResult] = {}
    for fname, meta in spec.items():
        observed = datetime.fromisoformat(str(meta["observed"])).replace(tzinfo=UTC)
        fetcher = FixtureFetcher({meta["url"]: fixture_dir / fname}, aliases, observed)
        entry = registry.source(meta["source_id"])
        adapter = ADAPTERS[entry.adapter](entry, registry, fetcher)
        page = fetcher.get(meta["url"], source_id=entry.source_id, source_type=_stype(meta["kind"]))
        parse = {"person": adapter.parse_person, "unit": adapter.parse_unit,
                 "project": adapter.parse_project, "listing": adapter.parse_listing}[meta["kind"]]
        res = parse(page)
        res.documents.append(page.document)
        by_source.setdefault(entry.source_id, ParseResult()).extend(res)
    return {sid: write_staged(paths, sid, res) for sid, res in by_source.items()}


def _stype(kind: str):
    from .models.enums import SourceType
    return {"person": SourceType.INSTITUTIONAL_PROFILE, "unit": SourceType.UNIT_PAGE,
            "project": SourceType.PROJECT_PAGE, "listing": SourceType.INSTITUTIONAL_LISTING}[kind]


def _apply_review(claims: list[Claim], path: Path) -> list[Claim]:
    if not path.exists():
        return claims
    decisions = {d["claim_id"]: d for d in (yaml.safe_load(path.read_text(encoding="utf-8")) or {})
                 .get("decisions") or []}
    out = []
    for c in claims:
        if c.claim_id in decisions:
            c.review_status = ReviewStatus(decisions[c.claim_id]["status"])
        if c.review_status is not ReviewStatus.REJECTED:
            out.append(c)
    return out


def build(release_id: str, *, source_ids: list[str] | None = None, paths: Paths | None = None,
          registry_path: Path = DEFAULT_REGISTRY, persist_identity: bool = True) -> tuple[Path, list]:
    paths = paths or Paths()
    registry = load_registry(registry_path)
    taxonomy = Taxonomy(paths.config / "taxonomy" / "topics.yaml", paths.config / "taxonomy" / "methods.yaml")

    combined = registry_claims(registry, registry_path)
    combined.extend(taxonomy.claims())
    used_sources = []
    for d in sorted(paths.staged.iterdir()) if paths.staged.exists() else []:
        if d.is_dir() and (not source_ids or d.name in source_ids):
            staged = read_staged(paths, d.name)
            if staged.claims:
                used_sources.append(d.name)
                combined.extend(staged)

    claims = {c.claim_id: c for c in combined.claims}
    derived = derive_classifications(list(claims.values()), taxonomy)
    claims.update({c.claim_id: c for c in derived})
    claim_list = _apply_review(list(claims.values()), paths.review / "disputed_claims.yaml")

    identity = IdentityMap(paths.review / "identity_map.jsonl")
    overrides = Overrides.load(paths.review / "manual_overrides.yaml")
    ref_to_id, decisions = resolve(combined.records, claim_list, overrides, identity)
    if persist_identity:
        identity.save()
    write_review_queue(decisions, paths.review / "unresolved_people.yaml")

    documents = list({d.document_id: d for d in combined.documents}.values())
    ds = build_canonical(claim_list, documents, ref_to_id)

    synthetic = any(d.synthetic for d in documents)
    parser_versions = dict(sorted({c.parser: c.parser_version for c in claim_list}.items()))
    manifest = {
        "release_id": release_id,
        "dataset_kind": "fixture" if synthetic else "snapshot",
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "schema_version": SCHEMA_VERSION,
        "software_version": __version__,
        "sources": used_sources,
        "parser_versions": parser_versions,
        "documents": len(documents),
        "claims": len(claim_list),
        "entities": dict(Counter(e.entity_type.value for e in ds.entities.values())),
        "relations": dict(Counter(r.type.value for r in ds.relations)),
        "source_retrieval_window": _window(documents),
    }
    findings = run_checks(ds, decisions, paths.config / "qa_seeds.yaml")
    manifest["quality"] = dict(Counter(f.severity for f in findings))

    out = paths.releases / release_id
    (out / "entities").mkdir(parents=True, exist_ok=True)
    for etype in sorted({e.entity_type for e in ds.entities.values()}, key=lambda t: t.value):
        dump_jsonl(out / "entities" / f"{etype.value}.jsonl",
                   sorted(ds.by_type(etype), key=lambda e: e.canonical_id))
    dump_jsonl(out / "relations.jsonl", sorted(ds.relations, key=lambda r: r.relation_id))
    dump_jsonl(out / "claims.jsonl", sorted(claim_list, key=lambda c: c.claim_id))
    dump_jsonl(out / "documents.jsonl", sorted(documents, key=lambda d: d.document_id))
    dump_jsonl(out / "matches.jsonl", sorted(decisions, key=lambda d: (d.left, d.right)))
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    (out / "quality_report.json").write_text(
        json.dumps([asdict(f) for f in findings], indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    (out / "quality_report.md").write_text(render_markdown(findings, manifest), encoding="utf-8")
    return out, findings


def _window(documents: list[SourceDocument]) -> dict[str, str] | None:
    web = [d.retrieved_at for d in documents if not d.url.startswith("repo://")]
    if not web:
        return None
    return {"from": min(web).isoformat(), "until": max(web).isoformat()}
