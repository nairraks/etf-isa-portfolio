"""Tests for etf_utils.data_provider -- DataProvider and symbol normalization."""

import json
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


@patch("etf_utils.data_provider.yf.download")
def test_get_historical_prices_warns_on_non_lse_suffix(mock_download):
    """A ticker resolving to a non-.L listing should emit an FX-boundary warning."""
    dates = pd.bdate_range("2024-01-02", periods=3)
    mock_df = pd.DataFrame({"Close": [100.0, 101.0, 102.0]}, index=dates)
    mock_download.return_value = mock_df

    provider = DataProvider(provider="yfinance")
    with pytest.warns(UserWarning, match="not an LSE"):
        # TRT is mapped to .TO (Toronto) by _normalize_symbol
        provider.get_historical_prices("AAA.TRT")


@patch("etf_utils.data_provider.yf.download")
def test_get_historical_prices_warns_on_us_bypass_ticker(mock_download):
    """US-listed bypass tickers (e.g. SPY) should also warn about FX exposure."""
    dates = pd.bdate_range("2024-01-02", periods=3)
    mock_df = pd.DataFrame({"Close": [400.0, 401.0, 402.0]}, index=dates)
    mock_download.return_value = mock_df

    provider = DataProvider(provider="yfinance")
    with pytest.warns(UserWarning, match="non-LSE .US-listed"):
        provider.get_historical_prices("SPY")


@patch("etf_utils.data_provider.yf.download")
def test_get_historical_prices_no_warning_for_lse_ticker(mock_download, recwarn):
    """A .L ticker should NOT emit the FX-boundary warning."""
    dates = pd.bdate_range("2024-01-02", periods=3)
    mock_df = pd.DataFrame({"Close": [100.0, 101.0, 102.0]}, index=dates)
    mock_download.return_value = mock_df

    provider = DataProvider(provider="yfinance")
    provider.get_historical_prices("VEVE")
    # No "non-LSE" warnings should have been raised
    non_lse_warnings = [w for w in recwarn.list if "non-LSE" in str(w.message) or "not an LSE" in str(w.message)]
    assert len(non_lse_warnings) == 0


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
    """Series entirely in GBX (pence) should be divided by 100 via explicit mapping."""
    dates = pd.bdate_range("2024-01-02", periods=5)
    # Prices in pence (~1800 GBX = £18 GBP)
    mock_df = pd.DataFrame({"Close": [1800.0, 1810.0, 1820.0, 1830.0, 1840.0]}, index=dates)
    mock_download.return_value = mock_df

    provider = DataProvider(provider="yfinance")
    # AUAD is mapped as GBX in currency_units.json
    result = provider.get_historical_prices("AUAD")

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


@patch("etf_utils.data_provider.yf.download")
def test_gbx_saaa_normalised_to_gbp(mock_download):
    """SAAA is mapped as GBX -- prices in pence should be divided by 100."""
    dates = pd.bdate_range("2024-01-02", periods=5)
    mock_df = pd.DataFrame(
        {"Close": [105.0, 105.5, 106.0, 105.8, 106.2]}, index=dates
    )
    mock_download.return_value = mock_df

    provider = DataProvider(provider="yfinance")
    result = provider.get_historical_prices("SAAA")

    # SAAA is GBX, so 105 pence -> 1.05 GBP
    assert result["close"].iloc[0] == pytest.approx(1.05, rel=0.01)
    assert result["close"].iloc[-1] == pytest.approx(1.062, rel=0.01)


@patch("etf_utils.data_provider.yf.download")
def test_gbx_mixed_units_low_range(mock_download):
    """Series that switches from GBP to GBX mid-series should normalise the GBX chunk (heuristic fallback)."""
    dates = pd.bdate_range("2024-01-02", periods=10)
    # First 5 days in GBP (~1.05), then jumps to GBX (~105)
    prices = [1.05, 1.06, 1.04, 1.05, 1.06, 105.0, 106.0, 104.5, 105.5, 106.0]
    mock_df = pd.DataFrame({"Close": prices}, index=dates)
    mock_download.return_value = mock_df

    provider = DataProvider(provider="yfinance")
    # Use unknown ticker to exercise heuristic fallback
    with pytest.warns(UserWarning, match="not found in currency_units.json"):
        result = provider.get_historical_prices("ZZMIX")

    # All values should be in GBP range (~1.0-1.1)
    assert result["close"].max() < 2.0
    assert result["close"].min() > 0.5


