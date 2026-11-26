# 0002 Python tooling: uv, ruff, pyright, pytest, pre-commit

- Status: accepted
- Date: 2026-11-26

## Context

The project needs reproducible installs, fast feedback on style and types, and the same
checks locally and in CI. These are development dependencies only; nothing ships to users.

## Decision

- **Python 3.13.** Recent, but mature enough for the ML libraries needed from phase 3
  (embeddings, reranker), which often lag behind the newest release.
- **uv** for environments, dependency resolution and the lockfile `uv.lock`.
- **ruff** for linting and formatting.
- **pyright** in strict mode for type checking.
- **pytest** for tests.
- **pre-commit** to run hygiene checks and ruff before every commit. Ruff runs through
  `uv run`, so the hook uses the version pinned in `uv.lock`.

## Alternatives considered

| Option | Pros | Cons |
| --- | --- | --- |
| uv | Very fast, one tool for venv, lockfile and Python versions | Younger than pip/Poetry |
| Poetry or pip-tools | Established | Slower, several tools needed |
| ruff | Replaces flake8, isort and black in one fast tool | Not every niche plugin exists |
| pyright | Fast, strict, same engine as the VS Code extension (Pylance) | Needs Node.js in the background (installed automatically) |
| mypy | The reference type checker, widely used | Slower, more lenient defaults |
| Python 3.14 | Newest | Risk of missing wheels for ML libraries |

## Consequences

- uv uses its own managed Python builds (`python-preference = "only-managed"`), not system
  installs, so every machine gets the same interpreter with working root certificates.
- `make test` is the single command for lint, types and tests, locally and in CI.
- CI installs with `uv sync --locked` and fails if the lockfile is out of date.
- Strict pyright means untyped third-party libraries may need stubs or targeted ignores.
