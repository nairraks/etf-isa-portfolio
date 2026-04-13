# Glossary

One-line definitions of every term used in the book. Cross-linked from the
notebooks and the methodology page.

## Wrappers & product types

- **ETF** — Exchange-Traded Fund. A basket of securities (shares, bonds,
  commodities) that trades on an exchange like a single share.
- **ETC** — Exchange-Traded Commodity. An ETF-like wrapper specifically for
  physical commodities (gold, silver) or commodity index exposure.
- **UCITS** — EU regulatory standard that UK-available ETFs must meet.
  Enforces diversification, transparency and liquidity rules.
- **ISA** — Individual Savings Account. UK tax wrapper that shields
  dividends and capital gains from tax. See [ISA Tax Context](98_isa_tax_context.md).
- **Distributing** — ETF that pays its dividends out to your account as cash.
- **Accumulating** — ETF that reinvests its dividends inside the fund.
- **Hedged** — share class that neutralises FX movements vs a target currency
  (e.g. "GBP-hedged"). Costs a small amount in fees and lost upside.

## Costs

- **TER** — Total Expense Ratio. The fund's annual running cost as a
  percentage of assets. Effectively the same number as OCF for UCITS ETFs.
- **OCF** — Ongoing Charges Figure. The UCITS-regulated disclosure of annual
  fund running costs. Usually identical to TER (< 1 bp difference).

## Return metrics

- **CAGR** — Compound Annual Growth Rate. The constant annual rate that
  takes you from a starting value to an ending value over *n* years.
- **TWR** — Time-Weighted Return. Compounded period returns, chained across
  every contribution/withdrawal so the result reflects the *strategy*, not
  the contribution timing. Used throughout this book.

## Risk metrics

- **Volatility** — annualised standard deviation of daily returns. The
  standard "how bumpy" measure.
- **Sharpe ratio** — (annual return − risk-free rate) ÷ annual volatility.
  Return per unit of total risk. Higher is better.
- **Beta** — Cov(asset, benchmark) ÷ Var(benchmark). A beta of 1.0 means the
  asset moves 1:1 with the benchmark on average.
- **Tracking Error** — annualised standard deviation of (portfolio − benchmark)
  returns. How tightly a portfolio follows its benchmark day-to-day.
- **Information Ratio** — annualised excess return ÷ tracking error. Active
  return per unit of active risk. Higher = more consistent outperformance.
- **Max Drawdown** — the worst peak-to-trough decline in the equity curve
  over a given window. Worst-case backward-looking loss, in percent.

## Pipeline terms

- **Benchmark (single-ETF)** — one representative index ETF used to judge an
  asset class (e.g. `VEVE.L` for developed-world equities).
- **Blended benchmark** — a weighted combination of single-ETF benchmarks
  matching the portfolio's asset-class mix. The correct comparator for a
  multi-asset portfolio.
- **Rebalance** — bringing actual weights back to target weights, usually
  calendar- or threshold-driven.
- **Survivorship bias** — overestimating historical returns by only looking
  at funds that still exist today.

## Future metrics (not yet in the book)

These are defined here so readers can recognise them elsewhere; they are
explicitly deferred (see Methodology → Future Work).

- **XIRR / MWR** — Money-Weighted Return. The IRR of your actual cash
  flows; answers "was my investor experience good?" rather than "was the
  strategy good?" (which is TWR).
- **Sortino ratio** — Sharpe but with downside deviation only — penalises
  losses without penalising upside volatility.
- **Calmar ratio** — annualised return ÷ |max drawdown|. A drawdown-aware
  risk-adjusted return.
- **Factor attribution** — decomposes returns into value / growth / size /
  momentum factor exposures (Fama–French style).
