# Project Rules

## Goal
A tool to assist with the EU AI Act and GDPR, featuring verified citations and measurable accuracy.

## Commands
- `make test` runs lint checks, type checks, and tests
- `make eval-retrieval` and `make eval-smoke` run the evaluation

## Rules
- Plan first, then make changes. Plans end with a list of files that will change.
- Every change must be accompanied by an explanation of no more than three sentences.
- No new dependencies without an ADR in `docs/adr`.
- Write tests first where it makes sense. Do not merge if CI fails (red).
- Never modify `eval/testset/test.jsonl`. Changes to the gold test set only after consultation.
- Result files in `eval/runs` and `docs/results.md` are generated only by the script, never manually.
- No keys in the code or in logs. Configuration via environment variables only.
- Responses from the assistant included in the product always contain references to relevant sources and a disclaimer that they do not constitute legal advice.