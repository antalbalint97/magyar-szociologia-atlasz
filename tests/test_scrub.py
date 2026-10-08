"""The fixture scrubber (#43): contact details must not reach a committed fixture."""

import pytest
from bs4 import BeautifulSoup

from szocatlas.registry import REPO_ROOT
from szocatlas.scrub import scrub_html

FIXTURES = sorted((REPO_ROOT / "tests" / "fixtures").rglob("*.html"))


def body(html: str) -> str:
    """What the scrubbed page holds between ``<body>`` and ``</body>``."""
    out = scrub_html(html)
    return out[out.index("<body>") + len("<body>"): out.index("</body>")]


@pytest.mark.parametrize("html, expected", [
    # the label is in its own element: the value after it is blanked, whatever it looks like
    ("<li><b>Telefonszám:</b> +36 1 224 6700</li>", "<li><b>Telefonszám:</b> XXX</li>"),
    ("<li><b>Telefonszám:</b> (1) 224 6700</li>", "<li><b>Telefonszám:</b> XXX</li>"),
    # the country prefix alone is enough
    ("<p>Hívjon: +36 1 224 6700</p>", "<p>Hívjon: XXX</p>"),
    ("<p>Hívjon: 0036 1 224 6700</p>", "<p>Hívjon: XXX</p>"),
    ("<p>Hívjon: 06 1 224 6700</p>", "<p>Hívjon: XXX</p>"),
    ("<p>+36-30-123-4567</p>", "<p>XXX</p>"),
    # the label is in the same text node as the number (the case that got through before #43)
    ("<p>Telefon: (1) 224 6700</p>", "<p>Telefon: XXX</p>"),
    ("<p>Tel.: 1/224-6700</p>", "<p>Tel.: XXX</p>"),
    ("<p>Mobil: 30 123 4567</p>", "<p>Mobil: XXX</p>"),
    ("<p>Tel./Fax: 224-6700</p>", "<p>Tel./Fax: XXX</p>"),
    ("<p>Telefon (1) 224 6700, szoba 1.30</p>", "<p>Telefon XXX, szoba 1.30</p>"),
    # an area code in brackets or before a slash, no label and no country prefix
    ("<p>Hívjon: (1) 224 6700</p>", "<p>Hívjon: XXX</p>"),
    ("<p>Hívjon: 1/224-6700</p>", "<p>Hívjon: XXX</p>"),
    # links and e-mail addresses
    ('<a href="tel:+3612246700">x</a>', '<a href="tel:XXX">x</a>'),
    ('<a href="mailto:kovacs.janos@example.org">x</a>', '<a href="mailto:xxx@example.org">x</a>'),
    ("<p>Írjon: kovacs.janos@example.org</p>", "<p>Írjon: xxx@example.org</p>"),
])
def test_contact_details_are_blanked(html, expected):
    assert body(html) == expected


@pytest.mark.parametrize("html", [
    "<p>ISBN 978-963-9741-55-3</p>",
    "<p>Budapest: Napvilág Kiadó, 2017. 376 p.</p>",
    "<p>pp. 123-145</p>",
    "<p>OTKA K 108836, NKFIH 119603 jelű</p>",
    "<p>2019-2023 között; 2020/2021 tanév</p>",
    "<p>Tér és Társadalom 33(4), 12-34</p>",
    # an issue number and a page range in a reference look like an area code and a number (found in a fixture)
    "<p>Szociológiai Szemle 2021 55 (2) 400-422.</p>",
    "<p>Replika 2016:(2) 104-116.</p>",
    "<p>Szemle 2019;(4) 983-1002.</p>",
    "<p>A telefon használata a fiatalok körében</p>",
])
def test_text_that_is_not_contact_data_is_left_alone(html):
    assert body(html) == html


def test_scrubbing_twice_changes_nothing():
    once = scrub_html("<p>Telefon: (1) 224 6700</p><li><b>Telefonszám:</b> 06 1 224 6700</li>")
    assert scrub_html(once) == once


def text_and_links(html: str):
    soup = BeautifulSoup(html, "lxml")
    return soup.get_text("\n"), [a.get("href") for a in soup.find_all("a")]


@pytest.mark.parametrize("path", FIXTURES, ids=lambda p: p.name)
def test_a_committed_fixture_has_nothing_left_to_scrub(path):
    """Every fixture went through the scrubber when it was captured; running it again finds nothing to change,
    so a fixture that still holds a number the scrubber knows (or a false positive) fails here."""
    html = path.read_text(encoding="utf-8")
    assert text_and_links(scrub_html(html)) == text_and_links(html)
