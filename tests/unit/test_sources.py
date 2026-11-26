from pathlib import Path

import pytest

from verbatim.ingestion.fetch import ChecksumMismatchError, fetch, sanitize, sha256_hex, verify
from verbatim.ingestion.sources import Source, load_sources

MANIFEST = Path(__file__).parents[2] / "data" / "sources.toml"


def test_manifest_lists_the_four_sources() -> None:
    sources = load_sources(MANIFEST)
    assert {s.celex for s in sources} == {
        "02024R1689-20260727",
        "32024R1689",
        "02016R0679-20160504",
        "32016R0679",
    }
    for s in sources:
        assert s.url.endswith(s.celex)
        assert len(s.sha256) == 64


def test_sanitize_removes_scripts_with_random_ids() -> None:
    a = b"<head><script src='x.js' data-id='123'></script></head><p>text</p>"
    b = b"<head><SCRIPT src='x.js' data-id='456'>\nvar x;</SCRIPT></head><p>text</p>"
    assert sanitize(a) == sanitize(b) == b"<head></head><p>text</p>"


def test_verify_accepts_matching_and_rejects_changed_content() -> None:
    content = b"<p>Article 1</p>"
    verify(content, sha256_hex(content), name="doc")
    with pytest.raises(ChecksumMismatchError):
        verify(b"<p>Article 2</p>", sha256_hex(content), name="doc")


def test_fetch_accepts_a_hand_downloaded_file_with_scripts(tmp_path: Path) -> None:
    clean = b"<p>Article 1</p>"
    (tmp_path / "TEST.html").write_bytes(b"<script>tracking()</script>" + clean)
    source = Source(
        celex="TEST",
        act="ai-act",
        version_date="2026-07-27",
        status="consolidated",
        language="en",
        url="https://example.invalid/TEST",
        sha256=sha256_hex(clean),
    )
    assert fetch(source, tmp_path) is False  # no download needed
    assert (tmp_path / "TEST.html").read_bytes() == clean
