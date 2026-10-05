"""FETCH -> RAW SNAPSHOT.

Every retrieval is written to the raw store before anything parses it:

    data/raw/<source_id>/pages/<sha256[:2]>/<sha256>.html   (body, byte-exact)
    data/raw/<source_id>/documents.jsonl                     (SourceDocument per fetch)

Parsers only ever receive (SourceDocument, text) pairs read back from the store, so a
parse can be replayed offline from the same snapshot (``ReplayFetcher``).
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
import urllib.robotparser
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Protocol

import httpx

from .models.enums import SourceType
from .models.provenance import SourceDocument
from .normalize.urls import canonical_url
from .registry import CrawlPolicy

FETCHER_VERSION = "fetch/0.1.0"
log = logging.getLogger(__name__)
RETRIES = 2
RETRY_STATUSES = {429, 500, 502, 503, 504}


class FetchRefused(Exception):
    """robots.txt or crawl policy forbids this request."""


@dataclass
class Page:
    document: SourceDocument
    text: str


class Fetcher(Protocol):
    def get(self, url: str, *, source_id: str, source_type: SourceType) -> Page: ...


class RawStore:
    def __init__(self, root: Path):
        self.root = root

    def _dir(self, source_id: str) -> Path:
        return self.root / source_id

    def write(self, doc: SourceDocument, body: bytes) -> None:
        path = self.root / doc.raw_path
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            path.write_bytes(body)
        with open(self._dir(doc.source_id) / "documents.jsonl", "a", encoding="utf-8") as fh:
            fh.write(doc.model_dump_json() + "\n")

    def documents(self, source_id: str) -> list[SourceDocument]:
        p = self._dir(source_id) / "documents.jsonl"
        if not p.exists():
            return []
        with open(p, encoding="utf-8") as fh:
            return [SourceDocument.model_validate_json(line) for line in fh if line.strip()]

    def latest(self, source_id: str, canon: str) -> SourceDocument | None:
        docs = [d for d in self.documents(source_id) if d.canonical_url == canon]
        return max(docs, key=lambda d: d.retrieved_at) if docs else None

    def read(self, doc: SourceDocument) -> str:
        return (self.root / doc.raw_path).read_bytes().decode("utf-8", errors="replace")


def _title(html: str) -> str | None:
    lo = html.lower()
    i = lo.find("<title>")
    j = lo.find("</title>", i)
    if i == -1 or j == -1:
        return None
    return " ".join(html[i + 7 : j].split()) or None


def make_document(
    *,
    url: str,
    final_url: str,
    body: bytes,
    source_id: str,
    source_type: SourceType,
    status: int,
    content_type: str | None,
    aliases: dict[str, str],
    retrieved_at: datetime,
    synthetic: bool = False,
) -> SourceDocument:
    sha = hashlib.sha256(body).hexdigest()
    canon = canonical_url(final_url, aliases=aliases)
    return SourceDocument(
        document_id=SourceDocument.make_id(canon, sha),
        source_id=source_id,
        url=url,
        final_url=final_url,
        canonical_url=canon,
        retrieved_at=retrieved_at,
        http_status=status,
        content_type=content_type,
        content_sha256=sha,
        raw_path=f"{source_id}/pages/{sha[:2]}/{sha}.html",
        page_title=_title(body.decode("utf-8", errors="replace")),
        source_type=source_type,
        fetcher_version=FETCHER_VERSION,
        synthetic=synthetic,
    )


class PoliteFetcher:
    """HTTP fetcher that honours robots.txt, per-host delay and a page budget."""

    def __init__(self, store: RawStore, policy: CrawlPolicy, aliases: dict[str, str]):
        self.store = store
        self.policy = policy
        self.aliases = aliases
        self.client = httpx.Client(
            headers={"User-Agent": policy.user_agent, "Accept-Language": "hu,en;q=0.5"},
            timeout=policy.timeout_seconds,
            follow_redirects=True,
        )
        self._robots: dict[str, urllib.robotparser.RobotFileParser | None] = {}
        self._robots_unavailable: dict[str, str] = {}  # origin -> why robots.txt could not be read
        self._last_hit: dict[str, float] = {}
        self.pages_fetched = 0

    @staticmethod
    def _origin(url: str) -> str:
        u = httpx.URL(url)
        return f"{u.scheme}://{u.host}"

    def _allowed(self, url: str) -> bool:
        if not self.policy.respect_robots:
            return True
        origin = self._origin(url)
        if origin not in self._robots:
            rp = urllib.robotparser.RobotFileParser()
            try:
                r = self.client.get(origin + "/robots.txt")
            except httpx.HTTPError as e:
                # Unreachable robots.txt: be conservative and do not crawl the host.
                log.warning("robots.txt unreachable for %s (%s); refusing host", origin, e)
                self._robots[origin] = None
                self._robots_unavailable[origin] = f"robots.txt unreachable ({type(e).__name__})"
                return False
            if r.status_code >= 500:
                self._robots[origin] = None
                self._robots_unavailable[origin] = f"robots.txt answered HTTP {r.status_code}"
            elif r.status_code >= 400:
                rp.parse([])  # no robots.txt: everything allowed
                self._robots[origin] = rp
            else:
                rp.parse(r.text.splitlines())
                self._robots[origin] = rp
        rp = self._robots[origin]
        return bool(rp and rp.can_fetch(self.policy.user_agent, url))

    def _wait(self, host: str) -> None:
        delay = self.policy.min_delay_seconds
        last = self._last_hit.get(host)
        if last is not None:
            remaining = delay - (time.monotonic() - last)
            if remaining > 0:
                time.sleep(remaining)
        self._last_hit[host] = time.monotonic()

    def _get_with_retry(self, url: str) -> httpx.Response:
        """GET with a few spaced retries on transport errors and 429/5xx (polite backoff)."""
        host = httpx.URL(url).host
        for attempt in range(RETRIES + 1):
            self._wait(host)
            try:
                r = self.client.get(url)
            except httpx.TransportError as e:
                if attempt == RETRIES:
                    raise FetchRefused(f"transport error after {RETRIES + 1} attempts: {url} ({e!r})") from e
                log.warning("transport error on %s (%r); retrying", url, e)
            else:
                if r.status_code not in RETRY_STATUSES or attempt == RETRIES:
                    return r
                log.warning("HTTP %s on %s; retrying", r.status_code, url)
            time.sleep(self.policy.min_delay_seconds * 2 ** (attempt + 1))
        raise AssertionError("unreachable")

    def get(self, url: str, *, source_id: str, source_type: SourceType) -> Page:
        canon = canonical_url(url, aliases=self.aliases)
        cached = self.store.latest(source_id, canon)
        if cached and datetime.now(UTC) - cached.retrieved_at < timedelta(
            days=self.policy.max_age_days
        ):
            return Page(cached, self.store.read(cached))
        if self.pages_fetched >= self.policy.max_pages_per_run:
            raise FetchRefused(f"page budget {self.policy.max_pages_per_run} exhausted")
        if not self._allowed(url):
            # not one fact: the site disallows the page, or its robots.txt could not be read (unreachable, HTTP 5xx)
            # and the host is refused to be safe. The message keeps them apart, because coverage must (#12).
            why = self._robots_unavailable.get(self._origin(url))
            raise FetchRefused(f"{why}, host not crawled: {url}" if why else f"robots.txt disallows {url}")
        r = self._get_with_retry(url)
        self.pages_fetched += 1
        doc = make_document(
            url=url,
            final_url=str(r.url),
            body=r.content,
            source_id=source_id,
            source_type=source_type,
            status=r.status_code,
            content_type=r.headers.get("content-type"),
            aliases=self.aliases,
            retrieved_at=datetime.now(UTC),
        )
        self.store.write(doc, r.content)
        return Page(doc, r.content.decode(r.encoding or "utf-8", errors="replace"))


class ReplayFetcher:
    """Serves pages from the raw store only. Used for offline re-parsing."""

    def __init__(self, store: RawStore, aliases: dict[str, str]):
        self.store = store
        self.aliases = aliases

    def get(self, url: str, *, source_id: str, source_type: SourceType) -> Page:
        doc = self.store.latest(source_id, canonical_url(url, aliases=self.aliases))
        if doc is None:
            raise FetchRefused(f"no snapshot for {url} in replay mode")
        return Page(doc, self.store.read(doc))


class FixtureFetcher:
    """Serves files from a fixture directory keyed by URL (tests and the fixture sample)."""

    def __init__(self, mapping: dict[str, Path], aliases: dict[str, str], observed: datetime):
        self.aliases = aliases
        self.observed = observed
        self.by_canon = {canonical_url(u, aliases=aliases): p for u, p in mapping.items()}

    def get(self, url: str, *, source_id: str, source_type: SourceType) -> Page:
        canon = canonical_url(url, aliases=self.aliases)
        path = self.by_canon.get(canon)
        if path is None:
            raise FetchRefused(f"no fixture for {url}")
        body = path.read_bytes()
        doc = make_document(
            url=url,
            final_url=url,
            body=body,
            source_id=source_id,
            source_type=source_type,
            status=200,
            content_type="text/html; charset=utf-8",
            aliases=self.aliases,
            retrieved_at=self.observed,
            synthetic=True,
        )
        return Page(doc, body.decode("utf-8"))


def dump_jsonl(path: Path, rows) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with open(path, "w", encoding="utf-8") as fh:
        for row in rows:
            fh.write((row.model_dump_json() if hasattr(row, "model_dump_json") else json.dumps(row, ensure_ascii=False, default=str)) + "\n")
            n += 1
    return n
