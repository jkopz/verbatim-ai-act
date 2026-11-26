# 0004 HTML parsing with Beautiful Soup, downloads with the standard library

- Status: accepted
- Date: 2026-11-26

## Context

EUR-Lex serves the legal texts as HTML in two different layouts. Official Journal documents
mark paragraphs with ids such as `005.001` and points as two-column tables. Consolidated
documents use `span.no-parag` for paragraph numbers and `div.grid-list` containers for points.
The pages are not well-formed XML, so `xml.etree` cannot read them. The parser is run once per
corpus build, so speed is not critical. Type checking runs in pyright strict mode.

## Decision

- Parse with **beautifulsoup4**, using the built-in `html.parser` backend.
- Download with **`urllib.request`** from the standard library.

## Alternatives considered

| Option | Pros | Cons |
| --- | --- | --- |
| beautifulsoup4 with `html.parser` | Readable tree navigation, ships type hints that work in strict mode, no compiled extension | Slower than lxml, one dependency (plus soupsieve) |
| Standard library `html.parser` only | No dependency | Event-based, needs a hand-written tree builder, much more code |
| lxml | Fast, XPath | Compiled extension, typing needs separate stubs and many casts in strict mode |
| requests or httpx for downloads | Nicer API | A dependency for four GET requests |

## Consequences

- One runtime dependency: `beautifulsoup4`.
- If parsing ever becomes a bottleneck, the backend can be switched to lxml without changing
  the parser code.
