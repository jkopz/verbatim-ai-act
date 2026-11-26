"""Parser for EUR-Lex HTML into the corpus model.

EUR-Lex uses two layouts, and the parser handles both in one recursive walk:

| Structure | Official Journal                    | Consolidated text                   |
| --------- | ----------------------------------- | ----------------------------------- |
| Paragraph | div id="005.001", "1.   " in text   | div.norm with span.no-parag "1."    |
| Point     | two-column table, label in 1st cell | div.grid-list, label in column 1    |
| Headings  | p.oj-ti-section-1 / -2              | p.title-division-1 / -2             |
| Footnote  | a > span.oj-note-tag                | a > span.superscript                |

Amendment markers (p.modref, inline ►C1 ... ◄) are dropped. Deleted provisions in consolidated
texts consist only of a marker and a dash line, so they disappear with it.
"""

import re
from collections.abc import Iterator

from bs4 import BeautifulSoup, Comment, Tag
from bs4.element import NavigableString

from verbatim.ingestion.models import Annex, Article, Block, Document, Recital
from verbatim.ingestion.normalize import clean_text
from verbatim.ingestion.sources import Source

_ARTICLE_ID = re.compile(r"^art_(\d+[a-z]*)$")
_ANNEX_ID = re.compile(r"^anx_([A-Z]+)$")
_RECITAL_ID = re.compile(r"^rct_(\d+)$")
_OJ_PARAGRAPH_ID = re.compile(r"^\d{3}\.\d{3}$")
_OJ_PARAGRAPH_LABEL = re.compile(r"^(\d+[a-z]*)\.(?:\s+|$)")
# (a) (ba) (iii) (1) 1. 1a. A.
_POINT_LABEL = re.compile(r"^\(?(\d+[a-z]*|[a-z]{1,4}|[A-Z])\)?\.?$")
_DASHES = {"—", "–", "-", "•"}

_HEADING_1 = {"oj-ti-section-1", "title-division-1"}
_HEADING_2 = {"oj-ti-section-2", "title-division-2"}
_SKIP = {
    # titles, read separately
    "oj-ti-art",
    "oj-sti-art",
    "title-article-norm",
    "stitle-article-norm",
    "eli-title",
    "oj-doc-ti",
    "title-annex-1",
    "title-annex-2",
    # footnotes and amendment markers
    "oj-note",
    "footnote",
    "modref",
    "arrow",
    # paragraph number, read by the paragraph rule
    "no-parag",
}


def parse_document(html: str, source: Source) -> Document:
    soup = BeautifulSoup(html, "html.parser")
    _remove_footnote_references(soup)
    _mark_superscripts(soup)

    articles: list[Article] = []
    annexes: list[Annex] = []
    recitals: list[Recital] = []
    chapter = chapter_title = section = section_title = None
    pending: str | None = None

    for el in soup.find_all(_is_relevant):
        el_id = str(el.get("id", ""))
        cls = _classes(el)
        if cls & _HEADING_1:
            heading = clean_text(el.get_text())
            kind, _, number = heading.partition(" ")
            if kind.upper() == "CHAPTER":
                chapter, chapter_title, section, section_title = number, None, None, None
                pending = "chapter"
            elif kind.upper() == "SECTION":
                section, section_title = number, None
                pending = "section"
        elif cls & _HEADING_2:
            title = clean_text(el.get_text())
            if pending == "chapter":
                chapter_title = title
            elif pending == "section":
                section_title = title
            pending = None
        elif m := _ARTICLE_ID.match(el_id):
            articles.append(
                Article(
                    number=m.group(1),
                    title=_title(el, {"oj-sti-art", "stitle-article-norm"}),
                    chapter=chapter,
                    chapter_title=chapter_title,
                    section=section,
                    section_title=section_title,
                    blocks=tuple(_walk(el, ())),
                )
            )
        elif m := _ANNEX_ID.match(el_id):
            annexes.append(
                Annex(number=m.group(1), title=_annex_title(el), blocks=tuple(_walk(el, ())))
            )
        elif m := _RECITAL_ID.match(el_id):
            text = clean_text(" ".join(b.text for b in _walk(el, ())))
            recitals.append(Recital(number=m.group(1), text=text))

    return Document(
        act=source.act,
        celex=source.celex,
        version_date=source.version_date,
        status=source.status,
        language=source.language,
        url=source.url,
        articles=tuple(articles),
        annexes=tuple(annexes),
        recitals=tuple(recitals),
    )


# --- Document-level helpers ----------------------------------------------------------------


def _classes(tag: Tag) -> set[str]:
    value = tag.get("class")
    if value is None:
        return set()
    if isinstance(value, str):
        return set(value.split())
    return set(value)


def _is_relevant(tag: Tag) -> bool:
    if tag.name == "p":
        return bool(_classes(tag) & (_HEADING_1 | _HEADING_2))
    if tag.name == "div":
        el_id = str(tag.get("id", ""))
        return bool(_ARTICLE_ID.match(el_id) or _ANNEX_ID.match(el_id) or _RECITAL_ID.match(el_id))
    return False


def _remove_footnote_references(soup: BeautifulSoup) -> None:
    for a in soup.find_all("a"):
        href = a.get("href")
        is_internal = isinstance(href, str) and href.startswith("#")
        if is_internal and a.find("span", class_=["oj-note-tag", "oj-super", "superscript"]):
            a.decompose()


