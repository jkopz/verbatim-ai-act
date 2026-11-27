"""The gold test set: schema, file format and validation against the corpus.

A test set is a JSONL file with one question per line. See eval/testset/labeling-guide.md for
the meaning of each field and the rules for labelling.
"""

import datetime
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from verbatim.ingestion.models import (
    Block,
    Document,
    ambiguous_references,
    load_document,
    reference_index,
)

CATEGORIES = (
    "fact_lookup",
    "definition",
    "dates",
    "risk_classification",
    "multi_step",
    "not_answerable",
    "false_premise",
    "legal_advice",
)
ACTS = ("ai-act", "gdpr")
FIELDS = (
    "id",
    "question",
    "category",
    "answerable",
    "as_of",
    "gold_refs",
    "answer_points",
    "optional_points",
    "notes",
    "source_text",
)


class InvalidTestsetError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class GoldRef:
    act: str
    ref: str

    def __str__(self) -> str:
        return f"{self.act} {self.ref}"


@dataclass(frozen=True, slots=True)
class Question:
    id: str
    question: str
    category: str
    answerable: bool
    as_of: str
    gold_refs: tuple[GoldRef, ...]
    answer_points: tuple[str, ...]
    notes: str
    optional_points: tuple[str, ...] = ()
    source_text: str = ""


# --- Parsing -------------------------------------------------------------------------------


def _string(data: dict[str, Any], key: str, *, allow_empty: bool = False) -> str:
    value = data[key]
    if not isinstance(value, str) or (not allow_empty and not value.strip()):
        raise InvalidTestsetError(f"{key} must be a non-empty string")
    return value


def _gold_ref(item: Any) -> GoldRef:
    if not isinstance(item, dict) or set(item) != {"act", "ref"}:  # pyright: ignore[reportUnknownArgumentType]
        raise InvalidTestsetError('each entry of gold_refs must be {"act": ..., "ref": ...}')
    entry: dict[str, Any] = item  # pyright: ignore[reportUnknownVariableType]
    if entry["act"] not in ACTS:
        raise InvalidTestsetError(f"act must be one of {', '.join(ACTS)}, got {entry['act']!r}")
    return GoldRef(act=entry["act"], ref=_string(entry, "ref"))


def _list(data: dict[str, Any], key: str) -> list[Any]:
    value = data[key]
    if not isinstance(value, list):
        raise InvalidTestsetError(f"{key} must be a list")
    return value  # pyright: ignore[reportUnknownVariableType]


def _points(data: dict[str, Any], key: str) -> tuple[str, ...]:
    points = _list(data, key)
    if not all(isinstance(p, str) and p.strip() for p in points):
        raise InvalidTestsetError(f"{key} must be non-empty strings")
    return tuple(points)


def parse_question(data: Any) -> Question:
    if not isinstance(data, dict):
        raise InvalidTestsetError("each line must be a JSON object")
    fields: dict[str, Any] = data  # pyright: ignore[reportUnknownVariableType]
    if unknown := sorted(set(fields) - set(FIELDS)):
        raise InvalidTestsetError(f"unknown field {', '.join(unknown)}")
    if missing := [f for f in FIELDS if f not in fields]:
        raise InvalidTestsetError(f"missing field {', '.join(missing)}")

    category = fields["category"]
    if category not in CATEGORIES:
        choices = ", ".join(CATEGORIES)
        raise InvalidTestsetError(f"category must be one of {choices}, got {category!r}")
    answerable = fields["answerable"]
    if not isinstance(answerable, bool):
        raise InvalidTestsetError("answerable must be true or false")
    as_of = _string(fields, "as_of")
    try:
        datetime.date.fromisoformat(as_of)
    except ValueError:
        raise InvalidTestsetError(f"as_of must be a date like 2026-11-27, got {as_of!r}") from None
    points = _points(fields, "answer_points")
    optional = _points(fields, "optional_points")

    return Question(
        id=_string(fields, "id"),
        question=_string(fields, "question"),
        category=category,
        answerable=answerable,
        as_of=as_of,
        gold_refs=tuple(_gold_ref(item) for item in _list(fields, "gold_refs")),
        answer_points=points,
        notes=_string(fields, "notes", allow_empty=True),
        optional_points=optional,
        source_text=_string(fields, "source_text", allow_empty=True),
    )


