# DeepCTM on Finch West: paper review and implementation

## What this implements

Source: Cellitti, Di Rocco and Ferraro Petrillo, *A Physics Informed GNN for Traffic Prediction: the DeepCTM Model*, supplied 12-page PDF, pp. 674–685, DOI 10.1007/978-3-032-38410-2_54. All pages were read; the architecture and equations on pp. 679–682 were also inspected as rendered pages. The supplied PDF is the reference; its publication metadata has not been independently verified.

DeepCTM forecasts macroscopic traffic **flow, density and speed** on a directed road graph. It is not a method that directly produces the earlier document's seven intersection KPIs, finds signal-head positions or optimizes signals. The existing historical KPI calculator remains separate.

This is a **provisional, independently implemented adaptation**, not the authors' code or an exact reproduction. The paper omits enough detail that an exact reproduction cannot honestly be claimed. Its Madrid results must not be used as Finch accuracy estimates.

## Understanding the paper

1. Represent roads as directed cells, including virtual cells without sensors. Each observed node supplies flow, occupancy/density proxy and speed.
2. Split recurrent state into a physical subspace and a free subspace (Eq. 2). The physical branch follows CTM plus a learned residual (Eq. 3).
3. Pass different messages downstream for vehicles and upstream for congestion (Eqs. 6–8). These are two learned transforms, not the same undirected average.
4. Mix neural and physical messages with a learned sigmoid gate receiving the observation mask (Eqs. 4–5). The equation does **not** force virtual-node gates to one.
5. Learn physical error correction, assimilating observed discrepancies into state. The paper gives an update but not the correction network, complete training loss or correction strength.
6. Train on observed nodes with MSE plus physical consistency, spatial smoothness and PEC penalties. Virtual nodes are not zero-valued training labels.
7. Evaluate forecast error and mass conservation. CTM alone conserves vehicles, but an unconstrained neural residual, gate and correction need not. We measure violations rather than claim the full model guarantees conservation.

The paper uses one year of Madrid data, originally five-minute and aggregated to 15-minute resolution. It reports 15- and 60-minute forecasts, physical/free dimensions 64/32, Adam approximately 0.001, dropout 0.102, weight decay 1e-6 and loss weights [1, 0.00292, 0.000610, 0.00411]. These numerical settings are retained.

### Important ambiguities

- The input lookback K, batch size, epochs, split dates, random seeds, complete adjacency normalization, CTM boundary/fundamental-diagram calibration and occupancy-to-density conversion are not specified.
- The mapping between the 64-dimensional physical latent state and three measurable variables is unspecified.
- Exact physics/smoothing/PEC loss formulas and units are missing. Their relative weights are not portable without knowing normalization.
- Table 1 reports full-model 60-minute RMSE **144.03**, while Table 2 reports **185.24**. We do not select one as an authoritative reproduction target.
- Eq. 10 is the absolute mass residual, in vehicles with consistent units. Eq. 11 sums across the network but divides by the number of observed nodes. We report both that normalization and the ordinary mean over all cells; they differ when virtual cells exist.
- The paper does not supply a verified signal model, junction turning model, author repository or runnable implementation in the provided text.

## Finch experiment and recording

Use **Weston (OBC-AG-SA-C257220)** and **Signet / Arrow (OBC-AG-SA-C251071)**. They are adjacent along Finch and both have overlapping archived data. The read-only archive audit found gaps and no new rows beyond October 16–17, rather than two continuously recording sites. User subsequently requested a new 24-hour capture; this is now the experiment's training source. Jane has no rows in that archive.

The recorder saves original FRAME, PHASE_CHANGE and LOOP_CHANGE payloads as received, with receipt time, site and collector-session ID, in hourly gzip JSONL files. It does not rewrite vendor data or the older 104 GB database. The metadata and capture configuration are saved alongside the files under ignored `data/deepctm/<UTC-start>/`.

