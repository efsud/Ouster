# Florida reconstruction implementation from the supplied recommendations

Source: `Florida_Corridor_Trajectory_Reconstruction_Recommendations.docx`, supplied 20 November 2026. The entire document text was reviewed, including its M1–M4 comparison, holdout requirements, assumptions and references. Its four-stage integration is a project recommendation, not a single published algorithm. It prioritizes interpretable physical models before neural models.

## Requirements and current evidence

| Requirement | Implementation/evidence | Remaining work |
| --- | --- | --- |
| Passenger cars; fixed movement paths | Study restricts SDK class 2; existing direction/entry/exit metadata | Verify lane groups, projection and signal mapping |
| Associate upstream/downstream tracklets | Movement eligibility and partial global assignment with edge-exclusion alternatives | Independent cross-sensor identity validation; calibrated uncertainty |
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


## Global association comparison — 21 November

`global_association.py` adds a partial min-cost assignment. Each departure and arrival can remain unmatched at a declared cost; physically infeasible or class-inconsistent pairs are removed before solving. Disconnected candidate groups are solved separately. For each proposed match, the solver forbids that edge and resolves the entire group. The increase in total cost measures ambiguity against a competing assignment, including unmatched alternatives. Ties remain unassigned. This margin is not a probability, and no global FIFO or lane equality is assumed.

Worked example: costs A→X=0.1, A→Y=0.2, B→X=0.2 and B→Y=1.4. Greedy selection costs 1.5; joint assignment chooses A→Y and B→X for 0.4. Removing either chosen edge raises the optimum by 1.1. This illustrates the optimization only; real identity still requires validation.

`study_association.py` used the frozen spatial and chronological partitions, passenger cars only, one hash-selected 20/50/100 m strip per fragment, and shuffled arrival order. Hidden identities are available only to the scorer. There were 3,576 training-area candidates (reserved, not fitted), 275 validation cases and 333 test cases. Parameters were fixed except for an ambiguity-margin choice from 0.25, 0.5 and 1.0. Validation selected 0.25 using a minimum 95% precision and 25 matches in each scenario, then maximum worst-scenario recall. Selection was saved before test scoring.

| Held-out scenario | Current conservative matcher | Global assignment |
| --- | --- | --- |
| All endpoints | 224/333 correct recovered (67.3%); 0 wrong; 100% precision | 261/333 (78.4%); 4 wrong; 98.5% precision |
| Missing departures and arrivals | 145/210 (69.0%); 1 wrong; 99.3% precision | 162/210 (77.1%); 6 wrong; 96.4% precision |

More recovered trajectories came at the cost of more false connections. The deployed between-intersection layer therefore retains the conservative matcher. Results are visible in the figure's comparison panel. These are same-sensor masked-identity experiments, not proof of identity across separate sensors. Scenarios reuse fragments, and sensor track IDs themselves are not independently annotated truth. Report: `data/reconstruction/word-v1-collection/association-20261121.json`. Five new matcher tests cover joint alternatives, ties, rejection, unequal group sizes, reorder invariance, class and physical gates. In total 36 targeted reconstruction, association and response tests passed; JavaScript syntax passed.

Saved AM/PM archive manifests were also audited: 13 November 07:00–09:00 Florida time reports 499,139 frames across seven sensors, and 16:00–18:00 reports 496,126. The earlier nighttime attempt reports no reception. These are worker-reported counts, not an independent recount. The archives are preserved as potential independent-date evaluation sources; this comparison did not score them. Audit: `data/reconstruction/word-v1-collection/archive-audit.json`.

Full M2–M4 integration remains incomplete: the rolling schema does not yet supply supported same-lane leader relationships, calibrated queue fields or verified signal permissions. These priors must not be invented merely to label the deployed kinematic estimator as the complete recommended method.


## Missing-match correction — feasible candidates first

The original matcher allowed motion-infeasible curves to compete in its ambiguity margin before rejecting those curves. A new `feasible` mode removes impossible candidates first, then performs one mutual-best round with unchanged cost/margin limits. It keeps all feasible competitors visible and does not cascade earlier identity hypotheses. The reconstruction publisher now uses this mode; signal, movement and physical gates remain in place.

Re-running the saved benchmark recovered 233/333 true matches versus 224/333, both with zero false matches. With missing departures/arrivals, it recovered 152/210 versus 145/210, both with one false match. Validation-area correct counts increased from 178 to 181 and from 118 to 121, with unchanged false counts. This reuses the prior benchmark and is a regression comparison, not a fresh independent test. Cross-sensor identities remain unverified. The broader global assignment remains experimental. Report: `data/reconstruction/word-v1-collection/association-feasible-20261121.json`.

