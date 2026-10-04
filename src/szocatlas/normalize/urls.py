"""URL canonicalisation with host aliases.

TK pages link to the same profile under several historical hosts
(szociologia.tk.mta.hu, szociologia.tk.hu, szociologia.tk.elte.hu). The alias map
comes from config/sources.yaml so that URL identity is a documented decision.
"""

from __future__ import annotations

import re
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

_MTMT_RE = re.compile(r"(?:sel=(?:authors)?|/authors?/)(\d{4,})")
_ORCID_RE = re.compile(r"(\d{4}-\d{4}-\d{4}-\d{3}[\dX])")
_SCHOLAR_RE = re.compile(r"[?&]user=([\w-]{6,})")
_TRACKING = {"utm_source", "utm_medium", "utm_campaign", "fbclid", "gclid"}


def canonical_url(url: str, base: str | None = None, aliases: dict[str, str] | None = None) -> str:
    if base:
        url = urljoin(base, url)
    parts = urlsplit(url.strip())
    host = (parts.hostname or "").lower()
    if aliases and host in aliases:
        host = aliases[host]
    query = urlencode(sorted((k, v) for k, v in parse_qsl(parts.query) if k not in _TRACKING))
    path = re.sub(r"/{2,}", "/", parts.path or "/")
    if len(path) > 1:
        path = path.rstrip("/")
    return urlunsplit(("https", host, path, query, ""))


def mtmt_id(url: str) -> str | None:
    if "mtmt.hu" not in url:
        return None
    m = _MTMT_RE.search(url)
    return m.group(1) if m else None


def orcid_id(url: str) -> str | None:
    if "orcid.org" not in url:
        return None
    m = _ORCID_RE.search(url)
    return m.group(1) if m else None


def scholar_id(url: str) -> str | None:
    if "scholar.google" not in url:
        return None
    m = _SCHOLAR_RE.search(url)
    return m.group(1) if m else None
