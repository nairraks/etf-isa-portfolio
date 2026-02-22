"""Check ETF availability on the InvestEngine platform."""

import requests

_INVESTENGINE_URL = "https://investengine.com/api/v0.29/public/securities/"


def check_etf_availability(
    etf_name: str,
    url: str = _INVESTENGINE_URL,
    timeout: int = 10,
) -> bool:
    """Return True if *etf_name* is found on InvestEngine.

    Searches the InvestEngine public securities API by ETF name.
    Returns False if the ETF is not listed or the request fails.
    """
    try:
        resp = requests.get(url, params={"search": etf_name}, timeout=timeout)
        if resp.status_code == 304:
            # Not Modified — assume previously found result is still valid
            return True
        resp.raise_for_status()
        data = resp.json()
        results = data.get("results", data) if isinstance(data, dict) else data
        return len(results) > 0
    except (requests.RequestException, ValueError):
        return False
