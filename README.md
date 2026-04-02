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
│  6. Composition Proxies │  C/S/M/V classification from taxonomy + albedo
└──────┬─────────────────┘
       │  data/processed/sbdb_composition_*.parquet
       ▼
┌──────────────────────────────┐
│  7. Economic Scoring + Atlas │  Mass, value, accessibility → economic_priority_rank
└──────┬───────────────────────┘
       │  data/processed/atlas_*.parquet (33 columns, final output)
       ▼
┌──────────────────────────┐
│  8. Analytics & Outputs  │  DuckDB query layer, Jupyter notebook, visualisation
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
│   │   ├── physical.py          # Gravity, rotation feasibility, regolith
│   │   ├── composition.py       # C/S/M/V classification from taxonomy + albedo
│   │   └── economic.py          # Mass, value, accessibility, ranking
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
│   ├── test_composition.py
│   ├── test_economic.py
│   ├── test_query.py
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
make pipeline     # ingest → clean → enrich → orbital → physical → composition → atlas

# Or run stages individually
make ingest            # fetch raw SBDB catalog (~1.5M objects)
make ingest-lcdb       # fetch LCDB rotation periods (~31K records)
make clean-data        # validate and filter → clean Parquet
make enrich            # LCDB merge + H→diameter estimation
make score-orbital     # add orbital features → scored Parquet
make score-physical    # add physical feasibility → scored Parquet
make score-composition # classify C/S/M/V composition from taxonomy + albedo
make atlas             # economic scoring + final ranked atlas
make query             # run a sample query against the atlas

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
  install            Install package and dev dependencies
  pipeline           Run full pipeline end-to-end
  ingest             Fetch raw SBDB catalog
  ingest-lcdb        Fetch LCDB rotation periods
  clean-data         Validate and filter raw CSV
  enrich             LCDB merge + H→diameter estimation
  score-orbital      Apply orbital scoring
  score-physical     Apply physical feasibility scoring
  score-composition  Classify composition from taxonomy + albedo
  atlas              Economic scoring + final ranked atlas
  query              Run a sample query against the atlas
  data-info          Show available pipeline outputs and metadata
  clean-outputs      Remove processed Parquet outputs (keeps raw data)
  lint               Lint with ruff
  format             Format with ruff
  typecheck          Type-check with mypy
  test               Run tests with coverage
  clean              Remove build artifacts and caches
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
- Taxonomy-aware albedo priors: measured albedo → class prior (C: 0.06, S: 0.25, M: 0.14, V: 0.35) → default 0.154
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

**Composition proxies with meteorite-analog resource model** ✓
- C/S/M/V/U classification from taxonomy → spectral type → albedo inference
- Multi-resource value model based on Cannon et al. (2023) and Lodders et al. (2025):
  - **Water** — C-type: 15 wt%, extraction yield 60%, $500/kg in-space propellant value
  - **Bulk metals** — Fe/Ni/Co: M-type 98.6 wt%, $50/kg in-orbit construction value
  - **Precious metals** — PGMs+Au: M-type 42 ppm (Cannon 2023 50th %ile), $35,000/kg spot
- Per-class total value: C=$50/kg (water-dominated), M=$25/kg (metals), S=$7/kg, V=$4/kg
- 149,782 classified (29,991 from taxonomy, 119,791 from albedo)

**Economic scoring and atlas assembly** ✓
- Mass estimation from diameter + composition-specific density (C: 1,300, S: 2,700, M: 5,300 kg/m³)
- Mission cost model: $2,700/kg LEO (Falcon Heavy) × exp(2 × dv / Ve), Isp=320s bipropellant
- Profit ratio: resource_value / mission_cost — **no asteroid is profitable with current chemical propulsion** (best ratio: 0.012). Profitability requires Starship-class economics (~$100/kg LEO) or electric propulsion (Isp ~3000s)
- `economic_priority_rank` — strict ordering with deterministic tie-breaking
- Final atlas: 1,519,870 asteroids scored across 36 columns

**DuckDB query layer** ✓
- Zero-server SQL over Parquet via stable `atlas` view
- Pre-built queries: `top_accessible`, `nea_candidates`, `stats`, `delta_v_histogram`
- Context manager support (`with CostAtlasDB(path) as db:`)
- Input validation on all query parameters
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

**Composition proxies** (added by `make score-composition`):

| Column | Description |
|---|---|
| `composition_class` | C/S/M/V/U — inferred from taxonomy, spectral type, or albedo |
| `composition_source` | Provenance: "taxonomy", "albedo", or "none" |
| `resource_value_usd_per_kg` | Total $/kg (sum of water + metals + precious) |
| `water_value_usd_per_kg` | Water contribution to value (C-type: $45/kg, others: $0) |
| `metals_value_usd_per_kg` | Bulk metals contribution (M-type: $24.65/kg) |
| `precious_value_usd_per_kg` | PGM+Au contribution (M-type: $0.44/kg) |

**Economic scoring** (added by `make atlas`):

