"""Checks on the processed corpus in data/processed. Runs without network access.

Expected counts were checked against the EUR-Lex documents on 2026-11-26.
"""

from pathlib import Path

import pytest

from verbatim.ingestion.models import (
    Block,
    Document,
    annex_ref,
    article_ref,
    iter_references,
    load_document,
)
from verbatim.ingestion.normalize import clean_text
from verbatim.ingestion.parser import parse_document
from verbatim.ingestion.sources import Source, load_sources

ROOT = Path(__file__).parents[2]
PROCESSED = ROOT / "data" / "processed"
RAW = ROOT / "data" / "raw"
SOURCES = load_sources(ROOT / "data" / "sources.toml")

# celex: (articles, annexes, recitals)
EXPECTED_COUNTS = {
    "02024R1689-20260727": (119, 14, 0),
    "32024R1689": (113, 13, 180),
    "02016R0679-20160504": (99, 0, 0),
    "32016R0679": (99, 0, 173),
}


def _doc(celex: str) -> Document:
    return load_document(PROCESSED / f"{celex}.json")


@pytest.mark.parametrize("celex", sorted(EXPECTED_COUNTS))
def test_counts(celex: str) -> None:
    doc = _doc(celex)
    assert (len(doc.articles), len(doc.annexes), len(doc.recitals)) == EXPECTED_COUNTS[celex]


@pytest.mark.parametrize("celex", sorted(EXPECTED_COUNTS))
def test_structure_is_consistent(celex: str) -> None:
    doc = _doc(celex)
    numbers = [a.number for a in doc.articles]
    assert len(numbers) == len(set(numbers))
    assert [r.number for r in doc.recitals] == [str(i) for i in range(1, len(doc.recitals) + 1)]
    for article in doc.articles:
        assert article.title
        assert article.chapter
        assert article.blocks
    for block in [b for a in (*doc.articles, *doc.annexes) for b in a.blocks]:
        assert block.text
        assert block.text == clean_text(block.text)
        assert "—————" not in block.text


def _reused_labels(blocks: tuple[Block, ...]) -> set[tuple[str, ...]]:
    """Paths whose label reappears under the same parent after a different sibling.

    Such a path stands for two different provisions, so its reference is ambiguous.
    """
    last: dict[tuple[str, ...], str] = {}
    seen: dict[tuple[str, ...], set[str]] = {}
    reused: set[tuple[str, ...]] = set()
    for block in blocks:
        for depth in range(1, len(block.path) + 1):
            parent, label = block.path[: depth - 1], block.path[depth - 1]
            if last.get(parent) != label:
                if label in seen.setdefault(parent, set()):
                    reused.add(block.path[:depth])
                seen[parent].add(label)
                last[parent] = label
    return reused


def _ambiguous_references(doc: Document) -> set[str]:
    refs = {article_ref(a.number, p) for a in doc.articles for p in _reused_labels(a.blocks)}
    refs |= {annex_ref(a.number, p) for a in doc.annexes for p in _reused_labels(a.blocks)}
    return refs


# Known ambiguities, documented in docs/adr/0003-corpus-version.md. Annexes VII, VIII and X
# restart their numbering per section, and Art. 43(1) has points (a) and (b) in two
# subparagraphs. The structural path does not yet carry sections or subparagraphs.
_ANNEX_SECTIONS = {
    "Annex VII, point a",
    "Annex VII, point b",
    "Annex VII, point c",
    "Annex X, point a",
    "Annex X, point b",
    "Art. 43(1)(a)",
    "Art. 43(1)(b)",
}
KNOWN_AMBIGUOUS = {
    "02024R1689-20260727": _ANNEX_SECTIONS
    | {f"Annex VIII, point {n}" for n in (1, 2, 3, 4, 5, 6, 8)},
    "32024R1689": _ANNEX_SECTIONS | {f"Annex VIII, point {n}" for n in range(1, 10)},
    "02016R0679-20160504": set[str](),
    "32016R0679": set[str](),
}


@pytest.mark.parametrize("celex", sorted(KNOWN_AMBIGUOUS))
def test_references_are_unambiguous_except_known_cases(celex: str) -> None:
    assert _ambiguous_references(_doc(celex)) == KNOWN_AMBIGUOUS[celex]


def test_inserted_articles_sit_in_their_chapters() -> None:
    doc = _doc("02024R1689-20260727")
    assert doc.article("4a").chapter == "I"
    assert doc.article("60a").chapter == "VI"
    for number in ["75a", "75b", "75c", "75d"]:
        article = doc.article(number)
        assert (article.chapter, article.section) == ("IX", "3")


def test_consolidated_ai_act_contains_the_omnibus_amendments() -> None:
    current = set(iter_references(_doc("02024R1689-20260727")))
    original = set(iter_references(_doc("32024R1689")))
    for added in ["Art. 4a", "Art. 60a", "Art. 75d", "Art. 5(1)(ba)", "Art. 5(1a)", "Annex XIV"]:
        assert added in current
        assert added not in original
    assert "Art. 10(5)" in original
    assert "Art. 10(5)" not in current


def test_high_risk_application_date_moved_by_the_omnibus() -> None:
    def text_of_art_113(celex: str) -> str:
        return " ".join(b.text for b in _doc(celex).article("113").blocks)

    assert "2 December 2027" in text_of_art_113("02024R1689-20260727")
    assert "2 December 2027" not in text_of_art_113("32024R1689")


def test_metadata_matches_the_manifest() -> None:
    for source in SOURCES:
        doc = _doc(source.celex)
        assert (doc.act, doc.version_date, doc.status, doc.language, doc.url) == (
            source.act,
            source.version_date,
            source.status,
            source.language,
            source.url,
        )


@pytest.mark.parametrize("source", SOURCES, ids=lambda s: s.celex)
def test_processed_file_matches_a_fresh_parse(source: Source) -> None:
    """Guards against a parser change without rebuilding data/processed. Needs `make fetch`."""
    raw = RAW / f"{source.celex}.html"
    if not raw.exists():
        pytest.skip("raw file not downloaded, run `make fetch`")
    assert parse_document(raw.read_text("utf-8"), source) == _doc(source.celex)


@pytest.mark.parametrize("celex", ["02024R1689-20260727", "32024R1689"])
def test_annexes_have_titles(celex: str) -> None:
    # Annex XIV, added by the Omnibus, has no title in the source.
    untitled = [a.number for a in _doc(celex).annexes if not a.title]
    assert untitled == (["XIV"] if celex.startswith("0") else [])
