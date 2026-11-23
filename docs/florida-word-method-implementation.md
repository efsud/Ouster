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

## Additional archival experiment: longer gaps and association

The new `deepctm.archive_snapshot` reader preserves the raw archives and never writes to the live buffer. It samples the first hour of each November 13 AM/PM archive at approximately half-second intervals, using the existing provisional road calibration and movement extraction. The AM hour contains 250,328 scanned records, 46,514 sampled frames and 26,614 displayed fragments; PM contains 251,345 scanned records, 46,419 sampled frames and 32,901 fragments. Fragment counts are not unique vehicle counts.

`deepctm.archive_extension` trains an empirical shape prior from AM 07:00–07:30, chooses its weight using complete fragments after 07:31, and freezes that choice before scoring PM 16:00–17:00 (Florida local time). It hides 10/30/60/90 seconds and evaluates only gaps with continuous recorded truth. Training identities are excluded from the local validation sample. Several gap lengths may reuse a track, so mask counts are not independent vehicles.

The prior learns normalized deviations from the endpoint Hermite curve, conditioned on visible endpoint speed, average speed, gap duration and location relative to the intersection. Five nearby training examples supply an optional soft reference; distant cases fall back to the original reference. Both endpoints still have exact position/speed constraints, with the previously frozen physical bounds. Example: a 60-second hidden interval with a visible queue departure can borrow a supported stopping/starting shape, but never the hidden test observations. This is an empirical reference for constrained reconstruction, not a newly trained DeepCTM neural network.

The association candidate calibrates expected travel time on training pairs, then selects an ambiguity margin on validation only. Selection requires at least 98% validation precision and no more wrong matches than the existing matcher in either complete or dropout scenarios. Original object IDs are retained only as scoring labels and never passed to the matcher. Reversed arrival order and deliberate missing arrivals/departures prevent order-based matching shortcuts. Same-sensor 20/50/100 m masks are proxies; they cannot validate identity across the actual sensors.

Archived signal events are not treated as verified state replay. The integrated comparator has CTM and available estimated leader context, without signal evidence. The deployed model is unchanged. Actual adjacent-sensor hypothesis counts are saved separately from measured matching accuracy.

Reproduction:

```sh
.venv-deepctm/bin/python -m deepctm.archive_snapshot --capture data/sr436/20261113T115900Z-89fb0f --output data/reconstruction/archive-extension/am
.venv-deepctm/bin/python -m deepctm.archive_snapshot --capture data/sr436/20261113T205900Z-7f94bd --output data/reconstruction/archive-extension/pm
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 .venv-deepctm/bin/python -m deepctm.archive_extension --am data/reconstruction/archive-extension/am/snapshot.json --pm data/reconstruction/archive-extension/pm/snapshot.json --study data/reconstruction/word-v1-collection/evaluation-001/report.json --output data/reconstruction/archive-extension/evaluation
.venv-deepctm/bin/python scripts/plot_archive_extension.py
PYTHONPATH=. .venv-deepctm/bin/python scripts/audit_archive_links.py
```

### Completed archival results

The shape prior used 1,248 training templates. On morning validation its common-case MAE improved from 1.691 m to 1.594 m (weight 0.25) and 1.540 m (weight 0.5), but accepted cases decreased from 69 to 68 and 64 out of 159. It therefore failed the predeclared coverage rule and was not selected for deployment or afternoon selection.

On the frozen afternoon test, current refinement accepted 66/168 cases and the CTM/available-leader comparator 67/168. Their 65 common cases had position MAE 1.812 versus 1.807 m. The exploratory paired 95% improvement interval is −0.101 to +0.110 m; there is no reliable overall gain. At 30/60/90 seconds, common-case MAE was 2.961→2.955 m (13 cases), 2.670→2.613 m (12), and 1.140→1.139 m (13). These are different accepted cohorts; the lower 90-second error does not mean long gaps are easier. Stop-duration error rose overall from 2.505 to 2.554 seconds.

An admission audit found negative endpoint slopes in 84 of 168 attempted masks, although mask creation permits slopes down to −0.5 m/s. Exact endpoint speeds conflict with the nonnegative downstream-speed constraint. These can include stopped-object jitter or genuine small reversals; they were **not** silently clamped to improve test coverage. A noise-aware endpoint model needs validation on another untouched period.

The travel-time-calibrated matcher selected margin 0.25 using morning validation. Afternoon identity-blind results:

| Scenario | Existing correct / eligible | Calibrated correct / eligible | Existing wrong | Calibrated wrong |
|---|---:|---:|---:|---:|
| Complete endpoints | 6,895 / 10,215 | 6,968 / 10,215 | 93 | 87 |
| Missing departures and arrivals | 4,337 / 6,182 | 4,373 / 6,182 | 150 | 141 |

This is a modest proxy matching improvement, not a field-verified cross-sensor identity claim. The dropout precision remains 96.88%, below the 98% validation target when transferred to afternoon data; no production promotion was made. Raw recordings are preserved. Reports, plots and actual-link counts reside in `data/reconstruction/archive-extension/evaluation/`; model code and explanation are versioned, private recordings are not committed.

On the actual seven-sensor PM corridor, the existing matcher proposed 2,200 connections and the calibrated candidate 2,172. These are **unverified hypotheses**, not correct-match counts. The smaller number is consistent with changed ambiguity/cost decisions and does not establish better or worse real identity accuracy. This is why the proxy improvement alone did not change the live layers. The added matching callback defaults to the existing behavior and is used only by the audit script.

Software verification: 38 targeted tests passed, including exact endpoint joins, zero-weight equivalence to the current estimator, identity/order-blind association, ambiguous duplicate rejection, prior availability, spatial matching and dashboard response behavior. Browser verification confirmed the completed archive table on the Florida figures page.

## Endpoint-speed correction and untouched-hour validation

