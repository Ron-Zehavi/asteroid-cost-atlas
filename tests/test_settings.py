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


def test_load_resolved_config_missing_file(env_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="Config file not found"):
        load_resolved_config(Path("nonexistent.yaml"), env_path)


def test_load_resolved_config_malformed_yaml(tmp_path: Path, env_path: Path) -> None:
    bad_yaml = tmp_path / "config.yaml"
    bad_yaml.write_text("key: [unclosed bracket\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Invalid YAML"):
        load_resolved_config(bad_yaml, env_path)


def test_load_resolved_config_invalid_page_size(config_path: Path, tmp_path: Path) -> None:
    env = tmp_path / ".env"
    env.write_text("SBDB_PAGE_SIZE=abc\n", encoding="utf-8")
    with pytest.raises(ValueError, match="SBDB_PAGE_SIZE must be an integer"):
        load_resolved_config(config_path, env)


def test_load_resolved_config_page_size_float_rejected(
    config_path: Path, tmp_path: Path
) -> None:
    env = tmp_path / ".env"
    env.write_text("SBDB_PAGE_SIZE=1000.5\n", encoding="utf-8")
    with pytest.raises(ValueError, match="SBDB_PAGE_SIZE must be an integer"):
        load_resolved_config(config_path, env)
