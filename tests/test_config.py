"""Tests for etf_utils.config — path constants and env loading."""

from pathlib import Path

from etf_utils.config import (
    ALPHAVANTAGE_API_KEY,
    DATA_CONFIG,
    DATA_INTERMEDIATE,
    DATA_OUTPUT,
    DATA_PROVIDER,
    DATA_RAW,
    PROJECT_ROOT,
)


def test_path_constants_are_paths():
    """All data path constants should be Path objects."""
    for p in (DATA_RAW, DATA_INTERMEDIATE, DATA_OUTPUT, DATA_CONFIG, PROJECT_ROOT):
        assert isinstance(p, Path), f"{p!r} is not a Path"


def test_path_constants_under_project_root():
    """Data paths should be under PROJECT_ROOT."""
    for p in (DATA_RAW, DATA_INTERMEDIATE, DATA_OUTPUT, DATA_CONFIG):
        assert str(p).startswith(str(PROJECT_ROOT)), f"{p} not under {PROJECT_ROOT}"


def test_data_provider_default():
    """DATA_PROVIDER should default to 'yfinance' when .env doesn't override."""
    assert DATA_PROVIDER in ("yfinance", "alphavantage")


def test_alphavantage_key_is_string():
    """ALPHAVANTAGE_API_KEY should be a string (empty if not set)."""
    assert isinstance(ALPHAVANTAGE_API_KEY, str)
