"""
NEOWISE diameter and albedo ingestion.

Downloads the NEOWISE asteroid diameters and albedos from the Planetary
Data System (PDS), parses the pipe-delimited table, and saves a clean
Parquet to ``data/raw/``.

The primary value is ~164 K measured diameters and geometric albedos from
thermal infrared observations — a major coverage uplift over the sparse
SBDB direct measurements (~9 % diameter, ~9 % albedo).

Join key: asteroid number + 20_000_000 = SBDB spkid (for numbered bodies).

References
----------
Mainzer et al. (2019), "NEOWISE Diameters and Albedos V2.0"
https://sbn.psi.edu/pds/resource/neowisediam.html
"""

from __future__ import annotations

import io
import logging
import time
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import requests

# PDS download URL for the NEOWISE diameters/albedos table
NEOWISE_URL = (
    "https://sbn.psi.edu/pds/resource/neowisediam/neowise_diameters_albedos_V2_0.csv"
)

logger = logging.getLogger(__name__)


def download_neowise(url: str = NEOWISE_URL, timeout: int = 180) -> bytes:
    """Download the NEOWISE CSV table and return raw bytes."""
    logger.info("Downloading NEOWISE diameters/albedos from %s", url)
    resp = requests.get(url, timeout=timeout)
    resp.raise_for_status()
    logger.info("Downloaded %.1f MB", len(resp.content) / 1e6)
    return resp.content


def parse_neowise(raw_bytes: bytes) -> pd.DataFrame:
    """
    Parse the NEOWISE CSV into a clean DataFrame.

    Returns columns: number, neowise_diameter_km, neowise_albedo.
    Rows with non-positive diameter or albedo are dropped.
    """
    df = pd.read_csv(
        io.BytesIO(raw_bytes),
        comment="#",
        skipinitialspace=True,
        low_memory=False,
    )

    # Normalise column names to lowercase, strip whitespace
    df.columns = df.columns.str.strip().str.lower()

    # Identify diameter and albedo columns (handle naming variants)
    diam_col = _find_column(df, ["diameter", "diam", "d_km", "diameter_km"])
    albedo_col = _find_column(df, ["albedo", "pv", "p_v", "geometric_albedo"])
    number_col = _find_column(df, ["number", "num", "ast_number", "id"])

    if diam_col is None or albedo_col is None or number_col is None:
        raise ValueError(
            f"Cannot identify required columns in NEOWISE data. "
            f"Found columns: {list(df.columns)}"
        )

    result = pd.DataFrame({
        "number": pd.to_numeric(df[number_col], errors="coerce"),
        "neowise_diameter_km": pd.to_numeric(df[diam_col], errors="coerce"),
        "neowise_albedo": pd.to_numeric(df[albedo_col], errors="coerce"),
    })

    # Drop rows missing the join key or both measurements
    result = result.dropna(subset=["number"])
    result["number"] = result["number"].astype(int)

    # Keep only positive values
    valid_diam = result["neowise_diameter_km"].gt(0) | result["neowise_diameter_km"].isna()
    valid_alb = result["neowise_albedo"].gt(0) | result["neowise_albedo"].isna()
    result = result[valid_diam & valid_alb].reset_index(drop=True)

    # Drop rows that have neither diameter nor albedo
    has_data = result["neowise_diameter_km"].notna() | result["neowise_albedo"].notna()
    result = result[has_data].reset_index(drop=True)

    # Deduplicate: keep best measurement per asteroid (largest diameter if dupes)
    result = (
        result.sort_values("neowise_diameter_km", ascending=False, na_position="last")
        .drop_duplicates(subset=["number"], keep="first")
        .reset_index(drop=True)
    )

    return result


def _find_column(df: pd.DataFrame, candidates: list[str]) -> str | None:
    """Find the first matching column name from candidates."""
    cols_lower = {c.lower(): c for c in df.columns}
    for name in candidates:
        if name.lower() in cols_lower:
            return cols_lower[name.lower()]
    return None


def add_spkid(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add ``spkid`` join key: numbered asteroid number + 20_000_000.

    Unnumbered bodies are dropped.
    """
    result = df.copy()
    has_number = result["number"].notna()
    dropped = int((~has_number).sum())
    if dropped:
        logger.info("Dropped %d unnumbered objects (no join key)", dropped)
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

    raw_bytes = download_neowise()
    df = parse_neowise(raw_bytes)
    logger.info("Parsed %d NEOWISE records", len(df))

    df = add_spkid(df)

    today = datetime.now(UTC).strftime("%Y%m%d")
    output_path = raw_dir / f"neowise_{today}.parquet"
    df.to_parquet(output_path, index=False, engine="pyarrow")

    n_diam = int(df["neowise_diameter_km"].notna().sum())
    n_alb = int(df["neowise_albedo"].notna().sum())
    logger.info(
        "Saved %s — %d records (%d diameters, %d albedos), %.1fs",
        output_path.name, len(df), n_diam, n_alb,
        time.perf_counter() - started,
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
