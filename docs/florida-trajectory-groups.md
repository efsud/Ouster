# Florida trajectory groups and individual reconstruction

The dashboard now interprets aggregation as **unsupervised groups of similar
individual trajectories**, following the user's clarification. It replaces the
mean-speed-cell control. Open `/florida_rolling.html?groups=1`, select **Group
similar trajectories**, and use **Show a group** or the group selector. Speed
colors remain available; membership colors identify groups. Every displayed
solid trajectory retains its recorded positions. The earlier `aggregate=1`
link opens the new grouping view.

## What makes two trajectories similar

`deepctm/trajectory_groups.py` compares crossing times and speeds at common
10-m road stations, using only actually observed segments. It never interpolates
across an observation hole longer than 1.5 seconds while computing features.
Candidates must share direction and object family and have compatible known
movement labels. Available lateral endpoints constrain spatial similarity;
full lateral paths are not retained, so this is not verified lane clustering.

The fixed candidate thresholds are: at least three shared stations, passage-time
lag at most 20 seconds, time-profile residual at most 4 seconds, speed-profile
difference at most 3 m/s, and lateral-center difference at most 2.5 m. These
thresholds are exploratory engineering settings, not field-calibrated truth.
Density support requires three **distinct sensor/session/object identities**.
Classification changes and multiple fragments of one object do not add support.
Every group has an actual observed representative member. Bounded neighborhoods
prevent a chain of nearby cars from joining an entire hour into one group.
Sparse, short, incompatible and isolated paths remain ungrouped.

For example, three vehicles follow the same path a few seconds apart with
similar acceleration profiles. They can form a group while retaining three
separate lines. A vehicle traveling the other direction, turning off the road,
or passing much later does not automatically join that group. Group membership
does not establish that two fragments belong to the same vehicle.

## Using groups to reconstruct individuals

**Within a sensor:** `deepctm/local_group_prior.py` excludes every fragment of
the target object from its donor groups. It assigns the target using visible
observations, fits other vehicles' time/position shifts from the four visible
seconds on either side, and requires at least three independent, continuously
observed peers. Their median shape is a soft prior for one missing segment.
Constrained optimization preserves that individual's measured endpoints and
physical speed/acceleration bounds. It does not replace the observed lines with
the group median. A version/configuration/validation gate protects production.

**Between sensors:** `deepctm/between_group_matching.py` clusters the two views
independently. Three other confident baseline group-pair associations can provide
a travel-time prior. Candidate identities are excluded from their own anchors.
The resulting penalty can resolve a previously ambiguous individual assignment;
movement, physical feasibility, one-to-one assignment and ambiguity checks still
apply. Existing endpoints already used by baseline or experimental layers are
reserved. Group IDs are never treated as cross-sensor vehicle identities.

Additional corridor hypotheses appear in a separate, initially unchecked
**group-assisted connections** control. **Inspect a group-assisted match**
selects its two intersections and time range. Dashed connections retain speed
colors even when the observed trajectories use group colors. Selecting one local
group focuses on its own observed individuals; the match inspection control
switches back to a two-site view.

## Recorded-data validation on November 23, 2026

The frozen 14:52:55–15:52:55 EST source contains 30,966 retained fragments.
Grouping produced 3,015 groups with 20,260 assigned fragments at all seven
intersections in about 23 seconds. These are retained-fragment counts, not unique
corridor flow or recovered missing vehicles. Raw inputs and measured positions
are unchanged.

Local evaluation used chronological development/later-test portions with a
30-second embargo and excluded test identities already observed earlier. Target
hidden samples and all same-ID fragments were excluded from donor grouping.
The prior weight was selected on development using a common baseline-fallback
denominator and frozen before test. The first review attempt was superseded by
`review-002` to correct acceptance-subset differences during weight selection.

| Later local test | Existing method | Group prior |
|---|---:|---:|
| Position MAE on 37 supported masks / 35 IDs | 0.896 m | 0.832 m |
| Speed MAE on those masks | 0.871 m/s | 0.852 m/s |
| Position MAE on all 514 accepted masks, using fallback | 1.515 m | 1.510 m |

There were 832 eligible masks. Supported peer cases were 25 five-second and
12 ten-second masks; **no twenty-second mask had enough support**. Each site
had only 2–8 supported distinct test IDs, below the predeclared ten-per-site
requirement. The local peer policy therefore remains **disabled**. Existing
local estimates remain active. The small pooled improvement does not establish
robust outage recovery.

The spatial benchmark hides 20/50/100-m strips inside recorded sensor views and
includes missing-endpoint scenarios. It compares baseline and group-assisted
individual association on chronological, identity-disjoint portions. On 3,074 later eligible cases, correct assignments increased from 2,451 to
2,455 and wrong assignments remained 79. The gain involved four distinct
vehicles at Essex. On the frozen live-window audit, three additional individual
hypotheses passed the full gates: Essex→Renaissance westbound, Essex→Plaza
eastbound, and Palm Springs→Boston eastbound, supported by 4, 5 and 3 other
anchors respectively. The adapter took about 142 seconds and verified endpoint
reservation. A proxy improvement cannot validate the
actual identity of a vehicle traveling between two sensors. Repeated masks of
one vehicle are not independent evidence.

Evidence stays local:

- `data/reconstruction/trajectory-group-review/groups.json`: memberships,
  original indices, observed representatives, source fingerprint and counts.
- `data/reconstruction/trajectory-group-local-review/review-002/`: protocol,
  frozen input, development/test cases, report and disabled policy.
- `data/reconstruction/trajectory-group-between/20261123/`: fixed protocol,
  spatial masking results and actual-window association audit.

These are software-tested and recorded-data experiments, not field validation.
Provisional geometry, unknown inter-sensor clock offsets and unverified identities
remain limitations. Group estimates do not enter measured KPI inputs.

## Reproduction and dashboard integration

Run the grouping/local/between unit tests with the scientific environment:

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 \
  .venv-deepctm/bin/python -m unittest \
  deepctm.test_trajectory_groups deepctm.test_local_group_prior \
  deepctm.test_between_group_matching
```

`deepctm/trajectory_group_layer.py` publishes original-track-index assignments
inside the reconstruction response. The browser uses them only when the source
snapshot timestamps agree; a new hour or failed group response falls back to
showing observations, rather than filtering everything out with stale IDs.
The rolling reconstruction worker recomputes groups for new hourly snapshots.
Finch rendering remains compatible with the shared JavaScript, and this change
adds no collection or site-configuration actions.

The large rolling API response is now encoded once per changed file, with an
opaque version token and at most two cached encoded region payloads. Subsequent
browser polls return `unchanged`; only one browser refresh can be in flight.
Expiry is rechecked even for an unchanged token. The local check returned the
seven-site hour in 2.92 seconds and the next poll in 0.003 seconds / 204 bytes.
Seven cache tests cover expiry, concurrent loading, changed files with unchanged
timestamps, region isolation and malformed replacements. The 39 grouping,
reconstruction-prior, association and cache tests, plus 53 existing reconstruction
regression tests, passed. Browser interaction checks are performed on the live
rolling page after publication.
