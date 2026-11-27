.PHONY: install lint format typecheck unit test fetch corpus \
	check-testset lookup pass2-template agreement split

install: ## Create .venv from uv.lock and install git hooks
	uv sync --locked
	uv run pre-commit install

lint: ## Check style and common bugs
	uv run ruff check .
	uv run ruff format --check .

format: ## Auto-fix style
	uv run ruff check --fix .
	uv run ruff format .

typecheck:
	uv run pyright

unit:
	uv run pytest

test: lint typecheck unit ## Everything CI runs

fetch: ## Download the legal texts into data/raw (checked against data/sources.toml)
	uv run python -m verbatim.ingestion.fetch

corpus: fetch ## Rebuild data/processed from data/raw
	uv run python -m verbatim.ingestion.build

# --- Gold test set (see eval/testset/labeling-guide.md) ---------------------------------------
TESTSET := eval/testset
LABELING := $(TESTSET)/labeling
EVAL := uv run python -m verbatim.evaluation.cli

check-testset: ## Validate test set files: make check-testset [FILE=eval/testset/labeling/pass1.jsonl]
	$(EVAL) check $(or $(FILE),$(wildcard $(LABELING)/*.jsonl $(TESTSET)/dev.jsonl $(TESTSET)/test.jsonl))

lookup: ## Show the text of a reference: make lookup ACT=ai-act REF="Art. 6(2)" [AS_OF=2026-11-27]
	$(EVAL) lookup $(ACT) "$(REF)" $(if $(AS_OF),--as-of $(AS_OF))

pass2-template: ## Write the blind template for the second labelling pass
	$(EVAL) template $(LABELING)/pass1.jsonl $(LABELING)/pass2.jsonl

agreement: ## Measure agreement between pass 1 and pass 2
	$(EVAL) agreement $(LABELING)/pass1.jsonl $(LABELING)/pass2.jsonl $(LABELING)/agreement.md

split: ## Split the reconciled set into dev.jsonl and test.jsonl (runs once)
	$(EVAL) split $(LABELING)/reconciled.jsonl $(TESTSET)
