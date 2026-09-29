# Build the dashboard with me

## 1. Follow a piece of data

```text
BlueCity Python SDK → collector/reception → SQLite raw_events → live map
Verified scene + raw_events → processing → seven KPI formulas → windows → anomalies
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
| `config/sites.json` | Ten Toronto and seven Florida names, IDs, corridors and timezones | Inventory without guessed map coordinates |
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

The ten Toronto UDIDs are configured. Enter credentials locally and supply the original conversion script; verify geometry and stream samples, then field-validate the implemented raw-frame annotator. It must assign lane groups, detect directional
crossings, compute stopped-time integrals, identify connected queues, handle
occlusion/identity switches, and map signal phases. These cannot be inferred safely
from an intersection name alone.

Corridor-wide delay must be weighted from physical traversals; percentiles must
be recalculated from raw samples. Do not average intersection P95s or rate values
to manufacture corridor KPIs. Cross-sensor identity matching needs validation.
The dashboard currently shows per-approach observed windows and a separate
corridor CTM scenario, not a validated corridor travel-time estimator.

The current Toronto entry point is `scripts/connect_toronto.command`. It calls the
same SDK launcher with `--toronto`, selecting the ten supplied Finch West sensor
IDs from configuration. Port 8767 avoids replacing an existing Florida session.


## 7. Toronto implementation: new components and examples

Read [the acceptance report](toronto-implementation.md) alongside these files.
Each task links to its GitHub issue there; software tests and field evidence are separate.

| Changed/new component | Purpose and small worked example | Validation |
| --- | --- | --- |
| `sdk_client.py`, `collector.py`, `reception.py` (F1) | HTTP 401 becomes `auth_http_401`; a timestamp without timezone is retained as quarantined, not guessed UTC. Batches flush after 0.25 s or 100 messages. | Mock authentication success/failure and timestamp tests; no real reception verified |
| `calibration.py` (L1) | Compare a projected landmark with its independently surveyed latitude/longitude; reject a residual above the configured 2 m default tolerance. | Known synthetic landmarks and deliberately wrong origin |
| `live.py`, `app.js` (L2/L3) | Two sensors can both have object ID `7`; they remain separate site observations. Hide a frame at age 5.1 s. Poll every second. Record display latency only when an object is rendered in the viewport. | Live unit tests and browser multiple-site/viewport checks |
| `storage.py`, `start_connected.py` (H1) | Replaying an identical event in a new collector session inserts zero new rows. Receipt at the exact 30-day cutoff is retained; an earlier receipt expires. | Restart, deduplication, atomic rollback, retention and migration backup tests |
| `processing.py` (H2/H3) | Twenty complete traversals of 100 m at 10 m/s produce 0 s mean excess time and 240 veh/h. A gap over 3 s splits/censors a track; it is never silently merged. | Geometry/count/conservation, censored gaps, session reset and DST tests |
| Signal processing (H3) | Arrivals at 20,32,...,248 seconds with green ending at 150 yield 11/20 = 55% AOG. Missing synchronization leaves signal KPIs unavailable. | Hand-calculated phase transition test |
| `worker.py` (H1/H3) | An independent background worker closes five-minute windows, purges expired raw data hourly, and computes yesterday from observations. Missing geometry exposes `blocked_metadata`. | Uses tested storage/processor; sustained operation needs field testing |
| `server.py`, HTML/JS/CSS (H4/A2) | Select a history row to inspect its inputs, source event keys and versions; inspect raw pages; export matching windows. Anomaly evidence links back to its window. | Browser history/chart/export checks; anomaly API tests described in report |
| `anomalies.py` (A1/A2) | A median 12, MAD 2 baseline has an upper bound 22.378 at 3.5 scaled MAD. Two consecutive good-quality windows above it form one alert. Nine valid baseline days produce no statistical alert. | Warmup, zero-MAD, persistence, deduplication, acknowledgement and recovery tests |
| `validate_live.py`, `review_anomalies.py` (L3/A3) | Compute observed latency separately from upstream clock difference. Manual review with 3 true positives, 1 false positive and 1 miss gives precision 75%, recall 75%. | Tools do not certify field validity; real session and labelled evidence still missing |

The original seven-formula calculator and Optimization placeholder are unchanged.
The CTM remains an educational simulation and is never anomaly ground truth.
Private credentials, scene metadata, raw observations and generated reports stay
outside Git. Share only reviewed, sanitized field evidence in acceptance issues.

## 8. First real Toronto reception and approximate markers

[The live-test report](toronto-live-test.md) records nine receiving sensors, one
routing 404, the offset-free timestamp issue, one-hour launcher usage, approximate
map provenance, and the distinction between an intersection pin and a calibrated
sensor origin. `start_connected.py` now bounds the test duration and shuts down
child process groups; `config/sites.json` adds reference locations; `app.js`
renders those pins and receipt health; `live.py` explains stored clock-pending
events rather than calling them absent. Vendor SDK files remain unchanged.

## 9. Live object animation (2026-09-28)

The live map now defaults to **Approximate live objects**. Select an intersection
(e.g. Driftwood); zoom 17+ shows its received road users. The rotation selector
starts at 180° and changes only the display. These positions use street reference
coordinates, not surveyed mounting points. Road alignment may therefore be wrong.

`storage.py` keeps one `preview_frames` row per sensor as events arrive, avoiding a
scan through the growing raw archive on every map update. Offset-free timestamps
remain quarantined for analytics. The preview's age uses the computer receipt
clock and does not claim the sensor event is less than five seconds old.
`live.approximate_snapshot()` explicitly labels this distinction; the calibrated
snapshot and KPI pipeline remain separate. Missing receipts expire after five
seconds; invalid/future-clock quarantines do not enter the preview cache.

The browser polls at 250 ms without overlapping requests. Markers are keyed by
sensor + collector session + object ID. If ID 7 moves between coordinates A and B,
its existing marker interpolates A→B for 250 ms instead of being destroyed and
recreated. No movement is extrapolated beyond B. Empty frames remove absent IDs;
stale markers expire even if the next request hangs. Uncheck approximate mode to
return to strict calibration requirements. This is live reception, not historical
replay. Sensor buffering/upstream delay remains unverified.

Validation: 43 Python tests pass. New tests prove that approximate projection does
not populate the strict calibrated view, that stale/empty frames clear, and that
invalid-clock events cannot enter the preview. The real-browser animation check
observed 25 objects at Driftwood, with 24 persistent IDs changing displayed
position in 1.5 seconds, zero JavaScript errors, and successful clearing when
approximate mode was disabled. This validates observed motion in the UI; it does
not validate alignment with lanes, absolute sensor time or KPI accuracy.

New `scripts/check_live_animation.cjs` requires a currently receiving stream.
Its screenshot stays in ignored `data/qa/`; no field payloads are committed.

## 10. Object legend

The map legend identifies vehicles (blue), pedestrians (teal), cyclists (purple), and unknown/unclassified objects (gray). `objectStyles` in app.js supplies both legend colours and marker colours, so they stay consistent. For example, an unknown class now renders gray rather than sharing the pedestrian colour. The legend wraps on small screens; tooltips still identify individual objects.

## 11. Object shapes

Map objects now use matching vector pictograms: car for vehicles, walking person for pedestrians, bicycle/rider for cyclists, and a question-mark diamond for unknown classes. The legend and Leaflet markers share `objectSymbol()` so both shape and colour agree. Existing marker interpolation, identity and expiry remain unchanged. Icons are fixed-size class symbols; their orientation and size do not claim measured heading or dimensions. No external images or icon service is required.

### Smaller, more detailed silhouettes

Object markers are now 16 px (previously 24 px), with no white tile behind them. Vehicles use a top-down car with wheels, windows and lights; pedestrians use a filled walking silhouette; cyclists show a rider and bicycle wheels/frame. Legend icons are 18 px for readability. These remain class symbols, not measured vehicle outlines or headings.

The map marker size was subsequently adjusted to 20 px at user request, with a centered 10 px anchor. The 18 px legend icons and detailed silhouettes remain the same.

## 12. User-requested map alignment

The approximate object preview now defaults to 210°, adding 30° anticlockwise to the previous 180° projection. Each position rotates about its own intersection reference point before conversion to latitude/longitude. For example, a previously westward 10 m offset becomes 8.66 m west and 5 m south. This moves object coordinates rather than rotating the icon artwork. Stored observations and verified calibration metadata are unchanged.

## 13. Continuous live viewing versus a one-hour archive

The two durations are now independent:

- `--record-duration 3600`: archive raw events for one hour, then keep live streaming.
- `--record-duration 0`: live viewing only; preserve previously recorded history.
- Omit `--record-duration`: unlimited raw recording (existing CLI compatibility).
- `--duration`: optional overall process shutdown; omit it for continuous live viewing.

The Toronto double-click launcher now defaults to one hour of raw recording and
continuous live viewing afterward. The restarted current session uses live-only
mode because the test archive is already saved. Credentials stay in memory.
Closing the map does not stop the collector; stopping Terminal, sleeping/shutting
down the computer, or losing network access can interrupt this local service.

`persist_observations()` splits batches at the recording deadline. After that
boundary `save_preview()` replaces the latest per-sensor display frame without
adding rows to raw history. Verified-clock frames also update the strict latest
cache. Historical queries only read the raw archive, never the live preview cache.
Boundary and live-only tests verify that history stops growing while live frames
advance. The suite now has 45 passing tests.

Historical performance also shows the last saved hour's received-message counts
per minute and timestamp-quality counts, using the receipt clock. The chart's
end is the last archived receipt, not the current live time. These are SDK-message
counts, not vehicles, flow or calibrated performance metrics. A covering index
avoids scanning full frame payloads to compute this summary. Gaps appear as zero
received messages; they do not imply zero traffic. Full traffic KPI analysis still
needs clock confirmation and verified scene annotations.

## 14. Muted basemap

A CSS filter on the Leaflet tile pane reduces basemap colour, contrast and brightness. Object icons, sensor markers, tooltips, controls and attribution remain outside that filter. This makes live objects stand out without changing coordinates or observations.

## 16. Recovering stalled live streams

On 2026-09-29 the local servers were still listening, but the last receipts from
nine sensors were about ten hours old. Collector processes remained open without
new events; the existing launcher only watched the web server. The evidence does
not establish whether sleep, connectivity or an upstream fault caused the stall.

The launcher now supervises every sensor collector. After a 60-second startup
grace period it restarts an exited collector or one with no receipts for over
30 seconds. Authentication/routing failures retain their specific errors and the
SDK retry behavior. Restarts stop the old process group before starting a new one.
The same credentials remain in process memory; none are written to the repository.

An absolute `--record-until` deadline passes to restarted collectors, so recovery
cannot reset a one-hour recording window and accidentally extend the archive.
The active session uses live-only mode and leaves the saved hour intact. The
watchdog works while the launcher/computer is running; it cannot keep a sleeping
or powered-off computer online. Objects still expire after five seconds so stale
positions cannot appear live during reconnection.

46 Python tests pass, including startup grace, healthy receipt, stalled receipt,
collector exit and explicit routing-failure cases. Field restart restored the
stream; long-duration unattended recovery remains to be monitored.

## 17. Click an intersection to inspect the paper's KPIs

`site_kpis.py` maps the seven Tier-1 definitions to saved results and explains
missing inputs. `server.py` exposes the read-only `/api/site-kpis` query. The new
panel in `index.html` and its `app.js` handlers keep the selected sensor, approach
and reporting window together; a request counter prevents a slow previous-site
response from replacing the current selection. No synthetic values are used for
real intersection cards. The panel's historical link selects the same sensor.
See [the document review and worked example](intersection-kpi-review.md) for
requirements, current data limitations and validation evidence.
