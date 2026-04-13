"""
Destination recommendation algorithm for TakeoffCity.

run_calculation(event_id, session_factory) is a generator that:
  1. Geocodes each unique departure city in the event's responses
  2. Searches flights from each person to each candidate destination
  3. Scores and ranks destinations by three strategies
  4. Identifies the bottleneck traveller (whose removal unlocks the most destinations)
  5. Stores the result in CalculationResultDB and sets event.calculated = True
  6. Yields log lines throughout so the caller can stream progress to the client

The generator takes a SQLAlchemy session *factory* (not a session) so it can
own its connection safely when run in a background thread.
"""

import json
import math
from datetime import datetime
from typing import Generator

import flights as flights_module
import tequila_client
from main import CalculationResultDB, EventDB, FeedbackDB


# ── Candidate destinations ────────────────────────────────────────────────────

CANDIDATE_DESTINATIONS = [
    # European hubs
    "LHR", "CDG", "AMS", "FRA", "MAD", "FCO", "BCN", "ZRH", "MUC", "VIE",
    "CPH", "OSL", "LIS", "DUB", "PRG", "WAW", "ATH", "BRU", "HEL", "BUD",
    # European interesting
    "EDI", "LYS", "NCE", "HAM", "MAN", "OPO", "RAK", "SVQ", "BIO",
    # Global
    "DXB", "SIN", "NRT", "HKG", "BKK", "JFK", "LAX", "YYZ", "DOH", "SYD",
]

DESTINATION_INFO: dict[str, tuple[str, str]] = {
    "LHR": ("London",       "GB"), "CDG": ("Paris",         "FR"),
    "AMS": ("Amsterdam",    "NL"), "FRA": ("Frankfurt",      "DE"),
    "MAD": ("Madrid",       "ES"), "FCO": ("Rome",           "IT"),
    "BCN": ("Barcelona",    "ES"), "ZRH": ("Zurich",         "CH"),
    "MUC": ("Munich",       "DE"), "VIE": ("Vienna",         "AT"),
    "CPH": ("Copenhagen",   "DK"), "OSL": ("Oslo",           "NO"),
    "LIS": ("Lisbon",       "PT"), "DUB": ("Dublin",         "IE"),
    "PRG": ("Prague",       "CZ"), "WAW": ("Warsaw",         "PL"),
    "ATH": ("Athens",       "GR"), "BRU": ("Brussels",       "BE"),
    "HEL": ("Helsinki",     "FI"), "BUD": ("Budapest",       "HU"),
    "EDI": ("Edinburgh",    "GB"), "LYS": ("Lyon",           "FR"),
    "NCE": ("Nice",         "FR"), "HAM": ("Hamburg",        "DE"),
    "MAN": ("Manchester",   "GB"), "OPO": ("Porto",          "PT"),
    "RAK": ("Marrakech",    "MA"), "SVQ": ("Seville",        "ES"),
    "BIO": ("Bilbao",       "ES"), "DXB": ("Dubai",          "AE"),
    "SIN": ("Singapore",    "SG"), "NRT": ("Tokyo",          "JP"),
    "HKG": ("Hong Kong",    "HK"), "BKK": ("Bangkok",        "TH"),
    "JFK": ("New York",     "US"), "LAX": ("Los Angeles",    "US"),
    "YYZ": ("Toronto",      "CA"), "DOH": ("Doha",           "QA"),
    "SYD": ("Sydney",       "AU"),
}


# ── Pure helpers ──────────────────────────────────────────────────────────────

def _coverage_threshold(n: int) -> int:
    """Minimum number of travellers who must reach a destination for it to qualify.
    Uses 80% floor threshold (at least 80% of the group must be able to reach it),
    with a minimum of 1 so a solo traveller always gets results.
    """
    return max(1, math.floor(0.8 * n))


def _cheapest(flights: list[dict]) -> dict | None:
    if not flights:
        return None
    return min(flights, key=lambda f: f.get("price", float("inf")))


def _coefficient_of_variation(prices: list[float]) -> float:
    if len(prices) < 2:
        return 0.0
    mean = sum(prices) / len(prices)
    if mean == 0:
        return 0.0
    variance = sum((p - mean) ** 2 for p in prices) / len(prices)
    return (variance ** 0.5) / mean


