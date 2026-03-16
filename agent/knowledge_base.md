# ETF ISA Portfolio — Knowledge Base

*Extracted from notebooks 01–04. This is the sole source of truth for answering questions about this portfolio.*

---

## 1. Investment Universe (Notebook 01)

### Purpose
A systematic DIY ETF portfolio for a UK ISA account. All ETFs must be distributing (income-generating) UCITS ETFs available on the InvestEngine platform.

### Countries Covered
17 countries selected based on 2023 GDP and MSCI classification:

**Developed Markets:**
| Country | Region | Currency |
|---------|--------|----------|
| United States | AmericasandUK | USD |
| Canada | AmericasandUK | CAD |
| United Kingdom | AmericasandUK | GBP |
| Japan | APAC | JPY |
| Australia | APAC | AUD |
| Germany | EMEA | EUR |
| France | EMEA | EUR |
| Italy | EMEA | EUR |
| Spain | EMEA | EUR |
| Netherlands | EMEA | EUR |
| Switzerland | EMEA | CHF |

**Emerging Markets:**
| Country | Region | Currency |
|---------|--------|----------|
| China | APACandEMEA | CNY |
| India | APACandEMEA | INR |
| South Korea | APACandEMEA | KRW |
| Indonesia | APACandEMEA | IDR |
| Brazil | Americas | BRL |
| Mexico | Americas | MXN |

### Asset Classes
- **Equities**: Scraped from JustETF by country
- **Bonds**: Scraped from JustETF by currency of underlying instrument

### Region Categories
- `Developed_AmericasandUK` — US, Canada, UK
- `Developed_EMEA` — Germany, France, Italy, Spain, Netherlands, Switzerland
- `Developed_APAC` — Japan, Australia
- `Emerging_Americas` — Brazil, Mexico
- `Emerging_APACandEMEA` — China, India, South Korea, Indonesia

---

## 2. ETF Screening Criteria (Notebook 02)

### Equity Screening Rules
All of the following must be true:
1. **Distributing** dividends only (no accumulating ETFs — income is required)
2. **Fund size > £100M** (liquidity filter)
3. **Not hedged** (currency hedging reduces return in the long run)
4. **TER < 0.5%** (exception: IBZL at 0.74% — only Brazil ETF available on InvestEngine)
5. **Available on InvestEngine** (verified via InvestEngine API)
6. **Excluded tickers**: XUCN, LYXIB, C001, SW2CHA, XSMI, SJPD, XESD, C024 (data quality or liquidity issues)

### Equity ETF Categories
After screening, equity ETFs are split into two categories per region:

- **High Yield**: The ETF with the highest `last_year_dividends` per region category. These are selected for their income-generating potential.
- **Beta**: The ETF with beta ≥ 1.0 vs its regional benchmark AND the lowest TER (highest beta as tiebreaker). Beta is calculated as `2024 return / benchmark 2024 return`. These track or beat their regional market.

### Bond ETF Selection
Bonds are manually curated (not screened from raw data) into:
- **Govt** (Government bonds): Lower risk, lower yield
- **Corp** (Corporate bonds): Higher risk, higher yield

Bond tickers by category:
| Ticker | Name | Region | Category |
|--------|------|--------|----------|
| IGLT | iShares Core UK Gilts | Developed_AmericasandUK | Govt |
| SLXX | iShares Core GBP Corporate Bond | Developed_AmericasandUK | Corp |
| TRXG | Invesco US Treasury Bond 7-10yr | Developed_AmericasandUK | Govt |
| UC81 | UBS Bloomberg US Liquid Corporates | Developed_AmericasandUK | Corp |
| PRIR | Amundi Prime Euro Govies | Developed_EMEA | Govt |
| VECP | Vanguard EUR Corporate Bond | Developed_EMEA | Corp |
| EMCP | iShares JPMorgan USD EM Corporate Bond | Emerging_APACandEMEA | Corp |
| VEMT | Vanguard USD Emerging Markets Govt Bond | Emerging_APACandEMEA | Govt |

