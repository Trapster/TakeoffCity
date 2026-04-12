import engine
import itertools
import random
import statistics
import time

# ---------------------------------------------------------------------------
# Parameter grid
# ---------------------------------------------------------------------------

# Origin group compositions — the primary variable for the failure mode study.
# Each list is one travel group; each string is one traveller's origin type.
ORIGIN_GROUPS = [
    # Homogeneous baselines
    ["hub"]    * 5,
    ["medium"] * 5,
    ["small"]  * 5,

    # Realistic mixed groups (5 travellers)
    ["hub", "medium", "medium", "small", "small"],
    ["hub", "hub",    "medium", "medium", "small"],
    ["medium", "medium", "medium", "small", "small"],

    # Stress cases
    ["hub", "small", "small", "small", "small"],   # 1 hub, 4 small

    # Group size variation
    ["medium", "small"],                            # 2-person trip
    ["hub", "medium", "medium", "small", "small",
     "medium", "medium", "small", "small", "hub"],  # 10-person trip
]

# Flight ranges: (min_results, max_results) per person per search.
# Upper bound capped at 200 to match the Tequila API hard limit.
FLIGHT_RANGES = [(10, 50), (40, 200), (150, 200)]

# Number of trials per configuration — needed to measure failure *rate*
# rather than just whether a single run succeeds.
N_TRIALS = 10


# ---------------------------------------------------------------------------
# Suite runner
# ---------------------------------------------------------------------------

def run_suite(seed=42):
    random.seed(seed)

    header = (
        f"{'GROUP':<45} | {'RANGE':<9} | "
        f"{'FAIL%':<6} | {'AVG_COM':<7} | {'BEST(BAL)':<10} | "
        f"{'DIR%':<5} | {'1ST%':<5} | {'2ST%':<5} | {'TIME(s)':<7}"
    )
    print(header)
    print("-" * len(header))

    suite_start = time.time()

    for origin_group, frange in itertools.product(ORIGIN_GROUPS, FLIGHT_RANGES):
        min_f, max_f = frange
        t0 = time.time()

        failure_count = 0
        common_counts = []
        last_best = None
        dir_pcts, one_pcts, two_pcts = [], [], []

        for _ in range(N_TRIALS):
            batches = engine.collect_simulations(
                origin_types=origin_group,
                min_per_batch=min_f,
                max_per_batch=max_f,
            )
            common = engine.find_common_acronyms(batches)
            common_counts.append(len(common))
            if not common:
                failure_count += 1
            else:
                last_best, _, _ = engine.analyze_metrics(batches, strategy="balanced", common_names=common)
                stops = engine.analyze_stops_metrics(batches, common_names=common)
                dir_pcts.append(stops["direct_pct"])
                one_pcts.append(stops["one_stop_pct"])
                two_pcts.append(stops["two_stop_pct"])

        elapsed      = time.time() - t0
        failure_rate = round(100.0 * failure_count / N_TRIALS, 0)
        avg_common   = round(statistics.mean(common_counts), 1)
        group_str    = "+".join(sorted(origin_group))
        range_str    = f"{min_f}-{max_f}"
        best_str     = last_best or "N/A"
        dir_pct      = round(statistics.mean(dir_pcts), 1) if dir_pcts else 0.0
        one_pct      = round(statistics.mean(one_pcts), 1) if one_pcts else 0.0
        two_pct      = round(statistics.mean(two_pcts), 1) if two_pcts else 0.0

        print(
            f"{group_str:<45} | {range_str:<9} | "
            f"{failure_rate:<6.0f} | {avg_common:<7.1f} | {best_str:<10} | "
            f"{dir_pct:<5} | {one_pct:<5} | {two_pct:<5} | {elapsed:<7.3f}"
        )

    print(f"\nTotal: {time.time() - suite_start:.2f}s")


if __name__ == "__main__":
    run_suite()
