"""COVERAGE: how much of the in-scope sources the release actually covers (#12, ADR-0009).

``quality_report`` answers "is what we built consistent?"; this module answers "how much of what the
sources state did we get?". A release with 0 QA errors can still be far from complete.

Rules of the measurement:

* every number is ``{"n": .., "of": .., "rate": ..}`` with the denominator named in the key above it
  and spelled out in ``coverage.md``; a rate without its denominator is not reported;
* the layers stay separate: discovery (was a page we know about found), fetch (did it come back),
  parse (did the parser find anything in it), canonicalisation (did the mentions resolve), fields
  (how many canonical entities carry each field);
* missing optional fields are coverage, never errors;
* the QA seeds are sentinels, not a sample, and are reported apart (``sentinels``);
* nothing here changes the data. ``network_bias`` exposes structural consequences of the gaps; it
  does not correct for them.
"""

from __future__ import annotations

import hashlib
import itertools
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import yaml

from ..canonical.build import CanonicalDataset
from ..discovery import GRANT_REGISTRY, IN_SCOPE, host_scope
from ..models.enums import EntityType, IdentityAnchor, RelationType
from ..normalize.urls import canonical_url
from ..registry import Registry
from ..resolution.projects import registry_grant_keys

SOURCE_TYPE_PAGE = {"institutional_profile": "profile", "unit_page": "unit", "project_page": "project",
                    "institutional_listing": "listing"}
PAGE_TYPES = ("profile", "unit", "project", "project_listing", "listing")
PROJECT_EDGES = {RelationType.PARTICIPATES_IN, RelationType.PRINCIPAL_INVESTIGATOR_OF}


def share(n: int, of: int) -> dict[str, Any]:
    return {"n": n, "of": of, "rate": round(n / of, 3) if of else None}


def _is_web(doc) -> bool:
    return not doc.url.startswith("repo://")


# What no figure in the report can see. Stated in every release so a rate is never read as more than it is.
BLIND_SPOTS = [
    "A page that no listing shows and no profile links is in no denominator: discovery covers only what the "
    "enabled sources point at (staff listings, configured units and category listings, links in profile "
    "project sections).",
    "The universe of people is each site's current staff listing. Former staff, outside collaborators and "
    "people on other units' sites appear only as mentions, so a person-mention rate depends on how many such "
    "people a site's pages name.",
    "Other TK units' sites, external project sites and grant records are counted where profiles link them and "
    "are not crawled; what they hold is not in any field or resolution figure.",
    "A field a site's template never shows has 0% coverage without being a defect; field rates compare sites "
    "only as far as their templates offer the same fields.",
    "'Fetched' means the page answered below HTTP 400 on the retrieval date; it says nothing about whether the "
    "page is current or complete.",
    "The QA seeds are sentinels: a missing seed shows a lost person, a present seed says nothing about the "
    "people not listed.",
]


def coverage_report(ds: CanonicalDataset, *, registry: Registry, frontier: list[dict[str, Any]],
                    diagnostics: list[dict[str, Any]], errors: list[dict[str, Any]],
                    seeds_path: Path | None = None) -> dict[str, Any]:
    sources = {s.source_id: s for s in registry.sources if s.enabled and s.adapter}
    labels = {sid: s.adapter_config.get("institute_code", sid) for sid, s in sources.items()}
    aliases = registry.host_aliases()
    docs = [d for d in ds.documents.values() if _is_web(d)]
    diag_by_doc = {r["document_id"]: r for r in diagnostics}
    cov: dict[str, Any] = {
        "scope": {"sources": {sid: {"institute": labels[sid], "base_url": s.base_url} for sid, s in sources.items()},
                  "note": "in scope = sources enabled in config/sources.yaml; every denominator below says what it counts"},
        "source_set": source_set(docs, diag_by_doc),
    }
    cov["fetch"] = _fetch(docs, diag_by_doc, errors, sources, aliases)
    cov["discovery"] = _discovery(ds, docs, frontier, registry, sources)
    cov["parse"] = _parse(docs, diagnostics, sources)
    cov["canonicalization"] = _canonicalization(ds, sources, frontier)
    cov["fields"] = _fields(ds, sources, registry)
    cov["network_bias"] = _network_bias(ds, sources, registry, frontier)
    cov["sentinels"] = _sentinels(ds, seeds_path)
    cov["blind_spots"] = BLIND_SPOTS
    cov["labels"] = labels
    return cov


# ------------------------------------------------------------------ document universe
def source_set(docs, diag_by_doc: dict[str, dict]) -> dict[str, Any]:
    """The document universe a release was built from. Two releases with different digests were built from
    different crawls, whatever the code did."""
    by_source: dict[str, Counter] = defaultdict(Counter)
    for d in docs:
        by_source[d.source_id][_page_type(d, diag_by_doc)] += 1
    times = [d.retrieved_at for d in docs]
    return {
        "documents": len(docs),
        "digest": hashlib.sha256("\n".join(sorted(d.document_id for d in docs)).encode()).hexdigest()[:16],
        "by_source": {s: {"documents": sum(c.values()), "by_page_type": dict(sorted(c.items()))}
                      for s, c in sorted(by_source.items())},
        "by_page_type": dict(sorted(Counter(_page_type(d, diag_by_doc) for d in docs).items())),
        "retrieved": {"from": min(times).isoformat() if times else None,
                      "until": max(times).isoformat() if times else None},
    }


