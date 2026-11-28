# Rolling figure recovery — November 24, 2026

The figures disappeared because both last published windows were older than the
90-minute rolling horizon. The Florida writer log also recorded a background
SQLite read failure caused by a database lock. Restarting exposed a second fault:
startup cleanup time incorrectly counted as collection time.
A refresh could therefore publish only a few frames, followed by a 30-minute wait.

The shared Florida/Finch writer now enables SQLite WAL on the **local rolling
buffer only**. A read-only transaction gives every query in one figure job the
same committed database view, while ingestion can continue committing. The view
is released when the job closes its reader; no permanent database copy is made.
Existing source/collector databases and upstream sensor settings are unchanged.
The existing single-writer file lock still prevents competing rolling writers.

Transient SQLite busy/locked errors in ingestion roll back the unfinished buffer
transaction and retry. Journal cursors advance only after `copy_batch` commits;
failed preview/phase writes are retried without claiming they were saved. Health
reports a retry state. Other SQLite failures still surface as errors rather than
being silently treated as contention.

Failed asynchronous figure jobs now preserve the previous complete snapshot and
leave ingestion running. They retry after 5, 10 and 20 seconds; recurring failure
then backs off for one normal 30-minute refresh interval. Health records the safe
exception category, failure count and next retry time. Successful publication
atomically replaces the snapshot and clears the retry state. A previous snapshot
still expires under the existing 90-minute display policy; retrying never makes
old data appear current.

Warm-up starts **after startup cleanup and setup finish**. Both normal refreshes
and explicit refresh markers require at least 30 seconds of warm-up, at least
30 seconds between the oldest/newest available receipts, and a receipt within
the latest 10 seconds. A manual refresh marker remains pending until those
conditions are met. The first diagram may be a clearly partial recorded hour;
it should not be an empty diagram produced immediately after a long cleanup.

For example, if cleanup ends at 09:20:00, a refresh request at 09:20:02 waits until
at least 09:20:30 and until sufficient fresh receipt evidence exists. A figure
read failing at 09:21:00 retries at 09:21:05 while received frames keep accumulating.

Validation: eight new resilience tests cover concurrent WAL readers/writers,
startup/request warm-up, stale/no receipt rejection, in-flight and backoff guards,
failed-job recovery without replacing the old snapshot, bounded/sanitized failure
reporting, and rejection of non-finite figure output. Together with existing
receipt-timing, frame-journal, replay and class-continuity tests, **18 tests pass**.
Runtime reception and visible publication must still be checked after deployment.

Run:

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 \
  .venv-deepctm/bin/python -m unittest deepctm.test_rolling_resilience \
  deepctm.test_rolling_time_basis deepctm.test_frame_journal \
  deepctm.test_frame_replay deepctm.test_vehicle_class_continuity
```

The viewer now has **Show recorded span** beside **Full hour**. This zooms to
retained trajectories in the selected direction/sites after a restart, while
keeping the full-hour view available. Florida was visually checked with fresh
trajectories at all seven intersections; both corridors published new snapshots.
The combined regression/cache/resilience check passed 19 tests.
