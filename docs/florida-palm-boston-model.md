# Palm Springs–Boston: paper-based prediction experiment

## Scope and current state

Only Palm Springs Dr & SR-436 (`OBC-AG-SA-C257225`) and Boston Ave & SR-436 (`OBC-AG-SA-C257206`) are modeled. There is one directed model for eastbound and another for westbound. The current implementation is an independent, provisional adaptation, not author code or an exact reproduction. It predicts aggregate traffic states and integrates representative paths through the predicted speed field. It does not identify the same vehicle across sensors.

Viewer: http://127.0.0.1:8775/florida-pair.html, also linked from the Florida section of Historical Performance. This is a saved experiment, not an automatically retraining live forecast service. Existing rolling observation figures and local gap interpolation remain separate.

## Sources and method mapping

- Cellitti, Di Rocco and Ferraro Petrillo, *A Physics Informed GNN for Traffic Prediction: the DeepCTM Model*, supplied PDF, pp. 674–685, DOI 10.1007/978-3-032-38410-2_54.
- Su & Deng, *LightSim: A Lightweight Cell Transmission Model Simulator for Traffic Signal Control Research*, https://arxiv.org/pdf/2602.21852, sections 3.1–3.4 and 4.2.

| Paper component | Implementation and adaptation |
|---|---|
| DeepCTM observed and virtual graph cells | Two 60 m observed endpoint cells; six virtual cells of about 37.62 m. Virtual targets are always masked. |
| Flow, density/occupancy, speed inputs | LiDAR Edie-style distance/time aggregates replace loop occupancy. Units are veh/h, veh/km and km/h. |
| Physical/free recurrent state | 64-dimensional physical encoding and 32-dimensional free LSTM state. Physical decoding/encoding choices are explicit implementation choices omitted from the paper. |
| CTM predictor plus learned residual | CFL-substepped triangular sending/receiving physics plus a bounded learned residual. |
| Asymmetric message passing | Separate learned upstream/downstream transforms, plus a self transform. |
| Adaptive physics-neural gate | Learned sigmoid mix conditioned on observation availability. Missing inputs are masked, including separately missing speed. |
| Physical error correction | Learned observed-feature discrepancy correction, with strength 0.1 and masked assimilation. The exact correction network is an adaptation. |
| Multi-objective training | Masked data error, physical consistency, spatial smoothness and PEC. Paper loss weights retained; normalizations are declared implementation choices. |
| LightSim conservation and CFL | Conservative inter-cell flow, finite sending/receiving capacity, jam density, CFL substeps and shared boundary fluxes. Tests cover both fundamental-diagram branches. |
| LightSim signal masks and downstream supply | Optional edge signal masks and downstream receiving density. Red-gate tests verify blocked flow and conservation. Live runs use no invented signal state because through-phase mapping is not verified. |
| LightSim RL/controller experiments | Outside this prediction-only task. No signal optimization or commands to real controllers are performed. |

Neither source supplies an individual-vehicle cross-sensor association algorithm. A predicted dashed curve is a virtual tracer in a macroscopic state forecast, not a recovered real vehicle. LightSim's validation of simulation/controller rankings is not validation of these paths.

## Geometry and time

Configured origins are 285.716 m apart using local geographic distance. The modeled chain runs from 30 m before the upstream origin to 30 m after the downstream origin: total 345.716 m. The 225.716 m between the two observed cells is subdivided into six virtual cells. Direction reverses the chain for westbound. Road bearing, origins and rotations are provisional; the configured SDK Y-axis inversion is applied before rotation.

The paper's 15-minute bins and 15/60-minute forecasts are too coarse for this short link and the retained 90-minute dataset. This experiment uses 10-second aggregates, two minutes of context and a two-minute open-loop forecast. This is a temporal adaptation, not a replication of the paper's Madrid results. The physical prior is 50 km/h free speed, 18 km/h backward wave speed and 300 veh/km aggregate jam density (assumed two lanes). These require calibration; the 50 km/h bound misses some higher observed Florida speeds.

Receipt-time bins are used. Relative sensor timestamps reject inconsistent intervals; absolute cross-sensor clock offsets remain unverified. Time mismatch limits travel-time and coordination interpretations.

## Missing data, supervision and splits