The layer response now includes per-link candidate and rejection diagnostics so missing connections can be distinguished from movement exclusions, insufficient endpoint support and coverage-edge exclusions. Thirty-seven targeted tests pass, including a new check that impossible competitors cannot block a feasible match and that this mode never performs recursive residual assignment.

## Local-layer empty-toggle repair — 22 November

The user's before/after screenshots correctly showed zero local estimates. Two pipeline mismatches were identified: the plot suppresses intervals over 1.5 s, but the local publisher searched only gaps over 3 s between separate fragments; and long-gap admission depended on the old Hermite estimator succeeding first. The local publisher now handles 1.5–3 s holes inside collector-validated tracks, with five-point context on each side and the same bounded kinematic solver. Long-gap candidates now carry separate same-chain clock, lateral-displacement and endpoint-motion evidence from the raw rolling builder. They no longer need an accepted old Hermite path. No change-ID or cross-intersection association is introduced by this fix.

The latest checked real hour produced five short local estimates (two eastbound, three westbound); 23 short gaps lacked sufficient continuous boundary context. This does not fill every circled discontinuity, and the historical screenshot's expired raw window cannot be independently reconstructed. Larger gaps and object-ID changes require further association work. Local prediction uncertainty from the original 5–30 s masked study is not a newly validated error guarantee for these short gaps. Thirty-nine targeted tests pass, including an internal two-second plotting-hole regression and clock/lateral rejection checks. Both derived workers were reloaded; live sensor ingestion was not restarted.

## Automatic local estimation and changed-ID experiment — 22 November

The within-intersection reconstruction layer is now checked by default. The existing background publisher automatically regenerates supported estimates for each rolling-hour snapshot. This is retrospective reconstruction using observations before and after a gap, not an online causal forecast.

A separate same-site changed-ID matcher was implemented in `local_tracklet_matching.py`. It uses same session/class/through movement, lateral separation ≤1.25 m, compatible sensor/receipt clocks, a 1.5–30 s gap, physical motion, partial global assignment and competing-endpoint margins. Existing local endpoints cannot be reused. Such associations are explicitly unverified. Rolling track metadata now includes visible lateral endpoints and sensor timestamps for this experiment.

A 5/10 s masked-ID proxy at the original test sites yielded 204 eligible cases, 72 matches, 67 correct and five wrong (93.1% precision; 32.8% recall). This does not justify automatic deployment. `generate(..., experimental_changed_ids=False)` leaves this extension disabled by default; the background publisher never enables it. No threshold was retuned on these test errors. The proxy uses receipt-aligned clocks and visible original lateral endpoints, so it does not establish real ID-change or lane-change accuracy. Report: `data/reconstruction/word-v1-collection/local-tracklet-validation.json`; reproduction module: `deepctm.validate_local_tracklets`.

Forty model tests passed, including new wrong-movement, lateral, clock/session, competing-candidate and endpoint-reuse checks. A fully continuous vehicle plot cannot be promised from incomplete observations without replacing unknown identities with a separate hypothetical simulation. The deployed layer remains model-estimated supported gaps rather than invented observations.

## Same-ID classification changes and smooth joins — 22 November

User requested that a vehicle's classification change not prevent a local connection. `same_id_gaps.py` groups by sensor (outer scope), session and object ID, ignoring differences between vehicle class codes. It considers adjacent, nonoverlapping fragments only; session/ID, direction, compatible known movement, sensor/receipt timing, ≤2 m lateral displacement, continuous boundary context and physical feasibility remain mandatory. Different IDs remain excluded from the automatic layer. Observed fragment classes and both endpoint labels are preserved rather than overwritten.

The rolling collector flushes the prior class fragment on a Florida classification transition, avoiding artificial overlap between class-specific tracks. Accepted same-ID class-change gaps carry the object ID and endpoint classifications for inspection. All local kinematic estimates now use exact endpoint positions and endpoint longitudinal velocities; their piecewise-constant acceleration representation has continuous position/velocity, but does not promise continuous acceleration. An infeasible smooth join is rejected. This changes the boundary constraints relative to the earlier frozen benchmark; earlier aggregate error statistics are not new accuracy measurements of this exact-join variant.

The checked hour published 100 local estimates: 69 short internal gaps, 29 same-class fragment gaps and two classification-change joins. Counts vary each update. Forty-six targeted tests passed, including cross-session/different-ID rejection, movement/lateral/clock rejection and exact position/tangent joins in both travel directions. JavaScript syntax and browser default-on state were checked. Live API ingestion was not restarted; only derived workers were reloaded.

## Recording-interruption evidence and inter-site endpoint closure

