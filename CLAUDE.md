# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Asteroid Cost Atlas — a data-engineering pipeline that fetches NASA's Small-Body Database, cleans/enriches the data, computes orbital and physical accessibility scores, and exposes the result through a DuckDB query layer. Python 3.11+, Pydantic v2, pandas, hatchling build.

## Commands

```bash
pip install -e ".[dev]"       # Install for development
make test                     # Run pytest with 85% coverage gate
pytest tests/test_orbital.py  # Run a single test module
pytest -k test_tisserand      # Run a single test by name
make lint                     # ruff check src tests
make format                   # ruff format src tests
make typecheck                # mypy src (strict mode)
make pipeline                 # Run full pipeline: ingest → clean → enrich → score
./start.sh                    # Launch web app (backend :8000 + frontend :5173)
make serve                    # Start FastAPI backend only (uvicorn on :8000)
make web-dev                  # Start React frontend dev server (Vite on :5173)
make web-build                # Production build of the React frontend
```

## Architecture

The pipeline is a linear chain of stages, each reading the previous stage's Parquet output:

```
ingest_sbdb → ingest_lcdb → clean_sbdb → enrich → orbital → physical
   (CSV)       (Parquet)     (Parquet)   (Parquet) (Parquet)  (Parquet)
```

All stages live under `src/asteroid_cost_atlas/` in three packages:

- **`ingest/`** — data acquisition and cleaning: SBDB fetch with page-level MD5 cache (`ingest_sbdb`), LCDB rotation periods (`ingest_lcdb`), rule-based cleaning (`clean_sbdb`), H→diameter enrichment + LCDB merge (`enrich`)
- **`scoring/`** — feature engineering: delta-v proxy, Tisserand parameter, inclination penalty (`orbital`); surface gravity, rotation feasibility, regolith likelihood (`physical`)
- **`api/`** — FastAPI REST API wrapping `CostAtlasDB` for the web frontend
- **`utils/query.py`** — `CostAtlasDB` class wrapping DuckDB over processed Parquet; supports `top_accessible()`, `nea_candidates()`, `stats()`, and raw SQL

Each module exposes scalar helper functions (for unit testing) and vectorized DataFrame transforms (for production). Each has a `main()` CLI entry point invoked via Makefile or `project.scripts` console entries.

## Configuration

- **`configs/config.yaml`** — SBDB fields, page size, file paths
- **`.env`** — runtime overrides (e.g. `SBDB_PAGE_SIZE=1000` for local testing)
- **`settings.py`** — merges YAML + .env via Pydantic, resolves all paths to absolute from repo root

## Code Conventions

- Strict mypy (`strict = true`), line length 100, ruff rules: E/F/I/UP
- All modules use `from __future__ import annotations`
- Pydantic models use `ConfigDict(extra="forbid")`
- Scalar functions return `float("nan")` for invalid input rather than raising
- Structured JSON logging with per-run metadata files in `data/raw/metadata/`
- Date-stamped output files (e.g. `sbdb_clean_20260330.parquet`)
- Data flows through `data/raw/` → `data/processed/` as Parquet
- `web/` contains the React frontend (Vite + TypeScript + Three.js)
