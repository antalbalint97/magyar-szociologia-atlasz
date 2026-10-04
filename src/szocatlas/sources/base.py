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

    def extend(self, other: ParseResult) -> None:
        self.records += other.records
        self.claims += other.claims
        self.documents += other.documents
        self.errors += other.errors


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

    def site_records(self) -> ParseResult:
        """Records describing the site's own organisational unit (from the registry)."""
        return ParseResult()

    # orchestration -------------------------------------------------------
    def fetch(self, url: str, source_type: SourceType) -> Page | None:
        try:
            return self.fetcher.get(url, source_id=self.entry.source_id, source_type=source_type)
        except FetchRefused as e:
            log.warning("%s: %s", self.entry.source_id, e)
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
                try:
                    out.extend(parse(page))
                except Exception as e:  # a broken page must not abort the source
                    log.exception("parse failed for %s", url)
                    out.errors.append({"url": url, "error": f"parse: {e!r}"})
        return out