def _identifier(fb: FeedbackDB) -> str:
    return fb.attendee_username or fb.attendee_email or f"Traveller {fb.id}"


def _geocode_city(city: str) -> tuple[float, float] | None:
    results = tequila_client.query_locations(city, location_types="city", limit=1)
    if not results:
        return None
    loc = results[0].get("location", {})
    lat = loc.get("lat")
    lon = loc.get("lon")
    if lat is None or lon is None:
        return None
    return float(lat), float(lon)


# ── Main generator ────────────────────────────────────────────────────────────

def run_calculation(event_id: str, session_factory) -> Generator[str, None, None]:
    """
    Generator that runs the full destination-scoring algorithm.

    Yields log lines (strings ending with '\n') as it progresses.
    Sets event.calculated = True and stores results in CalculationResultDB
    before the final yield.
    """
    db = session_factory()
    try:
        yield from _run(event_id, db)
    finally:
        db.close()


def _run(event_id: str, db) -> Generator[str, None, None]:
    # ── Load event and feedbacks ──────────────────────────────────────────────
    event = db.query(EventDB).filter(EventDB.id == event_id).first()
    if not event:
        yield "Event not found.\n"
        return

    feedbacks = db.query(FeedbackDB).filter(FeedbackDB.event_id == event_id).all()
    if not feedbacks:
        yield "No responses found. Ask your group to submit their details first.\n"
        return

    total = len(feedbacks)
    yield f"Found {total} response{'s' if total != 1 else ''}. Starting search...\n"

    # ── Geocode unique cities ─────────────────────────────────────────────────
    unique_cities = list({fb.city.strip() for fb in feedbacks if fb.city})
    yield f"Geocoding {len(unique_cities)} departure {'city' if len(unique_cities) == 1 else 'cities'}...\n"

    city_coords: dict[str, tuple[float, float] | None] = {}
    for city in unique_cities:
        try:
            city_coords[city.strip()] = _geocode_city(city.strip())
        except RuntimeError as exc:
            yield f"Configuration error: {exc}\n"
            return
        except Exception as exc:
            yield f"Warning: could not geocode '{city}': {exc}\n"
            city_coords[city.strip()] = None

    # ── Search flights for each (person, destination) pair ───────────────────
    date_from = event.earliest_date
    date_to   = event.latest_date

    # all_per_person[iata][fb.id] = per-person dict (or can_reach=False)
    all_per_person: dict[str, dict[int, dict]] = {}

    for iata in CANDIDATE_DESTINATIONS:
        yield f"Searching flights to {iata}...\n"
        dest_map: dict[int, dict] = {}

        for fb in feedbacks:
            city_key = fb.city.strip() if fb.city else ""
            coords   = city_coords.get(city_key)
            person_id = fb.id

            if coords is None:
                dest_map[person_id] = {
                    "identifier": _identifier(fb),
                    "origin_city": fb.city or "",
                    "can_reach": False,
                }
                continue

            lat, lon = coords
            try:
                raw_flights, *_ = flights_module.search_flights_from_city(
                    lat, lon, iata, date_from, date_to, 200, "EUR", db
                )
            except Exception as exc:
                yield f"Warning: flight search failed for {fb.city} → {iata}: {exc}\n"
                raw_flights = []

            best = _cheapest(raw_flights)
            if best is None:
                dest_map[person_id] = {
                    "identifier": _identifier(fb),
                    "origin_city": fb.city or "",
                    "can_reach": False,
                }
            else:
                duration_secs = (best.get("duration") or {}).get("total", 0)
                duration_mins = int(duration_secs) // 60
                route         = best.get("route") or []
                stops         = max(0, len(route) - 1)
                dest_map[person_id] = {
                    "identifier": _identifier(fb),
                    "origin_city": fb.city or "",
                    "can_reach": True,
                    "price":        float(best.get("price", 0)),
                    "duration_mins": duration_mins,
                    "stops":         stops,
                    "deep_link":    best.get("deep_link") or best.get("booking_token"),
                }

        all_per_person[iata] = dest_map

    # ── Coverage filter ───────────────────────────────────────────────────────
    threshold = _coverage_threshold(total)
    surviving: dict[str, dict[int, dict]] = {}

    for iata, dest_map in all_per_person.items():
        reachable = sum(1 for p in dest_map.values() if p["can_reach"])
        if reachable >= threshold:
            surviving[iata] = dest_map

    yield f"Found {len(surviving)} viable destination{'s' if len(surviving) != 1 else ''}.\n"

    # ── Score each surviving destination ─────────────────────────────────────
    scored: list[dict] = []
    for iata, dest_map in surviving.items():
        city_name, country_code = DESTINATION_INFO.get(iata, (iata, ""))
        reachable_entries = [p for p in dest_map.values() if p["can_reach"]]
        all_entries       = list(dest_map.values())
        reachable_count   = len(reachable_entries)

        prices    = [p["price"]         for p in reachable_entries]
        durations = [p["duration_mins"] for p in reachable_entries]

        scored.append({
            "iata":         iata,
            "city_name":    city_name,
            "country_code": country_code,
            "coverage":     {"reachable": reachable_count, "total": total},
            "strategy_scores": {
                "total_cost":           round(sum(prices), 2),
                "worst_case_cost":      round(max(prices), 2),
                "worst_case_time_mins": max(durations),
            },
            "per_person": all_entries,
        })

    # ── Rank by each strategy (top-3 per strategy) ───────────────────────────
    def _rank_all(items: list[dict], key_fn) -> dict[str, int]:
        sorted_iatas = [d["iata"] for d in sorted(items, key=key_fn)]
        return {iata: idx + 1 for idx, iata in enumerate(sorted_iatas)}

    rank_cheapest = _rank_all(scored, lambda d: d["strategy_scores"]["total_cost"])
    rank_fairest  = _rank_all(scored, lambda d: d["strategy_scores"]["worst_case_cost"])
    rank_fastest  = _rank_all(scored, lambda d: d["strategy_scores"]["worst_case_time_mins"])

    # Keep union of top-3 per strategy (avoids sending the entire list to the frontend)
    top_iatas = {
        iata for iata, rank in rank_cheapest.items() if rank <= 3
    } | {
        iata for iata, rank in rank_fairest.items()  if rank <= 3
    } | {
        iata for iata, rank in rank_fastest.items()  if rank <= 3
    }

    destinations_out = []
    for d in scored:
        if d["iata"] not in top_iatas:
            continue
        destinations_out.append({
            "rank_cheapest": rank_cheapest[d["iata"]],
            "rank_fairest":  rank_fairest[d["iata"]],
            "rank_fastest":  rank_fastest[d["iata"]],
            **d,
        })

    # ── Bottleneck attribution ────────────────────────────────────────────────
    bottleneck = None
    if len(surviving) < len(CANDIDATE_DESTINATIONS):
        best_unlock = 0
        best_fb     = None

        for fb in feedbacks:
            others     = [f for f in feedbacks if f.id != fb.id]
            n_others   = len(others)
            thr_others = _coverage_threshold(n_others)
            extra      = 0

            for iata, dest_map in all_per_person.items():
                if iata in surviving:
                    continue  # already available — doesn't count
                reachable_without = sum(
                    1 for f in others if dest_map.get(f.id, {}).get("can_reach", False)
                )
                if reachable_without >= thr_others:
                    extra += 1

            if extra > best_unlock:
                best_unlock = extra
                best_fb     = fb

        if best_fb is not None and best_unlock > 0:
            bottleneck = {
                "identifier":           _identifier(best_fb),
                "origin_city":          best_fb.city or "",
                "destinations_unlocked": best_unlock,
            }

    # ── Assemble result ───────────────────────────────────────────────────────
    result = {
        "calculated_at":  datetime.utcnow().isoformat(),
        "total_responses": total,
        "destinations":    destinations_out,
        "bottleneck":      bottleneck,
    }

    # ── Persist ───────────────────────────────────────────────────────────────
    db.query(CalculationResultDB).filter_by(event_id=event_id).delete()
    db.add(CalculationResultDB(
        event_id      = event_id,
        result_json   = json.dumps(result),
        calculated_at = datetime.utcnow(),
    ))
    event.calculated = True
    db.commit()

    yield "Calculation complete! Your gathering is ready.\n"
