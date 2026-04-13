"""
Tests for backend/flights.py.
All Tequila API calls are mocked — no real HTTP calls are made.
"""

import json
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

from main import FlightResultCacheDB
import flights


SAMPLE_FLIGHTS = [
    {"price": 89, "flyFrom": "LHR", "flyTo": "BCN", "duration": {"total": 7200}},
    {"price": 120, "flyFrom": "STN", "flyTo": "BCN", "duration": {"total": 6900}},
]


def _seed_flight_cache(db, fly_from, fly_to, date_from, date_to, curr="EUR", fetched_at=None):
    now = fetched_at or datetime.utcnow()
    cache_key = flights._make_cache_key(fly_from, fly_to, date_from, date_to, curr)
    db.add(FlightResultCacheDB(
        cache_key=cache_key,
        fly_from=fly_from,
        fly_to=fly_to,
        date_from=date_from,
        date_to=date_to,
        result_json=json.dumps(SAMPLE_FLIGHTS),
        fetched_at=now,
        result_count=len(SAMPLE_FLIGHTS),
    ))
    db.commit()


class TestIsoToTequila:
    def test_converts_correctly(self):
        assert flights._iso_to_tequila("2025-08-15") == "15/08/2025"

    def test_leading_zeros_preserved(self):
        assert flights._iso_to_tequila("2025-01-05") == "05/01/2025"


class TestCacheKey:
    def test_same_params_same_key(self):
        k1 = flights._make_cache_key("LHR", "BCN", "2025-08-01", "2025-08-15", "EUR")
        k2 = flights._make_cache_key("LHR", "BCN", "2025-08-01", "2025-08-15", "EUR")
        assert k1 == k2

    def test_different_params_different_key(self):
        k1 = flights._make_cache_key("LHR", "BCN", "2025-08-01", "2025-08-15", "EUR")
        k2 = flights._make_cache_key("LHR", "MAD", "2025-08-01", "2025-08-15", "EUR")
        assert k1 != k2


class TestSearchFlightsFromCity:
    def test_cache_miss_calls_api_and_stores_result(self, db):
        with patch(
            "flights.tequila_client.search_flights",
            return_value=SAMPLE_FLIGHTS,
        ) as mock_api:
            result, from_cache, fetched_at = flights.search_flights_from_city(
                51.5074, -0.1278, "BCN", "2025-08-01", "2025-08-15", db=db
            )

        mock_api.assert_called_once()
        assert result == SAMPLE_FLIGHTS
        assert not from_cache

        row = db.query(FlightResultCacheDB).first()
        assert row is not None
        assert row.result_count == 2

    def test_cache_hit_no_api_call(self, db):
        fly_from = "circle:51.5074,-0.1278:200km"
        _seed_flight_cache(db, fly_from, "BCN", "2025-08-01", "2025-08-15")

        with patch("flights.tequila_client.search_flights") as mock_api:
            result, from_cache, fetched_at = flights.search_flights_from_city(
                51.5074, -0.1278, "BCN", "2025-08-01", "2025-08-15", db=db
            )

        mock_api.assert_not_called()
        assert result == SAMPLE_FLIGHTS
        assert from_cache

    def test_stale_cache_calls_api(self, db):
        fly_from = "circle:51.5074,-0.1278:200km"
        stale_time = datetime.utcnow() - timedelta(minutes=flights.FLIGHT_CACHE_TTL_MINUTES + 5)
        _seed_flight_cache(db, fly_from, "BCN", "2025-08-01", "2025-08-15", fetched_at=stale_time)

        with patch(
            "flights.tequila_client.search_flights",
            return_value=SAMPLE_FLIGHTS,
        ) as mock_api:
            result, from_cache, fetched_at = flights.search_flights_from_city(
                51.5074, -0.1278, "BCN", "2025-08-01", "2025-08-15", db=db
            )

        mock_api.assert_called_once()
        assert result == SAMPLE_FLIGHTS
        assert not from_cache

    def test_circle_string_construction(self, db):
        with patch(
            "flights.tequila_client.search_flights",
            return_value=[],
        ) as mock_api:
            flights.search_flights_from_city(
                48.8566, 2.3522, "BCN", "2025-08-01", "2025-08-15",
                radius_km=150, db=db,
            )

        args, kwargs = mock_api.call_args
        assert kwargs.get("fly_from") == "circle:48.8566,2.3522:150km"

    def test_no_db_skips_cache(self):
        with patch(
            "flights.tequila_client.search_flights",
            return_value=SAMPLE_FLIGHTS,
        ) as mock_api:
            result, from_cache, fetched_at = flights.search_flights_from_city(
                51.5074, -0.1278, "BCN", "2025-08-01", "2025-08-15", db=None
            )

        mock_api.assert_called_once()
        assert result == SAMPLE_FLIGHTS
        assert not from_cache


class TestSearchFlightsFromAirports:
    def test_joins_iata_codes(self, db):
        with patch(
            "flights.tequila_client.search_flights",
            return_value=[],
        ) as mock_api:
            flights.search_flights_from_airports(
                ["LHR", "LGW", "STN"], "BCN", "2025-08-01", "2025-08-15", db=db
            )

        args, kwargs = mock_api.call_args
        assert kwargs.get("fly_from") == "LHR,LGW,STN"
