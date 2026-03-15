"""Tests for etf_utils.platform_check — InvestEngine availability."""

from unittest.mock import patch, MagicMock

import pytest
import requests as req_lib

from etf_utils.platform_check import check_etf_availability


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
def test_etf_304_not_modified(mock_get):
    """HTTP 304 Not Modified → True (previous result assumed valid)."""
    mock_resp = MagicMock()
    mock_resp.status_code = 304
    mock_resp.raise_for_status.side_effect = None
    mock_get.return_value = mock_resp

    assert check_etf_availability("VEVE") is True


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
