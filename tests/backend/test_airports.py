"""
Tests for backend/airports.py.
All Tequila API calls are mocked — no real HTTP calls are made.
"""

from datetime import datetime, timedelta
from unittest.mock import patch, call

import pytest

from main import AirportCacheDB
import airports


# ── Fixtures / shared data ────────────────────────────────────────────────────

CITY_RESPONSE = [{
    "id": "london_gb",
    "name": "London",
    "location": {"lat": 51.5074, "lon": -0.1278},
}]

AIRPORT_RESPONSE = [
    {
        "id": "LHR",
        "name": "London Heathrow",
        "city": {"name": "London"},
        "location": {"lat": 51.4775, "lon": -0.4614},
    },
    {
        "id": "LGW",
        "name": "London Gatwick",
        "city": {"name": "Crawley"},
        "location": {"lat": 51.1537, "lon": -0.1821},
    },
]


def _patch_locations(city_resp=None, airport_resp=None):
    """Return a side_effect function for tequila_client.query_locations."""
    city_resp = city_resp if city_resp is not None else CITY_RESPONSE
    airport_resp = airport_resp if airport_resp is not None else AIRPORT_RESPONSE

    def _side_effect(term, location_types="airport", **kwargs):
        if location_types == "city":
            return city_resp
        return airport_resp

    return _side_effect


def _seed_cache(db, city_query="london", radius_km=200, fetched_at=None):
    now = fetched_at or datetime.utcnow()
    for apt in AIRPORT_RESPONSE:
        db.add(AirportCacheDB(
            city_query=city_query,
            iata_code=apt["id"],
            airport_name=apt["name"],
            city_name=apt["city"]["name"],
            latitude=apt["location"]["lat"],
            longitude=apt["location"]["lon"],
            distance_km=25.0,
            radius_km=radius_km,
            fetched_at=now,
        ))
    db.commit()


# ── Cache miss / hit ──────────────────────────────────────────────────────────

class TestGetAirportsForCity:
    def test_cache_miss_calls_api_and_stores_rows(self, db):
        with patch(
            "airports.tequila_client.query_locations",
            side_effect=_patch_locations(),
        ) as mock_api:
            result, from_cache, fetched_at = airports.get_airports_for_city("London", db)

        # Two API calls: one for city geocoding, one for airports
        assert mock_api.call_count == 2
        assert any(
            c == call("london", location_types="city", limit=1)
            for c in mock_api.call_args_list
        )

        # Results returned correctly
        assert not from_cache
        iata_codes = {a["iata_code"] for a in result}
        assert iata_codes == {"LHR", "LGW"}

        # Rows persisted in DB
        rows = db.query(AirportCacheDB).filter_by(city_query="london").all()
        assert len(rows) == 2

    def test_cache_hit_within_ttl_no_api_call(self, db):
        _seed_cache(db)  # fresh rows

        with patch("airports.tequila_client.query_locations") as mock_api:
            result, from_cache, fetched_at = airports.get_airports_for_city("London", db)

        mock_api.assert_not_called()
        assert from_cache
        assert len(result) == 2

    def test_stale_cache_triggers_refresh(self, db):
        stale_time = datetime.utcnow() - timedelta(days=airports.AIRPORT_CACHE_TTL_DAYS + 1)
        _seed_cache(db, fetched_at=stale_time)

        with patch(
            "airports.tequila_client.query_locations",
            side_effect=_patch_locations(),
        ) as mock_api:
            result, from_cache, fetched_at = airports.get_airports_for_city("London", db)

        assert mock_api.call_count == 2
        assert not from_cache

        # Rows should have an updated fetched_at
        rows = db.query(AirportCacheDB).filter_by(city_query="london").all()
        for row in rows:
            assert row.fetched_at > stale_time

    def test_city_not_found_returns_empty(self, db):
        with patch(
            "airports.tequila_client.query_locations",
            side_effect=_patch_locations(city_resp=[]),
        ):
            result, from_cache, fetched_at = airports.get_airports_for_city("NoSuchCity", db)

        assert result == []
        assert not from_cache

    def test_normalisation_case_insensitive(self, db):
        _seed_cache(db, city_query="london")

        with patch("airports.tequila_client.query_locations") as mock_api:
            r1, *_ = airports.get_airports_for_city("LONDON", db)
            r2, *_ = airports.get_airports_for_city("  London  ", db)

        mock_api.assert_not_called()
        assert len(r1) == len(r2) == 2


class TestRefreshAirportCache:
    def test_force_refresh_ignores_ttl(self, db):
        _seed_cache(db)  # fresh rows — would normally skip API

        with patch(
            "airports.tequila_client.query_locations",
            side_effect=_patch_locations(),
        ) as mock_api:
            count = airports.refresh_airport_cache("london", db)

        assert mock_api.call_count == 2
        assert count == 2


class TestHaversine:
    def test_london_paris_approx_340km(self):
        # London (51.5074, -0.1278) → Paris (48.8566, 2.3522) ≈ 340 km
        dist = airports._haversine_km(51.5074, -0.1278, 48.8566, 2.3522)
        assert 330 < dist < 350

    def test_same_point_is_zero(self):
        dist = airports._haversine_km(51.5, -0.1, 51.5, -0.1)
        assert dist == pytest.approx(0.0, abs=0.01)
