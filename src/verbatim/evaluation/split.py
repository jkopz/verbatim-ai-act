"""Split the reconciled test set into dev and test, once.

The dev split is for development and the smoke evaluation in CI. The test split is opened only
for final results and is never rewritten, so this refuses to overwrite either file.
"""

import math
import random
from collections import defaultdict
from pathlib import Path

from verbatim.evaluation.testset import Question, load_testset, save_testset


def split(
    questions: list[Question], dev_size: int, seed: int
) -> tuple[list[Question], list[Question]]:
    """Stratified by category: each category goes to dev in proportion to `dev_size`.

    Rounding remainders are given to the categories with the largest fractional part, ties
    broken at random, so no category is systematically favoured.
    """
    if not 0 < dev_size < len(questions):
        raise ValueError("dev_size must be between 0 and the number of questions")
    rng = random.Random(seed)
    groups: dict[str, list[Question]] = defaultdict(list)
    for q in questions:
        groups[q.category].append(q)
    categories = sorted(groups)
    for category in categories:
        rng.shuffle(groups[category])

    quotas = {c: len(groups[c]) * dev_size / len(questions) for c in categories}
    take = {c: math.floor(quotas[c]) for c in categories}
    tiebreak = {c: rng.random() for c in categories}
    by_remainder = sorted(
        categories, key=lambda c: (quotas[c] - take[c], tiebreak[c]), reverse=True
    )
    for c in by_remainder[: dev_size - sum(take.values())]:
        take[c] += 1

    dev_ids = {q.id for c in categories for q in groups[c][: take[c]]}
    dev = [q for q in questions if q.id in dev_ids]
    test = [q for q in questions if q.id not in dev_ids]
    return dev, test


def write_split(source: Path, out_dir: Path, dev_size: int, seed: int) -> None:
    """Write dev.jsonl and test.jsonl from `source`, then delete `source`.

    The reconciled file is a working copy. After the split, dev.jsonl and test.jsonl are the
    only copy of the gold set, so the two cannot drift apart.
    """
    dev_path, test_path = out_dir / "dev.jsonl", out_dir / "test.jsonl"
    for path in (dev_path, test_path):
        if path.exists():
            raise FileExistsError(f"{path} exists. The split is written once and never redone.")
    dev, test = split(load_testset(source), dev_size, seed)
    save_testset(dev_path, dev)
    save_testset(test_path, test)
    source.unlink()
