"""Tests for etf_utils.platform_check — InvestEngine availability."""

from unittest.mock import patch, MagicMock

import pytest
import pandas as pd
import requests as req_lib

from etf_utils.platform_check import (
    check_etf_availability,
    check_investengine_availability,
    check_platform,
)
import etf_utils.platform_check as pc


@pytest.fixture(autouse=True)
def _clear_caches():
    """Reset module-level caches between tests."""
    pc._ie_cache = None
    pc._t212_cache = None
    yield
    pc._ie_cache = None
    pc._t212_cache = None


@patch("etf_utils.platform_check.requests.get")
def test_etf_available(mock_get):
    """API returning a non-empty list → True."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = [{"name": "Vanguard FTSE", "ticker": "VEVE"}]
    mock_get.return_value = mock_resp

    assert check_etf_availability("VEVE") is True
    mock_get.assert_called_once()


@patch("etf_utils.platform_check.requests.get")
def test_etf_not_available(mock_get):
    """API returning an empty list → False."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = []
    mock_get.return_value = mock_resp

    assert check_etf_availability("FAKEETF") is False


@patch("etf_utils.platform_check.requests.get")
def test_etf_api_error(mock_get):
    """Network or API error → False (graceful degradation)."""
    mock_get.side_effect = req_lib.ConnectionError("Network down")

    assert check_etf_availability("VEVE") is False


@patch("etf_utils.platform_check.requests.get")
def test_etf_no_exact_ticker_match(mock_get):
    """API returns results but none match the requested ticker → False.

    Guards against the full-text search returning an unrelated ETC whose
    description mentions the search term (e.g. searching 'CRUD' returns
    a broad commodities ETC with ticker 'AGCP').
    """
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = [{"ticker": "AGCP", "title": "WisdomTree Broad Commodities"}]
    mock_get.return_value = mock_resp

    assert check_etf_availability("CRUD") is False


@patch("etf_utils.platform_check.requests.get")
def test_check_investengine_case_insensitive(mock_get):
    """Ticker matching is case-insensitive."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = [{"ticker": "veve", "name": "Vanguard FTSE"}]
    mock_get.return_value = mock_resp

    assert check_investengine_availability("VEVE") is True


@patch("etf_utils.platform_check.requests.get")
def test_check_platform_returns_investengine(mock_get):
    """check_platform returns 'InvestEngine' when available there."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = [{"ticker": "VEVE", "name": "Vanguard FTSE"}]
    mock_get.return_value = mock_resp

    assert check_platform("VEVE") == "InvestEngine"


@patch("etf_utils.platform_check.requests.get")
def test_check_platform_not_found(mock_get):
    """check_platform returns None when not on any platform."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = []
    mock_get.return_value = mock_resp

    assert check_platform("FAKEETF") is None


def test_invalid_ticker():
    """Empty or non-string ticker → False."""
    assert check_etf_availability("") is False
    assert check_etf_availability(None) is False
