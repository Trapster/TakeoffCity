# Multi-Person Simulation — Learnings

Findings from the multi-person flight simulation, modelling group travel coordination where N people each search for flights from their own departure city to a shared destination.

Each "batch" represents one person's Tequila API search results. The algorithm finds destinations that appear in **every** person's results (strict intersection), then ranks them by cost, time, or a balanced score.

---

## Setup

- **Destinations**: ~110 real IATA airport codes in three tiers (20 mega-hubs, 50 regional hubs, 40 secondary)
- **Per-person availability**: Modelled by origin type — `hub` travellers see ~86% of the pool, `medium` ~55%, `small` ~25%
- **Flight fields**: `price`, `time` (minutes), `stops` (0/1/2) — all correlated with destination tier
- **API cap**: 200 results per search, matching the Tequila API limit
- **Measurement**: 10–100 trials per configuration

---

## Failure Modes

### 1. Group size cliff — all-small groups break at N=5

The failure rate is not linear with group size; it has a sharp cliff.

| N (all small, 150–200 results) | Fail% | Avg common | P(≥3 common) |
|---|---|---|---|
| 2 | 0% | 9.8 | 100% |
| 3 | 2% | 4.0 | 83% |
| 4 | 11% | 1.7 | 24% |
| 5 | **49%** | 0.7 | 2% |
| 6 | 67% | 0.4 | 0% |
| 7 | 90% | 0.1 | 0% |
| 8+ | 94–99% | ~0 | 0% |

**The cliff is at N=5.** Above that, even generous result counts cannot compensate — the pool is just too small. A 3-person all-small group is almost always viable; a 7-person all-small group is essentially broken.

---

### 2. A single small-origin traveller cuts available destinations by 65%

Adding just one small-origin traveller to an otherwise all-hub group causes a massive drop in common destinations, not a gradual one.

| Composition (5 people, 150–200 range) | Fail% | Avg common |
|---|---|---|
| 5× hub | 0% | 73.0 |
| 4× hub + 1× small | 0% | **25.5** |
| 3× hub + 2× small | 0% | 9.4 |
| 2× hub + 3× small | 1% | 3.7 |
| 1× hub + 4× small | 15% | 1.5 |
| 5× small | 45% | 0.7 |

Going from 0 to 1 small traveller reduces avg_common from 73 to 25.5 — a 65% drop. This person is the bottleneck, and the drop is disproportionate because their restricted pool eliminates entire tiers of destinations from the intersection.

---

### 3. Minimum ~50 results per person needed, even for all-hub groups

Result count has a hard floor below which failure is near-certain regardless of origin types.

| Results per person (5× hub) | Fail% | Avg common |
|---|---|---|
| 1 | 100% | 0.0 |
| 10 | 100% | 0.0 |
| 20 | 83% | 0.2 |
| 30 | 30% | 1.2 |
| **50** | **0%** | **9.5** |
| 80+ | 0% | 53–73 |

Below 30 results per person, even an all-hub group of 5 will usually fail. The Tequila API returns up to 200 results, so this is achievable — but it means the product must request a full result set, not early-terminate.

---

### 4. Large groups (N≥15) always fail with realistic origin mixes

| Group | Range | Fail% |
|---|---|---|
| 15-person (half medium, half small) | 150–200 | **100%** |
| 20-person (half medium, half small) | 150–200 | **100%** |
| 10-person mixed | 10–50 | 100% |
| 10-person mixed | 150–200 | 40% |

Groups of 15+ with any small-origin travellers produce zero common destinations in every tested trial. The strict intersection is not a viable approach for large groups.

---

### 5. More results do not help small-origin travellers

Giving small-origin travellers the maximum 200 results does not reduce failure — their airport pool is structurally limited, not result-count limited.

- `5× small + range(40–200)` → 30% failure
- `5× small + range(150–200)` → **40% failure** (worse)

The slight worsening at higher counts is noise from the random pool selection, but the point stands: availability is the constraint, not query size.

---

### 6. Strategies almost never agree on the best destination

Across 200 runs of a 5-hub group with 40–200 results:

- All 5 strategies (total_cost, worst_case_cost, total_time, worst_case_time, balanced) agreed on the same winner: **1 run out of 200 (0.5%)**

The choice of optimisation strategy is nearly always decisive. A product that presents a single "best" destination is implicitly making a strategy choice users may not have intended.

