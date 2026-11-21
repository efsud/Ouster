# Toronto live API test — 2026-09-28

The user supplied API access and authorized approximate location markers and a
one-hour recording test. Credentials were entered through the hidden local prompt;
none were added to code, GitHub, command arguments or documentation.

## Observed reception

The supplied SDK settings are used: `singleton=True`, FRAME, PHASE_CHANGE and
LOOP_CHANGE subscriptions, `semantic_abs=False`. Nine sites delivered real events
and the collector committed them to the ignored local SQLite database:

- Driftwood C618861
- Signet C251071
- Jane C351163
- Albion C251052
- Weston C257220
- Kipling C257238
- Martin Grove C257208
- York Gate C251055
- Islington C251064

Norfinch C618857 returns `beacon_http_404` at the routing endpoint. This establishes
a routing failure, not its cause; entitlement/routing/site availability needs
vendor confirmation. No remote configuration was changed.

All sampled event timestamps lack a UTC offset. README_sub.md calls the timestamps
ISO 8601 but does not establish a timezone for offset-free strings. The SDK itself
parses them as naive datetimes. The samples are broadly consistent with UTC, but
this is an inference, not verified clock metadata. Original events and receipt
clocks are retained with `unknown_timezone` quarantine. They are inspectable in
Received observations; they are not silently promoted to calibrated live frames
or operational KPIs. Some sampled sites also show substantial delay under the
UTC interpretation; those differences are not a certified latency measurement.

## One-hour recording

`scripts/start_connected.py --toronto --port 8768 --duration 3600` was launched.
The timer runs from service startup, including authentication time. It stops SDK
collectors and their process groups after one hour, while already committed
observations remain under the existing 30-day raw-retention rule. Duration zero
preserves the existing run-until-Ctrl+C behavior. The dashboard preview on port
8765 can continue reading the saved database after the recorder stops.

This report records the successful initial reception, **not completion of the
full hour**. An uninterrupted one-hour run still needs the end-of-run database
receipt-span/count audit. Computer sleep or process termination can interrupt it.

## Approximate map positions

All ten Toronto sites now have separate `reference_location` metadata. Coordinates
were retrieved on 2026-09-28 from ArcGIS World Geocoding's
[intersection search endpoint](https://geocode.arcgis.com/arcgis/rest/services/World/GeocodeServer/findAddressCandidates).
Every result was `StreetInt`, score 100, matching the named Finch Avenue West
intersection. These are approximate street-intersection points, **not surveyed
sensor mounting positions**. The inventory retains source/date and the approximate
accuracy label. Markers use a dashed outline and an explicit tooltip; the map
fits all ten. They are never passed to the object projection/calibration pipeline.

## Learning examples and validation

- Previously a recorder ran indefinitely. `--duration 3600` now means a maximum
  one-hour service session; `--duration 120` gives a two-minute test. The parent
  sends a graceful interrupt to each process group, then forces shutdown if it
  fails to exit within five seconds. Committed batches remain in SQLite.
- `origin` is a calibrated sensor reference; `reference_location` is a street
  landmark for navigation. Keeping them separate prevents a convenient map pin
  from silently becoming an inaccurate coordinate transformation.
- A recent receipt can show “receiving” while the sensor clock is unverified.
  Connection, clock interpretation and spatial calibration are separate facts.
- 41 Python tests pass, including existing storage and map-calibration gates.
  Browser smoke coverage now explicitly checks all ten Toronto reference markers.
  A mocked launcher test verifies the duration deadline and shutdown of all eleven
  child process groups without a network connection.
