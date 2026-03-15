"""Check ETF availability on the InvestEngine platform."""

import requests

_INVESTENGINE_URL = "https://investengine.com/api/v0.31/public/securities/"


def check_etf_availability(
    ticker: str,
    url: str = _INVESTENGINE_URL,
    timeout: int = 10,
) -> bool:
    """Return True if *ticker* is listed on InvestEngine.

    Searches the InvestEngine public securities API and checks that at least
    one returned result has a ``ticker`` field that exactly matches the
    requested ticker (case-insensitive).  A fuzzy ``len(results) > 0``
    check is deliberately avoided because the API performs a full-text
    search: e.g. searching "CRUD" can return an unrelated ETC whose
    description mentions crude oil.

    Returns False if the ticker is not listed or the request fails.
    """
    try:
        resp = requests.get(url, params={"search": ticker}, timeout=timeout)
        if resp.status_code == 304:
            # Not Modified — assume previously found result is still valid
            return True
        resp.raise_for_status()
        data = resp.json()
        results = data.get("results", data) if isinstance(data, dict) else data
        return any(
            r.get("ticker", "").upper() == ticker.upper()
            for r in results
            if isinstance(r, dict)
        )
    except (requests.RequestException, ValueError):
        return False
