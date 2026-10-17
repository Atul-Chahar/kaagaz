"""Shared text normalisation for excerpt checks (used by audit_data.py and check_excerpt.py)."""

import re
import unicodedata

_QUOTES = {"‘": "'", "’": "'", "“": '"', "”": '"', "–": "-", "—": "-", " ": " "}


def norm(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    for a, b in _QUOTES.items():
        text = text.replace(a, b)
    # pdftotext -layout can split words across columns; collapse all whitespace
    return re.sub(r"\s+", " ", text).strip().lower()
