# For Newcomers: The 5-Minute Primer

New to investing? This one page is all you need before the rest of the book
makes sense. Nothing here is financial advice — just definitions.

## What is an ETF?

An **Exchange-Traded Fund (ETF)** is a single fund that holds many stocks,
bonds, or commodities, and trades on a stock exchange like a share. Buying one
unit of a global equity ETF like Vanguard FTSE All-World (`VWRL`) gives you
fractional exposure to ~3,600 companies across 47 countries in a single trade.

Think of it as a ready-made basket: instead of picking individual stocks, you
buy the whole market.

## What is a UCITS ETF?

**UCITS** (Undertakings for Collective Investment in Transferable Securities)
is an EU regulatory framework with strict rules on diversification,
transparency and liquidity. Almost every ETF available to UK retail investors
is a UCITS ETF — the label is a safety standard, not a brand.

## What is an ISA?

An **Individual Savings Account (ISA)** is a UK tax wrapper that shields
investments from income tax and capital gains tax. The allowance is
**£20,000 per tax year** (as of 2025/26; verify the current figure at
[gov.uk](https://www.gov.uk/individual-savings-accounts)).

A **Stocks & Shares ISA** lets you hold ETFs inside the wrapper — dividends
and capital gains accumulate tax-free while the wrapper stays open.

See [ISA Tax Context](98_isa_tax_context.md) for a slightly fuller reference.

## Distributing vs Accumulating

- **Distributing ETF**: pays dividends out to your account as cash (you can
  reinvest or withdraw).
- **Accumulating ETF**: reinvests dividends inside the fund — the unit price
  just rises.

Both are valid. This book's equity and bond picks are **distributing** (for
income/flexibility); the commodity and precious-metals picks can be
accumulating because they don't pay meaningful yields.

## TER / OCF

The **Total Expense Ratio (TER)** — also called the **Ongoing Charges Figure
(OCF)** — is the annual percentage the fund manager deducts from the fund's
assets to pay management and operating costs. 0.07% is cheap; 0.50% is the
upper end of what this book considers acceptable. TER and OCF are effectively
the same number for UCITS ETFs.

## What this book does

Scrapes the UK ETF universe from [JustETF](https://www.justetf.com), filters
it by size / cost / quality / broker availability, ranks the survivors by
risk-adjusted returns, and produces a systematic portfolio across four asset
classes (equities, bonds, precious metals, commodities).

You can run the same code, edit the parameters, and build your own.

## Where the data comes from

Three tools, three jobs — listed here so you're not surprised later:

- **[JustETF](https://www.justetf.com)** — for *information about ETFs*:
  ticker, TER, fund size, whether it's distributing, which index it tracks.
- **[AlphaVantage](https://www.alphavantage.co)** — for *historical price
  data* (the numbers behind every Sharpe ratio, drawdown and return chart).
  A [yfinance](https://pypi.org/project/yfinance/) fallback is available if
  you'd rather not sign up for a free AlphaVantage key.
- **InvestEngine** or **Trading212** — for *actually buying the ETFs* inside
  a UK Stocks & Shares ISA. Both are zero-fee for ETF trading.

The [Methodology](00b_methodology.md) page has the full table.

## Glossary

Every technical term used later in the book is defined in the
[Glossary](99_glossary.md). Refer to it as you go.
