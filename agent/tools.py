"""Tool implementations and Claude tool schemas for the ETF Portfolio Agent.

Each tool function returns a plain Python dict/list — JSON-serialisable.
The TOOL_SCHEMAS list defines the tools in Anthropic's tool-use format.
"""

import sys
import warnings
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np

from etf_utils.data_io import load_output
from etf_utils.data_provider import DataProvider
from etf_utils.metrics import calculate_period_metrics, calculate_sharpe_ratio

# ---------------------------------------------------------------------------
# Methodology explanations (strictly from the notebooks — no general advice)
# ---------------------------------------------------------------------------

_METHODOLOGY: dict[str, str] = {
    "overview": (
        "This is a DIY ETF ISA portfolio investing £20,000 across 16 distributing UCITS ETFs "
        "on InvestEngine. It covers equities and bonds across 5 geographic regions. "
        "The construction pipeline has 4 stages: (1) data collection from JustETF, "
        "(2) ETF screening, (3) portfolio construction with Sharpe ratio adjustments, "
        "and (4) ongoing performance tracking."
    ),
    "screening_criteria": (
        "Equity ETFs must satisfy ALL of the following:\n"
        "• Distributing dividends only (no accumulating ETFs)\n"
        "• Fund size > £100M (liquidity)\n"
        "• Not currency-hedged\n"
        "• TER < 0.5% (exception: IBZL at 0.74% — only Brazil ETF on InvestEngine)\n"
        "• Available on InvestEngine (verified via their API)\n"
        "• Not in the exclusion list: XUCN, LYXIB, C001, SW2CHA, XSMI, SJPD, XESD, C024\n\n"
        "After screening, each region gets exactly 2 equity ETFs:\n"
        "• High Yield: highest last_year_dividends in that region\n"
        "• Beta: beta ≥ 1.0 vs regional benchmark, lowest TER\n\n"
        "Bond ETFs are manually curated into Govt and Corp categories per region. "
        "JNKE was excluded because it is not available on InvestEngine."
    ),
    "sharpe_adjustment": (
        "The Sharpe adjustment system re-weights ETFs based on risk-adjusted income:\n\n"
        "1. Each ETF's Sharpe ratio = (last_year_dividends - TER) / last_year_volatility\n"
        "2. Relative Sharpe = ETF Sharpe - median Sharpe within its asset class\n"
        "3. Relative Sharpe is mapped to an adjustment factor (0.6 → 1.48) via linear interpolation:\n"
        "   • Equities: ±0.1 relative Sharpe range → 0.6–1.48 factor\n"
        "   • Bonds: ±0.25 relative Sharpe range → 0.6–1.48 factor\n"
        "4. ETF risk weight = starting_weight × adjustment_factor\n"
        "5. Weights are then normalised within each asset class to sum to 100%.\n\n"
        "A separate asset-class-level adjustment is applied first: the equity (VEVE) and "
        "bond (SAAA) benchmarks' 2024 Sharpe ratios are used to adjust the 90/10 "
        "strategic split before the ETF-level adjustments."
    ),
    "asset_allocation": (
        "Strategic starting allocation: 90% equity risk weight / 10% bond risk weight.\n\n"
        "After Sharpe ratio adjustments and volatility normalisation, the final CASH weights are:\n"
        "• Equities: ~42.91%\n"
        "• Bonds: ~57.09%\n\n"
        "The inversion (bonds > equities in cash) is driven by risk parity: equities are "
        "3–4× more volatile than bonds, so equal risk contribution requires more capital "
        "in bonds. Cash weight = risk_weight / volatility."
    ),
    "regional_weights": (
        "Target regional risk allocations:\n"
        "• Developed_AmericasandUK: 10%\n"
        "• Developed_EMEA: 35%\n"
        "• Developed_APAC: 35%\n"
        "• Emerging_Americas: 10%\n"
        "• Emerging_APACandEMEA: 10%\n\n"
        "Within each region, weight is split equally between intra-region categories "
        "(Beta/High Yield for equities; Govt/Corp for bonds). "
        "Sharpe ratio adjustments then tilt weight within the region toward better-performing ETFs."
    ),
    "benchmark_selection": (
        "Asset-class benchmarks (used for asset-allocation-level Sharpe adjustment):\n"
        "• Equities: VEVE (Vanguard FTSE Developed World UCITS ETF)\n"
        "• Bonds: SAAA (iShares Core Global Aggregate Bond UCITS ETF)\n\n"
        "Regional equity benchmarks (used for beta calculation):\n"
        "• UK: ISF.LON (iShares Core FTSE 100)\n"
        "• US: SPY (SPDR S&P 500)\n"
        "• Canada: ZCN.TRT (BMO S&P/TSX Composite)\n"
        "• Eurozone: CS51.LON (iShares Core EURO STOXX 50)\n"
        "• Switzerland: CSWG.LON (Amundi MSCI Switzerland)\n"
        "• Japan: XDJP.LON (Xtrackers Nikkei 225)\n"
        "• Australia: SAUS.LON (iShares MSCI Australia)\n"
        "• Brazil: IBZL.LON (iShares MSCI Brazil)\n"
        "• Mexico: XMEX.LON (iShares MSCI Mexico)\n"
        "• China: ASHR (Xtrackers CSI 300)\n"
        "• India: XNIF.LON (Xtrackers Nifty 50)\n"
        "• South Korea: EWY (iShares MSCI South Korea)"
    ),
}


