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
from ..canonical.mentions import mention_id
from ..canonical.project_mentions import project_mention_id
from ..models.entities import Person, Project
from ..models.enums import EntityType, EpistemicStatus, MatchStatus, MentionResolutionStatus, RelationType
from ..normalize.names import name_key, order_free_key
from ..resolution.matcher import MatchDecision
from ..sources.tk.parser import is_project_metadata
from ..resolution.projects import activity_cues, grant_keys, title_key
from .mention_stats import mention_stats, project_mention_stats

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
    # pairs of identity-anchored records only; mention ambiguity is identity.unresolved_mentions
    anchored = getattr(ds, "anchor_refs", None)
    pending = [d for d in decisions if d.status is MatchStatus.POSSIBLE and d.entity_type is EntityType.PERSON
               and (not anchored or (d.left in anchored and d.right in anchored))]
    if pending:
        F.append(Finding("identity.possible_duplicates", "warning",
                         f"{len(pending)} possible duplicate Persons await review (review/unresolved_people.yaml)",
                         detail={"pairs": [[d.left_label, d.right_label, d.method] for d in pending[:20]]}))
    labels = defaultdict(list)
    for p in ds.by_type(EntityType.PERSON):
        labels[order_free_key(p.label)].append(p.canonical_id)
    same_label = {k: v for k, v in labels.items() if len(v) > 1}
    if same_label:
        F.append(Finding("identity.same_name_distinct_ids", "info",
                         f"{len(same_label)} names are carried by more than one canonical person "
                         "(expected until reviewed; never auto-merged)", detail={"names": same_label}))
    variants = {}
    multi: dict[str, list[str]] = {}
    for p in ds.by_type(EntityType.PERSON):
        if "mtmt_id" in p.conflicts or "orcid" in p.conflicts:
            F.append(Finding("identity.conflicting_hard_ids", "error",
                             f"{p.canonical_id} carries several MTMT ids / ORCIDs", [p.canonical_id]))
        anchored_refs = sorted(r for r in p.source_refs if r in ds.anchor_refs)
        if len(anchored_refs) > 1:
            multi[p.canonical_id] = anchored_refs
        keys = {name_key(n) for n in [p.label, *getattr(p, "alternate_names", [])]}
        orders = {order_free_key(n) for n in [p.label, *getattr(p, "alternate_names", [])]}
        if len(orders) > 1:
            anchored = [r for r in p.source_refs if r in ds.anchor_refs]
            if len(anchored) > 1 or not ds.anchor_refs:
                # several independent identity records joined under different names
                F.append(Finding("identity.suspicious_merge", "warning",
                                 f"{p.canonical_id} merges different names: {sorted(keys)}", [p.canonical_id],
                                 {"identity_records": anchored}))
            else:
                # one identity record observed under several name forms (#6)
                variants[p.canonical_id] = sorted(keys)
    if variants:
        F.append(Finding("identity.name_variants", "info",
                         f"{len(variants)} people are observed under several name forms of one identity record "
                         "(not a merge of different records)", list(variants), {"names": variants}))
    if multi:
        # one Person from several identity records (hard id or manual same_as): list them for audit
        F.append(Finding("identity.multi_record_persons", "info",
                         f"{len(multi)} Persons join several identity records (hard id or manual decision)",
                         sorted(multi), {"identity_records": multi}))

    F += _mention_checks(ds, claims_by_id)
    F += _project_checks(ds, claims_by_id)

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
    # a heading, role, period, grant id or funder name emitted as a project is a parser bug (#8)
    meta = sorted((p.label, p.canonical_id) for p in ds.by_type(EntityType.PROJECT) if is_project_metadata(p.label))
    if meta:
        F.append(Finding("parser.project_title_is_metadata", "warning",
                         f"{len(meta)} projects are titled with a section label, role, period, grant id or funder name",
                         [i for _, i in meta], {"labels": [label for label, _ in meta]}))

    # coverage & stats
    counts = Counter(e.entity_type.value for e in ds.entities.values())
    rel_counts = Counter(r.type.value for r in ds.relations)
    status_counts = Counter(r.epistemic_status.value for r in ds.relations)
    F.append(Finding("stats.entities", "info", "entity counts", detail=dict(counts)))
    if ds.mentions:
        F.append(Finding("stats.person_mentions", "info", "person mentions by resolution status",
                         detail=dict(Counter(m.resolution.status.value for m in ds.mentions.values()))))
    F.append(Finding("stats.relations", "info", "relation counts", detail=dict(rel_counts)))
    F.append(Finding("stats.epistemic", "info", "relations by epistemic status", detail=dict(status_counts)))
    if seeds_path and seeds_path.exists():
        F += _seed_coverage(ds, seeds_path)
    return F


