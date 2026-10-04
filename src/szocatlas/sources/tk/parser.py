"""Page parsers for the TK institute sites (szociologia / recens / kisebbsegkutato / ...).

Design choice: no CSS-class selectors. The parsers rely on things that survived the
site's several host migrations: the page title heading, labelled fields ("Osztály:",
"Kutatásvezető:"), section headings ("Kutatási területek", "Projektek") and URL
patterns (/kutato/<slug>, m2.mtmt.hu).

Observed markup (live pages, 2026-10-04): the page title is an <h2> (no <h1>), profile
sections use <h5> headings, project pages put funder / period / lead on one <p>
separated by <br>, and category listings are <article> lists with the same lines.

Each function returns plain dataclasses; the adapter turns them into claims.
Contact details (phone, room, e-mail local part) are recognised only to be dropped.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from urllib.parse import urlsplit

from bs4 import BeautifulSoup, NavigableString, Tag

from ...normalize.names import clean_display_name, normalise_whitespace
from ...normalize.urls import canonical_url, mtmt_id, orcid_id, scholar_id

PARSER_VERSION = "tk/0.2.0"

PROFILE_PATH_RE = re.compile(r"^/kutato/(?!pdf/)([a-z0-9][a-z0-9-]*)/?$")
CV_PATH_RE = re.compile(r"^/kutato/pdf/(\d+)$")
LISTING_PATH_RE = re.compile(r"^/kutatok(?:/[a-z]{1,3})?/?$")
PHONE_RE = re.compile(r"(\+36|telefon|tel\.|^\(?\+?\d[\d ()/-]{6,}$)", re.I)
ROOM_RE = re.compile(r"(épület|szoba|building|room)", re.I)
DEGREE_RE = re.compile(
    r"^(phd|ph\.d\.|habil\.?|dsc|csc|d\.sc\.|c\.sc\.|mta doktora|dla)([ ,.]+(phd|habil\.?|dsc|csc|dla))*\.?$",
    re.I,
)
POSITION_RE = re.compile(
    r"(munkatárs|professzor|kutató|igazgató|asszisztens|ösztöndíjas|tanácsadó|"
    r"emeritus|emerita|gyakornok|doktorandusz|vezető|titkár|könyvtáros|referens)",
    re.I,
)
DEGREE_TOKEN_RE = re.compile(r"(phd|ph\.d\.|habil\.?|dsc\.?|csc\.?|d\.sc\.|c\.sc\.|dla\.?)", re.I)
BARE_CODE_RE = re.compile(r"^\((TK [^)]+)\)$")
INSTITUTE_CODE_RE = re.compile(r"\((TK [^)]+)\)\s*$")
UNIT_RE = re.compile(
    r"(osztály|kutatócsoport|csoport|intézet|központ|centrum|laboratórium|recens)", re.I
)
LEADER_LABEL_RE = re.compile(
    r"^(osztályvezető|vezető|igazgató|intézetigazgató|csoportvezető|kutatócsoport-vezető)\s*:?\s*$",
    re.I,
)
# Header labels on profiles ("Osztály: X", "Tudományos cím vagy fokozat: PhD").
UNIT_LABEL_RE = re.compile(r"^(osztály|kutatási osztály|egység|csoport|kutatócsoport)$", re.I)
DEGREE_LABEL_RE = re.compile(r"^(tudományos cím|tudományos fokozat|fokozat)", re.I)
CONTACT_LABEL_RE = re.compile(r"^(e-?mail|telefon|telefonszám|mobil|fax|épület|szoba|iroda)", re.I)
# Project lines ("Kutatásvezető: X", "Kutatás résztvevői: Y, Z").
PROJECT_LEAD_LABEL_RE = re.compile(
    r"^(projektvezető|témavezető|kutatás ?vezető|vezető kutató|szakmai vezető)", re.I
)
PARTICIPANTS_LABEL_RE = re.compile(
    r"^(résztvevők|résztvevő kutatók|kutatás résztvevői|projekt résztvevők|projekt résztvevői|"
    r"kutatók|munkatársak|kutatócsoport|kutatócsoport tagjai|a kutatás résztvevői|közreműködők)",
    re.I,
)
GRANT_LABEL_RE = re.compile(r"^(projektazonosító|azonosító|pályázati azonosító|projektszám)", re.I)
PERIOD_LABEL_RE = re.compile(r"^(időtartam|futamidő|projekt időtartama|időszak)", re.I)
FUNDER_LABEL_RE = re.compile(r"^(finanszírozó|támogató|forrás)", re.I)
DATE_SPAN_RE = re.compile(
    r"(\d{4})(?:[.\-/](\d{1,2})(?:[.\-/](\d{1,2}))?)?\.?\s*[-–—]\s*(?:(\d{4})(?:[.\-/](\d{1,2})(?:[.\-/](\d{1,2}))?)?)?"
)
# A line that is nothing but a period: "2022 - 2024", "2025.09.01. – 2029.08.31.", "2024-".
PERIOD_LINE_RE = re.compile(
    r"^\s*\d{4}(?:[.\-/]\d{1,2}(?:[.\-/]\d{1,2})?)?\.?\s*[-–—]\s*(?:\d{4}(?:[.\-/]\d{1,2}(?:[.\-/]\d{1,2})?)?\.?)?\s*$"
)
TRAILING_PERIOD_RE = re.compile(r"\s*\((\d{4})\s*[-–]\s*(\d{4})?\)\s*$")
LEADING_PERIOD_RE = re.compile(r"^\s*(\d{4})\s*[-–]\s*(\d{4}|jelenleg|folyamatban)?(?:\s*[-–—:]\s+|\s+)")
PROJECT_ROLE_RE = re.compile(
    r"^(kutatásvezető|projektvezető|témavezető|szakmai vezető|vezető kutató|társkutató|"
    r"alprojekt-?vezető|résztvevő|résztvevő kutató|kutató|munkatárs|tag|koordinátor|"
    r"(nyertes )?társpályázó|konzorciumi partner)$",
    re.I,
)
TRAILING_PAREN_RE = re.compile(r"\s*\(([^()]*)\)\s*$")
FUNDER_PREFIX_RE = re.compile(r"^(NKFIH|OTKA|NKFI|ERC|H2020|Horizon Europe|MTA|EFOP|GINOP|TKP)\b", re.I)
ORG_WORD_RE = re.compile(
    r"(kutatóközpont|intézet|egyetem|alapítvány|hun-ren|\bTK\b|\bELTE\b|\bMTA\b|osztály|kar\b|"
    r"centrum|universit|institute|centre|center)",
    re.I,
)
SENTENCE_LABEL_SPLIT_RE = re.compile(r"(?<=[a-záéíóöőúüű)])\.\s+(?=[A-ZÁÉÍÓÖŐÚÜŰ][\w -]{2,40}:)")
GRANT_IN_LABEL_RE = re.compile(r"^(NKFIH|OTKA|NKFI)\s+([A-Z]{0,4}\s?-?\d{5,6})$")
AFFIL_SUFFIX_RE = re.compile(r"\s*\(([^()]*)\)\s*$")

SECTION_AREAS = re.compile(r"^kutatási (terület|téma)", re.I)
SECTION_PROJECTS = re.compile(r"^(projektek|kutatások|futó projektek|kutatási projektek)", re.I)
SECTION_PUBS = re.compile(r"publikáció", re.I)
SECTION_BIO = re.compile(r"^(szakmai )?(életrajz|bemutatkozás|önéletrajz)", re.I)
SECTION_MEMBERS = re.compile(r"^(munkatársak|tagok|kutatók)", re.I)

SECTION_HEADINGS = ("h2", "h3", "h5", "h6")
BLOCK_TAGS = ("p", "li", "dd", "dt", "td", "h4", "h5", "h6", "b", "strong")
LINE_BLOCKS = ("p", "li", "dd", "dt", "td", "h4")


def soup_of(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "lxml")


def text_of(el: Tag) -> str:
    return _tidy(el.get_text(" "))


def _tidy(s: str) -> str:
    return normalise_whitespace(s).replace(" ,", ",").replace(" .", ".").replace("( ", "(").replace(" )", ")")


def _is_leaf_block(el: Tag) -> bool:
    return not any(isinstance(c, Tag) and c.name in ("p", "div", "li", "ul", "ol", "table") for c in el.children)


def _main(soup: BeautifulSoup) -> Tag:
    return soup.find("main") or soup.find(attrs={"role": "main"}) or soup.body or soup


def _title_el(main: Tag) -> Tag | None:
    """The page's own title: <h1> if present, else the first <h2> outside the breadcrumb."""
    return main.find("h1") or main.find("h2")


