# Changelog

All notable changes to this project are documented here.

---

## [Unreleased]

### Added
- Physical feasibility scoring module (`scoring/physical.py`)
  — `surface_gravity_m_s2`, `rotation_feasibility`, `regolith_likelihood`
  — Each feature scored independently; gravity achieves 99.9% coverage
- Data enrichment stage (`ingest/enrich.py`)
  — H→diameter estimation via IAU formula (D = 1329/sqrt(pV) x 10^(-H/5))
  — LCDB merge: fills rotation/albedo gaps, adds taxonomy column
  — Provenance tracking: `diameter_source`, `rotation_source` columns
- LCDB ingestion (`ingest/ingest_lcdb.py`)
  — Downloads and parses LCDB fixed-width summary (~36K records)
  — Quality filter U >= 2- retains 31K reliable periods
  — Join key: asteroid number + 20,000,000 = SBDB spkid
- Expanded SBDB ingestion: 7 new fields
  — `H` (absolute magnitude), `G` (magnitude slope), `neo`, `pha`,
    `class` (orbit classification), `moid` (Earth MOID), `spec_B` (spectral type)
- `CostAtlasDB` DuckDB query layer over processed Parquet atlas (`utils/query.py`)
  — `top_accessible()`, `nea_candidates()`, `stats()`, `delta_v_histogram()`, raw `sql()`
- Orbital scoring module (`scoring/orbital.py`)
  — `tisserand_parameter`, `delta_v_proxy_km_s`, `inclination_penalty`, `add_orbital_features`
  — Vectorised over 1.5M rows with strict input validation
- Data cleaning stage (`ingest/clean_sbdb.py`)
  — Sequential rule-based filter: non-finite elements, `a <= 0`, `e >= 1`
  — Per-run metadata JSON with removal counts per rule
- SBDB ingestion pipeline (`ingest/ingest_sbdb.py`)
  — Paginated API fetch with MD5-keyed page-level disk cache
  — Retry adapter (3 retries, backoff, 429/500/503 handling)
  — Structured JSON logging, per-run metadata output
- Typed config loader (`settings.py`)
  — YAML + `.env` overrides via Pydantic v2, absolute path resolution
- CI/CD: GitHub Actions workflow with Python 3.11/3.12 matrix
- `AsteroidRecord` Pydantic model with Field descriptions (`models/asteroid.py`)
- `py.typed` marker for downstream type checking
- `make pipeline` target — runs full pipeline in order
- `make data-info` / `make clean-outputs` targets

### Pipeline output (data/processed/)
- `sbdb_clean_*.parquet` — 1,521,650 rows after removing 546 corrupt/hyperbolic records
- `sbdb_enriched_*.parquet` — 139,690 measured diameters + 1,380,180 H-estimated diameters
- `sbdb_orbital_*.parquet` — delta-v, Tisserand, inclination penalty (100% coverage)
- `sbdb_physical_*.parquet` — gravity (99.9%), rotation feasibility (2.3%), regolith (2.3%)

### Planned
- NEOWISE integration (~164K measured diameters/albedos)
- Taxonomy-aware albedo priors for improved H→diameter estimates
- Composition proxy module (C/S/M-type classification)
- Economic scoring engine (resource density x accessibility composite)
- Atlas assembly (unified ranked dataset)
- Visualization layer
