"""Hungarian personal-name normalisation.

Hungarian names are written family-name first ("Koltai Júlia"). English-language
pages often invert them ("Júlia Koltai"). We never decide which order a string is in
from the string alone; callers pass ``order`` when the source tells us.
"""

from __future__ import annotations

import re
import unicodedata

# Honorifics and degrees that appear inside name strings on Hungarian pages.
_TITLE_TOKENS = {
    "dr", "dr.", "prof", "prof.", "phd", "ph.d.", "habil", "habil.", "dsc", "d.sc.",
    "csc", "c.sc.", "mta", "rendes", "tag", "levelező", "emeritus", "emerita",
    "ifj.", "id.", "özv.",
}
_TITLE_RE = re.compile(r"\b(dr|prof|phd|habil|dsc|csc)\.?(?=\s|,|$)", re.I)
_SPACE_RE = re.compile(r"\s+")


def strip_accents(s: str) -> str:
    """'Ságvári Bence' -> 'Sagvari Bence'. ő/ű fold to o/u."""
    return "".join(
        c for c in unicodedata.normalize("NFKD", s) if unicodedata.category(c) != "Mn"
    )


def clean_display_name(raw: str) -> tuple[str, list[str]]:
    """Return (name without titles, titles found). Keeps diacritics and order."""
    titles: list[str] = []
    tokens = []
    for tok in _SPACE_RE.split(raw.replace(",", " ").strip()):
        if not tok:
            continue
        if tok.lower() in _TITLE_TOKENS or _TITLE_RE.fullmatch(tok):
            titles.append(tok.rstrip(","))
        else:
            tokens.append(tok)
    return " ".join(tokens), titles


def name_key(name: str) -> str:
    """Accent- and case-insensitive key preserving token order. Used for blocking only."""
    cleaned, _ = clean_display_name(name)
    s = strip_accents(cleaned).lower()
    s = re.sub(r"[^a-z\s-]", " ", s)
    return _SPACE_RE.sub(" ", s.replace("-", " ")).strip()


def order_free_key(name: str) -> str:
    """Token-set key: 'Koltai Júlia' and 'Júlia Koltai' collide. Blocking only, never a match."""
    return " ".join(sorted(name_key(name).split()))


def slugify(s: str) -> str:
    s = strip_accents(s).lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")


def normalise_whitespace(s: str) -> str:
    return _SPACE_RE.sub(" ", s).strip()
