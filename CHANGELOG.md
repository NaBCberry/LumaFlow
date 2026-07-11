# Changelog

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
