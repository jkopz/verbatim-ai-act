"""The source manifest data/sources.toml."""

import tomllib
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class Source:
    celex: str
    act: str
    version_date: str
    status: str
    language: str
    url: str
    sha256: str


def load_sources(path: Path) -> list[Source]:
    with path.open("rb") as f:
        data = tomllib.load(f)
    return [Source(**entry) for entry in data["source"]]
