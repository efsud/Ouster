# Florida live map

## Current dashboard and rolling figures

Open http://127.0.0.1:8775/?region=Florida#map for the combined dashboard. Its Florida figure panel now defaults to **Latest rolling hour**, rather than the frozen November 24 study. The recording selector still offers that frozen hour explicitly. Solid trajectories are observations; the separate dashed layers are estimates. Fresh live objects update independently of the figures, which rebuild every 30 minutes from the preceding hour (a shorter partial window during startup). The rolling buffer retains 90 minutes.

On November 27, a reception check found all seven Florida latest frames stale and the rolling figure and estimated layer expired. The collector processes had survived their supervisor, so they could not recover stalled streams. They were stopped for a clean private-login restart. This diagnosis does not establish resumed reception: verify advancing receipt timestamps and event counts after login, then check that rolling observations and estimated layers share the same snapshot timestamp. A running server alone is insufficient.

After private login, the November 27 check at 11:49 Florida time verified receipt ages of 0.08–0.31 seconds at all seven sites, advancing event counts and changing object positions. The rolling writer retained the newly received frames, and the fresh 11:48:21 snapshot contained 1,101 observed fragments with 59 within-intersection and 89 between-intersection estimates. The reconstruction's source timestamp matched the figure exactly. These counts cover both directions and the short startup recording, not a complete hour or verified cross-sensor identities. A one-time refresh produced this preview; the normal half-hour update interval remains enabled.

The combined figure footer now exposes the existing **Show recorded span** control. For example, after restarting at 11:46, use it to zoom to the collected minutes instead of seeing narrow lines at the right edge of an otherwise empty hour. **Full hour** restores the requested one-hour axis. Browser verification showed current vehicles and the new dashed estimate layers together; JavaScript syntax checks passed. Keep the Florida collector Terminal open so its reconnect supervisor remains active. Sensor timezone and spatial alignment remain unverified; freshness here means local receipt age, not measured end-to-end latency.

Double-click scripts/connect_florida.command and enter BlueCity credentials privately in Terminal. Open http://127.0.0.1:8773/?region=Florida. Select an intersection to zoom in; moving objects appear at zoom 17 or greater. Keep Terminal open. Ctrl+C stops the server and collectors.

The seven configured SR-436 sensors reuse the existing live-map platform: road-user icons, movement headings, interpolation, stale-object expiry, per-sensor health and the region selector. The Florida launcher uses its own database, data/florida-live.sqlite3. It is live-only: it updates latest frames but does not archive an unlimited raw event history. Toronto recordings and separate Florida scheduled captures are unchanged.

Origins come from the saved user-confirmed SDK origin coordinates in config/sr436.json. Rotation is assumed to be 180 degrees pending scene verification. This is approximate visualization, not calibrated positioning. The preview-rotation control is temporary and does not change site settings on BlueCity. Authentication or missing-data failures are shown individually; a running process is not proof of received objects.

Example: choose Cranes Roost. The marker sits at 28.661890, -81.384276. Fresh SDK local coordinates are projected around that same point with the explicitly assumed rotation. Verify visible lane alignment before using these positions for spatial analysis.

For a map-only view after stopping the connected launcher, use scripts/open_florida_live.command. Without a collector it cannot show current objects. On a different dashboard instance the region selector still shows Florida geometry, but live data depends on that instance's configured database.
