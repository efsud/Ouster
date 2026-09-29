# Recorded history and provisional CTM

Live collectors now save received events continuously as well as updating the live map. The Toronto launcher no longer stops raw recording after one hour. Raw records still expire 30 days after receipt. Keep the collector running and the computer awake. To request a bounded recording instead, use `--record-duration 3600`; live viewing then continues after recording ends.

## Using the historical tab

1. Choose the intersection in Dataset.
2. Choose From/To in your computer's local time, or click **Use latest recorded hour**. The shortcut rounds both boundaries down to minutes. Each calculation covers at most 24 hours.
3. Open the CTM assumptions and review the sensor-local count line, direction, width, approach length, lanes, speeds, jam density and signal timing.
4. Click **Calculate & save CTM**, then choose a KPI. The chart and table show five-minute windows in UTC. Missing coverage produces gaps, not zeros.
5. Download the JSON to retain the results, assumptions, model version, input counts and limitations. Each calculation is also saved locally under ignored `data/ctm-history/`.

Changing intersection, dates or assumptions clears the previous result. The ordinary observed-KPI cards remain separate and still require verified metadata. Optimization and the educational CTM explorer are unchanged.

## What the calculation does

`dashboard/historical_ctm.py` streams the selected sensor's stored FRAME events. A vehicle must be observed on both sides of the assumed count line, in the selected direction, within its width. Track IDs are namespaced by collector session; one crossing is accepted per ID/session in the selected interval. Reused IDs within that interval can therefore undercount. Gaps over three seconds, nonpositive timestamp deltas, invalid coordinates and implausible jumps are excluded. New appearances and SDK message counts are not treated as traffic flow.

Absolute sensor timezone remains unverified. Only this explicitly provisional calculation allows those quarantined frames, using sensor timestamps for relative track gaps and receipt timestamps for chart windows. Network buffering can shift the apparent demand. Continuous receipt coverage must reach 80% for a window to run; this is not proof of scene visibility or trajectory completeness. There is no claim that the paper's 15-valid-traversal requirement is satisfied by line crossings.

Crossings are converted to uniform demand within each window and applied to the upstream end of an assumed single approach. A triangular fundamental diagram limits sending/receiving flow; an assumed signal gates the downstream boundary. Cells are approximately 50 m and time steps are one second. Initial occupancy is empty; after a coverage gap the model resets. The first valid interval is labelled warm-up. Signal offset is relative to the selected range start, not a verified signal clock.

Example: 15 directional crossings in five minutes imply assumed demand of 180 vehicles/hour. With sufficient capacity the model admits approximately 15 vehicles, while departures and queue depend on road and signal assumptions. These are estimates of one assumed approach, not the intersection's total traffic.

## What each output means

| Output | Interpretation |
|---|---|
| Excess-time proxy | Model excess vehicle-seconds divided by departures in that window; not observed mean control delay |
| Queue P95 | P95 of downstream contiguous congested-cell length; roughly 50 m spatial resolution |
| Admitted approach flow | Model entries divided by reporting duration |
| Outflow per green-hour/lane | Model departures divided by assumed green time and lanes; not measured queued discharge |
| Residual-queue cycles | Fraction of model green endings with downstream congestion; not the paper's validated split-failure metric |
| Stopped delay / AOG | Unavailable: aggregate CTM does not supply the required individual trajectories/phase observations |

Upstream waiting outside the modelled approach is reported as backlog, but excluded from approach delay. Partial window cycles and empty initial conditions affect results. There is no turning model or cross-sensor tracking. These results are never used as observed KPI windows or anomaly ground truth.

## Validation

Automated checks cover directional crossings, session namespaces, repeated IDs, censored tracks, missing coordinates, observation gaps, signal sensitivity, conservation, coverage resets and unsupported outputs. The full Python suite passes 55 tests. A real Driftwood query after recording restarted processed 3,794 frames and found 18 assumed-line crossings; only one five-minute interval met the coverage threshold. Conservation residual was below 1e-12 vehicles. This verifies software execution on recorded input, not field calibration or KPI accuracy.

Browser validation passed against real recorded frames: 12 reporting intervals, KPI switching, unavailable AOG, JSON download, mobile width and clearing results on site change.

## Continuous archive update

The Historical CTM panel now displays the full retained receipt-time range and whether new raw events have been saved within 30 seconds while the collector is in recording mode. Refresh recording status to check again. A running process alone does not count as active recording. Analysis accepts arbitrary saved date ranges up to 24 hours per calculation, producing five-minute results throughout that range, with gaps retained. You can repeat for another day. Saving continues independently of the displayed tab. Closing the collector, sleeping or shutting down the computer interrupts capture; the dashboard cannot recover unreceived live frames. Existing raw retention is 30 days, while saved CTM results remain on disk.
