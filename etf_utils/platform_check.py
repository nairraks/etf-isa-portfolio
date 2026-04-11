"""Check ETF availability on the InvestEngine and Trading 212 platforms."""

import os
import requests
import pandas as pd
import base64

from .database import (
    save_trading212_instruments, 
    load_trading212_instruments,
    save_investengine_instruments,
    load_investengine_instruments
)

_INVESTENGINE_URL = "https://investengine.com/api/v0.31/public/securities/"
_TRADING212_URL = "https://live.trading212.com/api/v0/equity/metadata/instruments"

# In-memory caches to avoid repeated DB reads in a single session
_ie_cache = None
_t212_cache = None

def get_investengine_instruments() -> pd.DataFrame:
    """Fetch and cache InvestEngine instruments from the db, grabbing them if missing."""
    global _ie_cache
    if _ie_cache is not None:
        return _ie_cache
        
    cached_df = load_investengine_instruments()
    if not cached_df.empty:
        _ie_cache = cached_df
        return _ie_cache
        
    try:
        resp = requests.get(_INVESTENGINE_URL, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        instruments = data.get("results", data) if isinstance(data, dict) else data
        df = pd.DataFrame(instruments)
        save_investengine_instruments(df)
        _ie_cache = df
        return _ie_cache
    except (requests.RequestException, ValueError) as e:
        print(f"Error fetching InvestEngine instruments: {e}")
        return pd.DataFrame()

def get_trading212_instruments() -> pd.DataFrame:
    """Fetch and cache Trading 212 instruments from the db, grabbing them if missing."""
    global _t212_cache
    if _t212_cache is not None:
        return _t212_cache
        
    cached_df = load_trading212_instruments()
    if not cached_df.empty:
        _t212_cache = cached_df
        return _t212_cache
        
    api_key = os.getenv("TRADING212_API_KEY")
    api_secret = os.getenv("TRADING212_API_SECRET")
    if not api_key or not api_secret:
        print("Warning: TRADING212_API_KEY or TRADING212_API_SECRET not found in environment.")
        return pd.DataFrame()
        
    auth_str = base64.b64encode(f"{api_key}:{api_secret}".encode()).decode()
    headers = {"Authorization": f"Basic {auth_str}"}
    try:
        resp = requests.get(_TRADING212_URL, headers=headers, timeout=15)
        resp.raise_for_status()
        instruments = resp.json()
        df = pd.DataFrame(instruments)
        save_trading212_instruments(df)
        _t212_cache = df
        return _t212_cache
    except (requests.RequestException, ValueError) as e:
        print(f"Error fetching Trading212 instruments: {e}")
        return pd.DataFrame()

def check_investengine_availability(ticker: str) -> bool:
    """Return True if the fund is tradeable on InvestEngine."""
    df = get_investengine_instruments()
    if df.empty:
        return False
        
    ticker_upper = ticker.upper()
    if 'ticker' in df.columns:
        if (df['ticker'].str.upper() == ticker_upper).any():
            return True
    return False

def check_trading212_availability(ticker: str) -> bool:
    """Return True if the fund is tradeable on Trading 212."""
    df = get_trading212_instruments()
    if df.empty:
        return False
        
    ticker_upper = ticker.upper()
    if 'ticker' in df.columns:
        if (df['ticker'].str.upper() == ticker_upper).any():
            return True
            
    if 'shortName' in df.columns:
        if (df['shortName'].str.upper() == ticker_upper).any():
            return True
            
    return False

def check_etf_availability(
    ticker: str,
    name: str = None,
    url: str = _INVESTENGINE_URL,
    timeout: int = 15,
) -> bool:
    """DEPRECATED: Use check_platform instead.
    Return True if the fund is tradeable on InvestEngine using cached data.
    """
    return check_investengine_availability(ticker)

def check_platform(ticker: str, name: str = None) -> str:
    """Check availability on platforms, preferring InvestEngine."""
    if check_investengine_availability(ticker):
        return "InvestEngine"
    if check_trading212_availability(ticker):
        return "Trading212"
    return None
