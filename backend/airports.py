"""
Airport discovery with persistent DB caching.

Given a city name, returns all airports within a configurable radius, each
annotated with its haversine distance from the city centre. Results are cached
in the airport_cache table with a 30-day TTL; on a cache miss (or stale entry)
the Tequila Locations API is called and the cache is refreshed inline.
"""

import math
import os
from datetime import datetime, timedelta

import tequila_client
from main import AirportCacheDB

AIRPORT_CACHE_TTL_DAYS = 30
DEFAULT_RADIUS_KM = int(os.getenv("AIRPORT_SEARCH_RADIUS_KM", "200"))


# ── Public API ────────────────────────────────────────────────────────────────

def get_airports_for_city(
    city_name: str,
    db,
    radius_km: int = DEFAULT_RADIUS_KM,
) -> tuple[list[dict], bool, datetime]:
    """
    Return (airports, from_cache, fetched_at) for city_name within radius_km.

    airports:   list of dicts with iata_code, airport_name, city_name,
                latitude, longitude, distance_km
    from_cache: True when data was served from the DB cache
    fetched_at: timestamp when the data was fetched (oldest cache row, or now)

    Results are served from the DB cache when fresh (< 30 days old).
    A stale or empty cache triggers an inline refresh before returning.
    """
    city_query = _normalise(city_name)
    rows = _load_cache(city_query, radius_km, db)

    if rows:
        oldest = min(r.fetched_at for r in rows)
        if datetime.utcnow() - oldest <= timedelta(days=AIRPORT_CACHE_TTL_DAYS):
            return [_row_to_dict(r) for r in rows], True, oldest

    # Cache miss or stale — refresh inline
    airports, fetched_at = _fetch_and_cache(city_query, radius_km, db)
    return airports, False, fetched_at


def refresh_airport_cache(
    city_name: str,
    db,
    radius_km: int = DEFAULT_RADIUS_KM,
) -> int:
    """
    Force-refresh the airport cache regardless of TTL.
    Returns the number of airports found and stored.
    """
    city_query = _normalise(city_name)
    airports, _ = _fetch_and_cache(city_query, radius_km, db)
    return len(airports)


# ── Internal helpers ──────────────────────────────────────────────────────────

def _normalise(city_name: str) -> str:
    return city_name.strip().lower()


def _load_cache(city_query: str, radius_km: int, db) -> list:
    return (
        db.query(AirportCacheDB)
        .filter_by(city_query=city_query, radius_km=radius_km)
        .all()
    )


def _fetch_and_cache(city_query: str, radius_km: int, db) -> tuple[list[dict], datetime]:
    """
    1. Geocode the city to get its centre coordinates.
    2. Query airports within radius_km.
    3. Compute haversine distances.
    4. Replace cache rows and commit.
    """
    # Step 1: geocode city centre
    city_results = tequila_client.query_locations(
        city_query, location_types="city", limit=1
    )
    if not city_results:
        return [], datetime.utcnow()

    city_loc = city_results[0]
    city_lat = city_loc["location"]["lat"]
    city_lon = city_loc["location"]["lon"]

    # Step 2: find airports within radius
    airport_results = tequila_client.query_locations(
        city_query,
        location_types="airport",
        radius=radius_km,
        limit=50,
    )

    now = datetime.utcnow()
    airports: list[dict] = []

    for apt in airport_results:
        iata = apt.get("id", "")
        if not iata or len(iata) != 3:
            continue

        apt_lat = apt["location"]["lat"]
        apt_lon = apt["location"]["lon"]
        dist = _haversine_km(city_lat, city_lon, apt_lat, apt_lon)

        apt_city = apt.get("city", {})
        city_name_api = (
            apt_city.get("name", "") if isinstance(apt_city, dict) else ""
        )

        # Hard-filter by haversine distance. The Tequila Locations API matches
        # on airport name text as well as geography, so it can return airports
        # named "London ..." that are in Canada or South Africa. Dropping
        # anything beyond radius_km keeps the list to genuinely reachable
        # departure options.
        if dist > radius_km:
            continue

        airports.append({
            "iata_code":    iata,
            "airport_name": apt.get("name", ""),
            "city_name":    city_name_api,
            "latitude":     apt_lat,
            "longitude":    apt_lon,
            "distance_km":  round(dist, 1),
        })

    # Step 3: replace cache rows
    db.query(AirportCacheDB).filter_by(
        city_query=city_query, radius_km=radius_km
    ).delete()

    for a in airports:
        db.add(AirportCacheDB(
            city_query=city_query,
            iata_code=a["iata_code"],
            airport_name=a["airport_name"],
            city_name=a["city_name"],
            latitude=a["latitude"],
            longitude=a["longitude"],
            distance_km=a["distance_km"],
            radius_km=radius_km,
            fetched_at=now,
        ))

    db.commit()
    return airports, now


def _row_to_dict(row: AirportCacheDB) -> dict:
    return {
        "iata_code":    row.iata_code,
        "airport_name": row.airport_name,
        "city_name":    row.city_name,
        "latitude":     row.latitude,
        "longitude":    row.longitude,
        "distance_km":  row.distance_km,
    }


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Return the great-circle distance in kilometres between two points on Earth.
    Uses the haversine formula.
    """
    R = 6371.0  # Earth radius in km
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
