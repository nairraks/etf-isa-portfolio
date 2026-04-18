import numpy as np
import pandas as pd
import pytest
from etf_utils.backtesting import (
    Backtester,
    dynamic_portfolio_return,
    parse_investengine_statement,
    period_metrics_table,
    rolling_avg_pairwise_corr,
    rolling_constituent_beta,
)

def test_twr_chaining():
    # Jan 1 2026 = Thu, Jan 2 = Fri, Jan 5 = Mon, Jan 6 = Tue
    # We'll use 4 days: Jan 1 (Start), Jan 2 (Wait), Jan 5 (Rebalance), Jan 6 (End)
    dates = pd.to_datetime(["2026-01-01", "2026-01-02", "2026-01-05", "2026-01-06"])
    
    # A: 10, 10, 11, 12.1
    # B: 10, 10,  9,  9
    prices = {
        "A": pd.DataFrame({"close": [10.0, 10.0, 11.0, 12.1]}, index=dates),
        "B": pd.DataFrame({"close": [10.0, 10.0, 9.0, 9.0]}, index=dates)
    }
    
    trades = pd.DataFrame([
        {"ticker": "A", "trade_date": "2026-01-01", "signed_qty": 10.0, "signed_value": 100.0, "type": "Buy"},
        {"ticker": "B", "trade_date": "2026-01-01", "signed_qty": 10.0, "signed_value": 100.0, "type": "Buy"},
        # Day Jan 5: Sell B at 9, Buy A at 11
        {"ticker": "B", "trade_date": "2026-01-05", "signed_qty": -10.0, "signed_value": -90.0, "type": "Sell"},
        {"ticker": "A", "trade_date": "2026-01-05", "signed_qty": 8.1818, "signed_value": 90.0, "type": "Buy"}
    ])
    
    bt = Backtester(prices, "2026-01-01", "2026-01-06")
    # Force use of dates for test simplicity
    bt.all_dates = dates 
    
    twr_series = bt.run_twr_series(trades)
    
    final_return = twr_series.iloc[-1]
    print(f"Final TWR Return: {final_return:.2f}%")
    assert abs(final_return - 10.0) < 0.1
    print("TWR Chaining Test Passed!")

def test_buy_and_hold():
    dates = pd.to_datetime(["2026-01-01", "2026-01-02", "2026-01-05"])
    prices = {"A": pd.DataFrame({"close": [10.0, 12.5, 15.0]}, index=dates)}
    
    bt = Backtester(prices, "2026-01-01", "2026-01-05")
    bt.all_dates = dates
    bnh_series = bt.run_buy_and_hold_series({"A": 10.0})
    
    final_return = bnh_series.iloc[-1]
    print(f"Final B&H Return: {final_return:.2f}%")
    assert abs(final_return - 50.0) < 0.1
    print("B&H Test Passed!")

def test_blended_benchmark_single_weight_equals_ticker_return():
    """100% weight on one ticker => both methods match that ticker's B&H return.

    With zero cross-asset allocation there is nothing to rebalance, so the
    no-rebalance and daily-rebalanced variants must agree.
    """
    dates = pd.to_datetime(["2026-01-01", "2026-01-02", "2026-01-05"])
    prices = {
        "A": pd.DataFrame({"close": [10.0, 12.5, 15.0]}, index=dates),
        "B": pd.DataFrame({"close": [10.0, 10.0, 10.0]}, index=dates),
    }
    bt = Backtester(prices, "2026-01-01", "2026-01-05")
    bt.all_dates = dates

    no_reb = bt.build_blended_benchmark_no_rebalance({"A": 1.0, "B": 0.0})
    rebal = bt.build_blended_benchmark_rebalanced({"A": 1.0, "B": 0.0})

    # A goes 10 -> 15 = +50%; both methods should match.
    assert abs(no_reb.iloc[-1] - 50.0) < 0.1
    assert abs(rebal.iloc[-1] - 50.0) < 0.1


