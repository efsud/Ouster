# Florida: same-color extensions for remaining gaps

Implemented November 23, 2026. The requested method is an additional experimental layer; it does not replace existing estimates or edit recorded positions.

## What changed

Unused departures are processed chronologically. Candidate arrivals must have the same speed-color band (1 m/s bins, saturated at 20 m/s), compatible direction and motion, and an unused endpoint. The nearest candidate is ranked by spatial error relative to the departure's constant-slope projection at the arrival time. Near ties within 0.25 m remain unresolved.

The first 80% of an estimated gap retains the departure slope. The last 20% makes the smallest linear endpoint correction, limited to a 0.5 m/s speed adjustment. A nonzero endpoint discrepancy cannot be closed while preserving exactly the original slope for the entire gap.

Example: departure position 0 m at 10 m/s, followed 10 seconds later by a same-color arrival at 101 m. The initial eight seconds reach 80 m at 10 m/s. The last two seconds travel at 10.5 m/s to reach 101 m. Neither observed endpoint is moved.

Local gaps are limited to 90 seconds and 10 m extrapolation discrepancy; adjacent-intersection gaps to 120 seconds and 20 m. Other physical checks can impose tighter limits. Local matching checks session, sensor elapsed time, lateral separation, movement compatibility and intervening observations. Same object identity can survive a classification change. Different identities require compatible classifications. Intersections are linked only through existing corridor entry/exit eligibility rules.

## How to see it

Open http://127.0.0.1:8775/florida_rolling.html?between=1 on this computer. The third checkbox enables the new method by default. The first two checkboxes still control local and corridor estimates. Use **Show an added local connection** or **Show an added corridor connection** to select relevant sites and zoom directly to an example. The example is highlighted; estimates remain dashed and speed-colored. Visible counts change with direction, object and site filters.

For the inspected 13:14:49–14:14:49 EST recording window, the method added 10 local and 7 adjacent-intersection proposals across both directions. Existing connections and observations were preserved. The eastbound default view showed 7 local and 5 corridor additions. These counts describe that snapshot, not all future updates.

## Recorded-data validation

Fixed parameters were tested by masking recorded trajectory portions. Development used the earlier half of the hour; the later test excluded development identities with a 30-second embargo. Existing bidirectional matches reserved their endpoints before the new method ran. Object identities were used for scoring, not candidate ranking.

| Additional proposals | Earlier development | Later test |
| --- | ---: | ---: |
| Correct local matches | 116 | 75 |
| Wrong local matches | 9 | 13 |
| Correct spatial-proxy matches | 0 | 0 |
| Wrong spatial-proxy matches | 0 | 0 |

The later local test therefore achieved 85.2% precision among additional accepted proposals. Position MAE for its correct matches alone was 0.050 m; that value excludes the 13 wrong identities and must not be interpreted as overall matching accuracy. Repeated masks are correlated. The endpoint-association benchmark omits production's additional local 2D/clock gates, so it is not a direct field error rate.

There is no demonstrated extra recovery in the spatial proxy and no verified identity truth between sensors. The seven displayed corridor proposals are hypotheses, not established same-vehicle matches. Similar speeds and slopes can belong to different cars. This evidence does not establish superiority over the existing method, and unsuitable or ambiguous gaps remain blank.

Validation artifacts are in `data/reconstruction/residual-color-review/`: protocol, development results, test results and report. Browser screenshots show local and corridor examples. Software verification passed 42 trajectory tests and 6 dashboard API tests, plus JavaScript syntax and whitespace checks.

## Implementation

`deepctm/residual_color_slope.py` reserves existing endpoints and adds remaining proposals using `deepctm/color_slope.py`. `deepctm/reconstruction_layers.py` publishes them separately. `config/reconstruction/florida-residual-color.json` enables the layer. `deepctm/validate_residual_color.py` reproduces the masked-data comparison. The Florida figure renders the layer independently; Finch is unchanged.