**Product opportunity**: surfacing this choice explicitly is a UX feature, not just a technical detail. Different travellers have different priorities — a group trying to minimise total spend has different needs to one trying to minimise the worst-case journey for any single person. Letting users pick (or vote on) the ranking strategy — "cheapest overall", "fairest for everyone", "shortest travel time" — would make the product's recommendation feel like *their* decision rather than a black box. It also creates a natural conversation point within the group.

---

### 7. Balanced score = 0.0 is misleading when there is only 1 common destination

When exactly 1 common destination survives the intersection (common in all-small or large groups), the balanced score is always 0.0 — because min-max normalisation over a single point collapses to zero. This looks like a perfect score but conveys no information. In 38% of all-small 5-person trials, this is the reported result.

---

### 8. Tie-breaking is non-deterministic

When multiple destinations have identical balanced scores (e.g. all 0.0 with a single common airport, or all equal price+time), `min()` on a dict derived from a Python `set` picks based on hash-insertion order — effectively random across runs. In practice this affected 33 distinct airports as "best" across 200 single-common-destination trials, cycling between CDG, DFW, ATL, AMS, MAD, and others with no consistency.

---

## Earlier Findings (still valid)

### 9. Failure is driven by group size × small-origin ratio × result count

The three factors combine multiplicatively. The table below shows how they interact:

| Group | Range | Failure Rate |
|---|---|---|
| 5× hub | 10–50 | 50% |
| 5× hub | 40–200 | 0% |
| 5× small | 40–200 | 30% |
| 1 hub + 4 small | 40–200 | 20% |
| 10-person mixed | 10–50 | 100% |
| 2-person (medium + small) | 10–50 | 0% |

### 10. Tier-1 hubs dominate the surviving common set

When common destinations exist, they are almost exclusively tier-1 mega-hubs (CDG, LHR, DXB, SIN, NRT, etc.). The algorithm confirms feasibility but does not surface interesting or novel destinations.

### 11. Direct flight % rises as small-origin ratio rises

As small-origin travellers increasingly dominate the group, the surviving common destinations are only the very best-connected hubs — which also have the highest direct-service rates (40–70%). Paradoxically, the groups most constrained in destination choice tend to get the best connection quality on the flights they do find.

---

## Product Opportunity Simulations

### A. Departure flexibility — asking "can you travel to a nearby airport?" is high leverage

Upgrading a small-origin traveller to medium (they drive 45 min to a larger airport) has a large effect:

| Composition (5 people, 40–200 range) | Fail% | Avg common | P(≥3 common) |
|---|---|---|---|
| 5× small | 44% | 0.7 | 1% |
| 4× small + 1 upgraded to medium | 26% | 1.2 | 10% |
| 3× small + 2 upgraded to medium | 8% | 2.1 | 34% |
| 3× hub + 2 small | 0% | 8.3 | 99% |
| 3× hub + 2 upgraded small → medium | 0% | **30.0** | 100% |

A single traveller agreeing to use a nearby hub airport transforms a constrained group into a healthy one. Upgrading the 2 smalls in a mixed hub group jumps avg_common from 8.3 → 30.0.

**Product opportunity**: Before running the group search, ask each traveller if they can depart from a nearby larger airport. A simple yes/no question at onboarding could recover the majority of otherwise-failed searches. The question is most valuable targeted at small-origin travellers specifically.

---

### B. Coverage threshold — allowing one person to miss unlocks dramatically more destinations

For a 5-person group, these thresholds map as follows (due to rounding): 100% = all 5, 80–90% = 4 of 5, 60–70% = 3 of 5.

**Mixed 5-person group (hub+med+med+small+small), 40–200 range:**

| Threshold | Fail% | Avg common | P(≥10 common) |
|---|---|---|---|
| 100% (all 5) | 0% | 5.1 | 1% |
| 90% → 80% (4 of 5) | 0% | 24.0 | 100% |
| 60% (3 of 5) | 0% | 54.2 | 100% |

**5× small (hardest case):**

| Threshold | Fail% | Avg common | P(≥3 common) |
|---|---|---|---|
| 100% | 45% | 0.7 | 3% |
| 90% → 80% (4 of 5) | 0% | 5.2 | 96% |
| 60% (3 of 5) | 0% | 18.6 | 100% |

Allowing just one person to miss a destination (4 of 5 must be able to reach it) eliminates failure entirely and multiplies available destinations by ~5×. This is the single most impactful algorithmic change possible.

**Product opportunity**: "Everyone must make it" should not be the hardcoded default. The natural UX is "find destinations at least 4 of your 5 travellers can reach, and show who can't make each one." The person who can't make the top choice becomes a feature ("here's what [name] would need to do differently") rather than a silent failure mode.

