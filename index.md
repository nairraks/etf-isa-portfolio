# DIY ETF ISA Portfolio Guide

A practical guide to building a systematic, low-cost ETF portfolio in a UK ISA account, targeting 10% real annualised returns.

## What This Is

This book documents a data-driven approach to ETF investing using publicly available tools:

- **JustETF** for ETF universe data (via the `justetf-scraping` library)
- **yfinance** for historical price data (free, no API key needed)
- **InvestEngine** as the ISA platform (zero-fee ETF investing in the UK)

## Investment Approach

The portfolio targets **distributing (income) UCITS ETFs** across five asset classes, weighted by a composite Sharpe ratio score:

| Asset Class | Target Weight |
|---|---|
| Equities | 65% |
| Bonds | 10% |
| Precious Metals | 5% |
| Energy | 5% |
| Agriculture | 5% |

ETFs are ranked per region using a weighted composite of risk-adjusted returns:
- 50% weight on 1-year risk-adjusted return
- 30% weight on 3-year risk-adjusted return
- 20% weight on 5-year risk-adjusted return

Weights are then adjusted up or down based on each ETF's Sharpe ratio relative to its asset-class benchmark, and normalised to sum to 100%.

## How the Portfolio Is Built

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  STEP 1 — DATA COLLECTION  (notebook 01)                                     │
│  "Cast the net — gather every ETF available"                                 │
│                                                                              │
│  JustETF website                                                             │
│       ├──▶  Equities         (683 UK · 142 APAC · 88 EMEA · 94 Emerging)    │
│       ├──▶  Bonds            (537 UK · 424 EMEA · 30 Emerging)              │
│       ├──▶  Precious Metals  (52 ETCs globally)                              │
│       └──▶  Commodities      (121 ETCs globally → Energy + Agriculture)     │
│                                                                              │
│  Output: raw CSV files saved to data/raw/                                   │
└──────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│  STEP 2 — ETF SCREENING  (notebook 02)                                       │
│  "Pick only the best — filter out the noise"                                 │
│                                                                              │
│  Equities & Bonds:                    Precious Metals / Energy / Agriculture:│
│  ✓ Distributing (pays dividends)      ✓ Size > £100M                        │
│  ✓ Size > £100M                       ✓ TER (cost) < 0.60%                  │
│  ✓ TER < 0.50%                        ✓ Not currency-hedged                 │
│  ✓ Available on InvestEngine          ✓ Available on InvestEngine            │
│  ✓ Beta ≥ 1 vs. 2025 benchmark        Energy → Oil/Crude/Gas keyword filter │
│                                       Agri   → Wheat/Corn/Soy keyword filter│
│                                                                              │
│  2025 benchmarks: VEVE · SAAA · SGLN · CRUD · AIGA                         │
│                                                                              │
│  Output: ~18 shortlisted ETFs saved to database                             │
└──────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│  STEP 3 — PORTFOLIO CONSTRUCTION  (notebook 03)                              │
│  "Decide how much money goes where"                                          │
│                                                                              │
│  ① Start with strategic target weights:                                      │
│     Equities  65% ──────────────────────────────────────────────────────    │
│     Bonds     10% ──────                                                     │
│     Gold       5% ───                                                        │
│     Energy     5% ───                                                        │
│     Agri       5% ───                                                        │
│                                                                              │
│  ② Adjust weights based on Sharpe ratio vs. benchmark:                       │
│     Better than benchmark → weight UP   (up to ×1.48)                       │
│     Worse than benchmark  → weight DOWN (down to ×0.60)                     │
│                                                                              │
│  ③ Normalise adjusted weights to sum to 100%                                 │
│                                                                              │
│  ④ Reduce weight of volatile assets (volatility adjustment)                  │
│                                                                              │
│  Output: final_portfolio.csv  (e.g. £20,000 split across ~18 ETFs)         │
└──────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│  STEP 4 — PERFORMANCE TRACKING  (notebook 04)                                │
│  "Watch how your investment grows over time"                                 │
│                                                                              │
│  • Fetch latest prices for all held ETFs                                     │
│  • Calculate daily profit & loss (P&L) per position                         │
│  • Compare total return vs. benchmark (VEVE)                                │
│  • Track cumulative return since portfolio start                             │
│                                                                              │
│  Goal: 10% real (inflation-adjusted) annualised return                      │
└──────────────────────────────────────────────────────────────────────────────┘
```

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