def _host(url: str) -> str:
    return (urlsplit(url).hostname or "").lower()


@dataclass
class Link:
    url: str  # canonical
    text: str


@dataclass
class Line:
    """One visual line of text (a leaf block, or a <br>-separated part of one) and its links."""
    text: str
    links: list[Link]
    tag: str | None = None


@dataclass
class ProjectMention:
    title: str
    url: str | None
    snippet: str
    period_from: str | None = None
    period_until: str | None = None
    role: str | None = None          # e.g. "Kutatásvezető" when the person is the lead
    stated_lead: str | None = None   # "(kutatásvezető: Kovách Imre)" -> someone else leads


@dataclass
class ProfilePage:
    name: str
    name_snippet: str
    titles: list[str] = field(default_factory=list)
    staff_category: str | None = None  # "Kutató" heading above the position
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
    unknown_labels: list[str] = field(default_factory=list)  # for parser QA, never stored


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
    url: str | None = None
    grant_id: str | None = None
    grant_snippet: str | None = None
    funder: str | None = None
    funder_snippet: str | None = None
    funder_labelled: bool = False  # True: "Finanszírozó: X"; False: bare line above the period
    start: str | None = None
    end: str | None = None
    period_snippet: str | None = None
    leads: list[Link] = field(default_factory=list)
    lead_snippets: dict[str, str] = field(default_factory=dict)  # url -> line
    unlinked_leads: list[tuple[str, str]] = field(default_factory=list)  # (name, line)
    participants: list[Link] = field(default_factory=list)
    unlinked_participants: list[tuple[str, str]] = field(default_factory=list)  # (name, role)
    description: str | None = None


