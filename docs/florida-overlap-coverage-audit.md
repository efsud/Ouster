# Florida: separate observation overlap from missing roadway

November 23, 2026; inspected window 13:14:49–14:14:49 EST.

The seven-site review found that not every apparent intersensor discontinuity is an unobserved forward gap. Cranes Roost and Hattaway have overlapping projected coverage. A normal forward-gap solver rejects an upstream endpoint beyond the downstream start, because connecting the two endpoints would move backwards. The appropriate separate task is to compare the simultaneous observed portions, not draw an invented bridge through them.

## All adjacent links, both directions

The signed gap below is the median downstream start minus the median upstream end, oriented in the travel direction. It is a summary of eligible fragment endpoints, not a surveyed coverage boundary or the distance traveled by one vehicle. Negative values indicate projected overlap.

| Link | Direction | Median signed gap (m) | Additional observed-overlap hypotheses |
| --- | --- | ---: | ---: |
| Cranes Roost → Hattaway | Eastbound | −4.7 | 234 |
| Hattaway → Cranes Roost | Westbound | −14.9 | 226 |
| Hattaway → Renaissance | Eastbound | 20.7 | 1 |
| Renaissance → Hattaway | Westbound | 20.4 | 1 |
| Renaissance → Essex | Eastbound | 12.1 | 0 |
| Essex → Renaissance | Westbound | 105.7 | 0 |
| Essex → Plaza Entrance | Eastbound | 21.1 | 0 |
| Plaza Entrance → Essex | Westbound | 15.8 | 0 |
| Plaza Entrance → Palm Springs | Eastbound | 4.4 | 0 |
| Palm Springs → Plaza Entrance | Westbound | 7.6 | 0 |
| Palm Springs → Boston | Eastbound | 107.9 | 0 |
| Boston → Palm Springs | Westbound | 128.6 | 0 |

These 462 overlap hypotheses are not 462 newly recovered trajectories, verified global vehicle identities, or dashed missing-position estimates. They use simultaneous recorded observations and exclude endpoints occupied by existing local/corridor gap estimates. Resolving which overlapping fragments are the same vehicle still needs independent sensor alignment and clock validation.

Palm Springs–Boston is a different problem: its positive blind roadway distance remains approximately 108 m eastbound and 129 m westbound at the median endpoints. In the baseline audit, Palm→Boston had 1,791 candidate departure fragments, 440 assignments, 390 departures without a feasible edge, and 961 with feasible alternatives but insufficiently distinct assignment evidence. Those counts are fragments, not unique vehicles or corridor traffic volume.

## How the overlap check works

For each eligible adjacent-intersection pair, the check compares at least one second and ten meters of common observation. It requires median projected-position difference at most 3 m, 95th-percentile position difference at most 5 m, and median speed difference at most 3 m/s. Available measured object dimensions supplement the score. Partial one-to-one matching retains a competing-assignment margin of 0.5; ties remain unresolved. No fitted clock shift or position correction is introduced.

For example, if one sensor observes a vehicle from station 70 to 125 m while its neighbor observes from 100 to 160 m at overlapping times, the 100–125 m interval is already observed. A missing-position bridge from 125 back to 100 m would be wrong. The check instead compares the two observed curves in that common interval and reports an unverified correspondence if sufficiently distinctive.

## Hidden-view validation

The final quarter-hour was held out, with all earlier identities excluded and a 30-second embargo. Alternating real observations from a continuous trajectory formed two views. Both complete and missing-endpoint scenarios were tested at 20, 40, and 60 m overlap widths. The rule was fixed before testing.

| Intersection | Eligible masked cases | Correct accepted associations | Wrong accepted associations |
| --- | ---: | ---: | ---: |
| Cranes Roost | 241 | 127 | 0 |
| Hattaway | 243 | 92 | 0 |
| Renaissance | 237 | 105 | 0 |
| Essex | 244 | 73 | 0 |
| Plaza Entrance | 254 | 82 | 0 |
| Palm Springs | 237 | 87 | 0 |
| Boston | 238 | 111 | 0 |
| Total | 1,694 | 677 | 0 |

Only 677 masked pairs had enough overlapping evidence; the remaining 1,017 were not recovered. Widths and scenarios reuse vehicles, so these are correlated cases. Both views came from one sensor; zero false matches in this proxy does not establish accuracy for actual different sensors. No cross-sensor or corridor KPI becomes field-validated through this experiment.

## Reproduction

`deepctm/between_coverage_audit.py` exposes `audit(snapshot, layers)` and a CLI accepting `--snapshot`, `--layers`, and `--output`. It checks matching snapshot versions and reports all twelve directional links. The inspected run took 6.19 seconds, including reading the 105 MB snapshot. It does not modify recordings, estimates, or KPI inputs. Four new tests and four existing overlap-association tests passed.

Evidence is saved under `data/reconstruction/all-sites-between-review/`: `audit.json` for baseline candidate rejection, `overlap-reserved.json` for the final overlap audit, and `overlap-heldout.json` for the validation. `overlap.json` is an earlier exploratory audit that did not reserve occupied endpoints and must not be used for final counts.
