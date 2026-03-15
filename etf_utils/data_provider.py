"""Unified data provider: yfinance (default) or AlphaVantage."""

import datetime
import warnings

import pandas as pd
import requests
import yfinance as yf

from .config import ALPHAVANTAGE_API_KEY, DATA_PROVIDER

_AV_BASE = "https://www.alphavantage.co/query"


def _normalize_symbol(symbol: str, provider: str) -> str:
    """Convert a bare ticker to the provider-specific format."""
    if "." in symbol:
        return symbol
    if symbol in {"SPY", "ASHR", "EWY"}:
        return symbol
    if provider == "yfinance":
        return f"{symbol}.L"
    return f"{symbol}.LON"


def _sanitize_prices(df: pd.DataFrame) -> pd.DataFrame:
    """Detect and fix 100x jumps (GBP vs GBX unit issues)."""
    if df.empty or "close" not in df.columns:
        return df

    df = df.copy()
    prices = df["close"].values
    if len(prices) < 2:
        return df

    for i in range(1, len(prices)):
        ratio = prices[i] / prices[i - 1]
        # Detect ~100x jump (GBX to GBP or vice versa)
        if 80 < ratio < 125:
            # Assume previous prices were in GBP and current is GBX,
            # or current is GBP and previous was GBX.
            # Actually, if price[i] is ~100x price[i-1], price[i] is likely in pence.
            # We want everything in the same units. Let's normalize to the more recent unit?
            # No, let's normalize to the first unit seen to maintain consistency with historicals.
            prices[i:] /= 100
        elif 0.008 < ratio < 0.0125:
            prices[i:] *= 100

    df["close"] = prices
    return df


class DataProvider:
    """Unified interface for fetching ETF price and FX data."""

    def __init__(self, provider: str | None = None) -> None:
        self.provider = (provider or DATA_PROVIDER).lower()
        self._setup_yf_cache()

    def _setup_yf_cache(self) -> None:
        """Handle yfinance cache initialization and bypass if corrupt."""
        import os
        import tempfile
        from pathlib import Path

        try:
            # Try to use a local project-specific cache to avoid system-wide corruption
            cache_dir = Path("data/cache/yfinance").resolve()
            cache_dir.mkdir(parents=True, exist_ok=True)
            yf.set_tz_cache_location(str(cache_dir))
        except Exception as e:
            # Fallback to a temporary directory if permission issues occur
            try:
                temp_cache = Path(tempfile.gettempdir()) / "etf_yf_cache"
                temp_cache.mkdir(parents=True, exist_ok=True)
                yf.set_tz_cache_location(str(temp_cache))
            except Exception:
                pass

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
        if self.provider == "yfinance":
            try:
                sym = _normalize_symbol(symbol, "yfinance")
                kwargs = {"progress": False, "auto_adjust": True}
                if start_date:
                    kwargs["start"] = start_date
                if end_date:
                    kwargs["end"] = end_date
                if not start_date and not end_date:
                    kwargs["period"] = "max"
                df = yf.download(sym, **kwargs)
                if df.empty:
                    raise ValueError(f"No data returned for symbol {sym!r}")
                close = df["Close"]
                if hasattr(close, "columns"):
                    # Multi-ticker download — take the first (and only) column
                    close = close.iloc[:, 0]
                result = close.to_frame(name="close")
                result.index = pd.to_datetime(result.index)
                result = result.sort_index()
                return _sanitize_prices(result)
            except Exception as e:
                warnings.warn(f"yfinance failed for {symbol!r} ({e}). Falling back to AlphaVantage.", stacklevel=2)
        
        # AlphaVantage
        sym_av = _normalize_symbol(symbol, "alphavantage")
        # AlphaVantage
        params = {
            "function": "TIME_SERIES_DAILY_ADJUSTED",
            "symbol": sym_av,
            "outputsize": "full",
            "apikey": ALPHAVANTAGE_API_KEY,
        }
        resp = requests.get(_AV_BASE, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json().get("Time Series (Daily)", {})
        if not data:
            raise ValueError(f"No AlphaVantage data for {sym_av!r}. Check API key and symbol.")
        df = pd.DataFrame.from_dict(data, orient="index", dtype=float)
        df.index = pd.to_datetime(df.index)
        df = df.sort_index()
        df = df.rename(columns={"5. adjusted close": "close"})
        df = df[["close"]]
        if start_date:
            df = df[df.index >= pd.to_datetime(start_date)]
        if end_date:
            df = df[df.index <= pd.to_datetime(end_date)]
        return _sanitize_prices(df)

    def get_fx_rate(self, from_ccy: str = "GBP", to_ccy: str = "EUR") -> pd.DataFrame:
        """Return daily FX rates as a DataFrame with column ``rate``."""
        if self.provider == "yfinance":
            try:
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
            except Exception as e:
                warnings.warn(f"yfinance failed for FX {from_ccy}/{to_ccy} ({e}). Falling back to AlphaVantage.", stacklevel=2)
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
