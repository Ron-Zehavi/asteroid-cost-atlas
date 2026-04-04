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
NASA SBDB API     LCDB          NEOWISE (PDS)     SDSS MOC        MOVIS-C         JPL Horizons
     │              │                │                │                │                │
     ▼              ▼                ▼                ▼                ▼                │
┌──────────┐  ┌───────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐       │
│ 1. SBDB  │  │ 1b. LCDB  │  │ 1c. NEOWISE │  │ 1d. SDSS    │  │ 1f. MOVIS-C │       │
│  Ingest  │  │  Ingest   │  │   Ingest    │  │   Ingest    │  │   Ingest    │       │
└────┬─────┘  └─────┬─────┘  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘       │
     │              │               │                │                │               │
     ▼              │               │                │                │               │
┌──────────┐        │               │                │                │               │
│ 2. Clean │        │               │                │                │               │
└────┬─────┘        │               │                │                │               │
     │              │               │                │                │               │
     ▼              ▼               ▼                ▼                ▼               │
┌──────────────────────────────────────────────────────────────────────────┐          │
│  3. Enrich                                                              │          │
│  LCDB merge → NEOWISE merge → SDSS merge → MOVIS merge                  │          │
│  → H→diameter estimation (99.9% coverage)                               │          │
└────────────────────┬────────────────────────────────────────────────────┘          │
                     │                                               │
                     ▼                                               ▼
              ┌──────────────────────┐                    ┌───────────────┐
              │  4. Orbital Features │◄───────────────────│ 1e. Horizons  │
              │  Delta-v, Tisserand  │  Prefer Horizons   │  Ingest (NEA) │
              └──────┬───────────────┘  elements for NEAs └───────────────┘
                     │
                     ▼
              ┌───────────────────────────┐
              │  5. Physical Feasibility  │  Gravity, rotation, regolith
              └──────┬────────────────────┘
                     │
                     ▼
              ┌────────────────────────┐
              │  6. Composition Proxies │  Taxonomy → spectral → SDSS → albedo
              └──────┬─────────────────┘
                     │
                     ▼
              ┌──────────────────────────────┐
              │  7. Economic Scoring + Atlas │  Mass, value → economic_priority_rank
              └──────┬───────────────────────┘
                     │
                     ▼
              ┌──────────────────────────┐
              │  8. Analytics & Outputs  │  DuckDB, Jupyter, visualisation
              └────────────┬─────────────┘
                           │
                           ▼
              ┌──────────────────────────┐
              │  9. Web Application      │  FastAPI API + React/Three.js frontend
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
│   │   ├── ingest_neowise.py    # NEOWISE diameters/albedos (~164K objects)
│   │   ├── ingest_spectral.py   # SDSS MOC photometry, color indices
│   │   ├── ingest_horizons.py   # JPL Horizons high-precision orbital elements (NEAs)
│   │   ├── ingest_movis.py     # MOVIS-C near-IR colors and taxonomy (~18K objects)
│   │   ├── clean_sbdb.py        # Rule-based data cleaning with per-rule logging
│   │   └── enrich.py            # LCDB + NEOWISE + SDSS + MOVIS merge, H→diameter estimation
│   ├── scoring/
│   │   ├── orbital.py           # Delta-v, Tisserand, inclination penalty
│   │   ├── physical.py          # Gravity, rotation feasibility, regolith
│   │   ├── composition.py       # C/S/M/V classification from taxonomy + albedo
│   │   ├── ml_classifier.py     # Random forest composition classifier (94.4% accuracy)
│   │   ├── overlays.py          # Curated radar albedo + measured density overlays
│   │   └── economic.py          # Mass, value, accessibility, ranking
│   ├── models/
│   │   └── asteroid.py          # Pydantic AsteroidRecord model
│   ├── api/
│   │   ├── app.py               # FastAPI app, lifespan, CORS, static serving
│   │   ├── deps.py              # DuckDB dependency injection
│   │   ├── schemas.py           # Pydantic request validation
│   │   └── routes/              # asteroids, stats, search endpoints
│   ├── utils/
│   │   └── query.py             # DuckDB query layer (CostAtlasDB)
│   └── settings.py              # Typed config loader (YAML + .env overrides)
├── tests/
│   ├── conftest.py
│   ├── test_ingest_sbdb.py
│   ├── test_ingest_lcdb.py
│   ├── test_ingest_neowise.py
│   ├── test_ingest_spectral.py
│   ├── test_ingest_horizons.py
│   ├── test_ingest_movis.py
│   ├── test_clean_sbdb.py
│   ├── test_enrich.py
│   ├── test_orbital.py
│   ├── test_physical.py
│   ├── test_composition.py
│   ├── test_economic.py
│   ├── test_query.py
│   ├── test_api.py
│   ├── test_ml_classifier.py
│   ├── test_overlays.py
│   ├── test_pipeline_integration.py
│   └── test_settings.py
├── notebooks/
│   └── explore_atlas.ipynb      # Interactive data explorer (Jupyter)
├── configs/
│   └── config.yaml              # API fields, page size, output paths
├── data/
│   ├── raw/
│   │   ├── cache/               # Page-level API response cache
│   │   └── metadata/            # Per-run fetch metadata (JSON)
│   └── processed/               # Pipeline output Parquets
├── docs/
│   ├── DATA_DICTIONARY.md       # Complete field reference for all pipeline stages
│   └── METHODOLOGY.md           # Scientific methodology, models, and source citations
├── scripts/
│   └── audit.py                   # Pipeline audit: column counts, coverage, baselines
├── web/                           # React frontend (Vite + TypeScript + Three.js)
├── .github/workflows/
│   └── ci.yml                   # Lint → type-check → test (Python 3.11/3.12)
├── Dockerfile                     # Single-container deployment (API + frontend)
├── start.sh                       # One-command launcher (backend :8000 + frontend :5173)
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
# Launch the web application (backend + frontend, opens browser)
./start.sh        # starts API on :8000 and React dev server on :5173

