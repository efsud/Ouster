# Rolling trajectory reconstruction: methodology and limits

## Paper review

Sources: supplied Cellitti, Di Rocco and Ferraro Petrillo, *A Physics Informed GNN for Traffic Prediction: the DeepCTM Model*, pp. 674–685; and Su & Deng, *LightSim: A Lightweight Cell Transmission Model Simulator for Traffic Signal Control Research*, https://arxiv.org/pdf/2602.21852 (2026).

DeepCTM sections 4.1–4.5 distinguish observed and virtual graph cells, input flow/occupancy/speed, split physical/free recurrent states, asymmetric downstream/upstream messages, masked physics-neural gating, and physical error correction. Its loss combines observed-node error, CTM consistency, spatial smoothing and correction error. The experiments use a year of Madrid data at 15-minute resolution. A learned model and calibrated road graph are required for its full method; the paper does not provide individual cross-sensor identity reconstruction. The supplied tables also disagree on the full-model 60-minute RMSE (144.03 vs 185.24), so neither is a reproduction target here.

LightSim section 3.1, equations 1–5, provides sending and receiving flows with capacity and jam-density limits, CFL-compatible discretization, conservative density updates, and signal-gated movements. Sections 3.4 and 4 distinguish optional startup loss/stochastic demand and validation against theoretical fundamental diagrams and SUMO controller rankings. Those are simulator validations, not evidence that reconstructed individual trajectories are correct. The paper explicitly excludes microscopic acceleration, lane changing and gap acceptance.

## Implemented adaptation

The new rolling overlay is a **CTM reconstruction baseline, not a trained DeepCTM model or exact reproduction of either paper**. It uses DeepCTM's observed/virtual-cell distinction and LightSim's conservative sending/receiving equations. The existing exploratory neural model for older saved Finch data is not silently reused for these different corridors and rolling windows.

1. Solid local segments remain observations. Within the same sensor/session/object/class track, gaps of 1.5–3 seconds are displayed dashed with endpoint-interpolated along-road speed. Larger gaps, session changes and implausible positions are not joined. This is interpolation, not neural prediction.
2. Adjacent sensor reference positions define provisional road station distances. Local observation strips extend 120 m on each side. Overlapping strips and blind gaps shorter than 5 m do not create a virtual segment. Interior blind road is discretized into roughly 30–60 m cells (one smaller cell is possible).
3. For each direction, accepted vehicle track distance and time inside the 240 m strip give Edie-style flow and density proxies in 60-second bins. Each endpoint needs at least 80% occupied receipt-second coverage and three accepted fragments. These proxies omit rejected and stationary-only tracks and are **not unbiased ground truth**.
4. The CTM uses 1-second updates, an assumed aggregate jam density of 0.30 veh/m (two lanes at 0.15 veh/m/lane), backward-wave speed 5 m/s, and an 85th-percentile endpoint speed prior clamped to 8–22 m/s. A short-cell speed cap ensures CFL compatibility. Upstream demand and downstream receiving supply come from the current historical minute. This uses contemporaneous data, so it is reconstruction, not a forecast evaluation.
5. Density starts as a bounded interpolation between endpoints. Missing boundary minutes invalidate the field and reset subsequent initialization; no mass-continuity claim crosses a reset. Conservative updates themselves report their maximum numerical mass residual.
6. Representative tracers start near observed outgoing track endpoints and integrate dx/dt = CTM outflow/density. They stop at the downstream observation boundary, missing evidence, the window boundary, or ten minutes. They do not snap to an unrelated downstream track. Seeds are thinned to at most one per 15 seconds, a display choice, not traffic volume.
7. CTM estimates appear only for pooled Vehicles and selected adjacent endpoint sites. Pedestrians and cyclists retain local observations and short-gap interpolation only. Dash phase is continuous across rendered segments; red/yellow/green is the same speed scale as observations, not signal colors.

No verified signal gate, turning flow, lane geometry or intermediate ground truth is available. No signal cycle or vehicle identity is invented. Therefore some gaps intentionally remain blank, and CTM trajectories may differ from actual vehicle paths.

## Validation

Unit tests check conservative mass balance, nonnegative/jam-bounded density, bounded speeds, supported paths, suppression for missing endpoint data, overlapping strips, exclusion of pedestrians, and a known constant-speed masked-point example. The snapshot also masks real interior points and reports along-road interpolation MAE versus forward constant-velocity extrapolation. This is a local reconstruction diagnostic using both endpoints; it is not a forecast score or validation between sensors. Multi-second missing-block tests and independent intermediate observations would be needed for broader accuracy claims.

## Storage and use

Snapshot computation runs in a background worker thread so the sampler continues during modeling; per-site query results release their read cursor before trajectory processing. The two existing rolling buffers retain 90 minutes. Figures cover one hour and regenerate every 30 minutes. Each snapshot contains estimates, assumptions, boundary support and local mask validation; no extra long-lived trajectory archive is created. Open Historical Performance on the original dashboard, or /finch and /florida on the figure viewer. Toggle estimates, select adjacent sites and zoom to inspect dashed paths.
