# asteroid-cost-atlas

A reproducible data-engineering pipeline that transforms raw NASA small-body catalogs into an economic accessibility atlas for space-resource missions. Combines orbital mechanics proxies, physical asteroid properties, and mission-cost estimation features to rank candidate asteroid mining targets.

---

## Motivation

Thousands of asteroids are cataloged. Very few have been evaluated systematically for economic or mission feasibility. Most accessibility analyses are buried in academic papers, require specialized orbital mechanics tools, or are not reproducible.

`asteroid-cost-atlas` fills that gap: a structured, open pipeline that takes raw SBDB data and produces a ranked, feature-rich dataset answering the question — *which asteroids are cheapest to reach, easiest to mine, and most economically promising?*

---

## Pipeline Architecture

```
NASA SBDB API
     │
     ▼
┌─────────────┐
│  1. Ingest  │  Paginated API fetch, page-level caching, metadata logging
└──────┬──────┘
       │
       ▼
┌──────────────────────┐
│  2. Orbital Features │  Delta-v proxies, inclination penalties, Tisserand parameter
└──────┬───────────────┘
       │
       ▼
┌───────────────────────────┐
│  3. Physical Feasibility  │  Rotation period, gravity proxy, regolith likelihood
└──────┬────────────────────┘
       │
       ▼
┌────────────────────────┐
│  4. Composition Proxies │  C/S/M-type classification signals from albedo
└──────┬─────────────────┘
       │
       ▼
┌──────────────────────┐
│  5. Economic Scoring  │  Mission-cost proxies, resource density estimates
└──────┬───────────────┘
       │
       ▼
┌────────────────────┐
│  6. Atlas Assembly  │  Unified dataset with priority ranking
└──────┬─────────────┘
       │
       ▼
┌──────────────────────────┐
│  7. Analytics & Outputs  │  CSV exports, metadata, downstream visualization
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
SBDB_PAGE_SIZE=5000   # override page_size from config.yaml
```

All paths are resolved relative to the repository root regardless of working directory. Config is validated at startup via Pydantic — invalid fields raise immediately.

---

## Usage

```bash
# Run the full ingestion pipeline
make ingest

# Or with overrides
asteroid-ingest --page-size 5000 --output data/raw

# Run tests
make test

# Lint and type-check
make lint
make typecheck
```

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

**Ingestion**
- Full SBDB catalog fetch via paginated API requests
- Page-level MD5-keyed disk cache — reruns skip network entirely
- Per-run metadata output (timestamp, source URL, fields, record count)
- Structured JSON logging throughout

**Config system**
- YAML-defined fields with Pydantic validation (`extra="forbid"`)
- `.env` overrides for environment-specific parameters
- All paths resolved to absolute at load time

---

## Dataset Outputs

The final `asteroid_cost_atlas` dataset (CSV, `data/processed/`) will include one row per asteroid with the following feature groups:

| Feature Group | Columns |
|---|---|
| Identity | `spkid`, `name` |
| Orbital | `a_au`, `eccentricity`, `inclination_deg` |
| Accessibility | delta-v proxy, Tisserand parameter, inclination penalty |
| Physical | `diameter_km`, `rotation_hours`, gravity proxy, regolith likelihood |
| Composition | albedo-derived C/S/M-type signal |
| Economic | resource density estimate, mission-cost proxy score |
| Ranking | `economic_priority_rank` |

---

## Roadmap

- [ ] Orbital scoring module — delta-v proxies, Tisserand parameter, inclination penalty
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
