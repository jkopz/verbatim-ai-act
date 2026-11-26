"""Checks on the processed corpus in data/processed. Runs without network access.

Expected counts were checked against the EUR-Lex documents on 2026-11-26.
"""

from pathlib import Path

import pytest

from verbatim.ingestion.models import Document, iter_references, load_document
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
        for block in article.blocks:
            assert block.text == clean_text(block.text)
    refs = list(iter_references(doc))
    assert len(refs) == len(set(refs))


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
