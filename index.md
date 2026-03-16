# DIY ETF ISA Portfolio Guide

A practical guide to building a systematic, low-cost ETF portfolio in a UK ISA account.

## What This Is

This book documents a data-driven approach to ETF investing using publicly available tools:

- **JustETF** for ETF universe data (via the `justetf-scraping` library)
- **yfinance** for historical price data (free, no API key needed)
- **InvestEngine** as the ISA platform (zero-fee ETF investing in the UK)

## Investment Approach

The portfolio targets **distributing (income) UCITS ETFs** across four asset classes, weighted by a composite Sharpe ratio score:

| Asset Class | Target Weight | Benchmark |
|---|---|---|
| Equities | 65% | VEVE.L (Vanguard FTSE Dev World) |
| Bonds | 10% | SAAA.L (SPDR Bloomberg 0–3Y US Agg) |
| Precious Metals | 5% | SGLN.L (iShares Physical Gold ETC) |
| Commodities | 10% | CMOP.L (Invesco Bloomberg Commodity) |

ETFs are ranked per region using a weighted composite of risk-adjusted returns:
- 50% weight on 1-year risk-adjusted return
- 30% weight on 3-year risk-adjusted return
- 20% weight on 5-year risk-adjusted return

Weights are then adjusted up or down based on each asset class's Sharpe ratio relative to its benchmark, and normalised to sum to 100%.

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
│       └──▶  Commodities      (121 ETCs globally)                            │
│                                                                              │
│  Output: raw CSV files saved to data/raw/                                   │
└──────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│  STEP 2 — ETF SCREENING  (notebook 02)                                       │
│  "Pick only the best — filter out the noise"                                 │
│                                                                              │
│  Equities & Bonds:                    Precious Metals:                       │
│  ✓ Distributing (pays dividends)      ✓ Size > £100M                        │
│  ✓ Size > £100M                       ✓ TER < 0.60%                         │
│  ✓ TER < 0.50%                        ✓ Not currency-hedged                 │
│  ✓ Beta ≥ 1 vs. 2025 benchmark        ✓ Available on InvestEngine            │
│  ✓ Available on InvestEngine          ✓ Overlap-aware: prefer platinum &     │
│                                         palladium (0% in BCOM index) over   │
│                                         silver (4.49%) and gold (14.29%)    │
│                                       ✓ Metal diversity: one ETC per metal  │
│                                                                              │
│  Commodities:                                                                │
│  ✓ Size > £100M  ✓ TER < 0.60%  ✓ Not hedged                               │
│  ✓ Beta ≥ 1 vs. 2025 CMOP benchmark                                         │
│  ✓ Available on InvestEngine (naturally keeps broad diversified ETCs only)  │
│                                                                              │
│  Output: ~14 shortlisted ETFs saved to database                             │
└──────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│  STEP 3 — PORTFOLIO CONSTRUCTION  (notebook 03)                              │
│  "Decide how much money goes where"                                          │
│                                                                              │
│  ① Start with strategic target weights:                                      │
│     Equities    65% ────────────────────────────────────────────────────    │
│     Bonds       10% ──────                                                   │
│     Gold         5% ───                                                      │
│     Commodities 10% ──────                                                   │
│                                                                              │
│  ② Adjust weights based on Sharpe ratio vs. benchmark:                       │
│     Better than benchmark → weight UP   (up to ×1.48)                       │
│     Worse than benchmark  → weight DOWN (down to ×0.60)                     │
│                                                                              │
│  ③ Normalise adjusted weights to sum to 100%                                 │
│                                                                              │
│  ④ Reduce weight of volatile assets (volatility adjustment)                  │
│                                                                              │
│  Output: final_portfolio.csv  (e.g. £20,000 split across ~14 ETFs)         │
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
│  Monitor: track total return vs. benchmarks over time                       │
└──────────────────────────────────────────────────────────────────────────────┘
```

## Browse the Notebooks

::::{grid} 2
:gutter: 3

:::{grid-item-card} 1. Data Collection
:link: notebooks/01_data_collection
:link-type: doc

Scrape the full ETF universe from JustETF across equities, bonds, precious metals, and commodities.
:::

:::{grid-item-card} 2. ETF Screening
:link: notebooks/02_etf_screening
:link-type: doc

Filter and rank ETFs by size, cost, beta, platform availability, and risk-adjusted returns.
:::

:::{grid-item-card} 3. Portfolio Construction
:link: notebooks/03_portfolio_construction
:link-type: doc

Assign weights using Sharpe-ratio adjustments and build the final portfolio allocation.
:::

:::{grid-item-card} 4. Performance Tracking
:link: notebooks/04_performance_tracking
:link-type: doc

Track YTD profit & loss and compare total return against benchmarks.
:::

::::

## Quick Start

```bash
git clone https://github.com/nairraks/etf-isa-portfolio
cd etf-isa-portfolio
uv sync
cp .env.example .env  # edit if using AlphaVantage
```

Then run the notebooks in order (1 → 4) as described above.

---

> **Disclaimer**
>
> **This is NOT investment advice.** The content in this book is for educational and personal research purposes only. The author is not a financial adviser and nothing here constitutes a recommendation to buy, sell, or hold any security.
>
> - **You can lose money investing in financial markets.** The value of investments and the income from them can go down as well as up.
> - **Past performance does not guarantee future results.** Historical returns shown in this book are no indication of what you will earn.
> - **Do your own research.** Always consult a qualified, regulated financial adviser before making investment decisions.
> - **The author accepts no liability** for any losses arising from the use of information in this book.
