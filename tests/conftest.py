"""Pytest configuration and fixtures."""

from pathlib import Path

import pytest


@pytest.fixture
def example_dir() -> Path:
    """Return path to example directory."""
    return Path(__file__).parent.parent / "example"


@pytest.fixture
def simple_example(example_dir) -> Path:
    """Return path to example (used by integration tests)."""
    return example_dir
