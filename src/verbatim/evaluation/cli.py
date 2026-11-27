"""Command line tools for labelling the gold test set. The Makefile wraps each command.

check FILE...              validate test set files against the corpus
lookup ACT REF [--as-of]   show the text a reference covers
template PASS1 PASS2       write the blind template for the second labelling pass
agreement PASS1 PASS2 OUT  measure agreement between the two passes
split SOURCE OUT_DIR       split the reconciled set into dev.jsonl and test.jsonl, once
"""

import argparse
import datetime
import json
import sys
from pathlib import Path

from verbatim.evaluation.agreement import blank_template, compare, render_markdown
from verbatim.evaluation.split import write_split
from verbatim.evaluation.testset import (
    Corpus,
    GoldRef,
    InvalidTestsetError,
    load_testset,
    validate,
)

PROCESSED = Path("data/processed")
DEV_SIZE = 15
SPLIT_SEED = 20261127
TEMPLATE_SEED = 2


def _check(paths: list[Path], corpus: Corpus) -> int:
    failed = False
    for path in paths:
        try:
            questions = load_testset(path)
        except InvalidTestsetError as error:
            print(error, file=sys.stderr)
            failed = True
            continue
        errors = validate(questions, corpus)
        for message in errors:
            print(f"{path.name}: {message}", file=sys.stderr)
        if errors:
            failed = True
        else:
            print(f"{path}: {len(questions)} questions, valid")
    return 1 if failed else 0


def _lookup(act: str, ref: str, as_of: str, corpus: Corpus) -> int:
    try:
        hit = corpus.lookup(GoldRef(act, ref), as_of)
    except KeyError as error:
        print(error.args[0], file=sys.stderr)
        return 1
    print(f"{hit.ref} in {hit.celex} (version of {hit.version_date})")
    print(hit.url)
    print()
    for block in hit.blocks:
        label = "".join(f"({p})" for p in block.path)
        print(f"{label} {block.text}".strip())
    if problem := corpus.problem(hit.ref, as_of):
        print(f"\nNot usable as a gold reference: {problem}", file=sys.stderr)
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    check = commands.add_parser("check")
    check.add_argument("files", type=Path, nargs="+")
    lookup = commands.add_parser("lookup")
    lookup.add_argument("act")
    lookup.add_argument("ref")
    lookup.add_argument("--as-of", default=datetime.date.today().isoformat())
    template = commands.add_parser("template")
    template.add_argument("pass1", type=Path)
    template.add_argument("pass2", type=Path)
    agreement = commands.add_parser("agreement")
    agreement.add_argument("pass1", type=Path)
    agreement.add_argument("pass2", type=Path)
    agreement.add_argument("out", type=Path)
    split = commands.add_parser("split")
    split.add_argument("source", type=Path)
    split.add_argument("out_dir", type=Path)
    args = parser.parse_args(argv)

    corpus = Corpus.load(PROCESSED)
    if args.command == "check":
        return _check(args.files, corpus)
    if args.command == "lookup":
        return _lookup(args.act, args.ref, args.as_of, corpus)
    if args.command == "template":
        if args.pass2.exists():
            print(f"{args.pass2} exists, not overwriting it", file=sys.stderr)
            return 1
        rows = blank_template(load_testset(args.pass1), seed=TEMPLATE_SEED)
        text = "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows)
        args.pass2.write_text(text, encoding="utf-8")
        print(f"{args.pass2}: {len(rows)} questions without labels")
        return 0
    if args.command == "agreement":
        if _check([args.pass1, args.pass2], corpus):
            return 1
        result = compare(load_testset(args.pass1), load_testset(args.pass2))
        args.out.write_text(render_markdown(result), encoding="utf-8")
        print(f"{args.out}: {len(result.differences)} differences to reconcile")
        return 0
    # split
    if _check([args.source], corpus):
        return 1
    try:
        write_split(args.source, args.out_dir, dev_size=DEV_SIZE, seed=SPLIT_SEED)
    except FileExistsError as error:
        print(error, file=sys.stderr)
        return 1
    print(f"wrote {args.out_dir}/dev.jsonl and test.jsonl, removed {args.source}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
