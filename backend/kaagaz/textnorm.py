"""Text normalisation for excerpt checks. The same rule as scripts/textnorm.py (a test checks they agree)."""

import re
import unicodedata

_QUOTES = {"‘": "'", "’": "'", "“": '"', "”": '"', "–": "-", "—": "-", " ": " "}


def norm(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    for a, b in _QUOTES.items():
        text = text.replace(a, b)
    # pdftotext -layout can split words across columns; collapse all whitespace
    return re.sub(r"\s+", " ", text).strip().lower()
