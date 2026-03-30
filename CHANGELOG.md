# Changelog

All notable changes to this project are documented here.

---

## [Unreleased]

### Added
- `CostAtlasDB` DuckDB query layer over processed Parquet atlas (`utils/query.py`)
  — `top_accessible()`, `nea_candidates()`, `stats()`, `delta_v_histogram()`, raw `sql()`
- Orbital scoring module (`scoring/orbital.py`)
  — `tisserand_parameter`, `delta_v_proxy_km_s`, `inclination_penalty`, `add_orbital_features`
  — Vectorised over 1.5M rows with strict input validation
- Data cleaning stage (`ingest/clean_sbdb.py`)
  — Sequential rule-based filter: non-finite elements, `a ≤ 0`, `e ≥ 1`
  — Per-run metadata JSON with removal counts per rule
- SBDB ingestion pipeline (`ingest/ingest_sbdb.py`)
  — Paginated API fetch with MD5-keyed page-level disk cache
  — Structured JSON logging, per-run metadata output
- Typed config loader (`settings.py`)
  — YAML + `.env` overrides via Pydantic v2, absolute path resolution
- `make pipeline` target — runs `ingest → clean-data → score-orbital` in order
- `make query` target — sample DuckDB query against the latest atlas

### Pipeline output (data/processed/)
- `sbdb_clean_*.parquet` — 1,521,517 rows after removing 546 corrupt/hyperbolic records
- `sbdb_orbital_*.parquet` — same rows with `tisserand_jupiter`, `delta_v_km_s`,
  `inclination_penalty` added; 0 null scores

### Planned
- Physical feasibility module (rotation, gravity proxy, regolith likelihood)
- Composition proxy module (C/S/M-type classification from albedo)
- Economic scoring engine (resource density × accessibility composite)
- Atlas assembly (unified ranked dataset)
- JPL Horizons, NEOWISE, LCDB, spectral catalog integrations
