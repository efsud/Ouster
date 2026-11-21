# Hidden-trajectory validation and model revision — 19 November 2026

## What changed and why

Added a reproducible hide-and-reconstruct evaluation for local vehicle trajectories in both corridors. Five visible samples on either side enter the existing Hermite estimator; the hidden interior is used only for scoring. Tested roughly 5/10/20/30-second gaps on continuous ground truth. A sampling-boundary bug in the initial 30-second validation was corrected before the final run. The live estimator itself was not changed or tuned on this evaluation.

Added optional equal-feature training loss and training-only empirical scales to DeepCTM. A new experiment raises the speed cap from 50 to 69.50 km/h (training 99th percentile) and trains 120 epochs. This is a candidate empirical prior, not a verified road free-flow parameter. Legacy checkpoints remain compatible. Checkpoints are selected using validation loss, never later-period errors.

## Local trajectory findings

Florida: one-hour source window ending 2026-11-19T12:33:16-05:00.

Toronto: one-hour source window ending 2026-11-19T12:33:28-05:00.

| Corridor | Gap target (s) | Accepted / eligible | Mean gap MAE (m) | Linear MAE, same cases (m) | Moving-gap MAE (m), n | Worst gap MAE (m) |
|---|---|---|---|---|---|---|
| Florida | 5 | 8,750 / 12,316 | 0.51 | 0.76 | 0.68 (6,117) | 4.45 |
| Florida | 10 | 3,678 / 5,436 | 0.60 | 2.02 | 1.32 (1,452) | 7.91 |
| Florida | 20 | 1,994 / 2,953 | 0.81 | 2.52 | 5.70 (229) | 27.13 |
| Florida | 30 | 1,508 / 2,307 | 0.69 | 1.79 | 9.12 (79) | 23.29 |
| Toronto | 5 | 7,463 / 9,789 | 0.32 | 0.60 | 0.60 (3,337) | 3.17 |
| Toronto | 10 | 4,605 / 6,600 | 0.47 | 1.13 | 1.45 (1,185) | 8.70 |
| Toronto | 20 | 2,820 / 4,168 | 0.49 | 1.16 | 4.21 (224) | 16.12 |
| Toronto | 30 | 2,074 / 3,337 | 0.41 | 0.94 | 5.76 (79) | 17.36 |

Errors are average per-gap longitudinal MAEs. Moving gaps span more than 5 m in withheld observations, for evaluation stratification only. The linear baseline is evaluated on exactly the accepted cases. Different gap lengths reuse tracks; samples are not independent. Low errors for stationary traffic must not be generalized to moving vehicles. Worst examples expose missed stops and acceleration. The method uses future visible observations and is retrospective interpolation, not a causal DeepCTM forecast. Source alignment and clock offsets remain provisional. True missingness can differ from these artificial masks.

Worked example: a 10-second gap supplies five samples before and five after it. All interior samples are removed from estimator inputs. Position MAE compares interpolated positions with each hidden position, then averages those errors within that gap. Rejected gaps contribute to acceptance counts, not to a misleading zero error.

## Later-period model comparison

Speed RMSE in km/h; 17 nonoverlapping context-plus-forecast windows per direction, all contexts beginning after the original training experiment ends. Both checkpoints are frozen; no fitting uses later data.

| Direction | Lead (s) | Independent windows | Original DeepCTM | Revised DeepCTM | Persistence | Revised pure CTM |
|---|---|---|---|---|---|---|
| eastbound | 10 | 17 | 19.01 | 20.50 | 18.49 | 43.52 |
| eastbound | 60 | 17 | 22.65 | 22.47 | 36.26 | 46.77 |
| eastbound | 120 | 17 | 20.27 | 20.47 | 37.95 | 41.08 |
| westbound | 10 | 17 | 8.09 | 7.67 | 9.48 | 47.62 |
| westbound | 60 | 17 | 6.77 | 6.38 | 9.11 | 35.07 |
| westbound | 120 | 17 | 1.91 | 4.18 | 10.55 | 42.38 |

The candidate improves westbound 10/60-second speed modestly but has mixed endpoint results, including worse flow and westbound 120-second speed. Raising the speed prior worsens pure CTM error. **Do not promote this candidate to the dashboard default.** The viewer pointer remains unchanged. No intermediate-road ground truth exists, and endpoint metrics do not validate cross-sensor paths. This later dataset has now been evaluated; future development needs a fresh held-out period.

## Artifacts and reproduction

- Local report: http://127.0.0.1:8775/trajectory-validation.html (also linked in Historical Performance).
- Full per-site scores and representative observed/estimated examples: `data/validation/20261119/gap-validation.json`.
- Candidate checkpoint, feature archive, training history and held-out predictions: `data/florida-pair/20261119-balanced-v1/`.
- Frozen later evaluation for each model: its `later-evaluation.json`.
- Raw frames are not duplicated; existing rolling retention stays unchanged. Saved derived reports preserve validation evidence after expiry.

```sh
.venv-deepctm/bin/python -m deepctm.prepare_balanced --source data/florida-pair/20261118-palm-boston-v3 --output data/florida-pair/NEW-RUN
.venv-deepctm/bin/python -m deepctm.pair_train --experiment data/florida-pair/NEW-RUN
.venv-deepctm/bin/python -m deepctm.evaluate_later --experiment data/florida-pair/NEW-RUN --later data/florida-pair/20261118-palm-boston-later-v1
.venv-deepctm/bin/python -m deepctm.validate_gaps --output data/validation/NEW-RUN
```

A new gap run reads currently retained frames, so it is a new dataset. Saved reports can always be rendered again. `--reuse-window` holds an existing evaluation window fixed only while its underlying frames remain retained.

## Validation

DeepCTM test suite: 48 tests passed; an additional balanced-loss masking test also passed. The three new trajectory tests cover 30-second inclusion, invariance of estimated positions to hidden-truth changes, and exclusion of discontinuous truth. Synthetic tests are separate from the real-data scores above. Dashboard suite: 93 tests run, 2 skipped, no failures. The generated figure was visually inspected and deliberately includes the worst cases.