def _page_type(doc, diag_by_doc: dict[str, dict]) -> str:
    row = diag_by_doc.get(doc.document_id)
    return row["page_type"] if row else SOURCE_TYPE_PAGE.get(doc.source_type.value, doc.source_type.value)


# ------------------------------------------------------------------ fetch
def _fetch(docs, diag_by_doc, errors, sources, aliases) -> dict[str, Any]:
    """Of the distinct URLs the crawl requested: how many came back, failed, were redirected.

    Denominator: distinct canonical URLs with a retrieved document (latest retrieval), per source and page
    type. URLs that were requested but never retrieved are counted under ``not_retrieved``."""
    latest: dict[tuple[str, str], Any] = {}
    for d in docs:
        k = (d.source_id, d.canonical_url)
        if k not in latest or d.retrieved_at > latest[k].retrieved_at:
            latest[k] = d
    table: dict[str, dict[str, Counter]] = defaultdict(lambda: defaultdict(Counter))
    for (sid, _), d in latest.items():
        t = table[sid][_page_type(d, diag_by_doc)]
        t["urls"] += 1
        t["ok" if d.http_status < 400 else "http_error"] += 1
        if d.http_status < 400 and canonical_url(d.url, aliases=aliases) != d.canonical_url:
            t["redirected"] += 1
        if d.http_status >= 400:
            t[f"http_{d.http_status}"] += 1
    not_retrieved: dict[str, list[str]] = defaultdict(list)
    for e in errors:
        if e.get("error") == "not fetched" or str(e.get("error", "")).startswith(("transport", "robots", "page budget")):
            not_retrieved["all"].append(e["url"])
    return {
        "denominator": "distinct canonical URLs with a retrieved document, per source and page type",
        "by_source": {s: {t: dict(c) for t, c in sorted(types.items())} for s, types in sorted(table.items())},
        "totals": share(sum(1 for d in latest.values() if d.http_status < 400), len(latest)),
        "http_errors": dict(sorted(Counter(d.http_status for d in latest.values() if d.http_status >= 400).items())),
        "not_retrieved": {"urls": len(set(not_retrieved["all"])), "sample": sorted(set(not_retrieved["all"]))[:20]},
    }


# ------------------------------------------------------------------ discovery
def _link_status(url: str, ok_project_docs: set[str], frontier_by_url: dict[str, dict]) -> tuple[str, str | None]:
    row = frontier_by_url.get(url)
    if url in ok_project_docs:
        return "fetched", None
    final = ((row or {}).get("fetch") or {}).get("final_url")
    if final and canonical_url(final) in ok_project_docs:
        return "fetched", "redirected"  # the page came back from another URL: a mention cannot resolve by URL
    if row is None:
        return "not_attempted", "no_discovery_record"
    if row["decision"] == "skipped":
        return "not_followed", row["reason"]
    fetch = row.get("fetch") or {}
    if fetch.get("attempted") and fetch.get("error"):
        return "fetch_failed", fetch["error"]
    return "not_fetched", None