| Column | Description |
|---|---|
| `estimated_mass_kg` | Mass from diameter + composition-specific density |
| `estimated_value_usd` | mass × resource_value_usd_per_kg |
| `mission_cost_usd_per_kg` | Round-trip delivery cost: $2,700 × exp(2 × dv / Ve) |
| `profit_ratio` | resource_value / mission_cost — >1 means theoretically profitable |
| `accessibility` | 1/delta_v² — energy cost scaling |
| `economic_score` | estimated_value × accessibility |
| `economic_priority_rank` | Strict ranking (1 = best target) — 1,519,870 scored |

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

Round-trip delivery cost per kg, based on Tsiolkovsky rocket equation:

```
cost_per_kg = $2,700 × exp(2 × delta_v / Ve)
```

| Parameter | Value | Source |
|---|---|---|
| LEO launch cost | $2,700/kg | Falcon Heavy (2024) |
| Specific impulse | 320 s | Bipropellant (MMH/NTO) |
| Exhaust velocity | 3.14 km/s | Isp × g₀ |
| Round-trip factor | 2× | Outbound + return |

### Key finding: no asteroid is currently profitable

The best case is a C-type NEO at delta-v 0.74 km/s with a profit ratio of **0.012** — still 85× too expensive. This is consistent with the literature: asteroid mining with chemical propulsion is not economically viable at current launch costs.

Profitability requires one or more of:
- **Starship-class launch costs** (~$100/kg to LEO instead of $2,700)
- **Electric propulsion** (Isp ~3,000 s instead of 320 s — 10× more fuel-efficient)
- **In-situ resource utilization** (use water as propellant at the asteroid, avoiding Earth-return costs)

The atlas ranking remains valid for **comparative** target selection: "which asteroid is the *least unprofitable*" is the right question for planning future missions under improved economics.

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
- [ ] NEOWISE integration — ~164K measured diameters/albedos for quality uplift
- [x] Taxonomy-aware albedo priors — class-specific pV (C: 0.06, S: 0.25, M: 0.14, V: 0.35)
- [ ] JPL Horizons integration — higher-fidelity orbital elements
- [ ] Spectral catalog joins — SDSS/MOVIS taxonomy for improved composition signals

### Phase 2 — Interactive Mission Visualization Platform

The transition from static dataset to decision-support interface. A browser-based tool that lets users explore the atlas visually and plan missions interactively.

**Solar system scene**
- [ ] 3D browser-based scene — Sun, planets (Mercury–Neptune), and asteroid belt rendered in real scale
- [ ] Asteroid positions computed from Keplerian elements (a, e, i, longitude of ascending node, argument of perihelion)
- [ ] Color-coded by atlas score (delta-v, economic priority, composition type)
- [ ] Filterable overlays — NEOs only, T_J range, diameter range, orbit class

**Timeline and orbital motion**
- [ ] Scrollable time slider — animate orbital positions across months/years
- [ ] Epoch-aware positions — propagate mean anomaly forward from SBDB epoch
- [ ] Playback controls — play, pause, speed adjustment, jump to date

**Asteroid selection and detail panel**
- [ ] Click/search any asteroid to open a detail panel with all atlas columns
- [ ] Orbit visualization — highlight the selected asteroid's full elliptical orbit
- [ ] Comparison mode — pin multiple asteroids to compare accessibility metrics side-by-side

**Launch window analysis**
- [ ] For a selected asteroid, compute approximate launch windows from Earth over a date range
- [ ] Per-window trajectory visualization — show the transfer orbit (Earth → asteroid) in the 3D scene
- [ ] Delta-v breakdown per window — departure burn, arrival burn, inclination correction
- [ ] Porkchop plot — departure date vs arrival date contour map of total delta-v

**Mission layer architecture**
- [ ] REST API serving atlas data from DuckDB (`CostAtlasDB` as backend)
- [ ] WebSocket or polling for timeline state synchronisation
- [ ] Modular frontend — scene renderer (Three.js / Cesium), UI panels (React), trajectory solver (WASM or server-side)
- [ ] Plugin architecture for future mission types (sample return, flyby, rendezvous, mining)

---

## Intended Users

- **Space-resource researchers** building mission shortlists
- **Data engineers** looking for a reference pipeline on scientific catalog processing
- **Trajectory planners** needing a pre-filtered, ranked candidate set
- **Policy and economic analysts** modeling space-resource feasibility at scale

---

## Long-term Vision

Become a reproducible, openly maintained reference dataset **and interactive mission-planning tool** for asteroid economic accessibility. Phase 1 builds the data foundation — a scored, enriched catalog updated on a regular cadence as NASA catalogs are refreshed, extensible with new sources (NEOWISE, Gaia DR3, spectral surveys). Phase 2 puts that data into the hands of mission planners through a browser-based visualization platform where users can explore the solar system, select targets, and evaluate launch windows — turning a static dataset into a living decision-support interface.

---

## Changelog

See [CHANGELOG.md](./CHANGELOG.md) for release history.

---

## License

MIT
