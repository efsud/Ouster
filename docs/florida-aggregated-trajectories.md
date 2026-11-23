# Florida aggregated trajectory view

The **Aggregate trajectories (mean speed)** checkbox replaces individual trajectory lines with a time–distance speed heatmap. Uncheck it to restore the existing observed and estimated trajectory layers. The aggregation toggle is recorded in the link as `aggregate=1`; existing visitors otherwise retain the individual-line view.

Default cells cover 10 seconds and 10 metres. Available time cells are 5, 10, 30 and 60 seconds; distance cells are 5, 10, 20 and 40 metres. Intersection, direction and object filters apply. Mouse-centered zoom and panning retain the same bins, so zooming does not change the underlying summary. Larger bins smooth variation but conceal finer differences.

Only retained recorded points contribute. For each cell and sensor, average each session/object ID's observed speeds, then average those object means with equal weight. Classification changes and split fragments do not introduce a new ID. Duplicate timestamps for the same ID inside a cell count once. Different sensors and sessions remain separate. No reconstructed or estimated points enter these statistics.

For example, object A has speeds 2 and 8 m/s in a cell; object B has one observation at 20 m/s. A's mean is 5, so the displayed cell mean is (5 + 20)/2 = 12.5 m/s, with two local IDs and three samples. It is not the sampling-frequency-weighted mean of 10 m/s.

Red indicates slow or stopped observations, yellow about 10 m/s, and green 20+ m/s. Gray means **no retained observations**, not verified zero traffic or an outage. Hovering a tile reports its site, full time/distance interval, mean speed, local-ID count and sample count. Where sensors occupy the same cell, side-by-side strips show each sensor's separate summary; the strips cover the same full time interval and are not finer time bins.

This view can expose platoons and recurring slow regions despite individual fragmented tracks. It does not reconstruct any missing vehicle or fill unobserved roadway. Counts are not corridor-wide unique vehicles, flow or density. Short and wholly stationary fragments can be omitted by the existing retained-track pipeline. Timing and alignment remain subject to the same qualifications as the original figure.

## Validation

Nine Node tests verify weighting, ID/session/site separation, classification changes, duplicate/conflicting timestamps, filters, missing versus stopped cells, fixed-bin boundaries, invalid samples and input configuration. On the recorded 13:52:55–14:52:55 EST window of November 23, the JS engine matched an independent Python check at all seven sites: 45,519 eastbound vehicle cells from 669,115 retained samples. Westbound yielded 32,466 cells and the eastbound pedestrian filter 358. The source was unchanged, speeds were finite and nonnegative, and single-site filtering agreed with filtering the all-site result. These are software and recorded-input consistency checks, not validation of unobserved traffic.

Run `node --test dashboard/tests/test_trajectory_aggregation.js`. Evidence is saved under `data/reconstruction/aggregation-review/`. The engine is `dashboard/static/trajectory-aggregation.js`; rendering and controls are in the Florida rolling figure. Finch and KPI calculation inputs are unchanged.
