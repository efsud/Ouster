# One-hour Finch virtual-cell trial

Source: November 6, 2026 capture `20261106T164305Z`. These are held-out **endpoint** speed errors, not measurements of trajectory accuracy between intersections. Seven adjacent links have models in both directions. Each evaluation contains only five to eight target minutes. No claim of field validation is made.

| Link | Direction | Test minutes | DeepCTM speed RMSE (km/h) | Persistence | Pure CTM |
|---|---|---:|---:|---:|---:|
| Martin Grove → Albion | eastbound | 5 | 11.14 | 17.32 | 30.42 |
| Martin Grove → Albion | westbound | 5 | 10.22 | 14.38 | 30.79 |
| Albion → Kipling | eastbound | 5 | 8.29 | 16.33 | 32.69 |
| Albion → Kipling | westbound | 5 | 8.35 | 13.54 | 32.49 |
| Kipling → Islington | eastbound | 5 | 7.49 | 14.56 | 28.35 |
| Kipling → Islington | westbound | 5 | 8.54 | 16.10 | 27.36 |
| Islington → Weston | eastbound | 8 | 8.00 | 11.71 | 33.12 |
| Islington → Weston | westbound | 8 | 6.71 | 12.49 | 30.21 |
| Weston → Signet | eastbound | 5 | 7.41 | 11.45 | 35.44 |
| Weston → Signet | westbound | 5 | 9.50 | 17.47 | 35.70 |
| Signet → Norfinch | eastbound | 5 | 6.60 | 10.87 | 31.62 |
| Signet → Norfinch | westbound | 5 | 9.88 | 16.93 | 35.96 |
| Norfinch → York Gate | eastbound | 8 | 7.45 | 11.65 | 33.58 |
| Norfinch → York Gate | westbound | 8 | 5.96 | 8.75 | 34.45 |

Both models involving Jane are unavailable in each direction because Jane has no recorded frames. The dashed paths are virtual tracers through the learned speed field, never matches between observed object identities. See `deepctm.md` for cell design, features, chronological splitting, assumptions and reproduction commands.