def _mention_checks(ds: CanonicalDataset, claims_by_id: dict) -> list[Finding]:
    """ADR-0006: persons are identities with evidence; mentions are evidence with a decision."""
    F: list[Finding] = []
    persons = {p.canonical_id: p for p in ds.by_type(EntityType.PERSON)}
    no_evidence = [pid for pid, p in persons.items() if not getattr(p, "identity_evidence", None)]
    if no_evidence:
        F.append(Finding("identity.person_without_evidence", "error",
                         f"{len(no_evidence)} canonical people have no identity evidence", no_evidence[:50]))
    mentions = list(ds.mentions.values())
    missing = [m.canonical_id for m in mentions if m.resolution.person_id and m.resolution.person_id not in persons]
    if missing:
        F.append(Finding("identity.mention_target_missing", "error",
                         f"{len(missing)} mentions resolve to a Person that is not in the release", missing[:50]))
    profile_owner = {u: pid for pid, p in persons.items() for u in getattr(p, "profile_urls", [])}
    stranded = [m.canonical_id for m in mentions if m.resolution.status is MentionResolutionStatus.UNRESOLVED
                and m.linked_profile_url and m.linked_profile_url in profile_owner]
    if stranded:
        F.append(Finding("identity.unresolved_linked_profile", "error",
                         f"{len(stranded)} unresolved mentions link a profile URL a Person already has "
                         "(URL normalisation bug)", stranded[:50]))
    targets: dict[str, set[str]] = defaultdict(set)
    for m in mentions:
        if m.resolution.status is MentionResolutionStatus.DETERMINISTIC:
            targets[m.source_ref].add(m.resolution.person_id or "")
    multi = {ref: sorted(t) for ref, t in targets.items() if len(t) > 1}
    if multi:
        F.append(Finding("identity.multiple_deterministic_targets", "error",
                         f"{len(multi)} source records resolve deterministically to several people",
                         list(multi)[:50], {"targets": dict(list(multi.items())[:20])}))
    unstable = [m.canonical_id for m in mentions if m.canonical_id != mention_id(m.source_ref, m.source_url)]
    if unstable:
        F.append(Finding("identity.unstable_mention_id", "error",
                         f"{len(unstable)} mention ids are not derived from (record, page)", unstable[:50]))
    unsupported = [m.canonical_id for m in mentions
                   if not any(m.provenance.values())
                   or any(i not in claims_by_id for ids in m.provenance.values() for i in ids)]
    if unsupported:
        F.append(Finding("provenance.mention_without_claim", "error",
                         f"{len(unsupported)} mentions have no valid supporting claim", unsupported[:50]))
    auto = [m for m in mentions if m.resolution.status is MentionResolutionStatus.HIGH_CONFIDENCE_AUTO]
    unexplained = [m.canonical_id for m in auto
                   if not m.resolution.method or len(m.resolution.signals) < 2 or not m.resolution.resolver_version]
    if unexplained:
        F.append(Finding("identity.auto_resolution_unexplained", "error",
                         f"{len(unexplained)} automatic resolutions lack a rule, two signals or a resolver version",
                         unexplained[:50]))
    blocked = [m.canonical_id for m in auto if set(m.resolution.negative_signals) & {
        "LINKS_OTHER_PROFILE", "LINK_NAME_MISMATCH", "MULTIPLE_CANDIDATES", "SAME_NAME_MULTIPLE_PERSONS",
        "CONFLICTING_HARD_ID", "MANUAL_NOT_SAME_AS"}]
    if blocked:
        F.append(Finding("identity.auto_resolution_despite_contradiction", "error",
                         f"{len(blocked)} automatic resolutions carry a blocking negative signal", blocked[:50]))
    if mentions:
        st = mention_stats(ds)
        F.append(Finding("identity.mention_resolution", "info",
                         f"{st['resolved']} of {st['total']} person mentions resolved ({st['resolution_rate']:.1%}); "
                         f"{st['review_required']} need review, {st['no_candidate']} have no candidate Person",
                         detail={k: st[k] for k in ("by_status", "resolved_by_method", "by_source", "by_page_type",
                                                    "not_resolved_reasons")}))
        if st["source_rate_spread"] is not None and st["source_rate_spread"] > 0.2:
            F.append(Finding("identity.resolution_uneven_by_source", "warning",
                             f"mention resolution rates differ by {st['source_rate_spread']:.0%} between source "
                             "sites; network density may reflect markup quality, not collaboration",
                             detail={k: v["resolution_rate"] for k, v in st["by_source"].items()}))
        if st["not_resolved_sharing_a_person_name"]:
            F.append(Finding("identity.unresolved_mentions", "warning",
                             f"{st['not_resolved']} of {st['total']} person mentions are not resolved; "
                             f"{st['not_resolved_sharing_a_person_name']} share a canonical Person's name "
                             "(review/mention_review.yaml)",
                             detail={"top_persons": st["persons_with_most_unresolved_same_name_mentions"]}))
    return F


