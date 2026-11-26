"""Text normalisation shared by the corpus builder and, later, the citation validator.

Two levels:

- `clean_text` is applied once when the corpus is built. The stored text keeps the wording and
  typography of the source and only loses layout artefacts.
- `fold_for_match` is applied to both sides of a comparison, so that a quote with straight
  quotes or a different dash still matches the stored text. It never changes words or case.
"""

import re
import unicodedata

# EUR-Lex amendment markers in consolidated texts: ▼B, ▼M1, ►C1 ... ◄
_MARKERS = re.compile(r"[▼►][A-Z]\d*|◄")
# Parentheses left behind after a footnote reference was removed: "Council () and"
_EMPTY_PARENS = re.compile(r"\(\s*\)")
_SPACE_BEFORE_PUNCT = re.compile(r"\s+([,;:.])")
_WHITESPACE = re.compile(r"\s+")

_FOLD = str.maketrans(
    {
        "‘": "'",
        "’": "'",
        "‚": "'",
        "“": '"',
        "”": '"',
        "„": '"',
        "–": "-",
        "—": "-",
        "‑": "-",
    }
)


def clean_text(text: str) -> str:
    """Remove markers and layout whitespace from a piece of legal text."""
    text = unicodedata.normalize("NFC", text)
    text = _MARKERS.sub(" ", text)
    text = _EMPTY_PARENS.sub(" ", text)
    text = _WHITESPACE.sub(" ", text)
    text = _SPACE_BEFORE_PUNCT.sub(r"\1", text)
    return text.strip()


def fold_for_match(text: str) -> str:
    """Make typographic variants comparable. Use on both sides of a comparison."""
    return clean_text(text).translate(_FOLD)
