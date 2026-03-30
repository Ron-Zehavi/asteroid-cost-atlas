"""
Data cleaning stage: validates and filters raw SBDB CSV output.

Reads the latest sbdb_*.csv from data/raw/, applies validity filters,
logs every removal with count and reason, and writes a clean Parquet file
to data/processed/.

Raw data is never modified — all filtering happens here and is fully logged.

Cleaning rules (applied in order)
----------------------------------
1. Non-finite orbital elements (a, e, i)   — corrupt API records
2. a_au <= 0                               — physically impossible
3. e >= 1                                  — hyperbolic / interstellar objects,
                                             outside the scope of this pipeline
"""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

_RuleFn = Callable[[pd.DataFrame], "pd.Series[bool]"]

logger = logging.getLogger(__name__)

_ORBITAL_COLUMNS = ["a_au", "eccentricity", "inclination_deg"]


def _mask_non_finite(df: pd.DataFrame) -> pd.Series[bool]:
    result: pd.Series[bool] = (
        ~np.isfinite(df["a_au"])
        | ~np.isfinite(df["eccentricity"])
        | ~np.isfinite(df["inclination_deg"])
    )
    return result


def _mask_a_le_zero(df: pd.DataFrame) -> pd.Series[bool]:
    return df["a_au"] <= 0


def _mask_e_ge_one(df: pd.DataFrame) -> pd.Series[bool]:
    return df["eccentricity"] >= 1


# Each rule is (label, mask_fn) where mask_fn returns True for rows to DROP
_RULES: list[tuple[str, _RuleFn]] = [
    ("non_finite_orbital_elements", _mask_non_finite),
    ("a_au_le_zero",                _mask_a_le_zero),
    ("e_ge_one",                    _mask_e_ge_one),
]


def clean(df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, int]]:
    """
    Apply all cleaning rules to *df* and return the cleaned DataFrame
    plus a dict mapping each rule label to the number of rows it removed.

    Rules are applied sequentially — a row removed by rule 1 is not
    counted again by rule 2.
    """
    removed: dict[str, int] = {}
    result = df.copy()

    for label, mask_fn in _RULES:
        mask = mask_fn(result)
        count = int(mask.sum())
        removed[label] = count
        result = result[~mask].reset_index(drop=True)
        if count:
            logger.info("  removed %6d rows — %s", count, label)

    return result, removed


def _latest_raw_csv(raw_dir: Path) -> Path:
    candidates = sorted(raw_dir.glob("sbdb_*.csv"))
    if not candidates:
        raise FileNotFoundError(
            f"No sbdb_*.csv files found in {raw_dir}. Run 'make ingest' first."
        )
    return candidates[-1]


def _write_metadata(
    metadata_dir: Path,
    today: str,
    source_file: str,
    rows_in: int,
    rows_out: int,
    removed: dict[str, int],
) -> None:
    metadata_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "run_date": today,
        "source_file": source_file,
        "rows_in": rows_in,
        "rows_out": rows_out,
        "rows_removed": rows_in - rows_out,
        "removed_by_rule": removed,
    }
    path = metadata_dir / f"sbdb_clean_{today}.metadata.json"
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    logger.info("Metadata written to %s", path.name)


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    started = time.perf_counter()

    _module = Path(__file__).resolve()
    repo_root = next(p for p in [_module, *_module.parents] if (p / "pyproject.toml").exists())
    raw_dir = repo_root / "data" / "raw"
    processed_dir = repo_root / "data" / "processed"
    metadata_dir = repo_root / "data" / "raw" / "metadata"
    processed_dir.mkdir(parents=True, exist_ok=True)

    input_path = _latest_raw_csv(raw_dir)
    logger.info("Reading %s", input_path.name)

    df = pd.read_csv(input_path)
    rows_in = len(df)
    logger.info("Loaded %d rows — applying cleaning rules", rows_in)

    cleaned, removed = clean(df)
    rows_out = len(cleaned)

    today = datetime.now(UTC).strftime("%Y%m%d")
    output_path = processed_dir / f"sbdb_clean_{today}.parquet"
    cleaned.to_parquet(output_path, index=False, engine="pyarrow")

    _write_metadata(metadata_dir, today, input_path.name, rows_in, rows_out, removed)

    logger.info(
        "Saved %s — %d rows kept, %d removed, %.1fs",
        output_path.name,
        rows_out,
        rows_in - rows_out,
        time.perf_counter() - started,
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
