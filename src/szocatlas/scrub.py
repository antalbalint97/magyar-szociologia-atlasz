"""Remove contact details and page chrome from captured HTML before it is committed.

Captured fixtures are real page snapshots, but the repository never stores e-mail local
parts, phone numbers or room numbers (they are recognised by the parsers only to be
dropped). The markup is otherwise left as served, so parsers are tested on real
structure. Scripts, iframes and tracking snippets are removed.

A phone number is recognised in four ways (#43): the value after a contact label in its own
element (``<b>Telefonszám:</b> …``); a number with the country prefix (``+36``, ``0036``, ``06``);
a number after its label inside the same text node (``Telefon: (1) 224-6700``); and a Hungarian
number written with an area code, without a label or prefix (``(1) 224 6700``, ``1/224-6700``).
This is a safety net, not a guarantee: an unlabelled ``(1) 224-6700`` (hyphen, which a reference's
``(2) 400-422`` shares), an attribute other than ``href`` or a table laid out label-cell/value-cell
is not found, so a new capture is still read by eye before it is committed.
``tests/test_scrub.py`` scrubs every committed fixture and fails if anything is left to change.
"""

from __future__ import annotations

import re

from bs4 import BeautifulSoup, Comment

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@([A-Za-z0-9.-]+\.[A-Za-z]{2,})")
PHONE_RE = re.compile(r"(?:\(?\+\s?36\)?|\b0036|\b06)[\d ()/-]{6,}\d")
# "Telefon: (1) 224 6700", "Tel.: 1/224-6700", "Fax 224-6700": the label and its number in one text node.
LABELLED_NUMBER_RE = re.compile(
    r"\b(?:telefonszám|telefon|tel|mobil|fax)\b\.?\s*:?\s*(?P<number>[+(]?\d[\d ()/.–-]{3,}\d)", re.I)
# A number with an area code, no prefix needed: "(1) 224 6700" (groups separated by a space, because "(2) 400-422" is
# an issue number and a page range in a reference) or "1/224-6700" (area code before a slash).
AREA_CODE_RE = re.compile(r"\(\d{1,2}\)\s?\d{3}\s\d{4}\b|\b\d{1,2}/\d{3}[\s-]\d{3,4}\b")
CONTACT_LABEL_RE = re.compile(r"^\s*(telefon|telefonszám|mobil|fax|épület|szoba|iroda)\s*:?\s*$", re.I)


def scrub_text(text: str) -> str:
    """One text node with its e-mail addresses and phone numbers replaced."""
    text = PHONE_RE.sub("XXX", EMAIL_RE.sub(r"xxx@\1", text))
    text = LABELLED_NUMBER_RE.sub(lambda m: m.group(0)[: m.start("number") - m.start()] + "XXX", text)
    return AREA_CODE_RE.sub("XXX", text)


def scrub_html(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    for t in soup.find_all(["script", "noscript", "iframe"]):
        t.decompose()
    for c in soup.find_all(string=lambda s: isinstance(s, Comment)):
        c.extract()
    for a in soup.find_all("a", href=True):
        if a["href"].lower().startswith("mailto:"):
            a["href"] = EMAIL_RE.sub(r"xxx@\1", a["href"])
        elif a["href"].lower().startswith("tel:"):
            a["href"] = "tel:XXX"
    # "<b>Telefonszám:</b> +36 ..." / "<b>Épület:</b> B (szoba 1.30)": blank the value
    for label in soup.find_all(["b", "strong", "dt", "span"]):
        if CONTACT_LABEL_RE.match(label.get_text(" ")):
            for sib in list(label.next_siblings):
                if getattr(sib, "name", None) == "br":
                    break
                if isinstance(sib, str):
                    sib.replace_with(" XXX" if sib.strip() else sib)
                else:
                    sib.string = "XXX"
    for s in soup.find_all(string=True):
        new = scrub_text(str(s))
        if new != str(s):
            s.replace_with(new)
    return str(soup)
