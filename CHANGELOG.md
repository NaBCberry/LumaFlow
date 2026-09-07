# Changelog

## 1.9.0 - 2026-09-08

### Timeline display

- Added persistent CH0-CH9 visibility selection shared by the edit and source timelines, with CH0 as the default.
- Replaced repeated channel menu toggles with a compact multi-select dialog, including Select All and CH0 Only shortcuts.
- Rendered sparse channel selections as compact contiguous rows and limited aggregation work to visible channels.
- Reduced MARK and IDX to compact auxiliary tracks while preserving consistent proportions for any visible channel count.
- Fixed aggregated tail rendering so the last visible color extends to the next real keyframe.

### Markers and compatibility

- Normalized marker data as text even when CSV type inference reports an integer column, allowing values such as `66CCFF`.
- Treated legacy `0`, `0.0`, `null`, `None`, and `NaN` marker placeholders as empty instead of rendering labels.
- Routed marker updates through the correct undoable update command and shared safe marker writes across add, edit, and undo paths.
- Preserved the legacy `num_channels` render-worker call while supporting explicit sparse visible-channel mappings.
- Added regression coverage for channel selection, compact track layout, marker data types, placeholder filtering, and render boundaries.

### Reference media

- Expanded reference imports from video-only files to common video and audio formats, including MP3, WAV, FLAC, M4A, AAC, OGG, and Opus.
- Kept playback, seeking, timeline synchronization, audio analysis, and workspace restoration available for audio-only references.
- Hid video-only controls for audio references and exited fullscreen when replacing a video with audio.
- Cancelled stale media-load timers and video-refresh callbacks when switching reference files.
- Delivered audio analysis results, progress, and failures to both workspaces when they share the same reference file, while ignoring callbacks for replaced files.
- Routed VLC time and error callbacks through Qt signals to avoid touching widgets and timers from VLC worker threads.

### Release verification

- Included both `*_test.py` and `test_*.py` in the full regression command and stopped ignoring tests under `tests/`.
- Passed all 152 automated tests, including legacy positional render calls, Qt-thread callback routing, and reference-media routing and switching regressions.
- Verified real MP3 and MP4 decoding and Mel spectrogram generation with FFmpeg.
- Checked real VLC loading, seeking, playback, and fullscreen media switching with the Qt `minimal` backend and dummy outputs; native desktop and portable-package acceptance remain separate checks.

### Repository maintenance

- Added Windows CI for Python 3.10 and 3.12 with read-only permissions and commit-pinned GitHub Actions.
- Added editor and line-ending settings, build dependencies, contribution and security guides, and issue/PR templates.
- Refreshed the README with project badges, navigation, and an actual editor screenshot; clarified GPLv3 code licensing separately from reference sample restrictions.

## 1.8.0 - 2026-07-11

### Device output

- Added BLE transmitter discovery, connection, authentication, and STREAM output.
- Improved serial connection lifecycle so authentication is sent on each connection and reconnect no longer blocks the UI.
- Split UDP host and fixed port input, validated IPv4 targets, and added configurable STREAM repeats from 1 to 4.
- Added lightweight UDP AUTH/STREAM repetition while relying on transmitter-side duplicate filtering to avoid duplicate 433MHz frames.
- Added output-only global brightness modulation without modifying timeline data or function values.
- Included `bleak` and WinRT modules in the Windows portable package.

### Timeline editing

- Added undoable region commands for setting all channel functions, scaling RGB brightness, and setting RGB color.
- Added `Ctrl+1` through `Ctrl+4` function shortcuts and `Ctrl+Up` / `Ctrl+Down` brightness shortcuts.
- Added shared, theme-aware textures and icons for solid, 1Hz, 2Hz, and 4Hz function modes.
- Preserved blink activity and transitions in aggregated timeline rendering.
- Fixed initial color-picker HSV alignment so brightness changes retain the current frame hue.

### Workspace and media

- Added restoration of the last edit/source sequence and reference videos.
- Clarified edit workspace, material workspace, and file-menu terminology.
- Fixed video playback after reaching the end and restored the final frame and seeking behavior.
- Fixed black video output after hiding and reopening a preview dock.
- Prevented completed audio analysis from changing the current timeline viewport.
- Limited automatic fit to new/opened light sequences and the first successful video load.

### UI, packaging, and tests

- Completed light-theme styling for color dialogs, video controls, and related widgets.
- Added version and platform tags to portable executable and archive filenames.
- Added a mandatory PyInstaller archive check for the embedded Python DLL and PYZ before packaging.
- Added regression coverage for device transports, protocol output, region edits, function visuals, themes, workspace restoration, video playback, and viewport fit behavior.

## 1.7.0 - 2026-07-09

- Added initial BLE and UDP transmitter output support.
- Added UDP reliability controls and transmitter connection documentation.