def load_testset(path: Path) -> list[Question]:
    questions: list[Question] = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            questions.append(parse_question(json.loads(line)))
        except (InvalidTestsetError, json.JSONDecodeError) as error:
            raise InvalidTestsetError(f"{path.name}:{number}: {error}") from None
    return questions


def question_to_dict(question: Question) -> dict[str, Any]:
    data = asdict(question)
    return {field: data[field] for field in FIELDS}


def save_testset(path: Path, questions: list[Question]) -> None:
    lines = [json.dumps(question_to_dict(q), ensure_ascii=False) for q in questions]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(line + "\n" for line in lines), encoding="utf-8")


# --- The corpus, by version ----------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Hit:
    ref: GoldRef
    celex: str
    version_date: str
    url: str
    blocks: tuple[Block, ...]


@dataclass(frozen=True, slots=True)
class _Version:
    doc: Document
    index: dict[str, list[Block]]
    ambiguous: frozenset[str]


class Corpus:
    """The processed documents, chosen by act, kind of reference and as-of date."""

    def __init__(self, documents: list[Document]) -> None:
        self._versions = [
            _Version(d, reference_index(d), frozenset(ambiguous_references(d))) for d in documents
        ]

    @classmethod
    def load(cls, processed_dir: Path) -> "Corpus":
        return cls([load_document(p) for p in sorted(processed_dir.glob("*.json"))])

    def _version(self, ref: GoldRef, as_of: str) -> _Version | None:
        """The text in force on `as_of`.

        Recitals exist only in the Official Journal. Everything else comes from the latest
        version dated on or before `as_of`, preferring the consolidated text on the same date.
        """
        candidates = [
            v for v in self._versions if v.doc.act == ref.act and v.doc.version_date <= as_of
        ]
        if ref.ref.startswith("Recital "):
            candidates = [v for v in candidates if v.doc.status == "official-journal"]
        if not candidates:
            return None
        return max(candidates, key=lambda v: (v.doc.version_date, v.doc.status == "consolidated"))

    def lookup(self, ref: GoldRef, as_of: str) -> Hit:
        version = self._version(ref, as_of)
        if version is None:
            raise KeyError(f"no {ref.act} text in force on {as_of}")
        if ref.ref not in version.index:
            raise KeyError(f"{ref} not found in {version.doc.celex}")
        doc = version.doc
        return Hit(ref, doc.celex, doc.version_date, doc.url, tuple(version.index[ref.ref]))

    def problem(self, ref: GoldRef, as_of: str) -> str | None:
        """Why `ref` cannot serve as a gold reference on `as_of`, or None if it can."""
        version = self._version(ref, as_of)
        if version is None:
            return f"no {ref.act} text in force on {as_of}"
        if ref.ref not in version.index:
            return f"{ref} not found in {version.doc.celex}"
        if ref.ref in version.ambiguous:
            return f"{ref} is ambiguous, cite the enclosing level"
        return None


# --- Validation ----------------------------------------------------------------------------


def validate(questions: list[Question], corpus: Corpus) -> list[str]:
    """All problems of a test set, one message per problem. An empty list means valid."""
    errors: list[str] = []
    seen_ids: set[str] = set()
    for q in questions:

        def error(message: str, q: Question = q) -> None:
            errors.append(f"{q.id}: {message}")

        if q.id in seen_ids:
            error("duplicate id")
        seen_ids.add(q.id)

        if not q.answerable and q.category != "not_answerable":
            error("answerable is false, so category must be not_answerable")
        if q.answerable and q.category == "not_answerable":
            error("category not_answerable requires answerable false")
        if q.answerable and not q.gold_refs:
            error("answerable question needs at least one gold reference")
        if q.answerable and not q.answer_points:
            error("answerable question needs at least one answer point")
        for point in q.optional_points:
            if point in q.answer_points:
                error(f"answer point listed as required and optional: {point}")
        if q.source_text and q.source_text == q.question:
            error("source_text repeats the question, leave it empty")
        if q.gold_refs and all(r.ref.startswith("Recital ") for r in q.gold_refs):
            error("a recital is never the only gold reference")

        seen_refs: set[GoldRef] = set()
        for ref in q.gold_refs:
            if ref in seen_refs:
                error(f"gold reference {ref} listed twice")
                continue
            seen_refs.add(ref)
            if problem := corpus.problem(ref, q.as_of):
                error(problem)
    return errors
