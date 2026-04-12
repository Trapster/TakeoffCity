"""
Temporal simulation grid: how do window size, arrival tolerance, and
min_overlap_days interact with origin-type failure modes?

Each cell in the grid runs N_TRIALS independent trials and reports:
  FAIL%     — fraction of trials with zero viable destinations
  AVG_DEST  — mean number of viable destinations when > 0
  AVG_DAYS  — mean group overlap days at the top-ranked destination
  AVG_COST  — mean total group cost at the top-ranked destination
"""
import random
import statistics

from engine import (
    collect_simulations_dated,
    find_viable_destinations,
    analyze_dated_metrics,
)

ORIGIN_GROUPS = [
    ["hub"] * 5,
    ["hub", "medium", "medium", "small", "small"],   # realistic 5-person trip
    ["medium"] * 5,
    ["small"] * 5,
    ["hub", "small", "small", "small", "small"],     # 1 hub + 4 small
    # 10-person mixed
    ["hub", "medium", "medium", "small", "small",
     "medium", "medium", "small", "small", "hub"],
]

WINDOW_SIZES = [7, 14, 21, 30]   # days
TOLERANCES   = [0, 1, 2, 3]      # arrival_tolerance days
MIN_OVERLAPS = [1, 2, 3, 5]      # min group overlap days required
FLIGHT_RANGE = (40, 200)
N_TRIALS     = 20


def _group_label(group):
    counts = {}
    for t in group:
        counts[t] = counts.get(t, 0) + 1
    parts = []
    for t in ("hub", "medium", "small"):
        if t in counts:
            parts.append(f"{counts[t]}x{t}")
    return "+".join(parts)


def run_temporal_suite(seed=42):
    random.seed(seed)

    header = (
        f"{'GROUP':<30} {'WIN':>4} {'TOL':>4} {'OVL':>4} | "
        f"{'FAIL%':>6} {'AVG_DEST':>8} {'AVG_DAYS':>8} {'AVG_COST':>9}"
    )
    print(header)
    print("-" * len(header))

    for group in ORIGIN_GROUPS:
        label = _group_label(group)
        first = True
        for window in WINDOW_SIZES:
            for tol in TOLERANCES:
                for min_overlap in MIN_OVERLAPS:
                    fails = 0
                    dest_counts, overlap_days, costs = [], [], []

                    for _ in range(N_TRIALS):
                        prs = collect_simulations_dated(
                            group, window,
                            arrival_tolerance=tol,
                            min_per_batch=FLIGHT_RANGE[0],
                            max_per_batch=FLIGHT_RANGE[1],
                        )
                        viable = find_viable_destinations(prs, min_coverage=1.0)
                        ranked = analyze_dated_metrics(prs, viable,
                                                       min_overlap_days=min_overlap)
                        if not ranked:
                            fails += 1
                        else:
                            dest_counts.append(len(ranked))
                            overlap_days.append(ranked[0]["overlap_days"])
                            costs.append(ranked[0]["total_cost"])

                    fail_pct = round(100 * fails / N_TRIALS)
                    avg_dest = round(statistics.mean(dest_counts), 1) if dest_counts else 0.0
                    avg_days = round(statistics.mean(overlap_days), 1) if overlap_days else 0.0
                    avg_cost = round(statistics.mean(costs), 1) if costs else 0.0

                    row_label = label if first else ""
                    first = False
                    print(
                        f"{row_label:<30} {window:>4} {tol:>4} {min_overlap:>4} | "
                        f"{fail_pct:>6} {avg_dest:>8} {avg_days:>8} {avg_cost:>9}"
                    )
        print()


if __name__ == "__main__":
    run_temporal_suite()
