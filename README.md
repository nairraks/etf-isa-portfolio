# etf-isa-portfolio

Code and Jupyter Book behind a systematic DIY ETF portfolio for a UK Stocks &
Shares ISA. The rendered book is the user-facing artefact — this README covers
how to run the code, reproduce the numbers, and contribute.

> Rendered book: <https://nairraks.github.io/etf-isa-portfolio>

## What this repository contains

| Area | Path | Purpose |
|---|---|---|
| Book source | `index.md`, `content/*.md`, `notebooks/*.ipynb`, `_config.yml`, `_toc.yml` | Jupyter Book — the reader-facing guide |
| Python package | `etf_utils/` | Shared logic (data provider, screening, metrics, backtester, DB) |
| Tests | `tests/` | pytest suite (117 unit tests + opt-in pipeline smoke tests) |
| Data | `data/raw/`, `data/intermediate/`, `data/output/`, `data/etf_portfolio.db` | Scrape outputs, CSV backups, SQLite DB |
| Deploy | `.github/workflows/deploy-book.yml` | GitHub Pages build on push to `main` |

## Quick start

```bash
git clone https://github.com/nairraks/etf-isa-portfolio
cd etf-isa-portfolio
uv sync
cp .env.example .env    # see "Environment variables" below
```

Run the pipeline in order (1 → 5):

```bash
uv run jupyter lab notebooks/
```

Build the book:

```bash
uv run jupyter-book build .
# output at _build/html/index.html
```

Book execution is currently `off` in `_config.yml` (switch to `cache` once the
pipeline is stable for your local environment).

## Environment variables

Set in `.env` (copied from `.env.example`):

| Variable | Required? | Purpose |
|---|---|---|
| `DATA_PROVIDER` | Yes | `alphavantage` (preferred) or `yfinance` (no key needed) |
| `ALPHAVANTAGE_API_KEY` | If using AlphaVantage | Free key from <https://www.alphavantage.co/support/#api-key> |
| `FRED_API_KEY` | For notebook 04 | SONIA base-rate lookups. Free key: <https://fred.stlouisfed.org/docs/api/api_key.html> |
| `RISK_FREE_RATE` | Optional | Fallback annualised rate for Sharpe (default `0.0`) |
| `TRADING212_API_KEY`, `TRADING212_API_SECRET` | Optional | Extends platform availability check beyond InvestEngine |

**Default path:** set `DATA_PROVIDER=yfinance` for a key-less quick-start; the
book's reported numbers use AlphaVantage for cleaner LSE corporate-action
handling.

## Commands

```bash
# Install / update dependencies (uv only — not pip)
uv sync

# Unit tests (fast, no network)
uv run pytest tests/ -v

# Opt-in end-to-end smoke tests (executes notebooks 01-05 against live data)
uv run pytest -m pipeline
uv run pytest -m pipeline --pipeline-fast   # skip slow JustETF scrape
uv run pytest -m pipeline -k screening      # single notebook

# Build the book
uv run jupyter-book build .

# Quick sanity checks
uv run python -c "from etf_utils.data_provider import DataProvider; print('OK')"
uv run python -c "from etf_utils.database import init_db; init_db(); print('DB OK')"
```

## Directory layout

```
etf-isa-portfolio/
├── _config.yml / _toc.yml      Jupyter Book config
├── index.md                    Book landing page
├── content/                    Markdown chapters (newcomers, methodology,
│                               ISA tax context, glossary)
├── notebooks/                  Pipeline chapters 01-05
├── etf_utils/                  Shared Python package
├── data/
│   ├── raw/                    JustETF scrape CSVs (per asset class/region)
│   ├── intermediate/           Screening backups
│   ├── output/                 Final portfolio CSV backups
│   ├── etf_portfolio.db        SQLite DB (source of truth)
│   └── config/                 etf.json, etf_tickers.json, isin_ticker_map.json
├── tests/                      pytest suite
├── scripts/                    Build-time helpers
└── .github/workflows/          CI + book deploy
```

## Pipeline flow

```
01_data_collection   → JustETF scrape → raw CSVs + raw_etf_data table
02_etf_screening     → filter + rank  → screened_etfs table + backups
03_portfolio_construction → weights → portfolios table (year=2026)
04_performance_tracking  → live multi-tenor P&L from DB + IE statements
05_backtesting       → FY25 actual + 2025-vs-2026 counterfactual
```

See the rendered book for the investment rationale and results.

## `etf_utils` package

| Module | Purpose |
|---|---|
| `config.py` | `.env` loading, path constants (`DATA_RAW`, `DB_PATH`, etc.) |
| `database.py` | SQLite CRUD: raw scrapes, screened ETFs, portfolios (with version lock) |
| `data_provider.py` | Unified `DataProvider` over yfinance / AlphaVantage |
| `data_io.py` | CSV helpers + DB delegates |
| `metrics.py` | Sharpe, volatility, returns, drawdown, P&L, beta, tracking error |
| `platform_check.py` | InvestEngine / Trading212 availability check |
| `backtesting.py` | `Backtester`, InvestEngine statement parser, blended benchmark |

## Database

`data/etf_portfolio.db` holds four tables:

| Table | Purpose |
|---|---|
| `raw_etf_data` | Raw JustETF scrape by asset class / region |
| `screened_etfs` | Filtered and ranked per portfolio year |
| `portfolios` | Final weights + investments per portfolio year |
| `portfolio_meta` | Version-lock metadata (`is_locked`, `locked_at`) |

Versioning: `save_portfolio(df, year=2026)` raises `PortfolioLockedError` when
the year is locked. Year 2025 is locked (seeded from the legacy CSV); year
2026 is mutable until you call `lock_portfolio(2026)`.

## Contributing

- Feature branches only (don't push to `main`).
- Keep `uv run pytest tests/` green.
- For notebook changes, re-run the `pipeline` smoke test before pushing.
- The book deploy workflow runs on push to `main`.

## License

See repository metadata.
