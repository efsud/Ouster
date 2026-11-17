# Finch rolling speed figures

Open http://127.0.0.1:8768/finch. Florida remains at /florida and the saved Finch experiment gallery remains at /.

The Finch viewer uses the same tested trajectory pipeline as Florida, with a separate buffer in `data/finch-rolling`. It reads fresh preview frames from `data/finch-live.sqlite3` at up to 2 Hz. No new credentials or subscriptions are needed while the Finch live collector is running.

Each snapshot shows the preceding 60 minutes and is rebuilt every 30 minutes. The first snapshot appears after about 30 seconds; its hour is mostly blank until more data accumulates. For example, a snapshot produced at 12:30 shows 11:30–12:30, and the next snapshot at 13:00 shows 12:00–13:00. The rolling worker deletes sampled frames older than 90 minutes. Existing saved experiments are untouched.

Start the worker with `scripts/open_finch_rolling.command` and the viewer with `.venv/bin/python -m deepctm.preview`. Keep the computer, Finch live collector, and rolling worker running. Cleanup cannot execute while the computer is off; startup purges expired records. The API and browser refuse expired snapshots.

Choose intersections, direction, and object classes; zoom or pan within the hour. Times use America/Toronto. Alignment and corridor station distances remain provisional. These are local observed fragments, not matched vehicles across sensors or predicted paths. Missing or stale sensors remain blank; no traffic is invented.

Implementation shares the Florida collector and chart renderer, with independent storage and scheduling. Tests cover retention boundaries, duplicate suppression, time windows, session isolation, and Finch-specific snapshot reading and expiry. A full elapsed 90-minute run has not yet been validated.