# ---------------------------------------------------------------- helpers


def _link(a: Tag, base: str, aliases: dict[str, str]) -> Link | None:
    href = (a.get("href") or "").strip()
    if not href or href.startswith(("mailto:", "tel:", "#", "javascript:")):
        return None
    return Link(canonical_url(href, base=base, aliases=aliases), text_of(a))


def _links(el: Tag, base: str, aliases: dict[str, str]) -> list[Link]:
    return [lk for a in el.find_all("a", href=True) if (lk := _link(a, base, aliases))]


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


def _split_lines(block: Tag, base: str, aliases: dict[str, str]) -> list[Line]:
    """Split a leaf block on <br> into lines, keeping each line's links."""
    out: list[Line] = []
    texts: list[str] = []
    links: list[Link] = []

    def flush():
        t = _tidy(" ".join(texts))
        if t or links:
            out.append(Line(t, list(links), block.name))
        texts.clear()
        links.clear()

    def walk(node):
        for c in node.children:
            if isinstance(c, NavigableString):
                texts.append(str(c))
            elif isinstance(c, Tag):
                if c.name == "br":
                    flush()
                elif c.name in ("script", "style"):
                    continue
                else:
                    if c.name == "a" and (lk := _link(c, base, aliases)):
                        links.append(lk)
                    walk(c)

    walk(block)
    flush()
    return out


def _split_names(value: str) -> list[str]:
    """'Messing Vera, Ságvári Bence és Kiss Péter' -> names; drops affiliation suffixes."""
    out = []
    value = re.sub(r"\)\s+(?=[A-ZÁÉÍÓÖŐÚÜŰ])", "), ", value)  # "X (ELTE) Y Z" lacks a comma
    for part in re.split(r",|;| és | and ", value):
        n = AFFIL_SUFFIX_RE.sub("", part.strip()).strip(" .")
        n, _ = clean_display_name(n)
        if n and len(n) < 60 and not re.search(r"\d", n) and not ORG_WORD_RE.search(n) and len(n.split()) >= 2:
            out.append(n)
    return out


def _split_sentences(line: Line) -> list[Line]:
    """'Kutatásvezető: X. Résztvevő kutatók: Y, Z' -> one Line per label."""
    parts = SENTENCE_LABEL_SPLIT_RE.split(line.text)
    if len(parts) == 1:
        return [line]
    return [Line(p, [lk for lk in line.links if lk.text and lk.text in p], line.tag) for p in parts]


def _labelled_line(line: Line) -> tuple[str, str] | None:
    head = line.text[:60]
    if ":" not in head:
        return None
    label, _, value = line.text.partition(":")
    return label.strip(), value.strip()