### Benchmarks Used for Beta Calculation (Equity)
| Region | Benchmark Ticker | Description |
|--------|-----------------|-------------|
| Developed_AmericasandUK (UK) | ISF.LON | iShares Core FTSE 100 |
| Developed_AmericasandUK (US) | SPY | SPDR S&P 500 |
| Developed_AmericasandUK (CA) | ZCN.TRT | BMO S&P/TSX Composite |
| Developed_EMEA | CS51.LON | iShares Core EURO STOXX 50 |
| Developed_EMEA (CH) | CSWG.LON | Amundi MSCI Switzerland |
| Developed_APAC (JP) | XDJP.LON | Xtrackers Nikkei 225 |
| Developed_APAC (AU) | SAUS.LON | iShares MSCI Australia |
| Emerging_Americas (BR) | IBZL.LON | iShares MSCI Brazil |
| Emerging_Americas (MX) | XMEX.LON | iShares MSCI Mexico |
| Emerging_APACandEMEA (CN) | ASHR | Xtrackers CSI 300 |
| Emerging_APACandEMEA (IN) | XNIF.LON | Xtrackers Nifty 50 |
| Emerging_APACandEMEA (KR) | EWY | iShares MSCI South Korea |

**Portfolio benchmarks** (for asset-class-level Sharpe ratio adjustment):
- Equities benchmark: **VEVE** (Vanguard FTSE Developed World)
- Bonds benchmark: **SAAA** (iShares Core Global Aggregate Bond)

---

## 3. Portfolio Construction Methodology (Notebook 03)

### Step 1 — Strategic Asset Allocation (Starting Point)
- **90% equity risk weight**
- **10% bond risk weight**

This is the *starting* allocation before Sharpe ratio adjustments.

### Step 2 — Regional Weights
Risk is allocated across regions as follows:
| Region Category | Target Weight |
|-----------------|---------------|
| Developed_AmericasandUK | 10% |
| Developed_EMEA | 35% |
| Developed_APAC | 35% |
| Emerging_Americas | 10% |
| Emerging_APACandEMEA | 10% |

Within each region, weight is split equally between the two intra-region categories (e.g., Beta and High Yield for equities; Govt and Corp for bonds).

### Step 3 — Sharpe Ratio Adjustment System

**Why:** ETFs with better risk-adjusted returns (higher Sharpe ratios) receive more weight. ETFs with poor risk-adjusted returns receive less.

**How it works:**
1. Calculate each ETF's Sharpe ratio: `yield / last_year_volatility` where `yield = last_year_dividends - TER`
2. Calculate the median Sharpe ratio within each asset class (equities separately from bonds)
3. Calculate `relative_sharpe_ratio = ETF Sharpe - median Sharpe`
4. Map the relative Sharpe ratio to an adjustment factor using linear interpolation

**Adjustment factor scale (0.6 → 1.48):**
| Relative Sharpe | Factor |
|----------------|--------|
| -1.0 (equities) / -0.25 (bonds) | 0.60 |
| 0.0 | 1.00 |
| +1.0 (equities) / +0.25 (bonds) | 1.48 |

**Sensitivity by asset class:**
- **Equities**: ±0.1 relative Sharpe range (tighter — equities are more mean-reverting)
- **Bonds**: ±0.25 relative Sharpe range (wider — bonds have more persistent spread)

**Asset-class-level adjustment:** The equity and bond allocations are also adjusted relative to each other based on their benchmark Sharpe ratios (VEVE vs SAAA), then normalized to sum to 100%.

### Step 4 — Volatility Normalization (Risk Parity)
Cash weights are derived from risk weights by dividing by volatility:
```
cash_weight_guess = normalized_risk_weight / last_year_volatility
cash_weight = (sum_of_risk_weights / sum_of_cash_weight_guesses) × cash_weight_guess
```
This ensures higher-volatility ETFs receive less capital for the same risk contribution.

### Step 5 — Final Asset Class Weights (After All Adjustments)
The 90/10 strategic split adjusts to approximately:
- **42.91% equities** (cash weight)
- **57.09% bonds** (cash weight)

The inversion (bonds > equities in cash terms) is driven by the volatility normalization — equities are ~3-4× more volatile than bonds, so equal risk requires more capital allocated to bonds.

### Step 6 — Final Allocation
- **Total investment: £20,000**
- Invested across 16 ETFs (8 equities + 8 bonds)
- Investment per ETF = £20,000 × final_cash_weight / 100
- IGLT currently has 0% allocation (lowest Sharpe ratio among bonds after adjustments)

---

## 4. Final Portfolio Holdings

