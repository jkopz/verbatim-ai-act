"""Data model of the corpus.

A document is a list of articles, annexes and recitals. Articles and annexes hold their text as
blocks in document order. A block's path locates it in the legal structure, for example
("1", "ba") for Article 5(1)(ba). An empty path is text directly under the article or annex.
Several blocks may share a path, for example the subparagraphs of one paragraph.
"""

import json
from collections.abc import Iterator
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class Block:
    path: tuple[str, ...]
    text: str


@dataclass(frozen=True, slots=True)
class Article:
    number: str
    title: str
    chapter: str | None
    chapter_title: str | None
    section: str | None
    section_title: str | None
    blocks: tuple[Block, ...]


@dataclass(frozen=True, slots=True)
class Annex:
    number: str
    title: str
    blocks: tuple[Block, ...]


@dataclass(frozen=True, slots=True)
class Recital:
    number: str
    text: str


@dataclass(frozen=True, slots=True)
class Document:
    act: str
    celex: str
    version_date: str
    status: str
    language: str
    url: str
    articles: tuple[Article, ...]
    annexes: tuple[Annex, ...]
    recitals: tuple[Recital, ...]

    def article(self, number: str) -> Article:
        return _find(self.articles, number, "article")

    def annex(self, number: str) -> Annex:
        return _find(self.annexes, number, "annex")

    def recital(self, number: str) -> Recital:
        return _find(self.recitals, number, "recital")


def _find[T: (Article, Annex, Recital)](items: tuple[T, ...], number: str, kind: str) -> T:
    for item in items:
        if item.number == number:
            return item
    raise KeyError(f"{kind} {number} not found")


# --- References ----------------------------------------------------------------------------


def article_ref(number: str, path: tuple[str, ...]) -> str:
    return f"Art. {number}" + "".join(f"({p})" for p in path)


def annex_ref(number: str, path: tuple[str, ...]) -> str:
    ref = f"Annex {number}"
    if path:
        ref += f", point {path[0]}" + "".join(f"({p})" for p in path[1:])
    return ref


def recital_ref(number: str) -> str:
    return f"Recital {number}"


def iter_references(doc: Document) -> Iterator[str]:
    """Every citable reference in the document, each once, in document order."""
    seen: set[str] = set()

    def emit(ref: str) -> Iterator[str]:
        if ref not in seen:
            seen.add(ref)
            yield ref

    for article in doc.articles:
        for path in ((), *(b.path for b in article.blocks)):
            for depth in range(len(path) + 1):
                yield from emit(article_ref(article.number, path[:depth]))
    for annex in doc.annexes:
        for path in ((), *(b.path for b in annex.blocks)):
            for depth in range(len(path) + 1):
                yield from emit(annex_ref(annex.number, path[:depth]))
    for recital in doc.recitals:
        yield from emit(recital_ref(recital.number))


# --- Serialisation -------------------------------------------------------------------------


def document_to_dict(doc: Document) -> dict[str, Any]:
    return asdict(doc)


def _blocks(data: Any) -> tuple[Block, ...]:
    return tuple(Block(path=tuple(b["path"]), text=b["text"]) for b in data)


def document_from_dict(data: Any) -> Document:
    return Document(
        act=data["act"],
        celex=data["celex"],
        version_date=data["version_date"],
        status=data["status"],
        language=data["language"],
        url=data["url"],
        articles=tuple(
            Article(
                number=a["number"],
                title=a["title"],
                chapter=a["chapter"],
                chapter_title=a["chapter_title"],
                section=a["section"],
                section_title=a["section_title"],
                blocks=_blocks(a["blocks"]),
            )
            for a in data["articles"]
        ),
        annexes=tuple(
            Annex(number=a["number"], title=a["title"], blocks=_blocks(a["blocks"]))
            for a in data["annexes"]
        ),
        recitals=tuple(Recital(number=r["number"], text=r["text"]) for r in data["recitals"]),
    )


def save_document(doc: Document, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(document_to_dict(doc), ensure_ascii=False, indent=1)
    path.write_text(text + "\n", encoding="utf-8")


def load_document(path: Path) -> Document:
    return document_from_dict(json.loads(path.read_text(encoding="utf-8")))
