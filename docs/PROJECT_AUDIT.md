# Project Audit — Asteroid Cost Atlas

**Date:** 2026-04-02
**Version:** 0.1.0
**Branch:** main (commit f13ff66)
**Python:** 3.11+
**License:** MIT

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Repository Layout](#2-repository-layout)
3. [Technology Stack](#3-technology-stack)
4. [Pipeline Architecture](#4-pipeline-architecture)
5. [Data Sources and Ingestion](#5-data-sources-and-ingestion)
6. [Scoring Models](#6-scoring-models)
7. [Query Layer (CostAtlasDB)](#7-query-layer-costatlasdb)
8. [Final Atlas Schema](#8-final-atlas-schema)
9. [Configuration System](#9-configuration-system)
10. [Testing Infrastructure](#10-testing-infrastructure)
11. [CI/CD](#11-cicd)
12. [Data Inventory](#12-data-inventory)
13. [Documentation](#13-documentation)
14. [Notebook](#14-notebook)
15. [Code Metrics](#15-code-metrics)
16. [Known Limitations](#16-known-limitations)
17. [Web Integration Surface](#17-web-integration-surface)
18. [Appendix A: All Public Functions](#appendix-a-all-public-functions)
19. [Appendix B: All Constants](#appendix-b-all-constants)
20. [Appendix C: Intermodule Dependencies](#appendix-c-intermodule-dependencies)

---

## 1. Executive Summary

Asteroid Cost Atlas is a Python data-engineering pipeline that transforms the NASA Small-Body Database (~1.52M asteroids) into a ranked economic atlas for space-resource missions. It ingests data from 5 public catalogs, applies orbital/physical/composition scoring, and runs a subsystem-based mission cost model to identify viable precious-metal extraction targets.

**Key outputs:**
- `atlas_YYYYMMDD.parquet` — ~1.52M rows, ~80 columns, 156 MB
- 498 asteroids identified as economically viable (positive campaign profit)
- 10,310 asteroids with positive per-kg margin
- 23,127 total profitable missions supported across all viable targets

**Current state:** Phase 1 complete (all 15 roadmap items checked) and Phase 2 web application delivered. The pipeline runs end-to-end, all tests pass (87.3% coverage, 85% gate), lint and strict mypy are clean across 27 source files. A FastAPI REST API and React/Three.js frontend provide browser-based access to the atlas, including a 3D solar system visualization.

---

## 2. Repository Layout

```
asteroid-cost-atlas/
├── src/asteroid_cost_atlas/
│   ├── __init__.py
│   ├── settings.py                    # YAML + .env config loader (Pydantic v2)
│   ├── models/
│   │   └── asteroid.py                # Pydantic AsteroidRecord model (15 fields)
│   ├── ingest/
│   │   ├── ingest_sbdb.py             # NASA SBDB API fetch (paginated, MD5-cached)
│   │   ├── ingest_lcdb.py             # LCDB rotation periods (ZIP download, fixed-width parse)
│   │   ├── ingest_neowise.py          # NEOWISE diameters/albedos (PDS CSV)
│   │   ├── ingest_spectral.py         # SDSS MOC photometry (PDS table)
│   │   ├── ingest_horizons.py         # JPL Horizons orbital elements (REST API, NEA-only)
│   │   ├── clean_sbdb.py              # Rule-based validation filter
│   │   └── enrich.py                  # LCDB + NEOWISE + SDSS merge, H→diameter estimation
│   ├── scoring/
│   │   ├── orbital.py                 # Delta-v, Tisserand, inclination penalty
│   │   ├── physical.py                # Gravity, rotation feasibility, regolith
│   │   ├── composition.py             # C/S/M/V classification, per-metal resource model
│   │   └── economic.py                # Mission cost, break-even, campaign economics, ranking
│   ├── api/
│   │   └── main.py                    # FastAPI REST API wrapping CostAtlasDB
│   └── utils/
│       └── query.py                   # CostAtlasDB — DuckDB SQL over Parquet
├── web/                               # React frontend (Vite + TypeScript + Three.js)
├── tests/                             # 15 test modules (incl. test_api.py)
├── notebooks/
│   └── explore_atlas.ipynb            # 33-cell Jupyter explorer (13 query sections)
├── configs/
│   └── config.yaml                    # SBDB fields, page size, paths
├── docs/
│   ├── DATA_DICTIONARY.md             # Complete field reference (all stages)
│   └── METHODOLOGY.md                 # Scientific methodology + full citations
├── data/
│   ├── raw/                           # Ingested CSVs, Parquets, cache, metadata
│   └── processed/                     # Pipeline stage outputs + final atlas
├── .github/workflows/ci.yml           # Python 3.11/3.12 matrix CI
├── Makefile                           # 20+ targets including full pipeline
├── pyproject.toml                     # hatchling build, deps, tool config
├── CHANGELOG.md
├── Dockerfile                         # Single-container deployment
├── start.sh                           # One-command launcher (API + frontend)
├── CLAUDE.md                          # AI assistant project guidance
└── .env.example
```

---

## 3. Technology Stack

| Layer | Technology | Version | Purpose |
|---|---|---|---|
| Language | Python | 3.11+ | Core pipeline |
| Build | hatchling | latest | PEP 517 packaging |
| Validation | Pydantic | 2.x | Config + model validation (strict, extra="forbid") |
| Data | pandas | 2.x | DataFrame operations |
| Storage | PyArrow / Parquet | 15-19.x | Columnar storage |
| Query | DuckDB | 1.x | Zero-server SQL over Parquet |
| HTTP | requests | 2.31+ | API fetch with retry adapter |
| Config | PyYAML | 6.x | YAML config loading |
| Lint | ruff | 0.4+ | Rules: E, F, I, UP |
| Typecheck | mypy | 1.10+ | Strict mode, all files |
| Test | pytest + pytest-cov | 8.0+ / 5.0+ | 85% coverage gate |

**Phase 2 additions:** FastAPI (REST API), uvicorn (ASGI server), React 18 + Vite + TypeScript (frontend), Three.js / react-three-fiber / @react-three/drei (3D scene), @tanstack/react-table (data grid), lucide-react (icons).

---

## 4. Pipeline Architecture

### Execution Order (strict — each stage depends on the previous)

```
Stage  Module                    Input                           Output                              Columns Added
─────  ────────────────────────  ──────────────────────────────  ──────────────────────────────────  ────────────────────────
 1a    ingest_sbdb               NASA SBDB API                   data/raw/sbdb_{date}.csv            15 base columns
 1b    ingest_lcdb               LCDB ZIP download               data/raw/lcdb_{date}.parquet        rotation, taxonomy, albedo
 1c    ingest_neowise            NEOWISE PDS CSV                 data/raw/neowise_{date}.parquet     diameter, albedo
 1d    ingest_spectral           SDSS MOC PDS table              data/raw/sdss_moc_{date}.parquet    color indices (g-r, r-i, i-z)
 2     clean_sbdb                sbdb_{date}.csv                 sbdb_clean_{date}.parquet           (rows removed, no new cols)
 3     enrich                    sbdb_clean + lcdb + neowise     sbdb_enriched_{date}.parquet        +7 cols (diameter est, rotation src, taxonomy, colors)
                                 + sdss_moc
 1e    ingest_horizons           sbdb_enriched (to get NEA IDs)  data/raw/horizons_{date}.parquet    high-precision a, e, i
 4     orbital                   sbdb_enriched + horizons        sbdb_orbital_{date}.parquet         +4 cols (dv, T_J, inc_penalty, precision_src)
 5     physical                  sbdb_orbital                    sbdb_physical_{date}.parquet        +3 cols (gravity, rotation_feas, regolith)
 6     composition               sbdb_physical                   sbdb_composition_{date}.parquet     +14 cols (class, source, values, 7 metal ppms)
 7     economic                  sbdb_composition                atlas_{date}.parquet                +35 cols (mass, cost, extraction, viability, ranking)
```

### File Discovery Pattern

Every stage finds its input via:
```python
candidates = sorted(processed_dir.glob("sbdb_enriched_*.parquet"))
return candidates[-1]  # latest by date stamp
```

Some stages have fallbacks (e.g., orbital tries `sbdb_enriched_*` then `sbdb_clean_*`). Optional sources (NEOWISE, SDSS, Horizons) are skipped gracefully if not present.

### Makefile Pipeline Command

```makefile
pipeline: ingest ingest-lcdb ingest-neowise ingest-spectral clean-data enrich \
          ingest-horizons score-orbital score-physical score-composition atlas
```

Each target runs: `python -m asteroid_cost_atlas.<module>`

---

## 5. Data Sources and Ingestion

### 5.1 NASA SBDB (ingest_sbdb.py)

| Property | Value |
|---|---|
| URL | `https://ssd-api.jpl.nasa.gov/sbdb_query.api` |
| Records | ~1,520,416 |
| Fields | 15 (spkid, full_name, a, e, i, H, G, diameter, rot_per, albedo, neo, pha, class, moid, spec_B) |
| Pagination | 20,000 rows/page (~76 pages) |
| Caching | Page-level MD5 of (url + fields + page_size + offset) → `data/raw/cache/{hash}.json` |
| Retry | 3x exponential backoff via `requests.adapters.HTTPAdapter` |
| Output | `data/raw/sbdb_{YYYYMMDD}.csv` + `data/raw/metadata/sbdb_{date}.metadata.json` |

**Column rename map:**
```python
{"full_name": "name", "a": "a_au", "e": "eccentricity", "i": "inclination_deg",
 "H": "abs_magnitude", "G": "magnitude_slope", "diameter": "diameter_km",
 "rot_per": "rotation_hours", "moid": "moid_au", "class": "orbit_class",
 "spec_B": "spectral_type"}
```

### 5.2 LCDB (ingest_lcdb.py)

| Property | Value |
|---|---|
| URL | `https://minplanobs.org/MPInfo/datazips/LCLIST_PUB_CURRENT.zip` |
| Format | Fixed-width text (`lc_summary_pub.txt`) inside ZIP |
| Records | ~36K total, ~31K after U >= 2- quality filter |
| Join key | `spkid = asteroid_number + 20,000,000` |
| Quality codes kept | 2-, 2, 2+, 3-, 3 |
| Fields used downstream | `lcdb_rotation_hours`, `lcdb_albedo`, `taxonomy` |
| Output | `data/raw/lcdb_{YYYYMMDD}.parquet` |

### 5.3 NEOWISE (ingest_neowise.py)

| Property | Value |
|---|---|
| URL | `https://sbn.psi.edu/pds/resource/neowisediam/neowise_diameters_albedos_V2_0.csv` |
| Records | ~164K with measured diameters and/or albedos |
| Join key | `spkid = number + 20,000,000` |
| Dedup strategy | Keep largest diameter per asteroid number |
| Fields used downstream | `neowise_diameter_km`, `neowise_albedo` (fill gaps in `diameter_km`, `albedo`) |
| Output | `data/raw/neowise_{YYYYMMDD}.parquet` |

### 5.4 SDSS MOC (ingest_spectral.py)

| Property | Value |
|---|---|
| URL | `https://sbn.psi.edu/pds/resource/sdssmoc/sdssmoc4.tab` |
| Records | ~40K with g, r, i, z photometry |
| Join key | `spkid = number + 20,000,000` |
| Computed indices | `color_gr = g - r`, `color_ri = r - i`, `color_iz = i - z` |
| Fields used downstream | `color_gr`, `color_ri` (consumed by composition classification) |
| Output | `data/raw/sdss_moc_{YYYYMMDD}.parquet` |

### 5.5 JPL Horizons (ingest_horizons.py)

| Property | Value |
|---|---|
| API | `https://ssd.jpl.nasa.gov/api/horizons.api` |
| Scope | NEAs only (~35K objects, identified via `neo = 'Y'` in enriched parquet) |
| Rate limit | 0.5s between requests (~35K objects = ~5 hours) |
| Epoch | J2000 (JD 2451545.0) |
| Fields | `a_au_horizons`, `eccentricity_horizons`, `inclination_deg_horizons` |
| Output | `data/raw/horizons_{YYYYMMDD}.parquet` |

### 5.6 Cleaning (clean_sbdb.py)

Sequential rules (each applied to the output of the previous):

| Rule | Condition | Typical removals |
|---|---|---|
| Non-finite elements | `a_au`, `eccentricity`, or `inclination_deg` is NaN/Inf | ~200 |
| Invalid semi-major axis | `a_au <= 0` | ~50 |
| Hyperbolic orbits | `eccentricity >= 1` | ~300 |
| **Total removed** | | **~546 out of 1,520,416** |

Output: `data/processed/sbdb_clean_{YYYYMMDD}.parquet`

### 5.7 Enrichment (enrich.py)

Four sequential merge layers:

| Layer | Source | Join | Fields Added/Filled | Priority |
|---|---|---|---|---|
| 1. LCDB | `lcdb_*.parquet` | spkid | `rotation_hours` (gaps), `albedo` (gaps), `taxonomy`, `rotation_source` | SBDB > LCDB |
| 2. NEOWISE | `neowise_*.parquet` | spkid | `diameter_km` (gaps), `albedo` (gaps) | SBDB > NEOWISE |
| 3. SDSS | `sdss_moc_*.parquet` | spkid | `color_gr`, `color_ri`, `color_iz` | New columns |
| 4. H→D | Internal computation | — | `diameter_estimated_km`, `diameter_source` | Measured > NEOWISE > Estimated |

**H→Diameter formula:** `D = (1329 / sqrt(albedo)) * 10^(-H/5)` km

**Albedo priority for estimation:** measured (SBDB/LCDB/NEOWISE) → taxonomy class prior (C:0.06, S:0.25, M:0.14, V:0.35) → population default (0.154)

Output: `data/processed/sbdb_enriched_{YYYYMMDD}.parquet`

---

## 6. Scoring Models

### 6.1 Orbital Scoring (orbital.py)

**Required input:** `a_au`, `eccentricity`, `inclination_deg`
**Optional input:** `a_au_horizons`, `eccentricity_horizons`, `inclination_deg_horizons` (preferred when present)

| Feature | Formula | Range | Interpretation |
|---|---|---|---|
| `delta_v_km_s` | `sqrt(dv1^2 + dv2^2 + dv_i^2)` where dv1=departure burn, dv2=arrival burn, dv_i=plane change | >= 0 km/s | Lower = more accessible. Typical NEA: 4-8 km/s |
| `tisserand_jupiter` | `a_J/a + 2*cos(i)*sqrt((a/a_J)*(1-e^2))` | ~1-6 | >3: main belt; 2-3: Jupiter-family/NEA; <2: cometary |
| `inclination_penalty` | `sin^2(i/2)` | [0, 1] | 0=coplanar, 0.5=polar, 1=retrograde |
| `orbital_precision_source` | "horizons" or "sbdb" | enum | Tracks element provenance |

**Constants:** `V_EARTH = 29.78 km/s`, `A_JUPITER = 5.2026 AU`

Output: `data/processed/sbdb_orbital_{YYYYMMDD}.parquet`

### 6.2 Physical Feasibility (physical.py)

**Required input:** `diameter_estimated_km` or `diameter_km`
**Optional input:** `rotation_hours`

| Feature | Formula | Range | Coverage |
|---|---|---|---|
| `surface_gravity_m_s2` | `(2/3)*pi*G*rho*D` with rho=2000 kg/m^3 | >= 0 | 99.9% |
| `rotation_feasibility` | Piecewise: <2h→0, 2-4h→ramp, 4-100h→1.0, 100-500h→ramp down, >500h→0.5 | [0, 1] | ~4% (needs rotation) |
| `regolith_likelihood` | `clamp((D-0.15)/0.85, 0, 1) * clamp((P-2)/2, 0, 1)` | [0, 1] | ~4% (needs both) |

Output: `data/processed/sbdb_physical_{YYYYMMDD}.parquet`

### 6.3 Composition Classification (composition.py)

**Five-layer classification (first non-"U" wins):**

| Layer | Source | Method | Coverage |
|---|---|---|---|
| 1. Taxonomy | LCDB/SBDB `taxonomy` | Map Bus-DeMeo codes → C/S/M/V | ~2% |
| 2. Spectral type | SBDB `spectral_type` | Same taxonomy map | ~8% |
| 3. SDSS colors | `color_gr`, `color_ri` | Empirical boundaries (g-r < 0.50 ∧ r-i < 0.10 → C, etc.) | ~3% |
| 4. Albedo | Measured `albedo` | <0.10→C, 0.10-0.35→S, >=0.35→V | ~9% |
| 5. Default | — | "U" (unknown) | remainder |

**Resource value model (per kg of raw asteroid material):**

| Class | Water $/kg | Metals $/kg | Precious $/kg | Total $/kg | Specimen $/kg |
|---|---|---|---|---|---|
| C | $45.00 | $4.93 | $0.04 | $49.96 | ~$90K |
| S | $0.00 | $7.23 | $0.05 | $7.27 | ~$90K |
| M | $0.00 | $24.65 | $0.44 | $25.09 | ~$90K |
| V | $0.00 | $3.75 | $0.01 | $3.76 | ~$90K |
| U | $4.50 | $6.25 | $0.05 | $10.80 | ~$90K |

*Specimen value is the refined concentrate price (weighted by metal concentrations and spot prices), which is the same ~$90K/kg for any class — what varies is the extractable quantity.*

**7 precious metals tracked individually:**
Platinum (15.0 ppm M-type), Palladium (8.0), Rhodium (2.0), Iridium (5.0), Osmium (5.0), Ruthenium (6.0), Gold (1.0)

Output: `data/processed/sbdb_composition_{YYYYMMDD}.parquet`

### 6.4 Economic Scoring (economic.py)

**Mission cost model:**
```
transport_per_kg  = $2,700 * exp(2 * delta_v / 3.14)
total_fixed       = $300M + 1,000 kg * transport_per_kg
margin_per_kg     = specimen_value - transport_per_kg - $5,000
break_even_kg     = total_fixed / margin_per_kg
is_viable         = total_extractable_precious >= break_even_kg AND margin > 0
missions          = floor(total_extractable / mission_capacity)
```

**Class-specific densities for mass estimation:**
C: 1,300 kg/m^3, S: 2,700, M: 5,300, V: 3,500, U: 2,000

**Per-metal columns added (for each of 7 metals):**
- `extractable_{metal}_kg` = mass * ppm/1e6 * 0.30 yield
- `break_even_{metal}_kg` = $300M / (spot_price - transport - $5K)

**Campaign economics:**
- `mission_revenue_usd` = payload * specimen_value
- `mission_cost_usd` = fixed + payload * (transport + extraction)
- `campaign_profit_usd` = missions * per_mission_profit

**Ranking:** `economic_priority_rank` = row_number ordered by `economic_score` DESC, `name` ASC (deterministic tie-breaking)

Output: `data/processed/atlas_{YYYYMMDD}.parquet` (final)

---

## 7. Query Layer (CostAtlasDB)

**File:** `src/asteroid_cost_atlas/utils/query.py`
**Backend:** In-memory DuckDB connection over a single Parquet file, registered as view `atlas`.

### Constructor

```python
CostAtlasDB(parquet_path: Path)        # Direct path
CostAtlasDB.from_processed_dir(dir)    # Auto-select latest atlas_*.parquet
```

### Methods

| Method | Parameters | Returns | SQL Pattern |
|---|---|---|---|
| `sql(query)` | Raw SQL string | `pd.DataFrame` | Arbitrary — runs against `atlas` view |
| `top_accessible(n, max_delta_v, max_inclination)` | n=50, both optional floats | DataFrame | `SELECT * FROM atlas WHERE delta_v_km_s IS NOT NULL [AND delta_v_km_s <= ?] [AND inclination_deg <= ?] ORDER BY delta_v_km_s ASC LIMIT ?` |
| `nea_candidates(n, max_delta_v)` | n=50, optional float | DataFrame | `SELECT * FROM atlas WHERE tisserand_jupiter >= 2 AND tisserand_jupiter < 3 [AND delta_v_km_s <= ?] ORDER BY delta_v_km_s ASC LIMIT ?` |
| `stats()` | none | Single-row DataFrame | `SELECT COUNT(*) total, COUNT(delta_v_km_s) scored, COUNT(CASE WHEN tisserand >= 2 AND < 3 ...) nea, MIN/MAX/MEDIAN/AVG delta_v` |
| `delta_v_histogram(bin_width)` | bin_width=1.0 | DataFrame | `SELECT FLOOR(delta_v / ?) * ? AS bin_floor, COUNT(*) FROM atlas WHERE delta_v IS NOT NULL GROUP BY 1 ORDER BY 1` |

### Input Validation

All methods validate parameters and raise `ValueError`:
- `n > 0`, `max_delta_v > 0`, `max_inclination > 0`, `bin_width > 0`

### Lifecycle

```python
with CostAtlasDB(path) as db:
    df = db.top_accessible(n=10)
# auto-closes DuckDB connection
```

---

## 8. Final Atlas Schema

The `atlas_YYYYMMDD.parquet` file contains ~80 columns. Grouped by origin:

### Identifiers (2)
`spkid` (int64), `name` (string)

### Orbital Elements (5 + 3 optional)
`a_au`, `eccentricity`, `inclination_deg`, `moid_au`, `spectral_type`
Optional Horizons: `a_au_horizons`, `eccentricity_horizons`, `inclination_deg_horizons`

### Classification Flags (3)
`neo` (Y/N), `pha` (Y/N), `orbit_class` (APO/ATE/AMO/MBA/...)

### Raw Physical (3)
`abs_magnitude`, `magnitude_slope`, `diameter_km`, `rotation_hours`, `albedo`

### Enrichment (7)
`diameter_estimated_km`, `diameter_source`, `rotation_source`, `taxonomy`, `color_gr`, `color_ri`, `color_iz`

### Orbital Scores (4)
`delta_v_km_s`, `tisserand_jupiter`, `inclination_penalty`, `orbital_precision_source`

### Physical Scores (3)
`surface_gravity_m_s2`, `rotation_feasibility`, `regolith_likelihood`

### Composition (14)
`composition_class`, `composition_source`, `resource_value_usd_per_kg`, `water_value_usd_per_kg`, `metals_value_usd_per_kg`, `precious_value_usd_per_kg`, `specimen_value_per_kg`, `platinum_ppm`, `palladium_ppm`, `rhodium_ppm`, `iridium_ppm`, `osmium_ppm`, `ruthenium_ppm`, `gold_ppm`

### Economic — Mass & Transport (3)
`estimated_mass_kg`, `mission_cost_usd_per_kg`, `accessibility`

### Economic — Extraction (9)
`extractable_platinum_kg` ... `extractable_gold_kg` (7), `total_extractable_precious_kg`, `total_precious_value_usd`

### Economic — Viability (3)
`margin_per_kg`, `break_even_kg`, `is_viable`

### Economic — Per-Metal Break-Even (7)
`break_even_platinum_kg` ... `break_even_gold_kg`

### Economic — Mission/Campaign (7)
`missions_supported`, `mission_revenue_usd`, `mission_cost_usd`, `mission_profit_usd`, `campaign_revenue_usd`, `campaign_cost_usd`, `campaign_profit_usd`

### Ranking (2)
`economic_score`, `economic_priority_rank`

**Total: ~78 columns** (varies by ±3 depending on optional Horizons/SDSS availability)

---

## 9. Configuration System

### configs/config.yaml

```yaml
base_url: https://ssd-api.jpl.nasa.gov/sbdb_query.api
sbdb_fields: [spkid, full_name, a, e, i, H, G, diameter, rot_per,
              albedo, neo, pha, class, moid, spec_B]
page_size: 20000
paths:
  raw_json: data/raw/sbdb.json
  csv_dir: data/raw
  cache_dir: data/raw/cache
  metadata_dir: data/raw/metadata
```

### .env overrides

```
SBDB_PAGE_SIZE=20000   # reduce to e.g. 1000 for local testing
```

### Settings classes (Pydantic v2, extra="forbid")

```
YamlConfig → EnvOverrides → ResolvedConfig (all paths absolute)
```

**Note:** NEOWISE, SDSS, and Horizons URLs are currently hardcoded as module-level constants, not in config.yaml. This is a natural extension point.

---

## 10. Testing Infrastructure

### Summary

| Metric | Value |
|---|---|
| Test files | 14 |
| Total tests | 331 |
| Coverage | 87.7% (gate: 85%) |
| Framework | pytest 8.0+ with pytest-cov |
| Fixtures | `tmp_path` (built-in), `config_path`/`env_path` (conftest.py) |
| Mocking | `monkeypatch` for HTTP, `pd.DataFrame.to_parquet` for I/O |

### Per-Module Breakdown

| Test File | Tests | What It Covers |
|---|---|---|
| test_settings.py | 10 | Config loading, .env parsing, path resolution, Pydantic validation |
| test_ingest_sbdb.py | 9 | Page caching, pagination, DataFrame conversion, metadata, main() |
| test_ingest_lcdb.py | 11 | Quality filtering, spkid computation, fixed-width parsing, main() |
| test_ingest_neowise.py | 17 | CSV parsing, dedup, column matching, negative values, main() |
| test_ingest_spectral.py | 14 | Color computation, classification, dedup, main() |
| test_ingest_horizons.py | 11 | Field extraction, response parsing, batch mocking, Horizons preference |
| test_clean_sbdb.py | 29 | Each cleaning rule, rule ordering, metadata, edge cases |
| test_enrich.py | 44 | H→D estimation, LCDB merge, NEOWISE merge, SDSS merge, albedo priors |
| test_orbital.py | 43 | Tisserand, delta-v, inclination penalty, vectorisation, Horizons override |
| test_physical.py | 45 | Gravity, rotation feasibility, regolith, independent scoring |
| test_composition.py | 20 | Taxonomy mapping, albedo classification, SDSS colors, resource values |
| test_economic.py | 19 | Mass estimation, transport cost, break-even, viability, ranking |
| test_query.py | 28 | SQL interface, pre-built queries, input validation, context manager |
| test_pipeline_integration.py | 11 | End-to-end: clean → orbital → physical → composition → economic |

### Testing Patterns

- **Scalar functions:** Tested with known values, edge cases (NaN, Inf, negative, zero), boundary conditions
- **DataFrame transforms:** Verify column addition, row preservation, no input mutation, correct provenance
- **main() functions:** Mocked HTTP + file I/O, verify return code 0
- **Integration:** Full pipeline on synthetic 5-row dataset, verify final atlas has all expected columns

---

## 11. CI/CD

### .github/workflows/ci.yml

```yaml
Trigger: push to main, pull requests
Matrix: Python 3.11, 3.12
Steps:
  1. Install: pip install -e ".[dev]"
  2. Build verify: pip install --no-deps --force-reinstall .
  3. Lint: ruff check src tests
  4. Typecheck: mypy src
  5. Test: pytest --junitxml=test-results.xml
  6. Upload: test-results.xml as artifact
  7. Audit: pip-audit --strict (continue-on-error)
```

---

## 12. Data Inventory

### Processed Parquet Files (current)

| File | Date | Size | Rows | Columns |
|---|---|---|---|---|
| sbdb_clean_20260330.parquet | Mar 30 | 32 MB | ~1.52M | 15 |
| sbdb_enriched_20260401.parquet | Apr 1 | 35 MB | ~1.52M | 22 |
| sbdb_orbital_20260401.parquet | Apr 1 | 61 MB | ~1.52M | 26 |
| sbdb_physical_20260401.parquet | Apr 1 | 64 MB | ~1.52M | 29 |
| sbdb_composition_20260402.parquet | Apr 2 | 66 MB | ~1.52M | 43 |
| **atlas_20260402.parquet** | **Apr 2** | **156 MB** | **~1.52M** | **~78** |

### Raw Data

| Source | File Pattern | Size |
|---|---|---|
| SBDB | `data/raw/sbdb_*.csv` | ~300 MB |
| LCDB | `data/raw/lcdb_*.parquet` | ~5 MB |
| NEOWISE | `data/raw/neowise_*.parquet` | ~10 MB |
| SDSS | `data/raw/sdss_moc_*.parquet` | ~15 MB |
| Horizons | `data/raw/horizons_*.parquet` | ~2 MB |
| Cache | `data/raw/cache/*.json` | ~300 MB (76 pages) |

---

## 13. Documentation

| Document | Location | Lines | Content |
|---|---|---|---|
| README.md | repo root | ~540 | Pipeline overview, setup, usage, features, roadmap, valuation methodology |
| DATA_DICTIONARY.md | docs/ | ~290 | Every column across all 7 pipeline stages with type, range, description |
| METHODOLOGY.md | docs/ | ~430 | Scientific models, formulas, all academic citations with DOIs, known limitations |
| CHANGELOG.md | repo root | varies | Release history |
| CLAUDE.md | repo root | ~55 | AI assistant project guidance |

---

## 14. Notebook

**File:** `notebooks/explore_atlas.ipynb` (33 cells)

| Section | Query Type | What It Shows |
|---|---|---|
| 1. Overview | Aggregation | Total scored, viable, missions, campaign profit |
| 1b. Data Source Coverage | COUNTIF | Diameter/rotation/orbital/composition provenance distribution |
| 2. Most Profitable Campaigns | Top-N | 30 viable targets by campaign_profit DESC |
| 3. Per-Mission Economics | Top-N | Revenue, cost, profit per single mission |
| 4. Per-Metal Break-Even | Top-N | kg of Rh/Au/Ir/Pt needed vs. available |
| 5. M-type Material Inventory | Filtered | Extractable precious metals for metallic asteroids |
| 6. Break-Even by Delta-v | Binned | Profitability by accessibility range (<1, 1-2, ..., 5+ km/s) |
| 7. NEO Targets | Filtered | Viable near-Earth objects ranked by profit |
| 8. By Composition | Grouped | Campaign profit and missions per C/S/M/V/U class |
| 9. By Orbit Class | Grouped | Viable targets per Apollo/Aten/Amor/MBA/etc. |
| 10. Delta-v Distribution | Histogram | Full catalog accessibility distribution |
| 11. Custom Query | Template | User-editable SQL |
| 12. Horizons NEAs | Grouped | Horizons vs. SBDB precision comparison for NEAs |
| 13. Composition Breakdown | Grouped | Classification source x class cross-tabulation |

---

## 15. Code Metrics

| Metric | Value |
|---|---|
| Source files | 16 Python modules |
| Source lines | 3,359 |
| Test files | 14 modules |
| Test lines | 3,262 |
| Total Python | 6,621 lines |
| Test/source ratio | 0.97:1 |
| Test count | 331 |
| Coverage | 87.7% |
| mypy errors | 0 (strict mode) |
| ruff violations | 0 |
| Dependencies (core) | 6 |
| Dependencies (dev) | 7 |

---

## 16. Known Limitations

| # | Limitation | Impact | Mitigation Path |
|---|---|---|---|
| 1 | Circular-orbit delta-v (eccentricity excluded from transfer) | Underestimates delta-v for high-e targets | Tisserand parameter provides complementary stability signal |
| 2 | Static spot prices (April 2026) | Metal volatility not modeled | Parameterize in config, add historical price ranges |
| 3 | Uniform 2000 kg/m^3 density in physical stage | Gravity estimates inaccurate for extreme compositions | Economic stage uses class-specific densities (1300-5300) |
| 4 | M-type albedo ambiguity | M-types classified as S by albedo-only layer | SDSS colors partially mitigate; spectral data needed |
| 5 | Horizons rate-limited to NEAs | Main-belt asteroids use 2-body SBDB elements | Could batch via Horizons email service for MBA |
| 6 | 30% extraction yield assumption | Not empirically validated for space ops | Sensitivity analysis possible with parameterized yield |
| 7 | No launch window or phasing model | Delta-v is a time-independent average, not per-window | Phase 2 target: trajectory optimization |
| 8 | No web layer | Data only accessible via Python/Jupyter | Phase 2 target |

---

## 17. Web Integration Surface

### Ready-to-use Interfaces

**1. CostAtlasDB** — zero-server SQL query engine
```python
from asteroid_cost_atlas.utils.query import CostAtlasDB
db = CostAtlasDB(Path("data/processed/atlas_20260402.parquet"))
df = db.sql("SELECT name, delta_v_km_s, campaign_profit_usd FROM atlas WHERE is_viable ORDER BY campaign_profit_usd DESC LIMIT 10")
# Returns pandas DataFrame — serialize to JSON for API response
```

**2. Pre-built queries** map directly to API endpoints:
| CostAtlasDB Method | Natural REST Endpoint |
|---|---|
| `top_accessible(n, max_delta_v, max_inclination)` | `GET /api/asteroids?n=50&max_dv=5.0` |
| `nea_candidates(n, max_delta_v)` | `GET /api/asteroids/nea?n=50` |
| `stats()` | `GET /api/stats` |
| `delta_v_histogram(bin_width)` | `GET /api/charts/delta_v?bin=1.0` |
| `sql(query)` | `POST /api/query` (with sanitization) |

**3. Single-asteroid lookup** (not yet a method, but trivial):
```sql
SELECT * FROM atlas WHERE spkid = 20000001
SELECT * FROM atlas WHERE name ILIKE '%ceres%'
```

**4. DataFrame → JSON serialization:**
```python
df.to_dict(orient="records")  # list of dicts, ready for JSON response
df.to_json(orient="records")  # JSON string
```

### Data Characteristics for Frontend Planning

| Concern | Value |
|---|---|
| Total rows | ~1,520,000 |
| Final Parquet size | 156 MB |
| DuckDB query time (top-N) | <100ms for indexed scans |
| DuckDB query time (full aggregation) | ~500ms |
| DuckDB memory footprint | ~200 MB (memory-mapped) |
| Viable targets (primary UX focus) | 498 |
| Positive-margin targets | 10,310 |
| NEAs | ~35,000 |
| Columns useful for 3D visualization | `a_au`, `eccentricity`, `inclination_deg` (Keplerian → Cartesian position) |
| Color-coding candidates | `composition_class`, `economic_priority_rank`, `delta_v_km_s`, `is_viable` |
| Search/filter candidates | `name`, `spkid`, `neo`, `orbit_class`, `composition_class`, `is_viable` |

### Asterank Comparison

[Asterank](https://www.asterank.com) is a browser-based asteroid value estimator. Key differences:

| Feature | Asterank | This Project |
|---|---|---|
| Data size | ~600K asteroids | ~1.52M asteroids |
| Composition model | Single heuristic value | 5-layer classification + per-metal concentrations |
| Economic model | Single "value" estimate | Full mission cost with break-even, campaign, per-metal analysis |
| Data sources | SBDB only | SBDB + LCDB + NEOWISE + SDSS + Horizons |
| Metals tracked | Aggregate | 7 individual (Pt, Pd, Rh, Ir, Os, Ru, Au) |
| Mission model | None (just value) | $300M subsystem-based with Tsiolkovsky transport |
| 3D visualization | Yes (Three.js) | Not yet (Phase 2) |
| API | REST | DuckDB query layer (ready to wrap) |

---

## Appendix A: All Public Functions

### ingest_sbdb.py
- `parse_args(default_page_size: int, default_output_dir: Path) -> Namespace`
- `get_cache_path(cache_dir: Path, base_url: str, sbdb_fields: list[str], page_size: int, offset: int) -> Path`
- `fetch_page(session: Session, base_url: str, sbdb_fields: list[str], page_size: int, offset: int, cache_dir: Path) -> dict`
- `fetch_all_pages(session: Session, base_url: str, sbdb_fields: list[str], page_size: int, cache_dir: Path) -> dict`
- `to_dataframe(payload: dict) -> pd.DataFrame`
- `write_metadata(metadata_path: Path, run_date: str, source_url: str, sbdb_fields: list[str], record_count: int) -> None`
- `main() -> int`

### ingest_lcdb.py
- `download_lcdb_zip(url: str, timeout: int) -> bytes`
- `parse_summary(zip_bytes: bytes) -> pd.DataFrame`
- `filter_quality(df: pd.DataFrame, min_quality: frozenset[str]) -> pd.DataFrame`
- `add_spkid(df: pd.DataFrame) -> pd.DataFrame`
- `main() -> int`

### ingest_neowise.py
- `download_neowise(url: str, timeout: int) -> bytes`
- `parse_neowise(raw_bytes: bytes) -> pd.DataFrame`
- `add_spkid(df: pd.DataFrame) -> pd.DataFrame`
- `main() -> int`

### ingest_spectral.py
- `download_sdss_moc(url: str, timeout: int) -> bytes`
- `parse_sdss_moc(raw_bytes: bytes) -> pd.DataFrame`
- `classify_from_sdss_colors(color_gr: float, color_ri: float) -> str`
- `add_spkid(df: pd.DataFrame) -> pd.DataFrame`
- `main() -> int`

### ingest_horizons.py
- `fetch_horizons_elements(spkid: int, epoch_jd: str, api_url: str, timeout: int) -> dict | None`
- `fetch_batch(spkids: list[int], epoch_jd: str, api_url: str) -> pd.DataFrame`
- `main() -> int`

### clean_sbdb.py
- `clean(df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, int]]`
- `main() -> int`

### enrich.py
- `h_to_diameter_km(h: float, albedo: float) -> float`
- `merge_lcdb(df: pd.DataFrame, lcdb_path: Path) -> pd.DataFrame`
- `merge_neowise(df: pd.DataFrame, neowise_path: Path) -> pd.DataFrame`
- `merge_sdss(df: pd.DataFrame, sdss_path: Path) -> pd.DataFrame`
- `add_diameter_estimate(df: pd.DataFrame) -> pd.DataFrame`
- `main() -> int`

### orbital.py
- `tisserand_parameter(a: float, e: float, i_deg: float, a_j: float) -> float`
- `delta_v_proxy_km_s(a: float, e: float, i_deg: float) -> float`
- `inclination_penalty(i_deg: float) -> float`
- `add_orbital_features(df: pd.DataFrame) -> pd.DataFrame`
- `main() -> int`

### physical.py
- `surface_gravity_m_s2(diameter_km: float) -> float`
- `rotation_feasibility(period_hours: float) -> float`
- `regolith_likelihood(diameter_km: float, period_hours: float) -> float`
- `add_physical_features(df: pd.DataFrame) -> pd.DataFrame`
- `main() -> int`

### composition.py
- `classify_taxonomy(taxonomy: str | None) -> str`
- `classify_albedo(albedo: float) -> str`
- `specimen_value_per_kg(composition_class: str) -> float`
- `resource_value_per_kg(composition_class: str) -> float`
- `resource_breakdown(composition_class: str) -> dict[str, float]`
- `add_composition_features(df: pd.DataFrame) -> pd.DataFrame`
- `main() -> int`

### economic.py
- `estimated_mass_kg(diameter_km: float, composition_class: str) -> float`
- `mission_cost_per_kg(delta_v_km_s: float) -> float`
- `accessibility_score(delta_v_km_s: float) -> float`
- `add_economic_score(df: pd.DataFrame) -> pd.DataFrame`
- `main() -> int`

### query.py (CostAtlasDB)
- `__init__(parquet_path: Path) -> None`
- `from_processed_dir(processed_dir: Path) -> CostAtlasDB` (classmethod)
- `sql(query: str) -> pd.DataFrame`
- `top_accessible(n: int, max_delta_v: float | None, max_inclination: float | None) -> pd.DataFrame`
- `nea_candidates(n: int, max_delta_v: float | None) -> pd.DataFrame`
- `stats() -> pd.DataFrame`
- `delta_v_histogram(bin_width: float) -> pd.DataFrame`
- `close() -> None`

---

## Appendix B: All Constants

### Orbital (orbital.py)
| Name | Value | Unit |
|---|---|---|
| V_EARTH_KM_S | 29.78 | km/s |
| A_JUPITER_AU | 5.2026 | AU |

### Physical (physical.py)
| Name | Value | Unit |
|---|---|---|
| _G | 6.674e-11 | m^3 kg^-1 s^-2 |
| _RHO_KG_M3 | 2000.0 | kg/m^3 |

### Economic (economic.py)
| Name | Value | Unit |
|---|---|---|
| FALCON_LEO_COST | 2,700 | $/kg |
| ISP | 320 | seconds |
| G0 | 9.81 | m/s^2 |
| VE | 3.14 | km/s |
| MISSION_MIN_COST | 300,000,000 | USD |
| MISSION_SYSTEM_MASS_KG | 1,000 | kg |
| EXTRACTION_OVERHEAD | 5,000 | $/kg |
| MISSION_CAPACITY_KG | 1,000 | kg |

### Composition Densities (economic.py)
| Class | Density | Unit |
|---|---|---|
| C | 1,300 | kg/m^3 |
| S | 2,700 | kg/m^3 |
| M | 5,300 | kg/m^3 |
| V | 3,500 | kg/m^3 |
| U | 2,000 | kg/m^3 |

### Metal Spot Prices (composition.py, April 2026)
| Metal | $/kg |
|---|---|
| Rhodium | 299,000 |
| Iridium | 254,000 |
| Gold | 150,740 |
| Platinum | 63,300 |
| Ruthenium | 56,260 |
| Palladium | 47,870 |
| Osmium | 12,860 |

### Albedo Priors (enrich.py)
| Class | Prior pV |
|---|---|
| C | 0.06 |
| S | 0.25 |
| M | 0.14 |
| V | 0.35 |
| Default | 0.154 |

### Extraction Yields (composition.py)
| Resource | Yield |
|---|---|
| Water | 60% |
| Bulk metals | 50% |
| Precious metals | 30% |

### Commodity Prices
| Resource | $/kg |
|---|---|
| Water (cislunar) | 500 |
| Bulk metals (in-orbit) | 50 |

---

## Appendix C: Intermodule Dependencies

### Import Graph

```
composition.py ← ingest_spectral.py  (classify_from_sdss_colors)
enrich.py      ← composition.py       (classify_taxonomy for albedo priors)
economic.py    ← composition.py       (METAL_SPOT_PRICE, METALS, PRECIOUS_EXTRACTION_YIELD)
```

### Data Dependencies (Pipeline Order)

```
ingest_sbdb ─┐
ingest_lcdb ─┤
ingest_neowise ─┤
ingest_spectral ─┤
              ▼
          clean_sbdb
              │
              ▼
           enrich (merges LCDB + NEOWISE + SDSS)
              │
              ├──── ingest_horizons (reads enriched to identify NEAs)
              ▼
          orbital (merges Horizons if available)
              │
              ▼
          physical
              │
              ▼
         composition
              │
              ▼
          economic → atlas_YYYYMMDD.parquet (FINAL)
```

### Column Dependency Chain

```
economic REQUIRES: diameter_estimated_km, delta_v_km_s, composition_class,
                   resource_value_usd_per_kg, specimen_value_per_kg, {metal}_ppm
  └── composition REQUIRES: (optional) taxonomy, spectral_type, albedo, color_gr, color_ri
        └── physical REQUIRES: diameter_estimated_km OR diameter_km; rotation_hours (optional)
              └── orbital REQUIRES: a_au, eccentricity, inclination_deg
                    └── enrich REQUIRES: abs_magnitude; (optional) diameter_km, albedo, rotation_hours
                          └── clean REQUIRES: a_au, eccentricity, inclination_deg
```

---

## Phase 2: Web Application

### Overview

Phase 2 adds a browser-based interface on top of the Phase 1 data pipeline. A FastAPI REST API wraps the existing `CostAtlasDB` query layer, and a React/Three.js frontend provides interactive exploration of the atlas including a 3D solar system visualization.

### API Layer (`src/asteroid_cost_atlas/api/`)

The API is a thin FastAPI application that delegates all data access to `CostAtlasDB`.

| Endpoint | Method | Description |
|---|---|---|
| `/api/health` | GET | Health check |
| `/api/stats` | GET | Catalog-wide statistics (total objects, NEAs, viable count, etc.) |
| `/api/asteroids` | GET | Paginated, filterable asteroid list |
| `/api/asteroids/top` | GET | Top-ranked targets by economic priority |
| `/api/asteroids/nea` | GET | Near-Earth asteroid candidates |
| `/api/asteroids/{spkid}` | GET | Single asteroid detail (all atlas columns) |
| `/api/search?q=` | GET | Name/designation search |
| `/api/charts/delta-v` | GET | Delta-v distribution histogram data |
| `/api/charts/composition` | GET | Composition class breakdown data |

Backend dependencies (optional `[web]` extra): `fastapi`, `uvicorn`.

17 API tests in `tests/test_api.py`.

### Frontend (`web/`)

React 18 application built with Vite and TypeScript.

**Key components:**

| Component | Purpose |
|---|---|
| `AsteroidTable` | Sortable, filterable data grid with extraction quantities and 1t/10t/100t profit columns |
| `AsteroidDetail` | Slide-out drawer with full atlas data and mining scenario analysis |
| `FilterBar` | Controls for orbit class, composition, delta-v range, diameter, NEO/PHA flags |
| `SearchBox` | Typeahead asteroid name/designation search |
| `StatsCards` | Summary statistics dashboard (total objects, viable targets, top profit, etc.) |
| `ComparePanel` | Side-by-side comparison of up to 3 pinned asteroids |
| `TimelineSlider` | Epoch slider (2000-2035) for orbital position propagation |

**Frontend dependencies:** react, three, @react-three/fiber, @react-three/drei, @tanstack/react-table, lucide-react.

### 3D Solar System Scene

Built with react-three-fiber (React renderer for Three.js) and @react-three/drei helpers.

**Scene elements:**
- **Sun** at origin with emissive glow
- **8 planets** (Mercury through Neptune) orbiting with Kepler propagation from real orbital elements
- **Asteroid point clouds** — instanced meshes for performance, color-coded by composition class, delta-v, or viability score
- **Orbit line highlight** — when an asteroid is selected, its full elliptical orbit is rendered as a line
- **Camera focus** — clicking an asteroid or planet smoothly transitions the camera to that object

**Keplerian propagation** uses 4 additional orbital fields added to the pipeline ingest: `long_asc_node_deg`, `arg_perihelion_deg`, `mean_anomaly_deg`, `epoch_mjd`. These allow computing 3D positions at any epoch via standard two-body propagation (mean anomaly advance + eccentric anomaly solve via Newton iteration).

**Timeline slider** advances the epoch across 2000-2035, updating all object positions in real time.

### Deployment

| Method | Command | Description |
|---|---|---|
| Development | `./start.sh` | Starts backend on `:8000` and frontend dev server on `:5173`, opens browser |
| Backend only | `make serve` | Runs `uvicorn` on `:8000` |
| Frontend dev | `make web-dev` | Runs Vite dev server on `:5173` |
| Frontend build | `make web-build` | Production build of React app |
| Docker | `docker build -t asteroid-atlas .` | Single-container image serving both API and frontend |

### Test Coverage

- 17 API endpoint tests in `tests/test_api.py`
- Total project coverage: 87.3% (85% gate)
- 27 mypy-clean source files under strict mode
