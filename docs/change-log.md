# Centre placement update — 2026-10-06

## Revised clockwise and anticlockwise alignments

This revision supersedes the coordinate table below. Requested clockwise angles
are subtracted from the original 180-degree conversion, not from the previous
site-specific angle. Explicit 210-degree requests are total rotations. The marker
and all local object coordinates share the supplied origin. Movement headings
follow displayed trajectories. Tooltips now spell out clockwise versus
anticlockwise instead of displaying a misleading negative adjustment.

| Intersection | Latitude | Longitude | User adjustment | Total rotation |
|---|---:|---:|---|---:|
| Martin Grove | 43.736772 | -79.591825 | 40° clockwise | 140° |
| Albion | 43.741152 | -79.589252 | 35° clockwise | 145° |
| Kipling | 43.743273 | -79.582284 | 40° anticlockwise | 220° |
| Islington | 43.746175 | -79.568791 | Explicit previous alignment | 210° |
| Weston | 43.752070 | -79.542374 | Explicit previous alignment | 210° |
| Arrow / Signet | 43.753306 | -79.536397 | 45° clockwise | 135° |
| York Gate | 43.756759 | -79.520823 | 45° clockwise | 135° |
| Driftwood | 43.758042 | -79.513510 | 40° clockwise | 140° |

Finch's expected heavier traffic is context for visual review, not a reason to
alter observed counts or fabricate flow assignments. These are user-directed
preview alignments; field validation still requires scene evidence. Jane and
Norfinch remain unchanged. Eight preview/live tests pass, and browser/API checks
verify all eight exact coordinates, total angles and directional labels.

## Per intersection user alignment

The default preview now uses each site's own coordinates and angle. Angles are
counterclockwise beyond the original 180-degree conversion (35 means 215 total).
The same origin places the LiDAR marker and converts its local object positions.
Arrow Road uses the existing Signet UDID C251071. These user-specified positions
remain approximate until field calibration; raw data and historical CTM inputs
are unchanged. Jane and Norfinch retain their references and +40-degree defaults.

| Intersection | Latitude | Longitude | Adjustment |
|---|---:|---:|---:|
| Martin Grove | 43.736838 | -79.591507 | 35° |
| Albion | 43.741271 | -79.589169 | 45° |
| Kipling | 43.743321 | -79.581885 | 45° |
| Islington | 43.746264 | -79.568383 | 45° |
| Weston | 43.752070 | -79.542374 | 30° |
| Arrow / Signet | 43.753406 | -79.535887 | 40° |
| York Gate | 43.756934 | -79.520632 | 45° |
| Driftwood | 43.758108 | -79.513230 | 45° |

Validation: eight live/preview tests pass, including site-specific rotation,
zero-coordinate placement at the origin, and explicit global preview overrides.
The browser verifies all eight coordinates and rotations against the running API.

Increased the default network object preview rotation from 215 to 220 degrees:
40 degrees counterclockwise beyond the original 180-degree conversion. All sites
use the shared preview selection. Intersection centres remain fixed, and object
heading follows the rotated motion. The previous 215-degree option is retained.

All live object classes now rotate toward their observed travel direction. Bearing
is derived from displayed geographic displacement, so the existing map rotation
is already included. A 0.25 m displacement threshold reduces stationary jitter;
small movements accumulate against the last heading anchor. Stopped objects keep
their previous direction, and newly seen tracks wait for movement evidence. A small
direction tip makes orientation clear even for unclassified symbols. Icon rotation
uses a nested element so Leaflet positioning is unaffected and wraps by the shortest
angle. Browser checks cover four cardinal directions, all four classes, stationary
retention and sub-threshold motion. This is travel direction, not measured body yaw.

Returned LiDAR markers and live objects to the existing approximate intersection
centre references. Removed the 18 m south/east display translation for both layers;
the existing object rotation and raw recordings are unchanged. Browser validation
checks all ten markers against their references and confirms zero object offset.

# Live object map update — 2026-10-05

