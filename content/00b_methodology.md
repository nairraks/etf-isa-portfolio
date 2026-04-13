# Methodology & Assumptions

This page consolidates every assumption the pipeline makes, with a short
justification for each. Sceptical readers should read this first.

## Data sources and platforms

The book uses three clearly separated layers — ETF information, price data,
and order execution — each served by a different tool. The landing page has
a short summary; this table is the authoritative reference.

| Layer | Source | Role | Notes |
|---|---|---|---|
| **ETF information** | [JustETF](https://www.justetf.com) via the `justetf-scraping` fork | Ticker universe, TER, fund size, domicile, distribution policy, replication method, benchmark index | Scraped per region for equities & bonds; global for precious metals & commodities. The single source of truth for "what ETFs exist and what are their attributes". |
| **Historical prices (primary)** | [AlphaVantage](https://www.alphavantage.co) | Daily adjusted-close series used for Sharpe, beta, drawdown, TWR, and every numerical result in the book | **Preferred** data source. Cleaner corporate-action handling on `.LON` (LSE) listings than the free alternatives. Requires `ALPHAVANTAGE_API_KEY` in `.env`. Activate with `DATA_PROVIDER=alphavantage`. |
| **Historical prices (fallback)** | [yfinance](https://pypi.org/project/yfinance/) | Same role as above, but free and key-less | Exists so readers can run the notebooks without signing up to AlphaVantage. Results can differ at the last-decimal level (corporate-action timing, split/dividend adjustments). Activate with `DATA_PROVIDER=yfinance`. |
| **FX rates** | yfinance pairs (e.g. `GBPUSD=X`) | Disclosure only | Used to surface embedded FX exposure in the tracking notebook; no conversion is applied to selected `.L` tickers — see "FX boundary". |
| **Order execution** | **InvestEngine** or **Trading212** | Actual UK ISA account where portfolio is held and traded | Both are zero-fee for ETF trading. `etf_utils.platform_check.check_platform()` queries InvestEngine first, then Trading212 (requires `TRADING212_API_KEY` / `TRADING212_API_SECRET`). The screener is broker-agnostic. |

No Bloomberg, no Morningstar, no paid data feeds — the pipeline is fully
reproducible from these tools.

## Total-return proxy disclosure

Price series use adjusted close — AlphaVantage's `TIME_SERIES_DAILY_ADJUSTED`
endpoint (primary) or yfinance with `auto_adjust=True` (fallback). Both
apply provider-supplied dividend and split adjustments. This is the standard
DIY proxy for a total-return series, but it is **not** audit-grade:

- Dividend timing can differ from issuer fact-sheet accruals by a few days.
- Reinvestment assumptions are the data provider's, not the fund manager's.
- AlphaVantage and yfinance occasionally disagree at the last decimal place
  on the same bar — switching providers mid-backtest is **not** recommended.
- For fully audit-grade reports, cross-check against the issuer's published
  NAV history (e.g. Vanguard's `VWRL` factsheet).

## Platform availability

The portfolio is built from ETFs tradeable at zero commission in a UK ISA.
The screening helper `etf_utils.platform_check.check_platform()` checks two
brokers in order:

1. **InvestEngine** (public API, no key required).
2. **Trading212** (requires `TRADING212_API_KEY` and `TRADING212_API_SECRET`
   environment variables; silently skipped if either is missing).

Either broker is fine; both are free for ETF trading. The book's references
are intentionally broker-agnostic.

## Screening filters (per asset class)

| Filter | Equities & Bonds | Precious Metals | Commodities | Why |
|---|---|---|---|---|
| Dividend policy | Distributing | Any | Any | Distributing gives cash for rebalancing; ETCs for metals/commodities rarely pay yields. |
| Size | ≥ £100M | ≥ £100M | ≥ £100M | Liquidity threshold — smaller funds can close or have wide spreads. |
| TER | < 0.50% | < 0.60% | < 0.60% | Keeps the annual cost drag below the long-run index risk premium. |
| Beta vs benchmark | ≥ 0.89 | n/a | ≥ 1.0 | Filters out funds that don't actually track the asset class (e.g. factor tilts, narrow sub-sectors). 0.89 = 11% tracking slack, calibrated empirically. |
| Platform | Available on InvestEngine **or** Trading212 | " | " | Must be buyable in a zero-fee UK ISA. |

## Sharpe-based weighting

Within each asset class, surviving ETFs are ranked by a weighted composite
Sharpe ratio:

- **50%** weight on 1-year Sharpe
- **30%** weight on 3-year Sharpe
- **20%** weight on 5-year Sharpe

The composite is converted to an adjustment factor on the scale
**0.6 → 1.48** (poor → excellent) via linear interpolation between calibration
breakpoints. 1.48 ≈ 148% of the target weight — chosen so a top-decile fund
gets materially more capital without dominating. 0.6 ≈ 60% — a weak fund
still gets a floor allocation, not zero, to keep diversification.

### Sensitivity ranges

Each asset class has a different intra-class Sharpe sensitivity:

- **Equities**: ±0.1 — broad market funds have tight Sharpe clusters.
- **Bonds**: ±0.25 — bond Sharpes are lower and more dispersed.
- **Precious metals & commodities**: ±0.15 — between the two extremes.

These are set by inspection of the empirical Sharpe distributions, not
theoretical — a DIY calibration, not an institutional one.

## TER vs OCF

JustETF exposes **TER** (Total Expense Ratio). For UCITS ETFs, the regulatory
**OCF** (Ongoing Charges Figure) is effectively the same number — both
exclude transaction costs, spread, stamp duty, and FX. Expect a difference
< 1 bp in practice.

This book uses "TER" for consistency with the data source. Net returns apply
a daily drag of `ter / 252`. Neither TER nor OCF captures trading costs or
platform fees, so reported net returns remain an upper bound on investor
take-home.

## FX boundary

All selected ETFs are LSE-listed (ticker suffix `.L`) and quoted in GBP or
GBX (pence). The `DataProvider` pipeline does **no FX conversion**. This is
correct because:

- The fund issuer handles FX translation of the underlying holdings inside
  the NAV.
- Price series on `.L` listings are already in GBP from the investor's
  perspective.

What the pipeline does NOT strip out is the **embedded currency exposure**
of unhedged funds: a `VEVE.L` holding has ~60% USD exposure under the hood,
and sterling movements against the dollar flow through to reported GBP
returns. This is a feature of unhedged investing, not a bug; the book
acknowledges but does not neutralise it. If a non-`.L` ticker is ever passed
to the provider, it emits a runtime warning.

## Risk-free rate

The Sharpe ratio uses the `RISK_FREE_RATE` environment variable (default
`0.0`). In a rising-rate environment, setting this to the 3-month gilt
rate (e.g. `RISK_FREE_RATE=0.04` for 4%) materially changes rankings —
especially for bonds. Configure it in `.env` before running the notebooks.

## Rebalancing

The book's default is **calendar rebalancing** at the start of each UK tax
year (6 April), driven by the new annual ISA allowance. Notebook 04 parses
actual InvestEngine trading statements to compute the **Time-Weighted Return
(TWR)**, which chains sub-period returns across every rebalance so the
result reflects the strategy, not the contribution timing.

## Backtest limitations

- **Post-inception only**: each ETF's history starts at its launch date, so
  multi-asset backtests are effectively left-censored.
- **Survivorship**: closed/merged funds are not in the current JustETF
  export — survivorship bias is not corrected.
- **No slippage / spread**: fills assumed at closing price.
- **Market regime**: the bulk of the equity history is a post-2009 bull
  market; drawdown and volatility estimates should be treated as optimistic.

## Future Work

Deliberately deferred to a later pass — listed here so the gap is visible:

- **XIRR (money-weighted return)**: complements TWR with the investor's
  actual return including contribution timing. Needs `pyxirr` + a cleaner
  cashflow schema.
- **Sortino ratio**: Sharpe with downside deviation only — penalises losses
  rather than all volatility.
- **Calmar ratio**: return ÷ max drawdown — a drawdown-aware risk metric.
- **Factor-based attribution**: decomposes returns into value / growth /
  size / momentum exposures (Fama–French). Requires a factor-returns data
  source beyond JustETF.
- **Rolling / sensitivity analysis**: rolling 3y Sharpe, weight sensitivity,
  start-date robustness. Planned as the Robustness appendix.
