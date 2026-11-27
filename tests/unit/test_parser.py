"""Parser tests on small excerpts of the real EUR-Lex HTML (see tests/fixtures/eurlex)."""

from pathlib import Path

import pytest

from verbatim.ingestion.models import Document
from verbatim.ingestion.normalize import clean_text
from verbatim.ingestion.parser import parse_document
from verbatim.ingestion.sources import Source

FIXTURES = Path(__file__).parent.parent / "fixtures" / "eurlex"


def _parse(name: str, celex: str = "TEST") -> Document:
    source = Source(
        celex=celex,
        act="ai-act",
        version_date="2026-07-27",
        status="consolidated",
        language="en",
        url="https://example.invalid/doc",
        sha256="0" * 64,
    )
    return parse_document((FIXTURES / name).read_text("utf-8"), source)


def _paths(doc: Document, article: str) -> list[tuple[str, ...]]:
    return [b.path for b in doc.article(article).blocks]


def _text(doc: Document, article: str, path: tuple[str, ...]) -> str:
    return " ".join(b.text for b in doc.article(article).blocks if b.path == path)


ALL_FIXTURES = sorted(p.name for p in FIXTURES.glob("*.html"))


@pytest.mark.parametrize("name", ALL_FIXTURES)
def test_every_block_is_clean_and_non_empty(name: str) -> None:
    doc = _parse(name)
    texts = [b.text for a in doc.articles for b in a.blocks]
    texts += [b.text for a in doc.annexes for b in a.blocks]
    texts += [r.text for r in doc.recitals]
    assert texts, "fixture produced no text"
    for text in texts:
        assert text
        assert text == clean_text(text)
        assert not any(marker in text for marker in "▼►◄")
        assert "—————" not in text


# --- Official Journal layout -------------------------------------------------------------


def test_oj_article_with_points_in_tables() -> None:
    doc = _parse("oj_chapter_ii.html")
    art = doc.article("5")
    assert art.title == "Prohibited AI practices"
    assert (art.chapter, art.chapter_title) == ("II", "PROHIBITED AI PRACTICES")
    assert art.section is None

    paths = _paths(doc, "5")
    assert paths[0] == ("1",)
    assert _text(doc, "5", ("1",)).startswith("The following AI practices shall be prohibited:")
    assert _text(doc, "5", ("1", "a")).startswith("the placing on the market")
    assert ("1", "h", "iii") in paths
    assert {p[0] for p in paths} == {"1", "2", "3", "4", "5", "6", "7", "8"}


def test_oj_paragraph_number_is_not_part_of_the_text() -> None:
    doc = _parse("oj_chapter_ii.html")
    assert not _text(doc, "5", ("2",)).startswith("2.")


def test_oj_article_without_numbered_paragraphs() -> None:
    doc = _parse("oj_art_4.html")
    art = doc.article("4")
    assert art.title == "AI literacy"
    assert [b.path for b in art.blocks] == [()]
    assert art.blocks[0].text.startswith(
        "Providers and deployers of AI systems shall take measures"
    )


def test_oj_footnote_reference_is_removed() -> None:
    doc = _parse("oj_art_103.html")
    text = " ".join(b.text for b in doc.article("103").blocks)
    assert "of the European Parliament and of the Council, the requirements" in text
    assert "(*)" not in text


def test_oj_annex_with_nested_points() -> None:
    doc = _parse("oj_annex_iii.html")
    annex = doc.annex("III")
    assert annex.title == "High-risk AI systems referred to in Article 6(2)"
    by_path: dict[tuple[str, ...], str] = {}
    for b in annex.blocks:
        by_path.setdefault(b.path, b.text)  # first block per path; subparagraphs share a path
    assert by_path[()].startswith("High-risk AI systems pursuant to Article 6(2)")
    assert by_path[("1",)].startswith("Biometrics")
    assert by_path[("1", "a")].startswith("remote biometric identification systems")


def test_oj_recitals() -> None:
    doc = _parse("oj_recitals.html")
    assert [r.number for r in doc.recitals] == ["1", "2"]
    assert doc.recital("1").text.startswith("The purpose of this Regulation is to improve")


# --- Consolidated layout -----------------------------------------------------------------


