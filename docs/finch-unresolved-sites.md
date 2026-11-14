# Finch unresolved sites — 13 November 2026

## Live reception

The current Finch session uses port 8774. Eight sites received fresh object frames with the same account. Norfinch and Jane were checked independently from map rendering.

- **Norfinch — OBC-AG-SA-C618857:** authentication and beacon routing reached `awaiting_events`, but subsequent sessions delivered zero events. Earlier in this launch a short initial burst was received, then stopped. Automatic reconnects did not restore continuous reception.
- **Jane — OBC-AG-SA-C351163:** gRPC returned `UNAUTHENTICATED`, with zero events. Successful account login and routing do not establish authorization at this sensor's streaming endpoint. This may be an authorization or service configuration issue; the client cannot determine which from the status code alone.

A controlled FRAME-only subscription test, excluding phase and loop events, reproduced both failures. Normal subscriptions were restored afterward. Other collectors and saved recordings were left intact. No credentials were stored in this report.

Ask the BlueCity administrator to verify this account's streaming entitlement and the beacon/stream authentication configuration for Jane, and sensor publishing/upstream connection health for Norfinch. Provide the UDIDs above and the test date. These failures cannot be repaired by rotating map objects or displaying old frames as live.

## Alignment recheck

Recorded local vehicle segments from `data/deepctm/20261106T164305Z` were compared with saved OpenStreetMap road directions again. To avoid Finch's larger traffic volume dominating the result, the two approximate perpendicular movement axes were scored separately. First-five-minute and second-five-minute results are shown below. Lower is better; the score combines metres and angular penalty and is not a positional accuracy estimate.

All candidates below invert SDK Y before applying the stated counterclockwise rotation. They are diagnostic candidates, not verified sensor calibration.

| Site | Candidate | Raw velocity axis 0, fit / validation | Raw velocity axis 1, fit / validation |
|---|---:|---:|---:|
| Norfinch | 92° | 4.38 / 4.17 | 6.46 / 7.14 |
| Norfinch | 272° | 7.55 / 7.41 | 4.68 / 4.28 |
| Driftwood | 89° | 11.20 / 11.90 | 1.77 / 2.06 |
| Driftwood | 269° | 10.25 / 7.83 | 1.94 / 2.05 |

Norfinch's movement groups prefer opposite orientations. Driftwood's dominant axis is almost indistinguishable under the 180° alternative; the smaller group favors 269°, but this is insufficient to verify the full mapping given the provisional origin. Keep existing display settings pending a known landmark or vendor sensor-axis orientation. Do not treat repeated road-fit scores as independent field validation.

Useful calibration evidence: vendor axis orientation plus sensor origin, or corresponding local SDK coordinates and map coordinates for at least three well-separated scene landmarks. A known track associated with a physical approach can help resolve the half-turn ambiguity but does not alone verify metric accuracy.