# Run the full pipeline end-to-end
make pipeline     # ingest → enrich → score → atlas (all sources incl. MOVIS-C)

# Or run stages individually
make ingest            # fetch raw SBDB catalog (~1.5M objects)
make ingest-lcdb       # fetch LCDB rotation periods (~31K records)
make ingest-neowise    # fetch NEOWISE diameters/albedos (~164K objects)
make ingest-spectral   # fetch SDSS MOC photometry (~40K objects)
make clean-data        # validate and filter → clean Parquet
make enrich            # LCDB + NEOWISE + SDSS merge, H→diameter estimation
make ingest-horizons   # fetch JPL Horizons elements for NEAs (~35K objects)
make ingest-movis      # fetch MOVIS-C near-IR colors/taxonomy (~18K objects)
make score-orbital     # add orbital features (Horizons-enhanced) → scored Parquet
make score-physical    # add physical feasibility → scored Parquet
make score-composition # classify C/S/M/V from taxonomy + SDSS colors + albedo
make atlas             # economic scoring + final ranked atlas
make query             # run a sample query against the atlas
make audit             # run pipeline audit (column counts, coverage stats)

# Run audit with baseline comparison
python scripts/audit.py --save          # save current audit as baseline
python scripts/audit.py --compare       # compare against saved baseline

# CLI entry points (after pip install -e .)
asteroid-ingest --page-size 5000 --output data/raw

# Run tests
make test

# Lint and type-check
make lint
make typecheck
```

> **Note:** A full SBDB ingest fetches ~1.5 million records across ~75 paginated requests. On a typical connection this takes a few minutes. Subsequent runs skip all network requests — pages are cached to `data/raw/cache/` by content hash. LCDB download is ~40 MB, NEOWISE ~20 MB, SDSS MOC ~50 MB. Horizons is the slowest step — fetching ~35K NEAs at 2 req/s takes several hours; results are cached in `data/raw/horizons_*.parquet`.

Available `make` targets:

```
  install            Install package and dev dependencies (requires Python 3.11+)
  pipeline           Run full pipeline end-to-end
  ingest             Fetch raw SBDB catalog
  ingest-lcdb        Fetch LCDB rotation periods
  ingest-neowise     Fetch NEOWISE diameters/albedos
  ingest-spectral    Fetch SDSS MOC photometry
  ingest-horizons    Fetch JPL Horizons elements for NEAs
  ingest-movis       Fetch MOVIS-C near-IR colors and taxonomy
  clean-data         Validate and filter raw CSV
  enrich             LCDB + NEOWISE + SDSS + MOVIS merge, H→diameter estimation
  score-orbital      Apply orbital scoring (Horizons-enhanced)
  score-physical     Apply physical feasibility scoring
  score-composition  Classify composition from taxonomy + SDSS + albedo
  atlas              Economic scoring + final ranked atlas
  query              Run a sample query against the atlas
  audit              Run pipeline audit (column counts, coverage, baselines)
  data-info          Show available pipeline outputs and metadata
  clean-outputs      Remove processed Parquet outputs (keeps raw data)
  lint               Lint with ruff
  format             Format with ruff
  typecheck          Type-check with mypy
  test               Run tests with coverage
  serve              Start FastAPI backend (uvicorn on :8000)
  web-dev            Start React frontend dev server (Vite on :5173)
  web-build          Production build of the React frontend
  docker             Build Docker image (single-container deployment)
  clean              Remove build artifacts and caches