| Ticker | Name | Asset Class | Region | Cash Weight | Investment (£) | TER | Net Yield* |
|--------|------|-------------|--------|-------------|----------------|-----|-----------|
| IMIB | iShares FTSE MIB UCITS ETF EUR (Dist) | Equity | Developed_EMEA | 19% | £3,800 | 0.35% | 3.98% |
| XDDX | Xtrackers DAX ESG Screened UCITS ETF 1D | Equity | Developed_EMEA | 17% | £3,400 | 0.09% | 2.72% |
| AUAD | UBS MSCI Australia UCITS ETF (AUD) A-dis | Equity | Developed_APAC | 16% | £3,200 | 0.40% | 3.18% |
| LCUK | Amundi UK Equity All Cap UCITS ETF Dist | Equity | Developed_AmericasandUK | 10% | £2,000 | 0.04% | 3.70% |
| IBZL | iShares MSCI Brazil UCITS ETF (Dist) | Equity | Emerging_Americas | 9% | £1,800 | 0.74% | 4.85% |
| PRIJ | Amundi Prime Japan UCITS ETF DR (D) | Equity | Developed_APAC | 7% | £1,400 | 0.05% | 1.82% |
| QYLP | Global X Nasdaq 100 Covered Call UCITS ETF D | Equity | Developed_AmericasandUK | 7% | £1,400 | 0.45% | 11.27% |
| HMCH | HSBC MSCI China UCITS ETF USD | Equity | Emerging_APACandEMEA | 2% | £400 | 0.28% | 2.39% |
| VECP | Vanguard EUR Corporate Bond UCITS ETF Dist | Bonds | Developed_EMEA | 5% | £1,000 | 0.09% | 3.76% |
| SLXX | iShares Core GBP Corporate Bond UCITS ETF | Bonds | Developed_AmericasandUK | 2% | £400 | 0.20% | 3.29% |
| PRIR | Amundi Prime Euro Govies UCITS ETF DR (D) | Bonds | Developed_EMEA | 2% | £400 | 0.05% | 1.90% |
| TRXG | Invesco US Treasury Bond 7-10yr UCITS ETF Dist | Bonds | Developed_AmericasandUK | 1% | £200 | 0.06% | 3.95% |
| UC81 | UBS Bloomberg US Liquid Corporates UCITS ETF | Bonds | Developed_AmericasandUK | 1% | £200 | 0.16% | 3.13% |
| EMCP | iShares JPMorgan USD EM Corporate Bond UCITS ETF | Bonds | Emerging_APACandEMEA | 1% | £200 | 0.50% | 4.81% |
| VEMT | Vanguard USD Emerging Markets Govt Bond UCITS ETF | Bonds | Emerging_APACandEMEA | 1% | £200 | 0.25% | 3.97% |
| IGLT | iShares Core UK Gilts UCITS ETF | Bonds | Developed_AmericasandUK | 0% | £0 | 0.07% | 3.46% |

*Net yield = last_year_dividends - TER

---

## 5. Performance Tracking Methodology (Notebook 04)

### Annual Performance Metrics
For each year (2021–2025), and for each ETF:
- **Annual return**: `(end_price - start_price) / start_price × 100`
- **Annualized volatility**: `daily_returns.std() × √252 × 100`

### Portfolio-Level Performance
Portfolio metrics are weighted aggregations:
- `weighted_return = Σ (etf_return × investment_weight)`
- `weighted_volatility = Σ (etf_volatility × investment_weight)`
- `investment_weight = etf_investment / total_portfolio_investment`

### Risk-Adjusted Metrics
Sharpe ratio used for performance evaluation:
- Formula: `(portfolio_return - risk_free_rate) / portfolio_volatility`
- **Risk-free rate: 4.0%** (UK base rate benchmark)

### Periods Tracked
- **Annual**: Full calendar years 2021–2025
- **YTD (Year to Date)**: From 2025-01-01 to present
- **MTD (Month to Date)**: From start of current month to present
- **Daily PnL**: Daily return × investment amount in GBP

### Data Source
All price data fetched via **yfinance** (default, no API key required). AlphaVantage is a fallback option. Tickers are stored as bare symbols (e.g., `VEVE`) and `.L` is appended automatically for London Stock Exchange listings.

---

## 6. Platform and Tax Wrapper

- **Platform**: InvestEngine (UK)
- **Account type**: ISA (Individual Savings Account) — all gains and income are tax-free
- **ETF type**: All holdings are distributing UCITS ETFs — dividends are paid out to the account
- **Currency**: Portfolio base currency is GBP. Individual ETFs trade in GBP, EUR, USD, AUD, JPY

---

## Disclaimer

This portfolio is documented for educational purposes only. It is NOT investment advice. The author is not a financial adviser. Investing carries risk and you can lose money. Past performance does not guarantee future results. Always do your own research before investing.
