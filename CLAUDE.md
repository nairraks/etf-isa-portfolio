# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A Jupyter Book documenting a systematic DIY ETF portfolio. Scrapes ETF data from JustETF, screens and ranks by risk-adjusted metrics, constructs a weighted portfolio, and tracks performance. ETFs focus on distributing (income-generating) UCITS ETFs available on a UK zero-fee ISA platform — the screener (`check_platform()`) checks InvestEngine first, then falls back to Trading212.

## Commands

```bash
# Install dependencies (uses uv, not pip)
uv sync

# Run tests (117 unit tests across 8 files — fast, no network)
uv run pytest tests/ -v

# End-to-end pipeline smoke tests (opt-in; executes every cell of
# notebooks 01-05 against live data providers — takes several minutes).
# Catches regressions that unit tests miss (e.g. KeyError on screened frames).
uv run pytest -m pipeline
uv run pytest -m pipeline --pipeline-fast   # skip nb01 (JustETF scrape)
uv run pytest -m pipeline -k screening      # single notebook

# Build the Jupyter Book
uv run jupyter-book build .

# Quick import check
uv run python -c "from etf_utils.data_provider import DataProvider; print('OK')"

# Verify DB layer
uv run python -c "from etf_utils.database import init_db; init_db(); print('DB OK')"
```

Book output goes to `_build/html/`. Execution is currently `off` (set to `cache` once pipeline is stable).

## Directory Structure

```
etf-isa-portfolio/
├── _config.yml / _toc.yml      # Jupyter Book config (must be at root)
├── pyproject.toml               # uv project config
├── index.md                     # Book landing page
├── .env / .env.example          # Data provider config
│
├── notebooks/                   # Chapter notebooks (executed in order)
│   ├── 01_data_collection.ipynb        # Scrapes equity, bonds, preciousMetals, commodities
│   ├── 02_etf_screening.ipynb          # Screens all 4 asset classes, writes to DB
│   ├── 03_portfolio_construction.ipynb # 4-class weights, versioning, DB save
│   ├── 04_performance_tracking.ipynb   # Live multi-tenor TWR/MWR from DB + IE statements
│   └── 05_backtesting.ipynb            # Historical backtest (FY25) + 2025-vs-2026 counterfactual
│
├── data/
│   ├── raw/                     # JustETF scrape outputs (justetf_class-*.csv)
│   │                            #   equity/bonds: per-region CSV files
│   │                            #   preciousMetals/commodities: _global.csv
│   ├── intermediate/            # summary_*.csv backups (source of truth is DB)
│   ├── output/                  # final_portfolio.csv backup + final_portfolio_25.csv
│   ├── etf_portfolio.db         # SQLite database (all intermediate + portfolio data)
│   └── config/                  # etf.json, etf_tickers.json
│
├── etf_utils/                   # Shared Python package
│   ├── config.py                # .env loading, path constants (incl. DB_PATH)
│   ├── database.py              # SQLite layer: raw/screened/portfolio CRUD + versioning
│   ├── data_provider.py         # yfinance/AlphaVantage abstraction
│   ├── data_io.py               # CSV helpers + DB delegates for save/load
│   ├── metrics.py               # Sharpe ratio, volatility, returns, PnL
│   └── platform_check.py        # InvestEngine availability check
│
├── tests/                       # pytest test suite
│   ├── conftest.py              # Shared fixtures
│   ├── test_config.py
│   ├── test_data_io.py
│   ├── test_data_provider.py
│   ├── test_metrics.py
│   ├── test_platform_check.py
│   ├── test_database.py         # SQLite layer tests (monkeypatched tmp DB)
│   └── test_etf_analysis.py     # Integration tests + 4-class weight tests
│
├── archive/                     # Legacy notebooks (not in book)
│   ├── curation.ipynb
│   └── extras_dont_check_in_code.ipynb
│
└── .github/workflows/
    └── deploy-book.yml          # Build & deploy to GitHub Pages
```

## Pipeline Flow

```
01_data_collection → data/raw/*.csv + raw_etf_data table
                   → 02_etf_screening → screened_etfs table + summary_*.csv backups
                   → 03_portfolio_construction → portfolios table (year=2026)
                                               + final_portfolio.csv backup
                   → 04_performance_tracking (live multi-tenor P&L from DB + IE statements)
                   → 05_backtesting         (FY25 actual + 2025-vs-2026 counterfactual)
```

## etf_utils Module Index

