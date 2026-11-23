# Florida screenshot gap review — November 23, 2026

The annotated screenshot distinguishes local missing observations from missing
connections between adjacent intersections. This update addresses two specific
admission/association defects; it does not claim complete trajectory recovery.

## What the screenshot's vertical interruption means

A read-only check of raw frames around 12:08 EST found the following adjacent
receipt gaps. All pairs remained in the same collector session.

| Site | Receipt interval (s) | SDK elapsed interval (s) | Shared object IDs |
|---|---:|---:|---:|
| Renaissance | 5.268 | 0.099755 | 41 |
| Boston | 4.430 | 0.099991 | 48 |
| Cranes Roost | 4.682 | 0.100004 | 75 |
| Hattaway | 7.692 | 0.099892 | 49 |
| Palm Springs | 4.707 | 0.099989 | 59 |
| Plaza Entrance | 6.206 | 0.100015 | 45 |
| Essex | 4.539 | 0.099695 | 44 |

This establishes a discrepancy between delivery timing and frame timing. It does
not establish which network/process caused the pause, the absolute SDK timezone,
or synchronized clocks between sensors. Connecting these points across the
receipt-time delay as though a vehicle moved for five seconds would distort its
speed. The clock-disagreement checks remain active. A future event-time view
must handle duplicate timestamps, clock resets and cross-sensor offsets explicitly.

## Change 1: admit the existing stationary estimator at the local gate

The same-ID candidate gate previously rejected every negative signed displacement
before the already-validated stationary fallback could inspect it. Tiny position
noise in stopped queues therefore left recoverable gaps blank.

Admission now permits this exception only when the existing stationary estimator
passes: same site/session/object; quiet measured contexts on both sides; gap no
longer than 30 seconds; endpoint separation at most 10 cm. Clock, lateral,
movement and site-exclusion gates still apply. Hattaway remains excluded from this
stationary correction. Classification changes do not create a new object ID.

Example: measured endpoints 10.00 m and 9.96 m with quiet visible context produce
an estimated stationary position of 9.98 m. The dashed estimate has 2 cm residuals
at its ends. The solid observed points are unchanged. This is explicitly a latent
stationary position, not exact endpoint interpolation or observed truth.

Fixed 5/10/20-second masks were placed at fixed offsets in continuous recorded
tracks. Hidden points did not enter the estimator. The early half-hour was checked
first; the later half excludes earlier IDs and has a 30-second embargo.

| Partition | Accepted masks | Distinct IDs | Position MAE | Speed MAE | Stop precision |
|---|---:|---:|---:|---:|---:|
| Development | 1,341 | 398 | 0.02484 m | 0.07227 m/s | 1.0 |
| Later test | 2,601 | 614 | 0.02405 m | 0.07044 m/s | 1.0 |

These are conditional quiet-endpoint results, not overall gap recall. Repeated
masks from a vehicle are correlated. The source hour was 12:14:48–13:14:48 EST.

## Change 2: use terminal fragments for adjacent-intersection matching

If an accepted same-ID local bridge joins fragment A to fragment B, A's end is an
internal endpoint, not a new departure. B's beginning is likewise not a new
arrival. These endpoints are now excluded from cross-site matching. Only unique,
coincident endpoints of accepted same-ID bridges qualify; changed-ID hypotheses
cannot suppress competitors. No inferred samples enter observed endpoint speed
fits. Measured geometry and movement restrictions remain intact.

Worked example: A → local dashed bridge → B → next intersection. The matcher
considers B's final observed departure, rather than making A and B compete as
separate departing vehicles. Ambiguous duplicate fragments are left unchanged.

A fixed test fragmented recorded tracks before hidden spatial bands. The source
ID was used only for scoring and local continuity; cross-track costs remained
identity-blind. The later test excluded IDs seen in the earlier half.

| Partition | Correct before → after | Wrong identities before → after |
|---|---:|---:|
| Development | 794 → 798 | 10 → 9 |
| Later test | 787 → 787 | 3 → 2 |

This improves the proxy's error count, not held-out recall. Real cross-sensor
identities remain unverified.

## Published result for the same recorded hour

Local estimates increased **1,628 → 1,696**. The 68 added stationary estimates are
Cranes 15, Renaissance 9, Essex 19, Plaza 12, Palm 5 and Boston 8. Between-site
estimates changed **2,095 → 2,086** after internal endpoints were excluded. Fewer
rendered associations must not be described as more matched vehicles.

Both optional dashed layers remain separate. The expanded “Method comparison and
limitations” panel shows the new tests and timing explanation. The original
recordings, live collectors, signal settings and Finch policy were not changed.

A separate whole-recording-outage diagnostic deleted all frames in fixed
10/30/60-second intervals from a temporary database copy. It recovered 16/68
endpoint-supported IDs for the 10-second case and 2/15 for the 30-second case;
the 60-second case had no continuous endpoint-supported truth. An experimental
stationary-fragment retention option recovered 27 and 3 respectively, but is
not enabled by this update. These diagnostics show that general outage recovery
remains incomplete; they are not the acceptance test for the narrower deployed
stationary-admission fix.

## Reproduction and saved evidence

- `deepctm/validate_stationary_admission.py`: hidden quiet-gap evaluation.
- `deepctm/validate_fragment_terminals.py`: fragmented spatial matching proxy.
- `deepctm/validate_recording_outages.py`: whole-interval frame removal diagnostic.
- `data/reconstruction/nov23-gap-review/`: protocols, results, screenshot timing
  audit, before/after deployment counts, worker log and browser screenshot.
- `config/reconstruction/florida-gap-integrity.json`: enabled Florida policies.

Run from the project root using `.venv-deepctm/bin/python -m` and the relevant
module name. Validation reads current recordings and writes derived evidence;
it does not restart collection or modify the live raw database.
