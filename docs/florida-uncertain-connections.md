# Gray dashed alternatives between Florida intersections

The user requested uncertain connections even when they may pair the wrong
vehicles. A fourth checkbox, **Uncertain matches · gray dashed**, is enabled by
default in Florida's frozen and rolling figures. It is separate from the existing
speed-colored reconstruction layers. No observations or stored model outputs
are overwritten.

`dashboard/static/uncertain-connections.js` builds these display-only alternatives
from the exact snapshot and aligned reconstruction already loaded by the browser.
The calculation runs once per reconstruction revision. It does not write to the
server, merge IDs, or supply samples to a KPI calculation.

## How a connection is chosen

1. Reserve endpoints used by existing local, inter-intersection, residual-color
   and group estimates. An internal endpoint in an accepted local chain cannot
   also be used as a departure or arrival elsewhere.
2. Consider vehicle fragments from consecutive intersections in the same travel
   direction. Known corridor exits cannot depart downstream; known corridor
   entries cannot arrive from upstream. Unknown movement is allowed as an
   explicitly uncertain hypothesis.
3. Use measured endpoint slopes over up to three seconds. Retain endpoints
   within 60 m of each view's estimated coverage boundary. Stopped endpoints
   and vehicle classification differences are permitted.
4. Rank potential pairs by extrapolated position discrepancy, speed difference,
   elapsed time, and size discrepancy where available. Scale the position
   residual by `max(5 m, 0.35 × gap distance)`, so short gaps cannot absorb a
   large timing error. Keep up to ten physically feasible candidates per
   departure and assign the lowest-cost available pairs one-to-one. This
   layer deliberately does not require a clear margin over alternatives; ties
   are resolved deterministically, not interpreted as identity evidence.
5. Draw a cubic joining the observed endpoints **without reducing their measured
   forward slopes**. Reject a pair if that curve reverses, exceeds the speed
   bound or needs excessive acceleration. Check the analytic speed extrema and
   acceleration endpoints before shortlisting, not only sampled positions.
   Bounds remain: positive time up to 180 seconds,
   forward distance above 2 m and up to the smaller of 600 m or intersection
   spacing plus 260 m, speed up to 35 m/s and acceleration magnitude up to
   6 m/s². Overlapping observations are not joined with a backwards trajectory.

For example, two vehicles with similar endpoint speed can both be plausible
arrivals. The new layer can choose one and show the connection in gray without
claiming that it identified the same vehicle. Hover identifies it as uncertain
and excluded from KPIs. Gray does not encode speed or a calibrated probability.
The existing gray same-ID lines still indicate uncertain timing.

## Checks

Eleven unit tests cover exact observed endpoints, immutable inputs, tied matches,
one-to-one assignments, reserved endpoints, internal local-chain endpoints,
corridor exits versus unknown movements, time/direction/speed bounds, snapshot
alignment, adjacent-site restrictions, stopped vehicles and classification
changes, rejection of an observed flattening failure, preservation of endpoint
slopes and keeping feasible alternatives when lower-cost pairs are infeasible.
These are software checks, not traffic-identity validation.

The initial v1 replay on the frozen November 24 hour produced **9,933 additional uncertain
connections** across all six adjacent links and both directions. The replay
checked unique endpoint assignments, exact joins to recorded positions, forward
time and station progression, immutable source observations and accepted layers,
and `kpi_eligible: false` for every addition. The local audit is saved in
`data/reconstruction/uncertain-visual-v1/recorded-audit.json` (excluded from Git).
These counts are hypotheses between fragments, not recovered unique vehicles.
No cross-sensor identity accuracy or missing-position accuracy is established.

## November 25: correction to the flat gray connections

The user's Cranes Roost–Hattaway screenshot covers approximately 13:38:25–13:39:26
on the frozen November 24 recording. The previous fallback could pair endpoints
only a few metres apart but several seconds apart in time. It then reduced both
endpoint speeds to force a monotone curve. For example, one pair spanned **2.72 m
in 5.85 s**, despite measured endpoint slopes of **13.82 and 17.88 m/s**. Its drawn
endpoint speeds became about **0.85 and 1.10 m/s**. That was a matching defect,
not evidence that these vehicles stopped between the sensors.

Version `uncertain_endpoint_assignment_v2` rejects that pair and considers the
remaining candidates using the checks above. Across this screenshot minute,
v1 added 41 gray connections, including 16 with average speed below 3 m/s.
V2 adds 18 slope-preserving alternatives, none below 3 m/s. This does not prove
that each alternative belongs to the same vehicle. The full hour contains
6,232 gray alternatives after the correction. Solid observations and existing
stored reconstruction layers are unchanged; gray alternatives remain excluded
from KPIs.

### Masked recorded-data comparison

The fixed rules were replayed on the final 20 minutes of the same frozen
development hour, at all seven sites and in both directions. Spatial bands
5, 15, 40 and 80 m wide were hidden around each site, creating two partial views.
Candidate fragments competed for one-to-one assignments. Local track identities
were anonymized in the matcher and used only afterward to score correct pairs;
hidden positions, full-track movement labels and shape summaries were withheld.
Each width is a separate trial, so these totals are **cases, not distinct vehicles**.

| Metric | Previous v1 | Corrected v2 |
| --- | ---: | ---: |
| Eligible matching cases | 18,045 | 18,045 |
| Proposed matches | 17,968 | 15,251 |
| Correct matches | 10,556 | 10,625 |
| Wrong matches | 7,412 | 4,626 |
| Correct share of proposed matches | 58.75% | 69.67% |
| Eligible cases correctly recovered | 58.50% | 58.88% |
| Mean position error on correct pairs with hidden samples | 0.791 m | 0.790 m |

Correct matches increased by 69 while wrong matches fell by 2,786. Position
error is essentially unchanged. Accuracy remains limited: the gray layer is
still a permissive visual hypothesis, not an identity or KPI input. These are
single-sensor spatial-mask tests on a development recording; they do not test
unknown cross-sensor clock offsets, unseen side-road entries or true identities
between intersections. Pairs with no interior recorded sample contribute to
identity scoring only, not position error.

Reproduce the comparison from the project root (recordings remain local):

```sh
git show ea6e9f3:dashboard/static/uncertain-connections.js > /tmp/uncertain-v1.cjs
node --test dashboard/tests/test_uncertain_connections.js
node scripts/validate_uncertain_connections.cjs \
  --snapshot data/frozen/florida/20261124T194525Z/snapshot.json \
  --layers data/reconstruction/frozen/20261124T194525Z/same-id.json \
  --baseline /tmp/uncertain-v1.cjs \
  --out data/reconstruction/uncertain-slope-v2/masked-validation.json
```

The report includes source/module hashes, all site/direction/width results and a
full-hour replay checking endpoint uniqueness, immutable inputs, exact positional
joins, forward motion and preservation of the new endpoint slopes. Browser QA
on 13:38:26–13:39:23 showed 17 gray alternatives plus three existing stronger
connections; the uncertainty checkbox hides and restores the new alternatives.

The dashboard keeps the approved layout, with the new concise checkbox in the
existing control area. Direction, intersection, object and time filters apply
to this layer; hiding it restores the prior display.