The strict model can reject a gap when a noisy median derivative is slightly negative, even though the visible object is nearly stationary. The new `endpoint_speed` module keeps successful strict estimates unchanged. Only after strict failure does it examine five **visible** endpoint samples. A small negative derivative can become an estimated zero-speed endpoint only when position span is small, absolute context trend is at most 0.05 m/s, and maximum step speed is at most 0.5 m/s. Sustained reverse motion, missing evidence and large negative derivatives remain rejected. The original observed points and speeds are never edited; inferred gap positions still meet both recorded endpoints exactly. Each correction carries its original derivative and visible-context evidence.

A separate numerical fix ensures optimizer speed bounds always use floating point. Integer `vmax` values previously caused `numpy.full` to create integer arrays, silently truncating small negative endpoint bounds to zero. Earlier field benchmarks used floating-point limits and were unaffected; regression tests now cover integer limits explicitly.

Selection compares 0.1/0.25/0.5 m/s negative-speed limits paired with 0.1/0.25/0.5 m position spans. Morning validation is restricted to whole fragments after 07:31, excluding training identities. The selection rule maximizes acceptance without losing a strict success, and requires at least ten new cases with mean position error ≤3 m, mean speed error ≤1 m/s and 95th-percentile case position error ≤10 m. Selection is written to `selection.json` before test scoring.

The untouched period is the second hour of the preserved PM archive, **November 13, 17:00–18:00 Florida time**. IDs appearing anywhere in the previously scored 16:00–17:00 snapshot are excluded, with a balanced sample over seven sites, both directions and 10/30/60/90-second masks. This is an unused period of the same day, not an independent-day validation. New accepted gaps are scored separately; averaging them with the older, easier accepted cohort would obscure the coverage/accuracy trade-off.

Production plumbing is opt-in through a versioned policy file. It applies only within the same intersection, to car endpoints and gaps no longer than 90 seconds. Other class transitions retain their previous behavior. Cross-sensor matching is unchanged. Prior uncertainty bands do not apply to the newly admitted cases. Promotion requires the untouched test to meet the same error thresholds, at least 20 newly accepted cases, no lost strict cases and no physical violations; otherwise the policy remains disabled.

Reproduction uses `deepctm.archive_snapshot --offset-seconds 3600` for the new hour, then `deepctm.validate_endpoint_speed`. Per-case failures, corrections and metrics are retained in `data/reconstruction/endpoint-speed/evaluation/`; figures use `scripts/plot_endpoint_validation.py`.

### Untouched-hour result and bounded rollout

The selected 0.1 m/s / 0.1 m policy passed the predeclared test criteria. The test snapshot contained 46,311 sampled frames and 32,069 trajectory fragments. Excluding IDs seen in the preceding hour removed 143 eligible masks before balanced sampling. Of 270 tested masks, strict refinement accepted 119 (44.1%); correction accepted 188 (69.6%). All 119 prior successes and their errors remained identical. The 69 added gaps had mean position error 1.533 m, speed error 0.249 m/s, stop-duration error 3.447 seconds, and 95th-percentile per-gap position MAE 9.418 m. There were no tested physical violations.

| Hidden duration | Strict accepted | Corrected accepted | Attempted | Added-gap mean position error |
|---|---:|---:|---:|---:|
| 10 s | 48 | 62 | 70 | 0.116 m |
| 30 s | 23 | 43 | 70 | 1.959 m |
| 60 s | 22 | 41 | 65 | 1.144 m |
| 90 s | 26 | 42 | 65 | 2.703 m |

The overall test criterion passed, but tail errors remain: newly admitted 90-second gaps have 13.458 m 95th-percentile case error and 8.98 s mean stop-duration error. More coverage is not a promise that every inferred shape is accurate. The remaining 82 rejected masks include 37 endpoint-bound conflicts and 45 optimization failures. Recorded observations are preserved, and the new curves remain dashed estimates. This is a coverage improvement with separately measured new-case error, not an accuracy improvement on the unchanged old cases.

The versioned `config/reconstruction/florida-endpoint-speed.json` records the frozen parameters and validation-report hash. The policy is enabled only for the scope above; the broader 0.25/0.5 candidates and between-intersection matching were not enabled. Full CTM–Newell–signal field validation remains outstanding.

Rollout verification: 64 targeted software tests passed, including opt-in behavior, preserved westbound direction, visible-context checks, exact positional joins and an end-to-end dashed-layer test that leaves observations and cross-sensor output unchanged. The Florida derived workers and combined dashboard were restarted without stopping the sensor collectors. Browser verification showed the active policy and the 119→188 test comparison. The then-current rolling window had zero qualifying corrected gaps; no artificial gaps or extra connections were inserted merely to demonstrate the feature.

## Boston–Palm and all six Florida pairs: final-physics consistency

The same-window audit now reports all six adjacent pairs in both directions. The prior matcher admitted a monotone curve using a 35 m/s ceiling, whereas final refinement uses the frozen 24.5174 m/s ceiling and exact endpoint speeds. A candidate could therefore win identity competition and only then fail final reconstruction. The new `matching_physics` gate computes the minimum/maximum reachable distance on the same half-second integration grid, using both endpoint speeds, frozen speed limits and acceleration bounds. It filters impossible candidates **before** ambiguity comparison. Cost threshold 1.5, ambiguity margin 0.25, one mutual-best round, movement/coverage gates and final optimization are unchanged.

A reused archival matching regression (explicitly not a new untouched holdout) evaluated all seven sites, both directions and 20/50/100 m masks. Complete endpoints: both pipelines recovered 905 correct and 5 false associations from 1,129 eligible pairs. Missing endpoints: both recovered 546 correct and 4 false from 670 eligible pairs. These masks cannot verify identities across actual sensors.

On a frozen current window, final displayed hypotheses increased from 327 to 331, preserving every previously accepted connection. Palm Springs→Boston eastbound increased 135→138; Plaza→Essex westbound increased 51→52. The other ten directed pair counts were unchanged, including Boston→Palm westbound at 6. The four added paths are estimated associations, not confirmed identities. The frozen policy is `config/reconstruction/florida-association.json`.

