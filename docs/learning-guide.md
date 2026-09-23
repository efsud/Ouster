# Build the dashboard with me

## 1. Follow a piece of data

```text
BlueCity Python SDK → collector.py → local SQLite frames/events → server.py → live map
Annotated KPI windows → analytics.py → SQLite windows → filters/charts/CSV
CTM controls → analytics.simulate → density heatmap (separate from observations)
```

The Python backend owns calculation and storage. Browser JavaScript owns
interaction and display. SQLite is a file-based database, so measurements survive
server restarts without installing a database server. Git stores the code and
documentation; `data/` is deliberately ignored.

## 2. File tour

| File | What you would write here | Why it exists |
| --- | --- | --- |
| `config/sites.json` | Known Florida names, IDs, corridor and timezone | Inventory without guessed map coordinates |
| `config/sites.local.json` (you supply) | Verified Toronto metadata and calibration | Keeps local scene details separate from shared code |
| `dashboard/analytics.py` | KPI functions, coordinate rotation, CTM equations | One testable place for scientific calculations |
| `dashboard/storage.py` | Tables and parameterized SQL | Persistent records with source and quality metadata |
| `dashboard/bluecity.py` | Token acquisition and allowlisted historical reads | Clearly limits external API capabilities |
| `dashboard/collector.py` | SDK subscription and event recording | Saves original frames and phase events |
| `dashboard/live.py` | Freshness checks and calibrated map projection | Rejects stale streams and invalid objects per site |
| `dashboard/server.py` | Local HTTP routes and input checks | Connects the browser to calculations and data |
| `dashboard/demo.py` | Fixed synthetic annotated windows | Learn the features without confusing demo and field data |
| `dashboard/static/index.html` | Page structure and labelled controls | Defines the five dashboard sections |
| `dashboard/static/style.css` | Layout, colors, type and responsive rules | Makes information readable at desktop/mobile widths |
| `dashboard/static/app.js` | Filter interactions, maps, SVG charts, API requests | Turns inputs and results into an interactive dashboard |
| `dashboard/static/vendor/` | Unmodified Leaflet assets and license | Local, version-pinned map rendering |
| `scripts/start_connected.py` | Hidden password prompt and process launch | Enter credentials locally without saving them |
| `scripts/connect_florida.command` | macOS Terminal launcher for all seven Florida UDIDs | Opens the credential prompt directly, using port 8766 |
| `scripts/vendor_map.py` | Copy npm's pinned Leaflet files | Reproducible dependency refresh |
| `scripts/browser_check.cjs` | Exercise the UI in a real headless browser | Verify controls, exports, CTM behavior, and mobile layout |
| `dashboard/tests/` | Known numerical cases, failure cases, conservation | Catch scientific/data errors before using field data |
| `docs/kpi-specification.tex` | Your original source | Preserves provenance of the seven KPI definitions |
| `package.json`, `package-lock.json` | Map-library version and helper commands | Reproducible JavaScript dependency installation |
| `.gitignore` | Private data, environments and generated outputs | Prevents accidental commits of credentials/data |

## 3. Work one formula by hand

A vehicle enters a 100 m approach at time 0 and arrives at the stop line at 30 s.
Free-flow speed is 10 m/s. Free-flow time = 100/10 = 10 s. Its excess travel time
is 30 − 10 = **20 s**. The control-delay KPI is the mean across valid traversals.

Twenty vehicles enter in 300 s: volume = 20 × 3600 / 300 = **240 veh/h**.
If 20 queued vehicles discharge during 150 s effective green over two lanes,
discharge = 20 × 3600 / (150 × 2) = **240 veh/h/lane**.

These are test fixtures, not observations. A vehicle with a gap greater than
3 seconds is excluded; a track missing entry cannot contribute control delay.

## 4. Understand CTM

For each cell, calculate how much traffic it can send and how much the next
cell can receive. Their minimum is the boundary flow. Then update vehicle count
by adding inflow and subtracting outflow. A red signal makes that boundary's
flow zero. Cells fill upstream, producing a queue in the heatmap.

The conservation test checks that admitted vehicles = departed vehicles +
vehicles remaining. A separate source backlog accounts for demand unable to enter.
The heatmap is aggregate density; fractional vehicle values are normal in this model.

## 5. Exercises in the UI

1. Load the synthetic history. Click each KPI and inspect the quality table.
2. Restrict the date range, export CSV, and compare a plotted point with its row.
3. Run CTM with green = 0. Exits must be zero and upstream demand must accumulate.
4. Run green = 90. Compare queues and throughput with the red case.
5. Switch between one and seven intersections. Observe travel time and offsets.
6. Read `test_analytics.py`, change one fixture locally, predict the result, then run tests.

## 6. What remains before real Toronto KPIs

Enter API credentials locally, provide a Toronto UDID and the original conversion
script, verify geometry and stream samples, then implement and validate the
scene-specific raw-frame annotator. It must assign lane groups, detect directional
crossings, compute stopped-time integrals, identify connected queues, handle
occlusion/identity switches, and map signal phases. These cannot be inferred safely
from an intersection name alone.

Corridor-wide delay must be weighted from physical traversals; percentiles must
be recalculated from raw samples. Do not average intersection P95s or rate values
to manufacture corridor KPIs. Cross-sensor identity matching needs validation.
The dashboard currently shows per-approach observed windows and a separate
corridor CTM scenario, not a validated corridor travel-time estimator.
