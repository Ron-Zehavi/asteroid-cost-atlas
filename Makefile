.PHONY: install pipeline ingest ingest-lcdb ingest-neowise ingest-spectral ingest-movis ingest-horizons clean-data enrich score-orbital score-physical score-composition atlas query serve web-dev web-build docker lint format typecheck test clean clean-outputs data-info help

PYTHON_VERSION := $(shell python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null || echo "0.0")
MIN_PYTHON := 3.11

help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-12s %s\n", $$1, $$2}'

check-python:
	@python3 -c "import sys; assert sys.version_info >= (3, 11), f'Python 3.11+ required, got {sys.version}'" \
		|| (echo "ERROR: Python 3.11+ is required. Current: $(PYTHON_VERSION)" && exit 1)

install: check-python ## Install package and dev dependencies
	pip install -e ".[dev]"

# Pipeline stages must run in this order:
#   ingest → ingest-lcdb → ingest-neowise → ingest-spectral → ingest-movis → clean-data → enrich → ingest-horizons → score-orbital → score-physical → score-composition → atlas
pipeline: ingest ingest-lcdb ingest-neowise ingest-spectral ingest-movis clean-data enrich ingest-horizons score-orbital score-physical score-composition atlas ## Run full pipeline end-to-end

ingest: ## Fetch raw SBDB catalog → data/raw/sbdb_*.csv
	python -m asteroid_cost_atlas.ingest.ingest_sbdb

ingest-lcdb: ## Fetch LCDB rotation periods → data/raw/lcdb_*.parquet
	python -m asteroid_cost_atlas.ingest.ingest_lcdb

ingest-neowise: ## Fetch NEOWISE diameters/albedos → data/raw/neowise_*.parquet
	python -m asteroid_cost_atlas.ingest.ingest_neowise

ingest-spectral: ## Fetch SDSS MOC photometry → data/raw/sdss_moc_*.parquet
	python -m asteroid_cost_atlas.ingest.ingest_spectral

ingest-movis: ## Fetch MOVIS-C NIR taxonomy → data/raw/movis_*.parquet
	python -m asteroid_cost_atlas.ingest.ingest_movis

ingest-horizons: ## Fetch JPL Horizons elements for NEAs → data/raw/horizons_*.parquet
	python -m asteroid_cost_atlas.ingest.ingest_horizons

clean-data: ## Validate and filter raw CSV → data/processed/sbdb_clean_*.parquet
	python -m asteroid_cost_atlas.ingest.clean_sbdb

enrich: ## Estimate missing diameters from H magnitude → data/processed/sbdb_enriched_*.parquet
	python -m asteroid_cost_atlas.ingest.enrich

score-orbital: ## Apply orbital scoring → data/processed/sbdb_orbital_*.parquet
	python -m asteroid_cost_atlas.scoring.orbital

score-physical: ## Apply physical feasibility scoring → data/processed/sbdb_physical_*.parquet
	python -m asteroid_cost_atlas.scoring.physical

score-composition: ## Apply composition classification → data/processed/sbdb_composition_*.parquet
	python -m asteroid_cost_atlas.scoring.composition

atlas: ## Economic scoring + final ranked atlas → data/processed/atlas_*.parquet
	python -m asteroid_cost_atlas.scoring.economic

query: ## Run a sample query against the latest atlas
	python3 -c "\
from pathlib import Path; \
from asteroid_cost_atlas.utils.query import CostAtlasDB; \
p = sorted(Path('data/processed').glob('atlas_*.parquet')) \
 or sorted(Path('data/processed').glob('sbdb_physical_*.parquet')); \
db = CostAtlasDB(p[-1]); \
print('=== Stats ==='); print(db.stats().to_string(index=False)); \
print('\n=== Top 10 most accessible ==='); \
print(db.top_accessible(n=10)[['name','delta_v_km_s','tisserand_jupiter','diameter_estimated_km','surface_gravity_m_s2','neo']].to_string(index=False)); \
db.close()"

serve: ## Start FastAPI dev server on port 8000
	uvicorn asteroid_cost_atlas.api.app:app --reload --port 8000

web-dev: ## Start React dev server (requires npm install in web/)
	cd web && npm run dev

web-build: ## Build React production bundle
	cd web && npm run build

docker: ## Build Docker image
	docker build -t asteroid-cost-atlas .

docker-run: ## Run Docker container on port 8000
	docker run -p 8000:8000 asteroid-cost-atlas

audit: ## Run project audit and data integrity check
	python scripts/audit.py

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