| Module | Key exports |
|--------|------------|
| `config.py` | `DATA_RAW`, `DATA_INTERMEDIATE`, `DATA_OUTPUT`, `DATA_CONFIG`, `DB_PATH`, `PROJECT_ROOT`, `DATA_PROVIDER` |
| `database.py` | `save_raw_etf_data()`, `load_raw_etf_data()`, `save_screened_etfs()`, `load_screened_etfs()`, `save_portfolio()`, `load_portfolio()`, `lock_portfolio()`, `list_portfolio_versions()`, `seed_2025_portfolio()`, `PortfolioLockedError` |
| `data_provider.py` | `DataProvider` — unified class: `get_historical_prices()`, `get_fx_rate()`, `get_latest_price()`, `get_benchmark_period_return()` |
| `data_io.py` | `load_raw_etf_data()`, `save_intermediate()`, `load_intermediate()`, `save_output()`, `load_output()`, `load_config()`, filename parsers — intermediate/output functions delegate to DB |
| `metrics.py` | `calculate_annualized_volatility()`, `calculate_sharpe_ratio()`, `interpolate_adjustment_factor()`, `calculate_period_metrics()`, `calculate_daily_pnl()` |
| `platform_check.py` | `check_etf_availability()` — queries InvestEngine API |

## SQLite Database (`data/etf_portfolio.db`)

Three tables, all written via `pandas.to_sql` / `read_sql`:

| Table | Key columns | Description |
|-------|-------------|-------------|
| `raw_etf_data` | `asset_class`, `region_category`, `scraped_at` | Raw JustETF scrape data |
| `screened_etfs` | `portfolio_year`, `asset_class`, `screened_at` | Filtered/ranked ETFs per year |
| `portfolios` | `portfolio_year`, `created_at` | Final portfolio weights + investments |
| `portfolio_meta` | `year`, `is_locked`, `locked_at` | Version lock metadata |

**Versioning**: `save_portfolio(df, year=2026)` raises `PortfolioLockedError` if `is_locked=1`. Call `lock_portfolio(year)` to freeze a year permanently. `seed_2025_portfolio()` imports the existing CSV as year=2025 locked (idempotent).

## Portfolio Versioning

- **Year 2025** (locked): 2-asset-class portfolio (equity/bonds). Seeded from `final_portfolio.csv` / `final_portfolio_25.csv` by `seed_2025_portfolio()` called in notebook 03 setup.
- **Year 2026** (mutable): 4-asset-class portfolio. Overwritten on each notebook 03 run until explicitly locked via `lock_portfolio(2026)`.

## Data Provider Config

Default: **yfinance** (free, no API key). Set in `.env`:

```
DATA_PROVIDER=yfinance          # or alphavantage
ALPHAVANTAGE_API_KEY=your_key   # only needed for alphavantage
```

Tickers are stored bare (e.g. `VEVE`). `DataProvider` appends `.L` (yfinance) or `.LON` (AlphaVantage) automatically.

## Weight Scoring Model

**Asset class allocation (2026):** 65% Equities / 10% Bonds / 5% Precious Metals / 10% Commodities

**Benchmarks:**
- Equities: VEVE.L
- Bonds: SAAA.L
- Precious Metals: SGLN.L (iShares Physical Gold ETC)
- Commodities: CMOP.L (Invesco Bloomberg Commodity — broad: ~30% energy, ~20% agri, metals)

**Intra-asset Sharpe sensitivity:**
- Equities: ±0.1
- Bonds: ±0.25
- Precious Metals: ±0.15
- Commodities: ±0.15

Sharpe ratio adjustment factors: 0.6 (poor) → 1.48 (excellent) across all asset classes.

**Scraping:** equity/bonds scraped per country/currency; preciousMetals/commodities scraped once globally (single `_global.csv`). Pure energy/agriculture ETCs (CRUD, AIGA etc.) are not listed on InvestEngine; broad commodity ETCs (CMOP, COMM, COMX, ENCG) are available and selected instead.

**Distributing filter:** equity/bonds require `dividends == 'Distributing'`; preciousMetals/commodities allow accumulating ETCs.

**InvestEngine API:** uses `v0.31`. Availability check does exact ticker match (not fuzzy length check).

ETFs ranked by weighted composite of risk-adjusted returns:
- 5-year return/risk: 20%
- 3-year return/risk: 30%
- 1-year return/risk: 50%

## Deployment

GitHub Actions (`.github/workflows/deploy-book.yml`) builds and deploys to GitHub Pages on push to `main`. Served at `nairraks.github.io/etf-isa-portfolio`.

## Dependencies

Managed via `pyproject.toml` with `uv`. Key dependencies:
- `justetf-scraping` from `nairraks/justetf-scraping` fork (not upstream `druzsan`)
- `yfinance` for price data
- `jupyter-book` for documentation build
- `python-dotenv` for `.env` config
