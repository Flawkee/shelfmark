"""Shared title/author normalization for matching books across systems.

Used by the Kavita inventory sync (write side) and the metadata search
annotation (read side) so the keys line up. Keep both sides on these helpers.
"""

from __future__ import annotations

import re
import unicodedata

_LEADING_ARTICLES = ("the ", "a ", "an ")
_NON_ALNUM = re.compile(r"[^a-z0-9]+")
_WHITESPACE = re.compile(r"\s+")
_BRACKETED = re.compile(r"\([^)]*\)|\[[^\]]*\]|\{[^}]*\}")


def _fold(value: object) -> str:
    """Lowercase, strip accents, drop bracketed qualifiers and punctuation.

    Bracketed segments like "(Unabridged)", "(2020)", or "(Digital)" are
    dropped so library titles line up with provider search titles.
    """
    text = str(value or "")
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.lower()
    text = _BRACKETED.sub(" ", text)
    text = _NON_ALNUM.sub(" ", text)
    return _WHITESPACE.sub(" ", text).strip()


def normalize_title(value: object) -> str:
    """Normalize a book/series title for equality matching.

    Drops a leading article and anything after a colon (subtitle).
    """
    text = _fold(value)
    if ":" in str(value or ""):
        text = _fold(str(value).split(":", 1)[0])
    for article in _LEADING_ARTICLES:
        if text.startswith(article):
            text = text[len(article) :]
            break
    return text


def normalize_author(value: object) -> str:
    """Normalize an author string for equality matching.

    Uses only the first listed author so "Rowling" matches "J. K. Rowling, foo".
    """
    text = str(value or "")
    first = re.split(r"[,;&]| and ", text, maxsplit=1)[0]
    return _fold(first)


def series_key(value: object) -> str:
    """Normalize a series name for grouping/coverage counts."""
    return normalize_title(value)


def fold_series(value: object) -> str:
    """Colon-tolerant series key (no subtitle truncation, no article strip).

    Unlike :func:`normalize_title`, keeps the full name so series whose titles
    contain a colon ("Yashahime: Princess Half-Demon") still match the Kavita
    series name ("Yashahime - Princess Half-Demon").
    """
    return _fold(value)


_VOLUME_IN_TITLE = re.compile(r"[,:]?\s*\b(?:vol|volume|v)\b\.?\s*(\d+(?:\.\d+)?)", re.IGNORECASE)


def parse_volume_title(value: object) -> tuple[str | None, float | None]:
    """Split a volume title into (series_part, volume_number).

    "InuYasha, Vol. 1: Turning Back Time" -> ("InuYasha", 1.0)
    "Yashahime: Princess Half-Demon, Vol. 1" -> ("Yashahime: Princess Half-Demon", 1.0)
    Returns (None, None) when no volume marker is present.
    """
    text = str(value or "")
    match = _VOLUME_IN_TITLE.search(text)
    if not match:
        return None, None
    try:
        volume = float(match.group(1))
    except (TypeError, ValueError):
        return None, None
    series_part = text[: match.start()].strip(" ,:-")
    return (series_part or None), volume
