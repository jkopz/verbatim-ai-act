.PHONY: install lint format typecheck unit test

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
