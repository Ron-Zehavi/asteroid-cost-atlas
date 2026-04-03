# Data Dictionary

Complete field reference for the Asteroid Cost Atlas pipeline. Each table below corresponds to one pipeline stage. Columns are cumulative — later stages add to (never remove) earlier columns.

---

## Stage 1: Ingest SBDB

Raw catalog from [NASA Small-Body Database API](https://ssd-api.jpl.nasa.gov/doc/sbdb_query.html). ~1.52M objects, 15 fields.

| Column | Type | Valid Range | Description |
|---|---|---|---|
| `spkid` | int64 | > 0 | JPL SPK-ID. `20000001` = (1) Ceres |
| `name` | string | any | Full designation (e.g., `"1 Ceres (A801 AA)"`) |
| `a_au` | float64 | > 0 | Semi-major axis (AU) |
| `eccentricity` | float64 | [0, 1) | Orbital eccentricity |
| `inclination_deg` | float64 | [0, 180] | Orbital inclination (degrees) |
| `abs_magnitude` | float64 | any | Absolute magnitude H — brightness proxy for size. 99.8% coverage |
| `magnitude_slope` | float64 | any | Phase function slope parameter G. Sparse |
| `diameter_km` | float64 | > 0 or NaN | Measured diameter (km). ~9.2% coverage |
| `rotation_hours` | float64 | > 0 or NaN | Rotation period (hours). ~2.3% coverage |
| `albedo` | float64 | (0, 1] or NaN | Geometric albedo pV. ~9.1% coverage |
| `neo` | string | `"Y"`, `"N"`, NaN | Near-Earth Object flag |
| `pha` | string | `"Y"`, `"N"`, NaN | Potentially Hazardous Asteroid flag |
| `orbit_class` | string | see below | Orbit classification code |
| `moid_au` | float64 | >= 0 | Minimum Orbit Intersection Distance with Earth (AU) |
| `spectral_type` | string | SMASSII codes or NaN | Spectral taxonomy (sparse) |
| `long_asc_node_deg` | float64 | [0, 360) or NaN | Longitude of ascending node (degrees). Used for 3D position computation |
| `arg_perihelion_deg` | float64 | [0, 360) or NaN | Argument of perihelion (degrees). Used for 3D position computation |
| `mean_anomaly_deg` | float64 | [0, 360) or NaN | Mean anomaly at epoch (degrees). Used for epoch propagation |
| `epoch_mjd` | float64 | > 0 or NaN | Epoch of orbital elements (Modified Julian Date). Reference time for mean anomaly |

**`orbit_class` values:** `APO` (Apollo), `ATE` (Aten), `AMO` (Amor), `IEO` (Atira), `MBA` (Main Belt), `MCA` (Mars-crosser), `TJN` (Jupiter Trojan), `TNO` (Trans-Neptunian), `CEN` (Centaur), `OMB` (Outer Main Belt), `IMB` (Inner Main Belt), `HYA` (Hyperbolic), `PAA` (Parabolic), `AST` (unclassified).

---

## Stage 1b: Ingest LCDB

Rotation periods from the [Asteroid Lightcurve Database](https://minplanobs.org/mpinfo/php/lcdb.php). ~31K records after U >= 2- quality filter.

| Column | Type | Valid Range | Description |
|---|---|---|---|
| `spkid` | int64 | > 0 | Join key (number + 20,000,000) |
| `lcdb_rotation_hours` | float64 | > 0 | Rotation period from LCDB (hours) |
| `lcdb_albedo` | float64 | (0, 1] or NaN | Geometric albedo from LCDB |
| `taxonomy` | string | LCDB codes or NaN | Taxonomic class (C, S, B, V, M, X, etc.) |

*These columns are merged into the enrichment stage; only `taxonomy` and gap-filled `rotation_hours`/`albedo` appear in the final atlas.*

---

## Stage 1c: Ingest NEOWISE

Thermal-infrared diameters and albedos from [NEOWISE V2.0](https://sbn.psi.edu/pds/resource/neowisediam.html). ~164K objects.

| Column | Type | Valid Range | Description |
|---|---|---|---|
| `spkid` | int64 | > 0 | Join key |
| `neowise_diameter_km` | float64 | > 0 or NaN | WISE-measured diameter (km) |
| `neowise_albedo` | float64 | (0, 1] or NaN | WISE-measured geometric albedo |

*These fill gaps in `diameter_km` and `albedo` during enrichment; working columns are dropped.*

---

## Stage 1d: Ingest SDSS MOC

Photometric color indices from the [SDSS Moving Object Catalog](https://sbn.psi.edu/pds/resource/sdssmoc.html). ~40K objects.

| Column | Type | Valid Range | Description |
|---|---|---|---|
| `spkid` | int64 | > 0 | Join key |
| `color_gr` | float64 | any or NaN | SDSS g-r color index |
| `color_ri` | float64 | any or NaN | SDSS r-i color index |
| `color_iz` | float64 | any or NaN | SDSS i-z color index |

*Color indices are merged into the enrichment stage and consumed by composition classification.*

---

## Stage 1e: Ingest Horizons

High-precision osculating elements from [JPL Horizons](https://ssd.jpl.nasa.gov/horizons/). NEAs only (~35K objects).

| Column | Type | Valid Range | Description |
|---|---|---|---|
| `spkid` | int64 | > 0 | Join key |
| `a_au_horizons` | float64 | > 0 | Semi-major axis from numerical integration (AU) |
| `eccentricity_horizons` | float64 | [0, 1) | Eccentricity from perturbed model |
| `inclination_deg_horizons` | float64 | [0, 180] | Inclination from perturbed model (degrees) |

*These override SBDB elements for NEAs in the orbital scoring stage.*

---

## Stage 2: Clean

Validation filter. No columns added. Rows removed for:
- Non-finite orbital elements (`a_au`, `eccentricity`, `inclination_deg`)
- `a_au` <= 0
- `eccentricity` >= 1

---

## Stage 3: Enrich

Merges LCDB, NEOWISE, and SDSS data, then estimates diameters from absolute magnitude.

| Column | Type | Valid Range | Description |
|---|---|---|---|
| `rotation_source` | string | `"sbdb"`, `"lcdb"`, NaN | Which catalog supplied the rotation period |
| `taxonomy` | string | LCDB codes or NaN | Taxonomic class from LCDB (C, S, B, V, M, X, etc.) |
| `color_gr` | float64 | any or NaN | SDSS g-r color index (from SDSS merge) |
| `color_ri` | float64 | any or NaN | SDSS r-i color index (from SDSS merge) |
| `color_iz` | float64 | any or NaN | SDSS i-z color index (from SDSS merge) |
| `diameter_estimated_km` | float64 | > 0 or NaN | Measured or H-derived diameter. 99.9% coverage |
| `diameter_source` | string | `"measured"`, `"neowise"`, `"estimated"`, NaN | Provenance of the diameter value |

**`diameter_source` priority:** SBDB measured > NEOWISE measured > H-derived estimate.

**Albedo priority for H-to-diameter formula:** measured (SBDB/LCDB/NEOWISE) > taxonomy class prior (C: 0.06, S: 0.25, M: 0.14, V: 0.35) > population default (0.154).

---

## Stage 4: Orbital Scoring

Accessibility proxies from orbital elements.

| Column | Type | Valid Range | Description |
|---|---|---|---|
| `delta_v_km_s` | float64 | >= 0 or NaN | Simplified mission delta-v (km/s). Hohmann + inclination correction |
| `tisserand_jupiter` | float64 | any or NaN | Tisserand parameter w.r.t. Jupiter. T_J > 3: main belt; 2-3: accessible NEAs; < 2: cometary |
| `inclination_penalty` | float64 | [0, 1] or NaN | Normalised plane-change cost = sin^2(i/2) |
| `orbital_precision_source` | string | `"horizons"`, `"sbdb"` | Whether high-precision Horizons elements were used |

*If Horizons elements are available (NEAs), they override SBDB elements for delta-v computation.*

---

## Stage 5: Physical Feasibility

Surface operation feasibility scores.

| Column | Type | Valid Range | Description |
|---|---|---|---|
| `surface_gravity_m_s2` | float64 | >= 0 or NaN | Estimated surface gravity. Spherical model, rho=2000 kg/m^3. 99.9% coverage |
| `rotation_feasibility` | float64 | [0, 1] or NaN | Operational spin-rate score. 0=too fast (<2h), 1=ideal (4-100h), 0.5=slow (>500h). ~2.3% coverage |
| `regolith_likelihood` | float64 | [0, 1] or NaN | Probability of regolith retention. size_factor x rotation_factor. ~2.3% coverage |

---

## Stage 6: Composition Proxies

Composition classification and resource valuation.

| Column | Type | Valid Range | Description |
|---|---|---|---|
| `composition_class` | string | `"C"`, `"S"`, `"M"`, `"V"`, `"U"` | Inferred resource class. C=carbonaceous, S=silicaceous, M=metallic, V=basaltic, U=unknown |
| `composition_source` | string | `"taxonomy"`, `"sdss_colors"`, `"albedo"`, `"none"` | Which classification layer assigned the class |
| `resource_value_usd_per_kg` | float64 | >= 0 | Total commodity value per kg raw material (water + metals + precious) |
| `water_value_usd_per_kg` | float64 | >= 0 | Water extraction value contribution ($/kg) |
| `metals_value_usd_per_kg` | float64 | >= 0 | Bulk metal extraction value contribution ($/kg) |
| `precious_value_usd_per_kg` | float64 | >= 0 | Precious metal extraction value contribution ($/kg) |
| `specimen_value_per_kg` | float64 | >= 0 | Refined precious concentrate value per kg (weighted spot price) |
| `platinum_ppm` | float64 | >= 0 | Platinum concentration (ppm by mass) |
| `palladium_ppm` | float64 | >= 0 | Palladium concentration (ppm) |
| `rhodium_ppm` | float64 | >= 0 | Rhodium concentration (ppm) |
| `iridium_ppm` | float64 | >= 0 | Iridium concentration (ppm) |
| `osmium_ppm` | float64 | >= 0 | Osmium concentration (ppm) |
| `ruthenium_ppm` | float64 | >= 0 | Ruthenium concentration (ppm) |
| `gold_ppm` | float64 | >= 0 | Gold concentration (ppm) |

**Classification priority:** taxonomy > spectral_type > SDSS g-r/r-i colors > albedo ranges > "U" (unknown).

---

## Stage 7: Economic Scoring (Final Atlas)

Mission cost model, break-even analysis, and campaign economics.

### Mass and transport

| Column | Type | Valid Range | Description |
|---|---|---|---|
| `estimated_mass_kg` | float64 | >= 0 or NaN | Mass assuming sphere with class-specific density |
| `mission_cost_usd_per_kg` | float64 | >= 0 or NaN | Round-trip transport cost: $2,700 x exp(2 x dv / 3.14) $/kg |
| `accessibility` | float64 | >= 0 or NaN | Accessibility score = 1 / dv^2 |

### Per-metal extraction

| Column | Type | Valid Range | Description |
|---|---|---|---|
| `extractable_platinum_kg` | float64 | >= 0 or NaN | Extractable platinum at 30% yield |
| `extractable_palladium_kg` | float64 | >= 0 or NaN | Extractable palladium at 30% yield |
| `extractable_rhodium_kg` | float64 | >= 0 or NaN | Extractable rhodium at 30% yield |
| `extractable_iridium_kg` | float64 | >= 0 or NaN | Extractable iridium at 30% yield |
| `extractable_osmium_kg` | float64 | >= 0 or NaN | Extractable osmium at 30% yield |
| `extractable_ruthenium_kg` | float64 | >= 0 or NaN | Extractable ruthenium at 30% yield |
| `extractable_gold_kg` | float64 | >= 0 or NaN | Extractable gold at 30% yield |
| `total_extractable_precious_kg` | float64 | >= 0 or NaN | Sum of all extractable precious metals (kg) |
| `total_precious_value_usd` | float64 | >= 0 or NaN | Market value of all extractable precious metals |

### Viability

| Column | Type | Valid Range | Description |
|---|---|---|---|
| `margin_per_kg` | float64 | any or NaN | specimen_value - transport - $5K extraction overhead. Positive = profitable per kg |
| `break_even_kg` | float64 | >= 0 or NaN | Minimum total extraction to cover $300M fixed mission cost |
| `is_viable` | bool | True / False | Asteroid has enough extractable material to break even |

### Per-metal break-even

| Column | Type | Valid Range | Description |
|---|---|---|---|
| `break_even_platinum_kg` | float64 | >= 0 or NaN | kg of platinum needed to cover full mission cost |
| `break_even_palladium_kg` | float64 | >= 0 or NaN | kg of palladium needed |
| `break_even_rhodium_kg` | float64 | >= 0 or NaN | kg of rhodium needed |
| `break_even_iridium_kg` | float64 | >= 0 or NaN | kg of iridium needed |
| `break_even_osmium_kg` | float64 | >= 0 or NaN | kg of osmium needed |
| `break_even_ruthenium_kg` | float64 | >= 0 or NaN | kg of ruthenium needed |
| `break_even_gold_kg` | float64 | >= 0 or NaN | kg of gold needed |

### Mission and campaign economics

| Column | Type | Valid Range | Description |
|---|---|---|---|
| `missions_supported` | float64 | >= 0 or NaN | Number of full profitable missions this asteroid supports |
| `mission_revenue_usd` | float64 | >= 0 or NaN | Revenue from one mission (payload x specimen value) |
| `mission_cost_usd` | float64 | >= 0 or NaN | Cost of one mission ($300M + transport + extraction) |
| `mission_profit_usd` | float64 | any or NaN | Profit per mission = revenue - cost |
| `campaign_revenue_usd` | float64 | >= 0 or NaN | Total revenue across all missions |
| `campaign_cost_usd` | float64 | >= 0 or NaN | Total cost across all missions |
| `campaign_profit_usd` | float64 | any or NaN | Total campaign profit = missions x per-mission profit |

### Ranking

| Column | Type | Valid Range | Description |
|---|---|---|---|
| `economic_score` | float64 | >= 0 or NaN | Composite score = total_precious_value x accessibility |
| `economic_priority_rank` | int64 | >= 1 or NaN | Final rank (1 = best target). Deterministic tie-breaking by name |
