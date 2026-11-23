# Florida rejection audit and bidirectional matching — 23 November 2026

The previous kinematic trajectory generator remains active. A new, experimentally validated association score now combines its existing travel-time score with forward/backward motion evidence for **adjacent Florida intersections only**. Same-ID local reconstruction and Finch are unchanged. This is not a claim that actual vehicle identities between sensors have been verified.

## Rejection audit

The recorded 10:44:47–11:44:47 Florida window contained 14,398 departure fragments surviving the existing movement/coverage-edge filters in the evaluated adjacent links:

| Outcome under the previous matcher | Departure fragments |
|---|---:|
| Assigned | 2,294 |
| No feasible candidate edge | 10,037 |
| Had feasible candidates but remained unassigned | 2,067 |

These are endpoint opportunities across link/direction evaluations, not counts of unique vehicles. Among the 539,410 candidate pairs inside the 120-second time window, 380,433 failed the motion score, 91,452 failed direction/low endpoint speed, and 35,111 failed distance/overlap checks. Further pairs failed acceleration/distance feasibility or shape checks. Candidate-pair counts must not be interpreted as missing-vehicle counts. Coverage/movement filtering is necessary to avoid connecting vehicles that turn out of the corridor.

The contemporaneous local-layer report also recorded 216 same-ID physical rejections, 39 short gaps with insufficient endpoint context and two other local physical rejections. These are rejected proposals, not all visible gaps; an entirely unseen vehicle has no proposal to reconstruct.

## New matching score

1. Fit acceleration from up to three seconds of visible positions on each side; require at least six samples, two seconds of coverage, no large sample gap, and a bounded fit residual.
2. Project the upstream endpoint forward and the downstream endpoint backward to the midpoint. Trust acceleration only for three seconds; thereafter use constant velocity. Clamp predicted velocity to the existing nonnegative directional speed bounds.
3. Measure midpoint position and speed disagreement. Blend that score with the existing score; retain shape evidence, partial one-to-one assignment, unmatched alternatives and the original ambiguity margin.
4. Retain exact endpoint feasibility and final kinematic refinement. Colors, object IDs, hidden positions and signal permissions are not invented.

For example, when a vehicle is accelerating as it disappears, forward projection uses its visible acceleration briefly. The arrival's visible movement supplies a second, backward constraint. This changes candidate ranking, not the original measured points or the displayed curve solver. If either visible acceleration estimate is unsupported, the previous score is used.

## Selection and untouched later-interval test

Snapshot SHA-256: `19b4fc6249eb6e4b6a933b90d76569689f27fd2ca5a4e5eb23ada9554dcdfbdf`.

Selection used tracks entirely within 10:44:47–11:14:17. Testing used tracks entirely within 11:15:17–11:44:47, excluding any site/session/object identity present before the split. The fixed candidates were 25% and 50% bidirectional weighting; 50% was selected before reading test results. This is a later, previously unscored interval within the rolling recording, **not a separate independent day**.

Each car supplies a 20/50/100 m spatial mask and, when possible, a 5/15/30/60 s temporal mask. Candidate pools retain a contiguous group of up to 20 nearby fragments per site/direction/gap type. Both complete and deliberately missing-endpoint scenarios are tested. Identity is used only for scoring and split exclusion. Counts reuse vehicles/scenarios and are correlated.

| Held-out test | Eligible scenarios | Previous correct / wrong | Bidirectional correct / wrong |
|---|---:|---:|---:|
| Temporal gaps, unknown-identity matching | 1,369 | 270 / 10 | 279 / 10 |
| Spatial strips, proxy for adjacent sensors | 994 | 839 / 7 | 859 / 4 |

The temporal comparison is an experiment in fragment association; it is **not a comparison against production's stronger same-ID local reconstruction**. It therefore does not authorize replacing local ID checks. It adds 12 correct temporal scenarios but loses three; the spatial comparison adds 20 and loses none. The added correct scenarios correspond to nine temporal and 15 spatial distinct recorded identities, respectively.

Accepted correct-path mean position error changes from 1.331 to 1.368 m for temporal gaps, and 0.763 to 0.778 m for spatial strips, because the accepted set changes. Newly recovered spatial cases average 1.389 m error. The curve solver is unchanged; this experiment improves association counts, not the shape of already accepted trajectories. No real intermediate-road ground truth exists.

Deployment required improvements during selection, no additional wrong matches in either task on the held-out interval, and at least 20 additional correct test scenarios overall. The selected candidate passed with 29 additional correct and three fewer wrong. This is sufficient for the existing **experimental** between-intersection layer, not field validation.

## What is deployed and verified

`config/reconstruction/florida-bidirectional.json` enables the new score for Florida. The previous shape/feasibility matcher remains available by disabling this configuration. The constant-color experiment remains disabled.

On the same live snapshot, displayed between-intersection paths changed from 2,294 to 2,288; local paths remained 968. Fewer displayed paths do not establish worse accuracy, just as more paths would not establish correct vehicle identity. The masked test, rather than the number of dashed lines, is the evidence for the change.

46 science/regression tests and five dashboard API tests passed. Tests cover forward/backward signs, acceleration extraction, context gaps, preservation of physical gates, agreement with the published matcher when the new weighting is zero, and unchanged observed inputs. JavaScript syntax and diff checks passed.

Files: `data/reconstruction/bidirectional-review/{protocol,validation,test,rejections,report}.json` and `comparison.png`. The dashboard's method-comparison panel reports the new test separately from historical benchmarks.

- [Florida figures](http://127.0.0.1:8775/florida_rolling.html?between=1)
- [Combined dashboard](http://127.0.0.1:8775/)

Unresolved tasks: verify clock offsets and geometry independently; validate changed-ID local association with its actual lateral/clock/movement gates; obtain reference identities between sensors. Do not remove physical gates or fabricate vehicles to eliminate the remaining gaps.