# ---------------------------------------------------------------------------
# Tool functions
# ---------------------------------------------------------------------------


def get_portfolio_holdings() -> list[dict]:
    """Load current portfolio holdings from final_portfolio.csv."""
    df = load_output("final_portfolio.csv")
    cols = ["ticker", "name", "asset_class", "region_category",
            "intra_region_category", "final_cash_weights", "investment",
            "ter", "last_year_dividends", "yield"]
    df = df[cols].copy()
    df["investment"] = df["investment"].round(0)
    df["final_cash_weights"] = df["final_cash_weights"].round(1)
    return df.to_dict(orient="records")


def get_etf_performance(ticker: str, period: str = "ytd") -> dict:
    """Fetch live performance metrics for an ETF via yfinance."""
    today = date.today()
    if period == "ytd":
        start = date(today.year, 1, 1)
    elif period == "1y":
        start = today - timedelta(days=365)
    elif period == "3y":
        start = today - timedelta(days=365 * 3)
    elif period == "5y":
        start = today - timedelta(days=365 * 5)
    else:
        start = date(today.year, 1, 1)

    try:
        provider = DataProvider()
        df = provider.get_historical_prices(ticker)

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            metrics = calculate_period_metrics(df, str(start))

        if np.isnan(metrics.get("return", float("nan"))):
            return {"error": f"Insufficient price data for {ticker} over the {period} period."}

        ret_pct = round(metrics["return"] * 100, 2)
        vol_pct = round(metrics["volatility"] * 100, 2)
        sharpe = (
            round(calculate_sharpe_ratio(ret_pct, vol_pct, risk_free_rate=4.0), 2)
            if vol_pct > 0
            else None
        )

        return {
            "ticker": ticker,
            "period": period,
            "start_date": str(start),
            "end_date": str(today),
            "return_pct": ret_pct,
            "annualized_volatility_pct": vol_pct,
            "sharpe_ratio": sharpe,
        }
    except Exception as e:
        return {"error": str(e)}


def get_portfolio_income() -> dict:
    """Calculate weighted portfolio net income yield (dividends - TER)."""
    df = load_output("final_portfolio.csv")
    invested = df[df["investment"] > 0].copy()
    total_investment = invested["investment"].sum()
    invested["weight"] = invested["investment"] / total_investment
    invested["net_yield_pct"] = (invested["last_year_dividends"] - invested["ter"]).round(2)
    invested["weighted_net_yield"] = (invested["weight"] * invested["net_yield_pct"]).round(4)
    invested["annual_income_gbp"] = (invested["investment"] * invested["net_yield_pct"] / 100).round(2)

    portfolio_yield = round(float(invested["weighted_net_yield"].sum()), 2)
    annual_income_gbp = round(float(invested["annual_income_gbp"].sum()), 2)

    breakdown = (
        invested[["ticker", "name", "last_year_dividends", "ter", "net_yield_pct",
                   "investment", "annual_income_gbp"]]
        .sort_values("annual_income_gbp", ascending=False)
        .to_dict(orient="records")
    )

    return {
        "portfolio_net_yield_pct": portfolio_yield,
        "annual_income_gbp": annual_income_gbp,
        "total_investment_gbp": round(float(total_investment), 0),
        "note": "Net yield = last_year_dividends - TER. Income figures are estimates based on last year's dividends.",
        "breakdown": breakdown,
    }


