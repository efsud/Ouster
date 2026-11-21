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
