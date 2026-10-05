"""Pipeline orchestration: ingest (fetch+parse) and build (resolve+canonicalise+QA).

    ingest:  sources.yaml -> adapters -> data/raw (snapshots) + data/staged (records, claims)
    build:   data/staged + curated files -> derive -> resolve -> canonical -> QA -> data/releases/<id>
"""

from __future__ import annotations

import json
import logging
from collections import Counter, defaultdict
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from . import SCHEMA_VERSION, __version__
from .canonical.build import build_canonical
from .canonical.mentions import build_mentions
from .canonical.project_mentions import build_project_mentions
from .canonical.curated import Taxonomy, derive_classifications, registry_claims
from .discovery import follow_profile_project_links, merge_frontier
from .fetch import FixtureFetcher, PoliteFetcher, RawStore, ReplayFetcher, dump_jsonl
from .models.enums import EntityType, IdentityAnchor, ReviewStatus
from .models.provenance import Claim, SourceDocument, SourceRecord
from .registry import DEFAULT_REGISTRY, REPO_ROOT, Registry, load_registry
from .resolution.matcher import IdentityMap, Overrides, identity_anchors, resolve, write_review_queue
from .resolution.mentions import (
    MentionDecision,
    ResolutionConfig,
    claim_persons,
    load_mention_decisions,
    resolve_mentions,
)
from .resolution.projects import (
    ProjectDecision,
    ProjectIndex,
    claim_projects,
    load_project_decisions,
    resolve_project_mentions,
)
from .resolution.review import write_mention_review, write_project_review
from .validation.coverage import coverage_findings, coverage_report, render_coverage_markdown
from .validation.mention_stats import mention_stats, project_mention_stats
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
    diagnostics = {(r["document_id"], r["page_type"]): r for r in res.diagnostics}
    out = {
        "records": dump_jsonl(d / "records.jsonl", res.records),
        "claims": dump_jsonl(d / "claims.jsonl", {c.claim_id: c for c in res.claims}.values()),
        "documents": dump_jsonl(d / "documents.jsonl", docs.values()),
        "errors": dump_jsonl(d / "errors.jsonl", res.errors),
        # #16 / #12: what the crawl was told about, and what the parsers found in each page
        "frontier": dump_jsonl(d / "frontier.jsonl", sorted(res.frontier, key=lambda r: r["url"])),
        "diagnostics": dump_jsonl(d / "diagnostics.jsonl", [diagnostics[k] for k in sorted(diagnostics, key=lambda k: (k[1], diagnostics[k]["url"], k[0]))]),
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
    res.errors = [json.loads(x) for x in rows("errors.jsonl")]
    res.frontier = [json.loads(x) for x in rows("frontier.jsonl")]
    res.diagnostics = [json.loads(x) for x in rows("diagnostics.jsonl")]
    return res


def ingest(source_ids: list[str] | None, *, replay: bool = False, paths: Paths | None = None,
           registry: Registry | None = None) -> dict[str, dict]:
    """Fetch + parse the selected sources, then follow profile project links across them (#16).

    Every adapter runs first; only then are the project links its profiles stated routed to the source
    that owns the linked host (``discovery.follow_profile_project_links``), so a page linked from one
    site's profile and served by another is fetched by the site that owns it."""
    paths = paths or Paths()
    registry = registry or load_registry()
    store = RawStore(paths.raw)
    adapters: dict[str, SourceAdapter] = {}
    results: dict[str, ParseResult] = {}
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
        adapters[entry.source_id] = ADAPTERS[entry.adapter](entry, registry, fetcher)
        results[entry.source_id] = adapters[entry.source_id].run()
    discovery = follow_profile_project_links(adapters, results, registry)
    report: dict[str, dict] = {}
    for sid, res in results.items():
        adapter = adapters[sid]
        report[sid] = write_staged(paths, sid, res)
        (paths.raw / sid).mkdir(parents=True, exist_ok=True)
        with open(paths.raw / sid / "runs.jsonl", "a", encoding="utf-8") as fh:
            fh.write(json.dumps({
                "finished_at": datetime.now(UTC).isoformat(timespec="seconds"),
                "mode": "replay" if replay else "live",
                "adapter": f"{adapter.name}/{adapter.parser_version}",
                **report[sid],
            }) + "\n")
    report["_discovery"] = discovery
    return report


def ingest_fixtures(fixture_dir: Path, paths: Paths | None = None,
                    registry: Registry | None = None) -> dict[str, dict]:
    """Parse test fixtures as if fetched. Produces a *fixture* dataset only (never a release)."""
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
                 "project": adapter.parse_project, "listing": adapter.parse_listing,
                 "project_listing": lambda pg: adapter.parse_project_listing(pg, meta.get("status_label")),
                 }[meta["kind"]]
        res = parse(page)
        res.documents.append(page.document)
        by_source.setdefault(entry.source_id, ParseResult()).extend(res)
    return {sid: write_staged(paths, sid, res) for sid, res in by_source.items()}


