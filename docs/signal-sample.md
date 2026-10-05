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
