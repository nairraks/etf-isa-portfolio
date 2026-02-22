# DIY ETF ISA Portfolio Guide

A practical guide to building a systematic, low-cost ETF portfolio in a UK ISA account, targeting 10% real annualised returns.

## What This Is

This book documents a data-driven approach to ETF investing using publicly available tools:

- **JustETF** for ETF universe data (via the `justetf-scraping` library)
- **yfinance** for historical price data (free, no API key needed)
- **InvestEngine** as the ISA platform (zero-fee ETF investing in the UK)

## Investment Approach

The portfolio targets **distributing (income) UCITS ETFs** with a 90/10 equity/bond split, weighted by a composite Sharpe ratio score:

- 50% weight on 1-year risk-adjusted return
- 30% weight on 3-year risk-adjusted return
- 20% weight on 5-year risk-adjusted return

ETFs are ranked per region, with the top performer(s) selected to maintain broad geographic diversification.

## Quick Start

```bash
git clone https://github.com/nairraks/etf-isa-portfolio
cd etf-isa-portfolio
uv sync
cp .env.example .env  # edit if using AlphaVantage
```

Then run notebooks in order:

1. `notebooks/01_data_collection.ipynb` — scrape ETF universe from JustETF
2. `notebooks/02_etf_screening.ipynb` — filter and rank ETFs by risk-adjusted metrics
3. `notebooks/03_portfolio_construction.ipynb` — construct the weighted portfolio
4. `notebooks/04_performance_tracking.ipynb` — track YTD performance vs benchmarks

## Chapters

```{tableofcontents}
```

---

> **Disclaimer**: This is personal research, not financial advice. Past performance does not guarantee future results. Always do your own due diligence before investing.
