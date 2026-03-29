.PHONY: install ingest lint format typecheck test clean help

help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-12s %s\n", $$1, $$2}'

install: ## Install package and dev dependencies
	pip install -e ".[dev]"

ingest: ## Run SBDB ingestion pipeline
	python -m asteroid_cost_atlas.ingest.ingest_sbdb

lint: ## Lint with ruff
	ruff check src tests

format: ## Format with ruff
	ruff format src tests

typecheck: ## Type-check with mypy
	mypy src

test: ## Run tests with coverage
	pytest

clean: ## Remove build artifacts and caches
	rm -rf dist build .eggs
	rm -rf .mypy_cache .ruff_cache .pytest_cache htmlcov
	rm -f .coverage
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -name "*.py[cod]" -delete
