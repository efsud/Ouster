# Centre placement update — 2026-10-06

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
