# Portfolio walkthrough

## Narrated edition

`Ouster_Corridor_Observatory_With_My_Voice.mp4` adds Fatemeh's own recorded narration and runs **1:59.2**, in 1920 × 1080 at 25 fps with AAC audio. The scenes and burned-in captions follow the narration. `Ouster_Corridor_Observatory_Narrated_Subtitles.srt` contains the editable timed captions. There is no second embedded subtitle track, avoiding duplicated captions in players.

The original 2:23.27 voice recording is unchanged. Editing removed 8.79 seconds from long internal pauses, trimmed the leading/trailing silence, and used a 1.118837× pitch-preserving pace adjustment. Gentle filtering and loudness normalization make the narration clearer. The export uses the supplied voice recording, with no synthesized speech. Private voice-memo metadata and raw audio are not included in the repository.

Validation decoded the complete export, checked all 18 narration sections against local speech transcription, and inspected representative live, reconstruction and closing frames. Measured final audio loudness is −15.79 LUFS, with a −1.48 dBTP peak. `Narration_Validation.json` records the timing and technical checks. The task-specific `scripts/add_portfolio_narration.py` uses the private source audio, local word-timed transcript (`data/portfolio/narration-transcript.json`) and clean screen master (`data/portfolio/assembled.mp4`); these working assets remain outside Git.

## Silent edition

`Ouster_Corridor_Observatory_Walkthrough.mp4` is a 1:54, 1920 × 1080, 25 fps H.264 screen recording with burned-in English subtitles. It is silent, suitable for a portfolio or a muted social-media feed. `Ouster_Corridor_Observatory_Subtitles.srt` contains the editable captions; `Portfolio_Caption.txt` provides an introduction and a short provenance note.

## What the silent edition shows

| Time | Feature |
| --- | --- |
| 0:00–0:04 | Project introduction |
| 0:04–0:16 | Florida/Toronto network selection and intersection selection |
| 0:16–0:27 | Florida live moving objects with approximate map alignment |
| 0:27–0:36 | Received API phase colors, without claiming verified directional assignments |
| 0:36–0:57 | Recorded-hour figures, direction/object filters, site selection and pointer-centred zoom |
| 0:57–1:07 | Within-intersection estimates, off and on |
| 1:07–1:20 | Between-intersection estimates, off and on |
| 1:20–1:27 | Optional uncertain gray connections |
| 1:27–1:34 | Corridor time–space patterns |
| 1:34–1:50 | Educational CTM explorer: change green time and rerun |
| 1:50–1:54 | Closing project card |

## Recording evidence and limitations

The screen recordings were made on November 27, 2026 in an isolated browser, using the existing local dashboard. All seven Florida sensors were returning live objects during preparation. Toronto's streams were stale, so Toronto is shown only as a selectable network; the moving-object demonstration uses Florida.

The main workspace shows its rolling figure alongside live objects. The detailed historical scenes use the retained November 24 recording, `20261124T194525Z`, explicitly identified by the viewer as a frozen recording. The compact `Portfolio_Recording_Evidence.json` preserves the selected local and cross-site example provenance. Observations were not altered, and no artificial observations were inserted.

Solid lines are recorded positions. Dashed lines are model estimates; gray lines are weaker hypotheses. Cross-intersection identities and map calibration remain unverified. The CTM scene is an educational scenario, not a calibrated field prediction or a live signal-control action. The video demonstrates UI behavior, not a new accuracy-validation experiment.

No personal browser tabs, credential prompts or API credentials appear. Production website files and sensor settings were not changed for recording.

## Reproducing the artifact

The source scripts are `scripts/record_portfolio_walkthrough.cjs` and `scripts/render_portfolio_video.py`. Recording requires the local dashboard, the retained study-hour data, Playwright, Chrome and FFmpeg; rendering also needs Pillow. The recording script accepts `PORTFOLIO_BASE_URL`, `PORTFOLIO_CHROME` and `CODEX_NODE_MODULES` environment overrides. Its default browser is Google Chrome on macOS.

Working recordings and visual checks are saved under ignored `data/portfolio/`. The FFmpeg encoder is supplied locally by `imageio-ffmpeg` under `data/portfolio/runtime/`, with a symlink at `data/portfolio/browser-cache/ffmpeg-1011/ffmpeg-mac` for Playwright. Runtime binaries and raw footage are not committed. The final MP4, SRT, caption, provenance and scripts are versioned in GitHub.

The export preserves full-range screen colors during conversion to H.264, adds chapter labels and subtitles outside the dashboard viewport, and trims initialization/loading time. QA checks duration, dimensions, decode integrity, live-motion frames, and before/after reconstruction scenes.
