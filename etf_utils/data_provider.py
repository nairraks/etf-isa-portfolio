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

    If the symbol already has a suffix, it is converted to the
    correct format for the active provider.
    """
    # Mapping of known exchange suffixes between providers
    # AlphaVantage -> yfinance
    _AV_TO_YF = {".LON": ".L", ".TRT": ".TO"}
    # yfinance -> AlphaVantage
    _YF_TO_AV = {v: k for k, v in _AV_TO_YF.items()}

    if "." in symbol:
        if provider == "yfinance":
            for av_suffix, yf_suffix in _AV_TO_YF.items():
                if symbol.upper().endswith(av_suffix):
                    return symbol[: -len(av_suffix)] + yf_suffix
        else:
            for yf_suffix, av_suffix in _YF_TO_AV.items():
                if symbol.upper().endswith(yf_suffix):
                    return symbol[: -len(yf_suffix)] + av_suffix
        return symbol
    if symbol in {"SPY", "ASHR", "EWY"}:
        return symbol
    if provider == "yfinance":
        return f"{symbol}.L"
    return f"{symbol}.LON"


class DataProvider:
    """Unified interface for fetching ETF price and FX data."""

    def __init__(self, provider: str | None = None) -> None:
        self.provider = (provider or DATA_PROVIDER).lower()
        self._price_cache: dict[str, pd.DataFrame] = {}
        self._fx_cache: dict[str, pd.DataFrame] = {}
        self._setup_yf_cache()

    def _setup_yf_cache(self) -> None:
        """Handle yfinance cache initialization and bypass if corrupt."""
        import tempfile
        from pathlib import Path

        try:
            cache_dir = Path("data/cache/yfinance").resolve()
            cache_dir.mkdir(parents=True, exist_ok=True)
            yf.set_tz_cache_location(str(cache_dir))
        except Exception:
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
        cache_key = symbol
        if cache_key in self._price_cache:
            cached = self._price_cache[cache_key]
            if start_date or end_date:
                filtered = cached.copy()
                if start_date:
                    filtered = filtered[filtered.index >= pd.to_datetime(start_date)]
                if end_date:
                    filtered = filtered[filtered.index <= pd.to_datetime(end_date)]
                return filtered
            return cached

        # Intercept fallback tickers (e.g., IMIB) that need AlphaVantage + local caching
        FALLBACK_TICKERS = ["IMIB"]
        if self.provider == "yfinance" and symbol in FALLBACK_TICKERS:
            from pathlib import Path

            cache_dir = Path("data/intermediate")
            cache_dir.mkdir(parents=True, exist_ok=True)
            cache_file = cache_dir / f"av_cache_adj_{symbol}.csv"

            if cache_file.exists():
                print(f"Loading {symbol} from local AlphaVantage cache: {cache_file}")
                df = pd.read_csv(cache_file, index_col=0, parse_dates=True)
                result = df[["close"]]
                self._price_cache[cache_key] = result
                if start_date:
                    result = result[result.index >= pd.to_datetime(start_date)]
                if end_date:
                    result = result[result.index <= pd.to_datetime(end_date)]
                return result

            print(f"Fetching {symbol} from AlphaVantage (API call)...")
            av_sym = _normalize_symbol(symbol, "alphavantage")
            params = {
                "function": "TIME_SERIES_DAILY_ADJUSTED",
                "symbol": av_sym,
                "outputsize": "full",
                "apikey": ALPHAVANTAGE_API_KEY,
            }
            resp = requests.get(_AV_BASE, params=params, timeout=30)
            resp.raise_for_status()
            data = resp.json().get("Time Series (Daily)", {})
            if not data:
                raise ValueError(
                    f"No AlphaVantage data for {av_sym!r}. Check API key and symbol."
                )
            df = pd.DataFrame.from_dict(data, orient="index", dtype=float)
            df.index = pd.to_datetime(df.index)
            df = df.sort_index()
            df = df.rename(columns={"5. adjusted close": "close"})
            result = df[["close"]]
            result = self._normalize_pence_to_pounds(result, av_sym)
            result.to_csv(cache_file)
            print(f"Saved {symbol} to local cache: {cache_file}")
            self._price_cache[cache_key] = result
            if start_date:
                result = result[result.index >= pd.to_datetime(start_date)]
            if end_date:
                result = result[result.index <= pd.to_datetime(end_date)]
            return result

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
                # Fallback: if the normalised symbol returns nothing,
                # retry with the bare ticker (works for US-listed ETFs like SPY).
                if df.empty and sym != symbol:
                    df = yf.download(symbol, **kwargs)
                    sym = symbol
                if df.empty:
                    raise ValueError(f"No data returned for symbol {sym!r}")
                close = df["Close"]
                if hasattr(close, "columns"):
                    # Multi-ticker download — take the first (and only) column
                    close = close.iloc[:, 0]
                result = close.to_frame(name="close")
                result.index = pd.to_datetime(result.index)
                if result.index.tz is not None:
                    result.index = result.index.tz_localize(None)
                result = result.sort_index()
                # Normalise GBX (pence) to GBP (pounds) for LSE tickers.
                result = self._normalize_pence_to_pounds(result, sym)
                if not start_date and not end_date:
                    self._price_cache[cache_key] = result
                return result
            except Exception as e:
                warnings.warn(
                    f"yfinance failed for {symbol!r} ({e}). "
                    "Falling back to AlphaVantage.",
                    stacklevel=2,
                )

        # AlphaVantage fallback
        sym_av = _normalize_symbol(symbol, "alphavantage")
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
            raise ValueError(
                f"No AlphaVantage data for {sym_av!r}. Check API key and symbol."
            )
        df = pd.DataFrame.from_dict(data, orient="index", dtype=float)
        df.index = pd.to_datetime(df.index)
        df = df.sort_index()
        df = df.rename(columns={"5. adjusted close": "close"})
        result = df[["close"]]
        result = self._normalize_pence_to_pounds(result, sym_av)
        if start_date:
            result = result[result.index >= pd.to_datetime(start_date)]
        if end_date:
            result = result[result.index <= pd.to_datetime(end_date)]
        self._price_cache[cache_key] = result
        return result

    def _normalize_pence_to_pounds(self, result: pd.DataFrame, sym: str) -> pd.DataFrame:
        """Ensure all LSE-specific data is normalized from pence to pounds."""
        if (sym.endswith(".L") or sym.endswith(".LON")) and len(result) > 0:
            import numpy as np

            prev_prices = result["close"].shift(1)
            with np.errstate(divide="ignore", invalid="ignore"):
                ratio = result["close"] / prev_prices

            # Jumps >50x or <0.02x mark the boundaries of different reporting units
            is_jump = (ratio > 50) | (ratio < 0.02)
            jump_indices = list(result.index[is_jump])

            # Split series into continuous chunks bounded by jumps
            boundaries = (
                [result.index[0]]
                + jump_indices
                + [result.index[-1] + pd.Timedelta(days=1)]
            )

            for i in range(len(boundaries) - 1):
                chunk_start = boundaries[i]
                chunk_end = boundaries[i + 1]

                mask = (result.index >= chunk_start) & (result.index < chunk_end)
                if not mask.any():
                    continue

                chunk_series = result.loc[mask, "close"]

                # Iteratively divide by 100 while the median is > 500.
                for _ in range(3):
                    if chunk_series.median() > 500:
                        chunk_series = chunk_series / 100
                    else:
                        break

                result.loc[mask, "close"] = chunk_series
        return result

    def get_fx_rate(self, from_ccy: str = "GBP", to_ccy: str = "EUR") -> pd.DataFrame:
        """Return daily FX rates as a DataFrame with column ``rate``."""
        cache_key = f"{from_ccy}{to_ccy}"
        if cache_key in self._fx_cache:
            return self._fx_cache[cache_key]
        if self.provider == "yfinance":
            pair = f"{from_ccy}{to_ccy}=X"
            df = yf.download(pair, period="max", progress=False, auto_adjust=True)
            if df.empty:
                raise ValueError(f"No FX data for {pair!r}")
            close = df["Close"]
            if hasattr(close, "columns"):
                close = close.iloc[:, 0]
            result = close.to_frame(name="rate")
            result.index = pd.to_datetime(result.index)
            if result.index.tz is not None:
                result.index = result.index.tz_localize(None)
            result = result.sort_index()
            self._fx_cache[cache_key] = result
            return result
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
        result = df[["rate"]]
        self._fx_cache[cache_key] = result
        return result

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
