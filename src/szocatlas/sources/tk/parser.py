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

PARSER_VERSION = "tk/0.6.0"

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
# Short or misspelt forms of the participants label ("Résztvevő", "Részvevők", #16). Only profile links count on
# such a line: one SZI page lists countries and groups under "Részvevők", so its text is never read as names.
PARTICIPANTS_LINKS_ONLY_RE = re.compile(r"^(részt?vevő|részt?vevők)\s*$", re.I)
GRANT_LABEL_RE = re.compile(r"^(projektazonosító|azonosító|pályázati azonosító|projektszám)", re.I)
# "Időtartam", and the longer labels the KI / PTI / RECENS project pages use ("Kutatás időtartama",
# "A kutatás futamideje", "Ösztöndíj időtartama", "Pályázat időtartama")
PERIOD_LABEL_RE = re.compile(
    r"^(((a |az )?(kutatás|projekt|pályázat|ösztöndíj|program) )?(időtartam|futamid|időszak))", re.I)
# "Finanszírozó", "Támogató", and the KI / PTI template label "Támogatási forrás" (also "...források",
# "Támogatás forrása", "Projektfinanszírozás"). A bare "Forrás" is a data source ("Forrás: KSH adatok") and a
# "Forrásfeltárás: ..." line is an activity: neither is a funder, so there is no prefix match on "forrás" (#16).
FUNDER_LABEL_RE = re.compile(
    r"^(finanszírozó|támogató|támogatási forrás(ok)?\s*$|támogatás forrása\s*$|projektfinanszírozás\s*$)", re.I)
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
TRAILING_LEAD_RE = re.compile(
    r"[,;–-]\s*(?:a\s+)?(kutatás vezetője|kutatásvezető|projektvezető|témavezető)\s*:\s*([^():]+)$", re.I
)
TRAILING_PAREN_RE = re.compile(r"\s*\(([^()]*)\)\s*$")
FUNDER_PREFIX_RE = re.compile(r"^(NKFIH|OTKA|NKFI|ERC|H2020|Horizon Europe|MTA|EFOP|GINOP|TKP)\b", re.I)
ORG_WORD_RE = re.compile(
    r"(kutatóközpont|intézet|egyetem|alapítvány|hun-ren|\bTK\b|\bELTE\b|\bMTA\b|osztály|kar\b|"
    r"centrum|universit|institute|centre|center)",
    re.I,
)
SENTENCE_LABEL_SPLIT_RE = re.compile(r"(?<=[a-záéíóöőúüű)])\.\s+(?=[A-ZÁÉÍÓÖŐÚÜŰ][\w -]{2,40}:)")
PROSE_LINE_LEN = 150  # a longer line is a paragraph: the header block of a project page is over
NUMBERED_HEADING_RE = re.compile(r"^\d+(\.\d+)*\.?\s")
GRANT_IN_LABEL_RE = re.compile(r"^(NKFIH|OTKA|NKFI)\s+([A-Z]{0,4}\s?-?\d{5,6})$")
AFFIL_SUFFIX_RE = re.compile(r"\s*\(([^()]*)\)\s*$")

# Heading sections (#31): the legacy SZI project template writes a field's label as a heading and its value in the
# blocks that follow ("<h3>Résztvevők</h3><p>A<br>B</p>"), not as a "Label: value" line.
HEADING_TAGS = ("h2", "h3", "h4", "h5", "h6")
SECTION_BLOCK_TAGS = ("p", "div", "ul", "ol", "li", "dl", "dt", "dd", "blockquote", "section", "article", "center")
SECTION_STOP_TAGS = ("table", "hr", "form", "figure", "iframe", "svg")
SECTION_SKIP_TAGS = ("script", "style", "noscript")
DESCRIPTION_HEADING_RE = re.compile(r"^a kutatás$", re.I)
# What may not appear in a line read as names: a label colon, a link, an e-mail address, markup debris.
SECTION_NOT_NAMES_RE = re.compile(r"[:@/{}<>|]|https?|www\.", re.I)
# A person's name has two to five tokens; a token starts with a capital letter (a particle may not) and is no acronym.
NAME_PARTICLES = frozenset({"von", "van", "de", "der", "den", "di", "da", "del", "la", "le", "du", "zu", "zur", "af",
                            "ben", "bin", "al", "el", "dos", "das"})