---

### C. Cost fairness — someone pays materially more in ~70% of successful searches

Coefficient of variation (CV = std/mean) of per-person cost to the winning destination:

| Composition | Avg CV | CV > 0.3 rate |
|---|---|---|
| 5× hub | 0.37 | 69% |
| 5× medium | 0.38 | 75% |
| 5× small | 0.35 | 67% |
| hub+med+med+small+small | 0.38 | 79% |
| hub+small×4 | 0.36 | 72% |

CV > 0.3 means someone is paying a materially different amount to the rest of the group. This happens in 67–79% of successful searches, regardless of group composition. The unfairness is intrinsic to flight pricing variation, not the group mix.

**Product opportunity**: Cost fairness is not an edge case — it is the default condition. The product should surface per-person cost breakdowns alongside the group recommendation, and offer a "fairest split" strategy as a first-class option. Groups who see individual costs are more likely to have a meaningful conversation about destination choice; groups who only see a "total" may commit to a destination where one person is paying 2× the others.

---

### D. Bottleneck attribution — small-origin travellers are the bottleneck in 97% of cases

When one traveller is removed and the intersection grows the most, that person is the bottleneck. Across 300 trials of a hub+medium+small+small+small group:

| Traveller | Bottleneck% | Avg destinations unlocked |
|---|---|---|
| hub | 1% | +3.0 |
| medium | 2% | +3.4 |
| small-1 | 43% | +5.1 |
| small-2 | 31% | +5.5 |
| small-3 | 23% | +5.7 |

In the realistic mixed group (hub+med+med+small+small), the two small travellers are the bottleneck in 98% of trials, each unlocking ~9 additional destinations when removed.

**Product opportunity**: When a search returns few results, the product can identify the bottleneck traveller and tell them specifically: *"If you can fly from a nearby hub, your group would have 9 more destination options."* This is more actionable than a generic "no results found" state. Critically — removing one bottleneck person always helped (0% of trials had zero gain after removal), making this a reliable signal rather than a heuristic.

---

### E. Confidence/richness bands — group composition predicts search quality before running it

| Config | Dead end | Constrained | Viable | Healthy |
|---|---|---|---|---|
| 5× hub, 40–200 | 0% | 0% | 0% | **100%** |
| 5× medium, 40–200 | 0% | 0% | 9% | 91% |
| 2-person (med+small), 40–200 | 0% | 0% | 1% | 99% |
| mixed 5, 40–200 | 0% | 24% | **76%** | 0% |
| 5× small, 40–200 | **41%** | 59% | 0% | 0% |
| 5× hub, 10–50 | **40%** | 53% | 7% | 0% |
| mixed 5, 10–50 | **45%** | 53% | 1% | 0% |
| 10-person mix, 150–200 | **53%** | 47% | 0% | 0% |

*(Bands: dead end = 0 common, constrained = 1–3, viable = 4–10, healthy = 11+)*

The group composition and result count alone are strong predictors of outcome — before any API call is made. All-hub groups at full result counts are always healthy. Any 10-person group is usually a dead end. Mixed groups with smalls are almost always in the viable-but-not-healthy zone.

**Product opportunity**: The product can predict search quality at group setup time and set expectations before running the search. If the group has multiple small-origin travellers or more than 8 people, the UI can proactively prompt departure flexibility questions and explain why. This prevents the "no results" surprise, which is the worst possible UX outcome.

---

### F. Destination diversity — tier-1 hubs win 97–99% of the time even when tier-2 options exist

| Config | Winner is T1 | T2 options in pool | Avg T2 options available |
|---|---|---|---|
| 5× hub, 40–200 | 99% | 100% | 32.4 |
| 5× medium, 40–200 | 98% | 100% | 7.5 |
| mixed 5, 40–200 | 97% | 89% | 1.9 |

Even for an all-hub group where 32 tier-2 regional hub destinations are available in the common set, the algorithm picks a tier-1 mega-hub 99% of the time. This is partly a pricing model artifact (tier-1 routes are more competitive) and partly real — but it means the product will always recommend CDG, LHR, DXB, SIN etc. and never surface Barcelona, Vienna, or Copenhagen even when those are viable.

**Product opportunity**: Destination diversity should be a selectable mode. "Best value" will always converge on mega-hubs; "interesting destinations" should filter to tier-2 and present the trade-off in price/time explicitly. The data shows there are usually viable tier-2 options — the algorithm just never picks them.

