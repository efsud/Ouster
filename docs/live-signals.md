# Real-time signal phase reports

The existing collector already subscribes to FRAME, PHASE_CHANGE and LOOP_CHANGE. It uses the SDK's combined singleton queue so all event types can be archived together with a receipt timestamp and collector session. A separate `get_phase()` consumer would require a separate non-singleton connection; it is unnecessary for the current combined recorder. No extra credentials or sensor configuration changes were needed.

The Live network tab now shows phase reports for the selected intersection, refreshed once per second from saved events. `dashboard/signals.py` implements reconstruction; `/api/signals?site=...` is read-only. The raw phase events continue to be saved by the existing continuous recorder.

An absolute snapshot replaces the entire phase dictionary, including removing old phases. A delta changes only its listed phases. A new collector session or a receipt gap above five seconds clears completeness and prior phase states. Older per-phase timestamps cannot overwrite newer ones. Protobuf's omitted zero status is interpreted as INVALID. Unknown codes are labelled UNKNOWN.

Example: an absolute report `{1: GREEN, 2: RED}` followed by a delta `{1: YELLOW}` produces `{1: YELLOW, 2: RED}`. An absolute empty list then clears both phases.

To avoid scanning the whole multi-gigabyte archive for a live display, reconstruction starts with the last ten minutes and then reads incrementally. If no absolute snapshot exists in that span, reports are marked UNCONFIRMED and show their last reported value. They are not presented as a complete current signal plan. Disconnected streams and reports older than 180 seconds are also unconfirmed; this timeout is a conservative display policy, not a vendor signal-cycle specification. Other object traffic does not establish the freshness of a particular phase.

The sensor timestamps currently lack a verified timezone. Display age uses receipt time and does not measure upstream latency. The panel does not infer northbound/southbound or turning movements from phase numbers, coordination offsets, or active timing plans. Verified phase-to-movement mapping and clock synchronization are still required before these reports can replace assumed CTM signals or support arrivals-on-green KPIs.

Validation: unit tests cover absolute replacement, incremental changes, empty snapshots, reconnect/session reset, receipt gaps, missing/default status, stale reports and regressing timestamps. All 60 Python tests pass. Real phase changes were observed in the saved Toronto stream, including Driftwood.

## Signal indicators on the map

Each mapped intersection now has a signal badge at its reference point. At corridor zoom it shows counts of red, yellow, green and unconfirmed/invalid phases. At zoom 17 and above it shows numbered phase lights for reported non-invalid phases. Click a badge for all phases and completeness details. Phase numbers do not indicate physical signal-head locations or movement directions.

The browser requests the visible network's signal reports every second using `/api/network-signals`. Confirmed reported states use red/yellow/green; other states remain grey. If dashboard responses stop for more than five seconds, cached map colours turn grey automatically. Changing networks replaces the markers. Recording and sensor configuration are unchanged.

## Individual light display revision

The map now shows one three-lamp traffic-light symbol per channel whose reported status is RED, YELLOW or GREEN, at every zoom. Only the matching lamp illuminates when that state is confirmed; unconfirmed states have all lamps dark and a question mark. Invalid API slots are omitted. A Driftwood snapshot contained 12 valid-status channels and 52 invalid slots; this is not a verified count of physical heads, since several physical lights may share one phase. The read-only phase metadata request failed with a network error during this update, so no physical count or movement mapping was inferred. Symbols remain grouped schematically at the intersection centre.

## Recovering stopped local services

If objects vanish, first check whether the dashboard port and recorder supervisor are running and whether saved receipts are fresh. During the September 30 check, the supervisor and port 8765 server were absent, several collectors had exited with EOFError, and Driftwood frames were over five hours old. Stale frames must not be replayed as live. Double-click `scripts/connect_toronto.command` to start a supervised continuous session in your own Terminal at the normal port 8765, entering credentials privately. Keep that Terminal running and the computer awake. This avoids depending on the lifetime of an agent tool terminal, but does not provide service across shutdown or computer sleep.
