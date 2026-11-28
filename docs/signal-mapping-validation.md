# Signal-count and placement validation — October 1, 2026

## Finding

The previous display used one traffic-light icon per non-invalid API phase. That was a misleading physical representation: neither the icon count nor the largest phase number establishes a count of signal heads. The user-requested removal remains in effect. No physical signal locations have been added by this audit.

## Recorded evidence

The audit inspected each site's most recent saved hour (not necessarily the same hour across sites). Counts below are **phase identifiers reporting a valid colour**, not lights, approaches, movements or controllers.

| Intersection | Valid phase IDs | Receipt coverage of selected hour | Vehicle stop/release events |
|---|---|---|---|
| Finch W & Norfinch (LRT) | No data | 0.0% | 0 |
| Finch W & Driftwood (LRT) | 1, 2, 4, 5, 6, 8, 9, 10, 11, 12, 13, 14 | 20.3% | 247 |
| Finch W & Signet (LRT) | 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14 | 5.0% | 217 |
| Finch W & Jane (LRT) | 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14 | 19.8% | 348 |
| Finch W & Albion (LRT) | 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14 | 19.2% | 231 |
| Finch W & Weston (LRT) | 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14 | 20.3% | 412 |
| Finch W & Kipling (LRT) | 1, 2, 3, 4, 5, 6, 8, 9, 10, 11, 12, 14 | 20.3% | 234 |
| Finch W & Martin Grove (LRT) | 1, 2, 4, 5, 6, 8, 9, 10, 11, 12, 13, 14 | 19.8% | 220 |
| Finch W & York Gate (LRT) | 1, 2, 3, 4, 5, 6, 8, 9, 10, 11, 12, 13, 14 | 16.6% | 247 |
| Finch W & Islington (LRT) | 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14 | 20.2% | 304 |

## Driftwood: why flow cannot uniquely assign the phase numbers

The recorded sample has 12 valid phase IDs, 52 invalid-only slots, and the following pairs with identical reconstructed observed colour sequences: **1/5, 2/6, 4/8, 9/11, 10/12, 13/14**. Each pair changed colour in the sample; constant-red channels were excluded from this equivalence check. This does not prove permanent equivalence or a shared movement, only indistinguishability in these observations.

The selected hour contains 7,579 frames with 20.3% receipt coverage. Its gaps mean that it cannot validate an entire hour of signal operation. The exploratory detector found 247 stop/release events. These are track fragments, not deduplicated physical vehicles.

One cluster near local coordinates (15.0, 16.4) m contains 18 release events; 11 align within ten seconds after green onset for **each** of phases 2, 6, 9, 11, 13 and 14. A cluster near (43.8, -19.5) m has six releases matching **each** of phases 4, 8, 10 and 12. These ties show that selecting one phase based only on this correlation would be arbitrary. They are not probabilities or proof of causation.

## Spatial interpretation and limitations

The analysis uses position differences with gaps no greater than three seconds, a speed threshold of 0.5 m/s for at least two seconds, then acceleration to at least 2 m/s. It groups release positions in coarse 15 m / 45-degree bins, retaining bins with at least five events. A track contributes at most one detected release per uninterrupted fragment. Thresholds are exploratory and not field calibrated. Track-ID reuse, occlusion, noisy positions, queue discharge, pedestrian/LRT phases, permissive turns and shared greens can confound associations.

These points describe where vehicles were observed stopping and starting. They may lie anywhere along a queue. They do not locate poles, overhead mast arms, individual signal heads, or even verified stop lines. The sensor origins and 215-degree display rotation are approximate. No geographic signal placement is justified by these data alone.

## Required to place actual signals

Obtain a signal layout or surveyed/mapped physical-head locations, together with the controller/API phase-to-movement/head mapping and a verified sensor-to-map transform. Confirm timestamps and obtain sufficiently continuous observations. Vehicle flows can then cross-check approach assignments and red/green release consistency. If only an inferred approach diagram is desired, it must be labelled as such, without physical-light icons or claims of exact positions.

## Reproducing and learning from this audit

Run `.venv/bin/python scripts/audit_signal_mapping.py`. The script reads SQLite without writing to it; raw observations are untouched. Full private evidence goes to ignored `data/signal-mapping-audit.json`. No credentials or raw trajectories are committed. The test checks that shared changing phase sequences are detected, constant colours are not treated as strong equivalence evidence, missing data stays missing, and physical head count remains unavailable.
