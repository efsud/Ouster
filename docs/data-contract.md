# Annotated window import contract

POST `/api/import` or use Historical performance → Import JSON. Supply a JSON
array of 1–1000 windows, maximum 5 MB. Validation is atomic: one invalid window
rejects the batch. Reimporting the same site, approach, times and source replaces
that window. Record source lineage outside the dashboard if revisions must be audited.

Every timestamp is Unix seconds in UTC. Windows are half-open `[start,end)`.
The UI selects a local date/time and converts it to UTC. Windows must fit fully
inside the selected range; partial windows are not rescaled. Charts use UTC.
Daily processing uses local calendar boundaries in America/Toronto (23/24/25 hours) and recomputes from archived observations. Never average five-minute percentiles or rates.

```json
[
  {
    "site": "OBC-AG-SA-C251068",
    "approach": "NB",
    "source": "annotated-import",
    "start": 1789992000,
    "end": 1789992300,
    "length_m": 100,
    "free_speed_mps": 10,
    "lanes": 2,
    "coverage": 0.95,
    "signal_synchronized": false,
    "entry_observation_complete": true,
    "departure_observation_complete": false,
    "green_seconds": null,
    "tracks": [
      {
        "id": "unique-physical-trajectory",
        "vehicle": true,
        "entry": 1789992010,
        "arrival": 1789992040,
        "exit": 1789992042,
        "complete": true,
        "max_gap_s": 0.2,
        "stopped_s": 12,
        "green": null,
        "departed_from_queue_on_green": false
      }
    ],
    "queue_samples": [
      {"time": 1789992000, "length_m": 20, "visible": true},
      {"time": 1789992005, "length_m": 0, "visible": false},
      {"time": 1789992010, "length_m": 25, "visible": true}
    ],
    "cycles": []
  }
]
```

The example illustrates the schema; it is not real Florida data. It will be
provisional because only one complete traversal is included.

## Annotation responsibilities

- `id`: a physical trajectory ID after validated deduplication; duplicates reject.
- `vehicle`: explicit class validation, not an assumption for missing class codes.
- `entry`, `arrival`, `exit`: observed entry, first stop-line arrival within the
  tolerance, and downstream departure/crossing time. Null means censored/missing.
- `complete`: both approach boundaries observed; complete stopped delay additionally
  requires the exit and stopped-time integral. Do not set it on censored tracks.
- `max_gap_s`: largest gap across the trajectory. Required; >3 seconds excludes it.
- `stopped_s`: integral of speed <= chosen 2–3 m/s threshold over entry to exit.
  Compute from trustworthy timestamps; do not impute zero speed for missing SDK speed.
- `green`: true/false only when arrival phase is known and clocks synchronized.
- `departed_from_queue_on_green`: verified stopped-to-moving departure during green.
- `coverage`: valid observation fraction of the window, between 0 and 1.
- Observation-complete flags certify event counting was possible. Without them,
  volume/discharge are unavailable rather than interpreting no tracks as zero traffic.
- `queue_samples`: regular time grid, unique times, lane-consistent queue members,
  designated queue region, plausible spacing. Visible empty queue = 0; occlusion
  = `visible:false`. Invisible samples are excluded from P95.
- `cycles`: `{start,end,residual_queue_m,visible}` for complete nonoverlapping cycles;
  residual queue must be measured at effective-green end. Incomplete/out-of-window
  or invisible cycles are excluded from split failure.
- `green_seconds`: effective-green duration within this window for this lane group.
- Merge counts/merge audit logs, spatial calibration versions, phase mapping, and
  visibility assessment must be retained by the scene annotation pipeline.

The current calculator checks numbers, temporal ordering, duplicate IDs, basic
queue sampling, cycles, counts, and coverage. It cannot independently verify the
truth of imported scene annotations. `passes-input-checks` is not field validation.

## Local storage

`data/ouster.sqlite3` stores raw frames/events and normalized windows plus results.
`data/cloud/` stores raw vendor JSON responses from allowlisted GET requests.
Neither is included in Git. Cloud responses are not yet converted into paper KPIs.
History supports pagination; CSV exports all matching rows. The legacy unpaged JSON response remains limited to 10,000 windows. See toronto-implementation.md for raw retention and new interfaces.
