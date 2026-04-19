"""Financial metrics: volatility, Sharpe ratio, period returns, PnL.

This module covers the metrics currently surfaced in the book:

- Annualised volatility, Sharpe ratio (uses ``config.RISK_FREE_RATE`` as default)
- Portfolio volatility (weighted covariance)
- Period return / daily PnL
- Max drawdown (value + peak/trough dates + full drawdown series)
- Beta, Tracking Error, Information Ratio (vs a benchmark series)
- Sharpe adjustment-factor interpolation (for the weight-scoring model)

Deliberately **out of scope** (see `content/00b_methodology.md` Future Work):
XIRR (money-weighted return), Sortino ratio, Calmar ratio, and factor-based
attribution (value/growth/size). These require additional dependencies and
schema/data-series work; they will be added in a later pass.
"""

import datetime
import warnings

import numpy as np
import pandas as pd

from .config import RISK_FREE_RATE


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


def calculate_dynamic_rfr(
    rate_series: pd.Series,
    start_date: str | datetime.date,
    end_date: str | datetime.date,
) -> float:
    """Return the annualized compounded risk-free rate for a specific period.

    Geometrically compounds the annualized daily percentage rates (e.g. 4.0 for 4%)
    from SONIA and returns the equivalent annualized cash return for that specific tenor.

    Args:
        rate_series: Series of daily annualized rates (as a percentage, e.g. 4.0).
                     Index values are coerced to Datetime and sorted.
        start_date: Start of the compounding period (inclusive).
        end_date: End of the compounding period (inclusive).
    """
    if rate_series.empty:
        return float("nan")

    start_ts = pd.to_datetime(start_date)
    end_ts = pd.to_datetime(end_date)
    if end_ts < start_ts:
        return float("nan")

    rates = rate_series.copy()
    if not isinstance(rates.index, pd.DatetimeIndex):
        rates.index = pd.to_datetime(rates.index, errors="coerce")
        rates = rates[~rates.index.isna()]
        if rates.empty:
            return float("nan")

    rates = rates.sort_index().dropna()
    observed = rates.loc[:end_ts]
    if observed.empty:
        return float("nan")
    # Reject periods where the available observations do not cover start_date.
    if observed.index.min() > start_ts:
        return float("nan")

    calendar_index = pd.date_range(start=start_ts, end=end_ts, freq="D")
    calendar_rates = observed.reindex(calendar_index).ffill()
    if calendar_rates.isna().any():
        return float("nan")

    # SONIA standard actual/365 compounding convention
    daily_yields = calendar_rates / 100.0 / 365.0

    total_return = float((1 + daily_yields).prod()) - 1.0

    # Annualize using the inclusive calendar-day count in the requested range.
    n_days = len(calendar_rates)
    annualized_return = ((1.0 + total_return) ** (365.0 / n_days) - 1.0) * 100.0
    return float(annualized_return)


def calculate_sharpe_ratio(
    annual_return: float,
    annual_volatility: float,
    risk_free_rate: float | None = None,
) -> float:
    """Return the Sharpe ratio given annualized return and volatility.

    Args:
        annual_return: Annualized return (e.g. 0.12 for 12%).
        annual_volatility: Annualized volatility (e.g. 0.20 for 20%).
        risk_free_rate: Annualized risk-free rate (e.g. 0.04 for 4%). When
            ``None`` (the default), falls back to ``config.RISK_FREE_RATE``,
            which is sourced from the ``RISK_FREE_RATE`` environment variable
            (0.0 if unset).
    """
    if risk_free_rate is None:
        risk_free_rate = RISK_FREE_RATE
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


def calculate_max_drawdown(
    series: pd.Series,
    is_returns: bool = False,
) -> dict:
    """Return the maximum drawdown of a price or cumulative-return series.

    A drawdown at time *t* is the percentage decline from the running maximum
    up to *t*. Max drawdown is the most negative such value — a standard
    worst-peak-to-trough loss metric.

    Args:
        series: Pandas Series indexed by date. Either a price/equity-curve
            series (``is_returns=False``, the default) or a daily-return
            series (``is_returns=True``) that will be compounded internally.
        is_returns: If True, treat ``series`` as daily simple returns and
            compound them to an equity curve before computing the drawdown.

    Returns:
        Dict with keys:
            - ``value``: Max drawdown as a negative fraction (e.g. ``-0.23``
              for a 23% drawdown). ``0.0`` if the series never declines.
            - ``peak_date``: Date of the running peak preceding the trough.
            - ``trough_date``: Date of the maximum drawdown.
            - ``series``: Full drawdown time series (same index as input).

        Returns NaN values with a warning if the series has < 2 observations.
    """
    if series is None or len(series) < 2:
        warnings.warn(
            "Fewer than 2 observations — returning NaN drawdown.",
            stacklevel=2,
        )
        return {
            "value": float("nan"),
            "peak_date": pd.NaT,
            "trough_date": pd.NaT,
            "series": pd.Series(dtype=float),
        }

    if is_returns:
        equity = (1 + series.fillna(0)).cumprod()
    else:
        equity = series.astype(float)

    running_peak = equity.cummax()
    drawdown = equity / running_peak - 1.0
    trough_date = drawdown.idxmin()
    min_dd = float(drawdown.loc[trough_date])
    # Peak is the running-max date *on or before* the trough.
    peak_date = equity.loc[:trough_date].idxmax()
    return {
        "value": min_dd,
        "peak_date": peak_date,
        "trough_date": trough_date,
        "series": drawdown,
    }


