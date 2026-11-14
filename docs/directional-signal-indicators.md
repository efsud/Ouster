# Directional signal indicators — 14 November 2026

The combined live map now provides four schematic through-movement indicators per intersection for all ten Finch and seven Florida sites. They appear at zoom 17 or closer and can be hidden using Direction signals (schematic).

| Indicator placement | Vehicles travel |
|---|---|
| East | West to east (WE) |
| West | East to west (EW) |
| North | South to north (SN) |
| South | North to south (NS) |

These are schematic offsets from the intersection reference, not surveyed physical signal heads or a claim that the site has exactly four heads.

## How live state works

Previously, live-only recording kept the most recent object frame but could discard phase-only updates. Both recording paths now retain an accumulated current phase snapshot in live_signal_state. Absolute messages initialize it; subsequent changes update it. A new session or receipt gap greater than five seconds requires reinitialization. This stores current state, not a new historical archive.

The /api/directional-signals endpoint combines this state with config/signal_directions.json. A direction is colored only when its mapping has explicit verification evidence, the stream is fresh, an absolute snapshot has arrived, and every assigned phase has a recent valid agreeing state. Missing, conflicting or stale evidence produces gray. The conservative per-phase expiry is 180 seconds.

Worked example: a verified E assignment to phase 7 with received status GREEN would display green at the east indicator for W→E travel. This is an illustrative mapping, not an assignment made for any real site.

## Outstanding field evidence

All 17 sites currently have empty, unverified assignments. Saved Phase Details labels and IDs do not establish a verified join to live phaseNumber. No actual direction-specific colors are claimed yet. Obtain controller/vendor-confirmed mappings before setting verified=true and recording the source in evidence.

Opposing directions are not forced to match. The endpoint reports differing opposite states and simultaneous perpendicular through greens for review. These are diagnostic flags, not proof of a controller fault. Vehicle consistency remains unvalidated until stop lines, movement mapping and clock relationships are established; moving cars alone do not establish a green signal.

## Validation

- 71 Python tests passed, including absolute/delta reconstruction, live-only retention without raw archive, stale state, session reset, direction convention and unknown mappings.
- git diff --check passed.
- Browser inspection confirmed four gray indicators on Driftwood (Finch) and Renaissance (Florida), with E showing W→E and the other corresponding directions.
- Toronto endpoint returned fresh receiving streams and initialized absolute snapshots for inspected sites; direction colors remained unknown because mappings are unverified.

Implementation and software checks are complete for the indicator framework. Directional coloring and vehicle/signal coordination are not field-validated.
