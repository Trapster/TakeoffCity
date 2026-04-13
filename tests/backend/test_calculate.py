"""
Tests for the calculate endpoint and the calculate module.
All Tequila API calls are mocked — no real HTTP calls are made.
"""

import json
from datetime import datetime
from unittest.mock import patch

import pytest

import calculate
from main import EventDB, FeedbackDB


# ── Helpers ───────────────────────────────────────────────────────────────────

def _create_event(client):
    r = client.post(
        "/events",
        json={"name": "Trip", "earliest_date": "2024-06-01", "latest_date": "2024-06-30"},
        headers={"X-Username": "alice"},
    )
    return r.json()["event_id"]


def _add_feedback(client, event_id, city, email=None):
    client.post(
        f"/events/{event_id}/feedback",
        json={"city": city, "adults": 1, "children": 0, "attendee_email": email},
    )


_MOCK_FLIGHT_LIST = [
    {
        "price": 120.0,
        "duration": {"total": 7200},
        "route": [{"flyFrom": "LHR", "flyTo": "CDG"}],
        "deep_link": "https://kiwi.com/booking/1",
    }
]
# search_flights_from_city now returns (flights, from_cache, fetched_at)
MOCK_FLIGHTS = (_MOCK_FLIGHT_LIST, False, datetime(2024, 1, 1))

MOCK_LOCATION = [{"location": {"lat": 51.5, "lon": -0.1}, "name": "London"}]


# ── Endpoint: calculate ───────────────────────────────────────────────────────

def test_calculate_event_not_found(client):
    r = client.post("/calculate/nonexistent-id")
    assert r.status_code == 404


def test_calculate_marks_event_calculated(client):
    event_id = _create_event(client)
    _add_feedback(client, event_id, "London", "alice@example.com")

    r = client.get(f"/events/{event_id}", headers={"X-Username": "alice"})
    assert r.json()["calculated"] is False

    with (
        patch("tequila_client.query_locations", return_value=MOCK_LOCATION),
        patch("flights.search_flights_from_city", return_value=MOCK_FLIGHTS),
    ):
        client.post(f"/calculate/{event_id}")

    r2 = client.get(f"/events/{event_id}", headers={"X-Username": "alice"})
    assert r2.json()["calculated"] is True


def test_calculate_streams_text_plain(client):
    event_id = _create_event(client)
    _add_feedback(client, event_id, "London", "alice@example.com")
    with (
        patch("tequila_client.query_locations", return_value=MOCK_LOCATION),
        patch("flights.search_flights_from_city", return_value=MOCK_FLIGHTS),
    ):
        r = client.post(f"/calculate/{event_id}")
    assert r.status_code == 200
    assert "text/plain" in r.headers["content-type"]
    assert len(r.text) > 0


def test_calculate_no_feedbacks_does_not_set_calculated(client):
    event_id = _create_event(client)
    # No feedbacks added
    client.post(f"/calculate/{event_id}")
    r = client.get(f"/events/{event_id}", headers={"X-Username": "alice"})
    assert r.json()["calculated"] is False


# ── Endpoint: get results ─────────────────────────────────────────────────────

def test_get_results_before_calculation_returns_404(client):
    event_id = _create_event(client)
    r = client.get(f"/events/{event_id}/results")
    assert r.status_code == 404


def test_get_results_nonexistent_event(client):
    r = client.get("/events/nonexistent/results")
    assert r.status_code == 404


def test_get_results_after_calculation_returns_json(client):
    event_id = _create_event(client)
    _add_feedback(client, event_id, "London", "alice@example.com")

    with (
        patch("tequila_client.query_locations", return_value=MOCK_LOCATION),
        patch("flights.search_flights_from_city", return_value=MOCK_FLIGHTS),
    ):
        client.post(f"/calculate/{event_id}")

    r = client.get(f"/events/{event_id}/results")
    assert r.status_code == 200
    data = r.json()
    assert "destinations" in data
    assert "total_responses" in data
    assert data["total_responses"] == 1


def test_get_results_has_expected_shape(client):
    event_id = _create_event(client)
    _add_feedback(client, event_id, "London", "alice@example.com")
    _add_feedback(client, event_id, "Paris",  "bob@example.com")

    def mock_location(term, **kwargs):
        return [{"location": {"lat": 51.5, "lon": -0.1}, "name": term}]

    with (
        patch("tequila_client.query_locations", side_effect=mock_location),
        patch("flights.search_flights_from_city", return_value=MOCK_FLIGHTS),
    ):
        client.post(f"/calculate/{event_id}")

    r = client.get(f"/events/{event_id}/results")
    assert r.status_code == 200
    data = r.json()

    assert isinstance(data["destinations"], list)
    if data["destinations"]:
        dest = data["destinations"][0]
        assert "iata"          in dest
        assert "city_name"     in dest
        assert "country_code"  in dest
        assert "coverage"      in dest
        assert "strategy_scores" in dest
        assert "per_person"    in dest
        assert "rank_cheapest" in dest
        assert "rank_fairest"  in dest
        assert "rank_fastest"  in dest

        pp = dest["per_person"][0]
        assert "identifier"  in pp
        assert "origin_city" in pp
        assert "can_reach"   in pp


# ── Unit tests: pure helpers ──────────────────────────────────────────────────

class TestCoverageThreshold:
    def test_n1(self):
        assert calculate._coverage_threshold(1) == 1

    def test_n2(self):
        assert calculate._coverage_threshold(2) == 1

    def test_n5(self):
        assert calculate._coverage_threshold(5) == 4

    def test_n10(self):
        assert calculate._coverage_threshold(10) == 8

    def test_n3(self):
        assert calculate._coverage_threshold(3) == 2

    def test_large(self):
        # n-1 always <= ceil(0.8*n) for n >= 6
        assert calculate._coverage_threshold(20) == 16


class TestCoefficientOfVariation:
    def test_identical_prices_returns_zero(self):
        assert calculate._coefficient_of_variation([100, 100, 100]) == 0.0

    def test_single_price_returns_zero(self):
        assert calculate._coefficient_of_variation([100]) == 0.0

    def test_empty_returns_zero(self):
        assert calculate._coefficient_of_variation([]) == 0.0

    def test_varied_prices(self):
        cv = calculate._coefficient_of_variation([100, 200])
        assert cv > 0.3  # high spread

    def test_zero_mean(self):
        assert calculate._coefficient_of_variation([0, 0]) == 0.0


class TestCheapest:
    def test_returns_cheapest(self):
        flights = [{"price": 200}, {"price": 50}, {"price": 150}]
        assert calculate._cheapest(flights) == {"price": 50}

    def test_empty_returns_none(self):
        assert calculate._cheapest([]) is None

    def test_single_item(self):
        f = [{"price": 99}]
        assert calculate._cheapest(f) == {"price": 99}
