# Thirty-minute signal sample

Run `.venv/bin/python scripts/capture_signal_sample.py` in an interactive Terminal.
Enter credentials privately. The script subscribes only to Driftwood phase changes,
starts its 30-minute timer on the first phase message, and saves each original event
under ignored `data/signal-samples/`. Keep the computer awake and Terminal open.
It does not stop or change the existing dashboard recorder.

`raw.jsonl` preserves API messages and computer receipt times. `decoded.json`
and `report.md` decode phase status numbers, keeping sensor timestamps separately.
For example, phaseNumber 2 with status 1 becomes phase 2 GREEN; it does not become
an assigned direction. Absolute snapshots and repeated reports remain identifiable.
The report records interrupted or failed runs rather than claiming a complete sample.

Validation: Python compilation and a small decoder check passed (green status,
omitted invalid status and envelope timestamp fallback). Live capture remains
unvalidated until real messages arrive. A change-only stream cannot prove healthy
reception during silence. Signal timing and inter-phase relationships can be studied
after capture; direction assignments require a verified configuration join. Corridor
coordination requires synchronized observations at multiple intersections.

## Decoding a completed sample

Run `.venv/bin/python scripts/analyze_signal_sample.py data/signal-samples/<capture>`.
This saves `timing-analysis.json` and `timing-report.md` beside the original data.
Timing uses differences between sensor timestamps, with receipt times reported separately.
For example, an observed green onset at sensor time 18:43:00.604629 and yellow
onset at 18:44:00.104995 span 59.500366 seconds. These timestamps have no verified
timezone and do not themselves establish a movement direction.

The October 5 Driftwood capture completed with 498 messages in 30 minutes.
It included 301 startup absolute snapshots spanning about 30 seconds of older
sensor time, plus one later absolute snapshot. They are initialization evidence,
not hundreds of phase changes. An 80.24-second receipt gap is flagged and excluded
from episode/cycle calculations crossing it; change-only silence is not proof of loss.
The observed repeated pattern was approximately 130 seconds. Paired states were
1/5, 2/6, 4/8, 9/11, 10/12 and 13/14. These are not physical-light counts.

Some reported YELLOW intervals were approximately 15 or 27 seconds. Do not
interpret all phase channels as conventional vehicle yellow lamps without vendor
confirmation of channel semantics. The saved Phase Details configuration lacks
labels 9 and 13. Matching labels to live numbers remains a hypothesis.

Validation: a synthetic test confirms initial/final censored episodes are excluded,
duplicate reports preserve the original onset, and snapshots/long gaps reset timing.
All original observations remain in the ignored local data directory for audit.