def _align_returns(a: pd.Series, b: pd.Series) -> tuple[pd.Series, pd.Series]:
    """Inner-join two return series on date, drop NaNs."""
    joined = pd.concat([a, b], axis=1, join="inner").dropna()
    return joined.iloc[:, 0], joined.iloc[:, 1]


def rolling_volatility_from_cumret(
    cum_ret_pct: pd.Series,
    window: int = 30,
    period: int = 252,
) -> pd.Series:
    """Annualised rolling volatility from a cumulative-%-return series.

    Converts the cumulative percentage series (e.g. 15.43 = +15.43%) to an
    equity-curve multiplier, differences to daily returns, then applies the
    standard ``std * sqrt(period)`` annualisation. Output is in percent.
    """
    equity = 1 + cum_ret_pct / 100
    daily = equity.pct_change()
    return daily.rolling(window=window).std() * np.sqrt(period) * 100


def rolling_sharpe(
    returns: pd.Series,
    window: int = 30,
    period: int = 252,
    risk_free_rate: float = 0.0,
) -> pd.Series:
    """Rolling annualised Sharpe ratio from a daily-return series.

    ``risk_free_rate`` is the *annualised* risk-free rate; it is converted
    to a per-period drag internally.
    """
    rf_daily = risk_free_rate / period
    excess = returns - rf_daily
    mean = excess.rolling(window).mean() * period
    vol = returns.rolling(window).std() * np.sqrt(period)
    return mean / vol.where(vol > 0)


def calculate_beta(
    asset_returns: pd.Series,
    benchmark_returns: pd.Series,
) -> float:
    """Return the beta of an asset vs a benchmark return series.

    Beta = Cov(asset, benchmark) / Var(benchmark). Both inputs should be
    daily simple returns on a common date range; they are inner-joined
    and NaNs are dropped before the computation.

    A beta of 1.0 means the asset moves 1:1 with the benchmark on average;
    > 1.0 means more sensitive, < 1.0 means less sensitive.

    Returns NaN with a warning if < 2 aligned observations remain, or if
    the benchmark variance is zero.
    """
    a, b = _align_returns(asset_returns, benchmark_returns)
    if len(a) < 2:
        warnings.warn(
            "Fewer than 2 aligned observations — returning NaN beta.",
            stacklevel=2,
        )
        return float("nan")
    var_b = float(b.var())
    if var_b <= 0:
        return float("nan")
    cov = float(a.cov(b))
    return cov / var_b


def calculate_tracking_error(
    portfolio_returns: pd.Series,
    benchmark_returns: pd.Series,
    period: int = 252,
) -> float:
    """Return annualised tracking error: stdev(portfolio − benchmark) × √period.

    Tracking error measures how tightly a portfolio follows its benchmark on
    a day-by-day basis. Lower = tighter tracking. Zero when portfolio and
    benchmark return series are identical.

    Inputs are inner-joined on date before differencing.
    """
    a, b = _align_returns(portfolio_returns, benchmark_returns)
    if len(a) < 2:
        warnings.warn(
            "Fewer than 2 aligned observations — returning NaN tracking error.",
            stacklevel=2,
        )
        return float("nan")
    excess = a - b
    return float(excess.std() * np.sqrt(period))


def calculate_information_ratio(
    portfolio_returns: pd.Series,
    benchmark_returns: pd.Series,
    period: int = 252,
) -> float:
    """Return the annualised Information Ratio: mean excess return / tracking error.

    IR = (annualised excess return) / (annualised tracking error). A higher
    IR means the portfolio's outperformance over the benchmark is more
    consistent per unit of active risk taken.

    Returns NaN when the benchmark and portfolio are effectively identical
    (zero tracking error) or there are < 2 aligned observations.
    """
    a, b = _align_returns(portfolio_returns, benchmark_returns)
    if len(a) < 2:
        warnings.warn(
            "Fewer than 2 aligned observations — returning NaN information ratio.",
            stacklevel=2,
        )
        return float("nan")
    excess = a - b
    te = float(excess.std())
    if te <= 0:
        return float("nan")
    ann_excess = float(excess.mean() * period)
    ann_te = te * np.sqrt(period)
    return ann_excess / ann_te
