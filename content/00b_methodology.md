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

## TER, OCF, and adjusted-close prices

JustETF exposes **TER** (Total Expense Ratio). For UCITS ETFs the regulatory
**OCF** (Ongoing Charges Figure) is effectively the same number — both
exclude transaction costs, spread, stamp duty, and FX. Expect a difference
< 1 bp in practice. The book uses "TER" throughout for consistency with the
data source.

### Why we do NOT subtract TER from price returns

The TER reduces the fund's NAV daily, and the ETF's market price is tightly
arbitraged to NAV — so an **adjusted-close price series already embeds the
TER drag**. The price return *is* the net return after fund costs.

This pipeline takes price series from AlphaVantage (primary) and yfinance
(fallback). Both are adjusted-close series at the ETF ticker level. So:

- **Subtracting `ter / 252` from a price-derived return series would
  double-count costs** — and that mistake is precisely what an earlier
  iteration of `Backtester.apply_ter_drag` and the `ter_bps` parameter to
  `Backtester.build_blended_benchmark` did. Both have been removed; the
  blended benchmark is now split into two explicit variants
  (`build_blended_benchmark_no_rebalance` and
  `build_blended_benchmark_rebalanced`), neither of which applies a
  manual TER drag.
- The reported TWR for the actual portfolio and the blended benchmark are
  both already net-of-TER through this NAV-embedding mechanism.
- The TER value scraped from JustETF is therefore used **only for screening**
  (e.g. "TER < 0.50%") and for the cost-disclosure column in the portfolio
  table — never as a manual return adjustment.

### When manual fee subtraction *would* be correct

The double-counting only applies to ETF price series. If you ever swap in a
**raw index series** (e.g. MSCI World index level rather than VEVE.L price)
or a synthetic strategy backtest, that series is gross of fees and you
*would* need to model TER explicitly. None of the book's current notebooks
do this.

### What's still missing

TER is a useful *first-order* approximation of fund cost, but the rigorous
metric is **tracking difference** = ETF total return − index total return.
Tracking difference captures TER plus securities lending, sampling drag, tax
withholding and rebalancing frictions — i.e. the true cost of ownership.
Tracking-difference analysis is listed under [Future Work](#future-work) and
not yet implemented.

Reported net-of-TER returns also do not include platform fees (£0 on
InvestEngine and Trading212 today), spread, stamp duty (most ETFs are
exempt), or slippage — so they remain an upper bound on real investor
take-home, but they are not double-counting TER on top.

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

### Blended benchmark: two explicit variants

Notebook 04 compares the portfolio's TWR against a blended benchmark built
from the portfolio's own fixed target weights. There are two mathematically
distinct ways to turn a fixed-weight basket into a daily return series, and
`etf_utils.backtesting.Backtester` exposes both:

- **`build_blended_benchmark_no_rebalance(weights)`** — the true
  buy-and-forget counterfactual. Each component is bought on day 0 at its
  target weight and never touched; weights drift as prices diverge. Computed
  as a weighted sum of per-ticker growth factors:
  `V(t) / V(0) = Σ wᵢ · Pᵢ(t) / Pᵢ(0)`. **This is the variant used for the
  TWR comparison in Notebook 04**, because it matches the "what if I had
  bought the basket and never rebalanced?" question the actual portfolio is
  being judged against.
- **`build_blended_benchmark_rebalanced(weights)`** — the daily-rebalanced
  convention. Target weights are applied to each day's component returns and
  the result is compounded; mathematically equivalent to rebalancing the
  basket back to target at the end of every business day. This is what many
  published "60/40" style indices report. It is kept available for future
  multi-benchmark reporting but is **not** the primary comparator, because
  a daily-rebalanced index is materially harder for a real portfolio to beat
  than an untouched basket.

The gap between the two series is the "volatility drag" (or "rebalancing
bonus" in the opposite regime) — small over short windows, systematic over
years, and its sign depends on the components' co-movement.

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
- **Tracking difference vs index**: ETF total return − benchmark *index*
  total return. The rigorous measure of fund efficiency that supersedes
  comparing TER alone, because it bundles TER, securities lending,
  sampling drag, tax withholding and rebalancing frictions into one
  observable number. Requires raw index-level total-return series (not
  ETF-proxy series), which neither AlphaVantage nor yfinance provide
  directly for the benchmarks the book uses.
- **Rolling / sensitivity analysis**: rolling 3y Sharpe, weight sensitivity,
  start-date robustness. Planned as the Robustness appendix.
