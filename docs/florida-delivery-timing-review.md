# Florida delivery timing and corridor matching — November 23, 2026

## Problem and implemented correction

The earlier 12:08 audit showed 4–8 second delivery pauses while adjacent SDK frame
timestamps advanced about 0.1 second. Treating the delivery pause as vehicle travel
time creates artificial gaps and corrupts endpoint speeds. The original raw
12:08 window has now expired under the requested 90-minute retention; its saved
audit remains. The new method was tested on later recorded data, not on invented
replacement frames for 12:08.

`deepctm/delivery_timing.py` now corrects a narrowly defined delivery burst:

1. A receipt interval exceeds 1.5 seconds, while the SDK interval is positive and
   no more than 1.5 seconds; the excess delay is at least one second.
2. SDK time remains strictly increasing and continuous through the proposed
   correction. A duplicate, reset or missing SDK interval breaks eligibility.
3. Within 60 seconds, five consecutive frames return within 0.2 seconds of the
   pre-burst receipt/SDK offset. The two-anchor clock-rate difference is <=1%.
4. Delivery adjustment is bounded to 15 seconds, with at most 0.25 seconds of
   negative residual. The two receipt anchors are unchanged.
5. Between the anchors, the plotted timestamp follows SDK elapsed time scaled
   to their interval. Original receipt timestamps, SDK timestamps, payloads and
   observed coordinates remain stored. No missing positions are synthesized.

Example: consecutive frames captured 0.1 seconds apart may arrive five seconds
apart. When subsequent frames demonstrate a continuous clock and return to the
same delivery offset, their plotted intervals follow capture elapsed time. They
stay solid because their positions were actually observed. Hover displays the
original receipt time whenever plotted time changed. True missing positions
continue to use the separate dashed reconstruction layers.

This is retrospective, receipt-anchored timing reconstruction. It does not verify
SDK timezone, absolute capture time, or synchronization between intersections.
Unanchored delays and bad clocks remain uncorrected. Phase delivery timestamps
are not silently joined to the corrected object timeline: phase-based historical
inference is withheld for that time basis. Live phase reception is unchanged.

## Fixed tests on recorded observations

Source window: **12:44:49–13:44:49 EST**, November 23. The early half is development;
the later half excludes earlier object IDs and has a 30-second embargo. Parameters
and acceptance rules were saved before scores were opened. No model fitting or
threshold tuning was done after seeing the later test.

For local masks, the same actual observed positions are hidden under both time
bases. Reconstruction receives only the visible endpoint contexts. Available
frame-clock metadata is retained; this is an object-gap test, not proof that a
complete loss of frames can be repaired. Sampling is conditional on continuous
corrected tracks; counts are not corridor-wide recall.

| Delay-affected masks | Development | Later excluded-ID test |
|---|---:|---:|
| Masks / distinct IDs | 1,604 / 530 | 1,180 / 296 |
| Receipt-time accepted | 501 | 213 |
| Corrected-time accepted | 1,083 | 475 |
| Accepted by both | 483 | 194 |
| Common-case position MAE, receipt → corrected | 3.753 → 1.663 m | 3.431 → 1.981 m |
| Common-case speed MAE, receipt → corrected | 1.480 → 0.714 m/s | 1.102 → 0.748 m/s |

The later test gains 281 accepted cases and loses 19, for a net gain of 262.
Therefore this is not a claim that every gap improves. Unaffected common-case
position MAE changes about 0.0012 m, within the frozen 0.01 m tolerance. No tested
accepted curve violated the configured physics bounds. The corrected common-case
95th-percentile position MAE is still 9.48 m, so difficult cases remain.

A descriptive bootstrap grouping common affected masks by their 117 vehicle IDs
found mean per-ID improvement 1.33 m, with interval [0.83, 1.92] m. This is
conditional exploratory evidence, not independent-day or cross-sensor validation.

## Matching validation

Recorded trajectories were masked across 20/50/100 m spatial bands. Receipt and
corrected variants used identical observed fragments and the existing motion,
shape, physics and partial-assignment policy. Source IDs were used for scoring,
not identity-blind association costs. Complete and missing-arrival cases were
both tested.

| Partition | Correct, receipt → corrected | Wrong, receipt → corrected |
|---|---:|---:|
| Development | 3,878 → 4,000 | 18 → 16 |
| Later excluded-ID test | 4,074 → 4,084 | 25 → 22 |

These are same-sensor spatial-mask proxies. They cannot establish that a real
vehicle observed by one sensor is the same vehicle seen by the next sensor.
Overlapping masks/scenarios are correlated. Unsupported identities remain blank.

## Published same-hour comparison

The validated hour was republished with the new timing metadata; the rolling
writer uses the same policy for future Florida updates.

- 64 bounded bursts corrected; 6,240 full-rate frame timestamps adjusted.
- Observed fragments: 31,557 → 31,492, with unchanged raw recording storage.
- Local dashed estimates: 1,456 → 1,406. Some artificial discontinuities disappear
  from observed tracks, so a lower dashed count is not itself a loss of coverage.
- Between-intersection estimates: **2,249 → 2,372**. Counts are hypotheses, not
  verified recovered vehicle identities.

| Adjacent pair | Eastbound before → after | Westbound before → after |
|---|---:|---:|
| Cranes–Hattaway | 49 → 50 | 60 → 59 |
| Hattaway–Renaissance | 185 → 198 | 59 → 70 |
| Renaissance–Essex | 110 → 116 | 263 → 267 |
| Essex–Plaza | 514 → 536 | 271 → 295 |
| Plaza–Palm | 210 → 219 | 75 → 79 |
| Palm–Boston | 407 → 430 | 46 → 53 |

The UI reports timing corrections and paired test results. The two dashed layers
remain separate; original receipt times are inspectable by hovering. Finch is
unchanged. Florida collectors were not stopped; only the figure writer and
local dashboard were reloaded. The writer retains the 30-minute figure update
and 90-minute raw retention schedule.

## Code and evidence

- `deepctm/delivery_timing.py`: bounded preprocessing, independent of positions.
- `deepctm/validate_delivery_timing.py`: paired hidden-position comparison.
- `deepctm/validate_delivery_matching.py`: paired spatial association comparison.
- `config/reconstruction/florida-delivery-timing.json`: enabled policy, frozen
  bounds, test summary and report hashes.
- `data/reconstruction/delivery-timing-review/`: protocols, detailed scores,
  clock audit, bootstrap, deployment comparison and browser verification.

Run validation with `.venv-deepctm/bin/python -m deepctm.validate_delivery_timing
--output <review-directory>` from the repository root; then run
`deepctm.validate_delivery_matching` with the same output directory. The first
command produces the temporary paired candidate required by the second. It
reads a consistent temporary buffer copy and never rewrites raw recordings.

Verification: 69 scientific regression tests, six API tests, JavaScript syntax
check and diff checks passed. Tests explicitly check burst recovery, unchanged
payloads/original receipts, real frame loss, absent return anchors, clock resets,
duplicate timestamps and session separation.
