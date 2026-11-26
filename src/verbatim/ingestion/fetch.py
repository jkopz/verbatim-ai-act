"""Download the source documents listed in data/sources.toml into data/raw/.

Usage: python -m verbatim.ingestion.fetch [--manifest PATH] [--raw-dir DIR]
"""

import argparse
import hashlib
import re
import sys
import time
import urllib.request
from pathlib import Path

from verbatim.ingestion.sources import Source, load_sources

USER_AGENT = "verbatim-corpus-fetch/0.1"
TIMEOUT_SECONDS = 60
PAUSE_SECONDS = 2.0  # be polite to EUR-Lex between requests

# EUR-Lex injects a monitoring script with a random id into every response.
_SCRIPT = re.compile(rb"<script\b.*?</script>", re.DOTALL | re.IGNORECASE)


class ChecksumMismatchError(Exception):
    pass


def sanitize(content: bytes) -> bytes:
    """Remove <script> elements so that identical documents have identical bytes."""
    return _SCRIPT.sub(b"", content)


def sha256_hex(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def verify(content: bytes, expected: str, *, name: str) -> None:
    actual = sha256_hex(content)
    if actual != expected:
        raise ChecksumMismatchError(
            f"{name}: sha256 is {actual}, manifest expects {expected}. "
            "EUR-Lex may have changed the document. Review it, then update data/sources.toml."
        )


def download(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
        data: bytes = response.read()
    return data


def fetch(source: Source, raw_dir: Path) -> bool:
    """Make sure data/raw/<celex>.html exists and matches the manifest. True if downloaded."""
    target = raw_dir / f"{source.celex}.html"
    if target.exists():
        # Sanitize again: a file saved by hand from a browser still contains the scripts.
        content = sanitize(target.read_bytes())
        verify(content, source.sha256, name=source.celex)
        target.write_bytes(content)
        return False
    content = sanitize(download(source.url))
    verify(content, source.sha256, name=source.celex)
    raw_dir.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content)
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=Path("data/sources.toml"))
    parser.add_argument("--raw-dir", type=Path, default=Path("data/raw"))
    args = parser.parse_args(argv)

    for i, source in enumerate(load_sources(args.manifest)):
        if i:
            time.sleep(PAUSE_SECONDS)
        try:
            downloaded = fetch(source, args.raw_dir)
        except ChecksumMismatchError as error:
            print(error, file=sys.stderr)
            return 1
        print(f"{source.celex}: {'downloaded' if downloaded else 'up to date'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
