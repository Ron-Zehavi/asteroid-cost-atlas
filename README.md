# asteroid-cost-atlas

![Python](https://img.shields.io/badge/python-3.11+-blue) ![License](https://img.shields.io/badge/license-MIT-green)

A reproducible data-engineering pipeline that transforms raw NASA small-body catalogs into an economic accessibility atlas for space-resource missions. Combines orbital mechanics proxies, physical asteroid properties, and mission-cost estimation features to rank candidate asteroid mining targets.

---

## Motivation

Thousands of asteroids are cataloged. Very few have been evaluated systematically for economic or mission feasibility. Most accessibility analyses are buried in academic papers, require specialized orbital mechanics tools, or are not reproducible.

`asteroid-cost-atlas` fills that gap: a structured, open pipeline that takes raw SBDB data and produces a ranked, feature-rich dataset answering the question — *which asteroids are cheapest to reach, easiest to mine, and most economically promising?*

Inspired by the accessibility and value estimates pioneered by [Asterank](https://www.asterank.com), this project focuses on a similar but slithly improved goal: building a transparent, reproducible pipeline that evaluates asteroid mission accessibility across the full NASA catalog (~1.5 million objects) using orbital mechanics proxies such as inclination penalties, Tisserand stability, and future rotation/regolith feasibility signals. Rather than producing a single heuristic profitability score, it constructs a research-grade dataset from primary sources like the [SBDB Query API](https://ssd-api.jpl.nasa.gov/doc/sbdb_query.html) with planned higher-fidelity trajectory integrations from [JPL Horizons](https://ssd.jpl.nasa.gov/horizons/), enabling systematic comparison, extension with new surveys, and engineering-oriented target screening at scale. 🚀📊🛰️

---

## Pipeline Architecture

```
NASA SBDB API
     │
     ▼
┌─────────────┐
│  1. Ingest  │  Paginated API fetch, page-level caching, metadata logging
└──────┬──────┘
       │  data/raw/sbdb_*.csv  (untouched)
       ▼
┌─────────────┐
│  2. Clean   │  Drop corrupt records (a≤0, e≥1, non-finite), log removals
└──────┬──────┘
       │  data/processed/sbdb_clean_*.parquet
       ▼
┌──────────────────────┐
│  3. Orbital Features │  Delta-v proxies, inclination penalties, Tisserand parameter
└──────┬───────────────┘
       │
       ▼
┌───────────────────────────┐
│  4. Physical Feasibility  │  Rotation period, gravity proxy, regolith likelihood
└──────┬────────────────────┘
       │
       ▼
┌────────────────────────┐
│  5. Composition Proxies │  C/S/M-type classification signals from albedo
└──────┬─────────────────┘
       │
       ▼
┌──────────────────────┐
│  6. Economic Scoring  │  Mission-cost proxies, resource density estimates
└──────┬───────────────┘
       │
       ▼
┌────────────────────┐
│  7. Atlas Assembly  │  Unified dataset with priority ranking
└──────┬─────────────┘
       │
       ▼
┌──────────────────────────┐
│  8. Analytics & Outputs  │  Parquet exports, DuckDB query layer, visualisation
└──────────────────────────┘
```

---

## Repository Structure

```
asteroid-cost-atlas/
├── src/asteroid_cost_atlas/
│   ├── ingest/
│   │   └── ingest_sbdb.py       # SBDB API fetch: pagination, caching, metadata
│   ├── models/                  # Pydantic data models
│   ├── scoring/                 # Orbital, physical, and economic scoring engines
│   ├── utils/                   # Shared helpers
│   └── settings.py              # Typed config loader (YAML + .env overrides)
├── tests/
│   ├── conftest.py
│   ├── test_ingest_sbdb.py
│   └── test_settings.py
├── configs/
│   └── config.yaml              # API fields, page size, output paths
├── data/
│   ├── raw/
│   │   ├── cache/               # Page-level API response cache
│   │   └── metadata/            # Per-run fetch metadata (JSON)
│   └── processed/               # Final atlas datasets (CSV)
├── notebooks/                   # Exploratory analysis
├── Makefile
├── pyproject.toml
└── .env.example
```

---

## Setup

Requires **Python 3.11+**.

```bash
# Create and activate a virtual environment
python -m venv .venv && source .venv/bin/activate

# Install package with dev dependencies
pip install -e ".[dev]"

# Copy environment config
cp .env.example .env
```

---

## Configuration

Runtime configuration is split across two files:

**`configs/config.yaml`** — static pipeline parameters:

```yaml
base_url: https://ssd-api.jpl.nasa.gov/sbdb_query.api

sbdb_fields:
  - spkid
  - full_name
  - a           # semi-major axis (AU)
  - e           # eccentricity
  - i           # inclination (deg)
  - diameter    # estimated diameter (km)
  - rot_per     # rotation period (hours)
  - albedo      # geometric albedo

page_size: 20000

paths:
  raw_json:     data/raw/sbdb.json
  csv_dir:      data/raw
  cache_dir:    data/raw/cache
  metadata_dir: data/raw/metadata
```

**`.env`** — environment overrides (never committed):

```bash
SBDB_PAGE_SIZE=20000   # reduce to fetch a smaller sample (e.g. 1000 for local testing)
```

All paths are resolved relative to the repository root regardless of working directory. Config is validated at startup via Pydantic — invalid fields raise immediately.

---

## Usage

```bash
# Run the full pipeline end-to-end (ingest → clean → score)
make pipeline

# Or run stages individually
make ingest        # fetch raw SBDB catalog
make clean-data    # validate and filter → clean Parquet
make score-orbital # add orbital features → scored Parquet
make query         # run a sample query against the atlas

# CLI entry points (after pip install -e .)
asteroid-ingest --page-size 5000 --output data/raw

# Run tests
make test

# Lint and type-check
make lint
make typecheck
```

> **Note:** A full ingest fetches ~1.5 million records across ~75 paginated requests. On a typical connection this takes a few minutes. Subsequent runs skip all network requests — pages are cached to `data/raw/cache/` by content hash.

Available `make` targets:

```
  install      Install package and dev dependencies
  ingest       Run SBDB ingestion pipeline
  lint         Lint with ruff
  format       Format with ruff
  typecheck    Type-check with mypy
  test         Run tests with coverage
  clean        Remove build artifacts and caches
```

---

## Current Features

**Ingestion** ✓
- Full SBDB catalog fetch via paginated API requests (~1.5M objects, spkid range 1000001–54607103)
- Page-level MD5-keyed disk cache — reruns skip network entirely
- Per-run metadata output (timestamp, source URL, fields, record count)
- Structured JSON logging throughout

**Config system** ✓
- YAML-defined fields with Pydantic validation (`extra="forbid"`)
- `.env` overrides for environment-specific parameters
- All paths resolved to absolute at load time

**Orbital scoring** ✓
- Delta-v proxy (km/s) — Hohmann transfer + inclination correction (Shoemaker-Helin)
- Tisserand parameter w.r.t. Jupiter — orbit stability and accessibility classification
- Inclination penalty — normalised plane-change cost in [0, 1]
- Fully vectorised over the 1.5M-row catalog with strict input validation

---

## Dataset Outputs

The atlas dataset (CSV, `data/processed/`) contains one row per asteroid.

**Currently ingested** (available after `make ingest`):

| Column | Source | Description |
|---|---|---|
| `spkid` | SBDB | JPL SPK-ID — numbered asteroids follow the format `2` + 7-digit number (e.g. `20000001` = (1) Ceres) |
| `name` | SBDB | Full designation |
| `a_au` | SBDB | Semi-major axis (AU) |
| `eccentricity` | SBDB | Orbital eccentricity |
| `inclination_deg` | SBDB | Orbital inclination (degrees) |
| `diameter_km` | SBDB | Estimated diameter (km), sparse |
| `rotation_hours` | SBDB | Rotation period (hours), sparse |
| `albedo` | SBDB | Geometric albedo, sparse |

**Orbital scoring** (added by `scoring/orbital.py`):

| Column | Description |
|---|---|
| `delta_v_km_s` | Simplified mission delta-v proxy (km/s) — Hohmann transfer + inclination correction |
| `tisserand_jupiter` | Tisserand parameter w.r.t. Jupiter — T_J > 3 main belt, 2–3 accessible NEAs |
| `inclination_penalty` | Normalised plane-change cost in [0, 1] via sin²(i/2) |

**Planned** (added by future pipeline stages):

| Feature Group | Columns |
|---|---|
| Physical | gravity proxy, regolith likelihood |
| Composition | albedo-derived C/S/M-type signal |
| Economic | resource density estimate, mission-cost proxy score |
| Ranking | `economic_priority_rank` |

---

## Roadmap

- [x] Ingestion — paginated SBDB fetch, caching, metadata logging
- [x] Config system — typed YAML + `.env` loader with Pydantic
- [x] Data cleaning stage — rule-based filter with per-rule removal logging
- [x] Orbital scoring module — delta-v proxies, Tisserand parameter, inclination penalty
- [x] DuckDB query layer — `top_accessible`, `nea_candidates`, `stats`, `delta_v_histogram`
- [ ] Physical feasibility module — rotation, gravity proxy, regolith likelihood
- [ ] Composition proxy module — C/S/M-type classification from albedo
- [ ] Economic scoring engine — resource density × accessibility composite
- [ ] Atlas assembly — merge all feature groups into unified ranked dataset
- [ ] JPL Horizons integration — higher-fidelity orbital elements
- [ ] NEOWISE albedo refinements — improved diameter and composition estimates
- [ ] LCDB rotation reliability flags — filter unreliable rotation periods
- [ ] Spectral catalog joins — taxonomy-based composition signals
- [ ] Visualization layer — accessibility scatter plots, ranking dashboards

---

## Intended Users

- **Space-resource researchers** building mission shortlists
- **Data engineers** looking for a reference pipeline on scientific catalog processing
- **Trajectory planners** needing a pre-filtered, ranked candidate set
- **Policy and economic analysts** modeling space-resource feasibility at scale

---

## Long-term Vision

Become a reproducible, openly maintained reference dataset for asteroid economic accessibility — updated on a regular cadence as NASA catalogs are refreshed, and extensible as new data sources (Horizons, NEOWISE, spectral surveys) become available. The goal is a living atlas: every asteroid, ranked, with traceable methodology.

---

## License

MIT
