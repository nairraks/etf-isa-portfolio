# DIY ETF ISA Portfolio Guide

A practical guide to building a systematic, low-cost ETF portfolio in a UK ISA account.

```{admonition} New here?
:class: tip

Start with [For Newcomers](content/00a_for_newcomers.md) for a 5-minute
primer on ETFs, ISAs, and the terminology used throughout the book.
Every technical term is defined in the [Glossary](content/99_glossary.md);
every assumption is spelled out in [Methodology & Assumptions](content/00b_methodology.md).
```

## What This Is

A data-driven approach to ETF investing built on three clearly-separated
tools: **JustETF** for ETF information, **AlphaVantage** for historical price
data, and **InvestEngine or Trading212** for actual order execution inside a
UK ISA. See the [Data Sources & Platforms](#data-sources-and-platforms)
section below for the full breakdown.

## Data Sources and Platforms

Three distinct layers — don't conflate them:

| Layer | Tool | What it provides |
|---|---|---|
| **ETF information** | [JustETF](https://www.justetf.com) via the `justetf-scraping` fork | Ticker universe, TER, fund size, domicile, distribution policy, replication method, benchmark index |
| **Historical prices (all numbers)** | [AlphaVantage](https://www.alphavantage.co) (primary); [yfinance](https://pypi.org/project/yfinance/) (fallback) | Daily adjusted-close series used for Sharpe, beta, drawdown, TWR and every numerical result reported in the notebooks |
| **Order execution** | **InvestEngine or Trading212** | The actual UK ISA account used to buy and hold the selected ETFs |

**Which source drives the numbers?** **AlphaVantage.** Every quantitative
figure in the book is computed from AlphaVantage's adjusted-close series —
it handles corporate actions more consistently for LSE listings than the
free alternatives. A yfinance code path exists as a no-API-key fallback for
quick exploration (toggle via `DATA_PROVIDER=yfinance` in `.env`), but the
book's reported numbers come from AlphaVantage. Get a free key at
<https://www.alphavantage.co/support/#api-key>.

**JustETF is strictly for ETF attributes**, not prices. TER, fund size,
distribution policy and every screening filter input originate from
JustETF. The `justetf-scraping` library is a [fork from
`nairraks`](https://github.com/nairraks/justetf-scraping) (not the upstream
`druzsan`).

**InvestEngine or Trading212 are execution-only**, and the screener is
broker-agnostic: `check_platform()` in `etf_utils/platform_check.py`
queries InvestEngine first, then falls back to Trading212 if you've set
`TRADING212_API_KEY` and `TRADING212_API_SECRET` in `.env`. Both are
zero-fee for ETF trading in a UK ISA. The final `platform` column in the
portfolio table records which broker was matched for each ticker.

No Bloomberg, no Morningstar, no paid feeds — every number in the book is
reproducible from the three tools above.

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
│  ✓ Beta ≥ 1 vs. 2025 benchmark        ✓ On InvestEngine or Trading212       │
│  ✓ On InvestEngine or Trading212      ✓ Overlap-aware: prefer platinum &     │
│                                         palladium (0% in BCOM index) over   │
│                                         silver (4.49%) and gold (14.29%)    │
│                                       ✓ Metal diversity: one ETC per metal  │
│                                                                              │
│  Commodities:                                                                │
│  ✓ Size > £100M  ✓ TER < 0.60%  ✓ Not hedged                               │
│  ✓ Beta ≥ 1 vs. 2025 CMOP benchmark                                         │
│  ✓ On InvestEngine or Trading212 (keeps broad diversified ETCs only)        │
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

```{tableofcontents}
```

## Quick Start

```bash
git clone https://github.com/nairraks/etf-isa-portfolio
cd etf-isa-portfolio
uv sync
cp .env.example .env  # add your AlphaVantage API key (free)
```

Then run the notebooks in order (1 → 4) as described above. A free
AlphaVantage key is the default; if you'd rather skip the signup, set
`DATA_PROVIDER=yfinance` in `.env` to use the free fallback.

---

> **Disclaimer**
>
> **This is NOT investment advice.** The content in this book is for educational and personal research purposes only. The author is not a financial adviser and nothing here constitutes a recommendation to buy, sell, or hold any security.
>
> - **You can lose money investing in financial markets.** The value of investments and the income from them can go down as well as up.
> - **Past performance does not guarantee future results.** Historical returns shown in this book are no indication of what you will earn.
> - **Do your own research.** Always consult a qualified, regulated financial adviser before making investment decisions.
> - **The author accepts no liability** for any losses arising from the use of information in this book.