def test_blended_benchmark_no_rebalance_50_50_hand_computed():
    """No-rebalance 50/50: weighted sum of growth factors = exactly +5.0%.

    Prices:
        A: 10.0 -> 11.0 -> 12.0   (growth factors 1.0, 1.1, 1.2)
        B: 10.0 ->  9.5 ->  9.0   (growth factors 1.0, 0.95, 0.9)

    A true buy-and-forget basket never rebalances, so::

        V(t)/V(0) = 0.5 * (P_A(t)/P_A(0)) + 0.5 * (P_B(t)/P_B(0))
        V(1)/V(0) = 0.5*1.10 + 0.5*0.95 = 1.025      -> +2.5%
        V(2)/V(0) = 0.5*1.20 + 0.5*0.90 = 1.050      -> +5.0%

    Exact to floating point. Any drift here indicates the implementation
    has silently reintroduced daily rebalancing.
    """
    dates = pd.to_datetime(["2026-01-01", "2026-01-02", "2026-01-05"])
    prices = {
        "A": pd.DataFrame({"close": [10.0, 11.0, 12.0]}, index=dates),
        "B": pd.DataFrame({"close": [10.0, 9.5, 9.0]}, index=dates),
    }
    bt = Backtester(prices, "2026-01-01", "2026-01-05")
    bt.all_dates = dates

    blended = bt.build_blended_benchmark_no_rebalance({"A": 0.5, "B": 0.5})

    assert blended.iloc[0] == pytest.approx(0.0, abs=1e-9)
    assert blended.iloc[1] == pytest.approx(2.5, abs=1e-9)
    assert blended.iloc[-1] == pytest.approx(5.0, abs=1e-9)


def test_blended_benchmark_rebalanced_50_50_hand_computed():
    """Daily-rebalanced 50/50: compounded weighted daily returns.

    Using the same price series as the no-rebalance test::

        A daily returns: [NaN->0, +10.000%, +9.0909%]
        B daily returns: [NaN->0,  -5.000%, -5.2632%]

        port_daily(1) = 0.5*(+0.10)   + 0.5*(-0.0500) = +0.02500
        port_daily(2) = 0.5*(+0.0909) + 0.5*(-0.0526) = +0.01914

        V(1)/V(0) = 1.02500
        V(2)/V(0) = 1.02500 * 1.01914 ~ 1.04462
        final %   ~ +4.462

    Crucially, this is < the no-rebalance +5.0% finish on the same prices:
    that gap is the "volatility drag" of daily rebalancing. Small over two
    days, but systematic and compounding over years.
    """
    dates = pd.to_datetime(["2026-01-01", "2026-01-02", "2026-01-05"])
    prices = {
        "A": pd.DataFrame({"close": [10.0, 11.0, 12.0]}, index=dates),
        "B": pd.DataFrame({"close": [10.0, 9.5, 9.0]}, index=dates),
    }
    bt = Backtester(prices, "2026-01-01", "2026-01-05")
    bt.all_dates = dates

    blended = bt.build_blended_benchmark_rebalanced({"A": 0.5, "B": 0.5})

    assert blended.iloc[0] == pytest.approx(0.0, abs=1e-9)
    assert blended.iloc[1] == pytest.approx(2.5, abs=1e-9)
    expected_day2 = (1.025 * (1 + 0.5 * (12 / 11 - 1) + 0.5 * (9 / 9.5 - 1)) - 1) * 100
    assert blended.iloc[-1] == pytest.approx(expected_day2, abs=1e-9)
    # Must be strictly less than the no-rebalance +5.0% for these prices.
    assert blended.iloc[-1] < 5.0


def test_blended_benchmark_methods_diverge_on_volatile_paths():
    """Asymmetric paths: both methods hand-computable, and they must differ.

    Two assets, 50/50 weights:
        A: 1.00 -> 1.20 -> 1.20    (+20%, then flat)
        B: 1.00 -> 1.00 -> 0.80    (flat, then -20%)

    No-rebalance:
        V(0) = 1.00
        V(1) = 0.5*1.20 + 0.5*1.00 = 1.10   -> +10%
        V(2) = 0.5*1.20 + 0.5*0.80 = 1.00   ->  0% exactly

    Daily-rebalanced:
        port_daily(1) = 0.5*0.20 + 0.5*0.00   = +0.10   -> 1.10
        port_daily(2) = 0.5*0.00 + 0.5*-0.20  = -0.10   -> 0.99
        final % = (0.99 - 1)*100 = -1.0 exactly

    A 1.0-percentage-point gap in two days — the classic volatility-drag
    signature that distinguishes the two definitions. A regression that
    collapses them would make this test fail.
    """
    dates = pd.to_datetime(["2026-01-01", "2026-01-02", "2026-01-05"])
    prices = {
        "A": pd.DataFrame({"close": [1.00, 1.20, 1.20]}, index=dates),
        "B": pd.DataFrame({"close": [1.00, 1.00, 0.80]}, index=dates),
    }
    bt = Backtester(prices, "2026-01-01", "2026-01-05")
    bt.all_dates = dates

    no_reb = bt.build_blended_benchmark_no_rebalance({"A": 0.5, "B": 0.5})
    rebal = bt.build_blended_benchmark_rebalanced({"A": 0.5, "B": 0.5})

    # Both start at 0%, agree at day 1 (only A has moved), diverge at day 2.
    assert no_reb.iloc[0] == pytest.approx(0.0, abs=1e-9)
    assert rebal.iloc[0] == pytest.approx(0.0, abs=1e-9)
    assert no_reb.iloc[1] == pytest.approx(10.0, abs=1e-9)
    assert rebal.iloc[1] == pytest.approx(10.0, abs=1e-9)

    assert no_reb.iloc[-1] == pytest.approx(0.0, abs=1e-9)
    assert rebal.iloc[-1] == pytest.approx(-1.0, abs=1e-9)
    # Rebalanced strictly below no-rebalance on this path (vol drag).
    assert rebal.iloc[-1] < no_reb.iloc[-1]


