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
    """Symbols with a dot are converted to the right active provider suffix."""
    assert _normalize_symbol("ISF.LON", "yfinance") == "ISF.L"
    assert _normalize_symbol("VEVE.L", "alphavantage") == "VEVE.LON"


def test_normalize_symbol_no_suffix_various():
    assert _normalize_symbol("SPY", "yfinance") == "SPY"
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
    mock_download.assert_called_once_with("VEVE.L", period="max", progress=False, auto_adjust=True)


@patch("etf_utils.data_provider.requests.get")
@patch("etf_utils.data_provider.yf.download")
def test_get_historical_prices_empty_raises(mock_download, mock_get):
    """Empty download should raise ValueError after falling back to AlphaVantage."""
    mock_download.return_value = pd.DataFrame()
    mock_response = MagicMock()
    mock_response.json.return_value = {}
    mock_get.return_value = mock_response
    provider = DataProvider(provider="yfinance")
    with pytest.raises(ValueError, match="No AlphaVantage data for 'FAKE.LON'"):
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
    mock_download.assert_called_once_with("GBPEUR=X", period="max", progress=False, auto_adjust=True)


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


# --- GBX/GBP normalisation ---


@patch("etf_utils.data_provider.yf.download")
def test_gbx_whole_series_normalised_to_gbp(mock_download):
    """Series entirely in GBX (pence) should be divided by 100."""
    dates = pd.bdate_range("2024-01-02", periods=5)
    # Prices in pence (~1800 GBX = £18 GBP)
    mock_df = pd.DataFrame({"Close": [1800.0, 1810.0, 1820.0, 1830.0, 1840.0]}, index=dates)
    mock_download.return_value = mock_df

    provider = DataProvider(provider="yfinance")
    result = provider.get_historical_prices("AUAD")  # Will use AUAD.L

    # Should be normalised to GBP
    assert result["close"].iloc[0] == pytest.approx(18.0, rel=0.01)
    assert result["close"].iloc[-1] == pytest.approx(18.4, rel=0.01)


@patch("etf_utils.data_provider.yf.download")
def test_gbp_series_not_normalised(mock_download):
    """Series already in GBP should not be divided."""
    dates = pd.bdate_range("2024-01-02", periods=5)
    mock_df = pd.DataFrame({"Close": [12.0, 12.1, 12.2, 12.3, 12.4]}, index=dates)
    mock_download.return_value = mock_df

    provider = DataProvider(provider="yfinance")
    result = provider.get_historical_prices("LCUK")

    assert result["close"].iloc[0] == pytest.approx(12.0, rel=0.01)
    assert result["close"].iloc[-1] == pytest.approx(12.4, rel=0.01)

