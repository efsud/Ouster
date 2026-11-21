# Florida reconstruction implementation from the supplied recommendations

Source: `Florida_Corridor_Trajectory_Reconstruction_Recommendations.docx`, supplied 20 November 2026. The entire document text was reviewed, including its M1–M4 comparison, holdout requirements, assumptions and references. Its four-stage integration is a project recommendation, not a single published algorithm. It prioritizes interpretable physical models before neural models.

## Requirements and current evidence

| Requirement | Implementation/evidence | Remaining work |
| --- | --- | --- |
| Passenger cars; fixed movement paths | Study restricts SDK class 2; existing direction/entry/exit metadata | Verify lane groups, projection and signal mapping |
| Associate upstream/downstream tracklets | Existing cost/margin association and movement eligibility | Global assignment and competing hypotheses; calibrated uncertainty |
| CTM queues and explicit side movements | `movement_queue.py`: conservative sending/receiving, CFL substeps, finite internal supply, explicit side arrivals/departures | Fit parameters to field calibration; connect actual phase/side-flow inputs |
| No invented signal permissions | Unverified permission series returns unavailable | Controller/scene confirmation or explicitly soft estimated evidence |
| M1 linear/Hermite baseline | `trajectory_reconstruction.baseline` | Compare across representative traffic regimes |
| M2 Newell candidates | Time/distance translation plus desired-speed bound; supported leader flag and continuous coverage required | Establish same-lane leaders from evidence; calibrate lag/spacing |
| M3 Newell + CTM + signals | Components implemented separately; missing priors explicitly reported | Integrate supported real inputs and score full candidate pipeline |
| M4 constrained refinement | Velocity optimization, exact piecewise-constant-acceleration integration, speed/acceleration bounds, endpoint tolerances, optional spacing/red ceilings, soft CTM envelope | Field comparison with full M3 priors; current experiment is a kinematic-only ablation |
| Separate train/validate/test areas and times | Frozen `config/reconstruction/florida-study.json`; disjoint sites and chronological windows; 30 s embargo | Obtain enough qualifying tracks in every partition |
| Hide whole intervals; no inferred truth | Only recorded class-2 tracks; masks 5/10/20/30 s; hidden values used only in scoring | Spatial masks and identity uncertainty ablations in same protocol |
| Metrics beyond position | Position/speed, stop duration and stop-event precision/recall, physics violations, acceptance and gap/regime breakdown | Queue/discharge error with independent observations |
| Uncertainty | Validation-only error-band radius; empirical test coverage, with correlation/domain-shift warning | Association uncertainty and multiple trajectory hypotheses |
| Two map layers | Existing observations-only view preserved during development | Separate within-intersection and inter-intersection toggles after evaluation; both distinctly inferred |
| AM/PM and independent periods | Protocol records source window/hash | Multiple periods/days needed; a short rolling sample cannot establish this |

## First data audit

The first run is saved under `data/reconstruction/word-v1-first-study/report.json`. It stopped with `insufficient_training_data`: the designated train sites/time contained zero qualifying complete tracks; validation had one track and the test sites had 198. These are track counts, not evaluated mask counts. The pipeline did not borrow held-out data, fit parameters to test data, select a winner, or publish new estimates. Sensors were receiving at the time of the subsequent health check, but that does not establish uninterrupted earlier coverage.

The study assigns Cranes Roost, Hattaway, Renaissance and Essex to training in the first 60% of the window; Plaza to validation in 60–80%; Palm Springs and Boston to test in the last 20%. Entire visible context must lie inside a partition after the embargo. This deliberately tests spatial and temporal generalization together and may be demanding for one hour of sparse night traffic. Any future redesign must be versioned before inspecting its test scores.

## Worked example

A passenger car observed at 0 m at time 0 and 100 m at time 10 s provides endpoint position and visible-neighborhood speed estimates. M1 connects those boundaries directly. A Newell candidate needs a supported leader at shifted times; it is unavailable if lane correspondence or leader coverage is missing. Refinement optimizes velocities and integrates positions using trapezoidal integration, equivalent to constant acceleration within each step. A stop-line ceiling is only admissible for a verified no-crossing interval before release. A resulting path is inferred even when its endpoints agree perfectly with observations.

## Reproduction

Use the existing `.venv-deepctm` environment with the pinned SciPy dependency in `deepctm/requirements.txt`.

```sh
.venv-deepctm/bin/python -m unittest deepctm.test_reconstruction -q
.venv-deepctm/bin/python -m deepctm.reconstruction_study --snapshot data/florida-rolling/snapshot.json --output data/reconstruction/NEW-RUN
```

