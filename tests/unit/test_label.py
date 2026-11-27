"""The interactive labelling helper, driven by scripted input."""

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from verbatim.evaluation.label import label_pass1, label_pass2, parse_candidates
from verbatim.evaluation.testset import CATEGORIES, Corpus, GoldRef, load_testset

ROOT = Path(__file__).parents[2]
CORPUS = Corpus.load(ROOT / "data" / "processed")

CANDIDATES = """# Candidate questions

Intro text.

## definition

1. How does the AI Act define an "AI system"?
2. Who is a "deployer"
   under the AI Act?

## dates

3. Since when do the prohibitions apply?
"""


def _script(*answers: str) -> Callable[[str], str]:
    """Answer prompts in order, then behave like Ctrl-D."""
    remaining = iter(answers)

    def ask(prompt: str) -> str:
        try:
            return next(remaining)
        except StopIteration:
            raise EOFError from None

    return ask


def _run1(directory: Path, *answers: str, **options: object) -> str:
    output: list[str] = []
    label_pass1(directory, CORPUS, _script(*answers), output.append, **options)  # pyright: ignore[reportArgumentType]
    return "\n".join(output)


# Enter = label, keep category, default date, one reference (confirmed), one required point,
# no optional point, no note, save.
LABEL = ("", "", "", "Art. 3(1)", "", "", "A machine-based system (Art. 3(1))", "", "", "", "")


@pytest.fixture
def directory(tmp_path: Path) -> Path:
    (tmp_path / "candidates.md").write_text(CANDIDATES, encoding="utf-8")
    return tmp_path


def test_candidates_file_of_the_repo() -> None:
    path = ROOT / "eval" / "testset" / "labeling" / "candidates.md"
    candidates = parse_candidates(path.read_text("utf-8"))
    assert len(candidates) == 38
    assert {c.category for c in candidates} == set(CATEGORIES)
    assert candidates[3].text.endswith("for registration in the EU database?")  # wrapped line


def test_parse_candidates_joins_wrapped_lines() -> None:
    assert [(c.category, c.text) for c in parse_candidates(CANDIDATES)][1] == (
        "definition",
        'Who is a "deployer" under the AI Act?',
    )


def test_label_saves_one_question(directory: Path) -> None:
    _run1(directory, *LABEL, "q")
    [q] = load_testset(directory / "pass1.jsonl")
    assert (q.id, q.category, q.answerable, q.as_of) == ("q001", "definition", True, "2026-11-27")
    assert q.gold_refs == (GoldRef("ai-act", "Art. 3(1)"),)
    assert q.answer_points == ("A machine-based system (Art. 3(1))",)
    assert q.question == 'How does the AI Act define an "AI system"?'


def test_resume_continues_after_labelled_questions_and_keeps_lines(directory: Path) -> None:
    _run1(directory, *LABEL, "q")
    before = (directory / "pass1.jsonl").read_text("utf-8")
    output = _run1(directory, *LABEL, "q")
    assert 'Who is a "deployer"' in output
    assert (directory / "pass1.jsonl").read_text("utf-8").startswith(before)
    assert [q.id for q in load_testset(directory / "pass1.jsonl")] == ["q001", "q002"]


def test_aborting_in_the_middle_saves_nothing(directory: Path) -> None:
    _run1(directory, "", "", "", "Art. 3(1)")
    assert not (directory / "pass1.jsonl").exists()


def test_invalid_references_are_refused_with_a_reason(directory: Path) -> None:
    output = _run1(
        directory,
        "",
        "",
        "",
        "Art. 999",
        "Art. 43(1)(a)",
        "gdpr Art. 9",
        "",
        "",
        "point",
        "",
        "",
        "",
        "",
    )
    assert "not found" in output
    assert "ambiguous" in output
    [q] = load_testset(directory / "pass1.jsonl")
    assert q.gold_refs == (GoldRef("gdpr", "Art. 9"),)


