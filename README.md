# Cass Logger App

Desktop application for the [Cass Logger](https://github.com/mcharlesmorrison/cass_logger_dev) — a hardware data logger for suspension/IMU telemetry. Built with PyWebView + React.

> **Platform support:** macOS and Windows

---

## Setup

**Prerequisites:** Python ≥ 3.12, Node.js ≥ 18

```bash
# Python deps (installs cass-logger-dev from GitHub + GUI deps)
pip install -e .

# Frontend deps
cd gui/frontend && npm install
```

---

## Development

```bash
# Terminal 1 — Vite dev server (hot reload)
cd gui/frontend && npm run dev

# Terminal 2 — PyWebView host pointing at Vite
DEV=1 python gui/app.py

# Windows (PowerShell)
$env:DEV = "1"; python gui/app.py
```

## Production build

```bash
cd gui/frontend && npm run build   # outputs to gui/frontend/dist/
python gui/app.py                  # loads from gui/frontend/dist/
```

---

## Releasing a new app version

1. **Bump the version** in three places:

   | File | Field |
   |------|-------|
   | `gui/__version__.py` | `VERSION = "x.y.z"` |
   | `pyproject.toml` | `version = "x.y.z"` |
   | `gui/frontend/package.json` | `"version": "x.y.z"` |

   > `CassLogger.iss` (Windows installer) gets the version injected from the git tag by CI — no manual edit needed.

   Tip: search the codebase for the current version string to find all three locations quickly.

2. **Commit and tag**:
   ```bash
   git add gui/__version__.py pyproject.toml gui/frontend/package.json
   git commit -m "Bump version to x.y.z"
   git tag vx.y.z
   git push origin main --tags
   ```

GitHub Actions triggers on the tag, builds macOS (DMG) and Windows (installer) artifacts, and publishes a GitHub release automatically.

## Releasing new firmware

Requires `pip install boto3` and R2 credentials in the environment.

```bash
python scripts/release_firmware.py --changelog "Short description of changes"
```

This builds the firmware via PlatformIO, uploads the `.hex` to R2 as `{version}/logger-firmware_{version}_std.hex`, and updates the manifest at `https://firmware.casslabs.xyz/manifest.json`. The app picks up the new version on next launch.

---

## Architecture

```
gui/
├── app.py               # Entry point — creates PyWebView window, loads frontend
├── __version__.py       # App version string (bump before tagging a release)
├── api/
│   ├── main_api.py      # Flat API class exposed to JS via window.pywebview.api.*
│   └── _result.py       # ok() / err() result helpers
├── services/
│   ├── cass_service.py      # Singleton wrapper around CassCommands
│   ├── firmware_service.py  # Firmware manifest fetch, download, and flash
│   └── update_service.py    # App auto-update logic
└── frontend/            # React + Vite TypeScript app
    └── src/
        ├── App.tsx
        ├── types.ts     # PyWebView API type declarations
        └── components/
```

The CLI package (`cass-logger-dev`) is imported as a dependency — never modified here. The GUI calls it via `CassService`, which wraps `CassCommands` as a singleton and manages connection state.

PyWebView provides a direct Python ↔ JS bridge — there is no HTTP server. The frontend calls `window.pywebview.api.method_name()` directly.
