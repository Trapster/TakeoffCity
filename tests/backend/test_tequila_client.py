"""
Tests for backend/tequila_client.py.
All tests mock requests.get — no real HTTP calls are made.
TEQUILA_API_KEY is patched to a dummy value so the key-guard does not fire.
"""

from unittest.mock import patch, MagicMock

import pytest
import requests

import tequila_client


# ── Helpers ───────────────────────────────────────────────────────────────────

DUMMY_KEY = "test-api-key"


def _mock_response(json_data: dict, status_code: int = 200) -> MagicMock:
    mock = MagicMock()
    mock.status_code = status_code
    mock.json.return_value = json_data
    if status_code >= 400:
        mock.raise_for_status.side_effect = requests.HTTPError(response=mock)
    else:
        mock.raise_for_status.return_value = None
    return mock


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestQueryLocations:
    def test_returns_locations_list(self):
        payload = {"locations": [{"id": "LHR", "name": "Heathrow"}]}
        with patch("tequila_client.TEQUILA_API_KEY", DUMMY_KEY), \
             patch("requests.get", return_value=_mock_response(payload)) as mock_get:
            result = tequila_client.query_locations("london")

        assert result == [{"id": "LHR", "name": "Heathrow"}]
        mock_get.assert_called_once()

    def test_empty_locations_key_returns_empty_list(self):
        with patch("tequila_client.TEQUILA_API_KEY", DUMMY_KEY), \
             patch("requests.get", return_value=_mock_response({})):
            result = tequila_client.query_locations("nowhere")
        assert result == []

    def test_missing_api_key_raises_runtime_error(self):
        with patch("tequila_client.TEQUILA_API_KEY", ""):
            with pytest.raises(RuntimeError, match="TEQUILA_API_KEY"):
                tequila_client.query_locations("london")


class TestSearchFlights:
    def test_returns_data_list(self):
        payload = {"data": [{"price": 99, "flyFrom": "LHR", "flyTo": "BCN"}]}
        with patch("tequila_client.TEQUILA_API_KEY", DUMMY_KEY), \
             patch("requests.get", return_value=_mock_response(payload)):
            result = tequila_client.search_flights(
                fly_from="LHR", fly_to="BCN",
                date_from="01/08/2025", date_to="15/08/2025",
            )
        assert result == [{"price": 99, "flyFrom": "LHR", "flyTo": "BCN"}]

    def test_http_error_propagates(self):
        with patch("tequila_client.TEQUILA_API_KEY", DUMMY_KEY), \
             patch("requests.get", return_value=_mock_response({}, status_code=401)):
            with pytest.raises(requests.HTTPError):
                tequila_client.search_flights(
                    fly_from="LHR", fly_to="BCN",
                    date_from="01/08/2025", date_to="15/08/2025",
                )

    def test_request_timeout_is_set(self):
        payload = {"data": []}
        with patch("tequila_client.TEQUILA_API_KEY", DUMMY_KEY), \
             patch("requests.get", return_value=_mock_response(payload)) as mock_get:
            tequila_client.search_flights(
                fly_from="LHR", fly_to="BCN",
                date_from="01/08/2025", date_to="15/08/2025",
            )
        _, kwargs = mock_get.call_args
        assert kwargs.get("timeout") == tequila_client.REQUEST_TIMEOUT
