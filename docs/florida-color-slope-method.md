# Florida speed-color and constant-slope reconstruction

Implemented 23 November 2026, only for Florida. The configuration is `config/reconstruction/florida-color-slope.json`. Disabling it restores the previous Florida method; Finch is unchanged.

The two existing checkboxes remain separate: local missing segments and connections between consecutive intersections. Observations are never edited. Dashed segments are estimates, with the existing speed color scale.

## Algorithm and concrete example

The display is continuous HSL: 0 m/s is red, 10 m/s yellow, and 20+ m/s green. Exact equality of continuous colors would discard nearly all noisy measurements. The matching key therefore uses 1 m/s bands of endpoint displayed speed, equivalent to six hue degrees below saturation. Direction and endpoint slopes must also agree; saturated green alone does not match every fast vehicle.

For each departure in time order, compute a robust final slope from at least five observations covering one second. Project that slope to each eligible arrival's start time. Require the same speed-color band and choose the smallest absolute spatial residual. Each arrival is used at most once. Candidates within 0.25 m of the best residual remain ambiguous and unmatched. Local fragments cannot cross recording sessions. Existing corridor exit/entry and coverage-edge filtering remains active between adjacent sites; turning out of the corridor does not justify a through connection.

Example: a vehicle ends at time 0, position 0, speed 10 m/s. An arrival at time 10, position 100 matches exactly and receives a straight dashed line. An arrival at position 101 requires a 1 m correction: retain 10 m/s for the first eight seconds, then 10.5 m/s for the last two. This explicitly relaxes the original slope only where the user's minimum-distance fallback requires it. A single line cannot both preserve its original slope everywhere and end at an off-line point. We do not draw a vertical instantaneous jump or overwrite observations to conceal the discrepancy.

Limits: 90-second local / 120-second inter-site gaps, 350 m displacement, 10 m local / 20 m inter-site residual, endpoint slope difference at most 1 m/s, final correction at most 0.5 m/s, no reversal or speed above 35 m/s. The correction bound further restricts allowable residual to 0.1 times gap duration. Stationary paths cannot travel more than 0.5 m. These are transparent conservative defaults, not field-calibrated thresholds. New local IDs and all cross-sensor identities remain unverified. The method connects to the start of the upcoming observation; it does not draw through already observed portions to seek a later intersection.

## Recorded-data check

Command: `.venv-deepctm/bin/python -m deepctm.validate_color_slope --snapshot data/florida-rolling/snapshot.json --report data/reconstruction/word-v1-collection/evaluation-001/report.json --output data/reconstruction/color-slope/validation.json`.

The check hides 5, 10, 20, 30 and 60 seconds from continuous car tracks. A deterministic hashed order selects up to 20 eligible tracks per site and gap length. Hidden positions are never used by the matcher. The report records the exact snapshot SHA-256. This is a retrospective check of the requested fixed baseline, not a trained-model test or evidence of improvement over the previous method. Multiple masks may come from the same vehicle.

| Method | Accepted / 700 hidden gaps | Mean position error, accepted gaps | Mean error on 15 jointly accepted gaps |
|---|---:|---:|---:|
| Speed-color / constant slope | 28 / 700 | 0.046 m | 0.061 m |
| Strict previous kinematic reference | 306 / 700 | 2.308 m | 0.050 m |

The new method's accepted-case 95th-percentile error was 0.095 m. It matched 28 of 700 masked identities correctly with zero wrong matches in this small candidate-pool check. This does not imply zero errors in dense real traffic or verified identity between sensors. Low accepted-case error largely reflects selective acceptance of easy constant-speed/stationary gaps. It recovered far fewer gaps than the reference and did not improve error on the common subset. It is not a solution for acceleration, queues or arbitrary outages.

48 relevant tests passed, including chronological ordering, one-to-one assignment, same-color selection, ties, opposite travel directions, endpoint correction, unchanged input observations and existing reconstruction/matching regression tests. JavaScript syntax and Python compilation checks passed.

The dashboard labels this method experimental and shows its own masked-data results. Original measurements remain solid. An absence of suitable same-color evidence still leaves a gap.

Four dashboard API tests also passed. Browser verification showed the new method label, both enabled layer controls, and 74 local / 16 inter-site estimates in the eastbound full-hour selection (116 / 21 across both directions). Counts change with each rolling snapshot. The compact API now avoids loading unrelated archived study reports.

## Restored default

On 23 November 2026, at the user’s request, disabled the color-slope experiment and restored the previous kinematic reconstruction with its existing endpoint corrections, local fallbacks and shape/feasibility association policy. The experimental implementation and its validation remain available in the repository, but are not the active Florida method.
