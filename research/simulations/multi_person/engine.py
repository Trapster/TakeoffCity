from flights import get_random_flights, get_available_airports

# Lookup table for simple aggregation strategies — avoids fragile substring matching.
_STRATEGY_OPS = {
    "total_cost":      ("price", sum),
    "total_time":      ("time",  sum),
    "worst_case_cost": ("price", max),
    "worst_case_time": ("time",  max),
}


def collect_simulations(origin_types, min_per_batch=40, max_per_batch=200):
    """
    Runs one flight search per traveller.

    origin_types: list of 'hub'|'medium'|'small', one per traveller.
    Each traveller gets a different airport pool derived from their origin type,
    reflecting that different departure cities have different route networks.

    Returns a list of batches, each batch being a list of flight dicts.
    """
    all_batches = []
    for origin_type in origin_types:
        airports, weights = get_available_airports(origin_type)
        batch = get_random_flights(airports, weights, min_count=min_per_batch, max_count=max_per_batch)
        all_batches.append(batch)
    return all_batches


def find_common_acronyms(batches):
    """Returns a set of destination codes that appear in every batch."""
    if not batches:
        return set()
    common = {flight["name"] for flight in batches[0]}
    for batch in batches[1:]:
        common.intersection_update(flight["name"] for flight in batch)
    return common


def analyze_metrics(batches, strategy="total_cost", common_names=None):
    """Analyzes metrics of common destinations based on the selected strategy."""
    if common_names is None:
        common_names = find_common_acronyms(batches)
    if not common_names:
        return None, None, None

    # Single O(M) pass — build per-destination value lists
    accum = {name: {"price": [], "time": []} for name in common_names}
    for batch in batches:
        for f in batch:
            if f["name"] in accum:
                accum[f["name"]]["price"].append(float(f["price"]))
                accum[f["name"]]["time"].append(float(f["time"]))

    results = {}
    if strategy == "balanced":
        costs = {name: sum(v["price"]) for name, v in accum.items()}
        times = {name: sum(v["time"])  for name, v in accum.items()}
        min_cost, max_cost = min(costs.values()), max(costs.values())
        min_time, max_time = min(times.values()), max(times.values())
        for name in common_names:
            norm_cost = (costs[name] - min_cost) / (max_cost - min_cost) if max_cost > min_cost else 0
            norm_time = (times[name] - min_time) / (max_time - min_time) if max_time > min_time else 0
            results[name] = 0.5 * norm_cost + 0.5 * norm_time
    elif strategy in _STRATEGY_OPS:
        field, agg = _STRATEGY_OPS[strategy]
        for name, v in accum.items():
            results[name] = agg(v[field])
    else:
        raise ValueError(f"Unknown strategy: {strategy!r}")

    best = min(results, key=results.get)
    return best, results[best], common_names


def analyze_stops_metrics(batches, common_names=None):
    """
    Returns stop distribution across all flights to common destinations.

    dict keys: direct_pct, one_stop_pct, two_stop_pct, avg_stops, common_count
    """
    if common_names is None:
        common_names = find_common_acronyms(batches)
    if not common_names:
        return {"direct_pct": 0.0, "one_stop_pct": 0.0,
                "two_stop_pct": 0.0, "avg_stops": 0.0, "common_count": 0}

    stop_counts = {0: 0, 1: 0, 2: 0}
    total = 0
    for batch in batches:
        for flight in batch:
            if flight["name"] in common_names:
                stop_counts[flight.get("stops", 0)] += 1
                total += 1

    if total == 0:
        return {"direct_pct": 0.0, "one_stop_pct": 0.0,
                "two_stop_pct": 0.0, "avg_stops": 0.0, "common_count": len(common_names)}

    return {
        "direct_pct":   round(100.0 * stop_counts[0] / total, 1),
        "one_stop_pct": round(100.0 * stop_counts[1] / total, 1),
        "two_stop_pct": round(100.0 * stop_counts[2] / total, 1),
        "avg_stops":    round((stop_counts[1] + 2 * stop_counts[2]) / total, 2),
        "common_count": len(common_names),
    }