def _section_headings(main: Tag, title: Tag | None) -> list[Tag]:
    return [h for h in main.find_all(SECTION_HEADINGS) if h is not title]


def _sections(main: Tag, title: Tag | None) -> dict[str, list[Tag]]:
    """heading text -> leaf blocks until the next section heading."""
    out: dict[str, list[Tag]] = {}
    heads = _section_headings(main, title)
    for h in heads:
        blocks = []
        scope = h.parent  # the section's own container; keeps the page footer out
        for el in h.find_all_next():
            if el in heads or el.name == "h1" or scope not in el.parents:
                break
            if el.name in ("p", "li", "dd") and _is_leaf_block(el) and text_of(el):
                blocks.append(el)
        out.setdefault(text_of(h), blocks)
    return out


def _header_region(title: Tag, stop: Tag | None, main: Tag):
    """Elements after the title, up to the first section heading (never past main)."""
    for el in title.next_elements:
        if el is stop or (main is not None and main not in el.parents):
            return
        yield el


def _header_lines(title: Tag, stop: Tag | None, main: Tag) -> list[tuple[str, Tag | None]]:
    """Text lines between the title and the first section heading.

    A line is the text of the nearest line-level block (li, p, h4, ...); a bare text
    node sitting directly in a <div> (how the position is rendered) is its own line.
    """
    lines: list[tuple[str, Tag | None]] = []
    seen: set[int] = set()
    for el in _header_region(title, stop, main):
        if not isinstance(el, NavigableString) or not str(el).strip():
            continue
        if el.find_parent(["script", "style"]) or title in el.parents:
            continue
        block = el.find_parent(LINE_BLOCKS)
        if block is not None:
            if id(block) in seen:
                continue
            seen.add(id(block))
            lines.append((text_of(block), block))
        else:
            lines.append((_tidy(str(el)), None))
    return lines


def _degrees(value: str) -> list[str]:
    """'PhD, habil.' -> ['PhD', 'habil.']; 'MTA doktora' and 'MTA levelező tagja' stay whole."""
    out = []
    for part in re.split(r",\s*|;\s*", value):
        part = part.strip()
        if not part:
            continue
        toks = part.split()
        if all(DEGREE_TOKEN_RE.fullmatch(t) for t in toks):
            out += [t.rstrip(".") if t.lower() != "habil." else t for t in toks]
        else:
            out.append(part.rstrip("."))
    return out


def _list_items(text: str) -> list[str]:
    """Split a short research-area paragraph into items."""
    return [i.strip(" .") for i in re.split(r"[;\n•]|,(?![^()]*\))", text) if i.strip(" .")]


def _is_prose(text: str) -> bool:
    return len(text) >= 200 or len(re.findall(r"[a-záéíóöőúüű]\. [A-ZÁÉÍÓÖŐÚÜŰ]", text)) >= 1


# ---------------------------------------------------------------- parsers


def parse_listing(html: str, base: str, aliases: dict[str, str]) -> ListingPage:
    main = _main(soup_of(html))
    people: dict[str, tuple[Link, str | None]] = {}
    next_pages: list[str] = []
    for a in main.find_all("a", href=True):
        link = _link(a, base, aliases)
        if link is None:
            continue
        path = urlsplit(link.url).path
        if PROFILE_PATH_RE.match(path):
            if not link.text:
                continue  # the photo link; the name link follows
            container = a.find_parent(["article", "li", "tr"]) or a.find_parent("div") or a.parent
            position = None
            for line in container.find_all(["p", "span", "div"]):
                t = text_of(line)
                if t and t != link.text and _is_leaf_block(line) and POSITION_RE.search(t) and ":" not in t:
                    position = t
                    break
            people.setdefault(link.url, (link, position))
        elif LISTING_PATH_RE.match(path) and _host(link.url) == _host(base):
            next_pages.append(link.url)
        elif urlsplit(link.url).path == urlsplit(base).path and "page=" in urlsplit(link.url).query:
            next_pages.append(link.url)
    return ListingPage(list(people.values()), sorted(set(next_pages)))


