"""Shared test fixtures for etf_utils tests."""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

# Ensure etf_utils is importable from tests/
sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture
def sample_price_df():
    """Small DataFrame of mock daily prices with DatetimeIndex and 'close' column."""
    dates = pd.bdate_range("2024-01-02", periods=10)
    prices = [100.0, 101.5, 99.8, 102.3, 103.0, 101.2, 104.5, 105.1, 103.9, 106.0]
    return pd.DataFrame({"close": prices}, index=dates)


@pytest.fixture
def sample_portfolio_df():
    """Mock final_portfolio.csv content."""
    return pd.DataFrame(
        {
            "ticker": ["VEVE", "IGLT", "AUAD"],
            "name": ["Vanguard FTSE", "iShares Gilts", "UBS Australia"],
            "asset_class": ["equity", "bonds", "equity"],
            "region_category": [
                "Developed_AmericasandUK",
                "Developed_AmericasandUK",
                "Developed_APAC",
            ],
            "investment": [5000.0, 2000.0, 3000.0],
            "final_cash_weights": [50, 20, 30],
            "ter": [0.12, 0.07, 0.40],
        }
    )


@pytest.fixture
def tmp_data_dir(tmp_path):
    """Create a temporary directory structure mirroring data/{raw,intermediate,output,config}."""
    for sub in ("raw", "intermediate", "output", "config"):
        (tmp_path / sub).mkdir()
    return tmp_path