NAME_TOKEN_RE = re.compile(r"^[^\W\d_](?:[^\W\d_]|['’.\-])*$")
# Words that make a capitalised phrase an organisation, a programme or a place, not a person.
NON_PERSON_RE = re.compile(
    r"organi[sz]|international|nemzetközi|nemzeti|national|european|európai|federal|association|society|council|"
    r"ministr|minisztérium|department|facult|school|college|academy|akadémia|egyesület|egyesült|társaság|hivatal|"
    r"főiskola|tanszék|központ|szövetség|bizottság|kiadó|fórum|forum|research|foundation|network|hálózat|"
    r"királyság|kingdom|britain|köztársaság|republic|államok|states|\bunió\b|\bunion\b|\bkft\b|\bzrt\b|\bltd\b|"
    r"\bgmbh\b|université|universität|universidad|universidade|università|hochschule|laborat|institut",
    re.I,
)

# Lines in a profile's "Projektek" section that are metadata about a project, never a
# project title (#8). High precision only: a line is rejected when the whole line is a
# section label, a column header, a role, a period, a bare grant id or a bare funder name.
# Anything that might be a project, programme, network or infrastructure is kept (#9).
PROJECT_SECTION_LABEL_RE = re.compile(
    r"^((jelenleg |korábbi |futó |aktuális |lezárt |lezárult |befejezett |folyamatban lévő )*"
    r"(kutatási )?(projekt(ek)?|kutatás(ok)?)|cím ?/ ?téma|intézmény|időtartam|"
    r"szerep|finanszírozó|támogató|résztvevők|résztvevő kutatók|(a )?kutatás résztvevői|projekt résztvevői)\s*:?$",
    re.I,
)
_ROLE = (
    r"(kutatásvezető|projektvezető|témavezető|szakmai vezető|vezető kutató|társkutató|"
    r"alprojekt-?vezető|wp[ -]?vezető|résztvevő( kutató)?|(szenior |senior |junior )?kutató|munkatárs|"
    r"tag|(projekt ?)?koordinátor|(nyertes )?társpályázó|konzorciumi partner|national coordinator|"
    r"(fejezet)?szerző|principal investigator|researcher|team member)"
)
ROLE_LINE_RE = re.compile(rf"^{_ROLE}(\s*[,/]\s*{_ROLE})*\.?$", re.I)
_FUNDER = r"(NKFIH|NKFI|OTKA|ERC|H2020|Horizon 2020|Horizon Europe|EFOP|GINOP|TÁMOP|TKP|KEHOP|VEKOP)"
# "NKFI kutatás – kutatásvezető", "K–OTKA –résztvevő kutató": a funder plus the person's role
FUNDER_ROLE_LINE_RE = re.compile(rf"^(K\s*[–-]\s*)?{_FUNDER}\b[^–—-]{{0,25}}?\s*[–—-]+\s*(?P<role>{_ROLE})$", re.I)
# "NKFIH. K147329", "H2020. G-ID: 785125", "TÁMOP 5.4.1-12", "119603 jelű"
GRANT_LINE_RE = re.compile(
    rf"^({_FUNDER}[\s.:]*(G-ID:?\s*)?([A-Z]{{1,4}}\s?-?)?(\d{{4,7}}|\d+(\.\d+)+(-\d+)?)|"
    r"(K\s?)?\d{5,6}\s+jelű)\.?$",
    re.I,
)
FUNDER_ONLY_LINE_RE = re.compile(
    r"^(Magyar Tudományos Akadémia|MTA|NKFIH|NKFI|OTKA|Európai Bizottság|European Commission|ERC|"
    r"H2020|Horizon 2020|Horizon Europe)\.?$",
    re.I,
)
URL_TEXT_RE = re.compile(r"^(https?://|www\.)\S+$", re.I)
TRAILING_URL_RE = re.compile(r"\s*(https?://|www\.)\S+\s*$", re.I)

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
    url: str  # canonical (host aliases applied)
    text: str
    stated_url: str = ""  # as written on the page (absolute, aliases not applied): alias evidence for #5


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
    grant_id: str | None = None      # from a grant cell in the same table row
    stated_url: str | None = None    # the link as written (host aliases not applied): alias evidence (#16)


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
    rejected_project_lines: list[str] = field(default_factory=list)  # metadata lines (#8), parser QA


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
class HeadingSection:
    """What one lead / participants heading of a project page offered (#31): the names it states, and what was left out."""
    heading: str                 # as stated, e.g. "Résztvevők (MTA SZKI)"
    label: str                   # the heading without its trailing qualifier, e.g. "Résztvevők"
    tag: str                     # "h3"
    kind: str                    # "lead" | "participants"
    names: list[tuple[str, str]] = field(default_factory=list)   # (name, the line it was read from)
    links: list[tuple[Link, str]] = field(default_factory=list)  # (profile link, the line it was read from)
    rejected: list[tuple[str, str]] = field(default_factory=list)  # (line, why it was not read): parser QA only
    placeholders: int = 0        # "..." lines: the page states the heading and leaves the value out
    blocks: int = 0              # blocks before the section ended
    end: str = "end"             # why the section ended: "heading", "end", "non-name block", "table"

    def evidence(self, key: str) -> str:
        """The heading and the line a name (or a profile link URL) was read from: the claim's snippet."""
        for name, line in self.names:
            if name == key:
                return f"{self.heading}: {line}"
        for link, line in self.links:
            if link.url == key:
                return f"{self.heading}: {line}"
        return self.heading

    @property
    def read(self) -> bool:
        return bool(self.names or self.links)


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
    description_heading: str | None = None  # the heading the description was read under ("A kutatás"), else None
    unmapped_labels: list[str] = field(default_factory=list)  # "Label: value" lines no field took (parser QA, #12)
    sections: list[HeadingSection] = field(default_factory=list)  # lead / participants headings found (#31)
    # ("lead" | "participant", name or profile URL) -> the heading section that supplied it; absent when a label
    # line did. The adapter turns this into the claim's locator and snippet.
    heading_origin: dict[tuple[str, str], HeadingSection] = field(default_factory=dict)


