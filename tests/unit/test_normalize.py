import pytest

from verbatim.ingestion.normalize import clean_text, fold_for_match


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("1.   The  following\n practices", "1. The following practices"),
        ("  leading and trailing  ", "leading and trailing"),
        ("▼M1 inserted text", "inserted text"),
        ("►C1 The accreditation ◄ of bodies", "The accreditation of bodies"),
        ("▼B", ""),
        ("of the Council () and without", "of the Council and without"),
        ("of the Council ;", "of the Council;"),
        ("Article 6(2) and Annex III", "Article 6(2) and Annex III"),
    ],
)
def test_clean_text(raw: str, expected: str) -> None:
    assert clean_text(raw) == expected


def test_clean_text_keeps_typographic_quotes() -> None:
    # The corpus stores the text as published. Folding happens only for matching.
    assert clean_text("‘AI system’ means") == "‘AI system’ means"


def test_clean_text_is_idempotent() -> None:
    raw = "►C1 a  b ()  ; ◄"
    assert clean_text(clean_text(raw)) == clean_text(raw)


@pytest.mark.parametrize(
    ("left", "right"),
    [
        ("‘AI system’ means", "'AI system' means"),
        ("“provider” means", '"provider" means'),
        ("2024–2026 — see", "2024-2026 - see"),
        ("a  b", "a b"),
    ],
)
def test_fold_for_match_treats_typographic_variants_as_equal(left: str, right: str) -> None:
    assert fold_for_match(left) == fold_for_match(right)


def test_fold_for_match_keeps_case_and_wording() -> None:
    assert fold_for_match("Shall") != fold_for_match("shall")
    assert fold_for_match("may") != fold_for_match("shall")