def collect_simulations_dated(origin_types, window_days, arrival_tolerance=0,
                               min_per_batch=40, max_per_batch=200):
    """
    Like collect_simulations but each person also has a personal availability
    window within the event window and flights carry per-day route schedules.

    arrival_tolerance: person can arrive this many days before their nominal
    availability start (i.e. their window is extended backward by that amount).

    Returns list of PersonResult dicts:
      {"origin_type": str, "avail_days": set[int], "flights": list[dict]}
    """
    from flights import get_available_airports, get_flights_for_window
    from dates import generate_person_availability

    results = []
    for origin_type in origin_types:
        airports, weights = get_available_airports(origin_type)
        flights = get_flights_for_window(airports, weights, window_days,
                                         min_per_batch, max_per_batch)
        avail = generate_person_availability(window_days, origin_type)
        if arrival_tolerance:
            # Extend window backward: if you can arrive a day early you have
            # more flight options without missing any group time.
            extra = {d - i for d in list(avail)
                     for i in range(1, arrival_tolerance + 1) if d - i >= 0}
            avail = avail | extra
        results.append({"origin_type": origin_type, "avail_days": avail, "flights": flights})
    return results


def find_viable_destinations(person_results, min_coverage=1.0):
    """
    Returns dict[dest_code -> list[set[int]]] for destinations that are
    reachable by at least `min_coverage` fraction of travellers, where
    "reachable" means there is at least one day when both the route operates
    AND the person is available.

    min_coverage: 1.0 = strict (all must reach), 0.8 = 4 of 5, etc.
    """
    n = len(person_results)
    required = max(1, round(n * min_coverage))

    dest_person_days: dict = {}
    for pr in person_results:
        for f in pr["flights"]:
            reachable = f["available_days"] & pr["avail_days"]
            if reachable:
                dest_person_days.setdefault(f["name"], []).append(reachable)

    return {dest: sets for dest, sets in dest_person_days.items()
            if len(sets) >= required}


def analyze_dated_metrics(person_results, viable_destinations, min_overlap_days=1):
    """
    For each viable destination, computes:
      - overlap_days: days when ALL required travellers are simultaneously present
      - total_cost: sum of cheapest per-person flight to a reachable day
      - worst_case_cost: max of per-person cheapest flight
      - travellers_reached: how many people can make it

    Returns list of result dicts sorted by total_cost, filtered to those with
    overlap_days >= min_overlap_days.
    """
    if not viable_destinations:
        return []

    results = []
    for dest, day_sets in viable_destinations.items():
        overlap = set.intersection(*day_sets) if len(day_sets) > 1 else set(day_sets[0])
        if len(overlap) < min_overlap_days:
            continue

        per_person_costs = []
        for pr in person_results:
            reachable_flights = [
                f for f in pr["flights"]
                if f["name"] == dest and f["available_days"] & pr["avail_days"]
            ]
            if reachable_flights:
                per_person_costs.append(min(f["price"] for f in reachable_flights))

        if not per_person_costs:
            continue

        results.append({
            "dest": dest,
            "overlap_days": len(overlap),
            "total_cost": round(sum(per_person_costs), 2),
            "worst_case_cost": round(max(per_person_costs), 2),
            "travellers_reached": len(per_person_costs),
        })

    return sorted(results, key=lambda x: x["total_cost"])


def compute_price_saving_pct(static_cost, dated_cost):
    """Returns % saving from date-flexible pricing vs. static (no date model)."""
    if static_cost <= 0:
        return 0.0
    return round(100.0 * (static_cost - dated_cost) / static_cost, 1)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Flight Simulation Engine")
    parser.add_argument("--min_f",   type=int, default=40)
    parser.add_argument("--max_f",   type=int, default=200)
    parser.add_argument(
        "--origins", nargs="+",
        choices=["hub", "medium", "small"],
        default=["hub", "medium", "medium", "small", "small"],
    )
    args = parser.parse_args()

    batches = collect_simulations(
        origin_types=args.origins,
        min_per_batch=args.min_f,
        max_per_batch=args.max_f,
    )

    common = find_common_acronyms(batches)
    strategies = ["total_cost", "worst_case_cost", "total_time", "worst_case_time", "balanced"]
    print(f"\nOrigins: {args.origins}  range [{args.min_f}-{args.max_f}]")
    print("-" * 80)
    for strat in strategies:
        best_name, best_val, _ = analyze_metrics(batches, strategy=strat, common_names=common)
        if best_name:
            print(f"{strat:<20}: {best_name:<6} (Score: {best_val:.2f}, common: {len(common)})")
        else:
            print(f"{strat:<20}: NO COMMON AIRPORTS")

    stops = analyze_stops_metrics(batches, common_names=common)
    print(f"\nStops (common dests): direct={stops['direct_pct']}%  "
          f"1-stop={stops['one_stop_pct']}%  2-stop={stops['two_stop_pct']}%  "
          f"avg={stops['avg_stops']}")
