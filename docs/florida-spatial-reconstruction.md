# Florida spatial blind-band reconstruction

## Target clarified by the marked image

The red horizontal bands separate locally observed road sections along SR-436. The green outlines indicate interruptions inside observations and are not the target of this work. Florida now has a separate spatial-estimates checkbox, enabled initially; its temporal-gap checkbox is initially off. Finch behavior is unchanged. Solid observations are never overwritten.

## Implemented method

`deepctm/spatial_bridges.py` estimates associations between actual fragment endpoints at adjacent sensors, for eastbound and westbound vehicles. Candidate endpoints lie within 30 m of empirical outer coverage edges. Travel time, visible velocity and object class determine a candidate cost. One-to-one associations need a margin over competing candidates. Curves are monotone cubic Hermite reconstructions, bounded by speed and acceleration checks. They exactly meet the proposed visible endpoints; there are no arbitrary virtual seeds. A connection can be wrong even when physically plausible, so UI hover/status labels state that identity is unverified. No probability/confidence percentage is claimed from the cost margin.

The background Florida figure worker generates these paths with each snapshot. The client filters paths by selected adjacent intersections, direction and vehicle class, and uses dashed speed colors. Local temporal interpolation remains independently controlled. Raw rolling retention stays at 90 minutes. Existing committed observations and endpoints are not modified.

## Paper relationship

The supplied DeepCTM paper (DOI 10.1007/978-3-032-38410-2_54), especially observed/virtual-cell representation and physical/neural gating, addresses aggregate traffic-state inference. LightSim (https://arxiv.org/abs/2602.21852) supplies conservative sending/receiving cell dynamics and signal-gated flow. Neither establishes cross-sensor vehicle identity. Prior aggregate DeepCTM evaluation remains separate. The displayed curves are explicitly an alternative motion reconstruction, not claimed paper-model output.

## Real-data spatial masking

`deepctm/validate_spatial.py` removes entire 20/50/100 m strips from continuous observed tracks. Five visible samples before and after form the estimator inputs. Hidden interior points only supply scoring. It separately removes identities, and then removes 25% of arrivals to simulate missed detections/turns. There is no actual cross-sensor ground truth; same-sensor tests cannot establish clock-offset or field-alignment accuracy. Widths reuse tracks and are correlated. Cases are selected from the final 20% time portion with all context inside it; no coefficients are fitted on the test. New recordings after the recorder restart cover only part of that hour.

20 November comparison on the same accepted cases:

| Mask | Common/eligible | Linear MAE | Hermite MAE | Monotone MAE | Queue candidate MAE | Correct/matched, missing-arrival test |
|---|---|---|---|---|---|---|
| 20 m | 466/589 | 0.49 m | 0.50 m | 0.50 m | 0.50 m | 213/214 |
| 50 m | 483/512 | 1.02 m | 0.70 m | 0.70 m | 0.68 m | 186/192 |
| 100 m | 198/212 | 2.97 m | 1.27 m | 1.27 m | 1.21 m | 75/78 |

These averages do not describe every proposed line. Worst saved monotone examples reach 29 m MAE due to hidden stopping and acceleration. Association precision is conditional on accepted proposals, not total reconstruction coverage.

## Queue-aware experiment, not promoted

A fourth candidate brakes to zero, waits, accelerates and cruises to the visible arrival. It assumes acceleration/deceleration 3 m/s² and an entry-side stop, falling back to monotone motion if distance/time cannot support that hypothesis. This was designed after looking at failures, so its evaluation on the same sample is exploratory, not untouched validation. In six common 100 m stop-and-go cases, MAE changed from 10.28 to 7.25 m; in three 50 m cases from 3.89 to 0.81 m. These samples are too small for promotion. The live rolling chart still uses the monotone method. Remaining work: independently test queue location, longer recordings, clock-offset sensitivity, and association robustness under lane changes/turning flows. Keep the goal unfinished while these material modeling checks remain.

## Reproduction and evidence

- `python -m deepctm.validate_spatial --snapshot data/florida-rolling/snapshot.json --output data/validation/NEW-RUN` in `.venv-deepctm`.
- Initial benchmark: `data/validation/20261119-spatial/`.
- New same-case benchmark: `data/validation/20261120-spatial/`.
- Queue experiment on the identical source window: `data/validation/20261120-spatial-queue/`.
- Public-in-local-dashboard report: `/spatial-validation.html`, linked from `/florida_rolling.html`.
- Seven spatial software tests cover exact endpoints/speed, direction, hidden-truth isolation, ambiguous rejection, one-to-one matching, queue distance and nonfinite rejection. The 54-test model suite passed before the last two spatial tests were added; all seven spatial tests then passed. JavaScript syntax passed. The static comparison figure was visually inspected. Browser inspection on 19 November showed dashed connections in the formerly empty bands. On 20 November the refreshed figure API was checked again.

Historical startup recovery now waits for 30 seconds of fresh samples when the cached snapshot is expired, rather than immediately publishing a nearly empty snapshot. API collectors are separate and are not restarted for this operation.

## Florida movement-aware reconstruction — 20 November 2026

The rolling processor now retains full two-dimensional vehicle paths before cropping the corridor figure. It classifies twelve FROM-arm → TO-arm movements from approach and departure geometry. N/S are provisional road-relative arms; E/W follow the corridor alignment. A label is not assigned when the visible path is incomplete, discontinuous, or ambiguous. Counts are track fragments, not deduplicated vehicle totals.

| From | Straight | Left | Right |
| --- | --- | --- | --- |
| North | NS | NE | NW |
| South | SN | SW | SE |
| East | EW | ES | EN |
| West | WE | WN | WS |

Through traffic can match both adjacent intersections. Side-road entries can match onward only; corridor exits can match backward only. Cross-street paths and unknown movements cannot form inter-sensor connections. Example: NE enters eastbound and may match a WE or WN path at the next intersection. WN leaves eastbound and must not be linked onward. This prevents geometry-incompatible associations without claiming vehicle identity.

The buffer also retains receipt-timed phase snapshots for 90 minutes. Phase evidence is matched only within the same collector session. A qualifying release needs at least two seconds stopped, subsequent motion of at least 2 m/s, and entry into the central area within 20 seconds. We use the final qualifying release before entry to reduce queue-creep confusion. No saved phase-label/phaseNumber equality is assumed.

An estimated assignment requires at least ten minutes of phase observations, eight releases over three green-onset cycles, at least 80% green agreement, at most 10% red disagreement, at least 50% releases near green onset, enrichment over green duty, and a 0.2 score margin over the next candidate. Synchronized phases, permissive turns, geometry uncertainty and receipt-clock differences can prevent decoding. One phase may correlate with several movements; this does not establish a physical signal-head location or protected permission for each turn.

The selected-site movement table shows all twelve movements, corridor eligibility and estimated phase assignments. In the checked snapshot, 15 assignments passed across six sites; Renaissance had none. All 1,052 proposed spatial connections passed the directional entry/exit invariant. These are current-window results, not permanent mappings. No forced joins are created for missing evidence.

Validation: 103 dashboard tests and 57 DeepCTM tests passed; JavaScript syntax passed. Tests include all twelve turn labels, stopped approaches, incomplete tracks, wrong sessions, correlated phases, distant queue creep and asymmetric entry/exit matching. The new movement and phase inference has software validation, but not manually labelled field accuracy. The prior masked spatial benchmark remains separate and does not validate these new phase assignments. Further work requires annotated turns, independent release review and held-out identity association checks.
