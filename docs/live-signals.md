# Real-time signal phase reports

The existing collector already subscribes to FRAME, PHASE_CHANGE and LOOP_CHANGE. It uses the SDK's combined singleton queue so all event types can be archived together with a receipt timestamp and collector session. A separate `get_phase()` consumer would require a separate non-singleton connection; it is unnecessary for the current combined recorder. No extra credentials or sensor configuration changes were needed.

The Live network tab now shows phase reports for the selected intersection, refreshed once per second from saved events. `dashboard/signals.py` implements reconstruction; `/api/signals?site=...` is read-only. The raw phase events continue to be saved by the existing continuous recorder.

An absolute snapshot replaces the entire phase dictionary, including removing old phases. A delta changes only its listed phases. A new collector session or a receipt gap above five seconds clears completeness and prior phase states. Older per-phase timestamps cannot overwrite newer ones. Protobuf's omitted zero status is interpreted as INVALID. Unknown codes are labelled UNKNOWN.

Example: an absolute report `{1: GREEN, 2: RED}` followed by a delta `{1: YELLOW}` produces `{1: YELLOW, 2: RED}`. An absolute empty list then clears both phases.

To avoid scanning the whole multi-gigabyte archive for a live display, reconstruction starts with the last ten minutes and then reads incrementally. If no absolute snapshot exists in that span, reports are marked UNCONFIRMED and show their last reported value. They are not presented as a complete current signal plan. Disconnected streams and reports older than 180 seconds are also unconfirmed; this timeout is a conservative display policy, not a vendor signal-cycle specification. Other object traffic does not establish the freshness of a particular phase.

The sensor timestamps currently lack a verified timezone. Display age uses receipt time and does not measure upstream latency. The panel does not infer northbound/southbound or turning movements from phase numbers, coordination offsets, or active timing plans. Verified phase-to-movement mapping and clock synchronization are still required before these reports can replace assumed CTM signals or support arrivals-on-green KPIs.

Validation: unit tests cover absolute replacement, incremental changes, empty snapshots, reconnect/session reset, receipt gaps, missing/default status, stale reports and regressing timestamps. All 60 Python tests pass. Real phase changes were observed in the saved Toronto stream, including Driftwood.
