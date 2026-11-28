# Signal position and movement reference

Use geographic north (top), east (right), south (bottom) and west (left) on the north-up map. The 215° object display rotation does not rotate the compass or the base map. Compass letters around the selected intersection are directional aids, not surveyed approaches or signal locations.

| Intersection | Stable marker IDs | Current provisional placement |
|---|---|---|
| Finch W & Driftwood | DR1 | Centre |
| Finch W & Jane | JA1, JA2, JA3, JA4 | NW, NE, SE, SW respectively |
| Finch W & York Gate | YG1, YG2 | A/B; actual sides unconfirmed |
| Finch W & Norfinch / Oakdale | NO1, NO2 | A/B; actual sides unconfirmed |
| Finch W & Signet / Arrow | SI1 | Intersection reference; exact location unconfirmed |
| Finch W & Weston | WE1, WE2, WE3, WE4 | NW, NE, SE, SW respectively |
| Finch W & Islington | IS1, IS2, IS3, IS4 | NW, NE, SE, SW respectively |
| Finch W & Kipling | KI1, KI2, KI3, KI4 | NW, NE, SE, SW respectively |
| Finch W & Albion | AL1, AL2, AL3, AL4 | NW, NE, SE, SW respectively |
| Finch W & Martin Grove | MG1, MG2, MG3, MG4 | NW, NE, SE, SW respectively |

Movement codes use origin then destination: NS = north to south (southbound), SN = south to north (northbound), EW = east to west (westbound), WE = west to east (eastbound). For turns, give origin and destination explicitly. Only use arms that actually exist at the intersection. A corner label describes a physical position, not an approach or controlled movement. The prefix WE in marker WE1 identifies Weston; the separate movement code WE means west to east.

Correction format: `JA1; actual location = ...; controlled movement = ...; live phaseNumber = ... (if known)`. Multiple heads/movements at a reported assembly may be listed separately. Unknown phase identifiers should stay unknown. These human corrections still need separate confirmation of the Phase Details ID / real-time phaseNumber relationship before an automatic API join.
