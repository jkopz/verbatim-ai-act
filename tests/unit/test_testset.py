"""Schema and validation of the gold test set (eval/testset)."""

import json
from pathlib import Path
from typing import Any

import pytest

from verbatim.evaluation.testset import (
    Corpus,
    GoldRef,
    InvalidTestsetError,
    Question,
    load_testset,
    parse_question,
    save_testset,
    validate,
)

ROOT = Path(__file__).parents[2]
TESTSET = ROOT / "eval" / "testset"
CORPUS = Corpus.load(ROOT / "data" / "processed")


def _question(**changes: Any) -> dict[str, Any]:
    data: dict[str, Any] = {
        "id": "q001",
        "question": "When do the obligations for Annex III high-risk systems apply?",
        "category": "dates",
        "answerable": True,
        "as_of": "2026-11-27",
        "gold_refs": [{"act": "ai-act", "ref": "Art. 113"}],
        "answer_points": ["2 December 2027"],
        "optional_points": [],
        "notes": "",
        "source_text": "",
    }
    data.update(changes)
    return data


def _errors(*items: dict[str, Any]) -> list[str]:
    return validate([parse_question(item) for item in items], CORPUS)


# --- Parsing -------------------------------------------------------------------------------


def test_parse_question() -> None:
    q = parse_question(_question())
    assert q == Question(
        id="q001",
        question="When do the obligations for Annex III high-risk systems apply?",
        category="dates",
        answerable=True,
        as_of="2026-11-27",
        gold_refs=(GoldRef("ai-act", "Art. 113"),),
        answer_points=("2 December 2027",),
        notes="",
    )


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"category": "trivia"}, "category"),
        ({"answerable": "yes"}, "answerable"),
        ({"as_of": "27.11.2026"}, "as_of"),
        ({"gold_refs": [{"act": "dsa", "ref": "Art. 1"}]}, "act"),
        ({"gold_refs": [{"ref": "Art. 1"}]}, "gold_refs"),
        ({"answer_points": "2 December 2027"}, "answer_points"),
        ({"optional_points": [""]}, "optional_points"),
        ({"source_text": None}, "source_text"),
        ({"extra": 1}, "unknown field"),
    ],
)
def test_parse_rejects_malformed_questions(changes: dict[str, Any], message: str) -> None:
    with pytest.raises(InvalidTestsetError, match=message):
        parse_question(_question(**changes))


def test_parse_reports_missing_fields() -> None:
    data = _question()
    del data["as_of"]
    with pytest.raises(InvalidTestsetError, match="missing field as_of"):
        parse_question(data)


def test_load_names_the_line_of_an_error(tmp_path: Path) -> None:
    path = tmp_path / "set.jsonl"
    path.write_text(json.dumps(_question()) + "\n" + json.dumps(_question(category="x")) + "\n")
    with pytest.raises(InvalidTestsetError, match="set.jsonl:2"):
        load_testset(path)


def test_save_and_load_round_trip(tmp_path: Path) -> None:
    questions = [parse_question(_question()), parse_question(_question(id="q002"))]
    save_testset(tmp_path / "set.jsonl", questions)
    assert load_testset(tmp_path / "set.jsonl") == questions


# --- Validation against the corpus ---------------------------------------------------------


def test_valid_question_has_no_errors() -> None:
    assert _errors(_question()) == []


def test_reference_must_exist() -> None:
    errors = _errors(_question(gold_refs=[{"act": "ai-act", "ref": "Art. 200"}]))
    assert errors == ["q001: ai-act Art. 200 not found in 02024R1689-20260727"]


def test_as_of_selects_the_version_of_the_text() -> None:
    # Art. 10(5) was deleted by the Digital Omnibus, effective 27 July 2026.
    ref = [{"act": "ai-act", "ref": "Art. 10(5)"}]
    assert _errors(_question(as_of="2026-03-01", gold_refs=ref)) == []
    assert _errors(_question(as_of="2026-11-27", gold_refs=ref)) == [
        "q001: ai-act Art. 10(5) not found in 02024R1689-20260727"
    ]


def test_recitals_come_from_the_official_journal() -> None:
    article = {"act": "ai-act", "ref": "Art. 3"}
    assert _errors(_question(gold_refs=[article, {"act": "ai-act", "ref": "Recital 12"}])) == []
    assert _errors(_question(gold_refs=[article, {"act": "gdpr", "ref": "Recital 26"}])) == []


def test_ambiguous_reference_is_rejected() -> None:
    errors = _errors(_question(gold_refs=[{"act": "ai-act", "ref": "Art. 43(1)(a)"}]))
    assert errors == ["q001: ai-act Art. 43(1)(a) is ambiguous, cite the enclosing level"]


def test_no_text_before_the_act_existed() -> None:
    errors = _errors(_question(as_of="2015-01-01", gold_refs=[{"act": "gdpr", "ref": "Art. 9"}]))
    assert errors == ["q001: no gdpr text in force on 2015-01-01"]


def test_answerable_question_needs_references_and_answer_points() -> None:
    assert _errors(_question(gold_refs=[], answer_points=[])) == [
        "q001: answerable question needs at least one gold reference",
        "q001: answerable question needs at least one answer point",
    ]


def test_not_answerable_matches_its_category() -> None:
    assert _errors(_question(category="not_answerable", answerable=False, gold_refs=[])) == []
    assert _errors(_question(answerable=False)) == [
        "q001: answerable is false, so category must be not_answerable"
    ]
    assert _errors(_question(category="not_answerable")) == [
        "q001: category not_answerable requires answerable false"
    ]


def test_recital_is_never_the_only_gold_reference() -> None:
    recital = {"act": "ai-act", "ref": "Recital 12"}
    assert _errors(_question(gold_refs=[recital])) == [
        "q001: a recital is never the only gold reference"
    ]
    assert _errors(_question(gold_refs=[{"act": "ai-act", "ref": "Art. 3"}, recital])) == []


def test_source_text_holds_only_a_different_original_wording() -> None:
    assert _errors(_question(source_text="when does high risk apply")) == []
    same = _question()["question"]
    assert _errors(_question(source_text=same)) == [
        "q001: source_text repeats the question, leave it empty"
    ]


def test_a_point_is_either_required_or_optional() -> None:
    assert _errors(_question(optional_points=["2 December 2027"])) == [
        "q001: answer point listed as required and optional: 2 December 2027"
    ]


def test_ids_are_unique_and_references_not_repeated() -> None:
    ref = {"act": "gdpr", "ref": "Art. 9"}
    assert _errors(_question(gold_refs=[ref, ref]), _question()) == [
        "q001: gold reference gdpr Art. 9 listed twice",
        "q001: duplicate id",
    ]


# --- The committed test set ----------------------------------------------------------------


@pytest.mark.parametrize("name", ["dev.jsonl", "test.jsonl"])
def test_committed_split_is_valid(name: str) -> None:
    """Done criterion of phase 2: every gold reference exists in the corpus."""
    path = TESTSET / name
    if not path.exists():
        pytest.skip(f"{name} not written yet")
    assert validate(load_testset(path), CORPUS) == []


def test_corpus_lookup_returns_text_and_source() -> None:
    hit = CORPUS.lookup(GoldRef("ai-act", "Art. 5(1)(ba)"), "2026-11-27")
    assert hit.celex == "02024R1689-20260727"
    assert hit.blocks
