import pandas as pd
import numpy as np
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

if __name__ == "__main__":
    test_twr_chaining()
    test_buy_and_hold()
