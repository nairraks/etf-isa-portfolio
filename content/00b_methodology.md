# Methodology & Assumptions

This page consolidates every assumption the portfolio makes, with a short
justification for each. Sceptical readers should read this first.

## Data sources and platforms

The approach keeps three layers strictly separate: ETF information, price data
and order execution.

| Layer | Source | What it provides |
|---|---|---|
| **ETF information** | [JustETF](https://www.justetf.com) | Ticker universe, TER, fund size, domicile, distribution policy, replication method, benchmark index. Scraped per region for equities & bonds; globally for precious metals & commodities. |
| **Historical prices** | [AlphaVantage](https://www.alphavantage.co) (primary) · [yfinance](https://pypi.org/project/yfinance/) (fallback) | Daily adjusted-close series driving every Sharpe, beta, drawdown, TWR and return number in the book. AlphaVantage is preferred for cleaner corporate-action handling on LSE listings. |
| **FX rates** | yfinance pairs (e.g. `GBPUSD=X`) | Disclosure only — used to surface embedded currency exposure. No FX conversion is applied to GBP-quoted `.L` tickers. |
| **Order execution** | **InvestEngine** or **Trading212** | Zero-fee UK ISA brokers where the portfolio is actually held and traded. The screener is broker-agnostic: it accepts an ETF if either broker offers it. |

No Bloomberg, no Morningstar, no paid feeds — every number in the book is
reproducible from these tools.

## Total-return proxy disclosure

Price series use **adjusted close** from AlphaVantage or yfinance. Both apply
provider-supplied dividend and split adjustments, which is the standard
DIY proxy for a total-return series but **not audit-grade**:

- Dividend timing can differ from issuer fact-sheet accruals by a few days.
- Reinvestment assumptions are the data provider's, not the fund manager's.
- Providers occasionally disagree at the last decimal on the same bar —
  mixing providers mid-backtest is **not** recommended.
- For fully audit-grade reports, cross-check against the issuer's published
  NAV history (e.g. Vanguard's `VWRL` factsheet).

## Platform availability

The portfolio is built from ETFs tradeable at **zero commission** in a UK ISA.
InvestEngine is checked first (public API, no key required); Trading212 is
checked second when API credentials are available. Either broker is fine —
the book's references are intentionally broker-agnostic.

## Screening filters (per asset class)

| Filter | Equities & Bonds | Precious Metals | Commodities | Why |
|---|---|---|---|---|
| Dividend policy | [Distributing](99_glossary.md#wrappers-product-types) | Any | Any | Distributing gives cash for rebalancing; metal/commodity ETCs rarely pay yields. |
| Size | ≥ £100M | ≥ £100M | ≥ £100M | Liquidity threshold — smaller funds can close or have wide spreads. |
| [TER](99_glossary.md#costs) | < 0.50% | < 0.60% | < 0.60% | Keeps the annual cost drag below the long-run index risk premium. |
| [Beta](99_glossary.md#risk-metrics) vs benchmark | ≥ 0.89 | n/a | ≥ 1.0 | Filters out funds that don't actually track the asset class. 0.89 ≈ 11% tracking slack, calibrated empirically. |
| Platform | Available on InvestEngine **or** Trading212 | " | " | Must be buyable in a zero-fee UK ISA. |

## Sharpe-based weighting

Within each asset class, surviving ETFs are ranked by a weighted composite
[Sharpe ratio](99_glossary.md#risk-metrics):

- **50%** weight on 1-year Sharpe
- **30%** weight on 3-year Sharpe
- **20%** weight on 5-year Sharpe

The composite is converted to an adjustment factor on the scale
**0.6 → 1.48** (poor → excellent) by linear interpolation. 1.48 ≈ 148% of the
target weight — chosen so a top-decile fund gets materially more capital
without dominating. 0.6 keeps a floor allocation for weaker funds so
diversification is preserved rather than collapsed to one winner.

### Sensitivity ranges

Each asset class has a different intra-class Sharpe sensitivity:

- **Equities**: ±0.10 — broad market funds have tight Sharpe clusters.
- **Bonds**: ±0.25 — bond Sharpes are lower and more dispersed.
- **Precious metals & commodities**: ±0.15 — between the two extremes.

These are set by inspection of the empirical Sharpe distributions, not
theoretical — a DIY calibration, not an institutional one.

## TER, OCF, and adjusted-close prices

JustETF exposes **TER** (Total Expense Ratio). For UCITS ETFs the regulatory
**OCF** (Ongoing Charges Figure) is effectively the same number — both
exclude transaction costs, spread, stamp duty and FX. Expect a difference
< 1 bp in practice. The book uses "TER" throughout for consistency with the
data source.

### Why TER is NOT subtracted from price returns

The TER reduces the fund's NAV daily, and the ETF's market price is tightly
arbitraged to NAV, so an **adjusted-close price series already embeds the
TER drag**. The price return *is* the net return after fund costs.

This pipeline takes price series from AlphaVantage (primary) and yfinance
(fallback); both are adjusted-close at the ETF ticker level. Therefore:

- **Subtracting `ter / 252` from a price-derived return series would
  double-count costs** — the TWR shown in the book is already net-of-TER.
- TER is used **only for screening** (e.g. "TER < 0.50%") and for the
  cost-disclosure column in the portfolio table.

### When manual fee subtraction *would* be correct

If you ever swap in a **raw index series** (e.g. MSCI World index level rather
than VEVE.L price) or a synthetic strategy backtest, that series is gross of
fees and TER must be modelled explicitly. None of the book's current
notebooks do this.

### What's still missing

TER is a useful *first-order* approximation of fund cost, but the rigorous
metric is **tracking difference** = ETF total return − index total return.
Tracking difference captures TER plus securities lending, sampling drag, tax
withholding and rebalancing frictions — the true cost of ownership.
Tracking-difference analysis is listed under [Future Work](#future-work).

Reported net-of-TER returns also do not include platform fees (£0 on
InvestEngine and Trading212 today), bid-ask spread, stamp duty (most ETFs
exempt) or slippage — so they remain an upper bound on real investor
take-home, but they are not double-counting TER on top.

## FX boundary

All selected ETFs are LSE-listed (ticker suffix `.L`) and quoted in GBP or
GBX (pence). **No FX conversion is applied** because:

- The fund issuer handles FX translation of the underlying holdings inside
  the NAV.
- Price series on `.L` listings are already in GBP from the investor's
  perspective.

What is **not** stripped out is the **embedded currency exposure** of
unhedged funds: a `VEVE.L` holding has ~60% USD exposure under the hood, and
sterling movements against the dollar flow through to reported GBP returns.
This is a feature of unhedged investing, not a bug; the book acknowledges
but does not neutralise it.

## Risk-free rate

Sharpe ratios use an annualised risk-free rate. The live performance-tracking
chapter additionally overlays **SONIA** (Sterling Overnight Index Average)
compounded daily to provide a cash-yield benchmark per tenor — so the
excess-return view reflects the actual UK base-rate opportunity cost rather
than a flat number.

## Rebalancing

The book's default is **calendar
[rebalancing](99_glossary.md#pipeline-terms)** on the start of each UK tax
year (6 April), driven by the fresh annual ISA allowance. Performance is
reported as **[Time-Weighted Return (TWR)](99_glossary.md#return-metrics)**,
which chains sub-period returns across every rebalance so the result reflects
the strategy, not the contribution timing.

### Blended benchmark — two variants

The portfolio's TWR is compared against a blended benchmark built from the
portfolio's own fixed target weights. There are two mathematically distinct
ways to turn a fixed-weight basket into a daily return series:

- **No-rebalance variant** — the true buy-and-forget counterfactual. Each
  component is bought on day 0 at its target weight and never touched;
  weights drift as prices diverge. **This is the variant used for the TWR
  comparison throughout the book**, because it matches the "what if I had
  bought the basket and never rebalanced?" question the actual portfolio is
  being judged against.
- **Daily-rebalanced variant** — target weights reapplied every day and
  compounded; mathematically equivalent to rebalancing back to target at the
  end of every business day. This is what many published "60/40" style
  indices report. Kept available for future multi-benchmark reporting but is
  not the primary comparator, because a daily-rebalanced index is materially
  harder for a real portfolio to beat than an untouched basket.

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

## Future work

Deliberately deferred to a later pass — listed here so the gap is visible.

- **XIRR (money-weighted return)** — complements TWR with the investor's
  actual cash-flow-weighted return.
- **Sortino ratio** — Sharpe with downside deviation only; penalises losses
  rather than all volatility.
- **Calmar ratio** — return ÷ max drawdown; a drawdown-aware risk metric.
- **Factor-based attribution** — decomposes returns into value / growth /
  size / momentum exposures (Fama–French).
- **Tracking difference vs index** — ETF total return − benchmark *index*
  total return. The rigorous measure of fund efficiency that supersedes
  comparing TER alone.
- **Rolling / sensitivity analysis** — rolling 3-year Sharpe, weight
  sensitivity, start-date robustness.
