from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture()
def config_path() -> Path:
    return Path(__file__).parent.parent / "configs" / "config.yaml"


@pytest.fixture()
def env_path(tmp_path: Path) -> Path:
    return tmp_path / ".env"
