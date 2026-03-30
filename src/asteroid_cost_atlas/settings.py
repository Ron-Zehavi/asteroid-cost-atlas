from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict


class PathsConfig(BaseModel):
    """Paths section of config.yaml — all relative to the repo root."""

    model_config = ConfigDict(extra="forbid")

    raw_json: Path
    csv_dir: Path
    cache_dir: Path
    metadata_dir: Path


class YamlConfig(BaseModel):
    """Direct representation of the parsed config.yaml structure."""

    model_config = ConfigDict(extra="forbid")

    base_url: str
    sbdb_fields: list[str]
    page_size: int
    paths: PathsConfig


class EnvOverrides(BaseModel):
    """Optional environment-variable overrides applied on top of YAML config."""

    model_config = ConfigDict(extra="forbid")

    sbdb_page_size: int | None = None


class ResolvedConfig(BaseModel):
    """
    Fully resolved runtime configuration.

    All paths are absolute. page_size reflects any .env override.
    This is the single object passed through the pipeline at runtime.
    """

    model_config = ConfigDict(extra="forbid")

    base_url: str
    sbdb_fields: list[str]
    page_size: int
    raw_json_path: Path
    csv_dir: Path
    cache_dir: Path
    metadata_dir: Path


def load_env_file(path: Path) -> dict[str, str]:
    """
    Parse a .env file into a key/value dict.

    Lines starting with ``#`` and lines without ``=`` are ignored.
    Surrounding quotes are stripped from values.
    Returns an empty dict if the file does not exist.
    """
    if not path.exists():
        return {}

    values: dict[str, str] = {}

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()

        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")

    return values


def load_resolved_config(config_path: Path, env_path: Path) -> ResolvedConfig:
    """
    Load, merge, and validate the pipeline configuration.

    Reads ``config_path`` (YAML) then applies any overrides from ``env_path``
    (``.env`` format). All paths in the result are resolved to absolute using
    the repo root (the directory containing ``config_path``'s parent).

    Raises
    ------
    FileNotFoundError
        If ``config_path`` does not exist.
    ValueError
        If the YAML is malformed or ``SBDB_PAGE_SIZE`` is not a valid integer.
    """
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    try:
        raw_config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ValueError(f"Invalid YAML in {config_path}: {exc}") from exc

    yaml_config = YamlConfig.model_validate(raw_config)

    raw_env = load_env_file(env_path)

    page_size_override: int | None = None
    if "SBDB_PAGE_SIZE" in raw_env:
        try:
            page_size_override = int(raw_env["SBDB_PAGE_SIZE"])
        except ValueError:
            raise ValueError(
                f"SBDB_PAGE_SIZE must be an integer, got '{raw_env['SBDB_PAGE_SIZE']}'"
            )

    env_overrides = EnvOverrides(sbdb_page_size=page_size_override)

    root = config_path.resolve().parent.parent

    return ResolvedConfig(
        base_url=yaml_config.base_url,
        sbdb_fields=yaml_config.sbdb_fields,
        page_size=env_overrides.sbdb_page_size or yaml_config.page_size,
        raw_json_path=(root / yaml_config.paths.raw_json).resolve(),
        csv_dir=(root / yaml_config.paths.csv_dir).resolve(),
        cache_dir=(root / yaml_config.paths.cache_dir).resolve(),
        metadata_dir=(root / yaml_config.paths.metadata_dir).resolve(),
    )