PROJECT_BLOCKING = {"GRANT_ID_CONFLICT", "PERIOD_CONFLICT", "LINKS_OTHER_PAGE", "MULTIPLE_CANDIDATES",
                    "MANUAL_NOT_SAME_AS"}
PROJECT_INDEPENDENT = {"GRANT_ID_MATCH", "PAGE_LINKS_OWNER", "PAGE_NAMES_OWNER"}


def _project_checks(ds: CanonicalDataset, claims_by_id: dict) -> list[Finding]:
    """ADR-0008: Projects are identities with an anchor; project mentions are evidence with a decision."""
    F: list[Finding] = []
    projects = {p.canonical_id: p for p in ds.by_type(EntityType.PROJECT)}
    no_evidence = [pid for pid, p in projects.items() if not getattr(p, "identity_evidence", None)]
    if no_evidence:
        F.append(Finding("project.without_evidence", "error",
                         f"{len(no_evidence)} canonical Projects have no identity evidence", no_evidence[:50]))
    pms = list(ds.project_mentions.values())
    missing = [m.canonical_id for m in pms if m.resolution.project_id and m.resolution.project_id not in projects]
    if missing:
        F.append(Finding("project.mention_target_missing", "error",
                         f"{len(missing)} project mentions resolve to a Project that is not in the release", missing[:50]))
    unstable = [m.canonical_id for m in pms if m.canonical_id != project_mention_id(m.source_ref, m.source_url)]
    if unstable:
        F.append(Finding("project.unstable_mention_id", "error",
                         f"{len(unstable)} project mention ids are not derived from (record, page)", unstable[:50]))
    unsupported = [m.canonical_id for m in pms if not any(m.provenance.values())
                   or any(i not in claims_by_id for ids in m.provenance.values() for i in ids)]
    if unsupported:
        F.append(Finding("project.mention_without_claim", "error",
                         f"{len(unsupported)} project mentions have no valid supporting claim", unsupported[:50]))
    auto = [m for m in pms if m.resolution.status is MentionResolutionStatus.HIGH_CONFIDENCE_AUTO]
    unexplained = [m.canonical_id for m in auto
                   if not m.resolution.method or len(m.resolution.signals) < 2 or not m.resolution.resolver_version]
    if unexplained:
        F.append(Finding("project.auto_unexplained", "error",
                         f"{len(unexplained)} automatic project resolutions lack a rule, two signals or a resolver "
                         "version", unexplained[:50]))
    title_only = [m.canonical_id for m in auto if not set(m.resolution.signals) & PROJECT_INDEPENDENT]
    if title_only:
        F.append(Finding("project.title_only_auto", "error",
                         f"{len(title_only)} automatic project resolutions rest on title evidence alone",
                         title_only[:50]))
    blocked = [m.canonical_id for m in auto if set(m.resolution.negative_signals) & PROJECT_BLOCKING]
    if blocked:
        F.append(Finding("project.auto_despite_contradiction", "error",
                         f"{len(blocked)} automatic project resolutions carry a blocking negative signal", blocked[:50]))

    grants = {pid: sorted({k for v in [p.grant_id] + [cv.value for cv in p.conflicts.get("grant_id", [])] if v
                           for k in grant_keys(str(v))}) for pid, p in projects.items()}
    conflicting = {pid: g for pid, g in grants.items() if len(g) > 1}
    if conflicting:
        F.append(Finding("project.conflicting_grant_ids", "warning",
                         f"{len(conflicting)} Projects state more than one grant number", sorted(conflicting),
                         {"grants": conflicting}))
    multi_url = {pid: [p.website] + [cv.value for cv in p.conflicts.get("website", []) if cv.value != p.website]
                 for pid, p in projects.items() if p.conflicts.get("website")}
    if multi_url:
        F.append(Finding("project.multiple_urls", "warning",
                         f"{len(multi_url)} Projects carry more than one page URL (one project on several pages, "
                         "or a false join)", sorted(multi_url), {"urls": multi_url}))
    by_key: dict[str, list[str]] = defaultdict(list)
    for pid, p in sorted(projects.items()):
        by_key[title_key(p.title)].append(pid)
    same = {k: v for k, v in by_key.items() if k and len(v) > 1}
    if same:
        F.append(Finding("project.same_title_distinct", "info",
                         f"{len(same)} titles are shared by distinct Projects (editions or phases are kept apart "
                         "until a page states the relation)", [i for v in same.values() for i in v],
                         {"groups": {k: [(i, projects[i].title, projects[i].start, projects[i].end) for i in v]
                                     for k, v in same.items()}}))
    groups: dict[str, set[str]] = defaultdict(set)
    for m in pms:
        if not m.resolution.status.resolved and m.title_key:
            groups[m.title_key].add(m.source_url)
    dup = {k: sorted(v) for k, v in groups.items() if len(v) > 1}
    if dup:
        F.append(Finding("project.duplicate_title_groups", "info",
                         f"{len(dup)} unresolved project titles appear on several pages; never merged automatically "
                         "(review/project_review.yaml)", detail={"groups": dict(sorted(dup.items())[:30])}))
    cues = [m for m in pms if m.activity_cues]
    cued_projects = {pid: activity_cues(p.title) for pid, p in projects.items() if activity_cues(p.title)}
    if cues or cued_projects:
        F.append(Finding("project.activity_cues", "info",
                         f"{len(cued_projects)} Projects and {len(cues)} project mentions carry words suggesting a "
                         "journal, network, programme, infrastructure, consortium or newsletter (left for #9)",
                         sorted(cued_projects),
                         {"mentions": dict(Counter(c for m in cues for c in m.activity_cues)),
                          "projects": {pid: [projects[pid].title, c] for pid, c in sorted(cued_projects.items())}}))
    unattached = [c for c in ds.claims if c.predicate == "unattached_project_metadata"]
    if unattached:
        F.append(Finding("project.unattached_metadata", "info",
                         f"{len(unattached)} project-section metadata lines are kept unattached (no structural "
                         "evidence ties them to one project)",
                         detail=dict(Counter(str(c.qualifiers.get("kind")) for c in unattached))))
    if pms:
        st = project_mention_stats(ds)
        F.append(Finding("project.mention_resolution", "info",
                         f"{st['resolved']} of {st['total']} project mentions resolved ({st['resolution_rate']:.1%}); "
                         f"{st['review_required']} need review, {st['no_candidate']} have no candidate Project",
                         detail={k: st[k] for k in ("by_status", "resolved_by_method", "by_source", "by_observation",
                                                    "not_resolved_reasons")}))
        rates = {k: v["resolution_rate"] for k, v in st["by_source"].items() if v["total"] >= 20}
        if len(rates) > 1 and max(rates.values()) - min(rates.values()) > 0.2:
            F.append(Finding("project.resolution_uneven_by_source", "warning",
                             f"project mention resolution rates differ by "
                             f"{max(rates.values()) - min(rates.values()):.0%} between source sites; project "
                             "networks will be denser where project pages were crawled", detail=rates))
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
            mentioned = sorted({m.source_url for m in ds.mentions.values()
                                if order_free_key(m.stated_name) == order_free_key(s["name"])})
            out.append(Finding("seeds.missing", "warning", f"QA seed not in dataset as a person: {s['name']}",
                               detail={"expect": s.get("expect"), "mentioned_on": mentioned}))
            continue
        for p in hits:
            aff = sorted({units.get(r.target_id, r.target_id) for r in ds.relations
                          if r.source_id == p.canonical_id and r.type in AFFILIATION_TYPES})
            topics = sorted({units.get(r.target_id) for r in ds.relations if r.source_id == p.canonical_id
                             and r.type is RelationType.WORKS_ON_TOPIC})
            methods = sorted({units.get(r.target_id) for r in ds.relations if r.source_id == p.canonical_id
                              and r.type is RelationType.USES_METHOD})
            resolved = Counter(m.resolution.method for m in ds.mentions.values()
                               if m.resolution.person_id == p.canonical_id)
            out.append(Finding("seeds.present", "info", f"{s['name']} -> {p.canonical_id}",
                               [p.canonical_id], {"affiliations": aff, "topics": topics, "methods": methods,
                                                  "resolved_mentions": sum(resolved.values()),
                                                  "resolved_by_method": dict(sorted(resolved.items()))}))
        unresolved = [m for m in ds.mentions.values() if m.resolution.person_id is None
                      and order_free_key(m.stated_name) == order_free_key(s["name"])]
        if unresolved:
            out.append(Finding("seeds.unresolved_mentions", "info",
                               f"{s['name']}: {len(unresolved)} same-name mentions not resolved to the profile",
                               detail={"pages": sorted({m.source_url for m in unresolved}),
                                       "reasons": dict(Counter(m.resolution.reason for m in unresolved))}))
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
