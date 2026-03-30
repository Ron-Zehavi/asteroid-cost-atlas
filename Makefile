.PHONY: install pipeline ingest ingest-lcdb clean-data enrich score-orbital score-physical query lint format typecheck test clean clean-outputs data-info help

help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-12s %s\n", $$1, $$2}'

install: ## Install package and dev dependencies
	pip install -e ".[dev]"

# Pipeline stages must run in this order:
#   ingest → ingest-lcdb → clean-data → enrich → score-orbital → score-physical
pipeline: ingest ingest-lcdb clean-data enrich score-orbital score-physical ## Run full pipeline end-to-end

ingest: ## Fetch raw SBDB catalog → data/raw/sbdb_*.csv
	python -m asteroid_cost_atlas.ingest.ingest_sbdb

ingest-lcdb: ## Fetch LCDB rotation periods → data/raw/lcdb_*.parquet
	python -m asteroid_cost_atlas.ingest.ingest_lcdb

clean-data: ## Validate and filter raw CSV → data/processed/sbdb_clean_*.parquet
	python -m asteroid_cost_atlas.ingest.clean_sbdb

enrich: ## Estimate missing diameters from H magnitude → data/processed/sbdb_enriched_*.parquet
	python -m asteroid_cost_atlas.ingest.enrich

score-orbital: ## Apply orbital scoring → data/processed/sbdb_orbital_*.parquet
	python -m asteroid_cost_atlas.scoring.orbital

score-physical: ## Apply physical feasibility scoring → data/processed/sbdb_physical_*.parquet
	python -m asteroid_cost_atlas.scoring.physical

query: ## Run a sample query against the latest atlas
	python3 -c "\
from pathlib import Path; \
from asteroid_cost_atlas.utils.query import CostAtlasDB; \
p = sorted(Path('data/processed').glob('sbdb_physical_*.parquet')) \
 or sorted(Path('data/processed').glob('sbdb_orbital_*.parquet')); \
db = CostAtlasDB(p[-1]); \
print('=== Stats ==='); print(db.stats().to_string(index=False)); \
print('\n=== Top 10 most accessible ==='); \
print(db.top_accessible(n=10)[['name','delta_v_km_s','tisserand_jupiter','diameter_estimated_km','surface_gravity_m_s2','neo']].to_string(index=False)); \
db.close()"

lint: ## Lint with ruff
	ruff check src tests

format: ## Format with ruff
	ruff format src tests

typecheck: ## Type-check with mypy
	mypy src

test: ## Run tests with coverage
	pytest

clean-outputs: ## Remove processed Parquet outputs (keeps raw data)
	rm -f data/processed/sbdb_clean_*.parquet
	rm -f data/processed/sbdb_orbital_*.parquet

data-info: ## Show available pipeline outputs and their fetch metadata
	@echo "=== Raw CSVs ==="
	@ls -lh data/raw/sbdb_*.csv 2>/dev/null || echo "  (none — run: make ingest)"
	@echo ""
	@echo "=== Processed Parquets ==="
	@ls -lh data/processed/*.parquet 2>/dev/null || echo "  (none — run: make pipeline)"
	@echo ""
	@echo "=== Ingest metadata ==="
	@ls data/raw/metadata/*.metadata.json 2>/dev/null | tail -1 | xargs cat 2>/dev/null || echo "  (none)"

clean: ## Remove build artifacts and caches
	rm -rf dist build .eggs
	rm -rf .mypy_cache .ruff_cache .pytest_cache htmlcov
	rm -f .coverage
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -name "*.py[cod]" -delete
