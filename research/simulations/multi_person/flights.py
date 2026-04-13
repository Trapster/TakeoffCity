import random

# ---------------------------------------------------------------------------
# Airport catalog — real IATA codes grouped by tier
# ---------------------------------------------------------------------------

AIRPORT_TIERS = {
    1: [  # Mega-hubs (20)
        "JFK", "LHR", "CDG", "AMS", "FRA", "DXB", "SIN", "NRT", "LAX", "ORD",
        "ATL", "DFW", "IST", "PEK", "HKG", "ICN", "BKK", "SYD", "MUC", "MAD",
    ],
    2: [  # Regional hubs (50)
        "BOS", "MIA", "SEA", "YYZ", "MEX", "GRU", "LGW", "BCN", "FCO", "ZRH",
        "VIE", "CPH", "OSL", "HEL", "DUB", "BRU", "LIS", "ATH", "PRG", "WAW",
        "BUD", "MSP", "DTW", "PHX", "TPA", "DEN", "SFO", "IAH", "EWR", "CVG",
        "PHL", "MAN", "BHX", "EDI", "AGP", "PMI", "ALC", "NCE", "MRS", "LYS",
        "TLS", "HAM", "DUS", "STR", "CGN", "LEJ", "GVA", "BSL", "VCE", "NAP",
    ],
    3: [  # Secondary / leisure airports (40)
        "GLA", "BHD", "ABZ", "EXT", "NWI", "LBA", "SOU", "BOH", "NQY", "MME",
        "DSA", "HUY", "BRS", "CWL", "SWS", "INV", "KIR", "NOC", "SNN", "ORK",
        "GNB", "CLY", "BES", "RNS", "CFR", "BIQ", "PGF", "CCF", "RLX", "CRL",
        "EIN", "MST", "BLL", "SVG", "TRF", "BGO", "AES", "TRD", "BOO", "PMO",
    ],
}

AIRPORT_TIER = {code: tier for tier, codes in AIRPORT_TIERS.items() for code in codes}

MAX_API_RESULTS = 200  # Tequila API hard cap

# ---------------------------------------------------------------------------
# Per-origin-type availability model
# ---------------------------------------------------------------------------

# Fraction of each tier's airports visible from a given origin type.
# A person at a small regional airport simply cannot reach many destinations.
ORIGIN_REACH = {
    "hub":    {1: 1.00, 2: 1.00, 3: 0.60},  # ~86% of pool
    "medium": {1: 0.80, 2: 0.70, 3: 0.30},  # ~55% of pool
    "small":  {1: 0.50, 2: 0.30, 3: 0.10},  # ~25% of pool
}

# Sampling weight multipliers by destination tier.
# Tier-1 hubs appear in far more search results than obscure tier-3 airports.
TIER_WEIGHT_MULTIPLIER = {1: 3.0, 2: 1.5, 3: 0.5}

# ---------------------------------------------------------------------------
# Flight generation parameters per destination tier
# ---------------------------------------------------------------------------

TIER_PRICE_RANGE = {
    1: (150.0,  600.0),
    2: (200.0,  900.0),
    3: (300.0, 1500.0),
}

TIER_TIME_RANGE = {  # minutes, direct leg
    1: ( 90, 480),
    2: (120, 540),
    3: (150, 600),
}

# (direct, 1-stop, 2-stop) probability weights by destination tier.
# Tier-1 hubs have many direct services; tier-3 almost always needs a connection.
TIER_STOP_WEIGHTS = {
    1: (0.60, 0.30, 0.10),
    2: (0.35, 0.45, 0.20),
    3: (0.15, 0.45, 0.40),
}

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_available_airports(origin_type: str) -> tuple:
    """
    Returns (airports, weights) for a traveller departing from origin_type.

    origin_type: 'hub' | 'medium' | 'small'

    The within-tier selection is random, so two travellers of the same origin
    type see different (but overlapping) pools — reflecting that BOS and MIA
    are both 'medium' but serve different actual route networks.
    """
    if origin_type not in ORIGIN_REACH:
        raise ValueError(f"Unknown origin_type {origin_type!r}. Use 'hub', 'medium', or 'small'.")

    reach = ORIGIN_REACH[origin_type]
    airports = []
    weights = []
    for tier, codes in AIRPORT_TIERS.items():
        n = max(1, int(len(codes) * reach[tier]))
        for code in random.sample(codes, n):
            airports.append(code)
            weights.append(TIER_WEIGHT_MULTIPLIER[tier])
    return airports, weights


def get_random_flights(airports, weights, min_count=40, max_count=200):
    """Returns a list of random flight objects using weighted selection."""
    if min_count > max_count:
        raise ValueError(f"min_count ({min_count}) must not exceed max_count ({max_count})")
    max_count = min(max_count, MAX_API_RESULTS)
    min_count = min(min_count, max_count)
    count = random.randint(min_count, max_count)

    # Weighted sampling without replacement (Efraimidis-Spirakis)
    scored = [(random.random() ** (1.0 / max(1e-6, weights[i])), code)
              for i, code in enumerate(airports)]
    scored.sort(key=lambda x: x[0], reverse=True)

    return [_make_flight(code) for _, code in scored[:count]]


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _make_flight(code: str) -> dict:
    tier = AIRPORT_TIER.get(code, 3)

    # Number of stops — correlated with destination tier
    stops = random.choices((0, 1, 2), weights=TIER_STOP_WEIGHTS[tier])[0]

    # Flight time: base direct duration + layover penalty per stop
    base_time = random.randint(*TIER_TIME_RANGE[tier])
    total_time = base_time + sum(random.randint(90, 150) for _ in range(stops))

    # Price: base range from tier, stops add ±20% noise
    # (connections can be cheaper through indirect routing, or more expensive)
    base_price = random.uniform(*TIER_PRICE_RANGE[tier])
    stop_factor = 1.0 + random.uniform(-0.20, 0.20) * stops
    total_price = round(base_price * max(0.5, stop_factor), 2)

    return {"name": code, "price": total_price, "time": total_time, "stops": stops}


def get_flights_for_window(airports, weights, window_days: int,
                           min_count=40, max_count=200) -> list:
    """
    Like get_random_flights but each flight also carries:
      - available_days: set[int] — days in the window when this route operates
      - price adjusted by the cheapest day-of-week factor across available days

    Route availability is tier-dependent: tier-1 routes run daily, tier-3 only
    3×/week. The day-of-week price adjustment rewards travellers with flexible
    departure dates.
    """
    from dates import DOW_PRICE_FACTOR, get_route_days

    max_count = min(max_count, MAX_API_RESULTS)
    min_count = min(min_count, max_count)
    count = random.randint(min_count, max_count)

    scored = [(random.random() ** (1.0 / max(1e-6, weights[i])), code)
              for i, code in enumerate(airports)]
    scored.sort(key=lambda x: x[0], reverse=True)

    flights = []
    for _, code in scored[:count]:
        f = _make_flight(code)
        tier = AIRPORT_TIER.get(code, 3)
        avail = get_route_days(window_days, tier)
        if avail:
            best_dow_factor = min(DOW_PRICE_FACTOR[d % 7] for d in avail)
            f["price"] = round(f["price"] * best_dow_factor, 2)
        f["available_days"] = avail
        flights.append(f)
    return flights


if __name__ == "__main__":
    import json

    for origin_type in ("hub", "medium", "small"):
        airports, weights = get_available_airports(origin_type)
        print(f"{origin_type:<8}: {len(airports)} airports visible")

    print()
    airports, weights = get_available_airports("medium")
    sample = get_random_flights(airports, weights, 5, 10)
    print(json.dumps(sample, indent=2))