```

---

## Current Features

**Ingestion** ✓
- Full SBDB catalog fetch via paginated API requests (~1.5M objects, 15 fields)
- LCDB integration — 31K+ rotation periods with quality filtering (U >= 2-)
- NEOWISE integration — ~164K measured diameters and geometric albedos from thermal infrared
- SDSS MOC integration — ~40K photometric color indices for composition inference
- JPL Horizons integration — high-precision orbital elements for NEAs (~35K objects)
- MOVIS-C integration — ~18K near-IR color indices (Y-J, J-Ks, H-Ks) and probabilistic taxonomy from VizieR (Popescu et al. 2018)
- Page-level MD5-keyed disk cache — SBDB reruns skip network entirely
- Per-run metadata output (timestamp, source URL, fields, record count)
- Structured JSON logging with retry adapter for API resilience

**Data cleaning** ✓
- Sequential rule-based filter: non-finite elements, a <= 0, e >= 1
- Per-rule removal counts logged to metadata JSON
- Raw data never modified — all filtering is explicit and auditable

**Data enrichment** ✓
- Five-layer merge: LCDB → NEOWISE → SDSS → MOVIS → H→diameter estimation
- NEOWISE merge: fills diameter gaps (9% → ~20% directly measured), fills albedo gaps (9% → ~20%)
- SDSS merge: adds g-r, r-i color indices for composition inference downstream
- MOVIS merge: adds near-IR Y-J, J-Ks, H-Ks color indices for Bayesian composition model (particularly M-type identification)
- H→diameter estimation via IAU formula (D = 1329/sqrt(pV) x 10^(-H/5))
- Taxonomy-aware albedo priors: measured albedo → NEOWISE → class prior (C: 0.06, S: 0.25, M: 0.14, V: 0.35) → default 0.154
- LCDB merge: taxonomy, albedo gap-fill, rotation provenance tracking
- Provenance columns: `diameter_source` ("measured"/"neowise"/"estimated"), `rotation_source` ("sbdb"/"lcdb")

**Orbital scoring** ✓
- Delta-v proxy (km/s) — Hohmann transfer + inclination correction (Shoemaker-Helin)
- Tisserand parameter w.r.t. Jupiter — orbit stability and accessibility classification
- Inclination penalty — normalised plane-change cost in [0, 1]
- JPL Horizons preference — NEAs use higher-fidelity perturbed elements when available
- `orbital_precision_source` column tracks "horizons" vs "sbdb" element provenance
- Fully vectorised over the 1.5M-row catalog with strict input validation

**Physical feasibility scoring** ✓
- Surface gravity estimate (m/s²) — spherical model with assumed density (99.9% coverage)
- Rotation feasibility [0, 1] — piecewise model penalising spin-barrier (<2h) and thermal cycling (>100h)
- Regolith likelihood [0, 1] — combined size and rotation signal
- Each feature scored independently (gravity doesn't require rotation data)
- NEOWISE-measured diameters improve gravity estimates for ~164K objects

**Composition proxies with meteorite-analog resource model** ✓
- Probabilistic Bayesian composition model with class probability vectors (prob_C/S/M/V), confidence scores, and P10/P50/P90 PGM ranges
- ML classifier (random forest trained on 29,697 spectroscopically confirmed asteroids, 94.4% accuracy) adds ml_prob_C/S/M/V and ml_confidence columns. Requires optional `[ml]` dependency (scikit-learn)
- High-confidence overlays: curated radar albedo (Shepard et al. 2010, 2015) and measured density (Carry 2012) for ~20 well-studied asteroids, adjusting prob_* columns for confirmed metallic/carbonaceous targets
- Six-layer classification: taxonomy → spectral type → SDSS colors → MOVIS NIR → albedo → "U"
- MOVIS NIR colors as additional Bayesian likelihood term (particularly valuable for M-type identification)
- SDSS color-index inference: empirical g-r/r-i boundaries classify C/S/V types
- Multi-resource value model based on Cannon et al. (2023) and Lodders et al. (2025):
  - **Water** — C-type: 15 wt%, extraction yield 60%, $500/kg in-space propellant value
  - **Bulk metals** — Fe/Ni/Co: M-type 98.6 wt%, $50/kg in-orbit construction value
  - **Precious metals** — PGMs+Au: M-type 42 ppm (Cannon 2023 50th %ile), $35,000/kg spot
- Per-class total value: C=$50/kg (water-dominated), M=$25/kg (metals), S=$7/kg, V=$4/kg

**Economic scoring with mission-architecture cost model** ✓
- Mass estimation from diameter + composition-specific density (C: 1,300, S: 2,700, M: 5,300 kg/m³)
- Specimen-return model: selectively extract precious metals (Pt, Pd, Rh, Ir, Os, Ru, Au)
- Subsystem-based mission cost: $300M minimum (spacecraft + payload + ops) + transport + extraction
- Per-asteroid break-even analysis: minimum extraction to cover $300M fixed cost
- **10,310 asteroids** with positive per-kg margin; **498 viable** (enough extractable material)
- Every mission and campaign individually profitable by construction
- Per-metal break-even: kg of each specific metal needed to justify mission
- `economic_priority_rank` — strict ordering with deterministic tie-breaking
- Final atlas: 1,519,870 asteroids scored

**DuckDB query layer** ✓
- Zero-server SQL over Parquet via stable `atlas` view
- Pre-built queries: `top_accessible`, `nea_candidates`, `stats`, `delta_v_histogram`
- Context manager support (`with CostAtlasDB(path) as db:`)
- Input validation on all query parameters
- Returns DataFrames — ready for web API serialisation or notebook display

**Web application** ✓
- FastAPI REST API wrapping the CostAtlasDB query layer (`src/asteroid_cost_atlas/api/`)
- Endpoints: `/api/stats`, `/api/asteroids` (paginated, filterable), `/api/asteroids/{spkid}`, `/api/asteroids/top`, `/api/asteroids/nea`, `/api/search?q=`, `/api/charts/delta-v`, `/api/charts/composition`, `/api/health`
- React frontend (`web/`) with Vite + TypeScript
- AsteroidTable with extraction quantities, 1t/10t/100t profit columns, and composition confidence column
- AsteroidDetail drawer with mining scenario analysis
- FilterBar (default Max Dv = 3 km/s), SearchBox, StatsCards, ComparePanel components
- 3D solar system scene (react-three-fiber / Three.js): Sun + 8 planets with Kepler propagation, asteroid point clouds color-coded by composition/delta-v/viability/confidence, orbit line highlight on selection, camera focus on click
- Orbit zone shading: NEO Region, Main Belt, Jupiter Trojans bands
- Transfer trajectory simulation: Hohmann transfer arcs with 4 mission phases (waiting, window_open, in_transit, arrived) and animated spacecraft dot
- About modal with project vision, methodology, and references
- TimelineSlider for epoch propagation (2000-2035)
- Comparison mode — pin up to 3 asteroids for side-by-side metrics
- 17 API tests, 87.3% total coverage, 27 mypy-clean source files

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
| `diameter_source` | Provenance: "measured", "neowise", or "estimated" |
| `rotation_source` | Provenance: "sbdb" or "lcdb" |
| `taxonomy` | LCDB taxonomic class (C, S, V, B, M, etc.) — 2% coverage |
| `color_gr` | SDSS g-r color index (sparse — ~40K objects) |
| `color_ri` | SDSS r-i color index (sparse — ~40K objects) |

**Orbital scoring** (added by `make score-orbital`):

| Column | Description |
|---|---|
| `delta_v_km_s` | Simplified mission delta-v proxy (km/s) — Hohmann + inclination correction |
| `tisserand_jupiter` | Tisserand parameter w.r.t. Jupiter — T_J > 3 main belt, 2–3 accessible NEAs |
| `inclination_penalty` | Normalised plane-change cost in [0, 1] via sin²(i/2) |
| `orbital_precision_source` | Element provenance: "horizons" (NEAs) or "sbdb" (all others) |

**Physical feasibility scoring** (added by `make score-physical`):

| Column | Description |
|---|---|
| `surface_gravity_m_s2` | Estimated surface gravity (m/s²) — 99.9% coverage |
| `rotation_feasibility` | Operational spin-rate score [0, 1] — 2.3% coverage |
| `regolith_likelihood` | Regolith presence score [0, 1] — 2.3% coverage |

**Composition proxies** (added by `make score-composition`):

| Column | Description |
|---|---|
| `composition_class` | C/S/M/V/U — inferred from taxonomy, spectral type, SDSS colors, or albedo |
| `composition_source` | Provenance: "taxonomy", "sdss_colors", "albedo", or "none" |
| `resource_value_usd_per_kg` | Total $/kg (sum of water + metals + precious) |
| `water_value_usd_per_kg` | Water contribution to value (C-type: $45/kg, others: $0) |
| `metals_value_usd_per_kg` | Bulk metals contribution (M-type: $24.65/kg) |
| `precious_value_usd_per_kg` | PGM+Au contribution (M-type: $0.44/kg) |

**Economic scoring** (added by `make atlas`):

| Column | Description |
|---|---|
| `estimated_mass_kg` | Mass from diameter + composition-specific density |
| `mission_cost_usd_per_kg` | Falcon Heavy round-trip: $2,700 × exp(2 × dv / Ve) |
| `extractable_{metal}_kg` | Extractable kg per metal (platinum, palladium, rhodium, iridium, osmium, ruthenium, gold) |
| `total_extractable_precious_kg` | Sum of all extractable precious metals (kg) |
| `total_precious_value_usd` | Total value of extractable precious metals (USD) |
| `specimen_profit_per_kg` | Specimen value − transport − $5K overhead (>$0 = profitable) |
| `mission_1t_revenue_usd` | Revenue from a 1-ton return mission |
| `mission_1t_profit_usd` | Profit from a 1-ton return mission |
| `economic_score` | precious_value × accessibility (for ranking) |
| `economic_priority_rank` | Strict ranking (1 = best target) — 1,519,870 scored |

> **Full documentation:** See [docs/DATA_DICTIONARY.md](./docs/DATA_DICTIONARY.md) for the complete field reference across all pipeline stages, and [docs/METHODOLOGY.md](./docs/METHODOLOGY.md) for the scientific methodology with full citations.

---

## Resource Valuation Methodology

The economic model is built on measured meteorite compositions, not theoretical estimates.

### Data sources

| Source | Year | What it provides |
|---|---|---|
| **Cannon, Gialich & Acain** | 2023 | PGM concentrations in iron meteorites (50th %ile: 40.8 ppm). Supersedes Kargel (1994) estimates |
| **Lodders, Bergemann & Palme** | 2025 | CI chondrite bulk chemistry: Fe 18.5%, Ni 1.1%, PGM+Au 3.4 ppm |
| **Garenne et al.** | 2014 | Water content in CI/CM/CR chondrites: CI 10–20%, CM 4–13% |
| **Dunn et al.** | 2010 | Metal fractions in ordinary chondrites: H 15–20%, L 7–11% Fe-Ni |

### Resource value model

Each asteroid's value comes from three resource groups:

| Resource | Extraction yield | Price basis | Dominant class |
|---|---|---|---|
| **Water** (H₂O) | 60% | $500/kg in cislunar space (propellant) | C-type (15 wt%) |
| **Bulk metals** (Fe, Ni, Co) | 50% | $50/kg in orbit (construction) | M-type (98.6 wt%) |
| **Precious metals** (PGMs + Au) | 30% | $35,000/kg Earth-return spot | M-type (42 ppm) |

### Resulting values per kg of raw asteroid material

| Class | Water | Metals | Precious | **Total** |
|---|---|---|---|---|
| **C** (carbonaceous) | $45.00 | $4.92 | $0.04 | **$49.96** |
| **M** (metallic) | $0.00 | $24.65 | $0.44 | **$25.09** |
| **S** (silicaceous) | $0.00 | $7.22 | $0.05 | **$7.27** |
| **V** (basaltic) | $0.00 | $3.75 | $0.01 | **$3.76** |
| **U** (unknown) | $4.50 | $6.25 | $0.05 | **$10.80** |

### Mission cost model

Subsystem-based architecture calibrated from Discovery-class analogs (NEAR, Hayabusa2, DART, OSIRIS-REx):

```
total_cost = mission_min_cost
           + system_mass × transport_per_kg
           + extracted_mass × extraction_overhead

