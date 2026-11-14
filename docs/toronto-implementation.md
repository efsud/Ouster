# Toronto implementation and validation — 2026-09-24

Tracking: https://github.com/efsud/Ouster/issues/13. Draft PR: https://github.com/efsud/Ouster/pull/1.

## Actual evidence

40 Python tests pass, JavaScript syntax passes, and the browser smoke check passes
map inventory, history, export, CTM, Optimization, mobile layout and multi-site
viewport filtering. Fixtures are synthetic. The latest local database audit has
**zero raw events, zero latest frames, 36 synthetic windows, zero real KPI windows**.
No sensor access, coordinates, 30-minute operation, or traffic detector is field-validated.

| Task | Implementation and software evidence | Remaining acceptance evidence |
| --- | --- | --- |
| [F1 #2](https://github.com/efsud/Ouster/issues/2) | Sanitized auth/routing/transport states, clock quarantine, batched SDK writes; mocked auth and timestamp tests | Restart private credential launcher; inspect actual events and authorization for all ten sensors |
| [L1 #3](https://github.com/efsud/Ouster/issues/3) | Version/reference/landmark calibration gate; residual test | Authoritative origins, axes, rotation, independent landmarks, original Python converter |
| [L2 #4](https://github.com/efsud/Ouster/issues/4) | Calibrated markers, multi-site objects/classes, event age; unit/browser checks | Real coordinate and class comparison at every calibrated site |
| [L3 #5](https://github.com/efsud/Ouster/issues/5) | One-second poll, five-second expiry, rendered-object latency recording and audit script | 30-minute real session, P95 <=2 s, upstream latency and controlled recovery evidence |
| [H1 #6](https://github.com/efsud/Ouster/issues/6) | Backup before migration, atomic batches, replay dedup, receipt retention; restart/rollback/boundary tests | Sustained SDK-rate collection and real restart/storage-failure exercise |
| [H2 #7](https://github.com/efsud/Ouster/issues/7) | Geometry/lanes, directional crossings, position-derived speed, queues, censored fragments; synthetic motion/gap/session tests | Annotated real trajectories, occlusion/ID-switch review, verified geometry/phase mappings |
| [H3 #8](https://github.com/efsud/Ouster/issues/8) | Five-minute and calendar-day processing, provenance, quality flags; hand counts/AOG and DST tests | Field hand calculations and reference comparison |
| [H4 #9](https://github.com/efsud/Ouster/issues/9) | Received default, availability, raw pages, history pages, input evidence and complete CSV export; interface/browser tests | Trace real values and compare volume ±10%, AOG ±5 points, turns ±5% where references exist |
| [A1 #10](https://github.com/efsud/Ouster/issues/10) | Quality faults, robust baselines, 2-window persistence, verified storage thresholds; warmup/zero-MAD/outage tests | Labelled Toronto replay and threshold review |
| [A2 #11](https://github.com/efsud/Ouster/issues/11) | Persistent timeline/evidence/notes, acknowledgement, source links, marker highlighting; persistence/API tests | Real review workflow and evidence audit |
| [A3 #12](https://github.com/efsud/Ouster/issues/12) | Manual-label scoring tool and provisional labels | Independent positive/negative samples, false positives/misses, published review report |

All acceptance issues remain open. “Implemented” means code exists, “software-tested”
means the stated fixtures pass, and “field-validated” requires independent real evidence.
The review tool is a foundation for A3, not completion of the review itself.

## Local connection and metadata

Stop the previous Toronto launcher using Ctrl+C in its Terminal, then double-click
`scripts/connect_toronto.command`. Enter username/password in the private Python
prompt. It starts the updated ten-sensor collectors and dashboard at port 8767.
The preview at 8765 shares the database but has no credentials. Never paste
credentials or activation links into issues. No remote configuration is changed.

Supply verified metadata in ignored `config/sites.local.json`. Each site needs:

- `id`, `origin: {lat,lng}`, `rotation_deg`, `calibration_verified:true`.
- `calibration: {version,reference,max_residual_m,landmarks}`; at least three distinct
  independently located landmarks `{x,y,lat,lng}`. The 2 m default tolerance is
  configurable and must suit the survey. This is a residual check, not a survey.
- `scene: {verified:true,version,reference,signal_synchronized,approaches}`.
- Each approach: unique `id`, upstream-to-stop-line `centerline`, `analysis_polygon`,
  `queue_polygon`, `lane_polygons` (one per lane), `lanes`, `free_speed_mps`,
  `visibility_verified`; all local geometry is metres. Optional `exit_offset_m`
  defaults 3, `stopped_threshold_mps` 2.5, `max_queue_gap_m` 12. Optional `phase`
  requires independently verified synchronization; `storage_m` requires
  `storage_verified:true` before storage warnings are enabled.

The synthetic `site_fixture()` in tests illustrates the schema; **do not copy its
coordinates as Toronto metadata**. Intersection reference points are not sensor
origins. No origin, phase mapping or rotation is inferred from a street name.
Proto3 omits zero-valued coordinate fields; those defaults follow the SDK schema.
Missing timezone is quarantined, not guessed. This may expose a vendor clock
convention that requires confirmation before events can be processed.

## Storage, processing and limitations

Schema v2 keeps compatibility tables and adds `raw_events`, `latest_frames`,
`collector_health`, `anomalies`, `evaluations`, and `latency_samples`. Migration
first creates a local `.pre-v2-*.bak` backup. Raw retention is 30 days after
receipt; expired migration backups also expire. Derived inputs/results, anomaly
evidence and latency records remain. Legacy rows receive an explicitly labelled
migration receipt timestamp and are not treated as newly received SDK events.

A canonical event hash plus sensor/time deduplicates reconnect replays. Identities
are namespaced by sensor/session/fragment. No fragment merging or cross-sensor
matching is attempted. Gaps over three seconds split/censor observations. Position
differences determine speed; first-point speed is unknown. Queue tails are
stop-line-anchored, lane-specific connected stopped objects. Camera/LiDAR occlusion
cannot be proven absent by frame continuity; verified visibility is a required
operator assertion and must be checked against real scenes.

Five-minute windows use UTC-aligned boundaries, displayed with timestamp context.
Daily summaries use Toronto calendar days (23/24/25 hours) and recalculate from
observations. Daily discharge is unavailable per the source specification.
Coverage <80% and fewer than 15 complete traversals are flagged; traffic alerts
are suppressed when required inputs fail quality. Low-quality historical estimates
remain provisional for inspection. Signal metrics require verified phase data.
Complete observed green intervals provide residual queues at green end; field
comparison must confirm the vendor phase semantics match effective green.

The maintenance worker runs independently of UI polling; it processes at most two
new five-minute windows per minute after a five-minute settling buffer. Empty
intervals advance a persisted processing cursor without manufacturing observations.
Late events remain archived; manually reprocess affected ranges. The worker builds
yesterday's daily summary when the archive spans that day; historical backfill
uses the explicit processing interface. Processing cursor/calibration changes and
corrected windows require explicit reprocessing and anomaly review. This is a
local prototype; sustained throughput at ten real SDK rates remains unmeasured.

Baselines use prior 30 days, same site/approach/source/calibration, 30-minute local
time band and weekday/weekend; ten distinct valid days are required. MAD=0 yields
no statistical alert. The threshold is 3.5 scaled MAD, two consecutive five-minute
outliers in the same direction. Verified queue storage warnings use 90%, also two
windows. Outages are data-quality events, never evidence of zero traffic. All
traffic detections are provisional; historical corrections require review of
previous alerts, whose acknowledgement and notes are preserved.

## Interfaces

Existing clients retain their routes. New routes:

- GET `/api/received?site=...&cursor=...&limit=100`: keyset-paged original events,
  both clocks, source, processing status and quarantine reason.
- GET `/api/availability?site=...`: retained date bounds and status counts.
- GET `/api/history?...&paged=true&offset=0&limit=100&cadence=five_minute`;
  `daily` also supported. Unpaged legacy limit remains 10,000. CSV exports all
  matching records and ignores UI page offsets.
- GET `/api/window?site=...&approach=...&start=...&end=...&source=...`: saved inputs,
  raw-event keys, calibration/scene/calculation versions and result.
- POST `/api/process`: `{site,start,end,cadence:"five_minute"}` or
  `{site,day:"YYYY-MM-DD",cadence:"daily"}`. Geometry required; maximum two days.
- GET `/api/anomalies?site=...&category=traffic&offset=0&limit=100` and
  `/api/anomaly?id=...`: list/detail with retained evidence.
- GET `/api/anomaly-evaluations?site=...`: baseline readiness/suppression reasons.
- POST `/api/anomalies/evaluate`: `{site}`; POST `/api/anomalies/acknowledge`:
  `{id,note}`. These are local actions only.
- POST `/api/latency`: browser-render telemetry, keyed by recorded event.

## Field validation procedures still to run

Run `.venv/bin/python scripts/validate_live.py --start <UTC-epoch> --end <UTC-epoch>`
after a >=30-minute real session. Keep a calibrated site visible at zoom 17+;
latency telemetry samples actual displayed objects, not all received frames.
An animation callback is a browser-render scheduling approximation, not a
hardware display timing measurement. Validate computer/sensor clocks separately,
record controlled interruption/recovery and sensor-by-sensor availability.

For A3, manually label representative positive **and negative** windows, record
independent evidence references, and use `scripts/review_anomalies.py` (schema in
its docstring). Report precision/recall, false positives, missed labelled events
and threshold revisions. An alert-only review cannot measure missed events.

Optimization and the educational CTM are unchanged. CTM is never field truth.
