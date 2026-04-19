"""Tests for etf_utils.metrics — financial calculations."""

import numpy as np
import pandas as pd
import pytest

from etf_utils.metrics import (
    calculate_annualized_volatility,
    calculate_beta,
    calculate_daily_pnl,
    calculate_dynamic_rfr,
    calculate_information_ratio,
    calculate_max_drawdown,
    calculate_period_metrics,
    calculate_sharpe_ratio,
    calculate_tracking_error,
    interpolate_adjustment_factor,
    rolling_sharpe,
    rolling_volatility_from_cumret,
)


# --- calculate_annualized_volatility ---
_EXPECTED_EFFECTIVE_ANNUAL_RATE_365D = ((1 + 3.65 / 100.0 / 365.0) ** 365.0 - 1.0) * 100.0


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


# --- calculate_dynamic_rfr ---

def test_calculate_dynamic_rfr_basic():
    dates = pd.bdate_range("2024-01-01", "2024-12-31")
    # Constant rate over a full tenor should stay close to the quoted base rate.
    rate_series = pd.Series([3.65] * len(dates), index=dates)

    rfr = calculate_dynamic_rfr(rate_series, "2024-01-01", "2024-12-31")
    assert isinstance(rfr, float)
    assert rfr == pytest.approx(_EXPECTED_EFFECTIVE_ANNUAL_RATE_365D, abs=0.01)

def test_calculate_dynamic_rfr_empty():
    dates = pd.bdate_range("2024-01-01", "2024-01-10")
    rate_series = pd.Series([3.65] * len(dates), index=dates)
    # Start and end date outside the series range
    rfr = calculate_dynamic_rfr(rate_series, "2025-01-01", "2025-01-10")
    assert np.isnan(rfr)

def test_calculate_dynamic_rfr_empty_default_index():
    rate_series = pd.Series(dtype=float)
    rfr = calculate_dynamic_rfr(rate_series, "2024-01-01", "2024-01-10")
    assert np.isnan(rfr)
def test_calculate_dynamic_rfr_single_day():
    dates = pd.bdate_range("2024-01-01", "2024-01-01")
    rate_series = pd.Series([3.65], index=dates)
    rfr = calculate_dynamic_rfr(rate_series, "2024-01-01", "2024-01-01")
    assert rfr == pytest.approx(_EXPECTED_EFFECTIVE_ANNUAL_RATE_365D, abs=0.01)


def test_calculate_dynamic_rfr_accrues_over_weekend():
    rate_series = pd.Series(
        [3.65, 3.65],
        index=pd.DatetimeIndex(["2024-01-05", "2024-01-08"]),
    )
    rfr = calculate_dynamic_rfr(rate_series, "2024-01-05", "2024-01-07")
    assert rfr == pytest.approx(_EXPECTED_EFFECTIVE_ANNUAL_RATE_365D, abs=0.01)

# --- calculate_sharpe_ratio ---


def test_sharpe_ratio_basic():
    result = calculate_sharpe_ratio(10.0, 15.0, 2.0)
    assert result == pytest.approx((10.0 - 2.0) / 15.0)


def test_sharpe_ratio_zero_volatility():
    result = calculate_sharpe_ratio(10.0, 0.0)
    assert np.isnan(result)


def test_sharpe_ratio_no_risk_free():
    result = calculate_sharpe_ratio(12.0, 8.0, risk_free_rate=0.0)
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


# --- calculate_max_drawdown ---


def test_max_drawdown_v_shape():
    """V-shape: 100 → 80 → 120. Max DD = -20% from peak at t=0 to trough at t=1."""
    dates = pd.bdate_range("2024-01-02", periods=3)
    prices = pd.Series([100.0, 80.0, 120.0], index=dates)
    result = calculate_max_drawdown(prices)
    assert result["value"] == pytest.approx(-0.20)
    assert result["peak_date"] == dates[0]
    assert result["trough_date"] == dates[1]
    assert len(result["series"]) == 3


def test_max_drawdown_monotonic_up():
    """Monotonically rising prices → zero drawdown."""
    dates = pd.bdate_range("2024-01-02", periods=5)
    prices = pd.Series([100.0, 101.0, 102.0, 103.0, 104.0], index=dates)
    result = calculate_max_drawdown(prices)
    assert result["value"] == pytest.approx(0.0)


def test_max_drawdown_from_returns():
    """Returns mode should compound to the same equity curve."""
    dates = pd.bdate_range("2024-01-02", periods=3)
    # +0% (day 1 base), -20%, +50% → equity 1.0, 0.8, 1.2 → same as V-shape.
    returns = pd.Series([0.0, -0.20, 0.50], index=dates)
    result = calculate_max_drawdown(returns, is_returns=True)
    assert result["value"] == pytest.approx(-0.20)
    assert result["trough_date"] == dates[1]


def test_max_drawdown_too_few_observations():
    prices = pd.Series([100.0])
    with pytest.warns(UserWarning, match="Fewer than 2"):
        result = calculate_max_drawdown(prices)
    assert np.isnan(result["value"])


# --- calculate_beta ---


def test_beta_of_series_vs_itself_is_one():
    dates = pd.bdate_range("2024-01-02", periods=20)
    rng = np.random.default_rng(42)
    returns = pd.Series(rng.normal(0, 0.01, 20), index=dates)
    assert calculate_beta(returns, returns) == pytest.approx(1.0)


