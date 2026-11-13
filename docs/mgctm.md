# Movement-group CTM for SR-436

This passenger-car simulator runs independently of the DeepCTM viewer and the
live recorder. It does not fit a neural model or optimize signal timing.

## Reproduce

From the Ouster checkout, use Python 3.11+:

```sh
python3 -m venv .venv-mgctm
.venv-mgctm/bin/pip install -r mgctm/requirements.txt
.venv-mgctm/bin/python -m unittest mgctm.test_physics -v
.venv-mgctm/bin/python -m mgctm simulate config/mgctm/synthetic-2-am.json data/mgctm/two-am
.venv-mgctm/bin/python -m mgctm simulate config/mgctm/synthetic-8-am.json data/mgctm/eight-am
.venv-mgctm/bin/python -m mgctm simulate config/mgctm/synthetic-8-pm.json data/mgctm/eight-pm
```

Open `cell-map.html` in the output directory for an interactive directed cell
map. It uses local metric XY coordinates; shared road centerlines may be
slightly offset on screen to make the groups distinguishable. Outputs include
`cells.csv`, `cell-geometry.json`, `predictions.csv`, `summary.json`,
`density.png`, and `queues.png`. The demo is a single-direction arterial with
terminal side movements, fabricated timing and demand. It is not Florida.
A field network can include both directions and cross streets; the density
chart uses configuration order, so arrange the plotted through-cell sequence
appropriately before interpreting it as a physical time–space section.

## Physical model