The site-by-site endpoint audit also found that the corridor mean obscured Hattaway's 5.93 m mean error on newly admitted cases. The endpoint correction is now withheld there pending independent validation; strict estimation remains active. This is a post-hoc safety restriction, not a newly validated site model. All seven original per-site test results remain visible. Other new-case means were Cranes Roost 0.12 m, Renaissance 0.18 m, Essex 0.37 m, Plaza 1.99 m, Palm Springs 0.98 m, Boston 0.23 m.

The dashboard exposes each pair's departure/arrival fragments, displayed connections and final motion rejections. Counts of unmatched fragments are not counts of unique missing vehicles. The between-intersection layer must be enabled separately; it is never confused with within-intersection gap filling. Reports, frozen comparison snapshot and plot are stored in `data/reconstruction/all-florida/`.

Rollout checks: 69 targeted tests passed. The estimate worker and dashboard were refreshed without stopping collection. Browser verification showed all 12 directed pair rows, Hattaway's withheld status, and 191 eastbound estimated connections with the between-intersection layer enabled (331 across both directions). The `?between=1` figures link opens that layer explicitly; its dashed paths remain labeled estimated.


## November 22–23: Finch support and bounded prospective evaluation

User policy: keep unresolved gaps blank; show evidence-supported estimates only.
No simulated continuation layer and no guarantee of zero disconnected trajectories.

Finch now uses the shared within-intersection estimator, class-independent session/
object continuity checks, and two separate dashed layers. Its rolling pipeline
classifies observed 2D movement before linking corridor endpoints. Jane currently
has no frames and remains unavailable. No connection skips across a missing site.
The Finch matcher explicitly allows longer distances, bounded by its training-derived
speed limit and the existing 120-second limit; time, movement, ambiguity, and final
physical constraints still apply. Florida retains its 350 m default.

For example, a unique 600 m connection at 15 m/s over 40 s is admitted for Finch;
the same displacement in 5 s is rejected. Duplicate equally plausible endpoints
remain unresolved. This is a hypothesis of identity, not identification of a car
across sensors.

The bounded campaign lives in `deepctm/corridor_campaign.py`. Its stop deadline is
2026-11-23 12:22:17 UTC (07:22:17 Toronto), eight hours after the requested session
started. It evaluates existing rolling snapshots every half hour, saves metrics
and frozen models, and preserves the 90-minute raw buffer retention. It is an
existing-code experiment worker, not eight hours of autonomous code editing.
Models and completed reports survive worker restart. Known training/validation
IDs (ignoring class changes) are excluded from test masks. Multiple lengths from
one vehicle are correlated cases, not independent vehicles. Test results cannot
automatically promote a new method or change the model.

First fresh masked-gap results (10, 30, 60, 90 s where observations permit):

| Corridor | Eligible masks | Strict accepted | Correction candidate accepted | Added-case position MAE |
|---|---:|---:|---:|---:|
| Florida | 71 | 40 | 50 | 0.073 m (10 cases) |
| Finch | 112 | 53 | 79 | 0.189 m (26 cases) |

The common cases are unchanged. Finch's correction candidate passed pooled
validation but each site has fewer than ten newly accepted validation cases;
therefore correction is withheld at every Finch site for now. The strict local
estimator is deployed. Florida's previously excluded Hattaway correction stays
excluded. These candidate acceptance counts are not deployed connection counts.

A new experimental global partial assignment uses explicit unmatched alternatives
and an optimal-assignment cost margin. It is **not deployed**. On the first already
scored spatial-mask window, Florida was unchanged (137 correct/3 false), while
Finch improved from 104 correct/2 false to 105 correct/2 false. Eligible counts were
183 and 146 respectively, with deliberately missing endpoints. This is exploratory
reuse of a test window; later campaign windows provide prospective comparisons.
Local spatial masks do not validate true cross-sensor identities or unknown clock
offsets. No verified signal permission or lane leader is invented.

Initial Finch layer publication contains 18 within-intersection estimates and 142
cross-intersection hypotheses across both directions. Counts change with each
recorded window. The UI displays counts after selection and direction filtering.

Validation: 74 existing/new targeted tests passed before the additional global
assignment tests; all four global assignment tests passed. These cover longer
Finch links, impossible travel, ambiguous duplicates, unmatched endpoints, class-
independent identity exclusion, and deadline behavior. Browser verification showed
both Finch layer controls enabled and 12 local/82 between-site eastbound estimates.
The eight-hour campaign is still running; its final report is not yet available.


## Continued active investigation: projection and same-ID gaps

Two concrete causes of disconnected lines were found and corrected:

1. The rolling projection used the bearing of the chord between adjacent sensors.
   At Martin Grove this was about 67 degrees from east, while cached named-road
   geometry gives a local Finch tangent around 17 degrees. At Albion the chord
   was 43 degrees versus a local tangent around 70 degrees. The straight chord
   is inappropriate on this bend. A same-frame comparison recovered 417 classified
   Martin Grove fragments (261 through fragments) where the chord classified none.
   `config/reconstruction/corridor-road-axes.json` applies a provisional local
   tangent to these two Finch sites only. Live-map LiDAR rotation is unchanged.
   Projection version is stored in snapshots and prospective test reports.
2. Same-ID fallback recovery skipped ordinary short fragment breaks when the class
   stayed unchanged; it handled only class changes or full-frame outages. The
   new optional recovery admits short stable-class breaks with the same sensor,
   session, ID, SDK/receipt clock agreement, direction, lateral displacement and
   exact endpoint physics gates. Gaps over 30 seconds still require an independently
   observed recording outage. Intervening nonvehicle observations block a bridge.

A separate bug deduplicated outage gaps by timestamps without checking the object.
Several objects lost in the same frame outage share timestamps, so their estimates
could be suppressed. Deduplication now includes sensor/session/object identity.
A regression fixture with two objects sharing one outage retains both estimates.

Recorded-data masking check for the new short-gap admission (10 and 30 seconds):

| Corridor | Eligible | Pass identity/clock/lateral admission | Reconstructed | Position MAE | Case-MAE 95th percentile |
|---|---:|---:|---:|---:|---:|
| Florida | 102 | 66 | 45 | 1.48 m | 8.95 m |
| Finch | 144 | 85 | 38 | 1.15 m | 3.91 m |

