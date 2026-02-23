"""Tests for etf_utils.metrics — financial calculations."""

import numpy as np
import pandas as pd
import pytest

from etf_utils.metrics import (
    calculate_annualized_volatility,
    calculate_daily_pnl,
    calculate_period_metrics,
    calculate_sharpe_ratio,
    interpolate_adjustment_factor,
)


# --- calculate_annualized_volatility ---


def test_annualized_volatility_known_values(sample_price_df):
    vol = calculate_annualized_volatility(sample_price_df["close"])
    assert isinstance(vol, float)
    assert vol > 0
    # Rough check: daily std * sqrt(252) should be in a reasonable range
    daily_std = sample_price_df["close"].pct_change().dropna().std()
    expected = daily_std * np.sqrt(252)
    assert abs(vol - expected) < 1e-10


def test_annualized_volatility_constant_prices():
    """Constant prices → zero volatility."""
    prices = pd.Series([100.0] * 10)
    vol = calculate_annualized_volatility(prices)
    assert vol == 0.0


def test_annualized_volatility_too_few_observations():
    """Fewer than 2 returns → NaN with warning."""
    prices = pd.Series([100.0])
    with pytest.warns(UserWarning, match="Fewer than 2"):
        vol = calculate_annualized_volatility(prices)
    assert np.isnan(vol)


# --- calculate_sharpe_ratio ---


def test_sharpe_ratio_basic():
    result = calculate_sharpe_ratio(10.0, 15.0, 2.0)
    assert result == pytest.approx((10.0 - 2.0) / 15.0)


def test_sharpe_ratio_zero_volatility():
    result = calculate_sharpe_ratio(10.0, 0.0)
    assert np.isnan(result)


def test_sharpe_ratio_no_risk_free():
    result = calculate_sharpe_ratio(12.0, 8.0)
    assert result == pytest.approx(12.0 / 8.0)


# --- interpolate_adjustment_factor ---


_FACTORS = {
    -1.0: 0.60,
    -0.5: 0.80,
    0.0: 1.00,
    0.5: 1.20,
    1.0: 1.48,
}


def test_interpolate_exact_match():
    assert interpolate_adjustment_factor(0.0, _FACTORS) == pytest.approx(1.00)
    assert interpolate_adjustment_factor(-1.0, _FACTORS) == pytest.approx(0.60)
    assert interpolate_adjustment_factor(1.0, _FACTORS) == pytest.approx(1.48)


def test_interpolate_within_range():
    """Midpoint between 0.0 (1.00) and 0.5 (1.20) → 1.10."""
    result = interpolate_adjustment_factor(0.25, _FACTORS)
    assert result == pytest.approx(1.10)


def test_interpolate_below_min():
    """Below the minimum key → clipped to boundary."""
    result = interpolate_adjustment_factor(-2.0, _FACTORS)
    assert result == pytest.approx(0.60)


def test_interpolate_above_max():
    """Above the maximum key → clipped to boundary."""
    result = interpolate_adjustment_factor(5.0, _FACTORS)
    assert result == pytest.approx(1.48)


# --- calculate_period_metrics ---


def test_period_metrics_full_range(sample_price_df):
    start = str(sample_price_df.index[0].date())
    end = str(sample_price_df.index[-1].date())
    result = calculate_period_metrics(sample_price_df, start, end)
    assert "return" in result and "volatility" in result
    expected_return = (106.0 - 100.0) / 100.0
    assert result["return"] == pytest.approx(expected_return)
    assert result["volatility"] > 0


def test_period_metrics_too_few_points():
    df = pd.DataFrame({"close": [100.0]}, index=pd.DatetimeIndex(["2024-01-02"]))
    with pytest.warns(UserWarning, match="Fewer than 2"):
        result = calculate_period_metrics(df, "2024-01-02", "2024-01-02")
    assert np.isnan(result["return"])


# --- calculate_daily_pnl ---


def test_daily_pnl_basic(sample_price_df):
    result = calculate_daily_pnl(sample_price_df, 1000.0, "2024-01-02", "2024-01-15")
    assert "daily_return" in result.columns
    assert "pnl" in result.columns
    # First row should have NaN return (no prior day)
    assert np.isnan(result["daily_return"].iloc[0])
    # Non-first rows should have numeric PnL
    assert result["pnl"].iloc[1:].notna().all()


def test_daily_pnl_investment_scaling(sample_price_df):
    """PnL should scale linearly with investment amount."""
    pnl_1k = calculate_daily_pnl(sample_price_df, 1000.0, "2024-01-02")
    pnl_2k = calculate_daily_pnl(sample_price_df, 2000.0, "2024-01-02")
    # pnl_2k should be 2x pnl_1k (ignoring NaN first row)
    ratio = pnl_2k["pnl"].iloc[1:].values / pnl_1k["pnl"].iloc[1:].values
    np.testing.assert_allclose(ratio, 2.0)
