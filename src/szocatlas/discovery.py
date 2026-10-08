"""SOURCE DISCOVERY from profile project links (#16, ADR-0009).

A researcher's profile lists projects and often links the page of the project. Those links are
explicit statements, but the listing-driven crawl only fetches the project pages that a
configured category listing exposes, so a linked page that no listing shows stays unfetched and
its project mention can never resolve to a page-backed Project.

This module follows such links **one hop, under the registry's scope**:

* only links written in a profile's *project section* are candidates (an adapter collects them
  while parsing, ``SourceAdapter.linked_projects``); nothing else on a page is followed;
* the link's host must belong to a source that is **enabled** in ``config/sources.yaml`` and has
  an adapter, and the source's profiles must opt in (``follow_profile_project_links``);
* the URL must have the shape of one of that source's project pages (adapter decides);
* a page that every profile wrote on an *inferred* alias only is not fetched: that alias's path mapping
  was never verified. One statement on a canonical host or a verified alias is enough to fetch the
  page, whatever other profiles wrote (#40); a mention whose own link is inferred-only still does not
  resolve by URL (``canonical/project_mentions.py``);
* the page is fetched through the owner source's adapter with the usual polite fetcher (robots,
  delays, snapshot reuse), parsed with the ordinary project-page parser, and lands in the owner's
  staged output like any listing-discovered page;
* no recursion: a newly fetched page's own links are not followed.

Every candidate, followed or not, gets a **frontier row**: why it entered the frontier
(``discovered_via``), the decision and its reason, the host's status and what the fetch returned.
Nothing is inferred from a URL: a page that was not fetched stays "not fetched" with the reason.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any
from urllib.parse import urlsplit

from .models.enums import SourceType
from .normalize.urls import canonical_url
from .registry import Registry
from .resolution.projects import registry_grant_keys
from .sources.base import LinkedProject, ParseResult, SourceAdapter

log = logging.getLogger(__name__)

LINK_KIND = "profile_project_link"

# decisions
ENQUEUED = "enqueued"
ALREADY = "already_discovered"
SKIPPED = "skipped"

# scopes of the linked host, relative to the registry
IN_SCOPE = "in_scope"  # host of an enabled source with an adapter
OTHER_UNIT = "other_unit_site"  # a site of the same institution that is not an enabled source
EXTERNAL = "external"
GRANT_REGISTRY = "grant_registry"  # a public grant record: it states a grant, it is not a project page

# skip reasons
NOT_HTTP = "not_http"
GRANT_REGISTRY_LINK = "grant_registry_link"
SOURCE_NOT_ENABLED = "source_not_enabled"  # a registered source that is not enabled
SITE_NOT_REGISTERED = "site_not_registered"  # same institution's host, not in the registry
EXTERNAL_HOST = "external_host"
ALIAS_UNVERIFIED = "alias_unverified"
OWNER_NOT_IN_RUN = "owner_not_in_run"
NOT_PROJECT_PATH = "not_project_path"
UNIT_PAGE = "unit_page"


def host_scope(registry: Registry, host: str, institution: str | None) -> tuple[str, str | None, str | None]:
    """(scope, owner source id, why-not-in-scope reason) of a host, from the registry only."""
    for s in registry.sources:
        if s.base_url and (urlsplit(s.base_url).hostname or "").lower() == host:
            if s.enabled and s.adapter:
                return IN_SCOPE, s.source_id, None
            return OTHER_UNIT, s.source_id, SOURCE_NOT_ENABLED
    if institution:
        suffixes = registry.institution(institution).host_suffixes
        if any(host == x or host.endswith("." + x) for x in suffixes):
            return OTHER_UNIT, None, SITE_NOT_REGISTERED
    return EXTERNAL, None, EXTERNAL_HOST


def host_status(registry: Registry, stated_urls: list[str]) -> str:
    """The least certain registry status among the hosts a link was written with (what the frontier row reports;
    the fetch decision looks at the most certain statement, ``Registry.states_trusted_host``)."""
    statuses = {registry.alias_status(urlsplit(u).hostname or "") for u in stated_urls}
    for worst in ("inferred", "unknown", "verified", "canonical"):
        if worst in statuses:
            return worst
    return "unknown"


def follow_profile_project_links(adapters: dict[str, SourceAdapter], results: dict[str, ParseResult],
                                 registry: Registry) -> dict[str, int]:
    """Decide, fetch and parse the candidates every adapter collected; extends ``results`` in place.

    Returns counts by decision for the run report."""
    by_url: dict[str, list[LinkedProject]] = defaultdict(list)
    for a in adapters.values():
        for lp in a.linked_projects:
            by_url[lp.url].append(lp)
    known = {sid: {d.canonical_url for d in res.documents} for sid, res in results.items()}
    counts: dict[str, int] = defaultdict(int)

    for url in sorted(by_url):
        via = sorted(by_url[url], key=lambda v: (v.source_id, v.profile_url, v.title))
        stated = sorted({v.stated_url for v in via})
        parts = urlsplit(url)
        host = (parts.hostname or "").lower()
        institution = adapters[via[0].source_id].entry.institution
        scope, owner, reason = host_scope(registry, host, institution)
        if registry_grant_keys(url):
            scope, owner, reason = GRANT_REGISTRY, None, GRANT_REGISTRY_LINK
        hstat = host_status(registry, stated)
        decision, fetch = SKIPPED, {"attempted": False}
        if parts.scheme not in ("http", "https"):
            reason = NOT_HTTP
        elif scope == IN_SCOPE:
            reason = None
            adapter = adapters.get(owner or "")
            if hstat == "inferred" and not registry.states_trusted_host(stated):
                reason = ALIAS_UNVERIFIED
            elif adapter is None:
                reason = OWNER_NOT_IN_RUN
            else:
                reason = adapter.project_url_problem(url)
            if reason is None:
                if url in known[owner]:
                    decision = ALREADY
                else:
                    decision = ENQUEUED
                    fetch = _fetch_and_parse(adapter, results[owner], url)
                    known[owner].add(url)
        counts[decision if decision != SKIPPED else f"{SKIPPED}:{reason}"] += 1
        row = {"url": url, "kind": LINK_KIND, "host": host, "stated_urls": stated, "scope": scope,
               "owner_source": owner, "decision": decision, "reason": reason if decision == SKIPPED else None,
               "host_status": hstat, "fetch": fetch}
        for sid in sorted({v.source_id for v in via}):
            results[sid].frontier.append(row | {"discovered_via": [
                {"type": LINK_KIND, "source_id": v.source_id, "source_document": v.document_id,
                 "source_url": v.profile_url, "project_ref": v.project_ref, "title": v.title}
                for v in via if v.source_id == sid]})
    return dict(sorted(counts.items()))


def _fetch_and_parse(adapter: SourceAdapter, out: ParseResult, url: str) -> dict[str, Any]:
    """Fetch one linked page with the owner's adapter; documents, claims and errors go to its result."""
    page = adapter.fetch(url, SourceType.PROJECT_PAGE)
    if page is None:
        out.errors.append({"url": url, "error": "not fetched"})
        return {"attempted": True, "error": adapter.last_fetch_error or "not fetched"}
    doc = page.document
    out.documents.append(doc)
    outcome: dict[str, Any] = {
        "attempted": True, "document_id": doc.document_id, "http_status": doc.http_status,
        "final_url": doc.final_url, "redirected": canonical_url(doc.final_url) != url,
        "retrieved_at": doc.retrieved_at.isoformat(), "error": None}
    if doc.http_status >= 400:
        out.errors.append({"url": url, "error": f"HTTP {doc.http_status}"})
        outcome["error"] = f"HTTP {doc.http_status}"
        return outcome
    parsed = adapter.parse_safely(adapter.parse_project, page, SourceType.PROJECT_PAGE)
    if parsed.errors:
        outcome["error"] = parsed.errors[0]["error"]
    out.extend(parsed)
    return outcome


def merge_frontier(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """One row per URL: the sources' rows share decision and fetch outcome, so only ``discovered_via`` is united."""
    merged: dict[str, dict[str, Any]] = {}
    for r in rows:
        m = merged.setdefault(r["url"], r | {"discovered_via": []})
        for v in r["discovered_via"]:
            if v not in m["discovered_via"]:
                m["discovered_via"].append(v)
    for m in merged.values():
        m["discovered_via"].sort(key=lambda v: (v["source_id"], v["source_url"], v["title"]))
    return [merged[u] for u in sorted(merged)]