Actual raw API timestamps and lateral positions at both visible endpoints were
recovered from the retained rolling buffer. No raw endpoint evidence was missing.
Only recorded interior positions were hidden. A stricter replay derives each flank’s direction from visible points and removes the full-track movement label; these are the final numbers above (the initial scaffold check reported 48 and 47 accepted). The strict estimator was tested;
this does not establish cross-sensor identity, sensor timezone or surveyed geometry.
The sample uses several lengths from some vehicles. Frozen calibration remains in
use; `validate_same_class.py` does not train or select thresholds on these masks.
Configuration stores validation hashes and limitations without storing raw data.

A broader named-road ROI experiment remains **undeployed**: local road tangent
alone can remove a carriageway from the old fixed +/-18 m strip, while substituting
a map-based road-width buffer also removed observations at some Florida sites.
These results require further scene/ROI work, not blanket widening. Connected-road
versus chord distances are audited separately and not substituted automatically.
Unresolved identity, motion or clock cases remain blank.

Validation: 76 targeted tests passed after the same-ID/outage fixes, including
existing movement, reconstruction, clock, ambiguity and endpoint checks.

## Additional experiments during the eight-hour session

These experiments are separate from the published estimate layers. The dashboard
continues to use receipt time, the deployed conservative association policy, and
its existing duration limits.

### Sensor elapsed time

A fixed offset per sensor/session can preserve SDK timestamp differences while
retaining the original collector receipt timestamps. The experimental extractor
rejects clock resets, duplicate/reordered timestamps, short sessions, and excessive
clock-rate drift. It does not establish the SDK timezone or synchronization between
sensors. Receipt-timed phase events are excluded from this experimental view.
Only observations inside the selected display window are retained for plotting.

A raw-endpoint masked replay reconstructed 35/98 Florida cases (2.26 m MAE) and
39/144 Finch cases (1.52 m MAE). No raw endpoints were missing. These samples are
not identical to the earlier receipt-time cases; they do **not** establish an
accuracy improvement. A lower discrepancy between chart slopes and SDK-time-derived
speeds is an internal consistency check, not independent ground truth. This time
basis remains experimental and is not enabled in the rolling dashboard.

### Object dimensions as soft association evidence

The extractor now retains reported width/length alongside each observation, with
robust summaries from visible endpoint samples only. A size discrepancy is a soft
penalty, never an identity fingerprint. Missing dimensions remain competitors and
cannot gain a new match solely because other candidates received size penalties.
A first-half validation selected weight 0.5; the second half was evaluated after
an embargo and exclusion of earlier object IDs. On these correlated spatial-mask
scenarios, compared with the same global assignment without dimensions:

| Corridor | Baseline correct / false | Shape-assisted correct / false |
|---|---:|---:|
| Florida | 699 / 3 | 702 / 3 |
| Finch | 468 / 3 | 468 / 2 |

These are same-sensor masked-band tests, not verified cross-sensor identities.
Cross-sensor size bias remains unknown. Weight 0.5 is frozen for prospective
comparisons with both deployed mutual-best and global assignment. The selection
used an experimental sensor-elapsed snapshot; future receipt-time tests explicitly
check transfer to the production time basis. No automatic promotion is permitted.

### Longer duration and numerical solver experiments

An optional 120–300 second constrained bridge was tested without changing the
production 120-second limit. Only two eligible long-gap cases per corridor were
available; one was accepted in each. The Finch accepted case had 12.36 m MAE.
This is insufficient evidence to widen the deployed duration or identity gates.

A separate numerical experiment constructs a feasible initial velocity curve as
a convex combination of the endpoint-constrained minimum/maximum velocity envelopes.
Its trapezoidal integral equals the observed displacement, with unchanged speed
and acceleration limits. Optional scene ceilings must also hold before using it.
An optional larger solver iteration budget is being evaluated separately. Neither
option changes default published behavior. Synthetic feasibility tests are kept
separate from recorded-position masking results.

### Follow-up solver and local context results

Increasing the strict solver budget from 150 to 600 iterations recovered 27
Florida and 60 Finch development masks, without changing physical bounds. Their
mean position errors were 7.16 m and 9.18 m, respectively; the 95th percentiles of
case MAE were 18.64 m and 27.13 m. Numerical convergence alone is therefore not
adequate evidence to publish these extra paths. Feasible initialization alone
recovered no additional cases at the original iteration budget.

Two further soft-prior experiments were kept separate from production:

- Partial Newell following uses only the observed portion of an unambiguous nearby
  leader and never extrapolates it. On the recovered cases, one Florida case had
  support and became worse (1.14 m to 10.06 m MAE); Finch had no supported cases.
- An observed-flow envelope requires at least two distinct nearby other objects
  with consistent simultaneous speeds. Target identity fragments are excluded.
  It supported one Florida case with essentially unchanged error and none in Finch.
  Full-outage tests remove interior observations of all objects and cannot create
  a fictitious velocity field. These tests do not justify deployment.

### Same-ID lateral motion experiment

The original two-metre lateral-displacement gate rejects some plausible lane
changes or curved-road motion. An experimental gate uses visible lateral endpoint
contexts to construct a bounded cubic curve: displacement at most 7.2 m, lateral
speed at most 2 m/s, lateral acceleration at most 1.5 m/s², combined acceleration
at most 4 m/s², and the existing +/-18 m road strip. It retains same-site/session/ID,
clock, movement and longitudinal checks. This is estimated lateral motion, not a
verified lane change or permission to connect different identities.

Raw two-dimensional development masking produced 2 accepted Florida cases out of
29 eligible lateral masks (2.35 m longitudinal MAE, 0.35 m lateral MAE) and 36/69
in Finch (4.43 m longitudinal MAE, 0.43 m lateral MAE). Longer Finch masks had large
longitudinal errors despite plausible sideways motion. A ten-second maximum is
therefore frozen for a **new prospective test**, with all IDs seen in the retained
buffers excluded. These development results cannot validate that new selection.
No production lateral gate has been widened.