def _discovery(ds, docs, frontier, registry: Registry, sources) -> dict[str, Any]:
    """Explicit references in in-scope pages and what became of each.

    * project links: distinct canonical URLs written in the project section of a researcher profile;
    * project listing articles: distinct project URLs shown on a configured category listing;
    * profile links: distinct profile URLs of in-scope hosts written on listings, unit pages and project pages.
    """
    frontier_by_url = {r["url"]: r for r in frontier}
    ok_project_docs = {d.canonical_url for d in docs if d.source_type.value == "project_page" and d.http_status < 400}
    ok_profile_docs = {d.canonical_url for d in docs if d.source_type.value == "institutional_profile"
                       and d.http_status < 400}
    institution = next(iter(sources.values())).institution if sources else None

    by_url: dict[str, list] = defaultdict(list)
    for m in ds.project_mentions.values():
        if m.observation == "profile_list" and m.linked_url:
            by_url[m.linked_url].append(m)
    rows = []
    for url, ms in sorted(by_url.items()):
        host = (urlsplit(url).hostname or "").lower()
        if registry_grant_keys(url):
            scope, owner = GRANT_REGISTRY, None
        else:
            scope, owner, _ = host_scope(registry, host, institution)
        status, reason = _link_status(url, ok_project_docs, frontier_by_url) if scope == IN_SCOPE else \
            ("not_in_scope", None)
        row = frontier_by_url.get(url) or {}
        fetch = row.get("fetch") or {}
        rows.append({
            "url": url, "host": host, "scope": scope, "owner_source": owner, "status": status, "reason": reason,
            "http_status": fetch.get("http_status"), "redirected": fetch.get("redirected"),
            "mentions": len(ms), "researchers": len({m.observed_on_profile_of for m in ms if m.observed_on_profile_of}),
            "from_sources": sorted({m.source_id for m in ms}),
            "resolved_mentions": sum(1 for m in ms if m.resolution.status.resolved),
            "host_status": row.get("host_status"), "frontier_reason": row.get("reason"),
        })
    scope_counts = Counter(r["scope"] for r in rows)
    in_scope = [r for r in rows if r["scope"] == IN_SCOPE]
    shaped = [r for r in in_scope if r["status"] != "not_followed" or r["reason"] not in ("not_project_path", "unit_page")]

    def per_source(pred) -> dict[str, dict[str, Any]]:
        out = {}
        for sid in sorted(sources):
            rs = [r for r in in_scope if pred(r) and r["owner_source"] == sid]
            c = Counter(r["status"] for r in rs)
            out[sid] = {"urls": len(rs), "fetched": c["fetched"],
                        "not_fetched": len(rs) - c["fetched"], **{k: v for k, v in sorted(c.items()) if k != "fetched"},
                        "fetched_share": share(c["fetched"], len(rs))}
        return out

    listing_urls = {m.linked_url for m in ds.project_mentions.values()
                    if m.observation == "project_listing" and m.linked_url}
    profile_links = _profile_links(ds, docs, ok_profile_docs, registry, institution)
    return {
        "project_links": {
            "denominator": "distinct canonical URLs written in the project section of an in-scope researcher profile",
            "distinct_urls": len(rows),
            "by_scope": dict(sorted(scope_counts.items())),
            "mentions_by_scope": dict(sorted(Counter(
                {s: sum(r["mentions"] for r in rows if r["scope"] == s) for s in scope_counts}).items())),
            "in_scope": {
                "denominator": "distinct URLs of in-scope hosts linked from profile project sections",
                "urls": len(in_scope),
                "fetched": share(sum(1 for r in in_scope if r["status"] == "fetched"), len(in_scope)),
                "of_project_path_shape": {
                    "denominator": "the same, minus links whose path is not a project page path (news, units, sub-pages)",
                    "fetched": share(sum(1 for r in shaped if r["status"] == "fetched"), len(shaped)),
                },
                "by_status": dict(sorted(Counter(
                    r["status"] if r["status"] != "not_followed" else f"not_followed:{r['reason']}"
                    for r in in_scope).items())),
                "by_source": per_source(lambda r: True),
            },
            "urls_detail": rows,
        },
        "project_listing_links": {
            "denominator": "distinct project URLs shown on a configured category listing",
            "distinct_urls": len(listing_urls),
            "fetched": share(len(listing_urls & ok_project_docs), len(listing_urls)),
        },
        "profile_links": profile_links,
    }


def _profile_links(ds, docs, ok_profile_docs: set[str], registry: Registry, institution) -> dict[str, Any]:
    """Profile URLs of in-scope hosts that pages link: were they fetched?"""
    urls: dict[str, set[str]] = defaultdict(set)
    for m in ds.mentions.values():
        if m.linked_profile_url:
            host = (urlsplit(m.linked_profile_url).hostname or "").lower()
            if host_scope(registry, host, institution)[0] == IN_SCOPE:
                urls[m.linked_profile_url].add(m.source_id)
    fetched = {u for u in urls if u in ok_profile_docs}
    slug = lambda u: urlsplit(u).path.rstrip("/").rsplit("/", 1)[-1]  # noqa: E731
    fetched_slugs = {slug(u) for u in ok_profile_docs}
    missing = sorted(set(urls) - fetched)
    return {
        "denominator": "distinct profile URLs of in-scope hosts linked from a listing, unit page or project page",
        "distinct_urls": len(urls),
        "fetched": share(len(fetched), len(urls)),
        "not_fetched": len(missing),
        # profiles are fetched from staff listings; these are linked from a project or unit page and not listed
        "not_fetched_with_same_slug_on_another_site": sum(1 for u in missing if slug(u) in fetched_slugs),
        "not_fetched_sample": missing[:15],
    }


