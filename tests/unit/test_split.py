from collections import Counter
from dataclasses import replace
from pathlib import Path

import pytest

from verbatim.evaluation.split import split, write_split
from verbatim.evaluation.testset import GoldRef, Question, load_testset, save_testset


def _questions() -> list[Question]:
    base = Question(
        id="",
        question="?",
        category="",
        answerable=True,
        as_of="2026-11-27",
        gold_refs=(GoldRef("ai-act", "Art. 5"),),
        answer_points=("point",),
        notes="",
    )
    # 30 questions: 7 + 5 + 4 + 4 + 4 + 2 + 2 + 2 over the eight categories
    sizes = {
        "fact_lookup": 7,
        "definition": 5,
        "dates": 4,
        "risk_classification": 4,
        "multi_step": 4,
        "not_answerable": 2,
        "false_premise": 2,
        "legal_advice": 2,
    }
    out: list[Question] = []
    for category, size in sizes.items():
        for _ in range(size):
            out.append(replace(base, id=f"q{len(out) + 1:03d}", category=category))
    return out


def test_split_is_stratified_by_category() -> None:
    dev, test = split(_questions(), dev_size=15, seed=7)
    assert (len(dev), len(test)) == (15, 15)
    assert {q.id for q in dev}.isdisjoint(q.id for q in test)
    dev_counts = Counter(q.category for q in dev)
    for category, total in Counter(q.category for q in _questions()).items():
        assert abs(2 * dev_counts[category] - total) <= 1  # half of each, rounded


def test_split_is_reproducible_and_depends_on_the_seed() -> None:
    assert split(_questions(), 15, seed=7) == split(_questions(), 15, seed=7)
    assert split(_questions(), 15, seed=7) != split(_questions(), 15, seed=8)


def test_split_keeps_the_original_order_within_each_part() -> None:
    dev, test = split(_questions(), 15, seed=7)
    assert [q.id for q in dev] == sorted(q.id for q in dev)
    assert [q.id for q in test] == sorted(q.id for q in test)


def test_write_split_never_overwrites(tmp_path: Path) -> None:
    source = tmp_path / "reconciled.jsonl"
    save_testset(source, _questions())
    write_split(source, tmp_path, dev_size=15, seed=7)
    assert not source.exists()  # consumed: dev.jsonl and test.jsonl are now the gold set
    assert len(load_testset(tmp_path / "dev.jsonl")) == 15
    assert len(load_testset(tmp_path / "test.jsonl")) == 15

    save_testset(source, _questions())
    with pytest.raises(FileExistsError):
        write_split(source, tmp_path, dev_size=15, seed=7)
    assert source.exists()
