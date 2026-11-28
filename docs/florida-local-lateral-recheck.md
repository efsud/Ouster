# Florida local-gap recheck: all seven intersections

23 November 2026. Reused the existing, fixed same-ID local lateral-motion model on a later hour, 13:14:49–14:14:49 EST. The model, 10-second maximum gap, clock checks, lateral limits, and longitudinal physics constraints are unchanged. This is a narrower test of short same-ID missing positions, not a claim that every disconnected line belongs to a known vehicle.

The earlier model had been enabled at Cranes Roost, Hattaway, Renaissance and Essex. It withheld Plaza because its previous test speed error was 1.27 m/s, above the 1 m/s limit. Boston and Palm Springs lacked adequate identity counts. The earlier study is preserved in `data/reconstruction/local-lateral-review/`.

## Later hidden-data check

The first half of the later hour is development; the second half excludes identities seen in the first half and uses a 30-second embargo. Five- and ten-second masks conceal recorded positions. Reconstruction sees actual SDK timestamps and lateral endpoint context; hidden longitudinal/lateral positions are used only for scoring. No raw endpoints were missing. Cases are stratified toward lateral movement, and multiple mask lengths may share a vehicle; the numbers are not corridor recall or independent vehicle counts.

| Intersection | Development accepted IDs | Later test accepted IDs | Later test position MAE | Speed MAE | Lateral MAE | Decision |
|---|---:|---:|---:|---:|---:|---|
| Cranes Roost | 15 | 16 | 0.83 m | 0.53 m/s | 0.29 m | Keep enabled |
| Hattaway | 38 | 41 | 1.14 m | 0.84 m/s | 0.39 m | Keep enabled |
| Renaissance | 56 | 70 | 1.03 m | 0.69 m/s | 0.24 m | Keep enabled |
| Essex | 17 | 15 | 0.83 m | 0.78 m/s | 0.26 m | Keep enabled |
| Plaza Entrance | 18 | 17 | 1.21 m | 0.82 m/s | 0.39 m | Enable existing method |
| Palm Springs | 10 | 9 | 1.02 m | 0.67 m/s | 0.39 m | Still insufficient test IDs |
| Boston | 4 | 2 | 0.65 m | 0.78 m/s | 0.54 m | Still insufficient IDs |

Across all sites the fixed method accepted 178 test masks on 170 distinct identities: longitudinal MAE 1.03 m, speed MAE 0.73 m/s, lateral MAE 0.31 m, and no numerical physics violations. Plaza's development speed MAE was 0.77 m/s and later test MAE was 0.82 m/s. Its later evidence meets the existing site safeguards; this does not erase the earlier failure. Monitor the policy on further recordings.

Only Plaza was newly enabled. The inspected hour contains one additional eligible Plaza connection; no thresholds were loosened to increase that count. The code already supports this site through `enabled_sites` in `config/reconstruction/florida-local-lateral.json`. Existing local paths and all observed positions are preserved.

## Remaining local limitations

The same-ID audit found sensor/receipt elapsed-time disagreement at every site, often shared by several cars at the same frame boundaries. Examples include receipt gaps of 2.39 seconds with only 0.6 seconds of SDK elapsed time. Those are delivery-timing discrepancies, not evidence that the car disappeared for the entire plotted gap. They must not be bridged by relaxing the clock test.

Other rejected proposals have inconsistent direction, insufficient observed endpoint context, substantial lateral motion, or long disappearances without recording-outage evidence. Stationary fragment filtering and object-class restrictions also affect coverage. Neither the local test nor a plausible connecting curve proves that a trajectory left the corridor. Unresolved gaps must remain separately counted.

The method is suitable for experimental path visualization. It does not establish accurate stop time, travel time, signal state, or other operational KPI values inside an actual missing interval. Later test stop recall was 0.5 for the few accepted masks with hidden stops.

Reproduce with `.venv-deepctm/bin/python -m deepctm.validate_local_lateral --output <new-folder>` while the corresponding raw hour remains retained. Artifacts for this check are in `data/reconstruction/all-sites-local-review/`: protocol, development/test cases, per-site summaries, report and deployment decision. Earlier results remain unchanged.
