# Scientific Methodology and Source Documentation

Technical reference documenting the physical models, empirical parameters, data sources, and economic assumptions underlying the Asteroid Atlas pipeline. All models and constants are traceable to published literature or publicly available data catalogs.

---

## 1. Data Sources and Catalogs

### 1.1 NASA Small-Body Database (SBDB)

The primary asteroid catalog. Orbital elements are derived from astrometric observations and fit to Keplerian two-body solutions.

- **API endpoint:** `https://ssd-api.jpl.nasa.gov/sbdb_query.api`
- **Documentation:** JPL SSD, "SBDB Query API," [ssd-api.jpl.nasa.gov/doc/sbdb_query.html](https://ssd-api.jpl.nasa.gov/doc/sbdb_query.html)
- **Coverage:** ~1.52M cataloged small bodies (as of 2026)
- **Fields used:** spkid, full_name, a, e, i, H, G, diameter, rot_per, albedo, neo, pha, class, moid, spec_B

### 1.2 Asteroid Lightcurve Database (LCDB)

Rotation periods, taxonomic classifications, and albedos compiled from lightcurve photometry.

- **Source:** Warner, B. D., Harris, A. W., & Pravec, P. (2009). "The asteroid lightcurve database." *Icarus*, 202(1), 134-146. doi:[10.1016/j.icarus.2009.02.003](https://doi.org/10.1016/j.icarus.2009.02.003)
- **URL:** [minplanobs.org/mpinfo/php/lcdb.php](https://minplanobs.org/mpinfo/php/lcdb.php)
- **Coverage:** ~36K records; filtered to U >= 2- (reliable) = ~31K
- **Quality codes retained:** 2-, 2, 2+, 3-, 3 (following Warner et al. recommended threshold)
- **Used for:** Rotation period gap-filling, taxonomy, albedo gap-filling

### 1.3 NEOWISE Diameters and Albedos

Thermal-infrared diameter and geometric albedo measurements from the WISE spacecraft's NEOWISE mission.

- **Source:** Mainzer, A. K., et al. (2019). "NEOWISE Diameters and Albedos V2.0." *NASA Planetary Data System*, urn:nasa:pds:neowise_diameters_albedos::2.0. doi:[10.26033/18S3-2Z54](https://doi.org/10.26033/18S3-2Z54)
- **URL:** [sbn.psi.edu/pds/resource/neowisediam.html](https://sbn.psi.edu/pds/resource/neowisediam.html)
- **Coverage:** ~164K asteroids with measured diameters and/or albedos
- **Used for:** Diameter gap-filling (before H-to-D estimation), albedo gap-filling (before taxonomy priors)

### 1.4 SDSS Moving Object Catalog (MOC4)

Multi-band photometry (u, g, r, i, z) of asteroids observed serendipitously during the Sloan Digital Sky Survey.

- **Source:** Hasselmann, P. H., Carvano, J. M., & Lazzaro, D. (2012). "SDSS-based Asteroid Taxonomy V1.1." *NASA Planetary Data System*, EAR-A-I0035-5-SDSSTAX-V1.1.
- **Photometric calibration:** Ivezic, Z., et al. (2001). "Solar System Objects Observed in the Sloan Digital Sky Survey Commissioning Data." *Astronomical Journal*, 122(5), 2749-2784. doi:[10.1086/323452](https://doi.org/10.1086/323452)
- **URL:** [sbn.psi.edu/pds/resource/sdssmoc.html](https://sbn.psi.edu/pds/resource/sdssmoc.html)
- **Coverage:** ~40K asteroids with g, r, i, z magnitudes
- **Used for:** Color-index (g-r, r-i) based composition inference

### 1.6 MOVIS-C Near-Infrared Catalog

Near-infrared color indices and probabilistic taxonomy for ~18K asteroids observed in VISTA-VHS.

- **Source:** Popescu, M., et al. (2018). "MOVIS-C: A catalog of Visible-NIR colors of asteroids observed with VISTA-VHS." *Astronomy & Astrophysics*, 617, A12. doi:[10.1051/0004-6361/201833023](https://doi.org/10.1051/0004-6361/201833023)
- **URL:** VizieR catalog J/A+A/617/A12 at [vizier.cds.unistra.fr](https://vizier.cds.unistra.fr)
- **Coverage:** 18,081 asteroids with Y-J, J-Ks, H-Ks color indices
- **Join key:** `spkid = number + 20,000,000`
- **Used for:** NIR-based Bayesian composition likelihood, particularly valuable for M-type identification

### 1.5 JPL Horizons Ephemeris System

On-demand computation of high-precision osculating orbital elements using numerical integration models that account for planetary perturbations.

- **System:** Giorgini, J. D., et al. (1996). "JPL's On-Line Solar System Data Service." *Bulletin of the American Astronomical Society*, 28, 1158.
- **API endpoint:** `https://ssd.jpl.nasa.gov/api/horizons.api`
- **Documentation:** [ssd-api.jpl.nasa.gov/doc/horizons.html](https://ssd-api.jpl.nasa.gov/doc/horizons.html)
- **Scope:** NEAs only (~35K objects), to respect API rate limits
- **Epoch:** J2000 (JD 2451545.0 = 2000-01-01.5 TDB)
- **Used for:** Improved delta-v estimates for NEA mission targets

---

## 2. Orbital Mechanics Models

### 2.1 Delta-v Proxy (Hohmann + Inclination Correction)

A simplified mission accessibility metric estimating the total velocity change required for an Earth-to-asteroid transfer.

**Model:**
```
dv_1  = V_E * |sqrt(2a / (1+a)) - 1|              departure burn
dv_2  = (V_E / sqrt(a)) * |1 - sqrt(2 / (1+a))|   arrival circularisation
dv_i  = 2 * v_mid * sin(i/2)                       inclination correction
v_mid = V_E * sqrt(2 / (1+a))                      velocity at transfer midpoint
dv    = sqrt(dv_1^2 + dv_2^2 + dv_i^2)             total delta-v (km/s)
```

**Constants:**
- V_E = 29.78 km/s (Earth heliocentric velocity)

**Assumptions:** Circular-orbit approximation — eccentricity enters only via the Tisserand parameter, not the delta-v computation directly. This is a standard simplification for catalog-scale ranking (not trajectory optimization).

**References:**
- Shoemaker, E. M., & Helin, E. (1979). "Earth-Approaching Asteroids as Targets for Exploration." *NASA CP-2053*, 245-256.
- Sanchez, J. P., & McInnes, C. R. (2011). "Asteroid Resource Map for Near-Earth Space." *Journal of Spacecraft and Rockets*, 48(1), 153-165. doi:[10.2514/1.49851](https://doi.org/10.2514/1.49851)

### 2.2 Tisserand Parameter

A quasi-integral of the restricted three-body problem (Sun-Jupiter-asteroid) that classifies orbit families.

**Formula:** T_J = a_J / a + 2 * cos(i) * sqrt((a / a_J) * (1 - e^2))

**Constants:**
- a_J = 5.2026 AU (Jupiter semi-major axis)

**Classification:**
| T_J | Interpretation |
|---|---|
| > 3 | Main-belt; non-Jupiter-crossing |
| 2 - 3 | Jupiter-family comets; accessible NEAs |
| < 2 | Halley-type; long-period comets |

### 2.3 Inclination Penalty

Normalised plane-change cost, representing the fractional velocity required for a pure orbital plane change.

**Formula:** penalty = sin^2(i/2)

| Inclination | Penalty | Interpretation |
|---|---|---|
| 0 deg | 0.0 | Coplanar with ecliptic |
| 90 deg | 0.5 | Polar orbit |
| 180 deg | 1.0 | Retrograde |

---

## 3. Physical Feasibility Models

### 3.1 Surface Gravity

Spherical body with uniform bulk density.

**Formula:** g = (2/3) * pi * G * rho * D

**Constants:**
- G = 6.674 x 10^-11 m^3 kg^-1 s^-2 (CODATA 2018)
- rho = 2000 kg/m^3 (assumed average bulk density)

**Note:** The 2000 kg/m^3 density is a population average for stony/carbonaceous asteroids. The economic scoring stage uses composition-specific densities (see Section 5.1). The physical stage intentionally uses a single density to avoid circular dependency (composition classification happens later in the pipeline).

### 3.2 Rotation Feasibility

Piecewise linear score penalising operationally difficult spin rates.

| Period | Score | Rationale |
|---|---|---|
| < 2 h | 0.0 | Spin barrier — centrifugal force exceeds gravity for cohesionless bodies |
| 2 - 4 h | 0.0 -> 1.0 | Transition zone |
| 4 - 100 h | 1.0 | Ideal operational window |
| 100 - 500 h | 1.0 -> 0.5 | Long thermal cycles complicate operations |
| > 500 h | 0.5 | Very slow rotation, still feasible |

**Reference:** The 2-hour spin barrier corresponds to the cohesionless rubble-pile limit.
- Pravec, P., & Harris, A. W. (2000). "Fast and Slow Rotation of Asteroids." *Icarus*, 148(1), 12-20. doi:[10.1006/icar.2000.6482](https://doi.org/10.1006/icar.2000.6482)

### 3.3 Regolith Likelihood

Product of two independent signals: size factor and rotation factor.

**Formulas:**
```
size_factor     = clamp((D_km - 0.15) / (1.0 - 0.15), 0, 1)
rotation_factor = clamp((period_h - 2.0) / (4.0 - 2.0), 0, 1)
regolith        = size_factor * rotation_factor
```

**Rationale:**
- Asteroids smaller than ~150 m are unlikely to retain regolith due to low gravity and micrometeorite gardening efficiency.
- Fast rotators (< 2 h) shed loose material regardless of size.
- Both thresholds are empirically motivated by observational constraints on asteroid surface properties (e.g., thermal inertia measurements from WISE).

---

## 4. Composition Classification

### 4.1 Taxonomy-to-Class Mapping

Asteroid spectral types are mapped to five resource classes following the Bus-DeMeo taxonomy system.

| Resource Class | Analog | Mapped Taxonomies |
|---|---|---|
| **C** (carbonaceous) | CI/CM chondrites | C, B, F, G, D, T, CB, CG, CH, CX |
| **S** (silicaceous) | H/L/LL chondrites | S, K, L, A, Q, R, O, SA, SK, SL, SQ, SR, SE, SFC |
| **M** (metallic) | Iron meteorites | M, X, E, P, XC, XE |
| **V** (basaltic) | HED achondrites | V |
| **U** (unknown) | Population average | All unresolved types |

**Reference:**
- DeMeo, F. E., & Carry, B. (2013). "The Taxonomic Distribution of Asteroids from Multi-filter All-sky Photometric Surveys." *Icarus*, 226(1), 723-741. doi:[10.1016/j.icarus.2013.06.027](https://doi.org/10.1016/j.icarus.2013.06.027)

### 4.2 Classification Priority

Six layers are applied sequentially; the first layer to assign a non-"U" class wins. MOVIS NIR colors also serve as an additional Bayesian likelihood term when computing class probability vectors (prob_C/S/M/V).

1. **Taxonomy** — direct LCDB/SBDB taxonomy via the mapping above
2. **Spectral type** — SBDB SMASSII spectral classification via the same mapping
3. **SDSS color indices** — empirical g-r / r-i boundaries (Section 4.3)
4. **MOVIS NIR colors** — near-infrared class-conditional distributions (Section 4.6)
5. **Albedo** — measured geometric albedo thresholds
6. **Default** — "U" (unknown)

### 4.3 SDSS Color-Index Classification

Empirical boundaries derived from the SDSS asteroid color-color distribution.

| Condition | Class | Rationale |
|---|---|---|
| g-r < 0.50 and r-i < 0.10 | C | Low reflectance, neutral/blue slope |
| g-r < 0.45 and r-i > 0.10 | V | Blue-to-red slope with 1-micron absorption |
| g-r >= 0.50 and r-i < 0.20 | S | Moderate reflectance, red slope |
| g-r >= 0.45 and r-i >= 0.10 | S | Redder S-complex |
| Otherwise | U | Ambiguous |

**References:**
- Ivezic, Z., et al. (2001). "Solar System Objects Observed in the Sloan Digital Sky Survey." *AJ*, 122, 2749. doi:[10.1086/323452](https://doi.org/10.1086/323452)
- DeMeo, F. E., & Carry, B. (2013). *Icarus*, 226, 723.

### 4.4 Albedo-Based Classification

Fallback when no spectral data is available.

| Albedo Range | Class |
|---|---|
| < 0.10 | C (dark, carbonaceous) |
| 0.10 - 0.35 | S (moderate) |
| >= 0.35 | V (bright, basaltic) |

**Note:** M-types cannot be distinguished from S-types by albedo alone (both are moderate). This is a known limitation of albedo-only classification.

### 4.5 Taxonomy-Aware Albedo Priors

When a measured albedo is unavailable but taxonomy is known, the H-to-diameter formula uses class-specific geometric albedo priors from the WISE/NEOWISE survey.

| Class | Prior pV | Source |
|---|---|---|
| C | 0.06 | Mainzer et al. (2011) |
| S | 0.25 | Mainzer et al. (2011) |
| M | 0.14 | Mainzer et al. (2011) |
| V | 0.35 | Mainzer et al. (2011) |
| Default | 0.154 | Population average |

**Reference:**
- Mainzer, A. K., et al. (2011). "NEOWISE Observations of Near-Earth Objects: Preliminary Results." *Astrophysical Journal*, 743(2), 156. doi:[10.1088/0004-637X/743/2/156](https://doi.org/10.1088/0004-637X/743/2/156)

### 4.6 MOVIS Near-Infrared Classification

When MOVIS-C near-infrared color indices are available, they provide an additional likelihood term in the Bayesian composition model. The class-conditional distributions used are based on the MOVIS-C catalog centroids from Popescu et al. (2018):

| Class | Y-J (mean) | J-Ks (mean) | Characteristic |
|---|---|---|---|
| **C** (carbonaceous) | ~0.30 | ~0.35 | Neutral/blue NIR slope, low reflectance |
| **S** (silicaceous) | ~0.38 | ~0.55 | Moderately red NIR slope |
| **M** (metallic) | ~0.32 | ~0.42 | Intermediate slope, distinguishable from S |
| **V** (basaltic) | ~0.40 | ~0.60 | Reddest NIR slope, strong 1-micron band |

MOVIS NIR colors are particularly valuable for distinguishing M-types from S-types, which overlap in visible albedo space. The Y-J and J-Ks indices provide orthogonal classification power to SDSS optical colors.

**Reference:**
- Popescu, M., et al. (2018). "MOVIS-C: A catalog of Visible-NIR colors of asteroids observed with VISTA-VHS." *Astronomy & Astrophysics*, 617, A12. doi:[10.1051/0004-6361/201833023](https://doi.org/10.1051/0004-6361/201833023)

### 4.7 ML Composition Classifier

A random forest classifier provides an independent composition prediction trained on spectroscopically confirmed asteroids.

**Training set:** 29,697 asteroids with confirmed taxonomic classifications from LCDB/SDSS spectral surveys.

**Features:** Orbital elements (a, e, i), absolute magnitude (H), albedo, SDSS color indices (g-r, r-i, i-z), MOVIS NIR colors (Y-J, J-Ks, H-Ks) where available.

**Output:** Per-class probability predictions (ml_prob_C, ml_prob_S, ml_prob_M, ml_prob_V) and an overall ml_confidence score (maximum predicted probability).

**Performance:** 94.4% accuracy on held-out test set (stratified split). The classifier is most valuable for objects lacking spectral data but having photometric colors and/or albedo measurements.

**Dependency:** Requires scikit-learn, available via the optional `[ml]` install extra (`pip install -e ".[ml]"`).

### 4.8 High-Confidence Overlays

For approximately 20 well-studied asteroids with direct physical measurements, curated literature values override or refine the probabilistic composition estimates.

**Radar albedo** from Shepard et al. (2010, 2015) — high radar albedo (> 0.3) is a strong indicator of metallic (M-type) composition. These measurements directly adjust the prob_M probability upward for confirmed metallic targets.

**Measured bulk density** from Carry (2012) — density measurements constrain composition more tightly than spectral classification alone. High densities (> 4,000 kg/m^3) confirm metallic composition; low densities (< 2,000 kg/m^3) support carbonaceous classification.

**Columns added:** `radar_albedo`, `measured_density_kg_m3`, `overlay_source`.

**References:**
- Shepard, M. K., et al. (2010). "A radar survey of M- and X-class asteroids." *Icarus*, 208(1), 221-237. doi:[10.1016/j.icarus.2010.01.017](https://doi.org/10.1016/j.icarus.2010.01.017)
- Shepard, M. K., et al. (2015). "A radar survey of M- and X-class asteroids. III. Insights into their composition, hydration state, and structure." *Icarus*, 245, 38-55. doi:[10.1016/j.icarus.2014.09.016](https://doi.org/10.1016/j.icarus.2014.09.016)
- Carry, B. (2012). "Density of asteroids." *Planetary and Space Science*, 73(1), 98-118. doi:[10.1016/j.pss.2012.03.009](https://doi.org/10.1016/j.pss.2012.03.009)

---

### 4.9 Hohmann Transfer Simulation (Web)

The web frontend includes a visual Hohmann transfer trajectory simulation for mission planning visualization.

**Model:** Standard two-impulse Hohmann transfer between circular coplanar orbits (Earth orbit to asteroid semi-major axis). The simulation tracks four mission phases:

1. **Waiting** — spacecraft at Earth orbit, awaiting launch window
2. **Window open** — optimal departure alignment reached
3. **In transit** — spacecraft following the transfer ellipse (animated dot along arc)
4. **Arrived** — spacecraft at target asteroid orbit

The transfer arc is computed from the Hohmann transfer semi-major axis: `a_transfer = (r_earth + r_target) / 2`. Transfer time follows Kepler's third law: `T = pi * sqrt(a_transfer^3 / mu_sun)`.

**Mission state coloring (web):** During the launch window phase, Earth's emissive material is tinted green to mark it as the active departure body. When the spacecraft reaches the target, the selected asteroid is rendered as a green-tinted overlay sphere for the duration of the arrival window. Both effects are driven by `getCurrentMissionPhase()` in `web/src/utils/transfer.ts`, which is the single source of truth for the four-phase computation across the scene components.

This visualization is pedagogical — it illustrates the energy cost represented by the delta-v proxy but does not replace the simplified Hohmann + inclination model used for catalog-scale ranking.

---

## 5. Resource Valuation Model

### 5.1 Composition-Specific Densities

| Class | Density (kg/m^3) | Analog |
|---|---|---|
| C | 1,300 | CI chondrite |
| S | 2,700 | H/L chondrite |
| M | 5,300 | Iron meteorite |
| V | 3,500 | HED achondrite |
| U | 2,000 | Population average |

### 5.2 Water Content and Valuation

| Class | Water wt% | Extraction Yield | Price $/kg | $/kg Raw | Source |
|---|---|---|---|---|---|
| C | 15.0 | 60% | $500 | $45.00 | Garenne et al. (2014) |
| S | 0.0 | — | — | $0.00 | Anhydrous |
| M | 0.0 | — | — | $0.00 | Anhydrous |
| V | 0.0 | — | — | $0.00 | Anhydrous |
| U | 1.5 | 60% | $500 | $4.50 | Population average |

**References:**
- Garenne, A., et al. (2014). "The abundance and stability of 'water' in type 1 and 2 carbonaceous chondrites (CI, CM and CR)." *Geochimica et Cosmochimica Acta*, 137, 93-112. doi:[10.1016/j.gca.2014.03.034](https://doi.org/10.1016/j.gca.2014.03.034)
- Water price ($500/kg) reflects projected in-space propellant value in cislunar economy.

### 5.3 Bulk Metal Content and Valuation

| Class | Metal wt% | Extraction Yield | Price $/kg | $/kg Raw | Source |
|---|---|---|---|---|---|
| C | 19.7 | 50% | $50 | $4.93 | Lodders et al. (2025) — Fe 18.5%, Ni 1.1% |
| S | 28.9 | 50% | $50 | $7.23 | Dunn et al. (2010) — H/L chondrite |
| M | 98.6 | 50% | $50 | $24.65 | Iron meteorite composition |
| V | 15.0 | 50% | $50 | $3.75 | HED achondrite |
| U | 25.0 | 50% | $50 | $6.25 | Population average |

**References:**
- Lodders, K., Bergemann, M., & Palme, H. (2025). "Solar System Abundances of the Elements." arXiv:[2502.10575](https://arxiv.org/abs/2502.10575).
- Dunn, T. L., et al. (2010). "Principal component analysis of spectral data of ordinary chondrites." *Icarus*, 208(2), 789-797. doi:[10.1016/j.icarus.2010.02.016](https://doi.org/10.1016/j.icarus.2010.02.016)
- Bulk metal price ($50/kg) reflects projected in-orbit construction material value.

### 5.4 Precious Metal Concentrations (ppm by mass)

| Metal | C-type | S-type | M-type | V-type | U-type | Primary Source |
|---|---|---|---|---|---|---|
| Platinum | 0.90 | 1.20 | 15.0 | 0.10 | 1.50 | Lodders+ (2025), Cannon+ (2023) |
| Palladium | 0.56 | 0.75 | 8.0 | 0.06 | 0.90 | Lodders+ (2025), Cannon+ (2023) |
| Rhodium | 0.13 | 0.17 | 2.0 | 0.01 | 0.20 | Lodders+ (2025), Cannon+ (2023) |
| Iridium | 0.46 | 0.61 | 5.0 | 0.05 | 0.70 | Lodders+ (2025), Cannon+ (2023) |
| Osmium | 0.49 | 0.65 | 5.0 | 0.05 | 0.75 | Lodders+ (2025), Cannon+ (2023) |
| Ruthenium | 0.68 | 0.90 | 6.0 | 0.07 | 1.00 | Lodders+ (2025), Cannon+ (2023) |
| Gold | 0.15 | 0.20 | 1.0 | 0.02 | 0.25 | Lodders+ (2025), Cannon+ (2023) |
| **Total** | **3.37** | **4.48** | **42.0** | **0.36** | **5.30** | |

**C-type values** are from Lodders, Bergemann & Palme (2025) Table 4 (CI chondrite bulk chemistry).

**M-type values** are from Cannon, Gialich & Acain (2023) — median (50th percentile) PGM concentrations in iron meteorites. Total PGM = 40.78 ppm; individual metals scaled from CI ratios multiplied by the iron enrichment factor.

**S-type and V-type values** are interpolated from CI and M-type concentrations, weighted by the metal fraction typical of each class.

**U-type values** are population-weighted averages.

**References:**
- Cannon, K. M., Gialich, S., & Acain, A. (2023). "Accessible Precious Metals on Asteroids." *Planetary and Space Science*, 225, 105608. doi:[10.1016/j.pss.2022.105608](https://doi.org/10.1016/j.pss.2022.105608)
- Lodders, K., Bergemann, M., & Palme, H. (2025). arXiv:[2502.10575](https://arxiv.org/abs/2502.10575).

### 5.5 Precious Metal Spot Prices

Prices as of April 2, 2026. Conversion: $/troy oz x 32.1507 = $/kg.

| Metal | $/kg | $/troy oz | Source | Date |
|---|---|---|---|---|
| Rhodium | $299,000 | $9,300 | Kitco | Apr 2, 2026 |
| Iridium | $254,000 | $7,900 | DailyMetalPrice | Mar 31, 2026 |
| Gold | $150,740 | $4,690 | Kitco | Apr 2, 2026 |
| Platinum | $63,300 | $1,969 | Kitco | Apr 2, 2026 |
| Ruthenium | $56,260 | $1,750 | DailyMetalPrice | Mar 31, 2026 |
| Palladium | $47,870 | $1,489 | Kitco | Apr 2, 2026 |
| Osmium | $12,860 | ~$400 | Raw commodity estimate | — |

**Extraction yield:** 30% (refining in space).

---

## 6. Mission Cost Model

### 6.1 Transport Cost (Tsiolkovsky Rocket Equation)

**Formula:** transport_per_kg = FALCON_LEO_COST * exp(2 * dv / Ve)

| Parameter | Value | Notes |
|---|---|---|
| FALCON_LEO_COST | $2,700/kg | Falcon Heavy to LEO (SpaceX published pricing) |
| ISP | 320 s | Specific impulse (chemical bipropellant) |
| g_0 | 9.81 m/s^2 | Standard gravity |
| Ve | 3.14 km/s | Effective exhaust velocity = ISP * g_0 / 1000 |

The factor of 2 accounts for round-trip delta-v (Earth -> asteroid -> Earth return).

### 6.2 Mission Fixed Cost

| Component | Value | Calibration |
|---|---|---|
| Mission minimum cost | $300M | Spacecraft bus + mining payload + autonomy + I&T + operations reserve |

Calibrated from Discovery-class mission analogs:
- **NEAR Shoemaker** (~$224M, 1996 dollars)
- **Hayabusa2** (~$150M, sample return)
- **DART** (~$330M, kinetic impactor)
- **OSIRIS-REx** (~$800M, sample return with extensive science suite)

The $300M figure represents a focused mining mission with autonomous extraction capability but without the science instrumentation overhead of OSIRIS-REx class missions.

**References:**
- Sonter, M. J. (1997). "The Technical and Economic Feasibility of Mining the Near-Earth Asteroids." *Acta Astronautica*, 41(4-10), 637-647. doi:[10.1016/S0094-5765(98)00087-3](https://doi.org/10.1016/S0094-5765(98)00087-3)
- Elvis, M. (2014). "How many ore-bearing asteroids?" *Planetary and Space Science*, 91, 20-26. doi:[10.1016/j.pss.2013.11.008](https://doi.org/10.1016/j.pss.2013.11.008)

### 6.3 Extraction Parameters

| Parameter | Value | Notes |
|---|---|---|
| System mass | 1,000 kg | Deployed mining infrastructure |
| Extraction overhead | $5,000/kg | Amortised mining + refining equipment |
| Mission capacity | 1,000 kg | Per-mission return payload |
| Precious extraction yield | 30% | Refining efficiency |

### 6.4 Break-Even Analysis

**Total fixed cost per mission:**
```
total_fixed = mission_min_cost + system_mass * transport_per_kg
```

**Margin per kg:**
```
margin = specimen_value - transport_per_kg - extraction_overhead
```

**Break-even payload:**
```
break_even_kg = total_fixed / margin
```

An asteroid is **viable** if its total extractable precious metal mass exceeds the break-even payload. Each viable asteroid supports `floor(extractable / mission_capacity)` profitable missions.

---

## 7. Known Limitations

1. **Circular-orbit delta-v approximation** — eccentricity is excluded from the transfer model. This underestimates delta-v for highly eccentric targets. The Tisserand parameter partially compensates as a stability indicator.

2. **Static spot prices** — metal prices are frozen at a single date. Market volatility, particularly for rhodium and iridium, can significantly shift break-even calculations.

3. **Uniform density assumption (physical stage)** — surface gravity uses a single 2000 kg/m^3 density. Real asteroids range from ~1000 (rubble-pile C-types) to ~7000 (solid iron M-types).

4. **M-type ambiguity in albedo classification** — M-types and S-types overlap in albedo space (both ~0.10-0.30). Without spectral data, albedo-only classification assigns these as S-type, potentially underestimating the M-type population.

5. **Horizons API rate limits** — the per-object query model limits Horizons integration to NEAs. Main-belt asteroids use less precise SBDB elements.

6. **Extraction yield assumptions** — the 30% precious metal refining yield and $5,000/kg overhead are engineering estimates, not empirically validated for space operations.

---

## References (Consolidated)

Cannon, K. M., Gialich, S., & Acain, A. (2023). "Accessible Precious Metals on Asteroids." *Planetary and Space Science*, 225, 105608. doi:10.1016/j.pss.2022.105608

Carry, B. (2012). "Density of asteroids." *Planetary and Space Science*, 73(1), 98-118. doi:10.1016/j.pss.2012.03.009

DeMeo, F. E., & Carry, B. (2013). "The Taxonomic Distribution of Asteroids from Multi-filter All-sky Photometric Surveys." *Icarus*, 226(1), 723-741. doi:10.1016/j.icarus.2013.06.027

Dunn, T. L., et al. (2010). "Principal component analysis of spectral data of ordinary chondrites." *Icarus*, 208(2), 789-797. doi:10.1016/j.icarus.2010.02.016

Elvis, M. (2014). "How many ore-bearing asteroids?" *Planetary and Space Science*, 91, 20-26. doi:10.1016/j.pss.2013.11.008

Garenne, A., et al. (2014). "The abundance and stability of 'water' in type 1 and 2 carbonaceous chondrites (CI, CM and CR)." *Geochimica et Cosmochimica Acta*, 137, 93-112. doi:10.1016/j.gca.2014.03.034

Giorgini, J. D., et al. (1996). "JPL's On-Line Solar System Data Service." *Bulletin of the American Astronomical Society*, 28, 1158.

Hasselmann, P. H., Carvano, J. M., & Lazzaro, D. (2012). "SDSS-based Asteroid Taxonomy V1.1." *NASA Planetary Data System*, EAR-A-I0035-5-SDSSTAX-V1.1.

Ivezic, Z., et al. (2001). "Solar System Objects Observed in the Sloan Digital Sky Survey Commissioning Data." *Astronomical Journal*, 122(5), 2749-2784. doi:10.1086/323452

Lodders, K., Bergemann, M., & Palme, H. (2025). "Solar System Abundances of the Elements." arXiv:2502.10575.

Mainzer, A. K., et al. (2011). "NEOWISE Observations of Near-Earth Objects: Preliminary Results." *Astrophysical Journal*, 743(2), 156. doi:10.1088/0004-637X/743/2/156

Mainzer, A. K., et al. (2019). "NEOWISE Diameters and Albedos V2.0." *NASA Planetary Data System*, urn:nasa:pds:neowise_diameters_albedos::2.0. doi:10.26033/18S3-2Z54

Popescu, M., et al. (2018). "MOVIS-C: A catalog of Visible-NIR colors of asteroids observed with VISTA-VHS." *Astronomy & Astrophysics*, 617, A12. doi:10.1051/0004-6361/201833023

Pravec, P., & Harris, A. W. (2000). "Fast and Slow Rotation of Asteroids." *Icarus*, 148(1), 12-20. doi:10.1006/icar.2000.6482

Sanchez, J. P., & McInnes, C. R. (2011). "Asteroid Resource Map for Near-Earth Space." *Journal of Spacecraft and Rockets*, 48(1), 153-165. doi:10.2514/1.49851

Shepard, M. K., et al. (2010). "A radar survey of M- and X-class asteroids." *Icarus*, 215(2), 547-551. doi:10.1016/j.icarus.2010.02.002

Shepard, M. K., et al. (2015). "A radar survey of M- and X-class asteroids. III." *Icarus*, 245, 38-55. doi:10.1016/j.icarus.2014.09.016

Shoemaker, E. M., & Helin, E. (1979). "Earth-Approaching Asteroids as Targets for Exploration." *NASA CP-2053*, 245-256.

Sonter, M. J. (1997). "The Technical and Economic Feasibility of Mining the Near-Earth Asteroids." *Acta Astronautica*, 41(4-10), 637-647. doi:10.1016/S0094-5765(98)00087-3

Warner, B. D., Harris, A. W., & Pravec, P. (2009). "The asteroid lightcurve database." *Icarus*, 202(1), 134-146. doi:10.1016/j.icarus.2009.02.003
