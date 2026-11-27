"""Label the gold test set question by question in the terminal.

The tool handles ids, the file format and validation. Every label is typed by the person
labelling; nothing is suggested except the category of a candidate question in pass 1 and the
default as-of date. A question is saved as a whole, so stopping in the middle loses only that
question.
"""

import datetime
import json
import os
import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from verbatim.evaluation.testset import (
    CATEGORIES,
    DEFAULT_AS_OF,
    Corpus,
    GoldRef,
    InvalidTestsetError,
    Question,
    load_testset,
    parse_question,
    question_to_dict,
    validate,
)

Ask = Callable[[str], str]
Say = Callable[[str], None]

PREVIEW_BLOCKS = 8
PREVIEW_CHARS = 300
_DROPPED_ROW = re.compile(r"^\| (q\d+) \| (.*?) (?<!\\)\| .* \|$")
_DROPPED_HEADER = "# Dropped questions\n\n| Id | Question | Reason |\n| --- | --- | --- |\n"


@dataclass(frozen=True, slots=True)
class Candidate:
    category: str
    text: str


def parse_candidates(markdown: str) -> list[Candidate]:
    """Numbered items below "## <category>" headings. Indented lines continue an item."""
    items: list[tuple[str, list[str]]] = []
    category = None
    open_item = False
    for line in markdown.splitlines():
        if line.startswith("## "):
            category, open_item = line[3:].strip(), False
        elif category and (m := re.match(r"^\d+\.\s+(.*)", line)):
            items.append((category, [m.group(1)]))
            open_item = True
        elif open_item and line.startswith(" ") and line.strip():
            items[-1][1].append(line.strip())
        else:
            open_item = False
    return [Candidate(c, " ".join(parts)) for c, parts in items]


# --- Files ---------------------------------------------------------------------------------