margin_per_kg = specimen_value - transport_per_kg - extraction_overhead
break_even_kg = mission_min_cost / margin_per_kg
```

| Parameter | Value | Source |
|---|---|---|
| Mission minimum cost | $300M | Spacecraft bus + mining payload + autonomy + I&T + ops |
| Transport per kg | $2,700 × exp(2 × dv / 3.14) | Falcon Heavy + Tsiolkovsky |
| Extraction overhead | $5,000/kg | Mining + refining equipment amortized |
| System mass | 1,000 kg | Minimum deployed infrastructure |
| Mission capacity | 1,000 kg | Per-mission return payload |

### Specimen-return model

The commodity model values bulk rock, but a real mission selectively extracts only precious metals. The **specimen-return model** computes value from 7 individual metals at spot prices:

| Metal | Spot $/kg | $/oz | C-type ppm | M-type ppm | Source |
|---|---|---|---|---|---|
| Rhodium | $299,000 | $9,300 | 0.13 | 2.0 | Kitco Apr 2, 2026 |
| Iridium | $254,000 | $7,900 | 0.46 | 5.0 | DailyMetalPrice Mar 31, 2026 |
| Gold | $150,740 | $4,690 | 0.15 | 1.0 | Kitco Apr 2, 2026 |
| Platinum | $63,300 | $1,969 | 0.90 | 15.0 | Kitco Apr 2, 2026 |
| Ruthenium | $56,260 | $1,750 | 0.68 | 6.0 | DailyMetalPrice Mar 31, 2026 |
| Palladium | $47,870 | $1,489 | 0.56 | 8.0 | Kitco Apr 2, 2026 |
| Osmium | $12,860 | ~$400 | 0.49 | 5.0 | Raw commodity est. |

Weighted average specimen value: **~$90,000/kg** of refined concentrate.
Extraction yield: 30%. Extraction overhead: $5,000/kg.

### Key findings

**10,310 asteroids** have positive per-kg margin. When the full fixed cost ($300M mission + system mass transport) is included, **498 are viable** — containing enough extractable precious metals for at least one profitable mission. Total of **23,127 profitable missions** supported, with every mission individually profitable.

Top campaign profit: **$371M** across 11 missions. Break-even payload varies by delta-v:
- dv < 1 km/s: ~4,300 kg break-even (margin ~$81K/kg)
- dv = 3 km/s: ~5,500 kg break-even (margin ~$64K/kg)
- dv > ~5.5 km/s: impossible (transport exceeds specimen value)

Per asteroid, the atlas computes:
- **Per-metal extractable mass** (kg of Pt, Pd, Rh, Ir, Os, Ru, Au)
- **Break-even payload** (minimum extraction to cover $300M mission cost)
- **Viability** (asteroid has enough material to break even)
- **Missions supported** (total extraction ÷ mission capacity)
- **Campaign profit** (total revenue − total cost across all missions)

---

## Roadmap

### Phase 1 — Data Pipeline (current)

- [x] Ingestion — paginated SBDB fetch (15 fields), caching, metadata logging
- [x] Config system — typed YAML + `.env` loader with Pydantic
- [x] Data cleaning stage — rule-based filter with per-rule removal logging
- [x] Data enrichment — LCDB merge, H→diameter estimation (99.9% coverage)
- [x] LCDB integration — rotation periods, taxonomy, albedo from Lightcurve Database
- [x] Orbital scoring module — delta-v proxies, Tisserand parameter, inclination penalty
- [x] Physical feasibility module — gravity, rotation feasibility, regolith likelihood
- [x] DuckDB query layer — `top_accessible`, `nea_candidates`, `stats`, `delta_v_histogram`
- [x] CI/CD — GitHub Actions with Python 3.11/3.12 matrix
- [x] Composition proxy module — C/S/M/V classification from taxonomy + albedo
- [x] Economic scoring engine — mass × resource value × accessibility ranking
- [x] Atlas assembly — 33-column unified dataset with `economic_priority_rank`
- [x] Interactive notebook — Jupyter explorer with 10 query sections
- [x] NEOWISE integration — ~164K measured diameters/albedos for quality uplift
- [x] Taxonomy-aware albedo priors — class-specific pV (C: 0.06, S: 0.25, M: 0.14, V: 0.35)
- [x] JPL Horizons integration — higher-fidelity orbital elements (NEA-scoped)
- [x] Spectral catalog joins — SDSS MOC photometry for improved composition signals
- [x] MOVIS-C integration — near-IR color indices and probabilistic taxonomy (~18K objects)

### Phase 2 — Interactive Mission Visualization Platform

The transition from static dataset to decision-support interface. A browser-based tool that lets users explore the atlas visually and plan missions interactively.

**Solar system scene**
- [x] 3D browser-based scene — Sun, planets (Mercury-Neptune), and asteroid belt rendered in real scale
- [x] Asteroid positions computed from Keplerian elements (a, e, i, longitude of ascending node, argument of perihelion)
- [x] Color-coded by atlas score (delta-v, economic priority, composition type)
- [x] Filterable overlays — NEOs only, T_J range, diameter range, orbit class

**Timeline and orbital motion**
- [x] Scrollable time slider — animate orbital positions across months/years
- [x] Epoch-aware positions — propagate mean anomaly forward from SBDB epoch
- [x] Playback controls — play (10 d/s), fast-forward (100 d/s), pause, jump to date
- [x] Smooth animation via useFrame (60fps continuous motion)

**Asteroid selection and detail panel**
- [x] Click/search any asteroid to center view and show orbit
- [x] Orbit visualization — highlight the selected asteroid's full elliptical orbit with km + period labels
- [x] Per-metal resource breakdown in table (Pt, Pd, Rh, Ir, Os, Ru, Au with kg and $ value)

**Visual enhancements**
- [x] Milky Way galaxy skybox (procedural, tilted ~60 deg matching ecliptic-to-galactic angle)
- [x] Asterank-style sun glow (radial gradient sprites, additive blending)
- [x] Planet orbit lines colored to match planet color with orbit length (km) and period labels
- [x] Asteroid point cloud with custom shader (round, glowing, min 4px, diameter-proportional)
- [x] About modal with project vision, methodology summary, and M.A.-style references

**Mission layer architecture**
- [x] REST API serving atlas data from DuckDB (`CostAtlasDB` as backend)
- [x] Filtered stats — dashboard counters refresh with active filters
- [x] Modular frontend — scene renderer (Three.js), UI panels (React), data layer (REST API)

### Phase 3 — Mission Planner (planned)

- [ ] **Mission Planner** — select asteroid, configure mission parameters (payload mass, vehicle, extraction yield), compute cost/revenue/profit per scenario
- [ ] **Multi-scenario comparison** — side-by-side 1t / 10t / 100t / custom payload analysis
- [ ] **Transfer orbit visualization** — show Hohmann transfer path in 3D scene
- [ ] **Launch window analysis** — porkchop plots, per-window delta-v breakdown
- [ ] **Campaign optimizer** — given a fleet budget, find optimal target portfolio

---

## Intended Users

- **Space-resource researchers** building mission shortlists
- **Data engineers** looking for a reference pipeline on scientific catalog processing
- **Trajectory planners** needing a pre-filtered, ranked candidate set
- **Policy and economic analysts** modeling space-resource feasibility at scale

---

## Long-term Vision

Become a reproducible, openly maintained reference dataset **and interactive mission-planning tool** for asteroid economic accessibility. Phase 1 builds the data foundation — a scored, enriched catalog updated on a regular cadence as NASA catalogs are refreshed, extensible with new sources (NEOWISE, MOVIS-C, spectral surveys). Phase 2 puts that data into the hands of mission planners through a browser-based visualization platform where users can explore the solar system, select targets, and evaluate launch windows — turning a static dataset into a living decision-support interface.

---

## Changelog

See [CHANGELOG.md](./CHANGELOG.md) for release history.

---

## License

MIT
