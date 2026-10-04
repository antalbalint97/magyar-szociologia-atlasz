from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from szocatlas.pipeline import Paths
from szocatlas.registry import REPO_ROOT, load_registry

FIXTURES = REPO_ROOT / "tests" / "fixtures" / "tk"


@pytest.fixture(scope="session")
def registry():
    return load_registry()


@pytest.fixture(scope="session")
def aliases(registry):
    return registry.host_aliases()


@pytest.fixture
def fixture_html():
    def read(name: str) -> str:
        return (FIXTURES / name).read_text(encoding="utf-8")
    return read


@pytest.fixture
def workdir(tmp_path: Path) -> Paths:
    """An isolated repo-shaped directory (config + review copied, empty data)."""
    shutil.copytree(REPO_ROOT / "config", tmp_path / "config")
    (tmp_path / "review").mkdir()
    shutil.copy(REPO_ROOT / "review" / "manual_overrides.yaml", tmp_path / "review")
    shutil.copy(REPO_ROOT / "review" / "disputed_claims.yaml", tmp_path / "review")
    return Paths(tmp_path)
