# Florida corridor reconstruction: all-intersection review

23 November 2026. This review covers all seven intersections and twelve directed adjacent links. Its purpose is to improve reconstruction without treating a plausible connecting curve as recovered vehicle identity or measured KPI data.

## Changes delivered

- Added a recurring gap census to each published Florida reconstruction window, displayed in **All seven intersections: remaining gaps and KPI readiness**. It separates observed same-ID gaps, baseline estimates, experimental estimates and unresolved gaps. Unknown movements remain unknown rather than being counted as exits.
- Added overlap analysis for all adjacent links. Where both sensors already observe the roadway, concurrent-view association is evaluated separately from filling an unobserved segment. No backward or redundant dashed path is invented to make overlapping trajectories look connected.
- Enabled the existing short same-ID lateral-motion estimator at Plaza Entrance after a later masked-data check. Existing limits are unchanged; one additional path was eligible in the inspected hour. Boston and Palm Springs remain withheld from this particular extension for insufficient test identities.
- Added source provenance to every newly generated between-intersection estimate: both sensor-local object/session keys, fragment references and original observed endpoints. These references allow auditing endpoint reuse without claiming a shared global vehicle ID.

## What the observed gaps represent

For the inspected 13:14:49–14:14:49 EST hour, the initial census found:

| Site | Observable same-ID gaps | Baseline filled | Experimental same-ID filled | Unresolved |
| --- | ---: | ---: | ---: | ---: |
| Cranes Roost | 628 | 109 | 0 | 519 |
| Hattaway | 367 | 13 | 0 | 354 |
| Renaissance | 182 | 34 | 0 | 148 |
| Essex | 743 | 446 | 0 | 297 |
| Plaza Entrance | 252 | 121 | 0 | 131 |
| Palm Springs | 258 | 58 | 1 | 199 |
| Boston | 421 | 275 | 1 | 145 |

These are before the Plaza enablement. Future windows update the table automatically. The census is narrower than the total number of plotted estimates: it requires the same observed sensor/session/object at both ends, and excludes entirely unseen vehicles and changed identities. Gap duration totals can count concurrent vehicles; they are not stream-outage duration or coverage percentages.

The largest rejection category was sensor/receipt elapsed-time disagreement: 974 candidate gaps across these sites. Other causes include lateral displacement, long disappearance without evidence of a stream outage, conflicting direction and insufficient endpoint context. A shared break across many cars is not necessarily a missing car: receipt time can lag while the sensor clock advances normally.

## Between intersections: missing road versus overlap

Cranes Roost–Hattaway's projected coverage overlaps. Median endpoint separation is -4.7 m eastbound and -14.9 m westbound. A forward connection to the other sensor's earlier observed start would go backward in distance. Existing conservative overlap matching found 234 eastbound and 226 westbound hypotheses, plus one in each direction for Hattaway–Renaissance. These associations preserve both original observations; they are not 462 newly recovered missing trajectories.

Palm Springs–Boston instead has an unobserved median endpoint separation of about 108 m eastbound and 129 m westbound. The eastbound audit found 1,791 eligible departure fragments: 440 baseline assignments, 390 with no feasible candidate and 961 with competing ambiguous alternatives. These counts do not prove that any unmatched vehicle left the corridor. Fragments are not unique vehicles.

## Validation and practical limits

The fixed short local estimator was retested across all sites on a later hour. Of 178 accepted test masks from 170 distinct identities, longitudinal position MAE was 1.03 m, speed MAE 0.73 m/s and lateral MAE 0.31 m. Plaza's 17 test identities passed the existing site checks; its earlier failed speed test remains documented. See `florida-local-lateral-recheck.md`.

Overlap matching was checked with alternating partial views of actual recorded trajectories. There were 677 correct and zero incorrect accepted associations out of 1,694 eligible cases across all seven sites. This same-sensor proxy is correlated and does not establish accuracy across two physical sensors. See `florida-overlap-coverage-audit.md`.

The preceding color/slope experiment's 75 correct and 13 incorrect additional local associations are still reported. That layer remains experimental, rather than silently promoted to identity truth. No attempt is made to reach zero gaps by relaxing all ambiguity or timing checks.

## Subsequent timing correction delivered

A separate frozen recording from 13:43:30–14:43:30 EST tested a narrower missing-trigger fix: bounded receipt bursts of 0.5–1.5 seconds. Both preceding and following anchors must be stable; sensor time must remain continuous, fitted rate error at most 1%, and existing 15-second delay/60-second span bounds remain. Original positions, payloads and receipt timestamps are preserved. Missing frames are not generated.

Five sites passed development and later-test checks with sufficient common identities: Cranes Roost, Hattaway, Essex, Plaza Entrance and Palm Springs. Renaissance and Boston retain the earlier timing correction because development evidence was insufficient or regressed. The five-site change is configured in `florida-delivery-timing.json` and applied to newly generated windows.

On the five qualifying sites, later hidden affected gaps increased from **583 to 754 accepted**. Across 571 common masks from 264 identities, mean position error decreased **2.23 to 1.46 m**, and speed error **0.95 to 0.59 m/s**. This compares interpolation against recorded positions on each timeline, not independent true event times. Car trajectories were tested; the frame-level timing correction applies to all classes, whose position errors were not separately evaluated.

A separate later matching proxy improved from **4,101 to 4,195 correct**, with **15 to 11 wrong** matches. It used identical hidden rows and the five-site policy; unchanged sites remained unchanged. All original rows were preserved, and no duplicate receipt keys were found in the frozen comparison. Details and reproducible scripts are in `docs/florida-moderate-delivery-timing.md` and `data/reconstruction/moderate-delivery-validation/`.

## KPI boundary

Estimated overlays remain separate from observation-based KPI inputs. They cannot presently establish corridor travel time, volume deduplication or stop/delay measures for hidden portions. In particular, a connected path can miss a hidden stop while having a small mean position error. A valid KPI report must disclose available coverage, input geometry and clock status, identity uncertainty and which quantities are measured or model-derived. Neither a visually complete figure nor a same-color match supplies that evidence.

The model is not yet gap-free or field-validated for corridor KPIs. Unresolved cases stay visible in the audit instead of being falsely classified as corridor exits. The live dashboard remains at http://127.0.0.1:8775/ and the Florida figure at http://127.0.0.1:8775/florida_rolling.html?between=1 on this computer.