def parse_profile(html: str, base: str, aliases: dict[str, str], site_unit: str | None) -> ProfilePage:
    soup = soup_of(html)
    main = _main(soup)
    title = _title_el(main)
    if title is None:
        raise ValueError("profile without a title heading")
    raw_name = text_of(title)
    name, titles = clean_display_name(raw_name)
    page = ProfilePage(name=name, name_snippet=raw_name, titles=titles)
    heads = _section_headings(main, title)
    stop = heads[0] if heads else None

    # links in the header (MTMT, CV, ORCID, academia ...); icon links have no text
    for el in _header_region(title, stop, main):
        if not isinstance(el, Tag) or el.name != "a" or not el.get("href"):
            continue
        href = el["href"].strip()
        if href.startswith("mailto:"):
            addr = href[7:].split("?")[0]
            if "@" in addr:
                page.email_domain = addr.rsplit("@", 1)[1].lower()
            continue
        if href.startswith(("tel:", "#", "javascript:")):
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
        # linkedin, facebook and other social media are deliberately not recorded

    for line, block in _header_lines(title, stop, main):
        if not line:
            continue
        if block is not None and block.name == "h4":
            page.staff_category = line
            continue
        if block is not None and block.find("a", href=True) and ":" not in line:
            continue  # link-only lines ("Publikációk (MTMT)", "CV letöltése")
        if lab := _labelled_line(Line(line, [])):
            label, value = lab
            if CONTACT_LABEL_RE.match(label):
                continue  # contact details: never stored
            if UNIT_LABEL_RE.match(label):
                page.unit_lines += [v.strip() for v in value.split(";") if v.strip()]
            elif DEGREE_LABEL_RE.match(label):
                page.titles += _degrees(value)
            else:
                page.unknown_labels.append(label)
            continue
        if "@" in line or PHONE_RE.search(line) or ROOM_RE.search(line):
            continue
        if line.lower().startswith("cv letöltése"):
            continue
        if DEGREE_RE.match(line):
            page.titles += _degrees(line)
            continue
        if m := BARE_CODE_RE.match(line):
            # "<h4>Projektkutató</h4> (TK SZI)": the category is the only position stated
            page.institute_codes.append(m.group(1))
            if page.staff_category:
                page.positions.append(f"{page.staff_category} {line}")
            continue
        if POSITION_RE.search(line) and (INSTITUTE_CODE_RE.search(line) or len(line) < 80):
            page.positions.append(line)
            if m := INSTITUTE_CODE_RE.search(line):
                page.institute_codes.append(m.group(1))
            continue
        if UNIT_RE.search(line) and len(line) < 140:
            page.unit_lines.append(line)

    for heading, blocks in _sections(main, title).items():
        if SECTION_AREAS.match(heading):
            for b in blocks:
                t = text_of(b)
                if b.name != "li" and _is_prose(t):
                    # Several profiles put a narrative bio under this heading.
                    page.biography = page.biography or t
                    continue
                page.research_areas += [t] if b.name == "li" else _list_items(t)
        elif SECTION_BIO.match(heading):
            for b in blocks:
                if len(text_of(b)) >= 80:
                    page.biography = page.biography or text_of(b)
                    break
        elif SECTION_PROJECTS.match(heading):
            mentions = [_project_mention(line) for b in blocks
                        for line in _split_lines(b, base, aliases) if line.text]
            page.projects += _merge_period_headers(mentions)

    if page.biography is None:
        # first substantial paragraph directly under the title
        for p in main.find_all("p"):
            t = text_of(p)
            if len(t) < 80 or p.find_previous(SECTION_HEADINGS + ("h1",)) is not title:
                continue
            page.biography = t
            break
    if site_unit:
        # The site's own unit name repeated in the header is not a separate unit.
        key = normalise_whitespace(site_unit).lower()
        page.unit_lines = [u for u in page.unit_lines if normalise_whitespace(u).lower() != key]
    page.titles = list(dict.fromkeys(page.titles))
    return page


