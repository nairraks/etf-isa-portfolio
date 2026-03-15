"""Unified data provider: yfinance (default) or AlphaVantage."""

import datetime
import warnings

import pandas as pd
import requests
import yfinance as yf

from .config import ALPHAVANTAGE_API_KEY, DATA_PROVIDER

_AV_BASE = "https://www.alphavantage.co/query"


def _normalize_symbol(symbol: str, provider: str) -> str:
    """Convert a bare ticker to the provider-specific format.

    Tickers in config files are stored without exchange suffix
    (e.g. "VEVE"). This function appends the right suffix:
    - yfinance: .L  (e.g. VEVE.L)
    - alphavantage: .LON  (e.g. VEVE.LON)

    If the symbol already has a suffix (contains "."), it is left unchanged.
    """
    if "." in symbol:
        return symbol
    if provider == "yfinance":
        return f"{symbol}.L"
    return f"{symbol}.LON"


class DataProvider:
    """Unified interface for fetching ETF price and FX data."""

    def __init__(self, provider: str | None = None) -> None:
        self.provider = (provider or DATA_PROVIDER).lower()

    def get_historical_prices(
        self,
        symbol: str,
        start_date: datetime.date | str | None = None,
        end_date: datetime.date | str | None = None,
    ) -> pd.DataFrame:
        """Return daily adjusted close prices for *symbol*.

        Returns a DataFrame with a DatetimeIndex and a single column
        ``close`` containing adjusted closing prices, sorted ascending.
        """
        sym = _normalize_symbol(symbol, self.provider)
        if self.provider == "yfinance":
            kwargs = {"progress": False, "auto_adjust": True}
            if start_date:
                kwargs["start"] = start_date
            if end_date:
                kwargs["end"] = end_date
            df = yf.download(sym, **kwargs)
            if df.empty:
                raise ValueError(f"No data returned for symbol {sym!r}")
            close = df["Close"]
            if hasattr(close, "columns"):
                # Multi-ticker download — take the first (and only) column
                close = close.iloc[:, 0]
            result = close.to_frame(name="close")
            result.index = pd.to_datetime(result.index)
            return result.sort_index()
        # AlphaVantage
        params = {
            "function": "TIME_SERIES_DAILY_ADJUSTED",
            "symbol": sym,
            "outputsize": "full",
            "apikey": ALPHAVANTAGE_API_KEY,
        }
        resp = requests.get(_AV_BASE, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json().get("Time Series (Daily)", {})
        if not data:
            raise ValueError(f"No AlphaVantage data for {sym!r}. Check API key and symbol.")
        df = pd.DataFrame.from_dict(data, orient="index", dtype=float)
        df.index = pd.to_datetime(df.index)
        df = df.sort_index()
        df = df.rename(columns={"5. adjusted close": "close"})
        df = df[["close"]]
        if start_date:
            df = df[df.index >= pd.to_datetime(start_date)]
        if end_date:
            df = df[df.index <= pd.to_datetime(end_date)]
        return df

    def get_fx_rate(self, from_ccy: str = "GBP", to_ccy: str = "EUR") -> pd.DataFrame:
        """Return daily FX rates as a DataFrame with column ``rate``."""
        if self.provider == "yfinance":
            pair = f"{from_ccy}{to_ccy}=X"
            df = yf.download(pair, progress=False, auto_adjust=True)
            if df.empty:
                raise ValueError(f"No FX data for {pair!r}")
            close = df["Close"]
            if hasattr(close, "columns"):
                close = close.iloc[:, 0]
            result = close.to_frame(name="rate")
            result.index = pd.to_datetime(result.index)
            return result.sort_index()
        # AlphaVantage
        params = {
            "function": "FX_DAILY",
            "from_symbol": from_ccy,
            "to_symbol": to_ccy,
            "outputsize": "full",
            "apikey": ALPHAVANTAGE_API_KEY,
        }
        resp = requests.get(_AV_BASE, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json().get("Time Series FX (Daily)", {})
        if not data:
            raise ValueError(f"No FX data for {from_ccy}/{to_ccy} from AlphaVantage.")
        df = pd.DataFrame.from_dict(data, orient="index", dtype=float)
        df.index = pd.to_datetime(df.index)
        df = df.sort_index()
        df = df.rename(columns={"4. close": "rate"})
        return df[["rate"]]

    def get_latest_price(self, symbol: str) -> tuple[str, float]:
        """Return (date_string, price) for the most recent trading day."""
        df = self.get_historical_prices(symbol)
        recent = df.dropna().tail(5)
        if recent.empty:
            raise ValueError(f"No recent price data for {symbol!r}")
        latest = recent.iloc[-1]
        date_str = str(recent.index[-1].date())
        return date_str, float(latest["close"])

    def get_benchmark_period_return(
        self,
        symbol: str,
        start: datetime.date | str,
        end: datetime.date | str,
    ) -> float:
        """Return the total return (as a fraction) over [start, end].

        Returns ``float("nan")`` if the symbol has no data (e.g. delisted).
        """
        try:
            df = self.get_historical_prices(symbol, start_date=start, end_date=end)
        except ValueError as exc:
            warnings.warn(
                f"Could not fetch data for {symbol!r}: {exc}",
                stacklevel=2,
            )
            return float("nan")
        if len(df) < 2:
            warnings.warn(
                f"Fewer than 2 price points for {symbol!r} in [{start}, {end}]",
                stacklevel=2,
            )
            return float("nan")
        start_price = df["close"].iloc[0]
        end_price = df["close"].iloc[-1]
        return (end_price - start_price) / start_price
