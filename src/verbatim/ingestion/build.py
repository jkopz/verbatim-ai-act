"""Parse data/raw/*.html into data/processed/*.json.

Usage: python -m verbatim.ingestion.build [--manifest PATH] [--raw-dir DIR] [--out-dir DIR]
"""

import argparse
import sys
from pathlib import Path

from verbatim.ingestion.models import save_document
from verbatim.ingestion.parser import parse_document
from verbatim.ingestion.sources import load_sources


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=Path("data/sources.toml"))
    parser.add_argument("--raw-dir", type=Path, default=Path("data/raw"))
    parser.add_argument("--out-dir", type=Path, default=Path("data/processed"))
    args = parser.parse_args(argv)

    for source in load_sources(args.manifest):
        html = (args.raw_dir / f"{source.celex}.html").read_text(encoding="utf-8")
        doc = parse_document(html, source)
        save_document(doc, args.out_dir / f"{source.celex}.json")
        print(
            f"{source.celex}: {len(doc.articles)} articles, "
            f"{len(doc.annexes)} annexes, {len(doc.recitals)} recitals"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