def test_rewrite_keeps_the_original_wording(directory: Path) -> None:
    _run1(directory, "r", "What is an AI system under Article 3?", *LABEL[1:], "q")
    [q] = load_testset(directory / "pass1.jsonl")
    assert q.question == "What is an AI system under Article 3?"
    assert q.source_text == 'How does the AI Act define an "AI system"?'
    # the rewritten candidate counts as done
    assert 'Who is a "deployer"' in _run1(directory, "q")


def test_drop_records_the_reason_and_uses_up_an_id(directory: Path) -> None:
    _run1(directory, "d", "too | vague", *LABEL, "q")
    dropped = (directory / "dropped.md").read_text("utf-8")
    assert "| q001 | How does the AI Act define" in dropped
    assert "too \\| vague" in dropped
    assert [q.id for q in load_testset(directory / "pass1.jsonl")] == ["q002"]
    assert "Since when" in _run1(directory, "q")


def test_not_answerable_needs_no_reference(directory: Path) -> None:
    _run1(directory, "", "not_answerable", "", "", "", "", "", "", "q")
    [q] = load_testset(directory / "pass1.jsonl")
    assert (q.answerable, q.gold_refs, q.answer_points) == (False, (), ())


def test_edit_keeps_values_on_enter(directory: Path) -> None:
    _run1(directory, *LABEL, "q")
    # category, date, keep references, keep required, keep optional, new note, save
    _run1(directory, "", "", "", "", "", "checked", "", question_id="q001")
    [q] = load_testset(directory / "pass1.jsonl")
    assert q.notes == "checked"
    assert q.gold_refs == (GoldRef("ai-act", "Art. 3(1)"),)


def test_new_question_of_your_own(directory: Path) -> None:
    _run1(directory, "What is a provider?", "definition", *LABEL[2:], new=True)
    [q] = load_testset(directory / "pass1.jsonl")
    assert (q.question, q.category) == ("What is a provider?", "definition")


def test_pass2_never_reads_pass1_and_keeps_ids_and_order(directory: Path) -> None:
    blank: dict[str, Any] = {
        "category": "",
        "answerable": None,
        "as_of": "",
        "gold_refs": [],
        "answer_points": [],
        "optional_points": [],
        "notes": "",
        "source_text": "",
    }
    rows = [{"id": i, "question": f"Question {i}?", **blank} for i in ("q002", "q001")]
    pass2 = directory / "pass2.jsonl"
    pass2.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    (directory / "pass1.jsonl").write_text("not even json", encoding="utf-8")

    output: list[str] = []
    # label (Enter), category typed by the labeller, then as in LABEL
    answers = _script("", "definition", *LABEL[2:], "q")
    label_pass2(directory, CORPUS, answers, output.append)

    saved = [json.loads(line) for line in pass2.read_text("utf-8").splitlines()]
    assert [r["id"] for r in saved] == ["q002", "q001"]
    assert saved[0]["category"] == "definition"
    assert saved[1]["category"] == ""
    assert "Suggested" not in "\n".join(output)
    assert (directory / "pass1.jsonl").read_text("utf-8") == "not even json"


@pytest.mark.parametrize(
    ("typed", "expected"),
    [
        ("ANNEX IV", GoldRef("ai-act", "Annex IV")),
        ("annex viii,  section a, point 6", GoldRef("ai-act", "Annex VIII, Section A, point 6")),
        ("art. 5(1)(BA)", GoldRef("ai-act", "Art. 5(1)(ba)")),
        ("GDPR art. 9", GoldRef("gdpr", "Art. 9")),
    ],
)
def test_references_are_accepted_in_any_case(
    directory: Path, typed: str, expected: GoldRef
) -> None:
    _run1(directory, "", "", "", typed, "", "", "point", "", "", "", "", "q")
    [q] = load_testset(directory / "pass1.jsonl")
    assert q.gold_refs == (expected,)


def test_header_shows_progress_in_the_category(directory: Path) -> None:
    assert "definition: 0 of 2" in _run1(directory, "q")
    _run1(directory, *LABEL, "q")
    assert "definition: 1 of 2" in _run1(directory, "q")
