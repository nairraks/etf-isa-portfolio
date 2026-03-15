"""Tests for etf_utils.database SQLite layer."""

import pandas as pd
import pytest

import etf_utils.database as db_module
from etf_utils.database import (
    PortfolioLockedError,
    init_db,
    list_portfolio_versions,
    load_portfolio,
    load_raw_etf_data,
    load_screened_etfs,
    lock_portfolio,
    save_portfolio,
    save_raw_etf_data,
    save_screened_etfs,
    seed_2025_portfolio,
)


@pytest.fixture(autouse=True)
def _tmp_db(tmp_path, monkeypatch):
    """Redirect DB_PATH to a temp file and reset the init flag for each test."""
    tmp_db = tmp_path / "test.db"
    monkeypatch.setattr(db_module, "DB_PATH", tmp_db)
    monkeypatch.setattr(db_module, "_db_initialized", False)
    yield tmp_db
    monkeypatch.setattr(db_module, "_db_initialized", False)


@pytest.fixture
def sample_raw_df():
    return pd.DataFrame({
        "ticker": ["VEVE", "SAAA"],
        "name": ["ETF A", "ETF B"],
        "ter": [0.12, 0.08],
        "size": [500, 300],
    })


@pytest.fixture
def sample_screened_df():
    return pd.DataFrame({
        "ticker": ["AUAD", "PRIJ"],
        "name": ["ETF Equity 1", "ETF Equity 2"],
        "asset_class": ["equity", "equity"],
        "ter": [0.40, 0.05],
        "last_year_volatility": [12.0, 10.5],
    })


@pytest.fixture
def sample_portfolio_df():
    return pd.DataFrame({
        "ticker": ["AUAD", "PRIJ", "IGLT"],
        "name": ["ETF Equity 1", "ETF Equity 2", "ETF Bond 1"],
        "asset_class": ["equity", "equity", "bonds"],
        "final_cash_weights": [40.0, 35.0, 25.0],
        "investment": [8000.0, 7000.0, 5000.0],
    })


# ---------------------------------------------------------------------------
# init_db
# ---------------------------------------------------------------------------

def test_init_db_creates_tables(_tmp_db):
    """init_db() guarantees portfolio_meta; data tables are created lazily on first write."""
    import sqlite3
    init_db()
    conn = sqlite3.connect(_tmp_db)
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    conn.close()
    assert "portfolio_meta" in tables


# ---------------------------------------------------------------------------
# raw_etf_data
# ---------------------------------------------------------------------------

def test_save_and_load_raw_etf_data(sample_raw_df):
    save_raw_etf_data(sample_raw_df, asset_class="equity", region_category="Developed_APAC")
    result = load_raw_etf_data(asset_class="equity", region_category="Developed_APAC")
    assert len(result) == len(sample_raw_df)
    assert set(sample_raw_df["ticker"]) == set(result["ticker"])


def test_save_raw_etf_data_replaces_existing(sample_raw_df):
    save_raw_etf_data(sample_raw_df, "equity", "Developed_APAC")
    new_df = pd.DataFrame({"ticker": ["NEWETF"], "name": ["New ETF"], "ter": [0.1], "size": [200]})
    save_raw_etf_data(new_df, "equity", "Developed_APAC")
    result = load_raw_etf_data("equity", "Developed_APAC")
    assert len(result) == 1
    assert result["ticker"].iloc[0] == "NEWETF"


def test_load_raw_etf_data_no_filter_returns_all(sample_raw_df):
    save_raw_etf_data(sample_raw_df, "equity", "Developed_APAC")
    save_raw_etf_data(sample_raw_df, "bonds", "Developed_EMEA")
    result = load_raw_etf_data()
    assert len(result) == len(sample_raw_df) * 2


# ---------------------------------------------------------------------------
# screened_etfs
# ---------------------------------------------------------------------------

