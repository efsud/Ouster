# Florida reconstruction screenshot examples

These are cropped screenshots of the actual dashboard canvas, captured from
`http://127.0.0.1:8775/florida_rolling.html?between=1`. The source was the live-data
snapshot published on November 27, 2026 at 11:48:21 America/New_York time. The
figures are fixed illustrations, not a continuously refreshing recording.

* `within-before.jpg` and `within-after.jpg`: Essex Avenue, westbound,
  11:47:33–11:47:56. Only the local estimate checkbox changes. The enabled view
  contains 15 local connections.
* `between-before.jpg` and `between-after.jpg`: Palm Springs Drive and Boston
  Avenue, eastbound, 11:47:10–11:47:38. Only the between-intersection checkbox
  changes. The enabled view contains seven connections.

Gray uncertain matches, residual color-slope proposals and group-assisted
estimates are disabled in both examples. Observed positions are unchanged.
The Word methodology document includes the two enabled screenshots as Figures 1
and 2, each with a real numerical example and an editable Word cross-reference.
The disabled screenshots are retained here for comparison.

`examples.json` records the selected paths, endpoint provenance and source-file
hashes. Local identity uses sensor + session + object ID. Between-intersection
IDs are different and their association is not verified. These examples do not
measure reconstruction error or prove a server outage.

Rebuild the Word file with `scripts/create_reconstruction_methodology_doc.py`
using the bundled Python runtime obtained from `load_workspace_dependencies`.
Render with the documents skill's `render_docx.py` and inspect all three pages.
Validation on November 27 confirmed both images, captions, six SEQ/REF fields,
the two figure bookmarks, readable axes, and no page overflow.