# ------------------------------------------------------------------ parse
def _parse(docs, diagnostics, sources) -> dict[str, Any]:
    """Of the pages retrieved successfully: what the parsers made of them.

    Denominator: retrieved documents with HTTP status below 400, per source and page type. ``empty`` means the
    page parsed but offered nothing besides its title or name; ``unmapped_labels`` counts "Label: value"
    lines no field took (possible unsupported markup)."""
    ok_docs = {d.document_id for d in docs if d.http_status < 400}
    by: dict[str, dict[str, Counter]] = defaultdict(lambda: defaultdict(Counter))
    labels: Counter = Counter()
    for r in diagnostics:
        if r["document_id"] not in ok_docs:
            continue
        c = by[r["source_id"]][r["page_type"]]
        c["parsed"] += 1
        c[r["status"]] += 1
        if r["unmapped_labels"]:
            c["with_unmapped_labels"] += 1
            labels.update((r["page_type"], x) for x in r["unmapped_labels"])
    parsed = sum(c["parsed"] for t in by.values() for c in t.values())
    return {
        "denominator": "retrieved documents (HTTP < 400) per source and page type",
        "retrieved_ok": len(ok_docs),
        "with_parse_record": parsed,
        "without_parse_record": len(ok_docs) - parsed,
        "by_source": {s: {t: dict(c) for t, c in sorted(types.items())} for s, types in sorted(by.items())},
        "status": dict(sorted(Counter(r["status"] for r in diagnostics if r["document_id"] in ok_docs).items())),
        "unmapped_labels": [{"page_type": t, "label": lab, "pages": n}
                            for (t, lab), n in labels.most_common(25)],
    }


# ------------------------------------------------------------------ canonicalisation
def _canonicalization(ds, sources, frontier) -> dict[str, Any]:
    def table(mentions) -> dict[str, Any]:
        by: dict[str, Counter] = defaultdict(Counter)
        for m in mentions:
            for k in (m.source_id, "all"):
                by[k]["total"] += 1
                by[k][m.resolution.status.value] += 1
                by[k]["resolved"] += int(m.resolution.status.resolved)
        return {k: dict(sorted(v.items())) | {"resolved_share": share(v["resolved"], v["total"])}
                for k, v in sorted(by.items(), key=lambda kv: (kv[0] == "all", kv[0]))}

    pm = list(ds.project_mentions.values())
    frontier_by_url = {r["url"]: r for r in frontier}
    reasons: dict[str, Counter] = defaultdict(Counter)
    for m in pm:
        if not m.resolution.status.resolved:
            cat = unresolved_category(m, frontier_by_url)
            reasons[m.source_id][cat] += 1
            reasons["all"][cat] += 1
    return {
        "person_mentions": {"denominator": "person mentions observed in in-scope pages, by observing source",
                            "by_source": table(ds.mentions.values())},
        "project_mentions": {"denominator": "project mentions observed in in-scope pages, by observing source",
                             "by_source": table(pm),
                             "unresolved_by_category": {k: dict(v.most_common()) for k, v in sorted(reasons.items())}},
    }


# Why a project mention has no Project. Derived from the mention and the crawl frontier, never from a URL's
# text: what the profile stated, what the crawl decided, what the fetch returned.
UNRESOLVED_CATEGORIES = {
    "identity_review": "a candidate exists; the evidence is not enough to decide (review queue)",
    "deferred_to_ontology": "identity plausible, entity type undecided (#9)",
    "title_only_no_page_link": "the profile gives a title and no page: no page is asserted",
    "linked_page_external_site": "the linked page is on a site outside the in-scope sources",
    "linked_page_grant_registry": "the link is a grant record, not a project page",
    "linked_page_other_unit_site": "the linked page is on another TK unit's site that is not an enabled source",
    "linked_page_not_project_path": "the link is on an in-scope host but is not the path shape of a project page",
    "linked_page_fetch_failed": "the page was requested and did not come back",
    "linked_page_fetched_no_project": "the page was fetched and no Project was anchored on it",
    "linked_page_no_discovery_record": "the link was never put on the frontier",
}


def unresolved_category(m, frontier_by_url: dict[str, dict]) -> str:
    if m.resolution.method == "manual:project_deferred":  # a deferred mention is held in review too: say which
        return "deferred_to_ontology"
    if m.resolution.status.value == "REVIEW_REQUIRED":
        return "identity_review"
    if not m.linked_url:
        return "title_only_no_page_link"
    if registry_grant_keys(m.linked_url):
        return "linked_page_grant_registry"
    row = frontier_by_url.get(m.linked_url)
    if row is None:
        # listing rows are followed by the listing crawl, which only takes one-segment project paths
        return "linked_page_not_project_path" if m.observation == "project_listing" else "linked_page_no_discovery_record"
    if row["decision"] == "skipped":
        return {"external": "linked_page_external_site", "other_unit_site": "linked_page_other_unit_site",
                GRANT_REGISTRY: "linked_page_grant_registry"}.get(row["scope"], "linked_page_not_project_path")
    fetch = row.get("fetch") or {}
    if fetch.get("attempted") and fetch.get("error"):
        return "linked_page_fetch_failed"
    return "linked_page_fetched_no_project"