def test_blended_benchmark_three_asset_hand_computed():
    """Three-asset 50/30/20 dummy with exact hand-computed finals.

        A: 10 -> 12 -> 14  (weight 0.5)   growth factors 1.0, 1.2, 1.4
        B: 10 -> 11 ->  9  (weight 0.3)   growth factors 1.0, 1.1, 0.9
        C: 10 -> 10 -> 10  (weight 0.2)   growth factors 1.0, 1.0, 1.0

    No-rebalance final:
        V(2)/V(0) = 0.5*1.4 + 0.3*0.9 + 0.2*1.0
                  = 0.70 + 0.27 + 0.20 = 1.17
        final %   = +17.0 (exact)

    Daily-rebalanced final:
        port_daily(1) = 0.5*(12/10-1) + 0.3*(11/10-1) + 0.2*0 = 0.13
        port_daily(2) = 0.5*(14/12-1) + 0.3*( 9/11-1) + 0.2*0
                      = 0.5*0.16667 + 0.3*(-0.18182)
                      = 0.08333 - 0.05454 = 0.02879
        V(2)/V(0) = 1.13 * 1.02879 ~ 1.16253
        final %   ~ +16.253

    Pins both methods to their exact closed-form values and asserts
    the expected ~0.75 pp gap.
    """
    dates = pd.to_datetime(["2026-01-01", "2026-01-02", "2026-01-05"])
    prices = {
        "A": pd.DataFrame({"close": [10.0, 12.0, 14.0]}, index=dates),
        "B": pd.DataFrame({"close": [10.0, 11.0, 9.0]}, index=dates),
        "C": pd.DataFrame({"close": [10.0, 10.0, 10.0]}, index=dates),
    }
    bt = Backtester(prices, "2026-01-01", "2026-01-05")
    bt.all_dates = dates
    weights = {"A": 0.5, "B": 0.3, "C": 0.2}

    no_reb = bt.build_blended_benchmark_no_rebalance(weights)
    rebal = bt.build_blended_benchmark_rebalanced(weights)

    assert no_reb.iloc[-1] == pytest.approx(17.0, abs=1e-9)

    expected_rebal = (1.13 * (1 + 0.5 * (14 / 12 - 1) + 0.3 * (9 / 11 - 1)) - 1) * 100
    assert rebal.iloc[-1] == pytest.approx(expected_rebal, abs=1e-9)
    # No-rebalance beats rebalanced on this path (vol drag goes this way here).
    assert no_reb.iloc[-1] > rebal.iloc[-1]


def test_parse_investengine_statement_roundtrip(tmp_path):
    """Parser extracts ticker/date/price and sets signed_qty sign from Buy/Sell."""
    csv_body = (
        "Header line 1\n"
        "Header line 2\n"
        "Vanguard EUR Corporate Bond / ISIN IE00BZ163G84,Buy,10.0,\u00a350.00,\u00a3500.00,"
        "12/05/25 14:16:49,14/05/25,None\n"
        "iShares Core UK Gilts / ISIN IE00B1FZSB30,Sell,5.0,\u00a320.00,\u00a3100.00,"
        "13/05/25 09:00:00,15/05/25,None\n"
        "Unknown Fund / ISIN XX9999999999,Buy,1.0,\u00a31.00,\u00a31.00,"
        "14/05/25 10:00:00,16/05/25,None\n"
    )
    path = tmp_path / "trades.csv"
    path.write_text(csv_body, encoding="utf-8")

    trades = parse_investengine_statement(path)

    # Unknown ISIN row is dropped (ticker is NaN after map).
    assert len(trades) == 2
    assert set(trades["ticker"]) == {"VECP", "IGLT"}

    buy = trades[trades["ticker"] == "VECP"].iloc[0]
    assert buy["signed_qty"] == pytest.approx(10.0)
    assert buy["signed_value"] == pytest.approx(500.0)
    assert buy["trade_date"] == pd.Timestamp("2025-05-12")

    sell = trades[trades["ticker"] == "IGLT"].iloc[0]
    assert sell["signed_qty"] == pytest.approx(-5.0)
    assert sell["signed_value"] == pytest.approx(-100.0)


