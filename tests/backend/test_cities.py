from unittest.mock import patch

MOCK_LOCATIONS = [
    {"id": "LON", "name": "London", "country": {"code": "GB"}, "location": {"lat": 51.5, "lon": -0.1}},
    {"id": "LDY", "name": "Londonderry", "country": {"code": "GB"}, "location": {"lat": 54.9, "lon": -7.3}},
]


def test_cities_search_returns_results(client):
    with patch("tequila_client.query_locations", return_value=MOCK_LOCATIONS):
        r = client.get("/cities/search?q=London")
    assert r.status_code == 200
    data = r.json()
    assert "cities" in data
    assert len(data["cities"]) == 2
    assert data["cities"][0]["name"] == "London"
    assert data["cities"][0]["country_code"] == "GB"
    assert data["cities"][0]["id"] == "LON"


def test_cities_search_empty_query_returns_empty(client):
    r = client.get("/cities/search?q=")
    assert r.status_code == 200
    assert r.json()["cities"] == []


def test_cities_search_single_char_returns_empty(client):
    r = client.get("/cities/search?q=L")
    assert r.status_code == 200
    assert r.json()["cities"] == []


def test_cities_search_no_results(client):
    with patch("tequila_client.query_locations", return_value=[]):
        r = client.get("/cities/search?q=Xyzzy")
    assert r.status_code == 200
    assert r.json()["cities"] == []