The first three campaign windows also selected Weston and Kipling as candidates
for the already frozen stationary-noise correction: each had at least ten distinct
fragment ranks across multiple windows and passed the specified error thresholds.
Those earlier windows are reused development evidence for this site-selection
choice. A new timestamp embargo and exclusion of known IDs separate subsequent
prospective checks; no automatic site promotion is enabled.

### Paired clock experiment and projected coverage overlap

A paired clock check hid exactly the same physical observations under receipt and
receipt-anchored sensor-elapsed timelines. Among cases reconstructed in both views,
Florida mean position error changed from 2.80 m to 2.36 m (67 masks), and Finch
from 1.87 m to 1.84 m (135 masks). Exploratory fragment-cluster bootstrap ranges for
mean improvement included zero: -0.07 to 1.21 m in Florida and -0.02 to 0.11 m in
Finch. Availability was conditional on selecting continuous sensor-time tracks.
These results do not verify absolute clock synchronization or justify changing the
published time basis automatically.

A projected coverage audit found Cranes Roost–Hattaway edges overlapping by about
3.3 m eastbound and 16.8 m westbound in the evaluated hour. A positive blind-gap
matcher is inappropriate for many of these endpoints. Projected overlap is not
proof of shared physical sensor coverage or vehicle identity. A separate
`overlap_association.py` experiment compares simultaneous observed positions,
speeds and available dimensions, requires separation from competing assignments,
and fits no clock or position offset. It never treats overlapping observations as
missing road data. Validation uses disjoint, interleaved observations from known
single-sensor tracks; additional position/clock perturbations are explicitly
synthetic robustness checks. No overlap associations are published yet.

### Received-frame journal (2026-11-23)
The rolling recorder previously read only the latest preview frame every 0.5 s.
A 106-second comparison found about 10 received frames/s but only 2 archived
frames/s at most active sites. This is sampling loss, separate from upstream
outages or model errors. `deepctm.frame_journal` now captures every committed
preview update in a 120-second SQLite handoff queue. Rolling workers copy by
sequence, deduplicate by event key, and retain the usual 90-minute raw window.
Existing authenticated collectors do not need restarting. A renewable 90-second
lease stops new journaling if the rolling worker disappears; subsequent preview
updates purge expired handoff rows. An idle database may retain its last queue
until its next update. A worker outage longer than the handoff retention can still
lose data; this does not promise lossless upstream reception.

Tests cover a 50-frame burst overwritten in the preview cache, replay duplication,
lease expiry/retention, and restart-safe copying. The first implementation exposed
SQLite's outer-UPSERT conflict handling; explicit duplicate exclusion fixed it
before installing the live pilot. Pilot measurements are saved in ignored
`data/reconstruction/journal-review/comparison.json`. No upstream settings changed.

A separate unpublished association experiment replaces the legacy cubic-only
precheck with an exact discrete feasible-velocity envelope, while retaining the
same physical limits, assignment costs, ambiguity margins and final refinement.
On the first second-half masked window it increased Florida correct matches
580→629 and false matches 5→3; Finch correct matches 396→427 but false matches
1→2. These are correlated masked scenarios, not verified intersensor identities.
The Finch false-match increase prevents treating this as a universal improvement.
Reproduce with `deepctm.validate_kinematic_gate`; production defaults are unchanged.

Recording cadence also changes endpoint sample counts. Estimators now retain at
least five visible points and expand that context only as needed to cover one
second. The previous five-point behavior is unchanged at 2 Hz. At 10 Hz the
context expands rather than incorrectly rejecting a valid endpoint as too short.
Discontinuous, reversed-time and genuinely short contexts remain unavailable.
Snapshots identify this context version and the recording-mode transition; gains
from fuller observations must not be described as model-accuracy gains.

Full-rate receipt timestamps exposed short arrival-jitter fluctuations that the
existing sensor/receipt-ratio gate correctly refused to interpret as motion.
The journal still retains every received frame; figures now select actual frames
at a stable approximately 0.5-second interval before the established trajectory
checks. No positions or timestamps are synthesized by this sampling step. On a
fixed five-minute comparison Renaissance recovered 25 observed fragments instead
of zero; every available site gained observed track duration. This is a sampling
and extraction result, not an inference-accuracy result. Raw and processed frame
counts and fragment-break reasons remain separate in snapshots.

The new whole-recording-outage validator deletes all sites' frames and phase
samples in fixed 10/30/60-second intervals before rebuilding and estimating.
It separately counts vehicles wholly concealed by an outage: those lack endpoint
evidence and cannot legitimately be recovered by drawing connecting lines. An
experimental stationary-context option retains measured near-stationary fragments
only with nearby, nonconflicting same-ID direction evidence. It is disabled by
default and is being tested independently of the published layers.

An additional RTS smoother comparison follows the Word document's optional
short-gap preprocessing recommendation. The implementation uses a position-only
white-jerk state model and the fixed-interval recursion in Särkkä (2013), §8.2:
https://users.aalto.fi/~ssarkka/pub/cup_book_online_20131111.pdf . Measurement-noise
variance is estimated from the training partition (or an explicit fallback);
process-noise selection uses validation only, with embargoes and earlier-ID
exclusion. The final optimization retains the same physical bounds. The first
Florida selection retained the baseline: the smoother's best common-case position
error did not compensate for fewer accepted gaps and weaker stop recovery. No
Gaussian covariance is advertised as a calibrated field confidence interval.

The next prospective smoother experiment is a Finch-only hybrid: use the frozen
RTS reference only where both baseline and smoother pass, otherwise retain the
baseline. Validation improved Finch position error without losing accepted gaps;
Florida's stop-recovery regression excludes it. The protocol was saved before
future data collection, with previously seen IDs excluded. No smoother is yet
published.

Exact repeated SDK frame payloads are now excluded from figure extraction within
the same sensor/session, retaining the earliest receipt and all raw records. This
prevents a replay from introducing artificial clock/order breaks. A 40-record
fixture with 20 exact repeats produces one continuous 20-observation track; the
current fresh-data audit found no such repeats, so this is a robustness fix, not
an explanation for every visible gap.