def explain_construction_methodology(topic: str) -> str:
    """Return a pre-written methodology explanation for the given topic."""
    text = _METHODOLOGY.get(topic)
    if text is None:
        available = ", ".join(_METHODOLOGY.keys())
        return f"Unknown topic '{topic}'. Available topics: {available}"
    return text


# ---------------------------------------------------------------------------
# Tool dispatch
# ---------------------------------------------------------------------------

def execute_tool(name: str, inputs: dict) -> dict | list | str:
    """Dispatch a tool call by name and return the result."""
    if name == "get_portfolio_holdings":
        return get_portfolio_holdings()
    if name == "get_etf_performance":
        return get_etf_performance(
            ticker=inputs["ticker"],
            period=inputs.get("period", "ytd"),
        )
    if name == "get_portfolio_income":
        return get_portfolio_income()
    if name == "explain_construction_methodology":
        return explain_construction_methodology(topic=inputs["topic"])
    return {"error": f"Unknown tool: {name}"}


# ---------------------------------------------------------------------------
# Claude tool schemas
# ---------------------------------------------------------------------------

TOOL_SCHEMAS = [
    {
        "name": "get_portfolio_holdings",
        "description": (
            "Returns the current portfolio holdings: ticker, name, asset class, region, "
            "intra-region category, cash weight (%), investment (£), TER, last year dividends, "
            "and net yield. Use this when asked about what is in the portfolio, the allocation, "
            "or how much is invested in each ETF."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "get_etf_performance",
        "description": (
            "Fetches live performance metrics for a specific ETF via yfinance: "
            "total return (%), annualized volatility (%), and Sharpe ratio. "
            "Use this when asked about how an ETF or the portfolio has performed."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "ticker": {
                    "type": "string",
                    "description": "ETF ticker symbol as it appears in the portfolio (e.g. IMIB, AUAD, VECP, PRIJ).",
                },
                "period": {
                    "type": "string",
                    "enum": ["ytd", "1y", "3y", "5y"],
                    "description": "Time period: 'ytd' = year to date, '1y' = 1 year, '3y' = 3 years, '5y' = 5 years.",
                },
            },
            "required": ["ticker"],
        },
    },
    {
        "name": "get_portfolio_income",
        "description": (
            "Calculates the portfolio's estimated annual income: weighted net yield "
            "(dividends minus TER) and GBP income per ETF. Use this when asked about "
            "income, yield, dividends, or how the portfolio makes money."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "explain_construction_methodology",
        "description": (
            "Returns a detailed explanation of a specific aspect of how the portfolio "
            "was constructed, drawn strictly from the portfolio's own notebooks. "
            "Use this when asked about the methodology, construction process, or decisions."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "topic": {
                    "type": "string",
                    "enum": [
                        "overview",
                        "screening_criteria",
                        "sharpe_adjustment",
                        "asset_allocation",
                        "regional_weights",
                        "benchmark_selection",
                    ],
                    "description": (
                        "The methodology topic: "
                        "'overview' = high-level summary, "
                        "'screening_criteria' = how ETFs are filtered, "
                        "'sharpe_adjustment' = how Sharpe ratios adjust weights, "
                        "'asset_allocation' = equity vs bond split, "
                        "'regional_weights' = geographic allocation targets, "
                        "'benchmark_selection' = which benchmarks are used and why."
                    ),
                },
            },
            "required": ["topic"],
        },
    },
]