# ---------------------------------------------------------------- helpers


def _link(a: Tag, base: str, aliases: dict[str, str]) -> Link | None:
    href = (a.get("href") or "").strip()
    if not href or href.startswith(("mailto:", "tel:", "#", "javascript:")):
        return None
    return Link(canonical_url(href, base=base, aliases=aliases), text_of(a), canonical_url(href, base=base))


def _links(el: Tag, base: str, aliases: dict[str, str]) -> list[Link]:
    out: list[Link] = []
    for a in el.find_all("a", href=True):
        if (lk := _link(a, base, aliases)) is None:
            continue
        prev = a.find_previous_sibling("a")
        adjacent = prev is not None and out and not normalise_whitespace(
            "".join(str(x) for x in _between(prev, a)))
        if adjacent and out[-1].url == lk.url:
            out[-1] = Link(lk.url, out[-1].text + lk.text, lk.stated_url)  # one name split across two links
        elif adjacent and len(out[-1].text) <= 2 and lk.text[:1].islower():
            # "<a href=A>S</a><a href=B>zikra Dorottya</a>": a stray initial linked to the
            # wrong profile; the name belongs to the second link only
            out[-1] = Link(lk.url, out[-1].text + lk.text, lk.stated_url)
        else:
            out.append(lk)
    return out


def _between(a: Tag, b: Tag) -> list:
    out = []
    for sib in a.next_siblings:
        if sib is b:
            break
        out.append(sib.get_text() if isinstance(sib, Tag) else sib)
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


# Hungarian month names and the abbreviations the sites use ("2022. nov. 1.", "2019. október")
MONTHS = {
    "jan": 1, "január": 1, "feb": 2, "február": 2, "márc": 3, "március": 3, "ápr": 4, "április": 4,
    "máj": 5, "május": 5, "jún": 6, "június": 6, "júl": 7, "július": 7, "aug": 8, "augusztus": 8,
    "szept": 9, "szeptember": 9, "sze": 9, "okt": 10, "október": 10, "nov": 11, "november": 11,
    "dec": 12, "december": 12,
}
_MONTH_WORD = r"([a-záéíóöőúüű]+)\.?"
# a start such as "2022. nov. 1." or "2019. október"; an end that is a month date or a bare year, or nothing
MONTH_SPAN_RE = re.compile(
    r"(\d{4})\.?\s+" + _MONTH_WORD + r"(?:\s+(\d{1,2})\.?)?\s*[-–—]\s*"
    r"(?:(\d{4})\.?(?:\s+" + _MONTH_WORD + r"(?:\s+(\d{1,2})\.?)?)?)?",
    re.I,
)