def _mark_superscripts(soup: BeautifulSoup) -> None:
    """Keep exponents readable: 10<sup>25</sup> becomes 10^25 instead of 1025."""
    for span in soup.find_all("span", class_=["oj-super", "superscript"]):
        span.replace_with("^" + span.get_text().strip())


def _title(article: Tag, classes: set[str]) -> str:
    el = article.find(lambda t: t.name == "p" and bool(_classes(t) & classes))
    return clean_text(el.get_text()) if el else ""


def _annex_title(annex: Tag) -> str:
    """Title lines after "ANNEX III". Consolidated texts sometimes use title-annex-1 for both."""
    lines = annex.find_all("p", class_=["oj-doc-ti", "title-annex-1", "title-annex-2"])
    return clean_text(" ".join(p.get_text() for p in lines[1:]))


# --- The structural walk -------------------------------------------------------------------

_INLINE = {"span", "a", "em", "strong", "i", "b", "sup", "sub", "abbr", "br"}
_QUOTES = ("‘", "'", "“", '"')


def _walk(node: Tag, path: tuple[str, ...]) -> Iterator[Block]:
    """Yield the text blocks below `node`.

    Inline content is collected until the next block-level element, so that text split by
    spans (italics, exponents) stays one block. After a paragraph, following siblings belong
    to that paragraph until the next one starts: consolidated texts place later
    subparagraphs and points next to the paragraph's div instead of inside it.
    """
    current = path
    inline: list[str] = []
    for child in node.children:
        if isinstance(child, Comment):
            continue
        if isinstance(child, NavigableString):
            inline.append(str(child))
            continue
        if not isinstance(child, Tag) or _classes(child) & _SKIP:
            continue
        if child.name in _INLINE:
            inline.append(child.get_text())
            continue
        if text := clean_text("".join(inline)):
            yield Block(current, text)
        inline = []
        label = _paragraph_label(child)
        if label is None:
            yield from _walk_tag(child, current)
        else:
            current = (*path, label)
            yield from _paragraph(child, current)
    if text := clean_text("".join(inline)):
        yield Block(current, text)


def _paragraph_label(tag: Tag) -> str | None:
    """The paragraph number if `tag` is a numbered paragraph of this act, else None."""
    if tag.name != "div":
        return None
    if _OJ_PARAGRAPH_ID.match(str(tag.get("id", ""))):
        first = tag.find("p")
        m = _OJ_PARAGRAPH_LABEL.match(clean_text(first.get_text())) if first else None
        return m.group(1) if m else None
    span = tag.find("span", class_="no-parag", recursive=False)
    if span is None:
        return None
    label = clean_text(span.get_text())
    if label.startswith(_QUOTES):  # a paragraph quoted from another act
        return None
    return label.rstrip(".")


def _paragraph(tag: Tag, path: tuple[str, ...]) -> Iterator[Block]:
    blocks = list(_walk(tag, path))
    if blocks and _OJ_PARAGRAPH_ID.match(str(tag.get("id", ""))):
        # Official Journal: the number is part of the first text ("1.   The following ...")
        first = blocks[0]
        blocks[0] = Block(first.path, _OJ_PARAGRAPH_LABEL.sub("", first.text, count=1))
        blocks = [b for b in blocks if b.text]
    yield from blocks


def _walk_tag(tag: Tag, path: tuple[str, ...]) -> Iterator[Block]:
    cls = _classes(tag)

    # Paragraph quoted from another act, kept as text: <span class="no-parag">‘5.</span>
    if tag.name == "div" and (span := tag.find("span", class_="no-parag", recursive=False)):
        blocks = list(_walk(tag, path))
        if blocks:
            label = clean_text(span.get_text())
            blocks[0] = Block(blocks[0].path, f"{label} {blocks[0].text}")
        yield from blocks

    # Consolidated point: <div class="grid-container grid-list"> label | content
    elif tag.name == "div" and {"grid-container", "grid-list"} <= cls:
        label_el = tag.find("div", class_="grid-list-column-1", recursive=False)
        content = tag.find("div", class_="grid-list-column-2", recursive=False)
        label = _point_label(label_el.get_text()) if label_el else None
        if content is None or label is None:
            yield from _walk(tag, path)
        else:
            yield from _walk(content, (*path, *label))

    # Official Journal point: <table><tr><td>(a)</td><td>text</td></tr></table>
    elif tag.name == "table":
        yield from _oj_table(tag, path)

    else:
        yield from _walk(tag, path)


def _oj_table(table: Tag, path: tuple[str, ...]) -> Iterator[Block]:
    body = table.find("tbody", recursive=False) or table
    for row in body.find_all("tr", recursive=False):
        cells = row.find_all("td", recursive=False)
        label = _point_label(cells[0].get_text()) if len(cells) == 2 else None
        if label is None:
            yield from _walk(row, path)
        else:
            yield from _walk(cells[1], (*path, *label))


def _point_label(text: str) -> tuple[str, ...] | None:
    """("a",) for "(a)", () for an indent dash, None if the cell is not a label."""
    text = clean_text(text)
    if text in _DASHES:
        return ()
    m = _POINT_LABEL.match(text)
    return (m.group(1),) if m else None
