"""
Tequila (Kiwi.com) API client.

Authentication note
-------------------
The TEQUILA_DEEPLINKS_AND_BANNERS env var holds the API key registered under
Kiwi's Deeplinks & Banners product tier. The Locations API below should be
accessible with this key. The full Search API (/v2/search) may require a
separate key registered via the Tequila platform at tequila.kiwi.com — if you
receive 401 errors on flight searches, verify your key tier there.
"""

import os
import requests

TEQUILA_API_KEY = os.getenv("TEQUILA_API_KEY", "")
LOCATIONS_BASE  = "https://api.tequila.kiwi.com/locations/query"
SEARCH_BASE     = "https://api.tequila.kiwi.com/v2/search"
REQUEST_TIMEOUT = 10  # seconds


def _auth_headers() -> dict:
    if not TEQUILA_API_KEY:
        raise RuntimeError(
            "TEQUILA_API_KEY env var is not set. "
            "Register at tequila.kiwi.com to obtain a metasearch API key."
        )
    return {"apikey": TEQUILA_API_KEY}


def query_locations(
    term: str,
    location_types: str = "airport",
    radius: int = 200,
    active_only: bool = True,
    limit: int = 50,
) -> list[dict]:
    """
    Query the Tequila Locations API.

    Returns the list of location objects from the 'locations' key of the
    response. Each object contains at minimum: id (IATA), name, type,
    and coordinates (lat/lon nested under 'location').

    Args:
        term:           City or airport name to search for.
        location_types: 'airport', 'city', or comma-separated combination.
        radius:         Search radius in km around the matched location.
        active_only:    Only return currently operating locations.
        limit:          Maximum number of results.
    """
    params = {
        "term": term,
        "location_types": location_types,
        "active_only": str(active_only).lower(),
        "limit": limit,
    }
    if location_types == "airport":
        params["radius"] = radius

    response = requests.get(
        LOCATIONS_BASE,
        params=params,
        headers=_auth_headers(),
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()
    return response.json().get("locations", [])


def search_flights(
    fly_from: str,
    fly_to: str,
    date_from: str,
    date_to: str,
    curr: str = "EUR",
    limit: int = 200,
    sort: str = "price",
) -> list[dict]:
    """
    Query the Tequila Search API for available flights.

    Args:
        fly_from:  Comma-separated IATA codes OR circle:{lat},{lon}:{radius}km.
        fly_to:    Destination IATA code.
        date_from: Departure date lower bound in dd/mm/yyyy format.
        date_to:   Departure date upper bound in dd/mm/yyyy format.
        curr:      Currency for prices (e.g. 'EUR', 'USD').
        limit:     Max results (Tequila cap is 200).
        sort:      Sort order: 'price', 'duration', or 'quality'.

    Returns the list of flight objects from the 'data' key of the response.
    """
    params = {
        "fly_from":  fly_from,
        "fly_to":    fly_to,
        "date_from": date_from,
        "date_to":   date_to,
        "curr":      curr,
        "limit":     limit,
        "sort":      sort,
    }
    response = requests.get(
        SEARCH_BASE,
        params=params,
        headers=_auth_headers(),
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()
    return response.json().get("data", [])