def parse_period(text: str) -> tuple[str | None, str | None]:
    m = DATE_SPAN_RE.search(text)
    if m:
        return _partial_date(m.group(1), m.group(2), m.group(3)), _partial_date(m.group(4), m.group(5), m.group(6))
    # "2022. nov. 1. – 2026. okt. 1.", "2019. október - 2020. június". Every month word must be a real month: a
    # period is never guessed from a sentence, and an end that cannot be read is not read as "still open".
    m = MONTH_SPAN_RE.search(text)
    if not m:
        return None, None
    y1, w1, d1, y2, w2, d2 = m.groups()
    if w1.lower() not in MONTHS:
        return None, None
    start = _partial_date(y1, str(MONTHS[w1.lower()]), d1)
    if not y2:
        return start, None
    if not w2:
        return start, y2
    if w2.lower() not in MONTHS:
        return None, None
    return start, _partial_date(y2, str(MONTHS[w2.lower()]), d2)


def _split_lines(block: Tag, base: str, aliases: dict[str, str]) -> list[Line]:
    """Split a leaf block on <br> into lines, keeping each line's links."""
    return _lines_of(block.children, block.name, base, aliases)


def _lines_of(nodes, tag: str | None, base: str, aliases: dict[str, str], *, plain: bool = False) -> list[Line]:
    """<br>-separated lines of a run of sibling nodes (a block's children, or the bare text between two blocks).

    ``plain``: leave out comments and other special strings (the Word conditional comments some pages carry)."""
    out: list[Line] = []
    texts: list[str] = []
    links: list[Link] = []

    def flush():
        t = _tidy(" ".join(texts))
        if t or links:
            out.append(Line(t, list(links), tag))
        texts.clear()
        links.clear()

    def handle(c):
        if isinstance(c, NavigableString):
            if plain and type(c) is not NavigableString:
                return
            texts.append(str(c))
        elif isinstance(c, Tag):
            if c.name == "br":
                flush()
            elif c.name in ("script", "style"):
                return
            else:
                if c.name == "a" and (lk := _link(c, base, aliases)):
                    prev = c.find_previous_sibling()
                    if (links and links[-1].url == lk.url and prev is not None and prev.name == "a"
                            and c.previous_sibling is prev):
                        # "<a>S</a><a>zikra Dorottya</a>": one name split across two links
                        links[-1] = Link(lk.url, links[-1].text + lk.text, lk.stated_url)
                    elif (links and len(links[-1].text) <= 2 and lk.text[:1].islower()
                          and prev is not None and prev.name == "a" and c.previous_sibling is prev):
                        # "<a href=/en/…>D</a><a href=/…>onáció alapú …</a>": a stray initial
                        # linked elsewhere; the text belongs to the second link
                        links[-1] = Link(lk.url, links[-1].text + lk.text, lk.stated_url)
                    else:
                        links.append(lk)
                for child in c.children:
                    handle(child)

    for c in nodes:
        handle(c)
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


def _split_lead_value(value: str) -> tuple[str, list[tuple[str, str]]]:
    """'A; résztvevő kutató: B' -> ('A', [('résztvevő kutató', 'B')]): a ';' chunk with a short "role:" head is no lead."""
    lead, others = [], []
    for chunk in value.split(";"):
        role, sep, rest = chunk.partition(":")
        if sep and rest.strip() and 0 < len(role.split()) <= 3:
            others.append((role.strip(), rest.strip()))
        else:
            lead.append(chunk)
    return "; ".join(lead), others


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
            page.projects += _profile_projects(blocks, base, aliases, page.rejected_project_lines)

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
    # a link to a researcher profile names a person (usually the lead), not the project
    link = next((lk for lk in line.links
                 if not is_profile_url(lk.url) and not URL_TEXT_RE.match(lk.text.strip())), None)
    stated = None
    if m := TRAILING_LEAD_RE.search(t):
        stated, t = m.group(2).strip(), t[: m.start()].strip()
    title = link.text if link and link.text else t
    pm = ProjectMention(title=title, url=link.url if link else None, snippet=line.text, stated_lead=stated,
                        stated_url=link.stated_url if link else None)
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
        pm.title = TRAILING_URL_RE.sub("", rest).strip()  # "… TINLAB https://tinlab.hu/"
    return pm


def is_project_metadata(text: str) -> bool:
    """True when the whole line is a label, role, period, grant id or funder name (#8)."""
    t = text.strip().strip("„”\"").strip()
    return (not t or bool(PROJECT_SECTION_LABEL_RE.match(t) or ROLE_LINE_RE.match(t)
                          or PERIOD_LINE_RE.match(t) or re.fullmatch(r"\d{4}\.?", t)
                          or GRANT_LINE_RE.match(t) or FUNDER_ROLE_LINE_RE.match(t)
                          or FUNDER_ONLY_LINE_RE.match(t)))