---

## Recommended Algorithm Improvements

In priority order:

1. **Replace strict intersection with threshold-based overlap** (e.g. reachable by ≥ 80% of travellers). This is the single highest-impact change — it recovers nearly all failed searches and keeps the algorithm tractable.

2. **Surface "who is the bottleneck"** — if a destination is reachable by N−1 of N people, identify which traveller is the blocker and show alternatives for them. This converts a dead end into a conversation.

3. **Fix tie-breaking** — when balanced scores are equal, break ties with a deterministic secondary key (e.g. alphabetical code, or cheapest total price) rather than relying on dict insertion order.

4. **Report strategy disagreement to the user** — when different strategies produce different winners, show the top 2–3 options with their trade-off rather than forcing a single answer.

5. **Add a minimum group coverage parameter** — let users configure "everyone must make it" vs "at least 4 of 5 must make it."

---

---

## Temporal Simulation Findings

A new simulation layer (`dates.py`, `temporal_simulation.py`) added three dimensions:
- **Event window**: 7, 14, 21, or 30 days
- **Arrival tolerance**: 0–3 days (traveller can arrive early to catch more flights)
- **Min overlap days**: minimum days the whole group must be simultaneously present (1, 2, 3, or 5)

Route frequency by tier: T1=daily, T2=5×/week, T3=3×/week. Per-person availability fraction by origin type: hub 65–100%, medium 50–90%, small 35–75% of window.

*(20 trials per cell, group size 5 except the 10-person group)*

---

### T1. Short windows + min-overlap requirements break even all-hub groups

| Group | Window | Tolerance | Min overlap | Fail% |
|---|---|---|---|---|
| 5× hub | 7 | 0 | 1 | 0% |
| 5× hub | 7 | 0 | 3 | **35%** |
| 5× hub | 7 | 0 | 5 | **90%** |
| 5× hub | 14 | 0 | 5 | **0%** |

A 7-day window with a 5-day minimum overlap (e.g. "everyone must be there Mon–Fri") fails 90% of the time even for an all-hub group — simply because each person can only travel part of the window and route schedules don't always align. Doubling the window to 14 days eliminates failure entirely.

**Insight**: Requiring every traveller to overlap for most of a short window is structurally unrealistic. The product should surface how many overlap days are actually achievable rather than assuming "everyone's there the whole time."

---

### T2. A single day of arrival tolerance rescues realistic groups in short windows

| Group | Window | Tolerance | Min overlap | Fail% |
|---|---|---|---|---|
| 1hub+2med+2small | 7 | 0 | 1 | 25% |
| 1hub+2med+2small | 7 | **1** | 1 | **0%** |
| 5× medium | 7 | 0 | 3 | 75% |
| 5× medium | 7 | **2** | 3 | **0%** |

For the realistic 5-person group, 1 day of tolerance eliminates failure entirely in a 7-day window. For all-medium groups needing 3 overlap days, 2 days of tolerance drops failure from 75% to 0%.

**Insight**: This is the most impactful single UX question the product can ask: "Can you arrive a day early?" It costs the traveller almost nothing but unlocks dramatically more destinations, especially for tier-3 routes that only operate 3×/week.

---

### T3. Window size rescues hub/medium groups but not all-small groups

| Group | Window | Tolerance | Min overlap | Fail% |
|---|---|---|---|---|
| 5× small | 7 | 0 | 1 | 55% |
| 5× small | 14 | 0 | 1 | 55% |
| 5× small | 21 | 0 | 1 | 55% |
| 5× small | 30 | 0 | 1 | 45% |
| 5× hub | 7 | 0 | 1 | 0% |
| 5× hub | 14 | 0 | 1 | 0% |

Extending the window from 7 to 30 days barely moves the failure rate for all-small groups (55% → 45%). The structural limitation is their restricted airport pool, not their schedule. More days doesn't help when the available destinations are already few.

**Insight**: For all-small groups, temporal flexibility is nearly irrelevant. The product should immediately prompt departure flexibility (nearby larger airport) rather than asking about date flexibility.

---

### T4. Arrival tolerance outperforms window extension for constrained groups

For a 7-day window with realistic groups, tolerance is a more efficient lever than window size:

| Group | Window | Tolerance | Fail% |
|---|---|---|---|
| 1hub+4xsmall | 7 | 0 | 55% |
| 1hub+4xsmall | 7 | 3 | 25% |
| 1hub+4xsmall | 14 | 0 | 25% |
| 1hub+4xsmall | 21 | 0 | 5% |
| 1hub+4xsmall | 21 | 1 | 30% (high variance) |

