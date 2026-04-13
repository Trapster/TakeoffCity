"""
Flight search module.

Searches for flights from a departure city (expressed as a lat/lon circle) to a
destination airport using the Tequila Search API. Results are cached in the DB
with a 1-hour TTL to avoid redundant API calls during repeated calculate runs.

Date contract
-------------
Callers always pass dates as ISO 8601 strings (YYYY-MM-DD). This module
converts them to the dd/mm/yyyy format required by the Tequila API internally.
"""

import hashlib
import json
import os
from datetime import datetime, timedelta

import tequila_client
from main import FlightResultCacheDB

FLIGHT_CACHE_TTL_MINUTES = 60


# ── Public API ────────────────────────────────────────────────────────────────

def search_flights_from_city(
    city_lat: float,
    city_lon: float,
    fly_to: str,
    date_from: str,
    date_to: str,
    radius_km: int = 200,
    curr: str = "EUR",
    db=None,
) -> tuple[list[dict], bool, datetime]:
    """
    Search for flights departing from all airports within radius_km of the
    given city coordinates, arriving at fly_to.

    Uses Tequila's native circle parameter: circle:{lat},{lon}:{radius}km
    so multi-airport search is handled server-side.

    Returns (flights, from_cache, fetched_at).
    """
    fly_from = f"circle:{city_lat},{city_lon}:{radius_km}km"
    return _search(fly_from, fly_to, date_from, date_to, curr, db)


def search_flights_from_airports(
    iata_codes: list[str],
    fly_to: str,
    date_from: str,
    date_to: str,
    curr: str = "EUR",
    db=None,
) -> tuple[list[dict], bool, datetime]:
    """
    Search for flights from an explicit list of departure airports to fly_to.

    Useful when the caller has already resolved a city to specific IATA codes
    and wants precise control over the departure pool.

    Returns (flights, from_cache, fetched_at).
    """
    fly_from = ",".join(iata_codes)
    return _search(fly_from, fly_to, date_from, date_to, curr, db)


# ── Internal helpers ──────────────────────────────────────────────────────────

def _search(
    fly_from: str,
    fly_to: str,
    date_from: str,
    date_to: str,
    curr: str,
    db,
) -> tuple[list[dict], bool, datetime]:
    cache_key = _make_cache_key(fly_from, fly_to, date_from, date_to, curr)

    if db is not None:
        row, results = _get_cached_row(cache_key, db)
        if results is not None:
            return results, True, row.fetched_at

    results = tequila_client.search_flights(
        fly_from=fly_from,
        fly_to=fly_to,
        date_from=_iso_to_tequila(date_from),
        date_to=_iso_to_tequila(date_to),
        curr=curr,
    )

    now = datetime.utcnow()
    if db is not None:
        _store_result(cache_key, fly_from, fly_to, date_from, date_to, results, db, now)

    return results, False, now


def _iso_to_tequila(iso_date: str) -> str:
    """Convert "2025-08-15" → "15/08/2025" as required by the Tequila API."""
    y, m, d = iso_date.split("-")
    return f"{d}/{m}/{y}"


def _make_cache_key(
    fly_from: str,
    fly_to: str,
    date_from: str,
    date_to: str,
    curr: str,
) -> str:
    payload = json.dumps([fly_from, fly_to, date_from, date_to, curr], sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()


def _get_cached_row(
    cache_key: str, db
) -> tuple["FlightResultCacheDB | None", "list[dict] | None"]:
    """Return (row, results) if a fresh cache entry exists, else (None, None)."""
    row = db.query(FlightResultCacheDB).filter_by(cache_key=cache_key).first()
    if row is None:
        return None, None
    if datetime.utcnow() - row.fetched_at > timedelta(minutes=FLIGHT_CACHE_TTL_MINUTES):
        return None, None
    return row, json.loads(row.result_json)


def _store_result(
    cache_key: str,
    fly_from: str,
    fly_to: str,
    date_from: str,
    date_to: str,
    results: list[dict],
    db,
    now: datetime,
) -> None:
    db.query(FlightResultCacheDB).filter_by(cache_key=cache_key).delete()
    db.add(FlightResultCacheDB(
        cache_key=cache_key,
        fly_from=fly_from,
        fly_to=fly_to,
        date_from=date_from,
        date_to=date_to,
        result_json=json.dumps(results),
        fetched_at=now,
        result_count=len(results),
    ))
    db.commit()