def test_parse_investengine_statement_custom_isin_map(tmp_path):
    """Passing a custom ISIN map overrides the packaged default."""
    csv_body = (
        "Header line 1\n"
        "Header line 2\n"
        "Synthetic Fund / ISIN ZZ0000000001,Buy,1.0,\u00a31.0,\u00a31.0,"
        "01/01/26 00:00:00,01/01/26,None\n"
    )
    path = tmp_path / "trades.csv"
    path.write_text(csv_body, encoding="utf-8")
    trades = parse_investengine_statement(path, isin_map={"ZZ0000000001": "SYNZ"})
    assert list(trades["ticker"]) == ["SYNZ"]


def test_dynamic_portfolio_return_renormalises_weights():
    """When one ticker is NaN, its weight is redistributed to the rest."""
    dates = pd.to_datetime(["2026-01-02", "2026-01-05", "2026-01-06"])
    rets = pd.DataFrame({
        "A": [0.01, 0.02, 0.03],
        "B": [np.nan, 0.04, 0.05],
    }, index=dates)
    weights = {"A": 0.6, "B": 0.4}

    port = dynamic_portfolio_return(rets, weights)

    # Day 0: only A valid -> weight renormalised to 1.0 on A
    assert port.iloc[0] == pytest.approx(0.01)
    # Day 1: both valid -> 0.6*0.02 + 0.4*0.04 = 0.028
    assert port.iloc[1] == pytest.approx(0.6 * 0.02 + 0.4 * 0.04)


def test_dynamic_portfolio_return_ignores_missing_tickers():
    """Weights for tickers absent from the returns DF are silently dropped."""
    dates = pd.to_datetime(["2026-01-02", "2026-01-05"])
    rets = pd.DataFrame({"A": [0.05, 0.1]}, index=dates)
    port = dynamic_portfolio_return(rets, {"A": 0.5, "NOT_THERE": 0.5})
    # Only A remains -> fully weighted
    assert port.iloc[0] == pytest.approx(0.05)
    assert port.iloc[1] == pytest.approx(0.1)


def test_rolling_avg_pairwise_corr_constant_series_equals_one():
    """Two perfectly correlated series -> average pairwise corr is 1.0."""
    dates = pd.bdate_range("2026-01-01", periods=10)
    rets = pd.DataFrame({
        "A": np.linspace(0.01, 0.05, 10),
        "B": np.linspace(0.02, 0.06, 10),  # same linear relationship
    }, index=dates)
    corr = rolling_avg_pairwise_corr(rets, window=5)
    # After window fills, corr should be ~1
    assert corr.dropna().iloc[-1] == pytest.approx(1.0, abs=1e-6)


def test_rolling_constituent_beta_self_equals_one():
    """Beta of a single-asset portfolio on itself is 1.0."""
    dates = pd.bdate_range("2026-01-01", periods=15)
    rng = np.random.default_rng(42)
    series = pd.Series(rng.normal(0, 0.01, size=15), index=dates)
    rets = pd.DataFrame({"A": series})
    beta = rolling_constituent_beta(rets, series, window=10)
    assert beta.dropna().iloc[-1] == pytest.approx(1.0, abs=1e-6)


def test_period_metrics_table_structure():
    """Table has one row per consecutive timeline pair and exact-return values."""
    dates = pd.bdate_range("2026-01-01", periods=20)
    ret_a = pd.Series([0.01] * 20, index=dates)  # +1%/day
    ret_b = pd.Series([0.02] * 20, index=dates)  # +2%/day
    timeline = {
        "Start": dates[0].strftime("%Y-%m-%d"),
        "Mid":   dates[9].strftime("%Y-%m-%d"),
        "End":   dates[-1].strftime("%Y-%m-%d"),
    }
    df = period_metrics_table(ret_a, ret_b, timeline, label_a="A", label_b="B")
    assert len(df) == 2
    assert "Return A (%)" in df.columns
    assert "Return B (%)" in df.columns
    # B's return > A's return in every period
    assert (df["Return B (%)"] > df["Return A (%)"]).all()


if __name__ == "__main__":
    test_twr_chaining()
    test_buy_and_hold()
    test_blended_benchmark_single_weight_equals_ticker_return()
    test_blended_benchmark_no_rebalance_50_50_hand_computed()
    test_blended_benchmark_rebalanced_50_50_hand_computed()
    test_blended_benchmark_methods_diverge_on_volatile_paths()
    test_blended_benchmark_three_asset_hand_computed()
