"""Financial metrics: volatility, Sharpe ratio, period returns, PnL."""

import datetime
import warnings

import numpy as np
import pandas as pd


def calculate_annualized_volatility(prices: pd.Series, period: int = 252) -> float:
    """Return annualized volatility from a price series.

    Args:
        prices: Series of daily prices (adjusted close), sorted ascending.
        period: Number of trading days per year (default 252).
    """
    returns = prices.pct_change().dropna()
    if len(returns) < 2:
        warnings.warn("Fewer than 2 return observations — returning NaN.", stacklevel=2)
        return float("nan")
    return float(returns.std() * np.sqrt(period))


def calculate_sharpe_ratio(
    annual_return: float,
    annual_volatility: float,
    risk_free_rate: float = 0.0,
) -> float:
    """Return the Sharpe ratio given annualized return and volatility.

    Args:
        annual_return: Annualized return (e.g. 0.12 for 12%).
        annual_volatility: Annualized volatility (e.g. 0.20 for 20%).
        risk_free_rate: Annualized risk-free rate (e.g. 0.04 for 4%).
    """
    if annual_volatility <= 0:
        return float("nan")
    return (annual_return - risk_free_rate) / annual_volatility


def calculate_portfolio_volatility(
    returns_df: pd.DataFrame,
    weights: pd.Series,
    period: int = 252,
) -> float:
    """Return annualized portfolio volatility using covariance.

    Args:
        returns_df: DataFrame where each column is an asset's daily returns.
        weights: Series of weights indexed by ticker (must match columns).
        period: Number of trading days per year.
    """
    if returns_df.empty or weights.empty:
        return float("nan")

    # Align weights with columns
    w = weights.reindex(returns_df.columns).fillna(0).values
    cov_matrix = returns_df.cov() * period
    portfolio_var = np.dot(w.T, np.dot(cov_matrix, w))
    return float(np.sqrt(portfolio_var)) if portfolio_var > 0 else 0.0


def interpolate_adjustment_factor(
    sharpe_ratio: float,
    factors_dict: dict[float, float],
) -> float:
    """Map a Sharpe ratio to an adjustment factor using linear interpolation.

    Args:
        sharpe_ratio: The Sharpe ratio to look up.
        factors_dict: Dict mapping Sharpe ratio breakpoints → adjustment factors.
                      Keys must be sorted in ascending order.

    Returns:
        The interpolated adjustment factor.  Values outside the range are
        clipped to the nearest boundary value.
    """
    sharpe_values = sorted(factors_dict.keys())
    factor_values = [factors_dict[s] for s in sharpe_values]
    return float(np.interp(sharpe_ratio, sharpe_values, factor_values))


def calculate_period_metrics(
    df: pd.DataFrame,
    start_date: str | datetime.date,
    end_date: str | datetime.date | None = None,
) -> dict[str, float]:
    """Return total return and annualized volatility for a date range.

    Args:
        df: DataFrame with a DatetimeIndex and a ``close`` column.
        start_date: Start of the period (inclusive).
        end_date: End of the period (inclusive). Defaults to the last row.

    Returns:
        Dict with keys ``return`` (fractional) and ``volatility`` (annualized).
    """
    subset = df.loc[str(start_date) : str(end_date)] if end_date else df.loc[str(start_date):]
    if len(subset) < 2:
        warnings.warn(
            f"Fewer than 2 data points in [{start_date}, {end_date}] — returning NaN.",
            stacklevel=2,
        )
        return {"return": float("nan"), "volatility": float("nan")}
    close = subset["close"]
    total_return = (close.iloc[-1] - close.iloc[0]) / close.iloc[0]
    volatility = calculate_annualized_volatility(close)
    return {"return": float(total_return), "volatility": volatility}


def calculate_daily_pnl(
    df: pd.DataFrame,
    investment: float,
    start_date: str | datetime.date,
    end_date: str | datetime.date | None = None,
) -> pd.DataFrame:
    """Return a DataFrame of daily PnL from an investment in an ETF.

    Args:
        df: DataFrame with DatetimeIndex and ``close`` column.
        investment: Initial investment amount in GBP.
        start_date: Start of the period (inclusive).
        end_date: End of the period (inclusive). Defaults to the last row.

    Returns:
        DataFrame with columns ``daily_return`` and ``pnl``.
    """
    subset = df.loc[str(start_date) : str(end_date)] if end_date else df.loc[str(start_date):]
    result = subset[["close"]].copy()
    result["daily_return"] = result["close"].pct_change()
    result["pnl"] = result["daily_return"] * investment
    return result[["daily_return", "pnl"]]
