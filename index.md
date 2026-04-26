# DIY ETF ISA Portfolio Guide

A practical guide to building a systematic, low-cost ETF portfolio in a UK
Stocks & Shares ISA — written for a do-it-yourself investor who wants the
*why* behind every weight, not just a ticker list.

```{admonition} New here?
:class: tip

Start with [For Newcomers](content/00a_for_newcomers.md) for a five-minute
primer on ETFs, ISAs and distributing funds. Every technical term is defined
in the [Glossary](content/99_glossary.md); every assumption is spelled out in
[Methodology & Assumptions](content/00b_methodology.md).
```

## Investment philosophy — constant-mix with annual rebalancing

This book follows a **constant-mix strategy**: set a long-term target weight
per asset class, then **rebalance back to target** at the start of every UK
tax year (6 April) when the fresh £20,000 ISA allowance becomes available.

Why constant-mix?

- **Mechanically buys low and sells high.** When equities rip, rebalancing
  trims them back to target and tops up whatever has lagged. When they
  drawdown, rebalancing buys the discount. It imposes discipline that a
  discretionary investor rarely sustains on their own.
- **Harvests the "rebalancing bonus"** from components that are *volatile but
  lowly correlated*. Precious metals and broad commodities are in the 2026
  portfolio precisely for this reason: not because they out-return equities,
  but because they zig when equities zag.
- **Cheap, tax-efficient and sleep-friendly.** One decision a year. Inside an
  ISA, sales trigger no CGT; zero-fee brokers mean no trading costs. The
  strategy is dominated by *what you don't do* — no market timing, no
  fund-picking churn.

```{admonition} Constant-mix vs drift
:class: note

A portfolio that is never touched drifts toward whatever is winning. After a
ten-year equity bull run the bond sleeve shrinks to a rounding error — exactly
when you need it most. Constant-mix prevents that silent concentration.
```

## The portfolio in one table

Target weights for the 2026 portfolio:

| Asset class | Target | Benchmark | Role |
|---|---|---|---|
| Equities | **65%** | VEVE.L | Long-run return engine |
| Bonds | **20%** | SAAA.L | Ballast + rebalancing reserve |
| Precious metals | **5%** | SGLN.L | Crisis hedge, low equity correlation |
| Commodities | **10%** | CMOP.L | Inflation hedge, diversifier |

Within each class, ETFs are ranked by a composite risk-adjusted-return score
(see [Methodology](content/00b_methodology.md#sharpe-based-weighting)) and
weights are tilted toward the better performers. Everything is
[**distributing**](content/99_glossary.md#wrappers-product-types)
[**UCITS**](content/99_glossary.md#wrappers-product-types) for the equity and bond
sleeves, so dividends arrive as cash and fund the next rebalance.

## How the portfolio is built — three steps

The book is structured around three investor decisions, supported by a
backtest that grounds them in realised data.

```
┌────────────────────────────────────────────────────────────────────┐
│  STEP 1  —  SELECTION                                              │
│  "Which ETFs even deserve a look?"                                 │
│                                                                    │
│  Start from every UCITS ETF available in the UK, then filter:      │
│    • Distributing (equities & bonds)                               │
│    • Size ≥ £100M  •  TER < 0.50–0.60%                             │
│    • Tracks its asset class (beta check)                           │
│    • Buyable on a zero-fee UK ISA broker                           │
│                                                                    │
│  Rank the survivors by a composite                                  │
│  [Sharpe ratio](content/99_glossary.md#risk-metrics)               │
│  (50% 1-yr · 30% 3-yr · 20% 5-yr).                                 │
└────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌────────────────────────────────────────────────────────────────────┐
│  STEP 2  —  PORTFOLIO CONSTRUCTION                                 │
│  "How much money goes where?"                                      │
│                                                                    │
│    ① Strategic mix: 65 / 20 / 5 / 10                                │
│    ② Tilt each ETF's weight by [Sharpe](content/99_glossary.md#risk-metrics) vs class median│
│         (×0.60 weak → ×1.48 strong)                                │
│    ③ Shrink high-volatility names                                   │
│    ④ Normalise to 100% and allocate the ISA's £20,000               │
└────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌────────────────────────────────────────────────────────────────────┐
│  STEP 3  —  PERFORMANCE TRACKING                                   │
│  "Is this actually working?"                                       │
│                                                                    │
│    • [TWR](content/99_glossary.md#return-metrics) / [MWR](content/99_glossary.md#future-metrics-not-yet-in-the-book) across three tenors (Overall · FY25 · FY26) │
│    • Rolling volatility & Sharpe vs a blended benchmark            │
│    • Holdings snapshot with per-position P&L                       │
└────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌────────────────────────────────────────────────────────────────────┐
│  BACKTEST  —  GROUND TRUTH                                         │
│  "Would this have worked over last tax year?"                      │
│                                                                    │
│  Replay the 2025 portfolio over FY25 using the real trade ledger,  │
│  then ask the counterfactual: how would the 2026 weights (with     │
│  metals + commodities added) have behaved across the same window?  │
└────────────────────────────────────────────────────────────────────┘
```

## Browse the chapters

```{tableofcontents}
```

---

> **Disclaimer — this is NOT investment advice.**
>
> The content in this book is for educational and personal-research purposes
> only. The author is not a financial adviser and nothing here constitutes a
> recommendation to buy, sell or hold any security.
>
> - **You can lose money investing.** Markets go down as well as up.
> - **Past performance does not guarantee future results.** Every backtest is
>   historical; none is a prediction.
> - **Do your own research.** Always consult a qualified, regulated financial
>   adviser before making investment decisions.
> - **The author accepts no liability** for any losses arising from the use
>   of information in this book.