- Password entry is hidden in Terminal. Credentials remain in process memory/environment; no credentials are saved in the experiment or Git.
- The supervisor retries a stalled/failed worker, preserving the original deadline and earlier files. A session ID distinguishes reused IDs after reconnects.
- Ten failed restarts or less than 2 GiB free space stops the capture with a failed status. It does not silently shorten a successful capture.
- On macOS, `caffeinate -i` prevents idle sleep while the supervisor runs. Keep Terminal open, the computer powered and the lid open; shutdown, forced sleep or network loss can still interrupt capture.
- At the deadline, workers close their compressed files; feature extraction and training run automatically without credentials, if sufficient data exists.
- A new run uses its own folder. A completed capture is not automatically deleted by the dashboard's normal SQLite retention.

`/api/deepctm` and the read-only experiment viewer report receipt freshness, not merely whether a process exists. Counts shown are per current worker session. The new compressed capture is separate from the old live-map recorder and does not itself refresh that map.

## Feature definitions and limitations

Two directed chains are trained separately: Weston → Signet (eastbound) and Signet → Weston (westbound). Each has two observed 100 m cells and one unobserved 400 m cell. The 600 m length, road bearing, ROI width and lane assumptions are explicitly provisional. No lateral inflows/outflows, signal gates, junction turns or cross-sensor identity matching are claimed.

Positions use the user's saved rotations (Weston 210°, Signet 135°) and an assumed 17° eastbound road bearing measured from map east toward north. An assumed rectangle is 100 m long and 24 m wide. These are experiment assumptions, not verified lane geometry. Dominantly cross-street trajectories are excluded, but turns and misalignment can still contaminate features. Stopped tracks are retained only after their direction is established; vehicles first seen stopped are excluded until classified, which can undercount queues.

For each accepted trajectory segment clipped to that rectangle:

- `k = sum(vehicle time in seconds) / (ROI length in km × window seconds)` → veh/km.
- `q = sum(longitudinal distance in km) / (ROI length in km × window seconds) × 3600` → veh/h.
- `v = sum(longitudinal distance in km) / sum(vehicle time in hours)` → km/h.

These are **Edie-style trajectory estimates**, replacing the paper's occupancy proxy. They are not unique-vehicle crossing counts or lane-calibrated field measurements. Example: one vehicle travels 72 m in 9 seconds within a 100 m ROI during a 10-second window: k = 9 veh/km, q = 259.2 veh/h, v = 28.8 km/h.

Track keys include sensor session and ID. Segment gaps above 3 seconds, invalid coordinates, jumps above 60 m/s and receipt/sensor elapsed-time ratios outside [0.5, 2] are excluded. This also rejects startup buffering. Receipt bins are used because absolute sensor timezone/synchronization remains unverified. Relative sensor time supplies elapsed vehicle time. This does **not** establish synchronized directional travel times.

A valid 15-minute input needs at least 80% receipt coverage with acceptable relative clock intervals, plus classified vehicle-time for that direction. No vehicle-time means unavailable speed and an invalid feature window, not a false observed zero-speed measurement. A gap is never interpolated for training. ROI occlusion/completeness is not established by receipt coverage.

## Architecture choices made where the paper is silent

| Component | Implementation choice |
|---|---|
| Physical latent | 64-dimensional tanh encoding of normalized q/k/v; explicit three-variable CTM state |
| Free latent | 32-dimensional LSTMCell, recurrent hidden/cell state |
| CTM | Triangular diagram; v=50 km/h, w=18 km/h, jam=300 veh/km across assumed two lanes; open downstream boundary and persisted upstream demand |
| Integration | CFL-safe substeps inside each 15-minute step; veh/km, km and hours used consistently |
| Residual | Bounded tanh correction to normalized CTM q/k/v; no claim of strict conservation after correction |
| Graph | Forward predecessor and backward successor messages plus self transform, unweighted adjacent chain edges, LeakyReLU |
| Gate | Three-channel sigmoid over neural/physical embeddings plus observation mask; no hard virtual-node override |
| PEC | MLP predicts state-minus-observation residual during context; alpha=0.1 correction followed by 50% observation assimilation; no future observation access |
| Initialization | Observed first context features; virtual cell linearly interpolated between endpoints, explicitly unsupervised |
| Prediction bounds | Density [0, jam], speed [0, free speed], flow [0, 6000] veh/h |
| Scaling | Fixed [2000 veh/h, jam density, free speed]; no normalization fitted on future data |
| Losses | Normalized observed q/k/v MSE; normalized predicted-minus-CTM MSE; normalized neighboring prediction MSE; masked PEC discrepancy MSE |
| Lookback / horizon | Four 15-minute context steps → four future steps; only 15/60-minute headline metrics |
| Optimization | 40 full-batch epochs, seed 42, gradient clipping at 5; best validation flow MSE selects checkpoint |