def metadata_kind(text: str) -> str:
    """What kind of metadata a rejected project-section line is (#7: kept as an unattached claim)."""
    t = text.strip().strip("„”\"").strip()
    if " | " in t and not is_project_metadata(t):
        return "table_row"  # a row with no title cell, usually the header
    for kind, rx in (("section_label", PROJECT_SECTION_LABEL_RE), ("role", ROLE_LINE_RE),
                     ("period", PERIOD_LINE_RE), ("grant", GRANT_LINE_RE), ("funder_role", FUNDER_ROLE_LINE_RE),
                     ("funder", FUNDER_ONLY_LINE_RE)):
        if rx.match(t):
            return kind
    if re.fullmatch(r"\d{4}\.?", t):
        return "period"
    if (m := LEADING_PERIOD_RE.match(t)) and PROJECT_ROLE_RE.match(t[m.end():].strip()):
        return "period_role"  # "2022-2027 vezető kutató" with no project line after it (#45)
    return "table_row" if " | " in t else "other"


def _profile_projects(blocks: list[Tag], base: str, aliases: dict[str, str],
                      rejected: list[str]) -> list[ProjectMention]:
    """Project mentions in a profile's "Projektek" section.

    A table row is one project: the first cell that is not metadata is the title, and
    period / grant / role cells of the same row qualify it (observed column orders differ:
    title-institution-period, period-title, grant-role-title). Outside tables, metadata
    lines are dropped, not attached, because their direction is not determinable from
    the markup (role lines follow the title on some profiles, precede it on others).
    """
    out: list[ProjectMention] = []
    rows: dict[int, list[Tag]] = {}
    order: list[tuple[str, object]] = []
    for b in blocks:
        tr = b.find_parent("tr")
        if tr is None:
            order.append(("line", b))
        else:
            if id(tr) not in rows:
                rows[id(tr)] = []
                order.append(("row", id(tr)))
            rows[id(tr)].append(b)
    flat: list[ProjectMention] = []

    def flush_flat():
        out.extend(_merge_period_headers(flat, rejected))
        flat.clear()

    for kind, item in order:
        if kind == "line":
            for line in _split_lines(item, base, aliases):
                if not line.text:
                    continue
                pm = _project_mention(line)
                if (not pm.title.strip() or is_project_metadata(pm.title)) and not (
                        pm.period_from and PROJECT_ROLE_RE.match(pm.title.strip())):
                    rejected.append(line.text)  # "Korábbi projektek:", "Kutatásvezető", "2022-2024"
                    continue
                flat.append(pm)
            continue
        flush_flat()
        cells = [ln for b in rows[item] for ln in _split_lines(b, base, aliases) if ln.text]
        if pm := _table_row_mention(cells):
            out.append(pm)
        else:
            rejected.append(" | ".join(c.text for c in cells))
    flush_flat()
    return out


def _table_row_mention(cells: list[Line]) -> ProjectMention | None:
    title_cell = next((c for c in cells if not is_project_metadata(c.text)), None)
    if title_cell is None:
        return None  # header row ("Cím / téma | Intézmény | Időtartam") or an empty row
    pm = _project_mention(title_cell)
    if not pm.title.strip():
        return None
    pm.snippet = " | ".join(c.text for c in cells)
    for c in cells:
        if c is title_cell:
            continue
        t = c.text.strip()
        if PERIOD_LINE_RE.match(t) or re.fullmatch(r"\d{4}\.?", t):
            if not (pm.period_from or pm.period_until):
                pm.period_from, pm.period_until = (t[:4], None) if re.fullmatch(r"\d{4}\.?", t) else parse_period(t)
        elif GRANT_LINE_RE.match(t):
            pm.grant_id = pm.grant_id or t
        elif ROLE_LINE_RE.match(t):
            pm.role = pm.role or t
        elif m := FUNDER_ROLE_LINE_RE.match(t):
            pm.role = pm.role or m.group("role").strip()
        elif m := TRAILING_PAREN_RE.search(t):
            # "Magyar Közigazgatási Intézet (kutatásvezető)": the institution cell states the role
            if PROJECT_ROLE_RE.match(m.group(1).strip()):
                pm.role = pm.role or m.group(1).strip()
    return pm


KUTATAS_CIME_RE = re.compile(r"kutatás címe:\s*[„\"]?(.+?)[”\"]?(?:\.\s+[A-ZÁÉÍÓÖŐÚÜŰ][^.]{0,30}:|\.?$)", re.I)