def _stype(kind: str):
    from .models.enums import SourceType
    return {"person": SourceType.INSTITUTIONAL_PROFILE, "unit": SourceType.UNIT_PAGE,
            "project": SourceType.PROJECT_PAGE, "listing": SourceType.INSTITUTIONAL_LISTING,
            "project_listing": SourceType.INSTITUTIONAL_LISTING}[kind]


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
    anchors = identity_anchors(combined.records, claim_list, overrides)
    # person-to-person ambiguity between identities; mention ambiguity goes to mention_review.yaml
    write_review_queue(decisions, paths.review / "unresolved_people.yaml", only_refs=set(anchors))

    documents = list({d.document_id: d for d in combined.documents}.values())
    frontier = merge_frontier(combined.frontier)
    ds = canonicalize(combined.records, claim_list, documents, ref_to_id, decisions, anchors, registry,
                      ResolutionConfig.load(paths.config / "resolution.yaml"),
                      load_mention_decisions(paths.review / "manual_overrides.yaml"),
                      load_project_decisions(paths.review / "manual_overrides.yaml"), frontier)
    write_mention_review(ds, paths.review / "mention_review.yaml")
    write_project_review(ds, paths.review / "project_review.yaml")

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
        "entities": dict(Counter(e.entity_type.value for e in ds.entities.values()))
        | ({"PersonMention": len(ds.mentions)} if ds.mentions else {})
        | ({"ProjectMention": len(ds.project_mentions)} if ds.project_mentions else {}),
        "counts": person_counts(ds) | project_counts(ds, claim_list),
        "mention_resolution": mention_stats(ds),
        "project_mention_resolution": project_mention_stats(ds),
        "relations": dict(Counter(r.type.value for r in ds.relations)),
        "source_retrieval_window": _window(documents),
    }
    findings = run_checks(ds, decisions, paths.config / "qa_seeds.yaml")
    # #12: coverage is measured apart from consistency; gaps are warnings or info, never errors
    coverage = coverage_report(ds, registry=registry, frontier=frontier, diagnostics=combined.diagnostics,
                               errors=combined.errors, seeds_path=paths.config / "qa_seeds.yaml")
    findings += coverage_findings(coverage)
    manifest["source_set"] = {k: coverage["source_set"][k] for k in ("documents", "digest", "by_source", "by_page_type")}
    manifest["coverage"] = coverage_summary(coverage)
    manifest["quality"] = dict(Counter(f.severity for f in findings))

    out = paths.releases / release_id
    (out / "entities").mkdir(parents=True, exist_ok=True)
    for etype in sorted({e.entity_type for e in ds.entities.values()}, key=lambda t: t.value):
        dump_jsonl(out / "entities" / f"{etype.value}.jsonl",
                   sorted(ds.by_type(etype), key=lambda e: e.canonical_id))
    if ds.mentions:
        dump_jsonl(out / "entities" / "PersonMention.jsonl", [ds.mentions[k] for k in sorted(ds.mentions)])
    if ds.project_mentions:
        dump_jsonl(out / "entities" / "ProjectMention.jsonl",
                   [ds.project_mentions[k] for k in sorted(ds.project_mentions)])
    dump_jsonl(out / "relations.jsonl", sorted(ds.relations, key=lambda r: r.relation_id))
    dump_jsonl(out / "claims.jsonl", sorted(claim_list, key=lambda c: c.claim_id))
    dump_jsonl(out / "documents.jsonl", sorted(documents, key=lambda d: d.document_id))
    dump_jsonl(out / "matches.jsonl", sorted(decisions, key=lambda d: (d.left, d.right)))
    dump_jsonl(out / "frontier.jsonl", frontier)
    dump_jsonl(out / "parse_report.jsonl", sorted(combined.diagnostics, key=lambda r: (r["source_id"], r["page_type"], r["url"], r["document_id"])))
    (out / "coverage.json").write_text(json.dumps(coverage, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    (out / "coverage.md").write_text(render_coverage_markdown(coverage, release_id), encoding="utf-8")
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    (out / "quality_report.json").write_text(
        json.dumps([asdict(f) for f in findings], indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    (out / "quality_report.md").write_text(render_markdown(findings, manifest), encoding="utf-8")
    return out, findings


def coverage_summary(cov: dict[str, Any]) -> dict[str, Any]:
    """The few coverage figures worth keeping in the manifest; everything else is in coverage.json."""
    links = cov["discovery"]["project_links"]
    pm = cov["canonicalization"]["project_mentions"]["by_source"]
    return {
        "report": "coverage.md",
        "in_scope_project_links_fetched": links["in_scope"]["fetched"],
        "project_listing_urls_fetched": cov["discovery"]["project_listing_links"]["fetched"],
        "project_mentions_resolved_by_source": {s: v["resolved_share"] for s, v in pm.items() if s != "all"},
        "persons_without_project_edges": {
            s: v["without_project_edges"] for s, v in cov["network_bias"]["persons_without_project_edges"].items()},
    }


def person_counts(ds) -> dict[str, Any]:
    """Raw vs canonical person counts, always reported together (ADR-0006)."""
    persons = ds.by_type(EntityType.PERSON)
    evidence = Counter()
    for p in persons:
        kinds = set(p.identity_evidence)
        if IdentityAnchor.INSTITUTIONAL_PROFILE in kinds:
            evidence["profile_backed"] += 1
        elif kinds & {IdentityAnchor.MTMT, IdentityAnchor.ORCID}:
            evidence["externally_resolved"] += 1
        else:
            evidence["other_evidence"] += 1
    status = Counter(m.resolution.status.value for m in ds.mentions.values())
    unresolved = [m for m in ds.mentions.values() if not m.resolution.status.resolved]
    return {
        "persons": {
            "canonical": len(persons),
            "profile_backed": evidence["profile_backed"],
            "externally_resolved": evidence["externally_resolved"],
            "historical": 0,  # no historical sources yet
            "with_mtmt": sum(1 for p in persons if p.mtmt_id),
            "with_orcid": sum(1 for p in persons if p.orcid),
        },
        "person_mentions": {
            "total": len(ds.mentions),
            "resolved": len(ds.mentions) - len(unresolved),
            "unresolved": len(unresolved),
            "by_status": dict(sorted(status.items())),
            "unresolved_distinct_records": len({m.source_ref for m in unresolved}),
            "unresolved_distinct_names": len({m.normalized_name for m in unresolved}),
            "claims_only_on_unresolved_mentions": ds.mention_claims_skipped,
        },
        "person_like_records": len({r for p in persons for r in p.source_refs}
                                   | {m.source_ref for m in ds.mentions.values()}),
    }


def project_counts(ds, claims) -> dict[str, Any]:
    """Canonical Projects vs project mentions, always reported together (ADR-0008)."""
    projects = ds.by_type(EntityType.PROJECT)
    pms = list(ds.project_mentions.values())
    status = Counter(m.resolution.status.value for m in pms)
    unresolved = [m for m in pms if not m.resolution.status.resolved]
    titles: dict[str, set[str]] = defaultdict(set)
    for m in unresolved:
        titles[m.title_key].add(m.source_url)
    return {
        "projects": {
            "canonical": len(projects),
            "page_backed": sum(1 for p in projects if IdentityAnchor.PROJECT_PAGE in p.identity_evidence),
            "manual_only": sum(1 for p in projects if p.identity_evidence == [IdentityAnchor.MANUAL]),
            "with_grant_id": sum(1 for p in projects if p.grant_id),
        },
        "project_mentions": {
            "total": len(pms),
            "resolved": len(pms) - len(unresolved),
            "unresolved": len(unresolved),
            "by_status": dict(sorted(status.items())),
            "by_observation": dict(sorted(Counter(m.observation for m in pms).items())),
            "unresolved_distinct_records": len({m.source_ref for m in unresolved}),
            "unresolved_title_groups_on_several_pages": sum(1 for v in titles.values() if len(v) > 1),
            "with_activity_cues": sum(1 for m in pms if m.activity_cues),
            "claims_only_on_unresolved_project_mentions": ds.project_mention_claims_skipped,
        },
        "unattached_project_metadata": dict(sorted(Counter(
            c.qualifiers.get("kind", "other") for c in claims if c.predicate == "unattached_project_metadata").items())),
    }


def _window(documents: list[SourceDocument]) -> dict[str, str] | None:
    web = [d.retrieved_at for d in documents if not d.url.startswith("repo://")]
    if not web:
        return None
    return {"from": min(web).isoformat(), "until": max(web).isoformat()}


def canonicalize(records, claims, documents, ref_to_id, decisions, anchors, registry, config: ResolutionConfig,
                 mention_decisions: list[MentionDecision], project_decisions: list[ProjectDecision] | None = None,
                 frontier: list[dict] | None = None):
    """Claims + identity -> canonical dataset with person and project mentions (ADR-0006/0007/0008).

    Decisions never chain: project rules see certain evidence only; person rules see
    certain person evidence plus resolved projects (a one-way dependency, ADR-0008).
    """
    evidence: dict[str, set] = defaultdict(set)
    for ref, kinds in anchors.items():
        if ref in ref_to_id:
            evidence[ref_to_id[ref]] |= kinds
    ev = {k: sorted(v) for k, v in evidence.items()}
    docs = {d.document_id: d for d in documents}
    mb = build_mentions(records, claims, docs, ref_to_id, decisions, anchors, registry)
    pmb = build_project_mentions(records, claims, docs, ref_to_id, anchors, mb.own_claims)
    certain_persons = claim_persons(mb.mentions, mb.claim_mention, mb.own_claims, certain_only=True)
    certain_projects = claim_projects(pmb.mentions, pmb.claim_mention, pmb.own_claims, certain_only=True)
    # pass 1a: certain evidence only; the context project rules may use
    base = build_canonical(claims, documents, ref_to_id, ev, certain_persons, certain_projects)
    resolve_project_mentions(pmb.mentions, ProjectIndex(base, records, claims, certain_projects, ref_to_id),
                             config.project_resolver_version, project_decisions or [],
                             {r["url"]: r for r in frontier or []})
    projects = claim_projects(pmb.mentions, pmb.claim_mention, pmb.own_claims)
    # pass 1b: certain person evidence and every resolved project, the context #5 rules may use
    certain = build_canonical(claims, documents, ref_to_id, ev, certain_persons, projects)
    certain.project_mentions = pmb.mentions
    resolve_mentions(mb.mentions, certain, registry, config, ref_to_id, mention_decisions)
    # pass 2: project claims of every resolved mention onto its Person / Project
    ds = build_canonical(claims, documents, ref_to_id, ev, claim_persons(mb.mentions, mb.claim_mention, mb.own_claims),
                         projects)
    ds.anchor_refs = set(anchors)
    ds.mentions = mb.mentions
    ds.project_mentions = pmb.mentions
    return ds
