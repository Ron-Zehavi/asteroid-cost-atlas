"""
MOVIS-C near-infrared taxonomy ingestion.

Downloads the MOVIS-C catalog (Popescu et al. 2018, A&A 617, A12)
from VizieR, providing near-infrared Y-J, J-H, H-Ks color indices
for ~18,000 asteroids with probabilistic taxonomy.

NIR colors break the visible-light C/S degeneracy and are particularly
valuable for M-type identification. Combined with existing SDSS visible
colors, this significantly improves composition inference.

Join key: asteroid number + 20_000_000 = SBDB spkid.

References
----------
Popescu et al. (2018), "Taxonomic classification of asteroids based
on MOVIS near-infrared colors", A&A 617, A12.
"""

from __future__ import annotations

import io
import logging
import time
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import requests

# VizieR TAP query for MOVIS-C Table A1 (main results)
MOVIS_VIZIER_URL = "https://vizier.cds.unistra.fr/viz-bin/asu-tsv"
MOVIS_CATALOG = "J/A+A/617/A12/movistax"

logger = logging.getLogger(__name__)


def download_movis(
    url: str = MOVIS_VIZIER_URL,
    catalog: str = MOVIS_CATALOG,
    timeout: int = 300,
) -> pd.DataFrame:
    """Download MOVIS-C catalog from VizieR as a DataFrame."""
    logger.info("Downloading MOVIS-C from VizieR (%s)...", catalog)
    params = {
        "-source": catalog,
        "-out.max": "unlimited",
        "-out": "Number,Y-J,J-Ks,H-Ks,ClassFin,ClassProb,KNNProb",
    }
    resp = requests.get(url, params=params, timeout=timeout)
    resp.raise_for_status()
    logger.info("Downloaded %.1f KB", len(resp.content) / 1e3)

    # Parse TSV, skip VizieR header/metadata lines
    lines = resp.text.splitlines()
    data_lines = [
        ln for ln in lines
        if ln and not ln.startswith("#") and not ln.startswith("-")
    ]
    if len(data_lines) < 2:
        raise ValueError("No data rows in MOVIS VizieR response")

    df = pd.read_csv(
        io.StringIO("\n".join(data_lines)),
        sep="\t",
        skipinitialspace=True,
    )
    df.columns = df.columns.str.strip()
    return df


def parse_movis(df: pd.DataFrame) -> pd.DataFrame:
    """Clean and standardize MOVIS-C data."""
    result = pd.DataFrame()

    # Number column → spkid
    num_col = None
    for c in df.columns:
        if "num" in c.lower() or c.strip() == "Num":
            num_col = c
            break
    if num_col is None:
        raise ValueError(f"No number column found. Columns: {list(df.columns)}")

    result["number"] = pd.to_numeric(df[num_col], errors="coerce")
    result = result.dropna(subset=["number"])
    result["number"] = result["number"].astype(int)

    # NIR color indices
    for vizier_col, our_col in [
        ("Y-J", "movis_yj"),
        ("J-Ks", "movis_jks"),
        ("H-Ks", "movis_hks"),
    ]:
        matched = [c for c in df.columns if c.strip() == vizier_col]
        if matched:
            result[our_col] = pd.to_numeric(
                df[matched[0]], errors="coerce",
            ).iloc[result.index].values

    # MOVIS final taxonomy (ClassFin)
    tax_cols = [c for c in df.columns if c.strip() in ("ClassFin", "ClassProb")]
    if tax_cols:
        result["movis_taxonomy"] = df[tax_cols[0]].iloc[result.index].values
        result["movis_taxonomy"] = result["movis_taxonomy"].astype(str).str.strip()
        invalid = result["movis_taxonomy"].isin(["", "nan", "None", "--"])
        result.loc[invalid, "movis_taxonomy"] = pd.NA

    # Drop rows with no color data
    color_cols = [c for c in result.columns if c.startswith("movis_") and c != "movis_taxonomy"]
    if color_cols:
        has_data = result[color_cols].notna().any(axis=1)
        result = result[has_data].reset_index(drop=True)

    # Deduplicate
    result = result.drop_duplicates(subset=["number"], keep="first").reset_index(drop=True)

    return result


def add_spkid(df: pd.DataFrame) -> pd.DataFrame:
    """Add spkid join key: number + 20_000_000."""
    result = df.copy()
    has_number = result["number"].notna()
    result = result[has_number].reset_index(drop=True)
    result["spkid"] = (result["number"].astype(int) + 20_000_000).astype(int)
    return result


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    started = time.perf_counter()

    _module = Path(__file__).resolve()
    repo_root = next(p for p in [_module, *_module.parents] if (p / "pyproject.toml").exists())
    raw_dir = repo_root / "data" / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    raw_df = download_movis()
    df = parse_movis(raw_df)
    logger.info("Parsed %d MOVIS-C records", len(df))

    df = add_spkid(df)

    today = datetime.now(UTC).strftime("%Y%m%d")
    output_path = raw_dir / f"movis_{today}.parquet"
    df.to_parquet(output_path, index=False, engine="pyarrow")

    n_tax = int(df["movis_taxonomy"].notna().sum()) if "movis_taxonomy" in df.columns else 0
    logger.info(
        "Saved %s — %d records (%d with taxonomy), %.1fs",
        output_path.name, len(df), n_tax,
        time.perf_counter() - started,
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
