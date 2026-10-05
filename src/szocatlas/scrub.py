"""Remove contact details and page chrome from captured HTML before it is committed.

Captured fixtures are real page snapshots, but the repository never stores e-mail local
parts, phone numbers or room numbers (they are recognised by the parsers only to be
dropped). The markup is otherwise left as served, so parsers are tested on real
structure. Scripts, iframes and tracking snippets are removed.
"""

from __future__ import annotations

import re

from bs4 import BeautifulSoup, Comment

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@([A-Za-z0-9.-]+\.[A-Za-z]{2,})")
PHONE_RE = re.compile(r"(?:\(?\+\s?36\)?|\b06)[\d ()/-]{6,}\d")
CONTACT_LABEL_RE = re.compile(r"^\s*(telefon|telefonszám|mobil|fax|épület|szoba|iroda)\s*:?\s*$", re.I)


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
        new = PHONE_RE.sub("XXX", EMAIL_RE.sub(r"xxx@\1", str(s)))
        if new != str(s):
            s.replace_with(new)
    return str(soup)
