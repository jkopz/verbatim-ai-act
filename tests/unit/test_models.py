from dataclasses import replace

import pytest

from verbatim.ingestion.models import (
    Annex,
    Article,
    Block,
    Document,
    Recital,
    ambiguous_references,
    annex_ref,
    article_ref,
    document_from_dict,
    document_to_dict,
    iter_references,
    recital_ref,
    reference_index,
)


@pytest.mark.parametrize(
    ("number", "path", "expected"),
    [
        ("5", (), "Art. 5"),
        ("5", ("1",), "Art. 5(1)"),
        ("5", ("1", "ba"), "Art. 5(1)(ba)"),
        ("5", ("1", "h", "iii"), "Art. 5(1)(h)(iii)"),
        ("4a", ("1a",), "Art. 4a(1a)"),
    ],
)
def test_article_ref(number: str, path: tuple[str, ...], expected: str) -> None:
    assert article_ref(number, path) == expected


@pytest.mark.parametrize(
    ("number", "path", "expected"),
    [
        ("III", (), "Annex III"),
        ("III", ("1",), "Annex III, point 1"),
        ("III", ("1", "a"), "Annex III, point 1(a)"),
        ("VIII", ("Section A",), "Annex VIII, Section A"),
        ("VIII", ("Section A", "6"), "Annex VIII, Section A, point 6"),
        ("XI", ("Section 1", "1", "a"), "Annex XI, Section 1, point 1(a)"),
    ],
)
def test_annex_ref(number: str, path: tuple[str, ...], expected: str) -> None:
    assert annex_ref(number, path) == expected


def test_recital_ref() -> None:
    assert recital_ref("27") == "Recital 27"


def _sample() -> Document:
    return Document(
        act="ai-act",
        celex="02024R1689-20260727",
        version_date="2026-07-27",
        status="consolidated",
        language="en",
        url="https://example.invalid/doc",
        articles=(
            Article(
                number="5",
                title="Prohibited AI practices",
                chapter="II",
                chapter_title="PROHIBITED AI PRACTICES",
                section=None,
                section_title=None,
                blocks=(
                    Block(path=("1",), text="The following AI practices shall be prohibited:"),
                    Block(path=("1", "a"), text="the placing on the market ..."),
                ),
            ),
        ),
        annexes=(
            Annex(
                number="III",
                title="High-risk AI systems",
                blocks=(Block(("1",), "Biometrics"),),
            ),
        ),
        recitals=(Recital(number="1", text="The purpose of this Regulation ..."),),
    )


def test_iter_references_lists_every_level() -> None:
    refs = set(iter_references(_sample()))
    assert refs == {
        "Art. 5",
        "Art. 5(1)",
        "Art. 5(1)(a)",
        "Annex III",
        "Annex III, point 1",
        "Recital 1",
    }


def test_document_round_trips_through_dict() -> None:
    doc = _sample()
    assert document_from_dict(document_to_dict(doc)) == doc


def test_lookup_by_number() -> None:
    doc = _sample()
    assert doc.article("5").title == "Prohibited AI practices"
    assert doc.annex("III").title == "High-risk AI systems"
    assert doc.recital("1").text.startswith("The purpose")
    with pytest.raises(KeyError):
        doc.article("999")


def test_ambiguous_references_finds_a_label_reused_after_a_sibling() -> None:
    blocks = (
        Block(("1",), "first subparagraph"),
        Block(("1", "a"), "x"),
        Block(("1", "b"), "y"),
        Block(("1",), "second subparagraph"),
        Block(("1", "a"), "z"),
        Block(("2",), "next paragraph"),
    )
    article = Article("43", "t", "III", None, None, None, blocks)
    doc = replace(_sample(), articles=(article,), annexes=())
    assert ambiguous_references(doc) == {"Art. 43(1)(a)"}


def test_reference_index_maps_each_reference_to_the_blocks_below_it() -> None:
    index = reference_index(_sample())
    assert list(index) == list(iter_references(_sample()))
    assert [b.text for b in index["Art. 5(1)"]] == [
        "The following AI practices shall be prohibited:",
        "the placing on the market ...",
    ]
    assert [b.text for b in index["Art. 5(1)(a)"]] == ["the placing on the market ..."]
    assert [b.text for b in index["Recital 1"]] == ["The purpose of this Regulation ..."]
