# Live heading verification — 13 November 2026

Checked the active public viewer and sampled 20 snapshots per corridor, approximately one second apart. All seven Florida feeds and eight Finch feeds supplied current objects with orientation. Norfinch remained stale and Jane unavailable.

Replayed the actual frontend heading functions against the saved live sample:

| Corridor | Distinct vehicle IDs first encountered in sample | Stopped-vehicle updates | Heading changes during those stopped updates | Missing headings |
|---|---:|---:|---:|---:|
| Florida | 594 | 6,012 | 0 | 0 |
| Finch | 712 | 4,206 | 0 | 0 |

A first encounter includes vehicles already present at sampling start; it is not necessarily a sensor birth. Replay verifies display logic, not physical road alignment. First-frame initialization sets the transformed API orientation before the icon is inserted. The existing regression check covers initialization, stopped jitter, movement resumption, and axis reflection.

Visual inspection of the public Cranes Roost and Weston views showed approach queues oriented along their roads, with turning vehicles retaining their own direction. No additional rotation adjustment was justified by those views. This is a short spot check, not a guarantee for every object at every intersection. Incorrect sensor orientation, uncertain site alignment (especially Driftwood), and missing streams remain limitations. No road snapping or fabricated heading was introduced.

Local evidence (not published): `data/heading-review/live-sample.json`, `replay-results.json`, `florida.png`, `finch.png`. The 20-second diagnostic does not start ongoing recording or alter existing archives.
