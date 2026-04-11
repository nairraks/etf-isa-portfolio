"""Check ETF availability on the InvestEngine platform."""

import requests

_INVESTENGINE_URL = "https://investengine.com/api/v0.31/public/securities/"


def check_etf_availability(
    ticker: str,
    name: str = None,
    url: str = _INVESTENGINE_URL,
    timeout: int = 15,
) -> bool:
    """Return True if the fund is tradeable on InvestEngine.

    Strategy:
    1. Search by exact ticker first.
    2. If name is provided and ticker check fails, search by Name.
    3. Return True if any result in the API search matches the ticker or name.
    """
    try:
        # 1. Try search by ticker
        resp = requests.get(url, params={"search": ticker}, timeout=timeout)
        if resp.status_code == 304:
            # Not Modified — assume previously found result is still valid
            return True
        resp.raise_for_status()

        data = resp.json()
        results = data.get("results", data) if isinstance(data, dict) else data
        
        if any(r.get("ticker", "").upper() == ticker.upper() for r in results if isinstance(r, dict)):
            return True
            
        # 2. Try search by name if provided (fuzzy match)
        if name:
            resp = requests.get(url, params={"search": name}, timeout=timeout)
            resp.raise_for_status()
            data = resp.json()
            results = data.get("results", data) if isinstance(data, dict) else data
            
            for r in results:
                if isinstance(r, dict):
                    title = r.get("title", "").lower()
                    # Check if the fund name is contained within the IE 'title' or vice versa
                    if name.lower() in title or title in name.lower():
                        return True
        
        return False
    except (requests.RequestException, ValueError):
        return False