Reports contain aggregate metrics and provenance, not a duplicate raw-frame archive. Existing raw retention remains 90 minutes. The study fails closed if training, validation or test support is inadequate. Validation selects the method before test inference; the optimizer never receives masked ground-truth samples.

Initial software checks: twelve tests pass for exact kinematics, bounded optimization, infeasible rejection, Newell shift/coverage, missing leader and signal evidence, temporal/spatial separation, hidden-truth isolation, red outflow suppression, side-flow conservation and finite storage. These synthetic checks do not establish field reconstruction accuracy.

## First completed comparison and two-layer display

The collection runner subsequently met its fixed readiness thresholds: at least 30 qualifying car fragments in each partition and at least ten eligible 5 s and ten 10 s masks per partition. It retained 147 training, 125 validation and 166 test fragments. Validation supplied 115 masks; 113 were accepted by every candidate. Test supplied 154 masks. Counts across mask lengths are correlated and do not represent independent vehicles.

Validation selected the bounded-acceleration kinematic ablation with smoothness 0.01. Its held-out mean per-gap position MAE was 0.860 m, versus 1.236 m for Hermite and 2.634 m for linear interpolation. Speed MAEs were 0.553, 0.690 and 0.930 m/s respectively. The kinematic model had zero violations of the tested speed/acceleration bounds. Stop-event precision/recall were 0.964/0.915; those thresholds describe a stop lasting at least two seconds within a masked interval. It is not full M4: leader, CTM and verified signal priors remain unavailable to this field comparison.

Training-only empirical bounds were vmax 24.5174 m/s, amin -6 and amax 4 m/s². Acceleration quantiles reached the declared guardrails, indicating sensitivity to detector noise. These are provisional numerical limits, not independently validated driver parameters. The only moving 30 s test mask had 17.316 m position MAE; the overall average must not be generalized to long unobserved stops.

The validation-derived 90% full-gap band radius was 2.723 m, with empirical test coverage 90.91%. Masks are correlated and areas differ, so this is an empirical diagnostic, not a guaranteed confidence interval. It does not apply between sensors.

The Florida figure has independent controls for (1) within-intersection missing data and (2) between-intersection estimates. Both layers contain passenger-car estimates only and remain separate from recorded observations and KPIs. The first checked snapshot yielded one local gap and 77 between-site proposals; counts change each window. Local candidates retain original lateral/clock admission checks. Inter-site proposals retain entry/exit movement filters and uncertain identity labels. The selected local optimizer is transferred experimentally to those longer gaps; its local test accuracy is not an inter-site accuracy claim.

A background layer publisher reads each new half-hour snapshot and uses the frozen selected method. The API suppresses expired layers; the browser additionally requires matching snapshot versions and does not combine layers from different time windows. Both controls were browser-verified separately from the recorded layer. The live collectors and 90-minute buffer continue independently of the finished comparison process.

Reports: `data/reconstruction/word-v1-collection/evaluation-001/report.json`. Runner: `deepctm.collect_reconstruction_study`. Publisher: `deepctm.reconstruction_layers --watch`. Read-only API: `/api/florida-reconstruction`. Software verification: 76 modeling tests and two new response/expiry tests passed. Full Newell/CTM integration and broader field validation remain unfinished.

## Frozen later-period check — morning of 21 November

The original selected model and training-only physical bounds were frozen. A later, nonoverlapping morning window was evaluated at the original test areas (Palm Springs and Boston). Case selection used a deterministic metadata hash, at most twenty cases per site/direction/gap stratum, before evaluating errors. Of 320 sampled masks, 316 were accepted by the kinematic model and scored on common support across methods.

| Method | Mean per-gap position MAE | Speed MAE | Stop-duration error |
| --- | --- | --- | --- |
| Linear | 2.653 m | 0.720 m/s | 2.152 s |
| Hermite | 1.864 m | 0.588 m/s | 1.255 s |
| Frozen kinematic refinement | 0.769 m | 0.404 m/s | 0.878 s |

The frozen model had zero tested speed/acceleration violations. Moving-gap position MAE was 0.950 m (5 s, n=53), 1.507 m (10 s, n=29), 3.287 m (20 s, n=28), and 2.010 m (30 s, n=12). Stationary gaps lower the overall average. The original nominal 90% error-band radius covered only 84.18% of later full gaps: coverage degraded under the changed traffic distribution. Do not silently expand the band using these test errors or call it calibrated.

Report: `data/reconstruction/word-v1-collection/later-evaluation.json`. Reproduce with `deepctm.evaluate_reconstruction_later`, supplying the frozen study and a later snapshot. This is a later-time same-corridor check, not independent-day validation or evidence of cross-sensor vehicle identity. No model was refitted or selected using these later scores. The figure's method-comparison panel now exposes this later result and the uncertainty shortfall.