[LightSim paper](https://arxiv.org/abs/2602.21852), §§3.1 and 3.4, and its
[OSM importer](https://github.com/AnthonySu/LightSim/blob/master/lightsim/networks/osm.py)
inform the cell count, first-order CTM, linear start-up ramp, and Poisson
arrivals. The independent implementation does not reuse the importer’s inferred
signal phases, turns, reverse links, lane defaults, or free-speed reduction on
short links.

Specify physical homogeneous lane sections before discretizing. At the start
of a finite bay, end the upstream shared section and start the bay and any
parallel continuations. Lane IDs are physical and local to a directed link;
two groups cannot overlap on the same lane. Supply a metric polyline for
each section. The compiler uses
`max(1, floor(L / max(min_cell_m, vf*dt)))`, covers the full interval,
reduces the common step when a physical short segment requires it, and
coarsens cells if necessary for a faster backward wave. Every input boundary
must align with that step; the compiler refuses to round signal events.

Density is cars/m/lane, speeds m/s, state cars, and flow cars/s; external profiles
use cars/hour. For each cell, `k = n/(length*lanes)`,
`Q = vf*w*kj/(vf+w)` per lane, sending is `min(vf*k,Q)*lanes`, receiving is
`min(Q,w*(kj-k))*lanes`. Flow transfers multiply rates by dt. This constrains
capacity to the triangular fundamental diagram; a measured saturation flow
can instead limit the stop-line movement via an independent discharge cap.
Physical bounds and the combined cell/reservoir conservation equation are
checked every step. Unmet arrival demand stays in an external reservoir.
Unmet mid-block *withdrawals* are not queued; they represent a requested
exogenous exit subject to available sending.

Turning intent is represented as three fractional masses per cell. An origin
sets intent for its first intersection, and crossing a stop line sets intent
for the **next** intersection. The physical split only routes existing intent;
it never applies another turning ratio. Every allowed cell/intent has one
path, so no lateral lane switching can occur after commitment. A shared
through/right lane has one storage and sending budget. FIFO within a group
uses the most restrictive proportional movement limit. Finite receiving
space causes upstream spillback; independent downstream groups keep their
own capacity. Proportional allocation across competing incoming requests
is conservative and may leave spare supply after FIFO is applied. It does
not model vehicle ordering, conflict-gap acceptance, or optimal node throughput.

Supply a time series of movement permissions per stop line: protected,
permissive, right-on-red, red, yellow, or all-red. Yellow and all-red are
closed in this implementation. Protected discharge follows the LightSim
linear ramp; permissive left and right-on-red require explicit observed
capacity, and right-on-red also requires a verified permission flag. The
model does not infer conflicts or safe gaps. Controller logs can be represented
as noncycling change points after phase-to-movement decoding, including actuated
changes; synthetic scenarios use cycles with offsets. Pedestrian effects may
be supplied as a time-varying movement capacity cap. Exits use unlimited
receiving space and still obey sending, signals, and explicit discharge caps.

The queue estimate is contiguous above-critical-density cell length counted
backward from a section’s downstream end. Section spillback is when this
length covers the section. Speed is a fundamental-diagram proxy; simulated
vehicle-time, origin wait, throughput and section counts are aggregate.
Travel times, stopped delays and independently timed discharge headways
are not computed. State bytes describe only count/reservoir arrays, not
process peak memory. All runs start empty; use an independently justified
warm-up or initial-state extension before interpreting the first field bins.

## Florida geometry and recordings

The field study config has seven known reference sites from Cranes Roost to
Boston. The confirmed SDK origin for Plaza Entrance is at Altamonte Mall
Entrance, separate from Renaissance Dr. SDK yaw and movement gates are unverified. This is a field inventory, not a network
ready to simulate. The `sr436-am-template.json` and
`sr436-pm-template.json` files intentionally refuse simulation until populated
with verified geometry and inputs.

```sh
.venv-mgctm/bin/python -m mgctm geometry config/mgctm/sr436-study.json data/mgctm/osm
.venv-mgctm/bin/python -m mgctm audit-recordings data/sr436
```

The OSMnx download retains directed edges, tags, signal nodes, and service
roads in the bounding box and produces GraphML, GeoJSON, and an editable
`geometry-review.csv`. Review road-specific tags, stop lines, driveway
boundaries, and turn-restriction relations. Counts of graph nodes and edges
cover the entire bounding box, not the selected intersections alone.
On the initial run, OSM returned 1,965 directed edges and 21 tagged signal
nodes; 1,771 edges lacked `lanes` and 1,936 lacked `turn:lanes`. The
separate restriction request returned an HTTP error. No absence of restriction
was inferred. A manual conversion of verified sections and movements into
network JSON is required; OSM tags are not automatically treated as bay geometry.

For trajectory counts, use the verified gate template, keyed by target
movement and UDID. Each gate needs local SDK `p`, `q` endpoints in metres,
a `site`, `target`, and calibration `source`. Direction is the right-to-left
crossing of the directed segment p→q. Set `sensor_clock_verified` only after
checking absolute alignment. Conversion requires the completed fixed AM/PM
capture, explicit UTC offsets on sensor timestamps, close receipt alignment,
valid adjacent same-session tracks, and nearly complete per-bin frame
coverage. It counts only class 2 (Car), excludes SDK legacy ambiguous
vehicle classes, and neither extrapolates partial bins nor bridges gaps.
A single verified sensor measures a given target; overlapping sensors are
not added together. Receipt coverage does not prove detector completeness.

```sh
.venv-mgctm/bin/python -m mgctm car-counts data/sr436/CAPTURE data/mgctm/gates.json data/mgctm/car-counts.csv
.venv-mgctm/bin/python -m mgctm profiles data/mgctm/network.json data/mgctm/profiles.csv data/mgctm/am-aligned.json
```

The input template accepts piecewise constant `demand_vph`,
`midblock_exit_vph`, `capacity_vph`, `origin_turns`, `next_turns` and `signal_state` rows
for known model targets. Ratios are JSON objects such as
`{"L":0.2,"T":0.7,"R":0.1}` in a CSV-quoted field. Every profile begins
at 0 and carries provenance. Include signal intervals at recorded transitions,
not five-minute averages. Mid-block entries can be tagged `midblock: true`;
pair collocated entry and exit sections by `midblock_key` for the net-flow
comparison. Independent queue observations must come from a verified queue
measurement, not from counting raw frame objects. Separate boundary inputs
from independent validation targets.

## Experiments and validation

Create a plan with `cases` listing date, AM/PM, train/validation/test, network
JSON, observation CSV and optional seed. Dates must be strictly chronological
and disjoint by partition. Include `scales` for dimensionless metric losses
and `bounds` for bounded SciPy calibration. Supported parameters include
free-speed, wave-speed, jam-density and alternate-discharge scale factors,
plus startup lost time. An optional `screen_parameters` computes a low-cost
one-at-a-time endpoint screen on training days. Use `screen` to choose among
E1–E9 and `interactions` only for two screened candidates. E3 (infinite bays)
is a counterfactual permitted only on synthetic inputs; finite storage is a
mandatory field constraint. E8 needs alternate signal plans supplied explicitly.
E0 means the complete declared deterministic baseline, not an assumed set of
measured parameters.

Train shared starting parameters, screen changes on identical held-out date
and peak pairs, then refit retained models per peak using the same optimization
budget. The one-standard-error rule favors the simplest eligible configuration.
Test dates are scored only after selection. Use at least two validation dates
for selection and five independent paired dates for bootstrap intervals.
An interval based on few days remains weak evidence. Observation metrics are
count, queue_m, vehicles, speed_kmh, and binary spillback. Use stop-line
movement count as a discharge proxy, not individual headway.

Reproduce the synthetic recovery run:

```sh
PYTHONPATH=. .venv-mgctm/bin/python scripts/make_mgctm_recovery.py data/mgctm/recovery-input
.venv-mgctm/bin/python -m mgctm experiment data/mgctm/recovery-input/plan.json data/mgctm/recovery-output
```

The 2- and 8-signal synthetic runs verified numerical operation and storage.
The two-hour AM/PM eight-signal runs had max absolute vehicle residuals
1.33e-10 and 4.07e-10 cars, respectively. The recovery run identified a wave
speed multiplier about 1.132 for a synthetic target of 1.12 and selected E0
on both peaks. These are software and synthetic recovery checks. No field
model is calibrated or selected. The first Florida archive contained zero
frames; the planned peak windows are still separate from these results.
Even if both peaks record successfully, one day is insufficient for the
required disjoint calibration, validation and test dates.
