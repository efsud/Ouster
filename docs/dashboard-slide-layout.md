# Dashboard layout from the supplied slide

The main dashboard now uses the user's 1600 × 900 slide as its layout reference.
The permanent sidebar, introductory heading and summary cards no longer occupy
the live workspace. A 76 px toolbar contains the compact OUSTER mark, live-object
toggle, rotation preview and Network selector.

The viewport below the toolbar is divided into a 59.25% left workspace and a
40.75% right workspace. The left side contains the map and scrollable intersection
list, followed by the selected intersection's actual API phase cards. The right
side contains intersection filters, direction/object filters, reconstruction
checkboxes and the interactive time-space figure. At 1600 × 900, the map is
approximately 666 × 433 px, begins at y=135, and the phase panel begins at y=607,
matching the reference's main panel boundaries. Panels expand with the viewport.

The Network selector changes the map, inventory, phase selection and embedded
figure together. Florida opens the preserved November 24 study hour; a compact
recording selector beneath the figure can switch to the latest rolling hour.
Finch opens its rolling hour. The original full-hour default, mouse-anchored zoom,
object filtering and separate reconstruction layers are retained. The compact
figure includes zoom/reset controls and a link to its full standalone view.

Click the **OUSTER** mark for the existing workspace sections, including
Historical performance, Anomalies, CTM explorer and Optimization. **Details**
beside the live phase title opens sensor reception, calibration, phase evidence
and the selected site's stored KPI tools. The figure's own **Details** button
opens its model evidence and advanced controls. These are presentation changes;
the source observations, signal interpretation and reconstruction models are
unchanged.

For example, switching Network from Florida to Toronto selects the Finch map and
loads the Finch figure with ten sensor checkboxes. Selecting Westbound changes
the figure direction independently of the map. Removing Boston from the Florida
figure leaves six selected sites without changing the underlying recording.

## Validation

- Browser checks at 1600 × 900: document scroll extent is exactly 1600 × 900;
  map, phase panel and figure fit within the viewport.
- Browser checks at 390 px width: panels stack vertically; no horizontal page
  overflow; both the map and trajectory figure retain usable heights.
- Florida/Toronto switching updates both sides; Finch showed ten figure sensor
  checkboxes and its rolling recording interval.
- Eastbound/Westbound and intersection filters update the visible trajectories.
- Sensor details open and close; the workspace menu still opens Historical
  performance and returns to the live view.
- JavaScript syntax checks and `git diff --check` pass. Original services and
  collectors continue running; only static dashboard assets changed.

Source: `dashboard/static/workspace.js` and `workspace.css` arrange the main
workspace; `rolling-workspace.js` and `rolling-workspace.css` supply the compact
embedded figure. Their styles are scoped so standalone analytical pages retain
their existing controls and layout. The API and storage contracts are unchanged.

## Visual polish

The follow-up styling pass retains the same layout and words. It adds a shared
teal control palette, clearer selected-intersection accents, softly bordered
phase cards, compact sensor-filter chips and consistent hover/focus states.
Trajectory colors and signal status meanings are unchanged. Both main and
embedded styles are scoped; standalone figures retain their existing layout.

The trajectory column now starts at the top of the desktop viewport, beside the
left toolbar, recovering the previously empty 76 px strip for the figure. The
map and phase panels keep their positions. Narrow stacked layouts keep the
shared toolbar above both panels. The filter box grows with its contents so
wrapping sensor labels cannot hide the fourth reconstruction checkbox.