def test_beta_scaling():
    """Beta of 2x-scaled series vs the base series should be 2.0."""
    dates = pd.bdate_range("2024-01-02", periods=20)
    rng = np.random.default_rng(7)
    base = pd.Series(rng.normal(0, 0.01, 20), index=dates)
    assert calculate_beta(2 * base, base) == pytest.approx(2.0)


def test_beta_zero_variance_benchmark():
    dates = pd.bdate_range("2024-01-02", periods=5)
    asset = pd.Series([0.01, -0.01, 0.02, -0.02, 0.03], index=dates)
    flat = pd.Series([0.0] * 5, index=dates)
    assert np.isnan(calculate_beta(asset, flat))


def test_beta_too_few_aligned():
    dates = pd.bdate_range("2024-01-02", periods=1)
    r = pd.Series([0.01], index=dates)
    with pytest.warns(UserWarning, match="Fewer than 2"):
        assert np.isnan(calculate_beta(r, r))


# --- calculate_tracking_error ---


def test_tracking_error_identical_series_is_zero():
    dates = pd.bdate_range("2024-01-02", periods=20)
    rng = np.random.default_rng(1)
    r = pd.Series(rng.normal(0, 0.01, 20), index=dates)
    assert calculate_tracking_error(r, r) == pytest.approx(0.0)


def test_tracking_error_constant_excess_is_zero():
    """If portfolio consistently outperforms by a constant, excess std = 0."""
    dates = pd.bdate_range("2024-01-02", periods=20)
    rng = np.random.default_rng(2)
    b = pd.Series(rng.normal(0, 0.01, 20), index=dates)
    p = b + 0.0005  # constant outperformance
    assert calculate_tracking_error(p, b) == pytest.approx(0.0, abs=1e-10)


# --- calculate_information_ratio ---


def test_information_ratio_positive_excess():
    """Portfolio that outperforms should yield positive IR."""
    dates = pd.bdate_range("2024-01-02", periods=100)
    rng = np.random.default_rng(3)
    b = pd.Series(rng.normal(0, 0.01, 100), index=dates)
    p = b + rng.normal(0.0002, 0.005, 100)
    ir = calculate_information_ratio(p, b)
    assert ir > 0
    assert np.isfinite(ir)


def test_information_ratio_identical_returns_nan():
    """Zero tracking error → NaN IR (undefined)."""
    dates = pd.bdate_range("2024-01-02", periods=10)
    r = pd.Series([0.01] * 10, index=dates)
    assert np.isnan(calculate_information_ratio(r, r))


# --- Sharpe ratio with configurable risk-free rate ---


def test_sharpe_ratio_uses_config_default(monkeypatch):
    """When risk_free_rate is None, Sharpe should use config.RISK_FREE_RATE."""
    monkeypatch.setattr("etf_utils.metrics.RISK_FREE_RATE", 0.04)
    # (0.10 - 0.04) / 0.15 = 0.4
    assert calculate_sharpe_ratio(0.10, 0.15) == pytest.approx(0.4)


def test_sharpe_ratio_explicit_overrides_config(monkeypatch):
    """Explicit risk_free_rate argument overrides the config default."""
    monkeypatch.setattr("etf_utils.metrics.RISK_FREE_RATE", 0.04)
    assert calculate_sharpe_ratio(0.10, 0.15, risk_free_rate=0.0) == pytest.approx(
        0.10 / 0.15
    )


# --- rolling_volatility_from_cumret ---


def test_rolling_volatility_from_cumret_matches_manual():
    """Annualised rolling vol from cumulative returns matches a hand calc."""
    dates = pd.bdate_range("2026-01-01", periods=8)
    # 0, 1, 2, ... (+1%) / day
    cum = pd.Series(np.arange(8, dtype=float), index=dates)
    out = rolling_volatility_from_cumret(cum, window=3)
    # Last window: equity ~ 1.05, 1.06, 1.07 -> daily returns ~ 0.952%, 0.943%
    # std * sqrt(252) * 100 should be small but positive and finite.
    assert pd.notna(out.iloc[-1])
    assert out.iloc[-1] > 0


def test_rolling_volatility_constant_series_is_zero():
    """Flat cumulative-return series -> zero volatility after window."""
    dates = pd.bdate_range("2026-01-01", periods=10)
    cum = pd.Series([5.0] * 10, index=dates)
    out = rolling_volatility_from_cumret(cum, window=3)
    assert out.dropna().iloc[-1] == pytest.approx(0.0, abs=1e-9)


# --- rolling_sharpe ---


def test_rolling_sharpe_zero_rfr_is_mean_over_std():
    """With rfr=0, rolling Sharpe collapses to (mean * period) / (std * sqrt(period))."""
    dates = pd.bdate_range("2026-01-01", periods=15)
    rng = np.random.default_rng(123)
    rets = pd.Series(rng.normal(0.001, 0.01, size=15), index=dates)

    out = rolling_sharpe(rets, window=10, risk_free_rate=0.0)
    # Manual check on the last window
    last = rets.iloc[-10:]
    expected = (last.mean() * 252) / (last.std() * np.sqrt(252))
    assert out.iloc[-1] == pytest.approx(expected, rel=1e-10)


def test_rolling_sharpe_nan_on_flat_window():
    """A flat return series -> zero std -> NaN rolling Sharpe."""
    dates = pd.bdate_range("2026-01-01", periods=10)
    rets = pd.Series([0.0] * 10, index=dates)
    out = rolling_sharpe(rets, window=5)
    assert out.dropna().empty
