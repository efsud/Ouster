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
