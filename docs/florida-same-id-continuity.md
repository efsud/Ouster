# Same-ID connections within Florida intersections

This update makes sensor/session/object identity the first basis for connecting
local fragments. Vehicle classification is not part of the identity key. It is
enabled in Florida's rolling figures and as a derived revision of the frozen
24 November hour. Finch policy is unchanged.

## What changed

The existing constrained reconstructions keep priority. Remaining consecutive
fragments with the same intersection, collector session and object ID receive a
bounded monotone cubic connection. Visible positions on both sides supply the
endpoint slope estimates. No hidden positions enter the fit. Endpoint tangents
are limited when necessary to keep the curve within its endpoints, with speed
at most 35 m/s and internal acceleration magnitude at most 4 m/s². These bounds
do not guarantee acceleration continuity where the dashed curve meets observations.
Tangent adjustments are recorded. Measured points are unchanged.

For example, a car fragment ending at time 3 s / station 30 m and a truck-labelled
fragment of the same sensor/session/ID beginning at 8 s / 80 m are connected at
10 m/s. A classification change does not create a new vehicle. A conflicting
sensor/display elapsed interval instead produces a gray identity connector,
with no speed claim. Clock resets, opposing motion, impossible average motion
and gaps over ten minutes remain unconnected. Long admitted gaps are explicitly
flagged: identity continuity does not recover their actual stop/start history.

The previous 2 m lateral cutoff and 30-second outage-only cutoff no longer
automatically reject this display fallback. Feasible lateral motion and longer
same-ID gaps are recorded as warnings. Two distinct IDs, two collector sessions
or two intersections are never joined by this method. Nested/overlapping
fragments cannot create a bridge over already observed positions.

Dashed speed-colored paths represent interpolated motion. Gray dashed lines
represent identity continuity with uncertain timing; their hover text does not
report a speed. Every added path has `kpi_eligible=false`. These are not measured
KPI inputs and are not claimed as DeepCTM or recovered ground truth.

## Fixed-hour result

For the frozen hour **13:16:39–14:16:39 EST on 24 November 2026**:

- 1,533 additional connections: 843 speed-colored and 690 gray timing connectors.
- In the original comparable audit of 1,736 vehicle gaps longer than 1.5 seconds,
  connected gaps increase from 942 to 1,721; unresolved gaps fall from 794 to 15.
- The broader new scan includes shorter breaks and cross-class transitions. Its
  16 unresolved cases comprise 15 direction conflicts and one impossible average
  displacement. These denominators must not be mixed.
- Four previously proposed between-site links were suppressed because their
  exact provenance endpoints became internal to a same-ID local chain. No new
  cross-sensor identity claims were introduced.

| Intersection | Additional connections | Gray timing connectors | Unresolved in broader scan |
| --- | ---: | ---: | ---: |
| Cranes Roost | 343 | 183 | 0 |
| Hattaway | 264 | 188 | 0 |
| Renaissance | 91 | 36 | 7 |
| Essex | 209 | 72 | 4 |
| Plaza Entrance | 132 | 38 | 2 |
| Palm Springs | 157 | 55 | 2 |
| Boston | 337 | 118 | 1 |

## Recorded-data diagnostic

The test hides positions from continuous observed tracks, fits from visible
flanks only, then compares against the hidden positions. It uses fixed mask
lengths and at most 50 distinct IDs per site/length, with one mask per ID/length.
It contains 2,393 masks from 1,235 distinct site-local IDs; masks of different
lengths can reuse a vehicle. This is the already-used development hour, not an
independent test. Timing-conflict connectors are not validated by this test.

| Nominal hidden interval | Masks | Mean position error (m) | Straight-line comparator (m) |
| --- | ---: | ---: | ---: |
| 3 s | 350 | 0.65 | 0.75 |
| 5 s | 350 | 0.71 | 1.27 |
| 10 s | 350 | 1.23 | 4.62 |
| 20 s | 350 | 2.92 | 8.44 |
| 40 s | 350 | 5.29 | 10.07 |
| 60 s | 350 | 5.79 | 10.65 |
| 120 s | 293 | 7.88 | 11.72 |

Pooled mean case error is 3.39 m versus 6.67 m for straight-line interpolation.
This is not a comparison against the previous constrained estimator: this
fallback supplements that estimator. Long gaps are substantially less certain;
the 120-second 95th-percentile case mean error is 26.94 m. No claim of complete
actual trajectory recovery or cross-sensor identity accuracy follows.

## Saved outputs and reproduction

The read-only archive in `data/frozen/florida/20261124T194525Z/` remains unchanged.
The derived layer and detailed mask results are saved separately in
`data/reconstruction/frozen/20261124T194525Z/`. Serving the derived layer requires
matching SHA-256 hashes of both original inputs and the exact frozen window.

```sh
.venv-deepctm/bin/python -m deepctm.build_same_id_continuity --capture 20261124T194525Z
```

[Open the updated frozen hour](http://127.0.0.1:8775/florida_rolling.html?frozen=20261124T194525Z&between=1).
The within-intersection layer starts checked. **Inspect a same-ID gap** selects
one example and zooms to its observed endpoints. The layer checkbox hides and
shows the reconstruction while preserving the observed lines.

Validation: 40 focused software tests passed, including identity scope,
classification changes, long/lateral gaps, timestamp conflicts/reset handling,
endpoint interpolation, physical bounds, duplicate/overlapping fragments,
terminal reservation, archive isolation and unchanged rolling expiry. JavaScript
syntax and browser layer toggling were checked. The live collectors were left
running; only the combined dashboard and Florida reconstruction worker restarted.