def _read_lines(path: Path) -> list[str]:
    if not path.exists():
        return []
    return [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _write_atomically(path: Path, text: str) -> None:
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(text, encoding="utf-8")
    os.replace(temporary, path)


def _save_line(path: Path, question: Question, index: int | None) -> None:
    """Replace line `index`, or append. All other lines stay byte for byte."""
    lines = _read_lines(path)
    line = json.dumps(question_to_dict(question), ensure_ascii=False)
    if index is None:
        lines.append(line)
    else:
        lines[index] = line
    _write_atomically(path, "".join(item + "\n" for item in lines))


def _dropped(path: Path) -> list[tuple[str, str]]:
    """(id, question) of every dropped question."""
    rows = (_DROPPED_ROW.match(line) for line in _read_lines(path))
    return [(m.group(1), m.group(2).replace("\\|", "|")) for m in rows if m]


def _add_dropped(path: Path, question_id: str, text: str, reason: str) -> None:
    content = path.read_text(encoding="utf-8") if path.exists() else _DROPPED_HEADER
    cells = [c.replace("|", "\\|") for c in (question_id, text, reason)]
    _write_atomically(path, content.rstrip("\n") + f"\n| {' | '.join(cells)} |\n")


def _next_id(used: list[str]) -> str:
    numbers = [int(i[1:]) for i in used if re.fullmatch(r"q\d+", i)]
    return f"q{max(numbers, default=0) + 1:03d}"


# --- Prompts -------------------------------------------------------------------------------


def _yes(ask: Ask, prompt: str) -> bool:
    return ask(f"{prompt} [Y/n] ").strip().lower() not in ("n", "no")


def _ask_category(ask: Ask, say: Say, default: str | None) -> str:
    say("Categories: " + ", ".join(f"{i} {c}" for i, c in enumerate(CATEGORIES, start=1)))
    while True:
        hint = f" [{default}]" if default else ""
        answer = ask(f"Category{hint}: ").strip() or default or ""
        if answer.isdigit() and 0 < int(answer) <= len(CATEGORIES):
            return CATEGORIES[int(answer) - 1]
        if answer in CATEGORIES:
            return answer
        say("Enter a number or a name from the list.")


def _ask_date(ask: Ask, say: Say, default: str) -> str:
    while True:
        answer = ask(f"As-of date [{default}]: ").strip() or default
        try:
            return datetime.date.fromisoformat(answer).isoformat()
        except ValueError:
            say("Use the form 2026-11-27.")


def _parse_ref(text: str) -> GoldRef:
    """ "gdpr Art. 9" names the act, a bare reference belongs to the AI Act."""
    act, _, rest = text.partition(" ")
    if act.lower() in ("gdpr", "ai-act"):
        return GoldRef(act.lower(), rest.strip())
    return GoldRef("ai-act", text)


def _show_text(say: Say, corpus: Corpus, ref: GoldRef, as_of: str) -> None:
    hit = corpus.lookup(ref, as_of)
    say(f"  {ref} in the version of {hit.version_date}:")
    for block in hit.blocks[:PREVIEW_BLOCKS]:
        label = "".join(f"({p})" for p in block.path)
        text = f"{label} {block.text}".strip()
        if len(text) > PREVIEW_CHARS:
            text = text[:PREVIEW_CHARS] + " ..."
        say(f"    {text}")
    if len(hit.blocks) > PREVIEW_BLOCKS:
        say(f"    ... {len(hit.blocks) - PREVIEW_BLOCKS} more blocks (make lookup shows all)")


def _ask_refs(
    ask: Ask, say: Say, corpus: Corpus, as_of: str, answerable: bool
) -> tuple[GoldRef, ...]:
    say('Gold references, one per line, for example "Art. 6(2)" or "gdpr Art. 9".')
    say('Empty line: done. "-": remove the last one.')
    refs: list[GoldRef] = []
    while True:
        text = ask("Reference: ").strip()
        if not text:
            if refs or not answerable:
                return tuple(refs)
            say("An answerable question needs at least one reference.")
        elif text == "-":
            if refs:
                say(f"  removed {refs.pop()}")
        else:
            ref = corpus.spelling(_parse_ref(text), as_of)
            if ref in refs:
                say("  already listed")
            elif problem := corpus.problem(ref, as_of):
                say(f"  {problem}")
            else:
                _show_text(say, corpus, ref, as_of)
                if _yes(ask, "  Use it?"):
                    refs.append(ref)


def _ask_points(ask: Ask, say: Say, title: str, required: bool) -> tuple[str, ...]:
    say(f'{title}, one per line. Empty line: done. "-": remove the last one.')
    points: list[str] = []
    while True:
        text = ask(f"{title[:-1]}: ").strip()
        if not text:
            if points or not required:
                return tuple(points)
            say("At least one is needed.")
        elif text == "-":
            if points:
                say(f"  removed: {points.pop()}")
        else:
            points.append(text)


def _keep(ask: Ask, say: Say, title: str, values: list[str]) -> bool:
    say(f"{title}:")
    for value in values or ["(none)"]:
        say(f"  - {value}")
    return ask("[Enter] keep, [n] enter again: ").strip().lower() != "n"


def _ask_labels(
    ask: Ask,
    say: Say,
    corpus: Corpus,
    question_id: str,
    text: str,
    source_text: str,
    suggested: str | None,
    old: Question | None,
) -> Question:
    """Ask for every label of one question until it is valid and confirmed.

    With `old`, each step offers the existing value and Enter keeps it.
    """
    while True:
        category = _ask_category(ask, say, old.category if old else suggested)
        answerable = category != "not_answerable"
        as_of = _ask_date(ask, say, old.as_of if old else DEFAULT_AS_OF)

        if old and _keep(ask, say, "Gold references", [str(r) for r in old.gold_refs]):
            refs = old.gold_refs
        else:
            refs = _ask_refs(ask, say, corpus, as_of, answerable)
        if old and _keep(ask, say, "Required points", list(old.answer_points)):
            required = old.answer_points
        else:
            required = _ask_points(ask, say, "Required points", answerable)
        if old and _keep(ask, say, "Optional points", list(old.optional_points)):
            optional = old.optional_points
        else:
            optional = _ask_points(ask, say, "Optional points", False)
        old_notes = old.notes if old else ""
        hint = " (Enter keeps the existing note)" if old_notes else " (may be empty)"
        notes = ask(f"Notes{hint}: ").strip() or old_notes

        question = Question(
            id=question_id,
            question=text,
            category=category,
            answerable=answerable,
            as_of=as_of,
            gold_refs=refs,
            answer_points=required,
            notes=notes,
            optional_points=optional,
            source_text=source_text,
        )
        if errors := validate([question], corpus):
            for error in errors:
                say(f"  {error}")
            say("Please correct it. Enter keeps what you typed.")
        elif _yes(ask, f"Save {question_id}?"):
            return question
        old = question


def _until_stopped(say: Say, run: Callable[[], None]) -> None:
    try:
        run()
    except (EOFError, KeyboardInterrupt):
        say("\nStopped. Saved questions are kept, the unfinished one is not.")


# --- Pass 1 --------------------------------------------------------------------------------


def label_pass1(
    directory: Path,
    corpus: Corpus,
    ask: Ask,
    say: Say,
    *,
    question_id: str | None = None,
    new: bool = False,
) -> None:
    """Work through the candidate questions, edit one question or add a new one."""
    path = directory / "pass1.jsonl"
    dropped_path = directory / "dropped.md"

    def labelled() -> list[Question]:
        return load_testset(path) if path.exists() else []

    def new_id() -> str:
        return _next_id([q.id for q in labelled()] + [i for i, _ in _dropped(dropped_path)])

    def edit(wanted: str) -> None:
        for index, q in enumerate(labelled()):
            if q.id == wanted:
                say(f"{q.id}: {q.question}")
                changed = _ask_labels(
                    ask, say, corpus, q.id, q.question, q.source_text, None, old=q
                )
                _save_line(path, changed, index)
                say(f"Saved {q.id}.")
                return
        say(f"{wanted} is not in {path.name}.")

    def add_own() -> None:
        text = ask("Your question: ").strip()
        if text:
            q = _ask_labels(ask, say, corpus, new_id(), text, "", None, None)
            _save_line(path, q, None)
            say(f"Saved {q.id}.")

    def candidates() -> None:
        items = parse_candidates((directory / "candidates.md").read_text(encoding="utf-8"))
        for number, candidate in enumerate(items, start=1):
            done = {t for q in labelled() for t in (q.question, q.source_text)}
            done |= {t for _, t in _dropped(dropped_path)}
            if candidate.text in done:
                continue
            say(
                f"\nCandidate {number} of {len(items)}, {len(labelled())} labelled. "
                f"Suggested category: {candidate.category}\n{candidate.text}"
            )
            choice = ""
            while True:
                choice = ask("[Enter] label  [r] rewrite  [d] drop  [s] skip  [q] quit: ")
                choice = choice.strip().lower()
                if choice in ("", "r", "d", "s", "q"):
                    break
            if choice == "q":
                return
            if choice == "s":
                continue
            if choice == "d":
                if reason := ask("Reason for dropping (empty: cancel and skip): ").strip():
                    _add_dropped(dropped_path, new_id(), candidate.text, reason)
                continue
            text, source_text = candidate.text, ""
            if choice == "r":
                text = ask("New wording: ").strip() or candidate.text
                source_text = candidate.text if text != candidate.text else ""
            q = _ask_labels(ask, say, corpus, new_id(), text, source_text, candidate.category, None)
            _save_line(path, q, None)
            say(f"Saved {q.id}.")
        say(f"\nNo more candidates. {len(labelled())} questions labelled.")

    def run() -> None:
        if question_id:
            edit(question_id)
        elif new:
            add_own()
        else:
            candidates()

    _until_stopped(say, run)


# --- Pass 2 --------------------------------------------------------------------------------


def _is_labelled(row: object) -> Question | None:
    try:
        return parse_question(row)
    except InvalidTestsetError:
        return None


def label_pass2(
    directory: Path, corpus: Corpus, ask: Ask, say: Say, *, question_id: str | None = None
) -> None:
    """Label the blind template. This never opens pass 1 or the candidate list."""
    path = directory / "pass2.jsonl"

    def run() -> None:
        if not path.exists():
            say(f"{path} does not exist. Run `make pass2-template` first.")
            return
        rows = [json.loads(line) for line in _read_lines(path)]
        if question_id and question_id not in [row["id"] for row in rows]:
            say(f"{question_id} is not in {path.name}.")
            return
        for index, row in enumerate(rows):
            old = _is_labelled(row)
            if (row["id"] != question_id) if question_id else old is not None:
                continue
            say(f"\nQuestion {index + 1} of {len(rows)} ({row['id']})\n{row['question']}")
            if not question_id:
                choice = ask("[Enter] label  [s] skip  [q] quit: ").strip().lower()
                if choice == "q":
                    return
                if choice == "s":
                    continue
            q = _ask_labels(ask, say, corpus, row["id"], row["question"], "", None, old)
            _save_line(path, q, index)
            say(f"Saved {q.id}.")
        if not question_id:
            say("\nNo more open questions.")

    _until_stopped(say, run)
