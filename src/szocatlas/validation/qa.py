"""VALIDATION: data-quality checks run after every build (spec section 18).

Each check returns findings with a severity:
  error   -> the release is not publishable (``szocatlas build`` exits non-zero
             unless --allow-errors)
  warning -> needs review, release allowed
  info    -> statistics and coverage
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import yaml

from ..canonical.build import CanonicalDataset
from ..models.entities import Person, Project
from ..models.enums import EntityType, EpistemicStatus, MatchStatus, RelationType
from ..normalize.names import name_key, order_free_key
from ..resolution.matcher import MatchDecision

AFFILIATION_TYPES = {RelationType.AFFILIATED_WITH, RelationType.MEMBER_OF, RelationType.LEADS,
                     RelationType.WORKED_AT}


@dataclass
class Finding:
    check: str
    severity: str
    message: str
    subjects: list[str] = field(default_factory=list)
    detail: dict[str, Any] = field(default_factory=dict)


def _url_ok(u: str) -> bool:
    if u.startswith("repo://"):
        return True
    p = urlsplit(u)
    return p.scheme in ("http", "https") and bool(p.hostname) and "." in (p.hostname or "")


def run_checks(ds: CanonicalDataset, decisions: list[MatchDecision], seeds_path: Path | None) -> list[Finding]:
    F: list[Finding] = []
    claims_by_id = {c.claim_id: c for c in ds.claims}

    # build-stage issues
    for kind, items in _group(ds.issues, "check").items():
        sev = "error" if kind in ("dangling_relation", "id_type_collision", "unresolved_subject",
                                  "unresolved_object", "unknown_relation_type") else "warning"
        F.append(Finding(f"build.{kind}", sev, f"{len(items)} build issue(s): {kind}", detail={"items": items[:20]}))

    # provenance
    missing_docs = {c.evidence.document_id for c in ds.claims} - set(ds.documents)
    if missing_docs:
        F.append(Finding("provenance.missing_document", "error",
                         f"{len(missing_docs)} claims cite documents that are not in the dataset",
                         list(missing_docs)[:20]))
    for e in ds.entities.values():
        for fname, ids in e.provenance.items():
            bad = [i for i in ids if i not in claims_by_id]
            if bad or not ids:
                F.append(Finding("provenance.field_without_claim", "error",
                                 f"{e.canonical_id}.{fname} has no valid supporting claim", [e.canonical_id]))
    for r in ds.relations:
        if not r.claim_ids:
            F.append(Finding("provenance.relation_without_claim", "error", r.relation_id, [r.relation_id]))
        if r.epistemic_status is not EpistemicStatus.OBSERVED and not r.derivation_method:
            F.append(Finding("provenance.inferred_without_method", "error", r.relation_id, [r.relation_id]))
    synthetic = [d.document_id for d in ds.documents.values() if d.synthetic]
    if synthetic:
        F.append(Finding("provenance.synthetic_documents", "warning",
                         f"{len(synthetic)} documents are reconstructed fixtures; this dataset is NOT a "
                         "publishable release", synthetic[:10]))

    # temporal
    for r in ds.relations:
        if r.valid_from and r.valid_until and r.valid_from[:4] > r.valid_until[:4]:
            F.append(Finding("temporal.impossible_interval", "error",
                             f"{r.relation_id} {r.valid_from} > {r.valid_until}", [r.relation_id]))
    for p in ds.by_type(EntityType.PROJECT):
        assert isinstance(p, Project)
        if p.start and p.end and p.start > p.end:
            F.append(Finding("temporal.project_interval", "error", f"{p.canonical_id} {p.start} > {p.end}",
                             [p.canonical_id]))
    for p in ds.by_type(EntityType.PERSON):
        assert isinstance(p, Person)
        if p.birth_year and p.death_year and p.birth_year > p.death_year:
            F.append(Finding("temporal.life_span", "error", p.canonical_id, [p.canonical_id]))

    # urls
    for e in ds.entities.values():
        urls = [getattr(e, "website", None)] + list(getattr(e, "profile_urls", []) or [])
        for u in filter(None, urls):
            if not _url_ok(u):
                F.append(Finding("url.malformed", "warning", f"{e.canonical_id}: {u}", [e.canonical_id]))

    # structure
    parent = defaultdict(list)
    for r in ds.relations:
        if r.type is RelationType.PART_OF:
            parent[r.source_id].append(r.target_id)
    for start in parent:
        seen, stack = set(), [(start, [start])]
        while stack:
            node, path = stack.pop()
            for nxt in parent.get(node, []):
                if nxt == start:
                    F.append(Finding("structure.cyclic_hierarchy", "error", " -> ".join(path + [nxt]), path))
                elif nxt not in seen:
                    seen.add(nxt)
                    stack.append((nxt, path + [nxt]))
    affiliated = {r.source_id for r in ds.relations if r.type in AFFILIATION_TYPES}
    orphans = [p.canonical_id for p in ds.by_type(EntityType.PERSON) if p.canonical_id not in affiliated]
    if orphans:
        F.append(Finding("structure.orphan_person", "warning",
                         f"{len(orphans)} people have no affiliation/membership edge", orphans[:50]))
    units_without_parent = [u.canonical_id for t in (EntityType.ORG_UNIT, EntityType.RESEARCH_GROUP)
                            for u in ds.by_type(t) if u.canonical_id not in parent]
    if units_without_parent:
        F.append(Finding("structure.orphan_unit", "warning",
                         f"{len(units_without_parent)} organisational units have no PART_OF edge",
                         units_without_parent))

    # identity
    pending = [d for d in decisions if d.status is MatchStatus.POSSIBLE and d.entity_type is EntityType.PERSON]
    if pending:
        F.append(Finding("identity.possible_duplicates", "warning",
                         f"{len(pending)} possible person matches await review (review/unresolved_people.yaml)",
                         detail={"pairs": [[d.left_label, d.right_label, d.method] for d in pending[:20]]}))
    labels = defaultdict(list)
    for p in ds.by_type(EntityType.PERSON):
        labels[order_free_key(p.label)].append(p.canonical_id)
    same_label = {k: v for k, v in labels.items() if len(v) > 1}
    if same_label:
        F.append(Finding("identity.same_name_distinct_ids", "info",
                         f"{len(same_label)} names are carried by more than one canonical person "
                         "(expected until reviewed; never auto-merged)", detail={"names": same_label}))
    for p in ds.by_type(EntityType.PERSON):
        keys = {name_key(n) for n in [p.label, *getattr(p, "alternate_names", [])]}
        orders = {order_free_key(n) for n in [p.label, *getattr(p, "alternate_names", [])]}
        if len(orders) > 1:
            F.append(Finding("identity.suspicious_merge", "warning",
                             f"{p.canonical_id} merges different names: {sorted(keys)}", [p.canonical_id]))
        if "mtmt_id" in p.conflicts or "orcid" in p.conflicts:
            F.append(Finding("identity.conflicting_hard_ids", "error",
                             f"{p.canonical_id} carries several MTMT ids / ORCIDs", [p.canonical_id]))

    # conflicts
    for e in ds.entities.values():
        for fname, vals in e.conflicts.items():
            F.append(Finding("conflict.field", "warning",
                             f"{e.canonical_id}.{fname}: sources disagree ({len(vals)} values)", [e.canonical_id],
                             {"values": [v.value for v in vals]}))
    for p in ds.by_type(EntityType.PERSON):
        pts = {_core_position(x) for x in getattr(p, "position_titles", [])}
        if len(pts) > 1:
            F.append(Finding("conflict.positions", "warning",
                             f"{p.label} ({p.canonical_id}) has different current positions: {sorted(pts)}",
                             [p.canonical_id]))

    # projects that look like something else
    for p in ds.by_type(EntityType.PROJECT):
        if re.search(r"(journal|folyóirat|editor|főszerkesztő)", p.label, re.I):
            F.append(Finding("review.project_label_suspicious", "warning",
                             f"project '{p.label}' may be a journal/role listed under Projektek", [p.canonical_id]))

    # coverage & stats
    counts = Counter(e.entity_type.value for e in ds.entities.values())
    rel_counts = Counter(r.type.value for r in ds.relations)
    status_counts = Counter(r.epistemic_status.value for r in ds.relations)
    F.append(Finding("stats.entities", "info", "entity counts", detail=dict(counts)))
    F.append(Finding("stats.relations", "info", "relation counts", detail=dict(rel_counts)))
    F.append(Finding("stats.epistemic", "info", "relations by epistemic status", detail=dict(status_counts)))
    if seeds_path and seeds_path.exists():
        F += _seed_coverage(ds, seeds_path)
    return F


def _core_position(s: str) -> str:
    s = re.sub(r"^kutató,\s*", "", s.strip(), flags=re.I)
    return re.sub(r"\s*\(TK [^)]+\)\s*$", "", s).lower()


def _group(items, key):
    out = defaultdict(list)
    for it in items:
        out[it[key]].append(it)
    return out


def _seed_coverage(ds: CanonicalDataset, path: Path) -> list[Finding]:
    seeds = yaml.safe_load(path.read_text(encoding="utf-8"))["seeds"]
    index = defaultdict(list)
    for p in ds.by_type(EntityType.PERSON):
        for n in [p.label, *getattr(p, "alternate_names", [])]:
            index[order_free_key(n)].append(p)
    units = {e.canonical_id: e.label for e in ds.entities.values()}
    out = []
    for s in seeds:
        hits = index.get(order_free_key(s["name"]), [])
        if not hits:
            out.append(Finding("seeds.missing", "warning", f"QA seed not in dataset: {s['name']}",
                               detail={"expect": s.get("expect")}))
            continue
        for p in hits:
            aff = sorted({units.get(r.target_id, r.target_id) for r in ds.relations
                          if r.source_id == p.canonical_id and r.type in AFFILIATION_TYPES})
            topics = sorted({units.get(r.target_id) for r in ds.relations if r.source_id == p.canonical_id
                             and r.type is RelationType.WORKS_ON_TOPIC})
            methods = sorted({units.get(r.target_id) for r in ds.relations if r.source_id == p.canonical_id
                              and r.type is RelationType.USES_METHOD})
            out.append(Finding("seeds.present", "info", f"{s['name']} -> {p.canonical_id}",
                               [p.canonical_id], {"affiliations": aff, "topics": topics, "methods": methods}))
    return out


def render_markdown(findings: list[Finding], manifest: dict[str, Any]) -> str:
    sev_order = {"error": 0, "warning": 1, "info": 2}
    lines = [
        f"# Data-quality report: {manifest['release_id']}",
        "",
        f"- generated_at: {manifest['generated_at']}",
        f"- dataset_kind: **{manifest['dataset_kind']}**",
        f"- schema_version: {manifest['schema_version']}",
        f"- sources: {', '.join(manifest['sources'])}",
        f"- parsers: {', '.join(f'{k}={v}' for k, v in manifest['parser_versions'].items())}",
        "",
        "| severity | count |",
        "|---|---|",
    ]
    c = Counter(f.severity for f in findings)
    lines += [f"| {s} | {c.get(s, 0)} |" for s in ("error", "warning", "info")]
    lines.append("")
    for f in sorted(findings, key=lambda f: (sev_order[f.severity], f.check)):
        lines.append(f"## [{f.severity}] {f.check}")
        lines.append("")
        lines.append(f.message)
        if f.detail:
            lines.append("")
            lines.append("```yaml")
            lines.append(yaml.safe_dump(f.detail, allow_unicode=True, sort_keys=False, width=110).rstrip())
            lines.append("```")
        lines.append("")
    return "\n".join(lines)
