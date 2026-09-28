# Ouster Corridor Observatory

A local, read-only dashboard for LiDAR corridor and intersection analytics.
Developed from the API manual and SDK already in this repository and the supplied
[LaTeX KPI specification](docs/kpi-specification.tex).

## Run the dashboard

Requires Python 3.11. The dashboard uses Python's standard library; the pinned
Leaflet map library is included locally with its license.

```sh
python3 -m dashboard.server
```

Open **http://127.0.0.1:8765**. The dashboard opens on Toronto, centered on the Finch West LRT corridor,
with the ten supplied Toronto UDIDs in the intersection list. Florida remains
available in the network selector. Sensor locations
and live measurements remain unavailable until verified. In Historical performance, **Load learning dataset** creates
explicitly synthetic examples. The CTM explorer works without credentials.

## Connected mode: enter credentials privately

Use the supplied Python SDK, not the activation links or a browser login.
The API account must be authorized for the selected sensor. Portal account
activation does not establish API or sensor permissions by itself.

```sh
python3 -m venv .venv
.venv/bin/python -m pip install 'Data API/Realtime SDK/bctRealtimeSDK_Subscriber-3.1.0-py3-none-any.whl'
# Stop any existing dashboard on port 8765 first (Ctrl+C).
.venv/bin/python scripts/start_connected.py
```

The launcher asks for:

1. BlueCity API username.
2. BlueCity API password (hidden while typing).
3. Sensor UDIDs, separated by commas (leave blank for cloud history only).

For the ten Toronto sensors, double-click `scripts/connect_toronto.command`.
It selects all ten Finch West UDIDs, prompts privately for credentials, and uses
port 8767 so it can run alongside an existing session. Equivalent command:
`.venv/bin/python scripts/start_connected.py --port 8767 --toronto`.

For the seven supplied Florida sites, double-click
`scripts/connect_florida.command` on macOS. It opens Terminal, selects all seven
UDIDs automatically, and asks only for your API username and hidden password.
It starts the connected dashboard on port 8766, alongside the preview on 8765.
Equivalent command: `.venv/bin/python scripts/start_connected.py --port 8766 --florida`.

Credentials stay in process memory and are passed to the child processes through
their environment. They are never written to files or command-line arguments.
Ctrl+C stops the server and all recorders. Use `--port 8766` if the preview already
occupies port 8765. Never put passwords or activation tokens in Git.

The recorder uses `BCTWSConnection` with FRAME, PHASE_CHANGE, and LOOP_CHANGE
subscriptions. The supplied SDK owns streaming and reconnect behavior. A local wrapper adds bounded HTTP calls and sanitized authentication/routing diagnostics.
If authentication repeatedly fails, stop and verify API credentials and access
with Ouster. The SDK has no bounded authentication retry loop.

### Site metadata

Create `config/sites.local.json` (ignored by Git) with metadata verified by Ouster.
This merges with the configured Toronto/Florida inventory by ID:

```json
{
  "sites": [
    {
      "id": "REPLACE_WITH_TORONTO_UDID",
      "name": "Verified Toronto intersection name",
      "region": "Toronto",
      "corridor": "Verified corridor name",
      "timezone": "America/Toronto",
      "origin": {"lat": 0, "lng": 0},
      "rotation_deg": 180,
      "calibration_verified": false
    }
  ]
}
```

**Replace the origin; (0,0) is a placeholder, not a Toronto location.** Validate
sensor origin, axis convention, and rotation against known road features before
setting `calibration_verified` to true. The supplied coordinate script has not
yet been received. The independent local tangent-plane converter supports a
configurable rotation; 180° must be verified per sensor. Refresh the browser
after metadata changes. All calibrated site streams in the selected network are
shown at zoom 17+, with objects restricted to the map viewport; frames older than 5 seconds
are hidden and labelled stale.

For corridor lines, add a `corridors` array alongside `sites` in the local JSON.
Each item needs `name`, `region`, `geometry_verified:true`, and `coordinates` as
an ordered array of `[longitude, latitude]` points following the actual roadway.
Unverified paths are ignored. Site inventory order is never used to guess a corridor.

## Features and honest boundaries

| Section | Available now | Still needs verified site data |
| --- | --- | --- |
| Live network | Zoomable map, site inventory, read-only recorder, latest-frame display, freshness check | Authorized SDK access, verified georeferencing and corridor geometry |
| Historical performance | Persistent SQLite windows, seven KPI formulas, quality flags, date/approach selection, charts, JSON import, CSV export | Verified scene geometry, real trajectory samples and independent field comparisons |
| Anomalies | Explainable traffic/data-quality rules, baseline readiness, evidence, local acknowledgement | Ten valid baseline days and independent manual review |
| Cloud history | Allowlisted TMC and phase GET requests; raw JSON saved locally | API entitlement and live response validation |
| CTM explorer | Single-intersection / 3- or 7-intersection through-lane scenarios, signal gates, density heatmap, conserved upstream backlog | Calibration, turning flows, lane groups, observed signal plans |
| Optimization | Reserved tab | Reinforcement learning model; intentionally deferred |

The geometry-gated processor now turns received frames into provisional five-minute and Toronto calendar-day KPIs. It **does not establish field validity**. Lane assignment, entry/stop-line crossing, queue membership, physical-track
deduplication, and signal-phase mapping require real scene geometry and sample
data. Import validated annotated windows using [the data contract](docs/data-contract.md).
No cloud aggregate is silently substituted for the LaTeX definitions.

No site configuration or controller-writing endpoint is implemented. The server
binds to loopback only; it is not a multi-user internet deployment. Basemap tiles
are requested from OpenStreetMap and need an internet connection. Data is stored
under ignored `data/`; raw SDK events expire 30 days after receipt. Derived KPI/anomaly evidence remains indefinitely. SQLite is backed up before migration. See [implementation and validation](docs/toronto-implementation.md).

## Learn and verify

- [Learning guide](docs/learning-guide.md): architecture, formulas, exercises, and file tour.
- [Change log](docs/change-log.md): what was created, why, and remaining integration work.
- [API review](docs/api-review.md): reviewed sources, conventions, and unresolved details.
- [Data contract](docs/data-contract.md): imports and quality rules.

```sh
python3 -m unittest discover -s dashboard/tests -v
node --check dashboard/static/app.js
```

To refresh the map library reproducibly: `npm ci --ignore-scripts`, then
`python3 scripts/vendor_map.py`. `package-lock.json` pins the dependency.

Development branch: `codex/corridor-dashboard`. Existing vendor documents and SDK
are preserved. Measured datasets, local configuration, and credentials are not
published to GitHub.

## Toronto implementation and acceptance

Read [the task-by-task report](docs/toronto-implementation.md) for implemented behavior, tests, remaining field gates, local metadata schema and API interfaces. Calibration now requires versioned reference metadata and at least three independent landmark checks; setting the boolean alone is insufficient.

## One-hour Toronto test

Use `.venv/bin/python scripts/start_connected.py --toronto --port 8768 --duration 3600` and the private credential prompt. Saved raw observations remain after automatic shutdown. Approximate intersection markers are now available; they do not substitute for calibrated sensor origins. See [first real reception report](docs/toronto-live-test.md).
