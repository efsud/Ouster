# Rolling figures in Historical Performance

The original combined live dashboard now embeds both rolling figures in its Historical Performance tab:

- Toronto, Ontario — Finch corridor.
- Altamonte Springs, Florida — SR-436 corridor.

Each chart retains its intersection, direction, object filters and zoom controls. The figures load when the tab is opened, with full-window links for larger viewing. They use the existing independent 60-minute snapshots, 30-minute refresh and 90-minute buffers; embedding does not start another collector.

The dashboard serves the snapshots on its own origin, so embedded charts do not depend on a separate localhost port. Only the two chart pages permit same-origin framing; other pages retain their framing restriction. The public live-only allowlist remains unchanged. Saved experiments and KPI calculations remain below the figures.

Validation: dashboard unit tests and JavaScript syntax check. Existing missing-data and provisional-alignment labels remain visible.
