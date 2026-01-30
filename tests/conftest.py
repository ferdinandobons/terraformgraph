"""Pytest configuration and fixtures."""

from pathlib import Path

import pytest


@pytest.fixture
def examples_dir() -> Path:
    """Return path to examples directory."""
    return Path(__file__).parent.parent / "examples"


@pytest.fixture
def simple_example(examples_dir) -> Path:
    """Return path to simple example."""
    return examples_dir / "simple"