def test_consolidated_article_with_inserted_points_and_paragraphs() -> None:
    doc = _parse("cons_chapter_ii.html")
    art = doc.article("5")
    assert (art.chapter, art.chapter_title) == ("II", "PROHIBITED AI PRACTICES")
    paths = _paths(doc, "5")
    assert ("1", "ba") in paths
    assert ("1", "bb") in paths
    assert ("1a",) in paths
    assert ("1b",) in paths


def test_consolidated_inserted_article() -> None:
    doc = _parse("cons_art_4a.html")
    art = doc.article("4a")
    assert art.title == (
        "Processing of special categories of personal data for bias detection and correction"
    )
    assert art.blocks[0].path == ("1",)
    assert art.blocks[0].text.startswith("To the extent strictly necessary")


def test_consolidated_deleted_paragraph_is_absent() -> None:
    doc = _parse("cons_art_10.html")
    paragraphs = list(dict.fromkeys(p[0] for p in _paths(doc, "10")))
    assert paragraphs == ["1", "2", "3", "4", "6"]


def test_consolidated_footnote_reference_is_removed() -> None:
    doc = _parse("cons_art_40.html")
    text = " ".join(b.text for b in doc.article("40").blocks)
    assert "of the European Parliament and of the Council and without undue delay" in text


def test_consolidated_inline_corrigendum_markers_are_removed() -> None:
    doc = _parse("cons_gdpr_art_43.html")
    assert _text(doc, "43", ("3",)).startswith(
        "The accreditation of certification bodies as referred to in paragraphs 1 and 2"
    )


def test_metadata_is_taken_from_the_source() -> None:
    doc = _parse("oj_art_4.html", celex="32024R1689")
    assert doc.celex == "32024R1689"
    assert doc.act == "ai-act"
    assert doc.language == "en"


def test_consolidated_content_after_a_paragraph_belongs_to_it() -> None:
    # Consolidated texts put later subparagraphs and points next to the paragraph's div.
    doc = _parse("cons_art_6.html")
    paths = _paths(doc, "6")
    assert () not in paths
    assert ("3", "d") in paths
    assert "Notwithstanding the first subparagraph" in _text(doc, "6", ("3",))
    assert _text(doc, "6", ("4",)).startswith("A provider who considers")


def test_consolidated_superscript_stays_in_its_sentence() -> None:
    doc = _parse("cons_art_51.html")
    assert _text(doc, "51", ("2",)).endswith("floating point operations is greater than 10^25.")
    assert len([b for b in doc.article("51").blocks if b.path == ("2",)]) == 1


def test_quoted_paragraph_of_another_act_is_not_a_paragraph_of_this_one() -> None:
    doc = _parse("cons_art_105.html")
    assert all(not p or not p[0].startswith("‘") for p in _paths(doc, "105"))
    assert "‘5." in " ".join(b.text for b in doc.article("105").blocks)


# --- Sections in annexes -----------------------------------------------------------------


def _annex_paths(doc: Document, annex: str) -> list[tuple[str, ...]]:
    return [b.path for b in doc.annex(annex).blocks]


def test_annex_section_heading_starts_a_path_level() -> None:
    annex = _parse("cons_annex_viii.html").annex("VIII")
    assert annex.blocks[0].path == ("Section A",)
    assert annex.blocks[0].text.startswith("Section A — Information to be submitted by providers")
    paths = _annex_paths(_parse("cons_annex_viii.html"), "VIII")
    assert ("Section A", "1") in paths
    assert ("Section B", "1") in paths  # the numbering restarts, the paths differ


def test_annex_subtitle_after_a_section_heading_is_text_of_that_section() -> None:
    annex = _parse("cons_annex_xi.html").annex("XI")
    first, second = annex.blocks[:2]
    assert (first.path, first.text) == (("Section 1",), "Section 1")
    assert second.path == ("Section 1",)
    assert second.text.startswith("Information to be provided by all providers")
    assert ("Section 1", "1", "a") in _annex_paths(_parse("cons_annex_xi.html"), "XI")


def test_oj_annex_numbered_section_heading() -> None:
    annex = _parse("oj_annex_vii.html").annex("VII")
    assert (annex.blocks[0].path, annex.blocks[0].text) == (("1",), "1. Introduction")
    assert ("3", "a") in _annex_paths(_parse("oj_annex_vii.html"), "VII")
    assert annex.title.startswith("Conformity based on an assessment")
