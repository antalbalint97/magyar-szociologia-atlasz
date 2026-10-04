"""Page parsers for the TK institute sites (szociologia / recens / kisebbsegkutato / ...).

Design choice: no CSS-class selectors. The parsers rely on things that survived the
site's several host migrations: the <h1>, labelled fields ("Osztályvezető:",
"Időtartam:"), section headings ("Kutatási területek", "Projektek") and URL
patterns (/kutato/<slug>, m2.mtmt.hu). This keeps them working on markup changes and
makes them testable against reconstructed fixtures.

Each function returns plain dataclasses; the adapter turns them into claims.
Contact details (phone, room, e-mail local part) are recognised only to be dropped.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from urllib.parse import urlsplit

from bs4 import BeautifulSoup, Tag

from ...normalize.names import clean_display_name, normalise_whitespace
from ...normalize.urls import canonical_url, mtmt_id, orcid_id, scholar_id

PARSER_VERSION = "tk/0.1.0"

PROFILE_PATH_RE = re.compile(r"^/kutato/(?!pdf/)([a-z0-9][a-z0-9-]*)/?$")
CV_PATH_RE = re.compile(r"^/kutato/pdf/(\d+)$")
LISTING_PATH_RE = re.compile(r"^/kutatok(?:/[a-z]{1,3})?/?$")
PHONE_RE = re.compile(r"(\+36|telefon|tel\.|^\d[\d /-]{6,}$)", re.I)
ROOM_RE = re.compile(r"(épület|szoba|building|room)", re.I)
DEGREE_RE = re.compile(r"^(phd|ph\.d\.|habil\.?|dsc|csc|d\.sc\.|c\.sc\.|mta doktora)([ ,.]+(phd|habil\.?|dsc|csc))*\.?$", re.I)
POSITION_RE = re.compile(
    r"(munkatárs|professzor|kutató|igazgató|asszisztens|ösztöndíjas|tanácsadó|"
    r"emeritus|emerita|gyakornok|doktorandusz|vezető)",
    re.I,
)
INSTITUTE_CODE_RE = re.compile(r"\((TK [^)]+)\)\s*$")
UNIT_RE = re.compile(
    r"(osztály|kutatócsoport|csoport|intézet|központ|centrum|laboratórium|recens)", re.I
)
UNIT_LABEL_RE = re.compile(r"^(osztály|kutatási osztály|egység|csoport)\s*:\s*", re.I)
LEADER_LABEL_RE = re.compile(
    r"^(osztályvezető|vezető|igazgató|intézetigazgató|csoportvezető|kutatócsoport-vezető)\s*:?\s*$",
    re.I,
)
PROJECT_LEAD_LABEL_RE = re.compile(r"^(projektvezető|témavezető|kutatásvezető|vezető kutató)", re.I)
PARTICIPANTS_LABEL_RE = re.compile(r"^(résztvevők|résztvevő kutatók|kutatók|munkatársak|kutatócsoport)", re.I)
GRANT_LABEL_RE = re.compile(r"^(projektazonosító|azonosító|pályázati azonosító|projektszám)", re.I)
PERIOD_LABEL_RE = re.compile(r"^(időtartam|futamidő|projekt időtartama|időszak)", re.I)
FUNDER_LABEL_RE = re.compile(r"^(finanszírozó|támogató|forrás)", re.I)
DATE_SPAN_RE = re.compile(
    r"(\d{4})(?:[.\-/](\d{1,2})(?:[.\-/](\d{1,2}))?)?\.?\s*[-–—]\s*(?:(\d{4})(?:[.\-/](\d{1,2})(?:[.\-/](\d{1,2}))?)?)?"
)
TRAILING_PERIOD_RE = re.compile(r"\s*\((\d{4})\s*[-–]\s*(\d{4})?\)\s*$")
FUNDER_PREFIX_RE = re.compile(r"^(NKFIH|OTKA|NKFI|ERC|H2020|Horizon Europe|MTA|EFOP|GINOP|TKP)\b", re.I)

SECTION_AREAS = re.compile(r"^kutatási (terület|téma)", re.I)
SECTION_PROJECTS = re.compile(r"^(projektek|kutatások|futó projektek)", re.I)
SECTION_PUBS = re.compile(r"publikáció", re.I)
SECTION_MEMBERS = re.compile(r"^(munkatársak|tagok|kutatók)", re.I)

BLOCK_TAGS = ["p", "li", "div", "dd", "dt", "td", "span"]


def soup_of(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "lxml")


def text_of(el: Tag) -> str:
    return normalise_whitespace(el.get_text(" "))


def _is_leaf_block(el: Tag) -> bool:
    return not any(isinstance(c, Tag) and c.name in ("p", "div", "li", "ul", "ol", "table") for c in el.children)


def _main(soup: BeautifulSoup) -> Tag:
    return soup.find("main") or soup.find(attrs={"role": "main"}) or soup.body or soup


def _host(url: str) -> str:
    return (urlsplit(url).hostname or "").lower()


@dataclass
class Link:
    url: str  # canonical
    text: str


@dataclass
class ProjectMention:
    title: str
    url: str | None
    snippet: str
    period_from: str | None = None
    period_until: str | None = None


@dataclass
class ProfilePage:
    name: str
    name_snippet: str
    titles: list[str] = field(default_factory=list)
    positions: list[str] = field(default_factory=list)
    institute_codes: list[str] = field(default_factory=list)
    unit_lines: list[str] = field(default_factory=list)
    email_domain: str | None = None
    mtmt_id: str | None = None
    mtmt_url: str | None = None
    orcid: str | None = None
    scholar_id: str | None = None
    other_profiles: list[str] = field(default_factory=list)  # academia.edu etc.
    cv_url: str | None = None
    research_areas: list[str] = field(default_factory=list)
    projects: list[ProjectMention] = field(default_factory=list)
    biography: str | None = None


@dataclass
class ListingPage:
    people: list[tuple[Link, str | None]]  # (profile link, position line next to it)
    next_pages: list[str]


@dataclass
class UnitPage:
    name: str
    leaders: list[tuple[Link, str]]  # (person link, label e.g. "Osztályvezető")
    members: list[Link]
    description: str | None


@dataclass
class ProjectPage:
    title: str
    grant_id: str | None = None
    grant_snippet: str | None = None
    funder: str | None = None
    start: str | None = None
    end: str | None = None
    period_snippet: str | None = None
    leads: list[Link] = field(default_factory=list)
    participants: list[Link] = field(default_factory=list)
    unlinked_participants: list[tuple[str, str]] = field(default_factory=list)  # (name, role)
    description: str | None = None


# ---------------------------------------------------------------- helpers


def _links(el: Tag, base: str, aliases: dict[str, str]) -> list[Link]:
    out = []
    for a in el.find_all("a", href=True):
        href = a["href"].strip()
        if href.startswith(("mailto:", "tel:", "#", "javascript:")):
            continue
        out.append(Link(canonical_url(href, base=base, aliases=aliases), text_of(a)))
    return out


def is_profile_url(url: str) -> bool:
    return bool(PROFILE_PATH_RE.match(urlsplit(url).path))


def _partial_date(y: str | None, m: str | None, d: str | None) -> str | None:
    if not y:
        return None
    out = y
    if m:
        out += f"-{int(m):02d}"
        if d:
            out += f"-{int(d):02d}"
    return out


def parse_period(text: str) -> tuple[str | None, str | None]:
    m = DATE_SPAN_RE.search(text)
    if not m:
        return None, None
    return _partial_date(m.group(1), m.group(2), m.group(3)), _partial_date(
        m.group(4), m.group(5), m.group(6)
    )


def _header_lines(h1: Tag) -> list[Tag]:
    """Leaf blocks between the <h1> and the first section heading."""
    out = []
    for el in h1.find_all_next():
        if el.name in ("h2", "h3"):
            break
        if el.name in ("p", "li", "div", "dd") and _is_leaf_block(el) and text_of(el):
            out.append(el)
    return out


def _sections(main: Tag) -> dict[str, list[Tag]]:
    """heading text -> leaf blocks until the next heading of the same or higher level."""
    out: dict[str, list[Tag]] = {}
    for h in main.find_all(["h2", "h3"]):
        blocks = []
        for el in h.find_all_next():
            if el.name in ("h1", "h2", "h3"):
                break
            if el.name in ("p", "li", "dd") and _is_leaf_block(el) and text_of(el):
                blocks.append(el)
        out[text_of(h)] = blocks
    return out


def _labelled(main: Tag) -> list[tuple[str, Tag, str]]:
    """(label, block, value-text) for "Label: value" blocks (strong/b/span/dt markup or plain)."""
    out = []
    for el in main.find_all(["p", "div", "li", "dd", "tr"]):
        if not _is_leaf_block(el) and el.name != "tr":
            continue
        txt = text_of(el)
        if ":" not in txt[:60]:
            continue
        label, _, value = txt.partition(":")
        out.append((label.strip(), el, value.strip()))
    return out


# ---------------------------------------------------------------- parsers


def parse_listing(html: str, base: str, aliases: dict[str, str]) -> ListingPage:
    main = _main(soup_of(html))
    people: dict[str, tuple[Link, str | None]] = {}
    next_pages: list[str] = []
    for a in main.find_all("a", href=True):
        url = canonical_url(a["href"], base=base, aliases=aliases)
        path = urlsplit(url).path
        if PROFILE_PATH_RE.match(path):
            container = a.find_parent(["div", "li", "article", "tr"]) or a.parent
            position = None
            for line in container.find_all(["p", "span", "div"]):
                t = text_of(line)
                if t and t != text_of(a) and POSITION_RE.search(t):
                    position = t
                    break
            people.setdefault(url, (Link(url, text_of(a)), position))
        elif LISTING_PATH_RE.match(path) and _host(url) == _host(base):
            next_pages.append(url)
    return ListingPage(list(people.values()), sorted(set(next_pages)))


def parse_profile(html: str, base: str, aliases: dict[str, str], site_unit: str | None) -> ProfilePage:
    soup = soup_of(html)
    main = _main(soup)
    h1 = main.find("h1")
    if h1 is None:
        raise ValueError("profile without <h1>")
    raw_name = text_of(h1)
    name, titles = clean_display_name(raw_name)
    page = ProfilePage(name=name, name_snippet=raw_name, titles=titles)

    consumed: set[int] = set()
    for el in _header_lines(h1):
        line = text_of(el)
        if len(line) >= 80 and not el.find("a", href=True):
            continue  # long prose in the header area is biography, handled below
        consumed.add(id(el))
        for a in el.find_all("a", href=True):
            href = a["href"].strip()
            if href.startswith("mailto:"):
                addr = href[7:].split("?")[0]
                if "@" in addr:
                    page.email_domain = addr.rsplit("@", 1)[1].lower()
                continue
            url = canonical_url(href, base=base, aliases=aliases)
            if (mid := mtmt_id(url)) is not None:
                page.mtmt_id, page.mtmt_url = mid, url
            elif (oid := orcid_id(url)) is not None:
                page.orcid = oid
            elif (sid := scholar_id(url)) is not None:
                page.scholar_id = sid
            elif CV_PATH_RE.match(urlsplit(url).path):
                page.cv_url = url
            elif "academia.edu" in url or "researchgate.net" in url:
                page.other_profiles.append(url)
            # linkedin and other social media are deliberately not recorded
        if el.find("a", href=True):
            continue
        if "@" in line or PHONE_RE.search(line) or ROOM_RE.search(line):
            continue  # contact details: never stored
        if DEGREE_RE.match(line):
            page.titles += [t for t in re.split(r"[ ,]+", line) if t]
            continue
        labelled_unit = UNIT_LABEL_RE.match(line)
        if labelled_unit:
            page.unit_lines.append(line[labelled_unit.end():].strip())
            continue
        if POSITION_RE.search(line) and (INSTITUTE_CODE_RE.search(line) or len(line) < 80):
            page.positions.append(line)
            if m := INSTITUTE_CODE_RE.search(line):
                page.institute_codes.append(m.group(1))
            continue
        if UNIT_RE.search(line) and len(line) < 140:
            page.unit_lines.append(line)

    for heading, blocks in _sections(main).items():
        if SECTION_AREAS.match(heading):
            for b in blocks:
                t = text_of(b)
                items = [t] if b.name == "li" else [x.strip() for x in re.split(r"[;\n]", t)]
                page.research_areas += [i for i in items if i]
        elif SECTION_PROJECTS.match(heading):
            for b in blocks:
                t = text_of(b)
                links = _links(b, base, aliases)
                period_from = period_until = None
                title = t
                if m := TRAILING_PERIOD_RE.search(t):
                    period_from, period_until = m.group(1), m.group(2)
                    title = t[: m.start()].strip()
                page.projects.append(
                    ProjectMention(
                        title=links[0].text if links else title,
                        url=links[0].url if links else None,
                        snippet=t,
                        period_from=period_from,
                        period_until=period_until,
                    )
                )

    # biography: first substantial paragraph outside the header and outside sections
    for p in main.find_all("p"):
        t = text_of(p)
        if id(p) in consumed or len(t) < 80:
            continue
        prev_h = p.find_previous(["h1", "h2", "h3"])
        if prev_h is not None and prev_h.name != "h1":
            continue
        page.biography = t
        break
    if site_unit:
        # The site's own unit name repeated in the header is not a separate unit.
        key = normalise_whitespace(site_unit).lower()
        page.unit_lines = [u for u in page.unit_lines if normalise_whitespace(u).lower() != key]
    return page


def parse_unit(html: str, base: str, aliases: dict[str, str]) -> UnitPage:
    main = _main(soup_of(html))
    h1 = main.find("h1")
    if h1 is None:
        raise ValueError("unit page without <h1>")
    leaders: list[tuple[Link, str]] = []
    leader_urls: set[str] = set()
    for label, el, _value in _labelled(main):
        if LEADER_LABEL_RE.match(label + ":") or LEADER_LABEL_RE.match(label):
            for link in _links(el, base, aliases):
                if is_profile_url(link.url):
                    leaders.append((link, label))
                    leader_urls.add(link.url)
    members = []
    seen = set()
    for link in _links(main, base, aliases):
        if is_profile_url(link.url) and link.url not in seen:
            seen.add(link.url)
            if link.url not in leader_urls:
                members.append(link)
    description = None
    for p in main.find_all("p"):
        t = text_of(p)
        if len(t) >= 60 and not p.find("a"):
            description = t
            break
    return UnitPage(text_of(h1), leaders, members, description)


def parse_project(html: str, base: str, aliases: dict[str, str]) -> ProjectPage:
    main = _main(soup_of(html))
    h1 = main.find("h1")
    if h1 is None:
        raise ValueError("project page without <h1>")
    page = ProjectPage(title=text_of(h1))
    for label, el, value in _labelled(main):
        if GRANT_LABEL_RE.match(label):
            page.grant_id, page.grant_snippet = value, text_of(el)
            if m := FUNDER_PREFIX_RE.match(value):
                page.funder = m.group(1).upper()
        elif PERIOD_LABEL_RE.match(label):
            page.start, page.end = parse_period(value)
            page.period_snippet = text_of(el)
        elif FUNDER_LABEL_RE.match(label):
            page.funder = value
        elif PROJECT_LEAD_LABEL_RE.match(label):
            page.leads += [lk for lk in _links(el, base, aliases) if is_profile_url(lk.url)]
        elif PARTICIPANTS_LABEL_RE.match(label):
            page.participants += [lk for lk in _links(el, base, aliases) if is_profile_url(lk.url)]
            # unlinked names introduced by a role label, e.g. "Külső szakértő: X Y"
            for chunk in re.split(r";", value):
                if ":" in chunk:
                    role, _, names = chunk.partition(":")
                    for n in names.split(","):
                        n = n.strip()
                        if n and not any(n == lk.text for lk in page.participants):
                            page.unlinked_participants.append((n, role.strip()))
    for p in main.find_all("p"):
        t = text_of(p)
        if len(t) >= 80 and ":" not in t[:40]:
            page.description = t
            break
    return page
