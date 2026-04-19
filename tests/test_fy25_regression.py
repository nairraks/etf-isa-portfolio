"""FY25 end-to-end numerical regression test.

Freezes the inputs (trade ledger + live price snapshot from 05-Apr-2025 →
05-Apr-2026) and asserts that the TWR / MWR / volatility / Sharpe pipeline —
the same one executed in ``notebooks/04_performance_tracking.ipynb`` — still
produces the FY25 headline numbers the book reports. A mismatch means a
regression in one of:

- ``Backtester.from_trades`` / ``Backtester.run_twr_series`` (TWR chaining)
- ``rebase_cumret`` (per-tenor rebase)
- ``calculate_sharpe_ratio`` (risk-free-rate handling)
- Or the ``parse_investengine_statement`` output schema the Backtester consumes

Fixture is rebuilt by ``tests/fixtures/build_fy25_fixture.py`` — re-run it
only if the 2025 trade ledger or locked portfolio changes.
"""
from __future__ import annotations

import pickle
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from etf_utils.backtesting import Backtester, rebase_cumret
from etf_utils.metrics import calculate_sharpe_ratio

SNAPSHOT = Path(__file__).parent / "fixtures" / "fy25_backtest_snapshot.pkl"


@pytest.fixture(scope="module")
def fy25():
    if not SNAPSHOT.exists():
        pytest.skip(
            f"FY25 snapshot not built. Run "
            f"`uv run python tests/fixtures/build_fy25_fixture.py`."
        )
    snap = pickle.loads(SNAPSHOT.read_bytes())

    trades = snap["trades"]
    first_trade = pd.to_datetime(trades["trade_date"]).min()
    bt = Backtester(snap["prices"], first_trade, snap["fy25_end"])
    master_twr = bt.run_twr_series(trades)
    tenor = rebase_cumret(master_twr.loc[: snap["fy25_end"]], snap["fy25_start"])

    ledger = (
        trades[trades["trade_date"] <= snap["fy25_end"]]
        .groupby("ticker")["signed_qty"]
        .sum()
    )
    end_val = 0.0
    for t, sh in ledger.items():
        if sh <= 0:
            continue
        px = bt.get_price(t, snap["fy25_end"])
        if px:
            end_val += sh * px

    daily = (1 + tenor / 100).pct_change().dropna()
    ann_vol = float(daily.std() * np.sqrt(252) * 100)
    n_days = (tenor.index[-1] - tenor.index[0]).days
    ann_ret = ((1 + tenor.iloc[-1] / 100) ** (365 / n_days) - 1) * 100

    return {
        "snap": snap,
        "bt": bt,
        "tenor": tenor,
        "end_val": end_val,
        "ann_vol": ann_vol,
        "ann_ret": ann_ret,
    }


def test_fy25_trade_ledger_shape(fy25):
    trades = fy25["snap"]["trades"]
    assert len(trades) == 351
    assert sorted(trades["ticker"].unique()) == [
        "AUAD", "EMCP", "HMCH", "IBZL", "IGLT", "IMIB", "LCUK", "PRIJ",
        "PRIR", "QYLP", "SLXX", "TRXG", "UC81", "VECP", "VEMT", "XDDX",
    ]


def test_fy25_rebased_window(fy25):
    """Rebased series starts at the first trade, ends at the last trading day ≤ FY25_END."""
    tenor = fy25["tenor"]
    assert len(tenor) == 235
    assert tenor.index[0] == pd.Timestamp("2025-05-12")
    assert tenor.index[-1] == pd.Timestamp("2026-04-03")
    # Rebased series anchors at 0 on the first observation.
    assert tenor.iloc[0] == pytest.approx(0.0, abs=1e-9)


def test_fy25_twr_final(fy25):
    twr_final = fy25["tenor"].iloc[-1]
    assert twr_final == pytest.approx(15.62, abs=0.01)


def test_fy25_ending_value_and_mwr(fy25):
    end_val = fy25["end_val"]
    mwr = (end_val / fy25["snap"]["fy25_deposit_gbp"] - 1) * 100
    assert end_val == pytest.approx(23_091.60, abs=0.50)
    assert mwr == pytest.approx(15.46, abs=0.01)


def test_fy25_annualised_vol(fy25):
    assert fy25["ann_vol"] == pytest.approx(9.49, abs=0.01)


def test_fy25_annualised_return(fy25):
    assert fy25["ann_ret"] == pytest.approx(17.65, abs=0.01)


@pytest.mark.parametrize(
    "rf,expected",
    [
        (0.0, 1.8602),
        (0.04, 1.8560),
    ],
)
def test_fy25_sharpe(fy25, rf, expected):
    sharpe = calculate_sharpe_ratio(
        fy25["ann_ret"], fy25["ann_vol"], risk_free_rate=rf
    )
    assert sharpe == pytest.approx(expected, abs=0.005)