def _project_mention(line: Line) -> ProjectMention:
    """'<a>Title</a> (Kutatásvezető)', 'Title (kutatásvezető: X Y)', 'Title (2019-2023)'."""
    t = line.text
    link = line.links[0] if line.links else None
    title = link.text if link and link.text else t
    pm = ProjectMention(title=title, url=link.url if link else None, snippet=t)
    rest = t[len(link.text):] if link and t.startswith(link.text) else t
    if m := LEADING_PERIOD_RE.match(rest):
        # "2023-2027 – Title", "2024-jelenleg – Title"
        pm.period_from = m.group(1)
        pm.period_until = m.group(2) if m.group(2) and m.group(2).isdigit() else None
        rest = rest[m.end():]
    # peel trailing parentheticals: period, role, or "label: name"
    while m := TRAILING_PAREN_RE.search(rest):
        inner = m.group(1).strip()
        if pm_period := TRAILING_PERIOD_RE.search(m.group(0)):
            pm.period_from, pm.period_until = pm_period.group(1), pm_period.group(2)
        elif ":" in inner:
            label, _, who = inner.partition(":")
            if PROJECT_LEAD_LABEL_RE.match(label.strip()):
                pm.stated_lead = who.strip()
        elif PROJECT_ROLE_RE.match(inner):
            pm.role = inner
        else:
            break
        rest = rest[: m.start()]
    if not link:
        pm.title = rest.strip()
    return pm


KUTATAS_CIME_RE = re.compile(r"kutatás címe:\s*[„\"]?(.+?)[”\"]?(?:\.\s+[A-ZÁÉÍÓÖŐÚÜŰ][^.]{0,30}:|\.?$)", re.I)


def _merge_period_headers(mentions: list[ProjectMention]) -> list[ProjectMention]:
    """'<b>2022-2027 vezető kutató</b>' followed by a paragraph describing the project.

    The bold line carries the period and the person's role; the next paragraph names
    the project. They are one mention.
    """
    out: list[ProjectMention] = []
    pending: ProjectMention | None = None
    for pm in mentions:
        if pm.url is None and pm.period_from and PROJECT_ROLE_RE.match(pm.title.strip()):
            pending = pm
            continue
        if pending is not None:
            pm.period_from, pm.period_until = pending.period_from, pending.period_until
            pm.role = pm.role or pending.title.strip()
            pm.snippet = f"{pending.snippet} | {pm.snippet}"
            if pm.url is None:
                if m := KUTATAS_CIME_RE.search(pm.title):
                    pm.title = m.group(1).strip(" „”\"")
                elif len(pm.title) > 150 and ". " in pm.title:
                    pm.title = pm.title.split(". ", 1)[0]
            pending = None
        out.append(pm)
    if pending is not None:
        out.append(pending)
    return out


def parse_unit(html: str, base: str, aliases: dict[str, str]) -> UnitPage:
    main = _main(soup_of(html))
    title = _title_el(main)
    if title is None:
        raise ValueError("unit page without a title heading")
    leaders: list[tuple[Link, str]] = []
    leader_urls: set[str] = set()
    for el in main.find_all(["p", "li", "dd", "tr", "div"]):
        if not (_is_leaf_block(el) or el.name == "tr"):
            continue
        person: Link | None = None  # profile link opening this block ("<a>X</a><br>osztályvezető")
        for line in _split_lines(el, base, aliases):
            lab = _labelled_line(line)
            if lab and LEADER_LABEL_RE.match(lab[0]):
                for link in line.links:
                    if is_profile_url(link.url) and link.url not in leader_urls:
                        leaders.append((link, lab[0]))
                        leader_urls.add(link.url)
            elif person is not None and not line.links and LEADER_LABEL_RE.match(line.text):
                if person.url not in leader_urls:
                    leaders.append((person, line.text[:1].upper() + line.text[1:]))
                    leader_urls.add(person.url)
            profile_links = [lk for lk in line.links if is_profile_url(lk.url) and lk.text]
            if profile_links:
                person = profile_links[0]
    members = []
    seen = set()
    for link in _links(main, base, aliases):
        if is_profile_url(link.url) and link.text and link.url not in seen:
            seen.add(link.url)
            if link.url not in leader_urls:
                members.append(link)
    description = None
    for p in main.find_all("p"):
        t = text_of(p)
        if len(t) >= 60 and not p.find("a"):
            description = t
            break
    return UnitPage(text_of(title), leaders, members, description)