def _merge_period_headers(mentions: list[ProjectMention], rejected: list[str]) -> list[ProjectMention]:
    """'<b>2022-2027 vezető kutató</b>' followed by a paragraph describing the project.

    The bold line carries the period and the person's role; the next paragraph names
    the project. They are one mention. A header that no project line follows (the run of
    lines ends, or another header comes first) names no project: it is kept in ``rejected``
    as unattached metadata, never as a project titled with the role (#45).
    """
    out: list[ProjectMention] = []
    pending: ProjectMention | None = None
    for pm in mentions:
        if pm.url is None and pm.period_from and PROJECT_ROLE_RE.match(pm.title.strip()):
            if pending is not None:
                rejected.append(pending.snippet)
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
        rejected.append(pending.snippet)
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


def _is_label_head(label: str) -> bool:
    """Short enough to be a field label; a longer head before a colon is the start of a sentence (#16)."""
    return 0 < len(label) <= 48 and len(label.split()) <= 6


def _looks_like_label(label: str) -> bool:
    """A short "Label:" head, not the opening of a sentence (parser QA only, never a field)."""
    return 0 < len(label) <= 40 and len(label.split()) <= 5 and label[:1].isupper() and not label.endswith(".")


def _apply_project_lines(page: ProjectPage, lines: list[Line]) -> None:
    """Fill project fields from labelled lines and the bare funder / period lines."""
    # Bare lines, in the page's header block only: a short line above a bare period line is the funding scheme as
    # the site labels it ("NKFIH ADVANCED" / "2022 - 2024"), and the period line is the project's period. Once the
    # page turns to prose, a short heading or a bare year range is not a funder or a project period (a numbered
    # heading "3.1. Levéltári források" above "1918-1945" is a source period, #16). Labelled lines count anywhere.
    in_header = True
    pending_label: tuple[str, str] | None = None
    for line in [x for ln in lines for x in _split_sentences(ln)]:
        t = line.text
        if not t and not line.links:
            continue
        if len(t) > PROSE_LINE_LEN:
            in_header = False
        lab = _labelled_line(line)
        if lab is None:
            if not in_header:
                continue
            if PERIOD_LINE_RE.match(t):
                if page.start is None:
                    page.start, page.end = parse_period(t)
                    page.period_snippet = t
                if pending_label and page.funder is None:
                    page.funder, page.funder_snippet = pending_label
                pending_label = None
            elif len(t) <= 60 and not line.links and page.start is None and not NUMBERED_HEADING_RE.match(t):
                pending_label = (t, t)
            continue
        label, value = lab
        if not _is_label_head(label):
            continue  # "Kutatócsoportunk a következő alapkérdésre keresi a választ: ..." is prose, not a field
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
            # "Kutatásvezető: A; résztvevő kutató: B": the chunk with its own role label is not a lead (#16)
            lead_value, role_chunks = _split_lead_value(value)
            role_text = " ".join(rest for _, rest in role_chunks)
            linked = [lk for lk in line.links if is_profile_url(lk.url)]
            other = [lk for lk in linked if lk.text in role_text and lk.text not in lead_value]
            for lk in linked:
                if lk in other:
                    if lk.url not in {x.url for x in page.participants}:
                        page.participants.append(lk)
                elif lk.url not in page.lead_snippets:
                    page.leads.append(lk)
                    page.lead_snippets[lk.url] = t
            for n in _split_names(lead_value):
                if not any(n == lk.text for lk in linked) and n not in {x for x, _ in page.unlinked_leads}:
                    page.unlinked_leads.append((n, t))
            for role, rest in role_chunks:
                for n in _split_names(rest):
                    if not any(n == lk.text for lk in linked) and (n, role) not in page.unlinked_participants:
                        page.unlinked_participants.append((n, role))
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
        elif PARTICIPANTS_LINKS_ONLY_RE.match(label):
            linked = [lk for lk in line.links if is_profile_url(lk.url)]
            page.participants += [lk for lk in linked if lk.url not in {p.url for p in page.participants}]
        elif _looks_like_label(label):
            page.unmapped_labels.append(label)
    if page.funder and page.grant_id is None and (m := GRANT_IN_LABEL_RE.match(page.funder)):
        # "NKFIH K147304": the funder line carries the grant number
        page.grant_id, page.grant_snippet = page.funder, page.funder_snippet
        page.funder = m.group(1).upper()