def test_save_and_load_screened_etfs(sample_screened_df):
    save_screened_etfs(sample_screened_df, "equity", portfolio_year=2026)
    result = load_screened_etfs("equity", portfolio_year=2026)
    assert len(result) == len(sample_screened_df)
    assert set(result["ticker"]) == set(sample_screened_df["ticker"])


def test_screened_etfs_isolated_by_year(sample_screened_df):
    save_screened_etfs(sample_screened_df, "equity", portfolio_year=2025)
    save_screened_etfs(sample_screened_df.head(1), "equity", portfolio_year=2026)
    assert len(load_screened_etfs("equity", portfolio_year=2025)) == 2
    assert len(load_screened_etfs("equity", portfolio_year=2026)) == 1


def test_load_screened_etfs_all_asset_classes(sample_screened_df):
    bonds_df = sample_screened_df.copy()
    bonds_df["asset_class"] = "bonds"
    save_screened_etfs(sample_screened_df, "equity", portfolio_year=2026)
    save_screened_etfs(bonds_df, "bonds", portfolio_year=2026)
    result = load_screened_etfs(portfolio_year=2026)
    assert len(result) == len(sample_screened_df) * 2


# ---------------------------------------------------------------------------
# portfolios / versioning
# ---------------------------------------------------------------------------

def test_save_and_load_portfolio(sample_portfolio_df):
    save_portfolio(sample_portfolio_df, year=2026)
    result = load_portfolio(year=2026)
    assert len(result) == len(sample_portfolio_df)
    assert set(result["ticker"]) == set(sample_portfolio_df["ticker"])


def test_save_portfolio_overwrites_unlocked(sample_portfolio_df):
    save_portfolio(sample_portfolio_df, year=2026)
    smaller_df = sample_portfolio_df.head(1)
    save_portfolio(smaller_df, year=2026)
    result = load_portfolio(year=2026)
    assert len(result) == 1


def test_load_portfolio_empty_when_missing():
    result = load_portfolio(year=9999)
    assert result.empty


def test_lock_portfolio_prevents_overwrite(sample_portfolio_df):
    save_portfolio(sample_portfolio_df, year=2025)
    lock_portfolio(2025, notes="FY 2025-26 final")
    with pytest.raises(PortfolioLockedError):
        save_portfolio(sample_portfolio_df, year=2025)


def test_lock_portfolio_nonexistent_raises(sample_portfolio_df):
    with pytest.raises(ValueError, match="No portfolio found"):
        lock_portfolio(9999)


def test_list_portfolio_versions(sample_portfolio_df):
    save_portfolio(sample_portfolio_df, year=2025)
    save_portfolio(sample_portfolio_df, year=2026)
    lock_portfolio(2025)
    versions = list_portfolio_versions()
    assert len(versions) == 2
    by_year = {v["year"]: v for v in versions}
    assert by_year[2025]["is_locked"] is True
    assert by_year[2026]["is_locked"] is False


# ---------------------------------------------------------------------------
# seed_2025_portfolio
# ---------------------------------------------------------------------------

def test_seed_2025_portfolio_idempotent(tmp_path, monkeypatch, sample_portfolio_df):
    # Provide a source CSV
    csv_path = tmp_path / "final_portfolio.csv"
    sample_portfolio_df.to_csv(csv_path, index=False)
    monkeypatch.setattr(db_module, "DATA_OUTPUT", tmp_path, raising=False)

    # Patch DATA_OUTPUT in database module
    import etf_utils.database as dbm
    monkeypatch.setattr(dbm, "DATA_OUTPUT", tmp_path)

    seed_2025_portfolio()
    seed_2025_portfolio()  # second call should be a no-op

    versions = list_portfolio_versions()
    assert sum(1 for v in versions if v["year"] == 2025) == 1
    assert versions[0]["is_locked"] is True


def test_seed_2025_no_csv_prints_warning(capsys, monkeypatch, tmp_path):
    import etf_utils.database as dbm
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()
    monkeypatch.setattr(dbm, "DATA_OUTPUT", empty_dir)

    seed_2025_portfolio()
    captured = capsys.readouterr()
    assert "Warning" in captured.out
