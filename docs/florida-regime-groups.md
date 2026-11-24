# Florida: learning missing paths from local groups

> Status: inactive in the live dashboard at the user’s request on November 24.
> The previous analysis and figure controls have been restored. This document,
> the experimental model and its validation artifacts are retained for reference;
> they do not change the displayed trajectories.

## What your drawing changes

Your November 24 drawing distinguishes two things: blue outlines identify similar
parts of several vehicles' trajectories; purple strokes propose an individual
vehicle's missing connection. The implementation now keeps these separate.

A whole vehicle track is no longer the unit of the new grouping. A vehicle can
join a stopped queue group, a slow group, and a faster group at different times.
Grouping compares numeric speed, time–distance slope, nearby time and road
position, a lateral-position proxy, and compatible observed movements. Using
numeric speed matters because the green end of the color scale can represent
several different speeds.

Groups require at least three distinct sensor/session/object identities.
Classification changes do not create another identity. No observed point is
moved or averaged into a replacement vehicle. Group statistics include median
speed and slope, their interquartile spread, and independent member count.

Blue dashed outlines summarize the occupied time bins of these observed groups.
An empty bin stays open. No outline spans an unobserved road section between two
sensors. Long bands in the drawing motivate group correspondence across sites,
but do not establish shared vehicle identities.

## How an individual missing portion is estimated

1. Hide a known portion of one recorded trajectory.
2. Exclude every fragment of that vehicle's local identity from the peer groups.
3. Use only the target's visible positions and speeds before and after the hole
   to find compatible group members.
4. Fit small time and position shifts to the other members' observed paths.
   Require independent donors, a consistent shape, and usable visible context.
5. Learn how strongly the peer shape should influence an endpoint-constrained
   reconstruction. The learned stage is a ridge model conditioned on the target
   endpoints and the group's fit, support and spread. It shares training across
   groups, rather than fitting an unreliable independent model to three cars.
6. Enforce endpoint, speed and acceleration checks. Retain the previous supported
   estimate when the group has insufficient evidence or the learned method has
   not passed its recorded-data review.

For example, several cars may approach at about 12 m/s and then stop. If one car
has a five-second interruption, its visible approach and stop can select peers
showing the same transition. Their shifted shapes suggest where deceleration
occurred inside that car's missing interval. A nearby group continuing at speed
should not supply that stop shape merely because it is close on the plot.

This is supervised learning from self-generated labels: the hidden recorded
positions provide training answers. Your hand-drawn strokes guide the design;
they are not automatically treated as measured positions or confirmed matches.

## Recorded-data validation

The source is a frozen November 24 hour, approximately 12:16–13:16 Toronto time,
with all seven Florida sensors. The screenshot's 09:39–09:43 numeric data had
already expired from the 90-minute rolling buffer. The screenshot and its
interpretation are preserved with the new study.

The first 50% trains; the next 25% selects regularization; the final 25% tests
the frozen model. Boundaries have 30-second exclusion buffers. Target identities
do not overlap between partitions. The tests hide 5-, 10- and 20-second portions
and separately report stopped, moving and transition cases. Comparisons use the
same eligible cases and report fallback-inclusive results, so improved error
cannot be claimed merely by rejecting more difficult cases.

The group peers are contemporaneous observations, including observations after
the gap. This is retrospective reconstruction, not a real-time forecast. A
complete outage may leave no peer evidence; those gaps still need to remain
unresolved. Local masking does not verify changed-ID associations, actual
between-sensor identity, operational KPI accuracy, or the correctness of every
remaining blank region.

## Files and reproduction

- `deepctm/trajectory_regime_groups.py`: observed segment grouping.
- `deepctm/regime_group_learning.py`: learned peer influence and guarded adapter.
- `deepctm/validate_regime_group_learning.py`: frozen three-way evaluation.
- `deepctm/regime_between_matching.py`: separate endpoint-group association study.
- `dashboard/static/regime-groups.js`: blue envelopes, filters and group summaries.
- `data/reconstruction/regime-group-study-20261124/`: frozen source, annotation,
  protocols and evaluation artifacts. Raw source and credentials are not committed.

Reproduce a review in a new output directory with:

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 \
.venv-deepctm/bin/python -m deepctm.validate_regime_group_learning \
  --snapshot data/reconstruction/regime-group-study-20261124/snapshot.json \
  --output data/reconstruction/regime-group-study-20261124/reproduction
```

The rolling figure updates remain every 30 minutes. New group memberships must
match the exact displayed snapshot; stale memberships are never applied to a
new hour's track indices.

## November 24 results

The frozen hour contains 29,746 retained fragments. Its 60,412 eligible observed
segments form 5,762 local groups, including 751 stopped groups. There are 8,024
fragments with membership in more than one motion regime. All seven sites take
about 13 seconds to group on this computer when validation jobs are not competing
for CPU time.

The learned stage trained on 201 usable masks from 87 distinct target identities.
The held-out partition contains 415 eligible masks; the baseline reconstructs
321. The table uses those same 321 cases for the last column, retaining the
baseline whenever a peer method abstains.

| Method | Peer-supported masks / IDs | Position MAE with fallback, m |
| --- | ---: | ---: |
| Existing endpoint-based reconstruction | 321 / 157 | 0.8580 |
| Previous whole-fragment peer grouping | 26 / 13 | 0.8510 |
| Local segment groups, fixed peer weight | 105 / 58 | 0.8337 |
| Local segment groups, learned peer weight | 105 / 58 | 0.8330 |

On the 105 common supported masks, learned position MAE is 0.4101 m versus
0.4866 m for the baseline; speed MAE is 0.2893 versus 0.3175 m/s. The learned
weight adds only a small improvement over the fixed-weight local-group method.
Twenty-second position MAE worsens from 0.1793 to 0.2014 m. Stopped cases are
essentially unchanged; transition cases also show a small position regression.

Renaissance alone passes the predeclared per-site gate, based on 16 masks from
10 independent test vehicles. An exploratory identity-cluster bootstrap includes
no gain at this site (95% improvement interval −0.007 to +0.790 m). Therefore the
production viewer keeps established estimates as its default and offers qualifying
learned candidates only as an **optional purple dashed experimental preview**.
This changes shapes of already-supported same-ID gaps; it does not create new
verified matches. In the first published hour, 14 eligible actual gaps were
checked and none had sufficient consistent peer evidence for a learned preview.

The separate endpoint-group association study hides road strips inside recorded
sensor views. In its later half, correct matches increase 2,318 → 2,322 and wrong
matches remain 48. The four added masking cases involve only two distinct
vehicles at Hattaway. The early half adds one vehicle at Palm Springs. This fails
the predeclared multi-site support requirement, so the new between-regime method
stays disabled. Actual cross-sensor identities remain unverified.

`learner-review/report.json`, `split_audit.json`, `uncertainty_review.json`, and
`between-regimes/report.json` preserve the full denominators and limitations.
`dashboard/static/florida-regime-validation.png` shows the earliest accepted
held-out example of each motion type, selected by time rather than error. It
includes an example where the learned reconstruction is worse.
