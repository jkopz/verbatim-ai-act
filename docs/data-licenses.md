# Data licences

## Legal texts from EUR-Lex

All legal texts in this repository come from [EUR-Lex](https://eur-lex.europa.eu).

- Copyright: © European Union, 1998-2026.
- Reuse: The [EUR-Lex legal notice](https://eur-lex.europa.eu/content/legal-notice/legal-notice.html)
  states that the Commission's document reuse policy is based on Decision 2011/833/EU and that,
  unless otherwise specified, the legal documents published in EUR-Lex can be reused for
  commercial or non-commercial purposes. Checked on 2026-11-26.
- Attribution: the source of every document is named in `data/sources.toml` and in each
  processed file (CELEX number and URL).

| What | Where | In the repository |
| --- | --- | --- |
| Downloaded HTML | `data/raw/` | No. Reproduced with `make fetch`, verified by sha256 |
| Parsed text and structure | `data/processed/` | Yes, so that tests and CI run without network access |
| Short HTML excerpts | `tests/fixtures/eurlex/` | Yes, as parser test input |

The raw HTML stays out of the repository because it is large, contains page layout and
scripts, and can be reproduced exactly from the manifest.

## Authenticity

Consolidated texts on EUR-Lex are "meant purely as a documentation tool and have no legal
effect". Only the texts published in the Official Journal of the European Union are authentic.
See [ADR 0003](adr/0003-corpus-version.md) for which version the corpus uses.
