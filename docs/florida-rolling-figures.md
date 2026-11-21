# Florida rolling speed and trajectory figures

The Florida view is available at http://127.0.0.1:8768/florida. It shows a one-hour receipt-time window and publishes a new snapshot every 1,800 seconds. The first snapshot is produced after approximately 30 seconds of collection. Startup coverage is therefore short; after about an hour the view can contain a full hour of newly collected observations. The header states the window, snapshot time and next update time in America/New_York.

A separate worker samples the latest Florida frame at up to 2 Hz from data/florida-live.sqlite3. It deduplicates by site/session/event key and writes data/florida-rolling/buffer.sqlite3. It deletes rows older than 5,400 seconds on startup and each collection iteration (approximately every half second while running). SQLite secure_delete is enabled, and freed pages are reused. Existing historical captures and experiments are not deleted. Keep the Florida collector and rolling worker running; on restart the worker purges expired records before collection. A stopped computer cannot execute timed deletion.

Each published JSON snapshot contains only points within its one-hour window. Until the next half-hour refresh, its oldest point can approach 90 minutes in age. The viewer refuses an expired snapshot, including clearing an already rendered expired figure. The browser checks for a new snapshot every 15 seconds, so normal visual refresh can lag publication by up to 15 seconds. User filtering and zooming do not recalculate a newer collection window.

Trajectories are local sensor fragments, namespaced by site/session/track/class. Gaps over three seconds, incompatible receipt/sensor time increments, extreme speeds and discontinuities split tracks. Current provisional per-site rotation and Y reflection are applied; corridor direction comes from the local reference-point bearing. The display uses cumulative approximate inter-sensor distance, not surveyed road stationing. Directional and lateral filters are provisional. Sensor timezone and upstream latency remain unverified. Missing data remains blank and tracks are never joined between sensors. This view does not train DeepCTM or generate virtual paths.

Controls include selected intersections, eastbound/westbound direction, object classes, time zoom, pan slider, full-hour reset and speed hover labels. Red/yellow/green represent speed, not traffic signal state. The existing saved Finch gallery remains at the viewer root and links to the Florida rolling page.

## Running

- Keep scripts/connect_florida.command running with private credentials entered there.
- Run scripts/open_florida_rolling.command (or .venv/bin/python -m deepctm.florida_rolling) for retention and publishing. A file lock prevents duplicate writers.
- Run scripts/open_deepctm.command for the port 8768 viewer.
- Open http://127.0.0.1:8768/florida.

## Validation

85 dashboard tests passed. New tests cover 90-minute retention boundaries, duplicate suppression, session isolation, exact one-hour query bounds, the 1,800-second publication interval and expiration after the 90-minute horizon. JavaScript syntax and diff checks passed. Browser verification confirmed all seven sites in the first published snapshot and 177 eastbound local fragments at inspection. The first published snapshot contained 61 sampled frames per site. This verifies startup operation; a full 90-minute elapsed-time retention run has not yet completed.