def _apply_project_lines(page: ProjectPage, lines: list[Line]) -> None:
    """Fill project fields from labelled lines and the bare funder / period lines."""
    pending_label: tuple[str, str] | None = None  # bare line seen before the period line
    for line in [x for ln in lines for x in _split_sentences(ln)]:
        t = line.text
        if not t and not line.links:
            continue
        lab = _labelled_line(line)
        if lab is None:
            if PERIOD_LINE_RE.match(t):
                if page.start is None:
                    page.start, page.end = parse_period(t)
                    page.period_snippet = t
                if pending_label and page.funder is None:
                    page.funder, page.funder_snippet = pending_label
                pending_label = None
            elif len(t) <= 60 and not line.links and page.start is None:
                pending_label = (t, t)
            continue
        label, value = lab
        if GRANT_LABEL_RE.match(label):
            page.grant_id, page.grant_snippet = value, t
            if m := FUNDER_PREFIX_RE.match(value):
                page.funder, page.funder_snippet = m.group(1).upper(), t
                page.funder_labelled = True
        elif PERIOD_LABEL_RE.match(label):
            page.start, page.end = parse_period(value)
            page.period_snippet = t
        elif FUNDER_LABEL_RE.match(label):
            page.funder, page.funder_snippet, page.funder_labelled = value, t, True
        elif PROJECT_LEAD_LABEL_RE.match(label):
            linked = [lk for lk in line.links if is_profile_url(lk.url)]
            for lk in linked:
                if lk.url not in page.lead_snippets:
                    page.leads.append(lk)
                    page.lead_snippets[lk.url] = t
            for n in _split_names(value):
                if not any(n == lk.text for lk in linked) and n not in {x for x, _ in page.unlinked_leads}:
                    page.unlinked_leads.append((n, t))
        elif PARTICIPANTS_LABEL_RE.match(label):
            linked = [lk for lk in line.links if is_profile_url(lk.url)]
            page.participants += [lk for lk in linked if lk.url not in {p.url for p in page.participants}]
            # "Külső szakértő: X Y" inside the value introduces a role
            for chunk in re.split(r";", value):
                role = label
                if ":" in chunk:
                    before, _, chunk = chunk.partition(":")
                    names_before, _, role = before.rpartition(",")
                    for n in _split_names(names_before):  # "X, Y, külső szakértő: Z"
                        if not any(n == lk.text for lk in linked) and (n, label) not in page.unlinked_participants:
                            page.unlinked_participants.append((n, label))
                for n in _split_names(chunk):
                    if not any(n == lk.text for lk in linked) and (n, role.strip()) not in page.unlinked_participants:
                        page.unlinked_participants.append((n, role.strip()))
    if pending_label and page.funder is None and page.start is not None:
        page.funder, page.funder_snippet = pending_label
    if page.funder and page.grant_id is None and (m := GRANT_IN_LABEL_RE.match(page.funder)):
        # "NKFIH K147304": the funder line carries the grant number
        page.grant_id, page.grant_snippet = page.funder, page.funder_snippet
        page.funder = m.group(1).upper()


def parse_project(html: str, base: str, aliases: dict[str, str]) -> ProjectPage:
    main = _main(soup_of(html))
    title = _title_el(main)
    if title is None:
        raise ValueError("project page without a title heading")
    page = ProjectPage(title=text_of(title), url=canonical_url(base, aliases=aliases))
    lines: list[Line] = []
    for el in main.find_all(["p", "li", "dd", "tr"]):
        if (_is_leaf_block(el) or el.name == "tr") and el.find_previous(["h1", "h2"]) is not None:
            lines += _split_lines(el, base, aliases)
    _apply_project_lines(page, lines)
    for p in main.find_all("p"):
        t = text_of(p)
        if len(t) >= 80 and ":" not in t[:40]:
            page.description = t
            break
    return page


def parse_project_listing(html: str, base: str, aliases: dict[str, str]) -> list[ProjectPage]:
    """Category listing (/kategoria/futo-kutatasok): one <article> per project.

    Each article carries the project's title link and its lead lines (funder, period,
    lead, participants), which are often richer than the project page itself.
    """
    main = _main(soup_of(html))
    out: list[ProjectPage] = []
    for art in main.find_all("article"):
        head = art.find(["h1", "h2", "h3", "h4"])
        a = head.find("a", href=True) if head else None
        link = _link(a, base, aliases) if a else None
        if link is None or _host(link.url) != _host(canonical_url(base, aliases=aliases)):
            continue
        page = ProjectPage(title=link.text, url=link.url)
        lines: list[Line] = []
        for el in art.find_all(["p", "li"]):
            if _is_leaf_block(el):
                lines += _split_lines(el, base, aliases)
        _apply_project_lines(page, lines)
        out.append(page)
    return out