Frame coverage must reach 80% for a bin. A covered bin without accepted vehicle motion can supply zero observed flow/density proxies; speed is unobserved rather than labeled zero. The first-state prior and later assimilation both honor feature masks. Stationary objects whose direction is not established, cross-street motion and invalid segments are excluded, so these inputs remain detection/ROI-dependent proxies.

The 90-minute window is split chronologically 60/20/20. Every context-plus-target sequence lies entirely inside one partition. Each endpoint requires at least 80% valid bins in the context and target portions, while individual missing bins stay masked. This retains the paper's missing-observation mechanism rather than interpolating training targets or rejecting every sequence with one missing bin.

Model selection uses only normalized validation error across observed features. Test observations never enter forecast inputs. The current run has 271 training, 77 validation and 85 test windows per direction. Windows overlap and are not independent samples. There is no independent multi-day field test; repeated development inspection means these scores should be treated as exploratory evidence.

## Forecast visualization

Select direction, forecast origin and model. A forecast uses only its preceding two-minute context. Six representative tracers are seeded at 20-second intervals and propagated at one-second display steps through the predicted cell-speed field. The model state is held piecewise constant within its 10-second predicted intervals. Tracers start at the upstream observation-cell boundary and stop at the downstream boundary or forecast horizon. They never join unrelated downstream object IDs, exceed the selected forecast window or stitch forecasts from different origins.

Persistence uses past endpoint states, spatially interpolated through virtual cells only for visualization. Pure CTM rolls the same past initial state forward with persisted boundary demand. Their endpoint scores are compared against the neural model. Colors are speed, not signal state; tracer count is not volume.

## First evaluated run

Saved at `data/florida-pair/20261118-palm-boston-v3/`. Features, feature masks, configuration, quality evidence, checkpoints, predictions, split indices and reports are saved; original frame payloads are not copied into this experiment. Raw data retains its rolling 90-minute policy. Source hashes identify the training implementation. The persistence visualization's virtual cells were corrected after training; this changes no endpoint metric or learned checkpoint.

Speed RMSE (km/h):

| Direction / horizon | DeepCTM | Persistence | Pure CTM |
|---|---:|---:|---:|
| Eastbound, 10 s | 23.46 | 14.26 | 28.33 |
| Eastbound, 60 s | 23.49 | 34.99 | 28.66 |
| Eastbound, 120 s | 22.17 | 38.88 | 28.74 |
| Westbound, 10 s | 7.14 | 9.49 | 39.37 |
| Westbound, 60 s | 7.09 | 9.58 | 36.71 |
| Westbound, 120 s | 7.48 | 8.58 | 27.25 |

These are endpoint errors, not intermediate trajectory errors. Eastbound short-horizon speed is worse than persistence. Neural predictions are over-smoothed and the physical speed prior is low for some observed vehicles. Neither trained direction is field-validated. Neural corrections produce mean mass discrepancies of about 0.1192 eastbound and 0.0216 westbound vehicles per cell-step; exact CTM conservation does not imply exact conservation of the full neural model.

## Reproduce

```sh
.venv-deepctm/bin/python -m deepctm.florida_pair --output data/florida-pair/NEW-EXPERIMENT
.venv-deepctm/bin/python -m deepctm.pair_train --experiment data/florida-pair/NEW-EXPERIMENT
.venv-deepctm/bin/python -m deepctm.pair_view --experiment data/florida-pair/NEW-EXPERIMENT
.venv/bin/python -m deepctm.preview
```

The output directory must be new; existing experiments are not overwritten. Fresh preparation reads the currently retained data, so it is a new experiment. Rerunning training against saved aggregate features reproduces the same source window. `pair_view` updates the local viewer pointer after export. The public live-only allowlist remains unchanged.

## Validation and remaining work

Tests cover geographic chain length, chronological splits, mirror-Y direction, zero-flow versus unknown speed, masked-feature invariance, virtual target masking, gradient flow, conservative CTM updates, red gates, downstream supply, fundamental-diagram equilibrium, and tracer direction/bounds/time limits. Browser checks confirmed both travel directions and the endpoint comparison table.

Remaining: calibrate physical parameters using training-only data, address over-smoothing and feature imbalance, compare against a genuinely later untouched period, and evaluate spatial reconstruction by withholding measured local road strips. None of those can establish accuracy in the fully unobserved blind segment without additional reference observations. The goal remains active while those model-quality checks are completed.
