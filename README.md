# verbatim-ai-act

[![CI](https://github.com/jkopz/verbatim-ai-act/actions/workflows/ci.yml/badge.svg)](https://github.com/jkopz/verbatim-ai-act/actions/workflows/ci.yml)

An EU AI Act and GDPR assistant that proves every citation.

> **Not legal advice.** This is a research tool. Answers cite the legal text, but they do not
> replace advice from a qualified lawyer.

## Results

*Coming in phase 6. Numbers with confidence intervals per variant.*

## Quick start

Requires [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/jkopz/verbatim-ai-act.git && cd verbatim-ai-act
make install   # creates .venv from uv.lock and installs git hooks
make test      # lint, type check, tests
```

## Architecture

*Coming in phase 4. See [docs/plan.md](docs/plan.md) for the target design.*

## How the evaluation works

*Coming in phases 2 and 6: test set, metrics, judge and its calibration.*

## Error analysis and limits

*Coming in phases 6 and 9.*

## Reproducing the results

*Coming in phase 8: cached answers and the nightly run.*

## Decisions

Architecture decision records live in [docs/adr](docs/adr):

- [0001 Topic choice](docs/adr/0001-topic-choice.md)
- [0002 Python tooling](docs/adr/0002-python-tooling.md)

## Licence and data sources

Code under the [MIT licence](LICENSE). Legal texts come from EUR-Lex and are not stored in
this repo. Details follow in `docs/data-licenses.md` (phase 1).
