# Florida: evidence-supported local gap recovery

Implemented 23 November 2026. This is an **additive local reconstruction improvement**, not a replacement for existing matches. It recovers some short interruptions where the same tracked vehicle moves sideways. It does not guess a match between different IDs, infer a signal state, or connect different intersections.

## Why trajectories remained disconnected

The audit of consecutive same-ID fragments found lateral displacement, conflicting sensor/receipt durations, insufficient visible endpoint context, reverse motion, and long disappearances without an independently observed recording outage. Some gaps cannot be filled safely. The two-metre lateral gate was a useful target for a narrow improvement because a plausible lane change can exceed that displacement.

The per-intersection counts and source hash are saved in `data/reconstruction/local-lateral-review/rejections.json`. Counts describe rejected proposals, not unique missing vehicles. Clock, identity, direction and long-gap restrictions remain in place.

## New admission checks

- Same site, recording session and object ID; both fragments must be cars.
- More than 1.5 and at most 10 seconds missing.
- Consistent travel direction, movement labels when available, and SDK-versus-receipt elapsed time.
- The old same-ID gate must reject the proposal; existing accepted paths are preserved.
- Lateral displacement above 2 m and no more than 7.2 m, with continuous observed endpoint context.
- Exact longitudinal endpoint reconstruction under the existing speed and acceleration limits.
- A lateral curve consistent with both visible endpoint slopes, bounded by 2 m/s lateral speed, 1.5 m/s² lateral acceleration, road-region bounds, and no unexplained overshoot beyond 0.5 m. Combined acceleration is limited to 4 m/s².

The lateral curve is used as evidence for admission. The time–space diagram still shows longitudinal position; it does not establish a physical lane assignment. Raw observations remain unchanged and the missing portion is dashed. A failed test leaves a blank gap.

Example: the same ID disappears for five seconds and returns approximately 3.5 m sideways. If the two visible fragments, timestamps, direction, longitudinal curve and lateral motion are mutually consistent, the missing portion can be shown. A nine-metre sideways jump, another session/ID, inconsistent clocks, or an unsupported curve remains unconnected.

## Hidden-data validation

Recorded Florida window: 11:14:47–12:14:47 EST on 23 November 2026. Development uses tracks wholly before 11:44:17; test uses tracks wholly after 11:45:17. Site/session/object IDs appearing in the first half are excluded from the test. The test interval was not used to set curve parameters.

Hide five- and ten-second portions of continuous recorded tracks. Recover actual SDK endpoint timestamps and lateral positions from a temporary consistent SQLite copy, including visible lateral context and hidden lateral truth. Do not fabricate clocks or copy the complete track's movement label into the predictor. Missing raw evidence excludes a case; none was missing in this completed run.

Sampling is stratified toward tracks with lateral motion, so these acceptance rates are **not overall corridor recall**. Repeated gap lengths can reuse a vehicle. Raw replay is temporary; saved artifacts contain metrics, identity hashes and provenance.

| Partition | Evaluated masks | Additional accepted masks | Distinct accepted IDs | Mean longitudinal error | Mean lateral error |
|---|---:|---:|---:|---:|---:|
| Development | 2,543 | 192 | 169 | 1.11 m | 0.30 m |
| Later test | 2,686 | 149 | 138 | 1.05 m | 0.32 m |

The fixed aggregate acceptance rule required at least 20 distinct identities across two sites, mean longitudinal error ≤3 m, mean speed error ≤1 m/s, 95th-percentile case mean error ≤10 m, lateral mean error ≤0.75 m, and zero numerical physics violations in both partitions. It passed.

Additional conservative site-level safeguards withheld sites with insufficient evidence or poor errors; these are post-test deployment restrictions, not an independently optimized site policy:

| Intersection | Deployment | Evidence/reason |
|---|---|---|
| Renaissance | Enabled | 55 additional test masks, 51 identities |
| Cranes Roost | Enabled | 13 masks, 13 identities |
| Hattaway | Enabled | 25 masks, 24 identities |
| Essex | Enabled | 16 masks, 14 identities |
| Boston | Withheld | Only 3 distinct accepted test identities |
| Palm Springs | Withheld | Only 8 distinct test identities; development speed error also above threshold |
| Plaza Entrance | Withheld | Test speed MAE 1.27 m/s, above the 1 m/s threshold |

The enabled subset contains **109 additional test gaps / 102 identities**: longitudinal MAE 0.92 m, lateral MAE 0.27 m, speed MAE 0.71 m/s, and 95th-percentile case mean position error 2.10 m. These are errors against deliberately hidden recorded data, not accuracy measurements inside real outages.

Stop detection remains weak: among the four accepted test cases with a hidden stop, only one was reconstructed as stopped; two predicted stops included one false positive. This method must not be treated as verified stop duration, signal state or operational KPI ground truth. It is principally a short missing-path estimate.

## Software and operational checks

55 reconstruction/regression tests and six API tests passed, including preservation of existing paths, unchanged between-intersection output, site exclusions, mismatched IDs/sessions/clocks, excessive lateral motion, long gaps, and the two-coordinate lateral endpoint representation. A regression in optional speed-color metadata for two-coordinate lateral context was fixed; measured speed-color behavior for three-coordinate trajectories remains intact.

Configuration: `config/reconstruction/florida-local-lateral.json`. Code: `deepctm/local_lateral_recovery.py`. Validation: `python -m deepctm.validate_local_lateral --output data/reconstruction/local-lateral-review`. The dashboard shows the new local estimate count and its own validation summary. Finch and Florida's between-intersection matcher are unchanged.

[Florida figures](http://127.0.0.1:8775/florida_rolling.html?between=1)

The original request for evidence-supported connections is preserved: there is no claim that every disconnected trajectory is reconstructed, and there are no simulated continuations without observed endpoints.

## Current-hour publication check

The new output added 56 local estimates: Cranes Roost 32, Renaissance 12, Essex 7, and Hattaway 5. Total local paths rose from 1,051 to 1,107; between-intersection paths remained 2,212. These counts describe the current displayed hour, not validation recall. Existing paths are preserved by the additive integration test.
