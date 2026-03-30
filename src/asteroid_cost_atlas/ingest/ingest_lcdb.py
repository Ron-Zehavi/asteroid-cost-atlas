"""
LCDB (Asteroid Lightcurve Database) ingestion.

Downloads the latest LCDB public summary from minplanobs.org,
parses the fixed-width ``lc_summary_pub.txt``, filters by the
quality code (U >= 2-), and saves a clean Parquet to data/raw/.

The primary value is the rotation period — SBDB only has ~2 %
coverage, while LCDB adds ~30 K+ reliable periods.

Join key: asteroid number + 2_000_000 = SBDB spkid (for numbered bodies).

References
----------
Warner, Harris & Pravec, "The asteroid lightcurve database"
https://minplanobs.org/mpinfo/php/lcdb.php
"""

from __future__ import annotations

import io
import logging
import time
import zipfile
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import requests

LCDB_ZIP_URL = "https://minplanobs.org/MPInfo/datazips/LCLIST_PUB_CURRENT.zip"
SUMMARY_FILENAME = "lc_summary_pub.txt"

# Quality codes considered reliable for statistical use (U >= 2-)
_VALID_U_CODES = frozenset({"2-", "2", "2+", "3-", "3"})

# Fixed-width column specifications (0-indexed start, end positions)
_COLSPECS: list[tuple[int, int]] = [
    (0, 7),     # Number
    (10, 40),   # Name
    (41, 61),   # Desig
    (62, 70),   # Family
    (73, 83),   # Class
    (88, 96),   # Diam
    (99, 105),  # H
    (136, 142), # Albedo
    (143, 144), # PFlag
    (145, 158), # Period
    (187, 189), # U
    (196, 199), # Binary
]

_COLNAMES = [
    "number", "name", "designation", "family",
    "taxonomy", "lcdb_diameter_km", "lcdb_h",
    "lcdb_albedo", "period_flag", "lcdb_rotation_hours",
    "u_quality", "binary_flag",
]

logger = logging.getLogger(__name__)


def download_lcdb_zip(url: str = LCDB_ZIP_URL, timeout: int = 120) -> bytes:
    """Download the LCDB ZIP archive and return raw bytes."""
    logger.info("Downloading LCDB from %s", url)
    resp = requests.get(url, timeout=timeout)
    resp.raise_for_status()
    logger.info("Downloaded %.1f MB", len(resp.content) / 1e6)
    return resp.content


def parse_summary(zip_bytes: bytes) -> pd.DataFrame:
    """
    Extract and parse ``lc_summary_pub.txt`` from the LCDB ZIP.

    Returns a DataFrame with one row per asteroid, columns renamed
    and numeric fields coerced.
    """
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        with zf.open(SUMMARY_FILENAME) as f:
            raw = f.read().decode("ascii", errors="replace")

    df = pd.read_fwf(
        io.StringIO(raw),
        colspecs=_COLSPECS,
        names=_COLNAMES,
        skiprows=4,
    )

    # Coerce numeric columns
    for col in ("number", "lcdb_diameter_km", "lcdb_h", "lcdb_albedo", "lcdb_rotation_hours"):
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # Strip whitespace from string columns
    _str_cols = (
        "name", "designation", "family", "taxonomy",
        "u_quality", "binary_flag", "period_flag",
    )
    for col in _str_cols:
        df[col] = df[col].astype(str).str.strip()
        df.loc[df[col].isin(["", "nan", "None"]), col] = pd.NA

    return df


def filter_quality(df: pd.DataFrame, min_quality: frozenset[str] = _VALID_U_CODES) -> pd.DataFrame:
    """Keep only rows with U quality code in the accepted set."""
    mask = df["u_quality"].isin(min_quality)
    kept = int(mask.sum())
    dropped = len(df) - kept
    logger.info("Quality filter: %d kept (U >= 2-), %d dropped", kept, dropped)
    return df[mask].reset_index(drop=True)


def add_spkid(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add ``spkid`` join key: numbered asteroid number + 2_000_000.

    Unnumbered bodies (no number) are dropped since they can't be
    reliably joined to SBDB by spkid alone.
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

    zip_bytes = download_lcdb_zip()
    df = parse_summary(zip_bytes)
    logger.info("Parsed %d LCDB records", len(df))

    df = filter_quality(df)
    df = add_spkid(df)

    today = datetime.now(UTC).strftime("%Y%m%d")
    output_path = raw_dir / f"lcdb_{today}.parquet"
    df.to_parquet(output_path, index=False, engine="pyarrow")

    logger.info(
        "Saved %s — %d records with reliable rotation periods, %.1fs",
        output_path.name,
        len(df),
        time.perf_counter() - started,
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
