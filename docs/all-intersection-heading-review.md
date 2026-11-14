# All-intersection heading review — 13 November 2026

Sampled fresh stored preview frames for 30 seconds across both corridors. Norfinch delivered frames during this sample; Jane supplied none. Moving vehicle checks exclude observations within 20 m of the reference and beyond 180 m, require speed above 3 m/s, and select at most one observation per track per three-second bin. Road-match scores are diagnostic, not independent ground truth.

| Site | Moving samples | Median matched road heading error before display correction | Eligible vehicle observations / all observations |
|---|---:|---:|---:|
| Renaissance Dr & SR-436 | 27 | 1.1° | 85 / 147 |
| Boston Ave & SR-436 | 29 | 1.5° | 99 / 229 |
| Cranes Roost & SR-436 | 42 | 1.9° | 242 / 374 |
| Hattaway Dr & SR-436 | 17 | 1.6° | 140 / 162 |
| Palm Springs Dr & SR-436 | 58 | 1.2° | 143 / 487 |
| Plaza Entrance & SR-436 | 88 | 0.7° | 65 / 452 |
| Essex Ave & SR-436 | 47 | 1.7° | 73 / 162 |
| Finch W & Norfinch (LRT) | 44 | 3.5° | 183 / 296 |
| Finch W & Driftwood (LRT) | 64 | 16.5° | 82 / 360 |
| Finch W & Signet (LRT) | 56 | 3.5° | 126 / 393 |
| Finch W & Jane (LRT) | 0 | Unavailable | 0 / 0 |
| Finch W & Albion (LRT) | 93 | 1.2° | 311 / 510 |
| Finch W & Weston (LRT) | 139 | 1.6° | 564 / 854 |
| Finch W & Kipling (LRT) | 103 | 0.9° | 286 / 565 |
| Finch W & Martin Grove (LRT) | 92 | 1.3° | 225 / 587 |
| Finch W & York Gate (LRT) | 132 | 2.8° | 463 / 775 |
| Finch W & Islington (LRT) | 99 | 1.4° | 662 / 799 |

## Display changes and limits

Vehicles within 12 m of a named mapped road segment and with an API heading within 25° of its permitted direction may use that road bearing for their icon. The rule rejects the 30 m intersection-centre area, competing road directions, off-road observations and opposite-direction one-way matches. It never changes coordinates. Initial icons receive the corrected heading before display; stopping can align the icon once, then the heading holds. Moving vehicles outside the centre also use the same rule to avoid immediately reverting the visual correction. Pedestrians/cyclists retain their reported orientation. Tooltips and map notes disclose the provisional correction.

Driftwood: 82 of 360 vehicle observations were eligible (9 stopped). This is not proof that all remaining vehicles face correctly. Its site-wide rotation remains unresolved between competing orientations; the current site transform and origin were not changed. Norfinch also remains geometrically unresolved. Jane cannot be checked without data. No blanket 180° flip or road-position snapping was applied.

Validation: tests reject turns, opposing traffic, distant and ambiguous road candidates; existing tests cover first-frame heading, stop jitter and restart motion. All-intersection replay counts are eligibility counts, not unique vehicles or ground-truth accuracy. Local Driftwood screenshot verified rendering. Public hostname DNS resolution failed during browser checking; local combined viewer worked. Public origin was reloaded to permit the new static road asset without restarting collectors or changing the tunnel.

Local evidence: `data/heading-review/all-sites-raw.json`, `all-sites-audit.json`, `road-corrections.json`, `driftwood-road-heading.png`. Geometry source: saved OpenStreetMap extracts, © OpenStreetMap contributors (https://www.openstreetmap.org/copyright).
