import random

# How many days/week each tier operates routes.
# Tier-1 mega-hubs fly daily; tier-3 secondary airports have limited schedules.
TIER_ROUTE_FREQUENCY = {1: 7, 2: 5, 3: 3}  # days per week

# Fraction of the event window each origin type can typically attend.
# Represents personal schedule constraints (work, family, budget).
ORIGIN_FLEXIBILITY = {
    "hub":    (0.65, 1.00),
    "medium": (0.50, 0.90),
    "small":  (0.35, 0.75),
}

# Day-of-week price multipliers (0=Monday … 6=Sunday).
# Weekend departures cost more; mid-week is cheapest.
DOW_PRICE_FACTOR = {
    0: 0.88,  # Monday
    1: 0.92,  # Tuesday
    2: 0.95,  # Wednesday
    3: 0.97,  # Thursday
    4: 1.05,  # Friday
    5: 1.10,  # Saturday
    6: 1.15,  # Sunday
}


def generate_person_availability(window_days: int, origin_type: str) -> set:
    """
    Returns a set of day-offsets (0-indexed from window start) when this
    traveller is available to fly to the destination.

    The available span is a contiguous block, possibly starting up to 3 days
    into the window to model "I can't leave until Wednesday".
    """
    lo, hi = ORIGIN_FLEXIBILITY[origin_type]
    avail_days = max(1, int(window_days * random.uniform(lo, hi)))
    max_start_offset = max(0, window_days - avail_days)
    start = random.randint(0, min(max_start_offset, 3))
    return set(range(start, start + avail_days))


def get_route_days(window_days: int, tier: int) -> set:
    """
    Returns the set of days (0-indexed) within the window when this tier's
    route actually operates.

    Routes run `TIER_ROUTE_FREQUENCY[tier]` days per week on a fixed weekly
    pattern starting at a random day-of-week.
    """
    freq = TIER_ROUTE_FREQUENCY[tier]
    start_dow = random.randint(0, 6)
    return {day for day in range(window_days) if (start_dow + day) % 7 < freq}


if __name__ == "__main__":
    print("=== Route days over 14-day window ===")
    for tier in (1, 2, 3):
        days = get_route_days(14, tier)
        print(f"  Tier {tier} ({TIER_ROUTE_FREQUENCY[tier]}x/week): {sorted(days)}")

    print("\n=== Person availability over 14-day window ===")
    for origin in ("hub", "medium", "small"):
        for _ in range(3):
            avail = generate_person_availability(14, origin)
            print(f"  {origin:<8}: days {sorted(avail)} ({len(avail)} days)")
        print()
