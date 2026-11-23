# Florida and Finch reconstruction review — 23 November 2026

Work period: 04:22–12:22 UTC (22 November 23:22–23 November 07:22 Toronto), approximately eight hours. This combined implementation, live collection, prospective masked-data validation and browser verification. The bounded evaluation worker runs existing experiments; it is not continuous model reasoning.

## What changed

- Retain received frames through a bounded journal instead of sampling only the latest cache. A 57-second audit retained all 3,684 Florida and 5,013 Finch journal frames; this does not establish lossless upstream delivery.
- Use partial assignment, trajectory shape and exact kinematic feasibility for matching. Unmatched candidates remain unmatched.
- Correct small stationary endpoint-speed noise only at sites that passed the checks. Add a refined endpoint time grid and a tightly bounded stationary-position fallback. These local fallbacks never connect different sensors. Stationary estimates can differ from measured endpoints by at most 5 cm; raw observations are unchanged.
- Correct provisional Driftwood and Norfinch alignment using road geometry and independent vehicle segments.
- Fix a live-frame freshness race and SQLite validation-copy starvation. Bound copy duration and use automatically removed temporary storage.
- Keep within-intersection and between-intersection estimates separately selectable, dashed and explicitly provisional.

## Validation

The campaign freezes parameters before evaluating later recordings, excludes earlier identities, and uses a time embargo. It hides recorded segments so predictions can be compared with observations. Repeated gap lengths are correlated cases. Matching tests split known local tracks into fragments: they are not proof of identity across real sensors.

| Corridor | Evaluated matching scenarios | Correct: reference → improved | False: reference → improved |
|---|---:|---:|---:|
| Florida | 7,553 | 5,847 → 6,549 | 21 → 23 |
| Finch | 7,685 | 5,090 → 5,479 | 54 → 43 |

These are paired feasibility-gate comparisons, not measured cross-intersection identity accuracy. Florida gains coverage with two additional false matches; Finch improves both counts.


The refined-grid fallback added 14 Florida identities with mean position error 0.172 m and 24 Finch identities with 0.159 m in its prospective checks. Stationary-position checks had mean error 0.015 m (23 Florida masks) and 0.012 m (55 Finch masks, 51 identities); production site exclusions still apply. These small-error subsets do not describe all gaps.

The additional November 6 Finch recording improved correct masked associations from 2,455 to 2,620 and reduced false associations from 15 to 8 across 3,133 scenarios. This is an additional recording check, not a never-used dataset. York Gate and Florida Hattaway stationary corrections remain withheld after poor external results. The quadratic-solver extension failed prospective error thresholds; the smoother worsened tail errors. Neither was enabled merely to fill more space.

214 science tests and 11 relevant dashboard tests passed, with JavaScript syntax checking. The database snapshot concurrency/deadline tests also passed after switching its target to temporary storage.

## Dashboard verification

Browser checks around 07:20 Toronto confirmed both one-hour figures, their two enabled layer controls and visible results. Eastbound counts for the 06:14–07:14 hour were Florida 118 local / 843 between, and Finch 332 local / 226 between. These are snapshot counts, not before/after validation gains. All seven Florida and nine authorized Finch collectors were fresh in the final health check; Jane remains unauthorized. Brief interruptions occurred and are not concealed.

- [Combined live dashboard](http://127.0.0.1:8775/)
- [Florida figures](http://127.0.0.1:8775/florida_rolling.html?between=1)
- [Finch figures](http://127.0.0.1:8775/finch_rolling.html?between=1)

These addresses work on the hosting computer. Collectors and dashboard remain running; raw trajectory retention is bounded to 90 minutes and rolling figures cover up to one hour, refreshed every 30 minutes.

## What remains unresolved

Zero disconnected trajectories was not achieved. Entirely unobserved vehicles have no endpoints; turning/exiting vehicles should not be joined to unrelated arrivals. Long outages, overlapping sensor coverage, uncertain clocks and ambiguous candidates remain unresolved. Actual cross-sensor vehicle identity, signal-to-movement mapping and surveyed geometry are unverified. This is not a field-validated full CTM–Newell–signal system. It implements and evaluates constrained kinematic reconstruction and matching components. The user explicitly chose unresolved gaps over fabricated continuations.

Saved evidence: `data/reconstruction/eight-hour-20261123/summary.json`, per-region cycle reports, `masked-examples.png`, `finch-dashboard-final.jpg`, and `data/reconstruction/external-capture-review/finch-validation.png`. The detailed learning guide is [florida-word-method-implementation.md](florida-word-method-implementation.md).