The recommendations were reviewed again for the user's two requested layers. Rolling snapshots now record site-level intervals without received frames. Same-site/session/ID fragments can be considered up to 120 s apart when at least 80% of the gap is independently covered by missing-frame intervals. Gaps over 30 s without that evidence are rejected. A missing-frame interval indicates absence in this sampled recorder, not a proven cause such as network disconnection. Reconnects with a different session are not linked by numeric ID alone. Clock ratio, lateral continuity, direction, known movement compatibility and bounded kinematics remain required. Duplicate local endpoint intervals are suppressed.

Between-intersection candidates now use exact position and endpoint-speed constraints in the kinematic solver, like local curves. Accepted curves meet both measured boundary positions and slopes; an infeasible join remains omitted. This does not remove uncertainty in the association or reconstruct a uniquely determined stop history. Full CTM/signal/Newell priors remain incomplete.

Forty-nine targeted tests passed, including long-gap rejection without missing-frame evidence, short and long recording gaps, and rejection across recording sessions. The latest fixed-parameter spatial/time holdout contained only three eligible accepted 5 s masks (mean position MAE 0.396 m; no tested physical violation) and one rejected 30 s mask. This is insufficient evidence for long-gap accuracy. No threshold was tuned on those outcomes. Report: `data/reconstruction/word-v1-collection/exact-join-outage-validation.json`. The rolling collectors were refreshed without restarting live ingestion. Raw retention stays at 90 minutes.

## Integrated CTM–Newell–signal experiment — 22 November

`integrated_reconstruction.py` now composes estimated Newell leader translation, a twelve-cell CTM scenario and constrained trajectory refinement. Same-session, same-direction nearby car tracks with compatible visible lateral endpoints supply candidate leaders; ambiguous leaders are rejected. The target's entire ID is excluded from every prior. A one-second Newell lag and observed upstream spacing are provisional assumptions, not fitted driver parameters. The model can blend that candidate with Hermite and refine the result under exact endpoint position/speed constraints.

CTM cells are 20 m, covering ±120 m of the provisional intersection reference. Nominal backward wave speed is 5 m/s and jam density is 0.2 veh/m for the approximate lane group; free-flow speed comes from the earlier training-only calibration. Initial counts use visible observations at or before the gap. Upstream entry rates use preceding observations. Unobserved side-street demand and external entry reservoirs are not estimated by this restricted scenario. CTM speed ±5 m/s gives a soft envelope. Estimated phase capacity factors may reduce internal flow at the assumed zero-position stop line, but they are not verified permissions and do not impose a hard red-crossing constraint on individual trajectories. Internal CTM mass conservation remains tested.

`validate_integration.py` compares current, Newell-only, CTM-without-signals, CTM-with-estimated-signals and integrated models. Original disjoint sites/time partitions remain; at most twelve metadata-hash-selected masks per site/direction/scenario. Signal movement mappings are learned from only the first 60% of each site's period; approximate lateral interpolation is explicitly disclosed. Reconstruction parameters are fixed, with no selection or retuning on test errors. Local masks remove the target; outage masks remove all objects and signal inputs during the interval; spatial bands remove all vehicle observations within 20/50 m strips. These known-endpoint spatial masks do not validate inter-sensor association or unobserved road paths.

| Common held-out masks | n | Current position MAE | Integrated MAE | Exploratory 95% interval for improvement |
| --- | --- | --- | --- | --- |
| Local object gaps | 20 | 0.6860 m | 0.6769 m | -0.0009 to 0.0217 m |
| All-object outages | 20 | 0.6860 m | 0.6764 m | -0.0002 to 0.0226 m |
| Spatial blind bands | 22 | 0.8201 m | 0.8170 m | -0.0026 to 0.0119 m |

The current local model accepted 21/39 eligible cases, the integrated model 20/39; common-case metrics exclude rejected cases and must not be read as complete coverage. Spatial variants accepted 22/25. Only one common local case supplied an estimated leader. Eight local and twelve spatial cases supplied estimated signals, but none supplied all three priors together. Signal/no-signal ablations had effectively identical errors here. Therefore these results do not demonstrate full CTM–Newell–signal benefit; small improvements are mostly attributable to the nominal CTM soft prior. All exploratory bootstrap intervals include zero, and neither validation-area outage nor spatial performance consistently improved. No deployment switch was made.

Report: `data/reconstruction/word-v1-collection/integrated-validation.json`. Figure: `integrated-comparison.png` in the same folder, reproducible using `scripts/plot_integrated_validation.py`. The dashboard comparison panel exposes common counts, errors and uncertainty. Fifty-three targeted tests pass, including target exclusion, all-object masking, estimated internal capacity conservation and explicit missing-prior handling. This is an implemented experimental integration with partial field inputs, not a field-validated complete model. Next evidence priorities are sustained same-lane leaders, independently verified movement/phase/stop-line geometry, calibrated queue parameters and independent-day AM/PM evaluations.
