# DeepCTM validation record — November 4, 2026

## Implemented and software-tested

- Read all 12 supplied paper pages; visually inspected architecture and equations, including MMCE normalization. See `deepctm.md` for the equation-to-code mapping and unresolved author specifications.
- Read-only receipt audit of the existing 104 GB database: Weston/Signet overlap in 104 fifteen-minute bins with at least 80% receipt coverage. Longest run: 54 bins (13.5 hours). This audit includes all raw event types, so it is not proof of continuous valid FRAME data. Jane has no stored rows. New training uses the separately authorized 24-hour capture.
- Nine DeepCTM unit tests pass: 15-minute CTM conservation/jam bounds, finite gradients through recurrent/gate/PEC and directional paths, virtual target masking, deterministic evaluation, known Edie calculation, session/gap rejection, rectangle clipping, split-boundary/gap exclusion and insufficient-data refusal.
- All 65 pre-existing dashboard tests pass. JavaScript syntax and Python compilation pass.
- A two-epoch synthetic training smoke run produced checkpoints, chronological splits (50/12/13 sequences), baseline metrics and finite mass diagnostics. This is execution validation only, not model-quality evidence. Its artifacts remain in `data/deepctm/software-smoke/`, never the field result endpoint.
- Browser checks cover live capture status, missing trained results, direction selection, desktop/mobile width and a separate synthetic results-rendering fixture. No JavaScript errors were observed. Screenshots are private under `data/deepctm/qa-*.png`.

## Actual reception verified

Fresh frames from both Weston and Signet were saved to the compressed capture beginning **November 4, 2026, 22:45:55 America/Toronto**, ending at **November 5, 2026, 22:45:55** (03:45:55 UTC on November 6).

A bounded inspection of the first 3,000 received records per site yielded four complete one-minute windows. The feature extractor accepted both directions in all four windows. Receipt coverage after relative-clock checks was approximately 96.9–99.1% at Weston and 98.6–99.5% at Signet. This verifies real input processing, not road calibration, detection completeness or signal synchronization. One-minute checks do not substitute for the final fifteen-minute training coverage audit.

## Still pending

The 24-hour capture, final valid-window audit, actual training, validation-selected checkpoint and held-out field-input results are pending. The supervisor runs extraction/training after collection; the follow-up checks failure or completion. Keep the recorder Terminal open and the computer powered on. Verified road geometry, sensor clock synchronization, independent traffic counts and a multi-day test remain necessary for field validation. The running model should remain labelled provisional even if its one-day errors are small.
