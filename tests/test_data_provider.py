"""Tests for etf_utils.data_provider — DataProvider and symbol normalization."""

import pandas as pd
import pytest
from unittest.mock import patch, MagicMock

from etf_utils.data_provider import DataProvider, _normalize_symbol


# --- _normalize_symbol ---


def test_normalize_symbol_yfinance_bare():
    assert _normalize_symbol("VEVE", "yfinance") == "VEVE.L"


def test_normalize_symbol_alphavantage_bare():
    assert _normalize_symbol("VEVE", "alphavantage") == "VEVE.LON"


def test_normalize_symbol_already_has_suffix():
    """Symbols with a dot should pass through unchanged."""
    assert _normalize_symbol("ISF.LON", "yfinance") == "ISF.LON"
    assert _normalize_symbol("VEVE.L", "alphavantage") == "VEVE.L"


def test_normalize_symbol_no_suffix_various():
    assert _normalize_symbol("SPY", "yfinance") == "SPY.L"
    assert _normalize_symbol("AUAD", "yfinance") == "AUAD.L"


# --- DataProvider init ---


def test_provider_defaults_to_yfinance():
    provider = DataProvider()
    assert provider.provider == "yfinance"


@patch.dict("os.environ", {"DATA_PROVIDER": "alphavantage"})
def test_provider_from_env():
    """DATA_PROVIDER env var should control the default provider."""
    # Need to reimport config to pick up env change
    from etf_utils import config
    import importlib

    importlib.reload(config)
    provider = DataProvider(provider=config.DATA_PROVIDER)
    assert provider.provider == "alphavantage"
    # Restore
    importlib.reload(config)


def test_provider_explicit_override():
    provider = DataProvider(provider="alphavantage")
    assert provider.provider == "alphavantage"


# --- get_historical_prices (mocked) ---


@patch("etf_utils.data_provider.yf.download")
def test_get_historical_prices_yfinance(mock_download):
    """Mock yf.download and verify DataFrame schema."""
    dates = pd.bdate_range("2024-01-02", periods=5)
    mock_df = pd.DataFrame({"Close": [100, 101, 102, 103, 104]}, index=dates)
    mock_download.return_value = mock_df

    provider = DataProvider(provider="yfinance")
    result = provider.get_historical_prices("VEVE")

    assert list(result.columns) == ["close"]
    assert len(result) == 5
    assert result.index.is_monotonic_increasing
    mock_download.assert_called_once_with("VEVE.L", progress=False, auto_adjust=True)


@patch("etf_utils.data_provider.yf.download")
def test_get_historical_prices_empty_raises(mock_download):
    """Empty download should raise ValueError."""
    mock_download.return_value = pd.DataFrame()
    provider = DataProvider(provider="yfinance")
    with pytest.raises(ValueError, match="No data returned"):
        provider.get_historical_prices("FAKE")


# --- get_fx_rate (mocked) ---


@patch("etf_utils.data_provider.yf.download")
def test_get_fx_rate_yfinance(mock_download):
    dates = pd.bdate_range("2024-01-02", periods=3)
    mock_df = pd.DataFrame({"Close": [0.85, 0.86, 0.84]}, index=dates)
    mock_download.return_value = mock_df

    provider = DataProvider(provider="yfinance")
    result = provider.get_fx_rate("GBP", "EUR")

    assert list(result.columns) == ["rate"]
    assert len(result) == 3
    mock_download.assert_called_once_with("GBPEUR=X", progress=False, auto_adjust=True)


# --- get_latest_price ---


@patch("etf_utils.data_provider.yf.download")
def test_get_latest_price(mock_download):
    dates = pd.bdate_range("2024-01-02", periods=5)
    mock_df = pd.DataFrame({"Close": [100, 101, 102, 103, 104.5]}, index=dates)
    mock_download.return_value = mock_df

    provider = DataProvider(provider="yfinance")
    date_str, price = provider.get_latest_price("VEVE")

    assert isinstance(date_str, str)
    assert price == 104.5


# --- get_benchmark_period_return ---


@patch("etf_utils.data_provider.yf.download")
def test_benchmark_period_return(mock_download):
    dates = pd.bdate_range("2024-01-02", periods=250)
    prices = [100 + i * 0.1 for i in range(250)]
    mock_df = pd.DataFrame({"Close": prices}, index=dates)
    mock_download.return_value = mock_df

    provider = DataProvider(provider="yfinance")
    ret = provider.get_benchmark_period_return("VEVE", "2024-01-02", "2024-12-31")

    assert isinstance(ret, float)
    assert ret > 0  # Prices are rising
