from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict


class PathsConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    raw_json: Path
    csv_dir: Path
    cache_dir: Path
    metadata_dir: Path


class YamlConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    base_url: str
    sbdb_fields: list[str]
    page_size: int
    paths: PathsConfig


class EnvOverrides(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sbdb_page_size: int | None = None


class ResolvedConfig(BaseModel):
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
    Input:
        path (Path): .env file path

    Output:
        dict[str, str]: parsed key/value pairs
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
    Input:
        config_path (Path): YAML config file path
        env_path (Path): .env file path

    Output:
        ResolvedConfig: validated runtime configuration
    """
    raw_config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    yaml_config = YamlConfig.model_validate(raw_config)

    raw_env = load_env_file(env_path)
    env_overrides = EnvOverrides.model_validate(
        {
            "sbdb_page_size": int(raw_env["SBDB_PAGE_SIZE"])
            if "SBDB_PAGE_SIZE" in raw_env
            else None
        }
    )

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