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
   elapsed time, and size discrepancy where available. Keep up to ten candidates
   per departure and assign the lowest-cost available pairs one-to-one. This
   layer deliberately does not require a clear margin over alternatives; ties
   are resolved deterministically, not interpreted as identity evidence.
5. Draw a monotone cubic between the observed endpoints, reducing endpoint
   slopes where necessary. Bounds remain: positive time up to 180 seconds,
   forward distance above 2 m and up to the smaller of 600 m or intersection
   spacing plus 260 m, speed up to 35 m/s and acceleration magnitude up to
   6 m/s². Overlapping observations are not joined with a backwards trajectory.

For example, two vehicles with similar endpoint speed can both be plausible
arrivals. The new layer can choose one and show the connection in gray without
claiming that it identified the same vehicle. Hover identifies it as uncertain
and excluded from KPIs. Gray does not encode speed or a calibrated probability.
The existing gray same-ID lines still indicate uncertain timing.

## Checks

Eight unit tests cover exact observed endpoints, immutable inputs, tied matches,
one-to-one assignments, reserved endpoints, internal local-chain endpoints,
corridor exits versus unknown movements, time/direction/speed bounds, snapshot
alignment, adjacent-site restrictions, stopped vehicles and classification
changes. These are software checks, not traffic-identity validation.

Replay on the frozen November 24 hour produced **9,933 additional uncertain
connections** across all six adjacent links and both directions. The replay
checked unique endpoint assignments, exact joins to recorded positions, forward
time and station progression, immutable source observations and accepted layers,
and `kpi_eligible: false` for every addition. The local audit is saved in
`data/reconstruction/uncertain-visual-v1/recorded-audit.json` (excluded from Git).
These counts are hypotheses between fragments, not recovered unique vehicles.
No cross-sensor identity accuracy or missing-position accuracy is established.

The dashboard keeps the approved layout, with the new concise checkbox in the
existing control area. Direction, intersection, object and time filters apply
to this layer; hiding it restores the prior display.
