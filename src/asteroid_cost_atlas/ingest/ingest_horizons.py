"""
JPL Horizons orbital element ingestion for near-Earth asteroids.

Queries the JPL Horizons API for high-precision osculating orbital
elements (a, e, i) using numerical integration models that account for
planetary perturbations — significantly more accurate than the 2-body
SBDB elements for trajectory-sensitive targets.

Scoped to NEAs (~35 K objects) to respect API rate limits.  The
enrichment step merges these into the orbital scoring stage, with
SBDB elements as fallback for non-NEA objects.

Join key: spkid (directly from Horizons small-body lookup).

References
----------
JPL Horizons System: https://ssd.jpl.nasa.gov/horizons/
Horizons API: https://ssd-api.jpl.nasa.gov/doc/horizons.html
"""

from __future__ import annotations

import logging
import math
import time
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import requests

# Horizons API endpoint
HORIZONS_API_URL = "https://ssd.jpl.nasa.gov/api/horizons.api"

# Default epoch for osculating elements (J2000)
DEFAULT_EPOCH = "2451545.0"  # JD 2451545.0 = 2000-01-01.5 TDB

# Rate limiting: maximum requests per second
_RATE_LIMIT_DELAY = 0.5  # seconds between requests

logger = logging.getLogger(__name__)


def fetch_horizons_elements(
    spkid: int,
    epoch_jd: str = DEFAULT_EPOCH,
    api_url: str = HORIZONS_API_URL,
    timeout: int = 30,
) -> dict[str, float] | None:
    """
    Query Horizons for osculating orbital elements of a single object.

    Returns a dict with keys: a_au, eccentricity, inclination_deg,
    or None if the object cannot be resolved.
    """
    params = {
        "format": "json",
        "COMMAND": f"'{spkid}'",
        "OBJ_DATA": "NO",
        "MAKE_EPHEM": "YES",
        "EPHEM_TYPE": "ELEMENTS",
        "CENTER": "'500@10'",  # Sun
        "TLIST": epoch_jd,
    }

    try:
        resp = requests.get(api_url, params=params, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
    except (requests.RequestException, ValueError):
        return None

    return _parse_elements_response(data)


def _parse_elements_response(data: dict) -> dict[str, float] | None:  # type: ignore[type-arg]
    """Extract a, e, i from a Horizons JSON elements response."""
    result_text = data.get("result", "")
    if not result_text:
        return None

    a = _extract_field(result_text, "A=", "AU")
    e = _extract_field(result_text, "EC=", None)
    inc = _extract_field(result_text, "IN=", None)

    if a is None or e is None or inc is None:
        return None

    if not (math.isfinite(a) and math.isfinite(e) and math.isfinite(inc)):
        return None

    if a <= 0 or e < 0 or e >= 1:
        return None

    return {
        "a_au_horizons": a,
        "eccentricity_horizons": e,
        "inclination_deg_horizons": inc,
    }


def _extract_field(text: str, prefix: str, suffix: str | None) -> float | None:
    """Extract a numeric value following ``prefix`` in the Horizons text output."""
    idx = text.find(prefix)
    if idx < 0:
        return None
    start = idx + len(prefix)
    # Skip leading whitespace after prefix
    while start < len(text) and text[start] == " ":
        start += 1
    # Read until whitespace or suffix
    end = start
    while end < len(text) and text[end] not in (" ", "\n", "\r"):
        end += 1
    try:
        return float(text[start:end].strip())
    except ValueError:
        return None


def fetch_batch(
    spkids: list[int],
    epoch_jd: str = DEFAULT_EPOCH,
    api_url: str = HORIZONS_API_URL,
) -> pd.DataFrame:
    """
    Fetch Horizons elements for a batch of objects.

    Respects rate limiting. Returns a DataFrame with columns:
    spkid, a_au_horizons, eccentricity_horizons, inclination_deg_horizons.
    """
    records: list[dict[str, float | int]] = []

    for i, spkid in enumerate(spkids):
        if i > 0:
            time.sleep(_RATE_LIMIT_DELAY)

        elements = fetch_horizons_elements(spkid, epoch_jd, api_url)
        if elements is not None:
            elements["spkid"] = spkid
            records.append(elements)

        if (i + 1) % 100 == 0:
            logger.info("Horizons: fetched %d / %d", i + 1, len(spkids))

    if not records:
        return pd.DataFrame(
            columns=["spkid", "a_au_horizons", "eccentricity_horizons", "inclination_deg_horizons"]
        )

    return pd.DataFrame(records)


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    started = time.perf_counter()

    _module = Path(__file__).resolve()
    repo_root = next(p for p in [_module, *_module.parents] if (p / "pyproject.toml").exists())
    raw_dir = repo_root / "data" / "raw"
    processed_dir = repo_root / "data" / "processed"
    raw_dir.mkdir(parents=True, exist_ok=True)

    # Find the latest enriched or clean parquet to identify NEAs
    enriched_candidates = sorted(processed_dir.glob("sbdb_enriched_*.parquet"))
    clean_candidates = sorted(processed_dir.glob("sbdb_clean_*.parquet"))
    if enriched_candidates:
        input_path = enriched_candidates[-1]
    elif clean_candidates:
        input_path = clean_candidates[-1]
    else:
        logger.error("No processed parquet found. Run 'make enrich' first.")
        return 1

    df = pd.read_parquet(input_path)

    # Filter to NEAs only
    if "neo" in df.columns:
        nea_mask = df["neo"].astype(str).str.upper() == "Y"
        nea_spkids = df.loc[nea_mask, "spkid"].dropna().astype(int).tolist()
    else:
        logger.warning("No 'neo' column found — cannot identify NEAs")
        return 1

    logger.info("Found %d NEAs to query from Horizons", len(nea_spkids))

    result = fetch_batch(nea_spkids)

    today = datetime.now(UTC).strftime("%Y%m%d")
    output_path = raw_dir / f"horizons_{today}.parquet"
    result.to_parquet(output_path, index=False, engine="pyarrow")

    logger.info(
        "Saved %s — %d NEAs with Horizons elements, %.1fs",
        output_path.name, len(result),
        time.perf_counter() - started,
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
