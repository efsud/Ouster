# Florida: correcting moderate delivery delays before reconstruction

November 23, 2026. This is a validated experimental preprocessing improvement with explicit per-site opt-in. It adjusts supported observation times; it does not generate observations, move recorded positions, prove vehicle identity, or verify field KPIs.

## Cause and change

The existing bounded correction searched for a single receipt-time step greater than 1.5 seconds. Smaller delivery bursts could still break a vehicle's plotted trajectory or distort the endpoint slope used to match its next fragment. They were invisible to that trigger even when the SDK timestamp remained continuous.

`deepctm/moderate_delivery_timing.py` preserves the existing correction and additionally considers receipt steps greater than 0.5 and at most 1.5 seconds, with at least 0.25 seconds of excess delay. It requires five stable preceding frames and a stable return anchor; sensor intervals must remain positive and at most 1.5 seconds. Existing bounds remain: at most 60 seconds between anchors, at most 15 seconds of delay, at most 1% clock-rate discrepancy and 0.2-second anchor tolerance. No return anchor, clock reset, duplicate sensor time or unsupported delay means no repair.

Example: a sensor continues capturing every 0.1 seconds, but delivery temporarily incurs 0.8 seconds of extra delay. A 0.9-second receipt step does not activate the old trigger. Once delivery catches up and both anchors pass the checks, the recorded frames can be placed using their continuous sensor elapsed times between those unchanged anchors. Missing frames are not invented. Original receipt timestamps and payloads are retained.

The adapter `correct_for_build` returns the normal list-shaped clock audit and labels each added event `moderate_bounded_delivery_v1`. The pipeline decides which sites may use it; importing the module alone does not enable it. The five qualifying sites below are enabled in `config/reconstruction/florida-delivery-timing.json`; Renaissance and Boston retain the earlier method.

## Evidence from recorded Florida data

An initial timestamp-only audit of 13:14:49–14:14:49 EST found 225 same-ID gap pairs whose previously disagreeing clocks became consistent, with no previously consistent pairs becoming inconsistent. That is a diagnostic count, not trajectory reconstruction accuracy.

A separate frozen recording window, **13:43:30–14:43:30 EST**, supplied paired hidden-position validation. The earlier half was development; the later test excluded early identities and used a 30-second embargo. Both methods hid exactly the same measured position rows. Sampling was deterministic, with 5-, 10- and 20-second masks. All 250,849 source rows were preserved, and the frozen source had zero duplicate `(site, session, receipt)` keys.

The decision required improvement in both development and test, at least 20 affected identities and 20 commonly accepted identities, no increase in common position or speed error, no physics violations and negligible unaffected-case change. It was reviewed separately for every site.

| Site | Timing decision | Reason |
| --- | --- | --- |
| Cranes Roost | Eligible | Both partitions pass |
| Hattaway | Eligible | Both partitions pass |
| Renaissance | Keep previous correction | Only two development identities; speed error increased |
| Essex | Eligible | Both partitions pass |
| Plaza Entrance | Eligible | Both partitions pass |
| Palm Springs | Eligible | Both partitions pass |
| Boston | Keep previous correction | Seven commonly accepted development identities; slight regression |

For the **five eligible sites**, pooled later-test results were:

| Measure | Previous correction | Moderate correction |
| --- | ---: | ---: |
| Accepted affected gap masks | 583 | 754 |
| Common-mask position MAE | 2.234 m | 1.461 m |
| Common-mask speed MAE | 0.948 m/s | 0.593 m/s |
| Physics violations | 0 | 0 |

Common errors use the same 571 masks from 264 distinct identities. They are pooled from individual cases, not averaged across sites. Across all seven candidates the aggregate improved too, but that did not override the two site restrictions.

## Effect on matching between intersections

A second paired experiment hid 20-, 50- and 100-metre roadway sections from measured same-sensor trajectories, with complete and missing-arrival scenarios. It compared the intended five-site deployment against the current timing, preserving the same position rows and keeping the two withheld sites unchanged. Parameters were fixed before evaluation.

| Partition | Correct matches before → after | Wrong matches before → after |
| --- | ---: | ---: |
| Development | 4,163 → 4,193 | 28 → 28 |
| Later test | 4,101 → 4,195 | 15 → 11 |

No site lost correct matches or gained wrong matches in either partition. Later results for the five changed sites:

| Site | Correct before → after | Wrong before → after |
| --- | ---: | ---: |
| Cranes Roost | 453 → 454 | 0 → 0 |
| Hattaway | 769 → 826 | 1 → 1 |
| Essex | 824 → 844 | 2 → 0 |
| Plaza Entrance | 860 → 864 | 8 → 8 |
| Palm Springs | 421 → 433 | 4 → 2 |

These are same-sensor spatial proxies, not independently verified vehicle identities between sensors. The 11 remaining wrong test associations prevent any claim of perfect reconstruction.

## Limits and reproducibility

Position validation used cars (API class 2). Timing is a frame property, but reconstruction errors for other classes were not measured separately here. Masks and scenarios overlap; counts are not independent vehicles. Selection uses tracks continuous on the candidate timeline, so this is conditional interpolation evidence rather than corridor-wide recall. Each method's hidden positions use its own time assignment: lower errors demonstrate timing/interpolation consistency, not independent event-clock truth. Absolute cross-sensor synchronization remains unverified.

Evidence is under `data/reconstruction/moderate-delivery-validation/`: protocol, row preservation and uniqueness checks, development/test cases, gate assessment, qualified-site pooled scores, and matching validation. The earlier timestamp diagnostic is preserved separately under `delivery-candidate-review/`.

To reproduce on a fresh retained recording without overwriting this evidence:

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 \
  .venv-deepctm/bin/python -m deepctm.validate_moderate_delivery \
  --output data/reconstruction/moderate-delivery-next
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 \
  .venv-deepctm/bin/python -m deepctm.validate_moderate_matching \
  --output data/reconstruction/moderate-delivery-next
```

The validation scripts do not enable sites or change running services. Timing and provenance tests passed 13 cases; production integration is checked separately.
