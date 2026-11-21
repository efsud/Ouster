# Intersection KPI drill-down — review of the 2026-09-29 attachment

The newly attached LaTeX document is byte-for-byte identical to
`docs/kpi-specification.tex`; it has not been duplicated or altered. Its Tier-1
summary defines seven operational KPIs. The broader domain table includes
representative/Tier-2 measures, and saturation flow is discussed as a conditional
headway estimate; neither replaces the seven Tier-1 cards.

| KPI | Units | Required stored/annotated inputs |
| --- | --- | --- |
| Control delay | s/veh | Observed entry and stop-line arrival, approach length, free-flow speed |
| Stopped delay | s/veh | Complete entry-to-exit observations, valid speeds, stopped threshold |
| Queue P95 | m | Lane membership, stop line, queue region, spacing, visible regular samples |
| AOG | % | Stop-line arrivals (approximately 3 m tolerance), mapped phases, verified synchronized clocks |
| Split failure | % cycles | Complete cycles, effective-green end and visible residual queues |
| Approach volume | veh/h | Directional entry/count-line crossings and physical-track deduplication |
| Discharge | veh/h/lane | Queued stopped-to-moving departures during effective green, green duration and lanes |

The paper requires at least 15 valid traversals, coverage at least 80%, and
exclusion of gaps above 3 s. Censored tracks may support an observed crossing but
not full-traversal delay. Signal estimates require clock synchronization. Queue
membership is more than low speed. Discharge is real-time only. The prose/table
specifies per-lane discharge, while its displayed equation omits the explicit
lane divisor; the existing implementation follows the stated per-lane units.

## What the recorded data currently supports

The database contains real raw sensor events, but only 36 synthetic KPI windows.
There is no local verified scene metadata. Raw timestamps remain quarantined for
missing timezone information. Consequently no real value for these seven
operational KPIs can currently be shown from the archive under the paper's rules.
A rotating approximate map is a visualization and does not establish measurement
geometry. Received-message counts are not approach volumes or unique vehicles.

## Implemented behavior

Clicking a name in the Live network inventory reveals and scrolls to a saved-data
KPI panel. It lists all seven definitions, units, cadence and explicit reasons for
unavailable values. The last saved-hour receipt summary describes available data;
it is not misrepresented as a traffic KPI. Norfinch, with no saved events, shows
that fact rather than another site's values.

`/api/site-kpis?site=...` reads stored `sdk-derived` and `annotated-import` windows
only, excluding synthetic examples. Approach and window selectors display the
selected saved result without averaging percentiles, rates or approaches. Each
window carries its period, source and quality evidence. Values are labelled
provisional, not field validated. Daily discharge is suppressed. “Open historical
performance” selects the same sensor in the historical tab. No raw archive is
modified and the independent live stream continues.

## Worked example and validation

For a saved northbound five-minute window with control delay 12 s/veh followed by
a window with 24 s/veh, the default card shows 24; selecting the earlier window
shows 12. A southbound value of 99 is not mixed into either result. This example
is a unit-test fixture, not a Toronto measurement.

50 Python tests pass, including seven unavailable cards for missing observations,
exclusion of synthetic/other-site values, approach and window selection, retention
of quality evidence, quarantine explanations and suppression of daily discharge.
Browser verification covers the actual Driftwood/Norfinch stored-data states, seven
cards, site switching, the historical tab link and mobile layout. Field KPI
validation remains blocked on the required clock/geometry/annotation inputs.
