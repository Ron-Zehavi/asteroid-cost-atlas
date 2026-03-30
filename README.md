# asteroid-cost-atlas

![Python](https://img.shields.io/badge/python-3.11+-blue) ![License](https://img.shields.io/badge/license-MIT-green)

A reproducible data-engineering pipeline that transforms raw NASA small-body catalogs into an economic accessibility atlas for space-resource missions. Combines orbital mechanics proxies, physical asteroid properties, and mission-cost estimation features to rank candidate asteroid mining targets.

---

## Motivation

Thousands of asteroids are cataloged. Very few have been evaluated systematically for economic or mission feasibility. Most accessibility analyses are buried in academic papers, require specialized orbital mechanics tools, or are not reproducible.

`asteroid-cost-atlas` fills that gap: a structured, open pipeline that takes raw SBDB data and produces a ranked, feature-rich dataset answering the question — *which asteroids are cheapest to reach, easiest to mine, and most economically promising?*

Inspired by the accessibility and value estimates pioneered by [Asterank](https://www.asterank.com), this project focuses on a similar but slightly improved goal: building a transparent, reproducible pipeline that evaluates asteroid mission accessibility across the full NASA catalog (~1.5 million objects) using orbital mechanics proxies such as inclination penalties, Tisserand stability, and rotation/regolith feasibility signals. Rather than producing a single heuristic profitability score, it constructs a research-grade dataset from primary sources like the [SBDB Query API](https://ssd-api.jpl.nasa.gov/doc/sbdb_query.html) and the [LCDB](https://minplanobs.org/mpinfo/php/lcdb.php), with planned higher-fidelity integrations from [NEOWISE](https://sbn.psi.edu/pds/resource/neowisediam.html) and [JPL Horizons](https://ssd.jpl.nasa.gov/horizons/), enabling systematic comparison, extension with new surveys, and engineering-oriented target screening at scale.

---

## Pipeline Architecture

```
NASA SBDB API          LCDB (minplanobs.org)
     │                        │
     ▼                        ▼
┌─────────────┐     ┌──────────────────┐
│  1. Ingest  │     │  1b. Ingest LCDB │  Rotation periods, taxonomy, albedo
└──────┬──────┘     └────────┬─────────┘
       │  data/raw/sbdb_*.csv         │  data/raw/lcdb_*.parquet
       ▼                              │
┌─────────────┐                       │
│  2. Clean   │  Drop corrupt records │
└──────┬──────┘                       │
       │  data/processed/sbdb_clean_*.parquet
       ▼                              │
┌─────────────────┐                   │
│  3. Enrich      │◄──────────────────┘
│  LCDB merge     │  Fill rotation + albedo gaps from LCDB
│  H→diameter     │  Estimate diameter from absolute magnitude (99.9% coverage)
└──────┬──────────┘
       │  data/processed/sbdb_enriched_*.parquet
       ▼
┌──────────────────────┐
│  4. Orbital Features │  Delta-v proxies, inclination penalties, Tisserand parameter
└──────┬───────────────┘
       │  data/processed/sbdb_orbital_*.parquet
       ▼
┌───────────────────────────┐
│  5. Physical Feasibility  │  Surface gravity, rotation feasibility, regolith likelihood
└──────┬────────────────────┘
       │  data/processed/sbdb_physical_*.parquet
       ▼
┌────────────────────────┐
│  6. Composition Proxies │  C/S/M-type classification signals from albedo + taxonomy
└──────┬─────────────────┘
       │
       ▼
┌──────────────────────┐
│  7. Economic Scoring  │  Mission-cost proxies, resource density estimates
└──────┬───────────────┘
       │
       ▼
┌────────────────────┐
│  8. Atlas Assembly  │  Unified dataset with priority ranking
└──────┬─────────────┘
       │
       ▼
┌──────────────────────────┐
│  9. Analytics & Outputs  │  Parquet exports, DuckDB query layer, visualisation
└──────────────────────────┘
```

---

## Repository Structure

```
asteroid-cost-atlas/
├── src/asteroid_cost_atlas/
│   ├── ingest/
│   │   ├── ingest_sbdb.py       # SBDB API fetch: pagination, caching, metadata
│   │   ├── ingest_lcdb.py       # LCDB download: rotation periods, taxonomy
│   │   ├── clean_sbdb.py        # Rule-based data cleaning with per-rule logging
│   │   └── enrich.py            # LCDB merge + H→diameter estimation
│   ├── scoring/
│   │   ├── orbital.py           # Delta-v, Tisserand, inclination penalty
│   │   └── physical.py          # Gravity, rotation feasibility, regolith
│   ├── models/
│   │   └── asteroid.py          # Pydantic AsteroidRecord model
│   ├── utils/
│   │   └── query.py             # DuckDB query layer (CostAtlasDB)
│   └── settings.py              # Typed config loader (YAML + .env overrides)
├── tests/
│   ├── conftest.py
│   ├── test_ingest_sbdb.py
│   ├── test_ingest_lcdb.py
│   ├── test_clean_sbdb.py
│   ├── test_enrich.py
│   ├── test_orbital.py
│   ├── test_physical.py
│   ├── test_query.py
│   ├── test_pipeline_integration.py
│   └── test_settings.py
├── configs/
│   └── config.yaml              # API fields, page size, output paths
├── data/
│   ├── raw/
│   │   ├── cache/               # Page-level API response cache
│   │   └── metadata/            # Per-run fetch metadata (JSON)
│   └── processed/               # Pipeline output Parquets
├── .github/workflows/
│   └── ci.yml                   # Lint → type-check → test (Python 3.11/3.12)
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
  - H           # absolute magnitude — proxy for diameter
  - G           # magnitude slope parameter
  - diameter    # measured diameter (km), sparse
  - rot_per     # rotation period (hours), sparse
  - albedo      # geometric albedo, sparse
  - neo         # near-Earth object flag (Y/N)
  - pha         # potentially hazardous asteroid flag (Y/N)
  - class       # orbit classification (APO, ATE, AMO, etc.)
  - moid        # Earth minimum orbit intersection distance (AU)
  - spec_B      # SMASSII spectral taxonomy, sparse

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
# Run the full pipeline end-to-end
make pipeline     # ingest → ingest-lcdb → clean → enrich → score-orbital → score-physical

# Or run stages individually
make ingest          # fetch raw SBDB catalog (~1.5M objects)
make ingest-lcdb     # fetch LCDB rotation periods (~31K records)
make clean-data      # validate and filter → clean Parquet
make enrich          # LCDB merge + H→diameter estimation
make score-orbital   # add orbital features → scored Parquet
make score-physical  # add physical feasibility → scored Parquet
make query           # run a sample query against the atlas

# CLI entry points (after pip install -e .)
asteroid-ingest --page-size 5000 --output data/raw

# Run tests
make test

# Lint and type-check
make lint
make typecheck
```

> **Note:** A full SBDB ingest fetches ~1.5 million records across ~75 paginated requests. On a typical connection this takes a few minutes. Subsequent runs skip all network requests — pages are cached to `data/raw/cache/` by content hash. LCDB download is ~40 MB and takes about a minute.

Available `make` targets:

```
  install         Install package and dev dependencies
  pipeline        Run full pipeline end-to-end
  ingest          Fetch raw SBDB catalog
  ingest-lcdb     Fetch LCDB rotation periods
  clean-data      Validate and filter raw CSV
  enrich          LCDB merge + H→diameter estimation
  score-orbital   Apply orbital scoring
  score-physical  Apply physical feasibility scoring
  query           Run a sample query against the atlas
  data-info       Show available pipeline outputs and metadata
  clean-outputs   Remove processed Parquet outputs (keeps raw data)
  lint            Lint with ruff
  format          Format with ruff
  typecheck       Type-check with mypy
  test            Run tests with coverage
  clean           Remove build artifacts and caches
```

---

## Current Features

**Ingestion** ✓
- Full SBDB catalog fetch via paginated API requests (~1.5M objects, 15 fields)
- LCDB integration — 31K+ rotation periods with quality filtering (U >= 2-)
- Page-level MD5-keyed disk cache — SBDB reruns skip network entirely
- Per-run metadata output (timestamp, source URL, fields, record count)
- Structured JSON logging with retry adapter for API resilience

**Data cleaning** ✓
- Sequential rule-based filter: non-finite elements, a <= 0, e >= 1
- Per-rule removal counts logged to metadata JSON
- Raw data never modified — all filtering is explicit and auditable

**Data enrichment** ✓
- H→diameter estimation via IAU formula (D = 1329/sqrt(pV) x 10^(-H/5))
- Uses measured albedo when available, default pV = 0.154 otherwise
- LCDB merge: taxonomy, albedo gap-fill, rotation provenance tracking
- Provenance columns: `diameter_source` ("measured"/"estimated"), `rotation_source` ("sbdb"/"lcdb")

**Orbital scoring** ✓
- Delta-v proxy (km/s) — Hohmann transfer + inclination correction (Shoemaker-Helin)
- Tisserand parameter w.r.t. Jupiter — orbit stability and accessibility classification
- Inclination penalty — normalised plane-change cost in [0, 1]
- Fully vectorised over the 1.5M-row catalog with strict input validation

**Physical feasibility scoring** ✓
- Surface gravity estimate (m/s²) — spherical model with assumed density (99.9% coverage)
- Rotation feasibility [0, 1] — piecewise model penalising spin-barrier (<2h) and thermal cycling (>100h)
- Regolith likelihood [0, 1] — combined size and rotation signal
- Each feature scored independently (gravity doesn't require rotation data)

**DuckDB query layer** ✓
- Zero-server SQL over Parquet via stable `atlas` view
- Pre-built queries: `top_accessible`, `nea_candidates`, `stats`, `delta_v_histogram`
- Returns DataFrames — ready for web API serialisation or notebook display

**Config system** ✓
- YAML-defined fields with Pydantic validation (`extra="forbid"`)
- `.env` overrides for environment-specific parameters
- All paths resolved to absolute at load time

---

## Dataset Outputs

The atlas dataset (`data/processed/`) contains one row per asteroid in Parquet format.

**Ingested columns** (available after `make ingest`):

| Column | Source | Description |
|---|---|---|
| `spkid` | SBDB | JPL SPK-ID — `20000001` = (1) Ceres |
| `name` | SBDB | Full designation |
| `a_au` | SBDB | Semi-major axis (AU) |
| `eccentricity` | SBDB | Orbital eccentricity |
| `inclination_deg` | SBDB | Orbital inclination (degrees) |
| `abs_magnitude` | SBDB | Absolute magnitude H (99.8% coverage) |
| `magnitude_slope` | SBDB | Magnitude slope parameter G (sparse) |
| `diameter_km` | SBDB | Measured diameter (km) — 9.2% coverage |
| `rotation_hours` | SBDB | Rotation period (hours) — 2.3% coverage |
| `albedo` | SBDB | Geometric albedo — 9.1% coverage |
| `neo` | SBDB | Near-Earth Object flag (Y/N) |
| `pha` | SBDB | Potentially Hazardous Asteroid flag (Y/N) |
| `orbit_class` | SBDB | Orbit classification (APO, ATE, AMO, MBA, etc.) |
| `moid_au` | SBDB | Earth minimum orbit intersection distance (AU) |
| `spectral_type` | SBDB | SMASSII spectral taxonomy (sparse) |

**Enrichment columns** (added by `make enrich`):

| Column | Description |
|---|---|
| `diameter_estimated_km` | Measured diameter (pass-through) or H-derived estimate — 99.9% coverage |
| `diameter_source` | Provenance: "measured" or "estimated" |
| `rotation_source` | Provenance: "sbdb" or "lcdb" |
| `taxonomy` | LCDB taxonomic class (C, S, V, B, M, etc.) — 2% coverage |

**Orbital scoring** (added by `make score-orbital`):

| Column | Description |
|---|---|
| `delta_v_km_s` | Simplified mission delta-v proxy (km/s) — Hohmann + inclination correction |
| `tisserand_jupiter` | Tisserand parameter w.r.t. Jupiter — T_J > 3 main belt, 2–3 accessible NEAs |
| `inclination_penalty` | Normalised plane-change cost in [0, 1] via sin²(i/2) |

**Physical feasibility scoring** (added by `make score-physical`):

| Column | Description |
|---|---|
| `surface_gravity_m_s2` | Estimated surface gravity (m/s²) — 99.9% coverage |
| `rotation_feasibility` | Operational spin-rate score [0, 1] — 2.3% coverage |
| `regolith_likelihood` | Regolith presence score [0, 1] — 2.3% coverage |

**Planned** (added by future pipeline stages):

| Feature Group | Columns |
|---|---|
| Composition | albedo + taxonomy-derived C/S/M-type signal, taxonomy-aware albedo priors |
| Economic | resource density estimate, mission-cost proxy score |
| Ranking | `economic_priority_rank` |

---

## Roadmap

- [x] Ingestion — paginated SBDB fetch (15 fields), caching, metadata logging
- [x] Config system — typed YAML + `.env` loader with Pydantic
- [x] Data cleaning stage — rule-based filter with per-rule removal logging
- [x] Data enrichment — LCDB merge, H→diameter estimation (99.9% coverage)
- [x] LCDB integration — rotation periods, taxonomy, albedo from Lightcurve Database
- [x] Orbital scoring module — delta-v proxies, Tisserand parameter, inclination penalty
- [x] Physical feasibility module — gravity, rotation feasibility, regolith likelihood
- [x] DuckDB query layer — `top_accessible`, `nea_candidates`, `stats`, `delta_v_histogram`
- [x] CI/CD — GitHub Actions with Python 3.11/3.12 matrix
- [ ] NEOWISE integration — ~164K measured diameters/albedos for quality uplift
- [ ] Taxonomy-aware albedo priors — class/family-specific pV for better H→D estimates
- [ ] Composition proxy module — C/S/M-type classification from albedo + taxonomy
- [ ] Economic scoring engine — resource density x accessibility composite
- [ ] Atlas assembly — merge all feature groups into unified ranked dataset
- [ ] Visualization layer — accessibility scatter plots, ranking dashboards
- [ ] JPL Horizons integration — higher-fidelity orbital elements
- [ ] Spectral catalog joins — SDSS/MOVIS taxonomy for improved composition signals

---

## Intended Users

- **Space-resource researchers** building mission shortlists
- **Data engineers** looking for a reference pipeline on scientific catalog processing
- **Trajectory planners** needing a pre-filtered, ranked candidate set
- **Policy and economic analysts** modeling space-resource feasibility at scale

---

## Long-term Vision

Become a reproducible, openly maintained reference dataset for asteroid economic accessibility — updated on a regular cadence as NASA catalogs are refreshed, and extensible as new data sources (NEOWISE, Gaia DR3, spectral surveys) become available. The goal is a living atlas: every asteroid, ranked, with traceable methodology.

---

## Changelog

See [CHANGELOG.md](./CHANGELOG.md) for release history.

---

## License

MIT