# ---------------------------------------------------------------- heading sections (#31)
#
# A heading is a label only when its whole text is one of the project-line labels (lead, participants), with at most a
# trailing "(MTA SZKI)" qualifier. Its section is what follows it inside the heading's own parent, up to the next
# heading of any level: nothing outside that section is read, and nothing in it by proximity. A heading has no ":" to
# anchor its value, so the lines are held to a stricter test than a "Label: value" line (_name_line): a country, an
# organisation, a sentence or a "10 partners" line under a heading is never a person.


def _heading_label(h: Tag) -> tuple[str, str, str] | None:
    """(heading as stated, label without its qualifier, "lead" | "participants"), or None for any other heading."""
    stated = text_of(h).strip(" : ")
    label = AFFIL_SUFFIX_RE.sub("", stated).strip(" :")
    if not label or len(label.split()) > 3:
        return None
    for kind, patterns in (("lead", (PROJECT_LEAD_LABEL_RE,)),
                           ("participants", (PARTICIPANTS_LABEL_RE, PARTICIPANTS_LINKS_ONLY_RE))):
        for rx in patterns:
            m = rx.match(label)
            if m and len(label) - m.end() <= 2:  # "Projektvezetők" is a lead label, "Kutatóközpont" is not
                return stated, label, kind
    return None


def _section_blocks(h: Tag, base: str, aliases: dict[str, str]) -> tuple[list[list[Line]], str]:
    """The lines after a heading inside its own parent, grouped by block, up to the next heading of any level.

    A block is a leaf <p>/<div>/<li>..., or a run of bare text and <br> between two blocks. Returns (blocks, end)."""
    blocks: list[list[Line]] = []
    run: list = []  # inline nodes directly between blocks: bare text, <br>, <a>, <b> ...

    def flush() -> None:
        if run:
            if lines := _lines_of(run, h.parent.name, base, aliases, plain=True):
                blocks.append(lines)
            run.clear()

    def take(nodes) -> str | None:
        for c in nodes:
            if isinstance(c, NavigableString):
                if type(c) is NavigableString:  # not a comment or doctype
                    run.append(c)
                continue
            if not isinstance(c, Tag) or c.name in SECTION_SKIP_TAGS:
                continue
            if c.name in HEADING_TAGS or c.find(HEADING_TAGS):
                flush()
                return "heading"
            if c.name in SECTION_STOP_TAGS or c.find(SECTION_STOP_TAGS):
                flush()
                return "table"
            if c.name in SECTION_BLOCK_TAGS:
                flush()
                if _is_leaf_block(c):
                    if lines := _lines_of(c.children, c.name, base, aliases, plain=True):
                        blocks.append(lines)
                elif why := take(c.children):
                    return why
                else:
                    flush()
            else:
                run.append(c)
        return None

    why = take(h.next_siblings)
    flush()
    return blocks, why or "end"


def _not_a_person(name: str) -> bool:
    tokens = name.split()
    if not 2 <= len(tokens) <= 5:
        return True
    for t in tokens:
        if t.lower() in NAME_PARTICLES:
            continue
        if not NAME_TOKEN_RE.match(t) or not t[0].isupper() or (len(t) >= 3 and t.isupper()):
            return True  # lower case ("a kutatás"), a digit or a symbol, or an acronym ("MTA", "OSI")
    return bool(NON_PERSON_RE.search(name))


def _name_line(text: str) -> tuple[list[str], str]:
    """(names, why): the names on one line of a heading section, or why the line has none.

    The line is split like a "Label: value" value (_split_names), but it must look like names from its start:
    reading stops at the first part that is not a person, because what follows a name that is not one is its
    affiliation, city or country ("Ingrid Sharp, University of Leeds, Great Britain")."""
    if not text:
        return [], "blank"
    if not re.search(r"[^\W\d_]", text):
        return [], "placeholder"  # "...", "....", "-"
    if len(text) > PROSE_LINE_LEN or SECTION_NOT_NAMES_RE.search(text):
        return [], "prose or link"
    text = re.sub(r"\)\s+(?=[A-ZÁÉÍÓÖŐÚÜŰ])", "), ", text)  # "X (ELTE) Y Z" lacks a comma, as in _split_names
    text = re.sub(r"\s*[(\[][^()\[\]]*[)\]]", "", text)  # an affiliation, whatever it contains: "(dékán, BGF)", "[FMUP]"
    if not text.strip():
        return [], "placeholder"
    names: list[str] = []
    for part in re.split(r",|;| és | and ", text):
        if not part.strip():
            continue
        got = _split_names(part)
        if len(got) != 1 or _not_a_person(got[0]):
            break
        names.append(got[0])
    return names, "" if names else "not a person"


