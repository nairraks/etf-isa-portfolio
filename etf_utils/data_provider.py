"""Unified data provider: yfinance (default) or AlphaVantage."""

import datetime
import json
import warnings

import pandas as pd
import requests
import yfinance as yf

from .config import ALPHAVANTAGE_API_KEY, DATA_PROVIDER, FRED_API_KEY

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

    if not symbol or not isinstance(symbol, str):
        return symbol

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
    if symbol in {"SPY", "ASHR", "EWY", "EIDO"}:
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
        self._currency_units = self._load_currency_units()
        self._setup_yf_cache()

    @staticmethod
    def _load_currency_units() -> dict:
        """Load explicit GBX/GBP mappings from data/config/currency_units.json."""
        from .config import DATA_CONFIG

        path = DATA_CONFIG / "currency_units.json"
        if path.exists():
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        return {}

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

        # --- FRED API HANDLING ---
        if symbol.upper().startswith("FRED:"):
            from pathlib import Path
            
            series_id = symbol.split(":")[1]
            cache_dir = Path("data/intermediate")
            cache_dir.mkdir(parents=True, exist_ok=True)
            cache_file = cache_dir / f"fred_cache_{series_id}.csv"
            
            if cache_file.exists():
                print(f"Loading {symbol} from local FRED cache: {cache_file}")
                df = pd.read_csv(cache_file, index_col=0, parse_dates=True)
                result = df[["close"]]
            else:
                print(f"Fetching {symbol} from FRED (API call)...")
                url = f"https://api.stlouisfed.org/fred/series/observations?series_id={series_id}&api_key={FRED_API_KEY}&file_type=json"
                resp = requests.get(url, timeout=30)
                resp.raise_for_status()
                data = resp.json()
                observations = data.get("observations", [])
                
                if not observations:
                    raise ValueError(f"No FRED data for {symbol!r}. Check API key and series ID.")
                
                df = pd.DataFrame(observations)
                df['date'] = pd.to_datetime(df['date'])
                df['value'] = pd.to_numeric(df['value'], errors='coerce')
                df = df.rename(columns={"value": "close"})
                df = df.set_index("date").sort_index()
                result = df[["close"]].dropna()
                
                result.to_csv(cache_file)
                print(f"Saved {symbol} to local cache: {cache_file}")
                
            self._price_cache[cache_key] = result
            if start_date:
                result = result[result.index >= pd.to_datetime(start_date)]
            if end_date:
                result = result[result.index <= pd.to_datetime(end_date)]
            return result

        # --- DYNAMIC COMMODITY HANDLING ---
        # Intercept specialized Alpha Vantage commodity functions (GOLD, SILVER, WTI, etc.)
        AV_COMMODITY_FUNCTIONS = {
            "GOLD": "GOLD_SILVER_HISTORY",
            "SILVER": "GOLD_SILVER_HISTORY",
            "WTI": "WTI",
            "BRENT": "BRENT",
            "COPPER": "COPPER",
            "ALUMINUM": "ALUMINUM",
            "WHEAT": "WHEAT",
            "CORN": "CORN",
            "NATURAL_GAS": "NATURAL_GAS",
            "SUGAR": "SUGAR",
            "COFFEE": "COFFEE"
        }
        
        if not symbol or not isinstance(symbol, str):
            raise ValueError(f"Invalid symbol: {symbol!r}")

        up_sym = symbol.upper()
        if up_sym in AV_COMMODITY_FUNCTIONS:
            func = AV_COMMODITY_FUNCTIONS[up_sym]
            print(f"Fetching commodity {up_sym} from AlphaVantage via {func}...")
            params = {"function": func, "interval": "monthly", "apikey": ALPHAVANTAGE_API_KEY}
            if func == "GOLD_SILVER_HISTORY":
                params["symbol"] = up_sym
            
            resp = requests.get(_AV_BASE, params=params, timeout=30)
            resp.raise_for_status()
            raw_data = resp.json()
            
            # Aluminum/Copper etc. use "data" key, Metals use "data" key too for HISTORY
            data_list = raw_data.get("data", [])
            if not data_list:
                raise ValueError(f"No commodity data for {up_sym!r}. Response: {raw_data}")
            
            df = pd.DataFrame(data_list)
            df["date"] = pd.to_datetime(df["date"])
            # Some use 'value', metals use 'price'
            val_col = 'price' if 'price' in df.columns else 'value'
            df = df.rename(columns={val_col: "close"})
            df["close"] = pd.to_numeric(df["close"], errors='coerce')
            df = df.set_index("date").sort_index()
            result = df[["close"]].dropna()
            
            self._price_cache[cache_key] = result
            if start_date:
                result = result[result.index >= pd.to_datetime(start_date)]
            if end_date:
                result = result[result.index <= pd.to_datetime(end_date)]
            return result

        # --- EXISTING INTERCEPTS ---
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
                # The book's methodology is built around LSE-listed UCITS ETFs
                # (tickers ending in .L), which report in GBP/GBX. For any
                # non-LSE ticker the returned price series will be in the
                # listing exchange's currency (typically USD) — this pipeline
                # does NOT apply an FX conversion, so results carry embedded
                # currency exposure that the book does not strip out. We emit
                # a single warning so users are aware of that boundary.
                if "." in sym and not sym.upper().endswith(".L"):
                    warnings.warn(
                        f"{sym!r} is not an LSE (.L) listing — its price series "
                        "will be in the listing-exchange currency (typically USD). "
                        "This pipeline does not FX-convert to GBP; the returned "
                        "data carries unhedged currency exposure that the book's "
                        "methodology does not account for.",
                        stacklevel=2,
                    )
                elif "." not in sym and sym.upper() in {"SPY", "ASHR", "EWY", "EIDO"}:
                    # These are the explicitly bypassed US-listed tickers in
                    # _normalize_symbol — same FX caveat applies.
                    warnings.warn(
                        f"{sym!r} is a non-LSE (US-listed) ticker — its price "
                        "series will be in USD. This pipeline does not FX-convert "
                        "to GBP; the returned data carries unhedged currency "
                        "exposure that the book's methodology does not account for.",
                        stacklevel=2,
                    )
                kwargs = {"progress": False, "auto_adjust": True}
                if start_date:
                    kwargs["start"] = start_date
                if end_date:
                    # yfinance treats end as exclusive; add 1 day so the
                    # requested end_date is included in the result.
                    end_dt = pd.to_datetime(end_date) + pd.Timedelta(days=1)
                    kwargs["end"] = end_dt.strftime("%Y-%m-%d")
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
        """Ensure all LSE-specific data is normalized from pence to pounds.

        Primary: uses the explicit mapping in data/config/currency_units.json.
        Fallback: heuristic median-based detection with a warning for unknown tickers.
        """
        if not (sym.endswith(".L") or sym.endswith(".LON")) or len(result) == 0:
            return result

        # Extract bare ticker (e.g. "AUAD.L" -> "AUAD")
        sym = sym.strip()
        bare = sym.split(".")[0].upper()

        # --- Primary: explicit config lookup ---
        provider_units = self._currency_units.get(self.provider, {})
        # Normalize keys in provider_units for case-insensitive lookup
        provider_units_upper = {k.upper(): v for k, v in provider_units.items()}
        unit = provider_units_upper.get(bare)

        if unit is not None:
            if unit.upper() == "GBX":
                result = result.copy()
                result["close"] = result["close"] / 100
            # GBP -> no change needed
            return result

        # --- Fallback: heuristic for unknown tickers ---
        warnings.warn(
            f"Ticker {bare!r} for provider {self.provider!r} not found in currency_units.json. "
            f"Falling back to heuristic pence detection. ",
            stacklevel=3,
        )

        import numpy as np

        prev_prices = result["close"].shift(1)
        with np.errstate(divide="ignore", invalid="ignore"):
            ratio = result["close"] / prev_prices

        is_jump = (ratio > 50) | (ratio < 0.02)
        jump_indices = list(result.index[is_jump])

        boundaries = (
            [result.index[0]]
            + jump_indices
            + [result.index[-1] + pd.Timedelta(days=1)]
        )

        chunks = []
        for i in range(len(boundaries) - 1):
            chunk_start = boundaries[i]
            chunk_end = boundaries[i + 1]
            mask = (result.index >= chunk_start) & (result.index < chunk_end)
            if not mask.any():
                continue
            chunk_median = result.loc[mask, "close"].median()
            chunks.append((mask, chunk_median))

        if len(chunks) > 1:
            min_median = min(c[1] for c in chunks)
            for mask, chunk_median in chunks:
                chunk_series = result.loc[mask, "close"]
                for _ in range(3):
                    if chunk_median / max(min_median, 1e-9) > 50:
                        chunk_series = chunk_series / 100
                        chunk_median = chunk_series.median()
                    else:
                        break
                result.loc[mask, "close"] = chunk_series
        elif chunks:
            mask = chunks[0][0]
            chunk_series = result.loc[mask, "close"]
            for _ in range(3):
                if chunk_series.median() > 100:
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
            # Expand backwards slightly so we can anchor the base price safely to
            # the last officially closed trading day immediately preceding or exactly on `start`.
            start_dt = pd.to_datetime(start)
            query_start = (start_dt - pd.Timedelta(days=10)).strftime("%Y-%m-%d")
            df = self.get_historical_prices(symbol, start_date=query_start, end_date=end)
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
        
        # Base price: last available close <= start_date
        base_df = df[df.index <= start_dt]
        if base_df.empty:
            start_price = df["close"].iloc[0]
        else:
            start_price = base_df["close"].iloc[-1]
            
        end_price = df["close"].iloc[-1]
        return (end_price - start_price) / start_price
