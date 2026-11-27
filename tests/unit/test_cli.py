"""The labelling workflow end to end, on a tiny test set in a temporary directory."""

import json
from pathlib import Path
from typing import Any

import pytest

from verbatim.evaluation import cli


@pytest.fixture(autouse=True)
def _corpus_from_repo(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cli, "PROCESSED", Path(__file__).parents[2] / "data" / "processed")


def _write(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text("".join(json.dumps(r) + "\n" for r in rows))


def _row(id: str, ref: str) -> dict[str, Any]:
    return {
        "id": id,
        "question": f"Question {id}?",
        "category": "fact_lookup",
        "answerable": True,
        "as_of": "2026-11-27",
        "gold_refs": [{"act": "ai-act", "ref": ref}],
        "answer_points": ["point"],
        "optional_points": [],
        "notes": "",
        "source_text": "",
    }


def test_check_reports_errors_with_file_name(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _write(tmp_path / "pass1.jsonl", [_row("q1", "Art. 5"), _row("q2", "Art. 999")])
    assert cli.main(["check", str(tmp_path / "pass1.jsonl")]) == 1
    assert "pass1.jsonl: q2: ai-act Art. 999 not found" in capsys.readouterr().err


def test_lookup_rejects_an_ambiguous_reference(capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["lookup", "ai-act", "Art. 5(1)(a)", "--as-of", "2026-11-27"]) == 0
    assert cli.main(["lookup", "ai-act", "Art. 43(1)(a)", "--as-of", "2026-11-27"]) == 1
    assert "ambiguous" in capsys.readouterr().err


def test_template_agreement_and_split(tmp_path: Path) -> None:
    pass1, pass2 = tmp_path / "pass1.jsonl", tmp_path / "pass2.jsonl"
    rows = [_row(f"q{i:02d}", "Art. 5") for i in range(20)]
    _write(pass1, rows)

    assert cli.main(["template", str(pass1), str(pass2)]) == 0
    template = [json.loads(line) for line in pass2.read_text().splitlines()]
    assert all(t["gold_refs"] == [] and t["category"] == "" for t in template)
    assert cli.main(["template", str(pass1), str(pass2)]) == 1  # never overwrites

    _write(pass2, rows[:-1] + [_row("q19", "Art. 6")])
    assert cli.main(["agreement", str(pass1), str(pass2), str(tmp_path / "agreement.md")]) == 0
    assert "| q19 | gold_refs | ai-act Art. 5 | ai-act Art. 6 |" in (
        (tmp_path / "agreement.md").read_text()
    )

    reconciled = tmp_path / "reconciled.jsonl"
    _write(reconciled, rows)
    assert cli.main(["split", str(reconciled), str(tmp_path)]) == 0
    assert (tmp_path / "dev.jsonl").exists() and (tmp_path / "test.jsonl").exists()
    _write(reconciled, rows)
    assert cli.main(["split", str(reconciled), str(tmp_path)]) == 1
