# Fixed Florida hour for model development

The displayed hour from **24 November 2026, 13:16:39–14:16:39 EST** is preserved
in `data/frozen/florida/20261124T194525Z/`. Its window is exactly 3,600 seconds.
It contains all seven intersections, 243,012 received raw frames, 5,261 phase
samples and 29,725 plotted trajectory fragments. A fragment is not a distinct
vehicle. The archive occupies approximately 2.36 GB and is excluded from Git.

| Intersection | Raw frames |
| --- | ---: |
| Cranes Roost | 35,960 |
| Hattaway | 34,580 |
| Renaissance | 35,999 |
| Essex | 30,653 |
| Plaza Entrance | 35,631 |
| Palm Springs | 35,995 |
| Boston | 34,194 |

## What is fixed

- `snapshot.json` is the exact published time-space dataset, with its coordinate
  transforms, receipt timestamps and recorded gap evidence.
- `raw.sqlite3` retains the received frame and phase payloads for the same hour.
  All 242,815 raw frames counted by the published snapshot are present through
  its per-site receipt cutoffs. Another 197 raw frames from the final approximately
  three seconds are retained separately in the raw archive; the plot is not
  silently rewritten to include them.
- `reconstruction.json` keeps the corresponding inferred layers separately.
  They are comparison outputs, not ground-truth training labels.
- `coverage.json` records per-site counts, spans, occupied seconds and receipt
  gaps. Receipt gaps are not automatically interpreted as missing vehicle motion.
- `source/` keeps tracked source/configuration from commit `1546437`; the actual
  effective transforms are also embedded in the snapshot.
- `manifest.json` records the source, window, verification results and SHA-256
  checksums. Archive files are read-only to prevent accidental overwrites.

The database passed SQLite's `quick_check`. Counts at each published cutoff
match, and the raw archive has no frame outside the requested hour. The temporary
whole-buffer copy was removed after verification. Live collection and the
existing 90-minute rolling retention remain separate.

## Viewer

[Open the fixed hour](http://127.0.0.1:8775/florida_rolling.html?frozen=20261124T194525Z&between=1).
The seven-site selection, direction, object-type filtering and mouse-centered zoom
remain available. The page is explicitly labeled **frozen**, does not poll for a
new hour, and does not apply the rolling viewer's expiry rule. The original
rolling page remains available through its adjacent link.

The new read-only API accepts only a timestamp-shaped capture ID and verifies
saved-file hashes and window consistency. It exposes the plotted snapshot and
matching inferred layer; it does not expose the raw SQLite database. Traversal,
symlink escape, incomplete archives and mismatched layers are rejected.

The archive survives a dashboard restart. Its localhost viewer still requires
the dashboard server running on this computer; this is not a public link.

## Using the hour fairly

Use recorded positions as targets and store every model's output outside the
frozen directory. Keep the two tasks separate: same-intersection missing portions
and matching between adjacent intersections. Hiding observations can assess the
former and provide a same-sensor proxy for the latter; it cannot establish real
cross-sensor identities or the actual motion where neither sensor observed it.

This hour overlaps data already used in development and evaluation. It is a
repeatable benchmark, **not a newly untouched final test set**. Fixed time/identity
splits can guide further development, but final validation needs a different
later recording. Geometry, clock offsets and signal-to-movement mappings retain
their existing uncertainty. Freezing data improves reproducibility; it does not
make perfect recovery identifiable.

Validation: 11 archive/rolling-response tests passed, including fixed archived
windows, unchanged rolling expiry, integrity failures, traversal and window
mismatches. Browser verification checks the frozen-hour label, all seven sensors,
fixed bounds and working trajectory controls.