Moved the Toronto LiDAR display markers to approximate southeast corners, 18 m
south and 18 m east of each existing reference. The identical translation is
applied to live objects before viewport filtering and animation. Per-site reference
latitude keeps the offset consistent for every object. Raw observations and the
215-degree rotation remain intact. This is a user-requested visual alignment,
not a surveyed mounting coordinate or a historical KPI recalibration.

The network launcher now accepts repeatable `--exclude-site` arguments so an
already active Driftwood recorder can keep running while the other nine Toronto
sites connect. The map already requests all regional streams and displays fresh
objects from any site within the viewport at zoom 17 or above. Reconnection needs
private credentials; availability is checked per site rather than assumed.

Removed the signal overlay script at the user's request. Signal markers, manual
phase selectors and direction guides no longer appear or poll the signal API.
The live object renderer and saved signal recordings remain unchanged.
Browser validation confirmed map tiles load, signal controls and direction guides
are absent, and no JavaScript errors occur. The stream was stale at validation;
a private recorder prompt was opened to restore fresh Driftwood object reception.

# Toronto pipeline update — 2026-09-24

Added reception diagnostics, clock quarantine, batched/deduplicated storage, migration backup and 30-day raw retention; versioned calibration gates; geometric trajectory processing and calendar-day summaries; paginated received/history inspection; provisional anomaly rules, evidence and local review; live latency/manual review tools. Updated launcher, live status, UI, tests and learning documentation. Optimization and CTM unchanged. See [acceptance evidence](toronto-implementation.md).

# Development record

## 2026-09-23 — Initial dashboard and scientific foundation

Starting repository: API manual, archived vendor SDK, and sample code only.
Existing vendor materials were preserved. Work is isolated on
`codex/corridor-dashboard` for review in GitHub.

Created the local Python dashboard, a responsive browser interface, and five
sections: live network, history, CTM, reserved optimization, and learning notes.
Added the seven user-provided Florida site IDs without guessed coordinates.

Added seven Tier-1 KPI formulas with per-window quality metadata, a configurable
coordinate converter, and a one-lane CTM with conserved source backlog. Added
SQLite persistence, JSON import, CSV export, synthetic learning data, a read-only
SDK recorder, allowlisted cloud collection, and a private credential launcher.

Added source LaTeX, API review, import contract, file-by-file learning guide,
tests, dependency lockfile, vendored Leaflet/license, and private-data exclusions.

Scientific interpretation: lane-normalized discharge; entry-event volume can
include censored traversals; no fabricated values for missing signal/queue data;
negative delay flagged; low-quality windows labelled provisional; CTM never
presented as a field measurement. These decisions are explained in `api-review.md`.

Validation: 13 Python tests passed for formula fixtures, missing data, censored
tracks, gaps, zero flow, rotation, persistent storage, and CTM conservation.
The browser smoke test passed inventory selection, empty-stream status,
synthetic history, KPI selection, CSV download, red/green CTM behavior, the
optimization placeholder, mobile fit, and absence of JavaScript exceptions.
Desktop and mobile screenshots were reviewed locally. The vendor SDK installed
and imported successfully under Python 3.11; no authenticated site connection has
been claimed or tested without user-entered credentials.

Pending: user-entered API credentials, Toronto UDID and scene metadata, original
coordinate script, field validation, raw-frame-to-KPI annotation, corridor
geometry/identity matching, retention policy, and authenticated multi-user deployment
if desired. Optimization remains intentionally deferred.

## 2026-09-23 — Network-wide live view

Extended live mapping from a single selected site to every calibrated stream in
the selected network. Objects are displayed within the viewport at zoom 17+;
site-specific freshness and calibration states remain visible. The backend takes
one shared timestamp for a network snapshot. Malformed objects are counted and
excluded without discarding valid objects in the frame.

Added verified corridor path rendering from local metadata, using explicit
[longitude,latitude] coordinates rather than assuming the site inventory order
is a roadway path. The private launcher can record multiple comma-separated
UDIDs and checks its port before asking for credentials.