@patch("etf_utils.data_provider.yf.download")
def test_gbp_moderate_price_not_normalised(mock_download):
    """ETF at ~50 GBP should NOT be divided by 100."""
    dates = pd.bdate_range("2024-01-02", periods=5)
    mock_df = pd.DataFrame(
        {"Close": [50.0, 50.5, 51.0, 50.8, 51.2]}, index=dates
    )
    mock_download.return_value = mock_df

    provider = DataProvider(provider="yfinance")
    result = provider.get_historical_prices("VEVE")

    assert result["close"].iloc[0] == pytest.approx(50.0, rel=0.01)
    assert result["close"].iloc[-1] == pytest.approx(51.2, rel=0.01)


@patch("etf_utils.data_provider.yf.download")
def test_end_date_inclusive_for_yfinance(mock_download):
    """end_date should be adjusted +1 day when passed to yf.download."""
    dates = pd.bdate_range("2024-01-02", periods=5)
    mock_df = pd.DataFrame({"Close": [100, 101, 102, 103, 104]}, index=dates)
    mock_download.return_value = mock_df

    provider = DataProvider(provider="yfinance")
    provider.get_historical_prices("VEVE", start_date="2024-01-02", end_date="2024-01-08")

    call_kwargs = mock_download.call_args[1]
    # yfinance should receive end="2024-01-09" (one day after requested end)
    assert call_kwargs["end"] == "2024-01-09"


@patch("etf_utils.data_provider.yf.download")
def test_hmch_gbx_normalised(mock_download):
    """HMCH is mapped as GBX -- prices around 500 pence should become ~5 GBP."""
    dates = pd.bdate_range("2024-01-02", periods=5)
    mock_df = pd.DataFrame(
        {"Close": [550.0, 556.0, 560.0, 558.0, 579.0]}, index=dates
    )
    mock_download.return_value = mock_df

    provider = DataProvider(provider="yfinance")
    result = provider.get_historical_prices("HMCH")

    assert result["close"].iloc[0] == pytest.approx(5.50, rel=0.01)
    assert result["close"].iloc[-1] == pytest.approx(5.79, rel=0.01)


@patch("etf_utils.data_provider.yf.download")
def test_unknown_ticker_falls_back_to_heuristic(mock_download):
    """Ticker not in currency_units.json should trigger a warning and use heuristic."""
    dates = pd.bdate_range("2024-01-02", periods=5)
    mock_df = pd.DataFrame(
        {"Close": [1200.0, 1210.0, 1220.0, 1215.0, 1230.0]}, index=dates
    )
    mock_download.return_value = mock_df

    provider = DataProvider(provider="yfinance")
    with pytest.warns(UserWarning, match="not found in currency_units.json"):
        result = provider.get_historical_prices("ZZZNEW")

    # Heuristic: median 1215 > 500, so should be divided by 100
    assert result["close"].iloc[0] == pytest.approx(12.0, rel=0.01)


@patch("etf_utils.data_provider.yf.download")
def test_heuristic_low_range_100_500(mock_download):
    """Verify that tickers in the 100-500 range are now caught by the improved heuristic (threshold=100)."""
    dates = pd.bdate_range("2024-01-02", periods=5)
    # Median ~105, was ignored when threshold was 500
    mock_df = pd.DataFrame(
        {"Close": [105.0, 106.0, 104.0, 105.5, 106.5]}, index=dates
    )
    mock_download.return_value = mock_df

    provider = DataProvider(provider="yfinance")
    # Use unknown ticker to trigger heuristic
    with pytest.warns(UserWarning, match="not found in currency_units.json"):
        result = provider.get_historical_prices("LOW PRICE")

    # Should now be divided by 100
    assert result["close"].iloc[0] == pytest.approx(1.05, rel=0.01)


