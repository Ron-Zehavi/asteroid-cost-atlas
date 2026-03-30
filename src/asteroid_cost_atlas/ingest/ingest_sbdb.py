from __future__ import annotations

import argparse
import hashlib
import json
import logging
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd
import requests
from requests.adapters import HTTPAdapter, Retry

from asteroid_cost_atlas.settings import ResolvedConfig, load_resolved_config


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
            "logger": record.name,
        }

        if hasattr(record, "context"):
            payload["context"] = record.context

        return json.dumps(payload)


logger = logging.getLogger(__name__)


COLUMN_RENAME_MAP = {
    "full_name": "name",
    "a": "a_au",
    "e": "eccentricity",
    "i": "inclination_deg",
    "H": "abs_magnitude",
    "G": "magnitude_slope",
    "diameter": "diameter_km",
    "rot_per": "rotation_hours",
    "moid": "moid_au",
    "class": "orbit_class",
    "spec_B": "spectral_type",
}


NUMERIC_COLUMNS = [
    "a_au",
    "eccentricity",
    "inclination_deg",
    "abs_magnitude",
    "magnitude_slope",
    "diameter_km",
    "rotation_hours",
    "albedo",
    "moid_au",
]


def parse_args(default_page_size: int, default_output_dir: Path) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--page-size", type=int, default=default_page_size)
    parser.add_argument("--output", type=Path, default=default_output_dir)
    return parser.parse_args()


def get_cache_path(
    cache_dir: Path,
    base_url: str,
    sbdb_fields: list[str],
    page_size: int,
    offset: int,
) -> Path:
    cache_key = f"{base_url}|{','.join(sbdb_fields)}|{page_size}|{offset}"
    digest = hashlib.md5(cache_key.encode("utf-8")).hexdigest()
    return cache_dir / f"{digest}.json"


def fetch_page(
    session: requests.Session,
    base_url: str,
    sbdb_fields: list[str],
    page_size: int,
    offset: int,
    cache_dir: Path,
) -> dict[str, Any]:
    cache_dir.mkdir(parents=True, exist_ok=True)

    cache_path = get_cache_path(
        cache_dir,
        base_url,
        sbdb_fields,
        page_size,
        offset,
    )

    if cache_path.exists():
        return dict(json.loads(cache_path.read_text(encoding="utf-8")))

    params: dict[str, str | int] = {
        "fields": ",".join(sbdb_fields),
        "limit": page_size,
        "limit-from": offset,
    }
    response = session.get(base_url, params=params, timeout=30)

    response.raise_for_status()

    payload: dict[str, Any] = dict(response.json())

    cache_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    return payload


def fetch_all_pages(
    session: requests.Session,
    base_url: str,
    sbdb_fields: list[str],
    page_size: int,
    cache_dir: Path,
) -> dict[str, Any]:
    all_rows: list[list[str | None]] = []
    offset = 0
    page_number = 0

    while True:
        page_number += 1

        payload = fetch_page(
            session,
            base_url,
            sbdb_fields,
            page_size,
            offset,
            cache_dir,
        )

        if payload.get("fields") != sbdb_fields:
            raise ValueError(
                f"Returned fields {payload.get('fields')!r} "
                f"differ from requested {sbdb_fields!r}."
            )

        rows = payload.get("data", [])

        if not isinstance(rows, list):
            raise ValueError("Payload data must be a list.")

        row_count = len(rows)

        logger.info(
            "Fetched page",
            extra={
                "context": {
                    "page_number": page_number,
                    "offset": offset,
                    "row_count": row_count,
                }
            },
        )

        if row_count == 0:
            break

        if row_count > page_size:
            raise ValueError(
                f"Page returned {row_count} rows, exceeding page size {page_size}."
            )

        all_rows.extend(rows)

        if row_count < page_size:
            break

        offset += page_size

    return {"fields": sbdb_fields, "data": all_rows}


def to_dataframe(payload: dict[str, Any]) -> pd.DataFrame:
    df = pd.DataFrame(payload["data"], columns=payload["fields"])

    df = df.rename(columns=COLUMN_RENAME_MAP)

    df[NUMERIC_COLUMNS] = df[NUMERIC_COLUMNS].apply(
        pd.to_numeric,
        errors="coerce",
    )

    rows_before = len(df)
    df = df.dropna(subset=["a_au", "eccentricity", "inclination_deg"])
    dropped = rows_before - len(df)
    if dropped:
        logger.warning("Dropped %d rows with missing orbital elements at ingest", dropped)
    return df


def write_metadata(
    metadata_path: Path,
    run_date: str,
    source_url: str,
    sbdb_fields: list[str],
    record_count: int,
) -> None:
    metadata = {
        "run_date": run_date,
        "source_url": source_url,
        "sbdb_fields": sbdb_fields,
        "record_count": record_count,
    }

    metadata_path.parent.mkdir(parents=True, exist_ok=True)

    metadata_path.write_text(
        json.dumps(metadata, indent=2),
        encoding="utf-8",
    )


def main() -> int:
    _handler = logging.StreamHandler()
    _handler.setFormatter(JsonFormatter())
    logger.addHandler(_handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False

    started = time.perf_counter()

    _module = Path(__file__).resolve()
    _repo_root = next(p for p in [_module, *_module.parents] if (p / "pyproject.toml").exists())

    config: ResolvedConfig = load_resolved_config(
        _repo_root / "configs" / "config.yaml",
        _repo_root / ".env",
    )

    args = parse_args(config.page_size, config.csv_dir)

    today = datetime.now(UTC).strftime("%Y%m%d")

    csv_path = args.output / f"sbdb_{today}.csv"
    metadata_path = (
        config.metadata_dir
        / f"sbdb_{today}.metadata.json"
    )

    _adapter = HTTPAdapter(
        max_retries=Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 503])
    )
    with requests.Session() as session:
        session.mount("https://", _adapter)
        session.mount("http://", _adapter)
        payload = fetch_all_pages(
            session,
            config.base_url,
            config.sbdb_fields,
            args.page_size,
            config.cache_dir,
        )

    config.raw_json_path.write_text(
        json.dumps(payload, indent=2),
        encoding="utf-8",
    )

    df = to_dataframe(payload)

    df.to_csv(csv_path, index=False)

    write_metadata(
        metadata_path,
        today,
        config.base_url,
        config.sbdb_fields,
        len(df),
    )

    logger.info(
        "Ingestion complete",
        extra={
            "context": {
                "records": len(df),
                "duration_sec": round(
                    time.perf_counter() - started,
                    2,
                ),
            }
        },
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())