Five additional tests cover empty versus missing frames, stale/future timestamps,
required calibration, malformed objects, sensor isolation, and protobuf defaults.
Live access and field geometry remain pending; these tests use synthetic fixtures.
Browser tests also pass with two simultaneous synthetic site snapshots and verify
that objects outside the viewport are not displayed. `docs/goal-status.md` records
the requirement-by-requirement completion audit and required field inputs.


## 2026-09-23 — Florida selected as the current working network

At the user's request, changed the initial map center and default network to
Florida / SR-436, Altamonte Springs. The seven supplied UDIDs remain exactly as
provided in config/sites.json. Updated the dashboard banner, initial label,
credential prompt, and README to match the current Florida focus. Toronto remains
an optional network. No sensor coordinates or live data were invented.

## 2026-09-23 — Open the Python credential prompt

Rechecked the vendor main.py and SDK authentication guidance: BCTWSConnection
requires UDID, username and password and obtains its JWT internally. Added a
macOS Terminal launcher so the user is actually presented with the username and
hidden-password prompts. The --florida flag selects the seven existing UDIDs
automatically. The connected server uses 8766 while the preview remains on 8765.
Credentials remain in memory and are never added to project files or GitHub.


## 2026-09-23 — Toronto Finch West sensor inventory supplied

Added the ten exact Toronto UDIDs and intersection names provided by the user.
Changed the initial map to the Finch West corridor overview and Toronto network.
Added a --toronto SDK launcher option and connect_toronto.command for a private
credential prompt on port 8767. Florida remains available. The overview center
is a navigation aid, not a sensor georeference; no exact sensor origins or
rotations are assumed.

## 2026-09-29 — Additional 5° counterclockwise map alignment

Changed the approximate object display rotation from 210° to 215°. Each site's intersection reference location remains the pivot: a point at local (0,0) stays fixed, while all other points rotate another 5° counterclockwise at the same distance from it. The previous 210° alignment remains selectable. This display adjustment does not change raw recordings or the sensor-local CTM count line.

## 2026-10-01 — Fix recurring dashboard connection failures

The dashboard could remain listening while returning empty responses or resetting sockets. Inspection found SQLite/database-WAL handles occupying descriptors through 255. `with sqlite3.connect(...)` commits or rolls back a transaction but does not close the connection; repeated polling relied on eventual garbage collection and exhausted the process handle limit.

`Store.connect()` now uses a connection subclass that commits/rolls back and always closes on context exit, including failure paths. Migration backup connections use the same lifecycle. This preserves existing transaction semantics while releasing handles deterministically. The repaired dashboard remains at port 8766; the live recorder was not interrupted.

Validation: all 63 Python tests pass, including 1,000 connection contexts with garbage collection disabled, commit persistence, rollback and closure on exceptions. A four-client load check completed 120 live-network requests successfully. Afterward the server's open descriptors were back to its terminal, log, listener and runtime socket; no accumulated SQLite handles remained. Live browser motion was checked separately.

## 2026-11-04 — DeepCTM research adaptation and 24-hour capture

Reviewed the supplied 12-page paper, including equations/architecture; documented missing specifications and inconsistent 60-minute RMSE tables. Added an optional PyTorch implementation, conservative CTM integration, directional messages/gating/PEC, masked features and chronological evaluation against persistence/pure CTM. Added compressed Weston/Signet recording with a fixed 24-hour deadline, restart supervision and disk guard. Added a separate read-only experiment viewer and historical-page link. All results remain provisional pending calibration and sufficient recorded data. No change to signal controls or existing map alignment.

## 2026-11-06 — Measured trajectory figures

Generated full-hour and five-minute time–distance plots for both directions from the saved Weston/Signet hour. Added sensor-colored and speed-colored panels, a local gallery and indexed image endpoints. Gaps split tracks; the unobserved corridor is shaded rather than filled with invented vehicle paths. Four new extraction tests and 65 existing dashboard tests pass; browser selection/rendering verified. Field-model training remains separate and has not been represented by these figures.

## 2026-11-06 — Full Finch corridor capture and speed figures