3 days of tolerance within a 7-day window achieves the same failure rate as a 14-day window at 0 tolerance. This makes sense: tolerance adds flight options for tier-3 routes (3×/week) without requiring the group to commit to a longer trip.

---

### T5. Large groups (10-person) are not rescued by temporal flexibility

| Group | Window | Tolerance | Min overlap | Fail% |
|---|---|---|---|---|
| 2hub+4med+4small | 7 | 0 | 1 | 70% |
| 2hub+4med+4small | 14 | 3 | 1 | 65% |
| 2hub+4med+4small | 21 | 3 | 1 | 60% |
| 2hub+4med+4small | 30 | 3 | 1 | 65% |

Failure rates across all 10-person configurations hover at 40–95% regardless of window or tolerance. The strict 10-way intersection is the binding constraint; no amount of date flexibility can overcome the airport pool problem at scale.

**Insight**: For groups of 10+, the product must use threshold-based overlap (e.g. "8 of 10 must reach it") rather than strict intersection. Temporal flexibility is not the solution for large groups.

---

### T6. Overlap days grow linearly with window but plateau for small-origin groups

For 5× hub:
- 7-day window → avg 3.6 overlap days at top destination
- 14-day → 8.1 overlap days
- 21-day → 13.1 overlap days
- 30-day → 18–22 overlap days

For 5× small (when search succeeds):
- 7-day → ~1.1–3.5 overlap days (extremely tight)
- 14-day → ~3.3–6.7 overlap days
- 30-day → ~8–14 overlap days (more, but still far fewer than hub groups)

Hub groups gain ~0.6 overlap days per additional window day. Small groups gain only ~0.35 days — they're constrained by both route frequency and personal schedule.

---

### T7. Day-of-week pricing advantage is captured by groups with flexible windows

Groups with large windows (21–30 days) see 5–12% lower costs than equivalent groups with 7-day windows, reflecting that they can choose departures on cheaper mid-week days. For hub groups:

| Window | Avg cost (5× hub) |
|---|---|
| 7 days | ~1105–1245 |
| 14 days | ~1151–1240 |
| 21 days | ~1163–1246 |
| 30 days | ~1106–1219 |

The effect is modest (~10%) because tier-1 routes run daily and price variation is bounded. For small groups, day-of-week effects are less visible because they rarely have the flexibility to choose.

---

### T8. The compound failure mode: small-origin + short window + min-overlap ≥ 3

| Group | Window | Tolerance | Min overlap | Fail% |
|---|---|---|---|---|
| 5× small | 7 | 0 | 3 | **100%** |
| 5× small | 14 | 0 | 3 | **45%** |
| 5× small | 30 | 3 | 3 | **40%** |
| 1hub+2med+2small | 7 | 0 | 3 | **90%** |
| 1hub+2med+2small | 14 | 1 | 3 | **5%** |

When three constraints combine — small-origin travellers + short window + requiring 3+ group overlap days — failure is near-certain. The product must not present "when does everyone arrive?" as a post-search question; it should predict and surface this failure mode before running the search.

---

### Temporal Product Opportunities

**P1**: Ask "Can you arrive a day early?" before running any search involving non-hub travellers in windows under 14 days. The simulation shows this single question eliminates failure entirely for realistic mixed groups.

**P2**: For windows under 10 days, warn the group that requiring 3+ shared overlap days will likely fail, and suggest either extending the window or reducing the required overlap ("let's all aim to be there for at least the first 2 days").

**P3**: Distinguish "flight flexibility" (can you leave on a different day?) from "trip flexibility" (can you extend the trip?). These are different asks with different costs to the traveller — the first is a scheduling tweak, the second is a longer holiday.

**P4**: For all-small groups, skip temporal flexibility questions and go straight to departure flexibility (nearby airport). Window size and tolerance are irrelevant when the airport pool is the binding constraint.

---

## Simulation Limitations

- Destination availability per origin type uses fixed tier fractions. Real availability depends on specific city pairs and dates.
- Prices are randomly generated within tier ranges; real prices correlate more strongly with distance, season, and booking lead time.
- The simulation does not model date flexibility, return flights, or booking windows — all of which affect real result counts.
- All travellers are modelled as searching the same date window; differing availability windows across a group would further reduce the intersection.
- Multi-modal routes (trains, buses, connections through intermediate hubs) are not modelled — their absence makes the failure rates here an upper bound on what the real product would face.