CTM uses density as a cell state at a step boundary, whereas LiDAR targets are interval averages. The distinction is an additional approximation. CTM speed is an outflow/end-density proxy capped at free speed. Physical-loss weights are applied to normalized variables; they cannot be equated to the paper's unknown normalization.

## Validation and reading results

Split raw time bins chronologically 60% / 20% / 20% before making sliding windows. No input or target window crosses a split boundary. Every endpoint bin in the context and forecast must be valid. Require at least 8 training, 2 validation and 2 test sequences; otherwise report insufficient data. Virtual targets remain masked. Adjacent held-out forecasts overlap, so their errors are correlated, not independent trials.

MMCE uses each predicted node flow as its outgoing edge flow, shared with the next cell; upstream inflow is CTM-admitted persisted demand. A separate diagnostic measures the density correction against the pure CTM branch fluxes. Neither boundary demand nor virtual-cell truth is independently observed.

The output includes flow RMSE/MAE/MAPE at 15/60 minutes, zero-target exclusions for MAPE, persistence and pure-CTM baselines, two MMCE normalizations, held-out forecast intervals, selected epoch, feature coverage and configuration. The model is not declared useful merely because training succeeds. One day has no independent day-to-day or seasonal test; a robust study needs many days, calibrated regions and independent count validation.

Artifacts in the capture folder:

- `*.jsonl.gz`: original received observations; private, ignored by Git.
- `manifest.json`, `config.json`, `*-status.json`: provenance, deadline and reception evidence.
- `eastbound-features.npz`, `westbound-features.npz`: q/k/v plus masks, start and interval.
- `eastbound.pt`, `westbound.pt`: local model state and configuration when training is possible.
- `report.json`: actual held-out results or explicit insufficient-data status. Synthetic smoke tests are saved separately and never displayed as field results.

## Running it

From the repository root, install the optional ML environment once:

```sh
python3 -m venv .venv-deepctm
.venv-deepctm/bin/python -m pip install -r deepctm/requirements.txt
```

Use the existing SDK environment `.venv` for collection. On macOS double-click `scripts/capture_deepctm.command`, enter credentials privately and leave Terminal open. Double-click `scripts/open_deepctm.command` to view `http://127.0.0.1:8768/`. This address is local to this computer. The ordinary dashboard also links to `deepctm.html` from Historical performance after its server is restarted with the new code.

Manual re-analysis after a completed capture:

```sh
.venv-deepctm/bin/python -m deepctm.experiment --capture data/deepctm/<UTC-start> --epochs 40
```

Tests:

```sh
.venv-deepctm/bin/python -m unittest deepctm.test_deepctm -v
.venv/bin/python -m unittest discover -s dashboard/tests -q
```

The paper is supplied locally and is not copied into Git. Optional ML dependencies are isolated from the live dashboard. Optimization, live-object alignment and the existing CTM KPI formulas are unchanged.

### One-hour reception test

Double-click `scripts/record_one_hour.command` and enter credentials privately. It uses `--seconds 3600 --record-only`, creates a new capture folder, and stops after one hour without launching training. Existing recordings are not overwritten. One hour is insufficient for this model's separate training, validation and test windows.