Aggregate flow-lag and cached-road alignment audits are diagnostic only. They
separate earlier selection from later comparison, preserve missing evidence, and
never change calibration or establish cross-sensor identity. In particular, long
Finch links cannot be validated by simply extending a line or increasing a time
gate until it meets another trajectory.

Finch's stationary-endpoint correction is now enabled only at Weston and Kipling,
selected before three later test windows. It recovered 37 masks across 31 distinct
fragment ranks (not necessarily independent vehicles), with mean position error
0.079 m and case-MAE 95th percentile 0.296 m. The frozen threshold requires a
negative derivative no larger than 0.1 m/s, position span no larger than 0.1 m,
and near-zero trend. For example, a visible -0.03 m/s derivative in an otherwise
stationary endpoint may be estimated as zero for the dashed gap; the recorded
positions remain unchanged. Other Finch sites retain their original exclusions.
A same-snapshot publication preview increased local estimates 34→41, all seven
additional estimates at Weston; that count is not new ground-truth validation.

Fresh directed-road comparisons identified unresolved handedness at Driftwood and
Norfinch. Fixed candidates were selected on earlier segments and checked after a
30-second embargo on at least five minutes of new observations. Driftwood's later
median road distance improved 7.31→2.16 m and axis error 15.30→1.27 degrees;
Norfinch improved 12.28→4.81 m and 4.26→1.22 degrees. The application now reflects
SDK Y before rotations of 269 and 272 degrees respectively. Origins are unchanged;
these remain provisional cached-map fits, not surveyed calibration. Florida's
current transforms remained close to the fresh optima and were preserved.

Signal-direction correlations now carry the transform used to build their evidence.
Changing a transform invalidates old inferred directions, while received phase
colors remain available independently. The learner resets affected site evidence
when the transform changes. This prevents a trajectory-alignment fix from silently
reusing phase-direction correlations learned under the old coordinate system.

Whole-outage checks now also include fixed 90/120-second masks and restrict the
scoring denominator to the car class used by the frozen model. In the new long
outage window, neither corridor had continuously observed cars spanning the
90/120-second masks; many vehicles were entirely hidden. These are unsupported
reconstructions, not successful recoveries or zero-error results.

Florida's estimated intersensor layer now uses the frozen 0.5 shape penalty and
exact feasible-velocity admission gate, followed by the unchanged final bounded
refinement. Two later masked-association windows yielded 674 correct / 0 false
versus 599 / 0 for the same shape matcher with its old cubic-only gate, among
774 eligible scenarios. Scenarios reuse vehicles. Actual cross-sensor identity
and box-size biases remain unverified; these stay experimental dashed hypotheses.
A same-window display preview increased Florida links 141→185 without changing
the 52 local estimates. Finch retains its previous matcher pending more evidence.

Audit improvements keep map-transform manifests separate from model versions,
track exact reasons for same-ID rejection, and distinguish entirely hidden cars
from cars with too little visible endpoint context. The lateral-mask validator
now uses the same 0.5-second actual-frame selection as production and time-based
endpoint context. Earlier native-cadence lateral results remain historical records,
not interchangeable with the revised validation. Lateral gate widening remains off.

A second clock comparison is frozen prospectively after 07:26:47 UTC on Nov 23,
using the same actual-frame 0.5-second cadence as production. Both methods hide
identical physical observations, and earlier IDs are excluded. Receipt-anchored
sensor elapsed time is not a verified timezone or intersensor synchronization.
Raw clock resets/reordering still reject an experimental session; no timestamp
repair or unvalidated timeline change is deployed. The campaign records clock
exclusions and keeps windows/identities separate across repeated evaluations.

The seven accumulated early windows support testing the stationary-endpoint rule
at six additional Finch sites: Islington, Signet, Martin Grove, Norfinch, Driftwood
and York Gate. This site selection is post-hoc; those earlier results are now
development evidence, not independent confirmation of the expansion. A separate
protocol frozen at 07:36:39 UTC excludes earlier IDs and requires at least three
future windows and ten distinct newly recovered IDs per site before review.
Albion has too few development examples, and Jane has no authorized stream.
No additional site has been enabled by this protocol alone.

### Separate vehicle-class audit, November 23

A chronological class-specific diagnostic fits speed/acceleration bounds using
only the first half hour and tests later IDs in the final quarter, with a
30-second embargo. Default car-only admission is unchanged. Finch strict local
masks accepted 9/12 class-4 cases (MAE 1.42 m), 21/36 class-5 cases (3.29 m),
and 8/16 class-8 cases (0.70 m). Recalibrating bounds per class produced no
meaningful improvement or extra accepted cases. Florida had no eligible held-out
class-4/8 cases and insufficient class-5 training. These are vendor classes,
not manually confirmed vehicle types; class 8 may describe trailers. No broader
class matching is enabled. Unit checks preserve the car-only default and require
distinct training IDs rather than counting repeated fragments as new vehicles.

### Finch association deployment after future-window comparison

On the same two later cohorts (cycles 034 and 040), the current production
matcher produced 617 correct and 9 false masked associations; the frozen
shape-plus-exact-feasibility candidate produced 667 correct and 5 false, over
1,024 eligible scenarios. Scenarios reuse vehicles and are not independent.
No site increased its false-match count in this comparison. An earlier third
gate study supports the exact gate but has a different cohort from the production
comparison, so its totals are not combined with those two cohorts.

The experimental Finch between-intersection layer now uses this candidate.
On the identical current snapshot, local estimates stay at 46 and intersite
estimates rise from 108 to 114. Final endpoint/physical bounds remain unchanged.
This improves masked association evidence, not verified cross-sensor identities.
Raw observations, signal permissions and recorded KPI inputs are unchanged.

The outage validator now reports only cars with continuous visible endpoint
context as the supported denominator, separately from entirely hidden vehicles
and short-context vehicles. Unresolved cases retain hashed-identity diagnostics
(endpoint evidence and solver rejection) for investigation without claiming they
were reconstructed. Lateral-validation summaries separate legacy native-frame
cadence from production 0.5-second frame selection; pooled historical counts
are not used as interchangeable deployment evidence.

