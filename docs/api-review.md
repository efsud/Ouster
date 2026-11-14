# API and specification review

Reviewed on 2026-09-23:

- `Data API/Ouster BlueCity Traffic Data API Manual.pdf`, v1.0, August 31, 2026.
- `Data API/Realtime SDK/README.md`, `README_sub.md`, `main.py`, and wheel interface.
- The user's LaTeX document, preserved as `docs/kpi-specification.tex`.

There was no root README, AGENTS.md, application, or other project guideline
in the repository at the starting commit `9dcfb9fe93b2d6e19f2d935a3527758b70a3a6ae`.

## Confirmed interfaces

The manual distinguishes cloud REST aggregates, local edge analytics, and the
live gRPC stream. The implementation uses cloud REST and the existing Python
SDK. It does not require edge credential provisioning or changes to sites.

- Authentication: POST `https://core.api.bluecity.ai/api/token/` with username/password.
- TMC: GET `https://core.api.bluecity.ai/api/v2/turningmovement/` with UDID,
  fdate, tdate; `a=1` for 15-minute buckets and `simplified=false` for classes.
  Maximum request range: 24 hours (manual pp. 11–13).
- Phase discovery: GET `https://spm.api.bluecity.ai/api/v2/spm/phase/details/customer/`;
  `active_only=false` retains historical versions (pp. 16–17). SPM is beta.
- Real time: `BCTWSConnection` from `realtime_subscriber.Realtime_subscriber_api`.
  SDK requires Python >=3.8,<3.12. Application target: 3.11.
- Frame coordinates are sensor-relative metres; object rotation is radians.
  Speed and accuracy are optional. Missing speed must not be interpreted as a stop.
- Phases: 0 invalid, 1 green, 2 yellow, 3 red. Absolute phase messages describe
  initialization; missing events and clock drift require QA before signal KPIs.

The collector stores original events. The map displays only fresh, georeferenced
frames. The API adapter only has two allowlisted read endpoints and token acquisition.

## Decisions and unresolved items

1. Toronto UDIDs were not supplied. Florida hostnames are inventory identifiers
   until API entitlement and spelling/case are verified.
2. The coordinate-conversion attachment was absent; only the LaTeX was attached.
   An independent approximate converter is included and tested at 0/90/180°.
3. The paper labels discharge per lane but its displayed equation omits lane
   normalization. We divide by lane count explicitly; confirm with the author.
4. Queue P95 uses regularly sampled visible queue extents. A missing frame is
   not an empty queue. Queue-membership annotation is a prerequisite.
5. Volume uses observed entry events; censored tracks may count entries but
   cannot contribute full-approach delay, following the paper's later caveat.
6. Negative excess travel times are retained and flagged for calibration review.
7. Low-count/low-coverage values remain visible as provisional, not silently zeroed.
8. Vendor aggregate definitions may differ from the paper. Responses are saved
   raw pending sample inspection, not treated as equivalent Tier-1 KPIs.
9. Manual and SDK text disagree on token lifetime; the adapter reacquires at
   five minutes, and the SDK handles its own renewal. Production code should
   use verified expiration/refresh behavior.
10. The provided source references `corridor_lidar_lit.bib`, which was not supplied.
    The original LaTeX is preserved rather than claimed to be a compiled paper.

## CTM reference and scope

CTM uses a triangular fundamental diagram, sending/receiving constraints, and
vehicle conservation. Primary reference: Carlos F. Daganzo,
[The Cell Transmission Model, Part I](https://its.berkeley.edu/node/2283) and
[Network Traffic](https://its.berkeley.edu/node/2251).

This implementation uses one through lane, 50 m cells, 2 s steps, v=13.89 m/s,
w=5 m/s, kj=0.15 veh/m. Capacity is v*w*kj/(v+w). The CFL condition
max(v,w)*dt <= dx holds. Red signals set boundary flow to zero. Demand not
admitted to the first cell stays in a source queue. All values are uncalibrated
educational scenarios; no inferred RL or field performance claim is made.
