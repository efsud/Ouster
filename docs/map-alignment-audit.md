# Map-alignment audit — November 13, 2026

The live-map preview was checked against moving vehicle segments and OpenStreetMap road centerlines and explicit one-way direction tags. Origins were held fixed. These are provisional display adjustments, not surveyed calibration.

## Method

For each sensor, use the first ten minutes of the saved capture, skipping startup ten seconds. Use one-second vehicle displacements at 4–30 m/s within 180 m of the SDK origin, excluding the central 15 m and inconsistent receipt/sensor timing. Fit integer rotations across 360 degrees, testing both axis handedness conventions. Score each segment against nearby mapped road segments using position distance plus 0.6 metres per degree of direction error, with a trimmed mean. Explicit OSM one-way tags retain signed movement direction; two-way roads cannot resolve direction by themselves.

Fit on the earlier five minutes and assess on the later five minutes. Apply only when the best candidate beats alternatives at least 25 degrees away by 20% and reduces validation score by at least 20%. These thresholds are engineering screening rules, not statistical confidence intervals. Samples from the same tracks are correlated; origin errors, road-map errors and detection errors remain.

Florida source: `data/sr436/20261113T115900Z-89fb0f`. Finch source: `data/deepctm/20261106T164305Z`. The audit does not imply Finch is currently streaming. Road geometry: [OpenStreetMap API](https://api.openstreetmap.org/api/0.6/map), © OpenStreetMap contributors. Raw geometry, sample arrays and full evidence are saved locally in `data/alignment/`.

## Decisions

Angles are total counterclockwise rotations **after inverting local SDK Y** for applied rows. They cannot be compared directly with old rotation-only values. At 90 degrees this maps SDK X to north and SDK Y to east. This convention is inferred from these recordings, not certified for all BlueCity installations.

| Site | Previous rotation only | New rotation after Y inversion | Validation score before → after | Decision |
|---|---:|---:|---:|---|
| Renaissance Dr & SR-436 | 180° | 90° | 47.7 → 3.5 | Applied provisional display correction |
| Boston Ave & SR-436 | 180° | 89° | 18.8 → 2.9 | Applied provisional display correction |
| Cranes Roost & SR-436 | 180° | 90° | 13.7 → 3.9 | Applied provisional display correction |
| Hattaway Dr & SR-436 | 180° | 90° | 24.5 → 3.5 | Applied provisional display correction |
| Palm Springs Dr & SR-436 | 180° | 90° | 15.0 → 3.1 | Applied provisional display correction |
| Plaza Entrance & SR-436 | 180° | 90° | 33.3 → 2.8 | Applied provisional display correction |
| Essex Ave & SR-436 | 180° | 91° | 24.9 → 3.2 | Applied provisional display correction |
| Finch W & Norfinch (LRT) | 220° | Not applied | 13.3 → 5.2 | Retained prior setting; opposite orientation ambiguous |
| Finch W & Driftwood (LRT) | 140° | Not applied | 20.9 → 2.6 | Retained prior setting; opposite orientation ambiguous |
| Finch W & Signet (LRT) | 135° | 268° | 22.1 → 8.2 | Applied provisional display correction |
| Finch W & Jane (LRT) | 220° | Not applied | — | Retained; no recorded tracks |
| Finch W & Albion (LRT) | 145° | 89° | 15.9 → 4.5 | Applied provisional display correction |
| Finch W & Weston (LRT) | 210° | 91° | 16.5 → 3.4 | Applied provisional display correction |
| Finch W & Kipling (LRT) | 220° | 90° | 25.6 → 6.5 | Applied provisional display correction |
| Finch W & Martin Grove (LRT) | 140° | 90° | 21.4 → 5.4 | Applied provisional display correction |
| Finch W & York Gate (LRT) | 135° | 271° | 21.5 → 4.9 | Applied provisional display correction |
| Finch W & Islington (LRT) | 210° | 90° | 18.9 → 6.6 | Applied provisional display correction |

## What changed and what did not

14 sites updated: seven Florida and seven Finch. Norfinch, Driftwood and Jane remain unchanged. The map applies reflection in its approximate display layer, using each API response’s actual rotation. This works with existing running servers and avoids interrupting recorders. Strict calibrated output is untouched. Object headings continue to follow transformed movement. Raw events, origin coordinates, historical figure snapshots and trained models were not rewritten or retroactively relabelled. Saved figures therefore retain their original geometry and would need a separate, versioned recomputation.

Previous configuration: `data/alignment/sites-before-alignment.json`. Reproduce the diagnostic with `.venv-deepctm/bin/python scripts/audit_map_rotations.py` after retaining the saved map extracts. The diagnostic itself never edits configuration.

Validation: 65 dashboard tests, three rotation/direction scoring tests, and a JavaScript numerical test comparing display reflection with reflection-before-rotation. Visual review used before/after overlays against road geometry. Residual offsets remain at some Finch sites; changing the sensor origin would require separate evidence.

## Opening the corrected Finch live map

Run `scripts/connect_finch_live.command` and enter BlueCity credentials in its private Terminal prompt. It starts the current server and all ten configured Toronto subscriptions at `http://127.0.0.1:8774/?region=Toronto&site=OBC-AG-SA-C257220#map`, using an isolated `data/finch-live.sqlite3`. Keep Terminal open. This launcher updates live previews without creating a new raw historical archive. It does not interrupt the Florida session or replace historical recordings.

The previous Finch server on port 8765 was found running older code: it rejected `rotation=site` and returned stale/unavailable frames for all ten sites. The new session loads the existing seven provisional Finch corrections. Norfinch, Driftwood and Jane retain their documented unresolved settings. Authentication and fresh reception must be verified after login; the launcher alone is not proof of live access.
