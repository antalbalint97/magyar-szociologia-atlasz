"""Source adapter interface.

An adapter knows one family of websites. It discovers URLs, fetches them through
the shared Fetcher (so every page lands in the raw store) and turns each page into
SourceRecords + Claims. Adapters never resolve identities and never write canonical
data: that happens downstream, uniformly for every source.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

from ..fetch import Fetcher, FetchRefused, Page
from ..models.enums import (
    AssertionType,
    EntityType,
    EpistemicStatus,
    ExtractionMethod,
    SourceType,
    TemporalBasis,
)
from ..models.provenance import Claim, EntityRef, Evidence, SourceDocument, SourceRecord
from ..registry import Registry, SourceEntry

log = logging.getLogger(__name__)


@dataclass
class ParseResult:
    records: list[SourceRecord] = field(default_factory=list)
    claims: list[Claim] = field(default_factory=list)
    documents: list[SourceDocument] = field(default_factory=list)
    errors: list[dict[str, Any]] = field(default_factory=list)
    # #16: URLs a page told the crawl about, why each was or was not followed, what came of it
    frontier: list[dict[str, Any]] = field(default_factory=list)
    # #12: one row per parsed page: what the parser found in it (never claims, never identity)
    diagnostics: list[dict[str, Any]] = field(default_factory=list)

    def extend(self, other: ParseResult) -> None:
        self.records += other.records
        self.claims += other.claims
        self.documents += other.documents
        self.errors += other.errors
        self.frontier += other.frontier
        self.diagnostics += other.diagnostics


@dataclass
class LinkedProject:
    """A link in a profile's project section: the page the researcher says is the project (#16).

    Only links observed in that project context are ever candidates for crawling; the profile is
    the discovery evidence (``discovered_via`` in the frontier), not a proof that the page is a
    project page."""

    url: str  # canonical (host aliases applied)
    stated_url: str  # as written on the profile
    title: str
    source_id: str  # the source whose profile states the link
    profile_url: str
    document_id: str  # the profile's document
    project_ref: str  # source_ref of the project record the profile observation made


class ClaimFactory:
    """Builds claims bound to one document, so parsers cannot forget provenance."""

    def __init__(self, doc: SourceDocument, parser: str, parser_version: str):
        self.doc = doc
        self.parser = parser
        self.parser_version = parser_version

    def literal(
        self,
        subject: EntityRef,
        predicate: str,
        value: Any,
        *,
        locator: str,
        snippet: str,
        confidence: float = 0.95,
        assertion_type: AssertionType | None = AssertionType.INSTITUTIONAL,
        **kw: Any,
    ) -> Claim:
        return Claim(
            subject=subject,
            predicate=predicate,
            value=value,
            observed_at=self.doc.retrieved_at,
            temporal_basis=kw.pop("temporal_basis", TemporalBasis.OBSERVED_AT),
            evidence=Evidence(document_id=self.doc.document_id, locator=locator, snippet=snippet),
            extraction_method=ExtractionMethod.HTML_PARSER,
            parser=self.parser,
            parser_version=self.parser_version,
            epistemic_status=EpistemicStatus.OBSERVED,
            assertion_type=assertion_type,
            confidence=confidence,
            **kw,
        )

    def relation(
        self,
        subject: EntityRef,
        predicate: str,
        obj: EntityRef,
        *,
        locator: str,
        snippet: str,
        confidence: float = 0.9,
        assertion_type: AssertionType | None = AssertionType.INSTITUTIONAL,
        **kw: Any,
    ) -> Claim:
        return Claim(
            subject=subject,
            predicate=predicate,
            object=obj,
            observed_at=self.doc.retrieved_at,
            temporal_basis=kw.pop("temporal_basis", TemporalBasis.OBSERVED_AT),
            evidence=Evidence(document_id=self.doc.document_id, locator=locator, snippet=snippet),
            extraction_method=ExtractionMethod.HTML_PARSER,
            parser=self.parser,
            parser_version=self.parser_version,
            epistemic_status=EpistemicStatus.OBSERVED,
            assertion_type=assertion_type,
            confidence=confidence,
            **kw,
        )


PAGE_TYPES = {SourceType.INSTITUTIONAL_PROFILE: "profile", SourceType.UNIT_PAGE: "unit",
              SourceType.PROJECT_PAGE: "project", SourceType.INSTITUTIONAL_LISTING: "listing"}


def diagnostic(doc: SourceDocument, parser: str, page_type: str, fields: dict[str, int | bool],
               unmapped_labels: list[str] | None = None) -> dict[str, Any]:
    """What a parser found in one page (#12). ``fields`` lists what the page offered *besides* its
    title/name: a page with none of them parsed, but is empty."""
    found = {k: v for k, v in fields.items() if v}
    return {"document_id": doc.document_id, "url": doc.canonical_url, "source_id": doc.source_id,
            "page_type": page_type, "parser": parser, "status": "ok" if found else "empty",
            "fields": dict(fields), "unmapped_labels": sorted(set(unmapped_labels or [])), "error": None}


def local_ref(entry_or_id: SourceEntry | str, etype: EntityType, key: str) -> EntityRef:
    sid = entry_or_id if isinstance(entry_or_id, str) else entry_or_id.source_id
    return EntityRef(entity_type=etype, source_ref=f"{sid}|{key}")


class SourceAdapter(ABC):
    """Consistent interface every source family implements (spec section 9)."""

    name: str
    parser_version: str

    def __init__(self, entry: SourceEntry, registry: Registry, fetcher: Fetcher):
        self.entry = entry
        self.registry = registry
        self.fetcher = fetcher
        self.aliases = registry.host_aliases()
        self.linked_projects: list[LinkedProject] = []
        self.last_fetch_error: str | None = None

    # discovery -----------------------------------------------------------
    @abstractmethod
    def discover_people(self) -> Iterator[str]: ...

    def discover_units(self) -> Iterator[str]:
        return iter(())

    def discover_projects(self) -> Iterator[str]:
        return iter(())

    # parsing -------------------------------------------------------------
    @abstractmethod
    def parse_person(self, page: Page) -> ParseResult: ...

    def parse_unit(self, page: Page) -> ParseResult:
        return ParseResult()

    def parse_project(self, page: Page) -> ParseResult:
        return ParseResult()

    # profile project links (#16) ----------------------------------------
    @property
    def follows_profile_project_links(self) -> bool:
        """Registry opt-in (adapter_config.follow_profile_project_links) for this source's profiles."""
        return bool(self.entry.adapter_config.get("follow_profile_project_links"))

    def project_url_problem(self, url: str) -> str | None:
        """None when the URL has the shape of one of this source's project pages, else why not."""
        return "adapter has no project pages"

    def site_records(self) -> ParseResult:
        """Records describing the site's own organisational unit (from the registry)."""
        return ParseResult()

    # orchestration -------------------------------------------------------
    def fetch(self, url: str, source_type: SourceType) -> Page | None:
        self.last_fetch_error = None
        try:
            return self.fetcher.get(url, source_id=self.entry.source_id, source_type=source_type)
        except FetchRefused as e:
            log.warning("%s: %s", self.entry.source_id, e)
            self.last_fetch_error = str(e)
            return None

    def run(self) -> ParseResult:
        out = self.site_records()
        stages = (
            (self.discover_units, SourceType.UNIT_PAGE, self.parse_unit),
            (self.discover_people, SourceType.INSTITUTIONAL_PROFILE, self.parse_person),
            (self.discover_projects, SourceType.PROJECT_PAGE, self.parse_project),
        )
        for discover, stype, parse in stages:
            for url in discover():
                page = self.fetch(url, stype)
                if page is None:
                    out.errors.append({"url": url, "error": "not fetched"})
                    continue
                out.documents.append(page.document)
                if page.document.http_status >= 400:
                    out.errors.append({"url": url, "error": f"HTTP {page.document.http_status}"})
                    continue
                out.extend(self.parse_safely(parse, page, stype))
        return out

    def parse_safely(self, parse, page: Page, stype: SourceType) -> ParseResult:
        """Run one page parser; a broken page must not abort the source."""
        try:
            return parse(page)
        except Exception as e:
            log.exception("parse failed for %s", page.document.url)
            res = ParseResult()
            res.errors.append({"url": page.document.url, "error": f"parse: {e!r}"})
            res.diagnostics.append({
                "document_id": page.document.document_id, "url": page.document.canonical_url,
                "source_id": page.document.source_id, "page_type": PAGE_TYPES.get(stype, stype.value),
                "parser": f"{self.name}/{self.parser_version}", "status": "error", "fields": {},
                "unmapped_labels": [], "error": repr(e)})
            return res