def _read_section(h: Tag, stated: str, label: str, kind: str, base: str, aliases: dict[str, str]) -> HeadingSection:
    sec = HeadingSection(heading=stated, label=label, tag=h.name, kind=kind)
    blocks, sec.end = _section_blocks(h, base, aliases)
    # the short "Résztvevő" / "Részvevők" label reads profile links only, as on a "Label: value" line (#16)
    text_ok = kind == "lead" or bool(PARTICIPANTS_LABEL_RE.match(label))
    for block in blocks:
        read = placeholder = False
        for line in block:
            names, why = _name_line(line.text)
            linked = [lk for lk in line.links if is_profile_url(lk.url)]
            if names and text_ok:
                sec.names += [(n, line.text) for n in names]
                read = True
            elif names:
                sec.rejected.append((line.text, "label reads profile links only"))
            elif why == "placeholder":
                sec.placeholders += 1
                placeholder = True
            elif why != "blank":
                sec.rejected.append((line.text, why))
            if linked and (names or len(linked) == 1 and _tidy(line.text) == linked[0].text):
                sec.links += [(lk, line.text) for lk in linked]
                read = True
        if read:
            sec.blocks += 1
        elif not placeholder and any(line.text for line in block):
            sec.end = "non-name block"  # a block that is not a list of names ends the section (a p used as a heading)
            break
    return sec


def _heading_sections(main: Tag, title: Tag | None, base: str, aliases: dict[str, str]) -> list[HeadingSection]:
    out = []
    for h in main.find_all(HEADING_TAGS):
        if h is not title and (lab := _heading_label(h)):
            out.append(_read_section(h, *lab, base, aliases))
    return out


def _apply_heading_sections(page: ProjectPage, sections: list[HeadingSection]) -> None:
    """Feed what the headings stated through _apply_project_lines, as a "Label: names" line, so that a heading and
    a label line yield the same fields. A name or profile link the page already has, from a label line or an
    earlier heading, is not added again: one page states a person once as a lead and once as a participant."""
    for sec in sections:
        lead = sec.kind == "lead"
        known_names = {n for n, _ in (page.unlinked_leads if lead else page.unlinked_participants)}
        known_urls = {lk.url for lk in (page.leads if lead else page.participants)}
        names = list(dict.fromkeys(n for n, _ in sec.names if n not in known_names))
        links = list({lk.url: lk for lk, _ in sec.links if lk.url not in known_urls}.values())
        if not names and not links:
            continue
        before = (len(page.leads), len(page.unlinked_leads), len(page.participants), len(page.unlinked_participants))
        _apply_project_lines(page, [Line(f"{sec.label}: {'; '.join(names)}", links, sec.tag)])
        for lk in page.leads[before[0]:]:
            page.heading_origin[("lead", lk.url)] = sec
        for n, _ in page.unlinked_leads[before[1]:]:
            page.heading_origin[("lead", n)] = sec
        for lk in page.participants[before[2]:]:
            page.heading_origin[("participant", lk.url)] = sec
        for n, _ in page.unlinked_participants[before[3]:]:
            page.heading_origin[("participant", n)] = sec


def _heading_description(main: Tag, title: Tag | None, base: str, aliases: dict[str, str]) -> tuple[str, str] | None:
    """(heading, paragraph) under an "A kutatás" heading: the first paragraph of 80 characters or more, as for a
    <p> description. Only the first such heading, only up to the next heading, only the first paragraph, so a
    reference list or a footer after it is never read."""
    for h in main.find_all(HEADING_TAGS):
        stated = text_of(h).strip(" : ")
        if h is title or not DESCRIPTION_HEADING_RE.match(stated):
            continue
        for block in _section_blocks(h, base, aliases)[0]:
            t = _tidy(" ".join(line.text for line in block))
            if len(t) >= 80 and ":" not in t[:40]:
                return stated, t
        return None
    return None


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
    page.sections = _heading_sections(main, title, base, aliases)
    _apply_heading_sections(page, page.sections)
    for sec in page.sections:
        if not sec.read:
            page.unmapped_labels.append(f"{sec.label} (heading without a readable name)")
    if found := _heading_description(main, title, base, aliases):
        # an explicit "A kutatás" heading beats "the first long <p>", which on these pages is as often the participants
        # list or a coordinator's address as the description
        page.description_heading, page.description = found
    else:
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