### Endpoint-grid experiment (unpublished)

Half-second trapezoidal velocity integration can falsely exclude very short
terminal acceleration: a 0.107 m/s endpoint requires at least 0.02675 m on a
half-second grid, although 3 m/s² acceleration needs only about 0.00191 m in
continuous time. An experimental grid adds all endpoint-reachable velocity
envelope breakpoints and retries the same constrained objective only after a
rejection. It does not relax physical bounds or replace an accepted solution.
Development masks recovered one additional Finch stationary case (position MAE
0.020 m), and no Florida cases. This is insufficient for deployment. A frozen
future-data protocol requires at least three later windows and ten distinct
newly recovered IDs before review, with no automatic publication.

### Overlapping coverage is distinct from a missing spatial gap

A current Florida endpoint audit found overlapping projected coverage at Cranes
Roost/Hattaway in both directions and at Hattaway/Renaissance eastbound. A
backward connector is not an acceptable way to join those observations. A
separate diagnostic splits real local tracks into overlapping spatial views
using disjoint alternating observations, with identities hidden from matching.
Of 1,047 Florida paired scenarios, only 218 had enough sampled overlap evidence;
216 were matched correctly with no false match. Finch had 736 supported pairs
out of 1,245 scenarios, 727 correct matches and 2 false matches. Widths and
endpoint-removal scenarios reuse vehicles; these are not independent counts.
Both views still originate from one sensor, so this does not validate actual
cross-sensor clock/position bias. Overlap hypotheses remain unpublished and no
new line is drawn where overlapping observations already exist.

### Dedicated quadratic solver comparison (unpublished)

The kinematic loss is convex quadratic in interval velocity, with linear
acceleration, displacement and endpoint constraints. An optional OSQP 1.0.5
experiment expresses exactly that existing objective in matrix form. Unit tests
compare loss differences and verify that impossible motion remains rejected.
Strict physical checks still run after solving; current accepted estimates are
preserved. Optional installation: `pip install -r requirements-reconstruction-experiments.txt`.
Official API and formulation: https://osqp.org/docs/interfaces/python.html and
https://osqp.org/docs/solver/index.html .

On the development window, the fallback recovered 15 additional Finch masks:
10 thirty-second cases averaged 2.36 m position MAE, while five sixty-second
cases averaged 6.44 m. One additional Florida thirty-second case had 3.29 m MAE.
The prospective review scope is therefore limited to <=30 s, frozen before later
recordings, requiring three future windows and twenty distinct new IDs per
region before review. Larger-gap results remain diagnostic; no solver fallback
is enabled in the dashboard merely because it produces more lines.

### Timeline and bounded-order diagnostics (unpublished)

The first two prospective clock comparisons support further Finch testing:
197 common masks averaged 1.80 m receipt-time MAE versus 1.59 m sensor-elapsed
MAE. Grouping correlated masks by 174 vehicle IDs gave mean paired improvement
0.232 m, bootstrap 95% interval [0.082, 0.430] m. This is conditional on tracks
accepted by the experimental clock audit, not absolute clock synchronization.
Florida's 41 common cases improved only 0.035 m, interval [-0.045, 0.136] m.

A separate read-only experiment permits retrospective sorting of at most 1%
of frames with <=0.25 s lateness, preserving every retained timestamp and receipt.
Tied timestamps and larger resets still reject that experimental session. It
restored Renaissance and Essex in one audit, but Boston and Plaza had distinct
object observations sharing timestamps and remained excluded. No timing repair
or sensor-time view is deployed. The raw buffer retains these observations.
A Finch coverage audit also found short reconnect sessions failing clock-rate
checks, so a blanket timeline switch could lose usable received data.

### Stationary measurement-noise hypothesis (unpublished)

When both visible endpoint contexts support stationarity but centimetre-scale
position/speed noise makes exact monotone interpolation impossible, a separate
experiment estimates a constant latent position. It requires the same sensor,
session and object ID, duration <=30 s, endpoint separation <=0.1 m, and compact
quiet context on both sides. Original points are not changed. The estimated
position can differ from each endpoint by <=0.05 m, recorded explicitly; it is
not described as exact interpolation or calibrated uncertainty.
Development masks added four Florida cases (MAE 0.013 m) and three Finch cases
(0.016 m). A new frozen prospective protocol requires three future windows, ten
distinct added IDs, and stricter stationary-error/stop-precision limits before
review. No stationary plateau is published automatically.

### Additional Finch deployment after three prospective windows

Signet, Martin Grove and Norfinch passed the frozen expansion review: 50 new
masked cases across 45 distinct IDs, weighted position MAE 0.267 m, no
physical violations, and acceptable external daytime errors. They now join
Weston/Kipling in the published stationary endpoint correction scope.
On an identical current snapshot, local estimates increased from 38 to 43;
between-intersection estimates remained 123. Raw observations were unchanged.
York Gate passed overnight checks but failed the external daytime check
(additional-case MAE 4.07 m, p95 case MAE 17.23 m), so remains withheld.
Islington and Driftwood had nine distinct new IDs each and remain pending the
frozen ten-ID requirement, despite encouraging errors.

The separate November 6 external-recording audit read 326,411 frames without
archive errors. Association improved from 2,455 correct / 15 false to 2,620
correct / 8 false in 3,133 correlated masked scenarios. A saved validation figure
is generated by `deepctm.render_archive_validation`; results concern hidden
recorded sections, not verified identities between physical sensors.

### External stationary-plateau check

The same frozen plateau rule was applied to the November 6 Finch archive,
without fitting to it. It evaluated 288 masks and added five distinct vehicle
IDs: mean position error 0.0303 m, speed error 0.0700 m/s, no physical violations,
and stop precision/recall 1.0. This small external sample does not replace the
required three prospective windows and ten distinct added IDs. The candidate
remains unpublished. Archive loading is now shared by the validation commands;
the original recordings and raw endpoints remain unchanged.

### Fourth prospective expansion window

