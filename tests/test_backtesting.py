import pandas as pd
from etf_utils.backtesting import Backtester

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
    """A blended benchmark with 100% weight on one ticker ≈ that ticker's B&H return."""
    dates = pd.to_datetime(["2026-01-01", "2026-01-02", "2026-01-05"])
    prices = {
        "A": pd.DataFrame({"close": [10.0, 12.5, 15.0]}, index=dates),
        "B": pd.DataFrame({"close": [10.0, 10.0, 10.0]}, index=dates),
    }
    bt = Backtester(prices, "2026-01-01", "2026-01-05")
    bt.all_dates = dates

    blended = bt.build_blended_benchmark({"A": 1.0, "B": 0.0})
    # A goes 10 -> 15 = +50%
    assert abs(blended.iloc[-1] - 50.0) < 0.1


def test_blended_benchmark_50_50_weight():
    """50/50 weighting averages the two cumulative return paths."""
    dates = pd.to_datetime(["2026-01-01", "2026-01-02", "2026-01-05"])
    prices = {
        # +20% total
        "A": pd.DataFrame({"close": [10.0, 11.0, 12.0]}, index=dates),
        # -10% total
        "B": pd.DataFrame({"close": [10.0, 9.5, 9.0]}, index=dates),
    }
    bt = Backtester(prices, "2026-01-01", "2026-01-05")
    bt.all_dates = dates

    blended = bt.build_blended_benchmark({"A": 0.5, "B": 0.5})
    # Compound blend of 50/50 daily returns: approximately the mean of the
    # two paths, but not exactly equal to the simple average of final values.
    # Sanity: result should be between -10% and +20%.
    assert -10.0 < blended.iloc[-1] < 20.0
    # And above zero because A outperforms B by more than B falls below.
    assert blended.iloc[-1] > 0.0


if __name__ == "__main__":
    test_twr_chaining()
    test_buy_and_hold()
    test_blended_benchmark_single_weight_equals_ticker_return()
    test_blended_benchmark_50_50_weight()
