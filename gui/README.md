# Cass Logger GUI

Desktop app wrapping the `cass_logger_app` CLI package via PyWebView + React.

## Prerequisites

- Python ≥ 3.12 with the repo's `src/` package installed (`pip install -e .` from repo root)
- Node.js ≥ 18

## Setup

```bash
# Python GUI deps (from repo root)
pip install -r gui/requirements.txt

# Frontend deps
cd gui/frontend
npm install
```

## Development

Run both the Python host and the Vite dev server:

```bash
# Terminal 1 — Vite dev server (hot reload)
cd gui/frontend
npm run dev

# Terminal 2 — PyWebView host pointing at Vite
DEV=1 python gui/app.py

# WINDOWS - if running Powershell:
$env:DEV = "1"
python gui/app.py
```

## Production build

```bash
cd gui/frontend
npm run build          # outputs to gui/frontend/dist/

cd ../..
python gui/app.py      # loads from gui/frontend/dist/
```

## PyInstaller packaging

```bash
pyinstaller \
  --name "CassLogger" \
  --windowed \
  --add-data "gui/frontend/dist:gui/frontend/dist" \
  --add-data "src:src" \
  gui/app.py
```

Distributable lands in `gui/dist/`.

## Releasing a new app version

1. **Commit your changes** on `main`.

2. **Bump the version** in three places (keep them in sync):

   | File | Field |
   |------|-------|
   | `gui/__version__.py` | `VERSION = "0.1.X"` |
   | `pyproject.toml` | `version = "0.1.X"` |
   | `gui/frontend/package.json` | `"version": "0.1.X"` |

   > `CassLogger.iss` (Windows installer) gets the version injected from the git tag by CI — no manual edit needed.

You can easily navigate to these three locations by searching the codebase (<kbd>Cmd</kbd> + <kbd>Shift</kbd> + <kbd>F</kbd>) for the current version.

3. **Commit the version bump**:
   ```bash
   git add gui/__version__.py pyproject.toml gui/frontend/package.json
   git commit -m "Bump version to 0.1.X"
   ```

4. **Tag and push**:
   ```bash
   git tag v0.1.X
   git push origin main --tags
   ```

GitHub Actions triggers on the tag, builds macOS (DMG) and Windows (installer) artifacts, and publishes a GitHub release automatically.

## Releasing new firmware

Use `scripts/release_firmware.py` (requires `pip install boto3` and R2 credentials):

```bash
python scripts/release_firmware.py --changelog "Short description of changes"
```

This builds the firmware via PlatformIO, uploads the `.hex` to R2, and updates the manifest at `https://firmware.casslabs.xyz/firmware/manifest.json`. The app picks up the new version on next launch.

## Architecture

```
gui/
├── app.py               # Entry point — creates PyWebView window, loads frontend
├── __version__.py       # App version string (bump before tagging a release)
├── api/
│   ├── main_api.py      # Flat API class exposed to JS via window.pywebview.api.*
│   └── _result.py       # ok() / err() result helpers
├── services/
│   ├── cass_service.py  # Singleton wrapper around CassCommands
│   └── firmware_service.py  # Firmware manifest fetch, download, and flash
└── frontend/            # React + Vite TypeScript app
    └── src/
        ├── App.tsx
        ├── types.ts     # PyWebView API type declarations
        └── components/
            ├── DevicePanel.tsx    # Connection, firmware, device config
            ├── FilesPanel.tsx
            ├── DataPanel.tsx
            └── FirmwarePanel.tsx  # OTA firmware download and flash
```

`src/` (the CLI package) is never modified — the GUI imports it as a read-only dependency.
