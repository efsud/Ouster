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

## Estimated mode — 16 November 2026

User-authorized estimated mapping is now separate from controller verification. Run `scripts/estimate_signal_directions.command` alongside the two live collectors. The combined/public viewers consume its local `data/signal-estimates.json` report. There is no credential entry in the estimator. It reads only the two small live databases, never the historical archive.

Every half second it pairs a latest object frame with accumulated phase state in one SQLite read transaction. It uses observed coordinate displacement, with the same provisional rotation and Y reflection as the map, rather than the cosmetically adjusted icon heading. Tracks must stop for two seconds, release upstream within 80 metres of the assumed centre, and subsequently pass through to the opposite side. Turning, large sideways drift, excessive speed, missing initialization and gaps are rejected. Cardinal assignment permits at most 35 degrees deviation from the named direction. This may omit oblique roads and is not a verified lane classifier.

For each direction and candidate phase, evidence includes green and red fractions at release, release proximity to observed green onset (0–12 seconds), green duty fraction, number of cycles, and distinct cycles with matched releases. Score = 0.6 × green release fraction + 0.4 × onset-match fraction. It is a heuristic score, NOT a probability or statistical confidence interval.

Acceptance requires at least 600 seconds of observation, eight supported through releases, three observed green onsets and three distinct matched release cycles, ≥80% releases on green, ≤10% on red, ≥50% near green onset, green association ≥1.5 times background green duty, and a score margin ≥0.2 over the next candidate. Tied phases stay ambiguous. These initial thresholds need field review. Evidence uses a rolling hour, resets after outages/session changes, and is not trained from the old previews. Restarting the estimator starts a new learning window. No automatic controller verification is written to configuration.

Accepted mappings use live API colors with explicit EST labels and provisional confidence in tooltips. Fresh stream, absolute snapshot, phase age and mapping-report freshness gates still apply. After five seconds without fresh input or fifteen seconds without estimator reports, inferred colors are disabled. Opposing colors are never forced to agree. Gray means insufficient, ambiguous, stale or unavailable evidence. This is an exploratory through-movement association, not physical-head identification or a safety assessment.

Limitations: receipt clocks can mask transport lag; approximate origin/rotation can misclassify direction; queues unrelated to lights can produce associations; correlated phases may remain indistinguishable. The estimator reports evidence but does not prove signal/vehicle consistency. Candidate details are available in marker tooltips and the local report. Raw vehicle trajectories are not added to a historical archive; only bounded in-memory samples/tracks and derived report evidence are used.

Validation: automated cases cover coordinate reflection, ambiguous headings, stop/release completion, session/gap reset, sufficient evidence and tied candidates. Real estimates remain pending fresh live collection and review. The previous controller-verified-only behavior remains available and takes priority over estimates.
