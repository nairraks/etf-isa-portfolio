# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A Jupyter Book that documents a systematic DIY ETF portfolio targeting 10% real annualised returns. The book scrapes ETF data from JustETF, screens and ranks ETFs by risk-adjusted metrics, constructs a weighted portfolio, and tracks performance. ETFs focus on distributing (income-generating) UCITS ETFs available on InvestEngine (UK platform).

## Commands

### Install dependencies
```bash
pip install -r requirements.txt
```

The `justetf-scraping` dependency is installed directly from GitHub. The repo-level `.venv` is at `../.venv` (parent directory).

### Build the Jupyter Book
```bash
# Windows
build.bat

# Cross-platform
python -m jupyter_book build .
```

The book output goes to `_build/html/`. Notebooks are auto-executed on each build (`execute_notebooks: auto`, timeout 300s).

### Run tests
```bash
python -m pytest test_etf_analysis.py
# or
python -m unittest test_etf_analysis.py
```

## Architecture

### Pipeline (Jupyter Book chapters in order)

| Notebook | Purpose |
|---|---|
| `01_data_collection.ipynb` | Defines investment universe (GDP + MSCI classification), scrapes JustETF for equity/bond ETFs by region, checks InvestEngine availability |
| `02_etf_screening.ipynb` | Filters distributing ETFs, verifies platform availability, ranks by TER and risk-adjusted returns (1/3/5-year Sharpe ratios) |
| `03_portfolio_construction.ipynb` | Allocates 90% equities / 10% bonds, applies Sharpe-ratio-based weight adjustments, outputs `final_portfolio.csv` |
| `04_performance_tracking.ipynb` | Tracks YTD performance, calculates annualised volatility and Sharpe ratios vs benchmarks |
| `05_rebalancing.ipynb` | Defines rebalancing strategy |

`curation.ipynb` is a standalone all-in-one notebook with the full pipeline (precursor to the split chapters). `extras_dont_check_in_code.ipynb` is a scratch notebook not intended for check-in.

### Data files

JustETF scrape outputs follow the pattern:
```
justetf_class-{equity|bonds}_{market}_{region}.csv
```
e.g. `justetf_class-equity_developed_americasanduk.csv`

Benchmark data:
```
benchmark_distributing_df*.csv
```

Portfolio configuration:
- `etf.json` — manually curated ETF list grouped by region/category (used during curation)
- `etf_tickers.json` — final selected ETF tickers with region and yield-category labels (`Beta` / `High Yield`)

Pipeline outputs: `summary_equities.csv`, `summary_bonds.csv`, `summary_all.csv`, `final_portfolio.csv`

### Weight scoring model

ETFs are ranked by a weighted composite of risk-adjusted returns:
- 5-year return/risk: 20%
- 3-year return/risk: 30%
- 1-year return/risk: 50%

Sharpe ratio adjustment factors range from 0.6 (poor) to 1.48 (excellent), with equities having ±0.1 sensitivity and bonds ±0.25.

### Book structure

`_toc.yml` defines the chapter order. `_config.yml` sets Jupyter Book options including MyST extensions (`dollarmath`, `colon_fence`, `substitution`, `tasklist`). The book is published to GitHub Pages from the `main` branch.
