# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A Jupyter Book documenting a systematic DIY ETF portfolio targeting 10% real annualised returns. Scrapes ETF data from JustETF, screens and ranks by risk-adjusted metrics, constructs a weighted portfolio, and tracks performance. ETFs focus on distributing (income-generating) UCITS ETFs available on InvestEngine (UK platform).

## Commands

```bash
# Install dependencies (uses uv, not pip)
uv sync

# Run tests (50 tests across 6 files)
uv run pytest tests/ -v

# Build the Jupyter Book
uv run jupyter-book build .

# Quick import check
uv run python -c "from etf_utils.data_provider import DataProvider; print('OK')"
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
│   ├── 01_data_collection.ipynb
│   ├── 02_etf_screening.ipynb
│   ├── 03_portfolio_construction.ipynb
│   └── 04_performance_tracking.ipynb
│
├── data/
│   ├── raw/                     # JustETF scrape outputs (justetf_class-*.csv)
│   ├── intermediate/            # summary_*.csv, benchmark_*.csv
│   ├── output/                  # final_portfolio.csv
│   └── config/                  # etf.json, etf_tickers.json
│
├── etf_utils/                   # Shared Python package
│   ├── config.py                # .env loading, path constants
│   ├── data_provider.py         # yfinance/AlphaVantage abstraction
│   ├── data_io.py               # CSV read/write helpers
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
│   └── test_etf_analysis.py     # Legacy integration tests
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
01_data_collection → data/raw/*.csv → 02_etf_screening → data/intermediate/summary_all.csv
→ 03_portfolio_construction → data/output/final_portfolio.csv → 04_performance_tracking
```

## etf_utils Module Index

| Module | Key exports |
|--------|------------|
| `config.py` | `DATA_RAW`, `DATA_INTERMEDIATE`, `DATA_OUTPUT`, `DATA_CONFIG`, `PROJECT_ROOT`, `DATA_PROVIDER` |
| `data_provider.py` | `DataProvider` — unified class: `get_historical_prices()`, `get_fx_rate()`, `get_latest_price()`, `get_benchmark_period_return()` |
| `data_io.py` | `load_raw_etf_data()`, `save_intermediate()`, `load_intermediate()`, `save_output()`, `load_output()`, `load_config()`, filename parsers |
| `metrics.py` | `calculate_annualized_volatility()`, `calculate_sharpe_ratio()`, `interpolate_adjustment_factor()`, `calculate_period_metrics()`, `calculate_daily_pnl()` |
| `platform_check.py` | `check_etf_availability()` — queries InvestEngine API |

## Data Provider Config

Default: **yfinance** (free, no API key). Set in `.env`:

```
DATA_PROVIDER=yfinance          # or alphavantage
ALPHAVANTAGE_API_KEY=your_key   # only needed for alphavantage
```

Tickers are stored bare (e.g. `VEVE`). `DataProvider` appends `.L` (yfinance) or `.LON` (AlphaVantage) automatically.

## Weight Scoring Model

ETFs ranked by weighted composite of risk-adjusted returns:
- 5-year return/risk: 20%
- 3-year return/risk: 30%
- 1-year return/risk: 50%

Sharpe ratio adjustment factors: 0.6 (poor) → 1.48 (excellent). Equities ±0.1 sensitivity, bonds ±0.25.

## Deployment

GitHub Actions (`.github/workflows/deploy-book.yml`) builds and deploys to GitHub Pages on push to `main`. Served at `nairraks.github.io/etf-isa-portfolio`.

## Dependencies

Managed via `pyproject.toml` with `uv`. Key dependencies:
- `justetf-scraping` from `nairraks/justetf-scraping` fork (not upstream `druzsan`)
- `yfinance` for price data
- `jupyter-book` for documentation build
- `python-dotenv` for `.env` config