Added a one-hour launcher for all ten Finch sensors with per-site failure isolation and automatic figure generation after collection. Generalized stationing, local road bearing, sensor names, multi-site plot layout and dashboard status; absent sensors remain blank and labelled. Recording-only mode avoids running the two-site neural training pipeline on corridor data. Existing captures remain unchanged.

## Interactive recorded corridor figures — November 6, 2026

The recorded-trajectory viewer now lets users check individual intersections, select a direction/time window, and inspect speed by hovering over measured track points. Weston and Signet are selected initially; Select all and Clear selection are available. The plot rescales to the selected sites while preserving approximate corridor station distances. Jane stays explicitly empty. The original PNG gallery remains available below the interactive chart.

The plotting pipeline writes compact per-site JSON containing the same accepted measured fragments, downsampled to approximately 2 Hz for display. Raw recordings remain intact. The viewer loads selected sites only and caches them for subsequent selections. These are measured local fragments with provisional geometry, not model predictions or inferred links between sensors.

Worked example: select Kipling and Islington, then choose westbound 11:45–11:50. The two panels show those two sites only, colored by site and speed respectively. Gray areas have no measured trajectories. Hover shows Toronto receipt time and speed in m/s and km/h.

Validation: nine existing trajectory/corridor tests pass. Browser checks cover pair selection, direction/time changes, clearing selection, Jane's missing data, all ten sites, and JavaScript errors.

### Speed-only interactive view

Removed the site-colored measured-track panel at the user's request. The interactive view now shows a single, larger speed panel with intersection selection and hover readouts. Original two-panel PNGs remain available as download links rather than embedded charts. No recorded data was removed. Existing browser selection, direction/window, and missing-data checks pass.

### Full-hour default and interactive time zoom

The speed chart now opens at the exact recorded one-hour interval. Zoom in/out buttons change the visible duration; scrolling over the chart zooms around the pointer. A time-position slider moves the zoomed window within recording boundaries. Full hour or double-click resets the interval. The minimum window is ten seconds. Intersection changes preserve the visible time interval; choosing a figure preset sets its time window. Raw data and original PNGs are unchanged.

Worked example: open the chart, click Zoom in twice to see fifteen minutes, then use the slider to inspect a later period. Click Full hour to return to the complete recording. Browser validation covers the 3600-second initial window, button zoom, slider navigation, preserving time on intersection changes, wheel zoom, double-click reset, and existing site/direction selections.

## Provisional virtual-cell paths and object filters

Added SDK-named object-type filtering to the interactive speed figure. Re-exported measured fragments with class codes, including non-vehicle classes; retained pooled vehicle defaults. Added a one-minute-resolution adaptation of the existing DeepCTM architecture for adjacent links, with chronological splits and endpoint comparisons against persistence and pure CTM. Seven adjacent pairs trained in both directions; links involving unavailable Jane have no predictions. Dashed model tracers appear only in final held-out windows and only for pooled vehicles. The method and limitations are documented in docs/deepctm.md.

Worked example: select Weston and Signet, pooled Vehicles, eastbound, and enable the virtual-path layer; inspect 12:38–12:43 Toronto. Blue dashed lines are representative paths through predicted cell speeds, not identities matched across sensors. Select Car to inspect observed cars; the pooled-model layer is then hidden.

Validation: model/trajectory/corridor test suite passes, including split boundaries, mask behavior, class preservation and tracer termination at missing forecasts. Browser checks cover the model layer, held-out-only display, class filtering and pooled-model restriction. Intermediate paths have no ground truth and are not field validated.

### Make estimated paths easy to find

Added a View estimated paths button that enables pooled-vehicle estimates and focuses the time range on available predicted paths. It preserves selected adjacent links where possible; otherwise it selects Weston–Signet (or the first available trained pair in that direction). Increased blue dashed-line contrast and corrected the observation-only caption. Loading failures now show the HTTP error instead of silently hiding the result. Browser validation confirms one-click activation, object filter, time focus and visible dashed paths.
