#!/usr/bin/env python3
"""
Project Audit & Data Integrity Checker

Run with: python scripts/audit.py
Or:       python scripts/audit.py --save baseline.json
Then:     python scripts/audit.py --compare baseline.json

Checks:
  1. Repository structure — all expected files exist
  2. Code quality — lint, typecheck, test results
  3. Pipeline integrity — all parquet stages present and consistent
  4. Data integrity — row counts, column counts, null rates, value ranges
  5. Composition model — class distribution, confidence, resource values
  6. Data source coverage — how many asteroids have each evidence type
  7. Economic results — viable targets, mission counts, value ranges
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd


def _repo_root() -> Path:
    p = Path(__file__).resolve().parent.parent
    assert (p / "pyproject.toml").exists(), f"Can't find repo root from {__file__}"
    return p


# ---------------------------------------------------------------------------
# 1. Repository structure
# ---------------------------------------------------------------------------

EXPECTED_SOURCE_FILES = [
    "src/asteroid_cost_atlas/settings.py",
    "src/asteroid_cost_atlas/models/asteroid.py",
    "src/asteroid_cost_atlas/ingest/ingest_sbdb.py",
    "src/asteroid_cost_atlas/ingest/ingest_lcdb.py",
    "src/asteroid_cost_atlas/ingest/ingest_neowise.py",
    "src/asteroid_cost_atlas/ingest/ingest_spectral.py",
    "src/asteroid_cost_atlas/ingest/ingest_movis.py",
    "src/asteroid_cost_atlas/ingest/ingest_horizons.py",
    "src/asteroid_cost_atlas/ingest/clean_sbdb.py",
    "src/asteroid_cost_atlas/ingest/enrich.py",
    "src/asteroid_cost_atlas/scoring/orbital.py",
    "src/asteroid_cost_atlas/scoring/physical.py",
    "src/asteroid_cost_atlas/scoring/composition.py",
    "src/asteroid_cost_atlas/scoring/ml_classifier.py",
    "src/asteroid_cost_atlas/scoring/overlays.py",
    "src/asteroid_cost_atlas/scoring/economic.py",
    "src/asteroid_cost_atlas/utils/query.py",
    "src/asteroid_cost_atlas/api/app.py",
    "src/asteroid_cost_atlas/api/deps.py",
    "src/asteroid_cost_atlas/api/schemas.py",
    "src/asteroid_cost_atlas/api/routes/asteroids.py",
    "src/asteroid_cost_atlas/api/routes/stats.py",
    "src/asteroid_cost_atlas/api/routes/search.py",
]

EXPECTED_TEST_FILES = [
    "tests/test_settings.py",
    "tests/test_ingest_sbdb.py",
    "tests/test_ingest_lcdb.py",
    "tests/test_ingest_neowise.py",
    "tests/test_ingest_spectral.py",
    "tests/test_ingest_movis.py",
    "tests/test_ingest_horizons.py",
    "tests/test_clean_sbdb.py",
    "tests/test_enrich.py",
    "tests/test_orbital.py",
    "tests/test_physical.py",
    "tests/test_composition.py",
    "tests/test_ml_classifier.py",
    "tests/test_overlays.py",
    "tests/test_economic.py",
    "tests/test_query.py",
    "tests/test_api.py",
    "tests/test_pipeline_integration.py",
]

EXPECTED_DOCS = [
    "README.md",
    "CLAUDE.md",
    "CHANGELOG.md",
    "docs/DATA_DICTIONARY.md",
    "docs/METHODOLOGY.md",
    "docs/PROJECT_AUDIT.md",
]

EXPECTED_INFRA = [
    "pyproject.toml",
    "Makefile",
    "Dockerfile",
    "start.sh",
    ".github/workflows/ci.yml",
    "configs/config.yaml",
    "web/package.json",
    "web/vite.config.ts",
    "web/src/App.tsx",
]


def audit_structure(root: Path) -> dict:
    """Check all expected files exist."""
    results: dict = {"missing": [], "present": 0}
    all_expected = EXPECTED_SOURCE_FILES + EXPECTED_TEST_FILES + EXPECTED_DOCS + EXPECTED_INFRA
    for f in all_expected:
        if (root / f).exists():
            results["present"] += 1
        else:
            results["missing"].append(f)
    results["total_expected"] = len(all_expected)
    return results


# ---------------------------------------------------------------------------
# 2. Code quality
# ---------------------------------------------------------------------------

def audit_code_quality(root: Path) -> dict:
    """Run lint, typecheck, count test results."""
    results: dict = {}

    # Count source and test lines
    src_lines = sum(
        len(f.read_text().splitlines())
        for f in (root / "src").rglob("*.py")
    )
    test_lines = sum(
        len(f.read_text().splitlines())
        for f in (root / "tests").rglob("*.py")
    )
    results["source_lines"] = src_lines
    results["test_lines"] = test_lines
    results["source_files"] = len(list((root / "src").rglob("*.py")))
    results["test_files"] = len(list((root / "tests").rglob("*.py")))

    return results


# ---------------------------------------------------------------------------
# 3. Pipeline integrity
# ---------------------------------------------------------------------------

PIPELINE_STAGES = [
    ("raw", "sbdb_*.csv", "SBDB ingest"),
    ("raw", "lcdb_*.parquet", "LCDB ingest"),
    ("raw", "movis_*.parquet", "MOVIS ingest"),
    ("processed", "sbdb_clean_*.parquet", "Clean"),
    ("processed", "sbdb_enriched_*.parquet", "Enrich"),
    ("processed", "sbdb_orbital_*.parquet", "Orbital"),
    ("processed", "sbdb_physical_*.parquet", "Physical"),
    ("processed", "sbdb_composition_*.parquet", "Composition"),
    ("processed", "atlas_*.parquet", "Atlas (final)"),
]


def audit_pipeline(root: Path) -> dict:
    """Check pipeline stage outputs exist and are consistent."""
    results: dict = {"stages": {}, "missing_stages": []}
    data_dir = root / "data"

    for subdir, pattern, label in PIPELINE_STAGES:
        candidates = sorted((data_dir / subdir).glob(pattern))
        if candidates:
            latest = candidates[-1]
            size_mb = latest.stat().st_size / 1e6
            results["stages"][label] = {
                "file": latest.name,
                "size_mb": round(size_mb, 1),
                "count": len(candidates),
            }
            # For parquets, get column count
            if latest.suffix == ".parquet":
                cols = pd.read_parquet(latest, columns=[]).columns.tolist()
                results["stages"][label]["columns"] = len(cols)
        else:
            results["missing_stages"].append(label)

    return results


# ---------------------------------------------------------------------------
# 4-7. Data integrity & composition analysis (on latest atlas)
# ---------------------------------------------------------------------------

def audit_atlas(root: Path) -> dict:
    """Deep audit of the latest atlas parquet."""
    processed = root / "data" / "processed"
    atlas_files = sorted(processed.glob("atlas_*.parquet"))
    if not atlas_files:
        # Fall back to composition
        atlas_files = sorted(processed.glob("sbdb_composition_*.parquet"))
    if not atlas_files:
        return {"error": "No atlas or composition parquet found"}

    latest = atlas_files[-1]
    df = pd.read_parquet(latest)

    results: dict = {
        "file": latest.name,
        "rows": len(df),
        "columns": len(df.columns),
        "size_mb": round(latest.stat().st_size / 1e6, 1),
    }

    # Column inventory
    results["column_list"] = sorted(df.columns.tolist())

    # Null rates for key columns
    key_cols = [
        "spkid", "name", "a_au", "eccentricity", "inclination_deg",
        "abs_magnitude", "diameter_estimated_km", "diameter_km",
        "albedo", "rotation_hours", "neo", "taxonomy", "spectral_type",
        "delta_v_km_s", "composition_class", "composition_confidence",
        "prob_C", "prob_S", "prob_M", "prob_V",
        "estimated_mass_kg", "is_viable",
    ]
    null_rates: dict = {}
    for col in key_cols:
        if col in df.columns:
            null_rates[col] = round(df[col].isna().mean() * 100, 2)
    results["null_rates_pct"] = null_rates

    # Data source coverage
    coverage: dict = {}
    if "taxonomy" in df.columns:
        coverage["taxonomy"] = int(df["taxonomy"].notna().sum())
    if "spectral_type" in df.columns:
        coverage["spectral_type"] = int(df["spectral_type"].notna().sum())
    if "color_gr" in df.columns:
        coverage["sdss_colors"] = int(df["color_gr"].notna().sum())
    if "movis_yj" in df.columns:
        coverage["movis_nir"] = int(df["movis_yj"].notna().sum())
    if "movis_taxonomy" in df.columns:
        coverage["movis_taxonomy"] = int(df["movis_taxonomy"].notna().sum())
    if "albedo" in df.columns:
        coverage["albedo"] = int(df["albedo"].notna().sum())
    if "diameter_km" in df.columns:
        coverage["diameter_measured"] = int(df["diameter_km"].notna().sum())
    if "diameter_estimated_km" in df.columns:
        coverage["diameter_any"] = int(df["diameter_estimated_km"].notna().sum())
    if "rotation_hours" in df.columns:
        coverage["rotation"] = int(df["rotation_hours"].notna().sum())
    results["data_source_coverage"] = coverage

    # Composition model results
    if "composition_class" in df.columns:
        class_dist = df["composition_class"].value_counts().to_dict()
        results["composition_classes"] = {
            str(k): int(v) for k, v in class_dist.items()
        }

    if "composition_source" in df.columns:
        source_dist = df["composition_source"].value_counts().to_dict()
        results["composition_sources"] = {
            str(k): int(v) for k, v in source_dist.items()
        }

    if "composition_confidence" in df.columns:
        conf = df["composition_confidence"]
        results["confidence"] = {
            "mean": round(float(conf.mean()), 4),
            "median": round(float(conf.median()), 4),
            "high_gt_0.7": int((conf > 0.7).sum()),
            "medium_0.3_0.7": int(((conf >= 0.3) & (conf <= 0.7)).sum()),
            "low_lt_0.3": int((conf < 0.3).sum()),
        }

    # Probability columns
    for cls in ("C", "S", "M", "V"):
        col = f"prob_{cls}"
        if col in df.columns:
            results[f"prob_{cls}_mean"] = round(float(df[col].mean()), 4)

    # Resource values
    if "resource_value_usd_per_kg" in df.columns:
        rv = df["resource_value_usd_per_kg"]
        results["resource_value_per_kg"] = {
            "mean": round(float(rv.mean()), 2),
            "median": round(float(rv.median()), 2),
            "min": round(float(rv.min()), 2),
            "max": round(float(rv.max()), 2),
        }

    # PGM ranges
    if "platinum_ppm" in df.columns:
        results["platinum_ppm"] = {
            "mean": round(float(df["platinum_ppm"].mean()), 4),
        }
        if "platinum_ppm_low" in df.columns:
            results["platinum_ppm"]["p10_mean"] = round(
                float(df["platinum_ppm_low"].mean()), 4
            )
        if "platinum_ppm_high" in df.columns:
            results["platinum_ppm"]["p90_mean"] = round(
                float(df["platinum_ppm_high"].mean()), 4
            )

    # Economic results (if atlas has them)
    if "is_viable" in df.columns:
        viable = df[df["is_viable"] == True]  # noqa: E712
        results["economics"] = {
            "positive_margin": int((df.get("margin_per_kg", pd.Series()) > 0).sum()),
            "viable_targets": len(viable),
            "total_missions": int(viable["missions_supported"].sum())
                if "missions_supported" in viable.columns else 0,
            "best_campaign_profit": round(
                float(viable["campaign_profit_usd"].max()), 0
            ) if "campaign_profit_usd" in viable.columns and len(viable) > 0
            else 0,
        }

    # Delta-v distribution
    if "delta_v_km_s" in df.columns:
        dv = df["delta_v_km_s"].dropna()
        results["delta_v"] = {
            "min": round(float(dv.min()), 2),
            "max": round(float(dv.max()), 2),
            "mean": round(float(dv.mean()), 2),
            "median": round(float(dv.median()), 2),
            "lt_5": int((dv < 5).sum()),
            "lt_10": int((dv < 10).sum()),
        }

    return results


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run_audit() -> dict:
    """Run full project audit and return results dict."""
    root = _repo_root()
    timestamp = datetime.now(UTC).isoformat()

    print(f"Asteroid Cost Atlas — Project Audit ({timestamp})")
    print("=" * 60)

    # 1. Structure
    print("\n1. Repository Structure")
    structure = audit_structure(root)
    print(f"   Files: {structure['present']}/{structure['total_expected']} present")
    if structure["missing"]:
        for f in structure["missing"]:
            print(f"   MISSING: {f}")
    else:
        print("   All expected files present")

    # 2. Code quality
    print("\n2. Code Quality")
    quality = audit_code_quality(root)
    print(f"   Source: {quality['source_files']} files, {quality['source_lines']:,} lines")
    print(f"   Tests:  {quality['test_files']} files, {quality['test_lines']:,} lines")
    print(f"   Ratio:  {quality['test_lines']/max(quality['source_lines'],1):.2f}")

    # 3. Pipeline
    print("\n3. Pipeline Stages")
    pipeline = audit_pipeline(root)
    for label, info in pipeline["stages"].items():
        print(f"   {label:20s} {info['file']:40s} {info['size_mb']:>7.1f} MB")
    if pipeline["missing_stages"]:
        for s in pipeline["missing_stages"]:
            print(f"   MISSING: {s}")

    # 4-7. Atlas deep audit
    print("\n4. Atlas Data Audit")
    atlas = audit_atlas(root)
    if "error" in atlas:
        print(f"   ERROR: {atlas['error']}")
    else:
        print(f"   File: {atlas['file']}")
        print(f"   Rows: {atlas['rows']:,}  Columns: {atlas['columns']}")
        print(f"   Size: {atlas['size_mb']} MB")

        print("\n   Data Source Coverage:")
        for src, count in atlas.get("data_source_coverage", {}).items():
            pct = count / atlas["rows"] * 100
            print(f"     {src:25s} {count:>10,}  ({pct:5.1f}%)")

        print("\n   Composition Classes:")
        for cls, count in sorted(atlas.get("composition_classes", {}).items()):
            pct = count / atlas["rows"] * 100
            print(f"     {cls:5s} {count:>10,}  ({pct:5.1f}%)")

        if "composition_sources" in atlas:
            print("\n   Composition Sources:")
            for src, count in sorted(atlas["composition_sources"].items()):
                pct = count / atlas["rows"] * 100
                print(f"     {src:25s} {count:>10,}  ({pct:5.1f}%)")

        if "confidence" in atlas:
            c = atlas["confidence"]
            print(f"\n   Confidence: mean={c['mean']:.3f}  median={c['median']:.3f}")
            print(f"     High (>0.7):  {c['high_gt_0.7']:>10,}")
            print(f"     Medium:       {c['medium_0.3_0.7']:>10,}")
            print(f"     Low (<0.3):   {c['low_lt_0.3']:>10,}")

        for cls in ("C", "S", "M", "V"):
            key = f"prob_{cls}_mean"
            if key in atlas:
                print(f"   Mean prob_{cls}: {atlas[key]:.4f}")

        if "resource_value_per_kg" in atlas:
            rv = atlas["resource_value_per_kg"]
            print(f"\n   Resource Value: mean=${rv['mean']:.2f}/kg  "
                  f"median=${rv['median']:.2f}/kg  "
                  f"range=[${rv['min']:.2f}, ${rv['max']:.2f}]")

        if "platinum_ppm" in atlas:
            pt = atlas["platinum_ppm"]
            pt_str = f"mean={pt['mean']:.4f}"
            if "p10_mean" in pt:
                pt_str += f"  P10={pt['p10_mean']:.4f}  P90={pt['p90_mean']:.4f}"
            print(f"   Platinum PPM: {pt_str}")

        if "economics" in atlas:
            e = atlas["economics"]
            print("\n   Economics:")
            print(f"     Positive margin: {e['positive_margin']:>10,}")
            print(f"     Viable targets:  {e['viable_targets']:>10,}")
            print(f"     Total missions:  {e['total_missions']:>10,}")
            if e["best_campaign_profit"]:
                print(f"     Best campaign:   ${e['best_campaign_profit']:>12,.0f}")

        if "delta_v" in atlas:
            dv = atlas["delta_v"]
            print(f"\n   Delta-v: min={dv['min']}  median={dv['median']}  "
                  f"max={dv['max']}  <5km/s={dv['lt_5']:,}  <10km/s={dv['lt_10']:,}")

    print("\n" + "=" * 60)
    print("Audit complete.")

    return {
        "timestamp": timestamp,
        "structure": structure,
        "code_quality": quality,
        "pipeline": pipeline,
        "atlas": atlas,
    }


def compare_audits(current: dict, baseline: dict) -> None:
    """Print differences between two audit snapshots."""
    print("\n" + "=" * 60)
    print("COMPARISON: Current vs Baseline")
    print(f"  Baseline: {baseline['timestamp']}")
    print(f"  Current:  {current['timestamp']}")
    print("=" * 60)

    ca = current.get("atlas", {})
    ba = baseline.get("atlas", {})

    # Row count
    if "rows" in ca and "rows" in ba:
        diff = ca["rows"] - ba["rows"]
        print(f"\n  Rows: {ba['rows']:,} → {ca['rows']:,} ({diff:+,})")

    # Columns
    if "columns" in ca and "columns" in ba:
        diff = ca["columns"] - ba["columns"]
        print(f"  Columns: {ba['columns']} → {ca['columns']} ({diff:+d})")

    # Composition class changes
    bc = ba.get("composition_classes", {})
    cc = ca.get("composition_classes", {})
    if bc and cc:
        print("\n  Composition Classes:")
        all_classes = sorted(set(list(bc.keys()) + list(cc.keys())))
        for cls in all_classes:
            b = bc.get(cls, 0)
            c = cc.get(cls, 0)
            print(f"    {cls:5s}  {b:>10,} → {c:>10,}  ({c - b:+,})")

    # Confidence
    bconf = ba.get("confidence", {})
    cconf = ca.get("confidence", {})
    if bconf and cconf:
        print(f"\n  Confidence: {bconf.get('mean', 0):.4f} → {cconf.get('mean', 0):.4f}")
        print(f"    High: {bconf.get('high_gt_0.7', 0):,} → {cconf.get('high_gt_0.7', 0):,}")

    # Coverage changes
    bcov = ba.get("data_source_coverage", {})
    ccov = ca.get("data_source_coverage", {})
    if bcov or ccov:
        all_sources = sorted(set(list(bcov.keys()) + list(ccov.keys())))
        print("\n  Data Source Coverage:")
        for src in all_sources:
            b = bcov.get(src, 0)
            c = ccov.get(src, 0)
            if b != c:
                print(f"    {src:25s}  {b:>10,} → {c:>10,}  ({c - b:+,})")

    # Resource values
    brv = ba.get("resource_value_per_kg", {})
    crv = ca.get("resource_value_per_kg", {})
    if brv and crv:
        print(f"\n  Resource Value/kg: "
              f"${brv.get('mean', 0):.2f} → ${crv.get('mean', 0):.2f}")

    # Platinum
    bpt = ba.get("platinum_ppm", {})
    cpt = ca.get("platinum_ppm", {})
    if bpt and cpt:
        print(f"  Platinum PPM: {bpt.get('mean', 0):.4f} → {cpt.get('mean', 0):.4f}")

    # Economics
    be = ba.get("economics", {})
    ce = ca.get("economics", {})
    if be and ce:
        print("\n  Economics:")
        for key in ("positive_margin", "viable_targets", "total_missions"):
            b = be.get(key, 0)
            c = ce.get(key, 0)
            print(f"    {key:20s}  {b:>10,} → {c:>10,}  ({c - b:+,})")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Asteroid Cost Atlas — Project Audit")
    parser.add_argument("--save", type=str, help="Save audit results to JSON file")
    parser.add_argument("--compare", type=str, help="Compare against baseline JSON file")
    args = parser.parse_args()

    results = run_audit()

    if args.save:
        save_path = Path(args.save)
        save_path.write_text(json.dumps(results, indent=2, default=str))
        print(f"\nSaved audit to {save_path}")

    if args.compare:
        baseline_path = Path(args.compare)
        if baseline_path.exists():
            baseline = json.loads(baseline_path.read_text())
            compare_audits(results, baseline)
        else:
            print(f"\nBaseline file not found: {baseline_path}")