Islington and Driftwood now passed the unchanged expansion criteria over four
future windows. Islington added 18 masks from 15 distinct IDs (MAE 0.101 m);
Driftwood added 18 masks from 14 IDs (MAE 0.161 m). Both had zero physical
violations and passed the additional November 6 daytime check. Their narrow
stationary endpoint correction is enabled; York Gate remains withheld.
On the identical current snapshot this raised local estimates from 39 to 41,
with 132 between-intersection estimates unchanged. Ten relevant endpoint/config
tests passed. Evidence hashes are saved in the configuration.

The plateau candidate now has an explicitly disabled layer-builder option. It
can run only as a same-intersection car fallback after the regular estimate
fails. Between-intersection matching never invokes it. Metadata preserves the
original endpoint speeds and signed position residuals, and states that this is
not exact interpolation. No region is enabled until the prospective criteria
pass. The full 210-test scientific suite passed, including both-direction
residual-sign and observation-preservation checks.

### Live freshness race corrected

A per-sensor API check caught a newly received Signet frame labeled stale with
negative age: the preview function sampled its clock before querying health and
the latest frame. Collection committed during that query. The function now
samples the clock after fetching the frame, retaining strict future/stale checks
for explicitly supplied clocks. A regression test reproduces the concurrent
arrival; eleven live/preview/combined tests passed. Only the dashboard server
was restarted. The subsequent API check showed all seven Florida and all nine
authorized Finch sensors fresh within 0.71 s; Jane remained unavailable.

### Inspecting accepted-case failures

`deepctm.render_gap_examples` saves median-error and worst-error accepted masks
for each corridor from the latest hour's final quarter, excluding earlier IDs.
It uses frozen published parameters, performs no fitting, and retains source
hashes and scoring metadata. The inspected figure shows that exact endpoints
and physical bounds alone do not recover stop location inside a long gap: the
worst illustrated Florida 30-second gap has 17.57 m MAE; Finch's 60-second gap
has 18.54 m MAE. Median illustrated cases are 0.45 m and 0.29 m. These are
declared selected examples, not aggregate error claims. No missing trajectory
is represented as a recovered ground-truth identity.

### Finch local fallbacks enabled after prospective review

The stationary plateau passed three future windows (33 added masks, 30 IDs,
MAE 0.00983 m, maximum error 0.09 m). Deployment is further restricted to the
seven endpoint-correction-enabled Finch sites, so withheld sites do not gain an
untested fallback. The adaptive endpoint grid passed four windows (10 added
IDs, MAE 0.296 m, p95 case MAE 1.057 m). Both retain physical checks; the grid
keeps exact endpoints, while the plateau explicitly reports its <=0.05 m
endpoint residuals. Neither changes between-intersection matching.

A paired composition check added 15 masks with MAE 0.122 m, p95 case MAE
0.573 m and zero physical violations; every previously accepted path was
identical. On the same current-hour snapshot, local estimates increased from
39 to 42 (one plateau, two grid retries), while all 139 between-site paths were
identical. The Finch derived-layer worker was reloaded; collectors were not
restarted. All 211 scientific tests passed. Florida remains disabled pending
its unchanged minimum sample requirements. Broad OSQP fallback failed quality
limits in both regions and remains unpublished.

The figure status and hover text now distinguish adaptive-grid estimates from
stationary latent-position estimates, including the latter's endpoint residual.
Browser verification showed the two grid retries and one stationary fallback
with both estimated layers enabled; the current eastbound view displayed 18
local and 62 between-site estimates. JavaScript syntax validation passed.

### Florida stationary fallback enabled

Four future windows supplied 15 added stationary masks from 15 distinct IDs:
MAE 0.0151 m, maximum error 0.31 m, stop precision 1.0, zero physical violations.
The same frozen criteria passed. Hattaway remains excluded by the published
site policy; 14 of the 15 qualifying IDs belong to permitted sites. The Florida
layer worker now enables the bounded stationary fallback. On the deployment
snapshot it added no new paths: all 61 local and 249 between-site estimates
were unchanged. Enablement is not a promise of an extra line in every window.
A regression test confirms excluded sites cannot receive this fallback.
Florida's adaptive-grid retry remains withheld at seven distinct added IDs.

### Larger prospective matching sample

After nine matching-validation windows, the feasible gate recovered 4,564
correct Florida masked matches versus 4,063 for the previous gate; wrong matches
increased from 10 to 12. Finch improved from 3,651 correct / 43 wrong to 3,968
correct / 33 wrong. The extra Florida errors are retained in the report rather
than hidden by the higher recall. These are correlated same-sensor scenarios,
not actual cross-sensor identity labels. The dashboard now shows this direct
gate comparison and labels older comparators as frozen references.

The RTS reference improved mean error on 617 accepted Finch masks, with an
identity-grouped mean gain of 0.124 m (exploratory bootstrap interval 0.009–0.252
m across 554 IDs). Its p95 case error worsened and Islington/Martin Grove mean
errors worsened, so a blanket deployment remains withheld. No test-based site
selection is silently promoted.

### Florida adaptive grid enabled

Seven complete prospective windows supplied 14 added masks from 14 distinct
vehicles: mean position error 0.172 m, speed error 0.110 m/s, p95 case MAE
0.688 m, zero physical violations. The unchanged review requirements passed.
The same local-only adaptive-grid retry is now enabled in Florida. An identical
current snapshot increased local estimates from 134 to 135; all 595 between-site
paths and all previously accepted local paths were unchanged. The existing
worker reads this configuration on its next refresh; the current layer was
also regenerated and published. No collector restart or bound relaxation.

### Validation-copy starvation fixed without stopping collection

A one-second native performance sample showed the slow final batch spending
its time in SQLite incremental backup, rather than model inference. Concurrent
commits could repeatedly restart the copy. Validation copies now pin a
consistent read transaction only while copying, close the source immediately,
and enforce a 30-second progress deadline. No source write or collector pause.
A real 457,645-frame Finch buffer copied in 3.212 seconds after the fix.
Regression tests cover a concurrent commit and deadline cancellation; all 214
scientific tests passed. The existing validation campaign resumed from its
completed reports with the original deadline; the incomplete in-memory batch
was discarded, not reported as a successful validation window.