# ------------------------------------------------------------------ fields
def _fields(ds, sources, registry: Registry) -> dict[str, Any]:
    """How many canonical entities carry each optional field.

    Denominators: profile-backed canonical Persons; canonical Projects. A person with profiles on two sites
    counts on both; a Project counts on the source of its page."""
    rel: dict[RelationType, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
    for r in ds.relations:
        rel[r.type]["out"].add(r.source_id)
        rel[r.type]["in"].add(r.target_id)
    host_source = {(urlsplit(s.base_url).hostname or "").lower(): sid for sid, s in sources.items()}
    persons = [p for p in ds.by_type(EntityType.PERSON) if IdentityAnchor.INSTITUTIONAL_PROFILE in p.identity_evidence]
    has_edge = rel[RelationType.PARTICIPATES_IN]["out"] | rel[RelationType.PRINCIPAL_INVESTIGATOR_OF]["out"]

    def person_flags(p) -> dict[str, bool]:
        return {
            "affiliation": p.canonical_id in rel[RelationType.AFFILIATED_WITH]["out"],
            "named_unit": p.canonical_id in rel[RelationType.MEMBER_OF]["out"],
            "position": bool(p.position_titles),
            "mtmt_id": bool(p.mtmt_id),
            "orcid": bool(p.orcid),
            "stated_research_areas": bool(p.stated_research_areas),
            "topics": p.canonical_id in rel[RelationType.WORKS_ON_TOPIC]["out"],
            "methods": p.canonical_id in rel[RelationType.USES_METHOD]["out"],
            "project_edges": p.canonical_id in has_edge,
        }

    def project_flags(p) -> dict[str, bool]:
        return {
            "page_url": bool(p.website),
            "period": bool(p.start),
            "funding_body": bool(p.funding_body),
            "grant_id": bool(p.grant_id),
            "principal_investigator": p.canonical_id in rel[RelationType.PRINCIPAL_INVESTIGATOR_OF]["in"],
            "participants": p.canonical_id in rel[RelationType.PARTICIPATES_IN]["in"],
            "description": bool(p.abstract),
        }

    def person_sources(p) -> set[str]:
        out = {host_source[h] for u in p.profile_urls if (h := (urlsplit(u).hostname or "").lower()) in host_source}
        return out or {"other"}

    def project_source(p) -> str:
        return host_source.get((urlsplit(p.website or "").hostname or "").lower(), "other")

    def tabulate(items, flags, source_of) -> dict[str, Any]:
        by: dict[str, Counter] = defaultdict(Counter)
        for it in items:
            for sid in source_of(it):
                for key in (sid, "all"):
                    by[key]["total"] += 1
                    for k, v in flags(it).items():
                        by[key][k] += int(v)
        out = {}
        for sid, c in sorted(by.items(), key=lambda kv: (kv[0] == "all", kv[0])):
            out[sid] = {"total": c["total"]} | {k: share(n, c["total"]) for k, n in c.items() if k != "total"}
        return out

    return {
        "persons": {"denominator": "profile-backed canonical Persons (a person with two profiles counts on both sites)",
                    "by_source": tabulate(persons, person_flags, person_sources)},
        "projects": {"denominator": "canonical Projects, by the source of their page",
                     "by_source": tabulate(ds.by_type(EntityType.PROJECT), project_flags,
                                           lambda p: {project_source(p)})},
    }


# ------------------------------------------------------------------ network bias
def _network_bias(ds, sources, registry: Registry, frontier: list[dict[str, Any]]) -> dict[str, Any]:
    """Structural consequences of the gaps, exposed and not corrected.

    * persons with no project edge, and why their own-profile project mentions did not resolve;
    * pairs of researchers whose profiles link the same page that has no anchored Project: an upper bound on
      collaboration ties missing because of coverage, not evidence that the ties exist;
    * the realised ties, for scale."""
    persons = {p.canonical_id: p for p in ds.by_type(EntityType.PERSON)
               if IdentityAnchor.INSTITUTIONAL_PROFILE in p.identity_evidence}
    members: dict[str, set[str]] = defaultdict(set)
    edge_persons: set[str] = set()
    for r in ds.relations:
        if r.type in PROJECT_EDGES and r.source_id in persons:
            members[r.target_id].add(r.source_id)
            edge_persons.add(r.source_id)
    host_source = {(urlsplit(s.base_url).hostname or "").lower(): sid for sid, s in sources.items()}

    def site_of(pid: str) -> str:
        for u in persons[pid].profile_urls:
            if (h := (urlsplit(u).hostname or "").lower()) in host_source:
                return host_source[h]
        return "other"

    frontier_by_url = {r["url"]: r for r in frontier}
    own_open: dict[str, list] = defaultdict(list)
    for m in ds.project_mentions.values():
        if m.observed_on_profile_of in persons and not m.resolution.status.resolved:
            own_open[m.observed_on_profile_of].append(m)
    by_source: dict[str, dict[str, Any]] = {}
    for sid in sorted(sources):
        ps = [p for p in persons if site_of(p) == sid]
        none = [p for p in ps if p not in edge_persons]
        reasons: Counter = Counter()
        for p in none:
            for rc in {unresolved_category(m, frontier_by_url) for m in own_open.get(p, [])}:
                reasons[rc] += 1
        by_source[sid] = {
            "persons": len(ps),
            "without_project_edges": share(len(none), len(ps)),
            "of_those_with_no_project_mention_at_all": sum(1 for p in none if not own_open.get(p)),
            "of_those_with_unresolved_project_mentions": sum(1 for p in none if own_open.get(p)),
            "by_unresolved_category (persons; one person can have several)": dict(reasons.most_common()),
        }
    # pairs sharing an unresolved linked page
    pair_scope: dict[str, set[tuple[str, str]]] = defaultdict(set)
    urls: dict[str, set[str]] = defaultdict(set)
    for m in ds.project_mentions.values():
        if (m.observation == "profile_list" and m.linked_url and m.observed_on_profile_of in persons
                and not m.resolution.status.resolved and not registry_grant_keys(m.linked_url)):
            urls[m.linked_url].add(m.observed_on_profile_of)
    institution = next(iter(sources.values())).institution if sources else None
    for url, ps in urls.items():
        scope = host_scope(registry, (urlsplit(url).hostname or "").lower(), institution)[0]
        for a, b in itertools.combinations(sorted(ps), 2):
            pair_scope[scope].add((a, b))
    realised = {tuple(sorted(pair)) for ms in members.values() for pair in itertools.combinations(sorted(ms), 2)}
    by_project_sites = {pid: {site_of(p) for p in ms} for pid, ms in members.items()}
    return {
        "persons_without_project_edges": by_source,
        "unrealised_ties_upper_bound": {
            "definition": "pairs of researchers whose profiles link the same URL that has no anchored Project; "
                          "an upper bound on ties missing because of coverage, not evidence that they exist",
            "by_scope_of_linked_host": {k: len(v) for k, v in sorted(pair_scope.items())},
            "not_already_realised": {k: len(v - realised) for k, v in sorted(pair_scope.items())},
        },
        "realised": {
            "persons_with_project_edges": share(len(edge_persons), len(persons)),
            "co_participation_ties": len(realised),
            "projects_with_participants": len(members),
            "multi_source_projects": sum(1 for s in by_project_sites.values() if len(s) > 1),
        },
    }


# ------------------------------------------------------------------ sentinels
def _sentinels(ds, seeds_path: Path | None) -> dict[str, Any]:
    """QA seeds: people we expect to find. A sentinel diagnostic, not a sample, so it estimates nothing."""
    if not seeds_path or not seeds_path.exists():
        return {}
    names = [s["name"] for s in yaml.safe_load(seeds_path.read_text(encoding="utf-8"))["seeds"]]
    persons = {p.label for p in ds.by_type(EntityType.PERSON)}
    return {"note": "sentinels, not a coverage estimate: passing says nothing about the people not listed",
            "present": sorted(n for n in names if n in persons), "missing": sorted(n for n in names if n not in persons)}


# ------------------------------------------------------------------ findings and rendering
def coverage_findings(cov: dict[str, Any]):
    """Coverage as QA findings. Gaps are warnings or info; coverage never fails a build."""
    from .qa import Finding

    out = []
    pl = cov["discovery"]["project_links"]
    ins = pl["in_scope"]
    nf = [r for r in pl["urls_detail"] if r["scope"] == IN_SCOPE and r["status"] != "fetched"
          and not (r["status"] == "not_followed" and r["reason"] in ("not_project_path", "unit_page"))]
    out.append(Finding(
        "coverage.linked_project_pages", "warning" if nf else "info",
        f"{ins['fetched']['n']} of {ins['fetched']['of']} distinct in-scope project URLs linked from profile "
        f"project sections were fetched ({len(nf)} of project-page shape were not)",
        [r["url"] for r in nf][:20], {"by_status": ins["by_status"], "by_source": ins["by_source"]}))
    fe = cov["fetch"]["http_errors"]
    if fe or cov["fetch"]["not_retrieved"]["urls"]:
        out.append(Finding("coverage.fetch_failures", "warning",
                           f"{sum(fe.values())} retrieved URLs answered with an HTTP error and "
                           f"{cov['fetch']['not_retrieved']['urls']} were requested but not retrieved",
                           detail={"http_errors": fe, "not_retrieved": cov["fetch"]["not_retrieved"]}))
    parse = cov["parse"]
    errs = parse["status"].get("error", 0)
    if errs or parse["without_parse_record"]:
        out.append(Finding("coverage.parse_failures", "warning",
                           f"{errs} pages failed to parse and {parse['without_parse_record']} retrieved pages have "
                           f"no parse record", detail={"status": parse["status"]}))
    out.append(Finding("coverage.parse", "info",
                       f"{parse['status'].get('ok', 0)} of {parse['retrieved_ok']} retrieved pages parsed with at least one "
                       f"field beyond their title, {parse['status'].get('empty', 0)} were empty",
                       detail={"unmapped_labels": parse["unmapped_labels"]}))
    out.append(Finding("coverage.source_set", "info",
                       f"{cov['source_set']['documents']} documents from the crawl (set digest {cov['source_set']['digest']})",
                       detail=cov["source_set"]))
    nb = cov["network_bias"]
    out.append(Finding("coverage.network_bias", "info",
                       "researchers without a project edge, by source: " + ", ".join(
                           f"{s} {v['without_project_edges']['n']}/{v['without_project_edges']['of']}"
                           for s, v in nb["persons_without_project_edges"].items()),
                       detail=nb))
    if cov["sentinels"].get("missing"):
        out.append(Finding("coverage.sentinels_missing", "info",
                           "sentinel QA seeds not in the dataset (a sentinel diagnostic, not a coverage estimate): "
                           + ", ".join(cov["sentinels"]["missing"])))
    return out


def _percent(s: dict[str, Any]) -> str:
    """Whole percent, half up, from the counts. The stored 3-decimal rate is for machines: rounding it again
    would show 71.46% as 72% and 52.5% as 52%."""
    return f"{(200 * s['n'] + s['of']) // (2 * s['of'])}%" if s["of"] else ""


def _pct(s: dict[str, Any]) -> str:
    return f"{s['n']} of {s['of']}" + (f" ({_percent(s)})" if s["of"] else "")


def render_coverage_markdown(cov: dict[str, Any], release_id: str) -> str:
    lab = cov["labels"]
    L = [f"# Coverage report: {release_id}", "",
         "Coverage is not correctness: 0 QA errors says the build is consistent, not that it is complete. "
         "Every figure names its denominator; layers are kept apart.", ""]
    ss = cov["source_set"]
    L += ["## Document universe", "",
          f"{ss['documents']} documents (set digest `{ss['digest']}`); retrieved {ss['retrieved']['from']} to "
          f"{ss['retrieved']['until']}.", "",
          "| source | documents | by page type |", "|---|---|---|"]
    for s, v in ss["by_source"].items():
        L.append(f"| {lab.get(s, s)} | {v['documents']} | {', '.join(f'{k} {n}' for k, n in v['by_page_type'].items())} |")
    L.append("")

    L += ["## Discovery: explicit references and what became of them", ""]
    pl = cov["discovery"]["project_links"]
    L.append(f"{pl['distinct_urls']} distinct URLs are written in the project sections of in-scope researcher profiles "
             f"({pl['mentions_by_scope'] and sum(pl['mentions_by_scope'].values())} mentions). By host scope: "
             + ", ".join(f"{k} {v}" for k, v in pl["by_scope"].items()) + ".")
    ins = pl["in_scope"]
    L += ["", f"**Same-host project pages:** {_pct(ins['fetched'])} of the distinct URLs of in-scope hosts linked from "
          f"profile project sections were fetched; {_pct(ins['of_project_path_shape']['fetched'])} of those with the "
          "path shape of a project page.", "",
          "| source (owner of the linked host) | distinct URLs | fetched | not fetched | rate |", "|---|---|---|---|---|"]
    for s, v in ins["by_source"].items():
        L.append(f"| {lab.get(s, s)} | {v['urls']} | {v['fetched']} | {v['not_fetched']} | "
                 f"{_percent(v['fetched_share'])} |")
    L += ["", "Status of those URLs: " + ", ".join(f"{k} {v}" for k, v in ins["by_status"].items()) + ".", ""]
    pll = cov["discovery"]["project_listing_links"]
    L.append(f"Category listings show {pll['distinct_urls']} distinct project URLs; {_pct(pll['fetched'])} were fetched.")
    pf = cov["discovery"]["profile_links"]
    L += ["", f"Profile links: {_pct(pf['fetched'])} of the distinct profile URLs of in-scope hosts linked from listings, unit "
          f"pages and project pages were fetched. Profiles are fetched from staff listings, so the other {pf['not_fetched']} "
          "are linked from a project or unit page and are not on that host's current staff listing "
          f"({pf['not_fetched_with_same_slug_on_another_site']} of them have a profile with the same slug on another TK "
          "site).", ""]

    L += ["## Fetch", "", cov["fetch"]["denominator"] + ".", "",
          "| source | page type | URLs | ok | HTTP error | redirected |", "|---|---|---|---|---|---|"]
    for s, types in cov["fetch"]["by_source"].items():
        for t, c in types.items():
            L.append(f"| {lab.get(s, s)} | {t} | {c.get('urls', 0)} | {c.get('ok', 0)} | {c.get('http_error', 0)} | "
                     f"{c.get('redirected', 0)} |")
    nr = cov["fetch"]["not_retrieved"]
    L += ["", f"Overall {_pct(cov['fetch']['totals'])} answered below HTTP 400; {nr['urls']} URLs were requested but "
          "not retrieved.", ""]

    L += ["## Parse", "", cov["parse"]["denominator"] + ".", "",
          "| source | page type | parsed | ok | empty | error | with unmapped labels |", "|---|---|---|---|---|---|---|"]
    for s, types in cov["parse"]["by_source"].items():
        for t, c in types.items():
            L.append(f"| {lab.get(s, s)} | {t} | {c.get('parsed', 0)} | {c.get('ok', 0)} | {c.get('empty', 0)} | "
                     f"{c.get('error', 0)} | {c.get('with_unmapped_labels', 0)} |")
    recurring = [x for x in cov["parse"]["unmapped_labels"] if x["pages"] > 1]
    if recurring:
        L += ["", "Labelled lines no field took, on more than one page (possible unsupported markup; one-off labels, "
              "mostly names and places in reference lists, are in coverage.json): " + "; ".join(
                  f"{x['page_type']} \"{x['label']}\" ×{x['pages']}" for x in recurring[:12]) + "."]
    L.append("")

    L += ["## Canonicalisation", ""]
    for kind in ("person_mentions", "project_mentions"):
        c = cov["canonicalization"][kind]
        L += [f"**{kind.replace('_', ' ')}**: {c['denominator']}.", "",
              "| source | total | certain | by rule | manual | review | no candidate | resolved |",
              "|---|---|---|---|---|---|---|---|"]
        for s, v in c["by_source"].items():
            L.append(f"| {lab.get(s, s)} | {v['total']} | {v.get('DETERMINISTIC', 0)} | "
                     f"{v.get('HIGH_CONFIDENCE_AUTO', 0)} | {v.get('MANUAL_CONFIRMED', 0)} | "
                     f"{v.get('REVIEW_REQUIRED', 0)} | {v.get('UNRESOLVED', 0)} | {_pct(v['resolved_share'])} |")
        L.append("")
    L += ["Why project mentions have no Project (explicit category; denominator: project mentions not resolved):", "",
          "| category | " + " | ".join(lab.get(s, s) for s in cov["canonicalization"]["project_mentions"]["by_source"]) + " |",
          "|---|" + "---|" * len(cov["canonicalization"]["project_mentions"]["by_source"])]
    ur = cov["canonicalization"]["project_mentions"]["unresolved_by_category"]
    for cat, meaning in UNRESOLVED_CATEGORIES.items():
        row = [ur.get(s, {}).get(cat, 0) for s in cov["canonicalization"]["project_mentions"]["by_source"]]
        if any(row):
            L.append(f"| {cat}: {meaning} | " + " | ".join(str(n) for n in row) + " |")
    L.append("")

    L += ["## Field coverage", ""]
    for kind in ("persons", "projects"):
        f = cov["fields"][kind]
        L += [f"**{kind}**: {f['denominator']}.", ""]
        by = f["by_source"]
        if not by:
            continue
        cols = [k for k in next(iter(by.values())) if k != "total"]
        L += ["| source | total | " + " | ".join(cols) + " |", "|---|---|" + "---|" * len(cols)]
        for s, v in by.items():
            L.append(f"| {lab.get(s, s)} | {v['total']} | " + " | ".join(_percent(v[c]) for c in cols) + " |")
        L.append("")

    nb = cov["network_bias"]
    L += ["## Structural consequences for network analysis (exposed, not corrected)", "",
          "Researchers: profile-backed canonical Persons, each counted once, at the site of their first profile.", "",
          "| source | researchers | without a project edge | no project mention at all | unresolved project mentions |",
          "|---|---|---|---|---|"]
    for s, v in nb["persons_without_project_edges"].items():
        L.append(f"| {lab.get(s, s)} | {v['persons']} | {_pct(v['without_project_edges'])} | "
                 f"{v['of_those_with_no_project_mention_at_all']} | {v['of_those_with_unresolved_project_mentions']} |")
    L += ["", "Why (researchers without a project edge, by the category of their unresolved project mentions; one "
          "researcher can appear under several):", ""]
    for s, v in nb["persons_without_project_edges"].items():
        for r, n in v["by_unresolved_category (persons; one person can have several)"].items():
            L.append(f"- {lab.get(s, s)}: {r} ({UNRESOLVED_CATEGORIES.get(r, r)}): {n}")
    ub = nb["unrealised_ties_upper_bound"]
    L += ["", f"Unrealised ties, upper bound ({ub['definition']}): "
          + (", ".join(f"{k} host {v}" for k, v in ub["by_scope_of_linked_host"].items()) or "none") + ".", "",
          f"Realised: {_pct(nb['realised']['persons_with_project_edges'])} researchers have a project edge; "
          f"{nb['realised']['co_participation_ties']} co-participation ties over {nb['realised']['projects_with_participants']} "
          f"projects with participants ({nb['realised']['multi_source_projects']} span more than one source site).", ""]

    sn = cov["sentinels"]
    if sn:
        L += ["## Sentinels (not a coverage estimate)", "", sn["note"] + ".", "",
              f"Present: {', '.join(sn['present']) or 'none'}. Missing: {', '.join(sn['missing']) or 'none'}.", ""]
    L += ["## Blind spots", ""] + [f"* {x}" for x in cov["blind_spots"]] + [""]
    return "\n".join(L)
