from __future__ import annotations

from pathlib import Path

import pytest

from asteroid_cost_atlas.settings import load_env_file, load_resolved_config


def test_load_env_file_empty(tmp_path: Path) -> None:
    env = tmp_path / ".env"
    env.write_text("", encoding="utf-8")
    assert load_env_file(env) == {}


def test_load_env_file_missing(tmp_path: Path) -> None:
    assert load_env_file(tmp_path / "nonexistent.env") == {}


def test_load_env_file_parses_values(tmp_path: Path) -> None:
    env = tmp_path / ".env"
    env.write_text('SBDB_PAGE_SIZE=500\n# comment\nFOO="bar"\n', encoding="utf-8")
    result = load_env_file(env)
    assert result["SBDB_PAGE_SIZE"] == "500"
    assert result["FOO"] == "bar"
    assert "# comment" not in result


def test_load_resolved_config_defaults(config_path: Path, env_path: Path) -> None:
    config = load_resolved_config(config_path, env_path)
    assert config.base_url == "https://ssd-api.jpl.nasa.gov/sbdb_query.api"
    assert config.page_size == 20000
    assert "spkid" in config.sbdb_fields


def test_load_resolved_config_env_override(config_path: Path, tmp_path: Path) -> None:
    env = tmp_path / ".env"
    env.write_text("SBDB_PAGE_SIZE=500\n", encoding="utf-8")
    config = load_resolved_config(config_path, env)
    assert config.page_size == 500


def test_resolved_config_paths_are_absolute(config_path: Path, env_path: Path) -> None:
    config = load_resolved_config(config_path, env_path)
    assert config.raw_json_path.is_absolute()
    assert config.csv_dir.is_absolute()
    assert config.cache_dir.is_absolute()
    assert config.metadata_dir.is_absolute()
