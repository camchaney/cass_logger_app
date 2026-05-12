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

### Using the release script (recommended)

Use the release script — it bumps all three version files, commits, tags, and pushes in one step:

```bash
python3 scripts/release.py 0.2.0
```

Optional flags:

| Flag | Effect |
|------|--------|
| `-m "message"` | Custom commit and tag message (default: `bump to version v0.2.0`) |
| `--force` | Overwrite an existing tag; also allows re-releasing the same version or a downgrade |
| `--no-push` | Commit and tag locally, but do not push to remote |
| `--dry-run` | Preview every action without making any changes |

The script updates these three files automatically:

| File | Field |
|------|-------|
| `gui/__version__.py` | `VERSION = "x.y.z"` |
| `pyproject.toml` | `version = "x.y.z"` |
| `gui/frontend/package.json` | `"version": "x.y.z"` |

> `CassLogger.iss` (Windows installer) gets the version injected from the git tag by CI — no manual edit needed.

It also guards against common mistakes: warns if you're not on `main`, errors on version downgrades or existing tags (both bypassable with `--force`), and alerts if staged changes would sneak into the version commit.

### Manual release

If you prefer to bump the version by hand, edit the three files above, then:

```bash
git add gui/__version__.py pyproject.toml gui/frontend/package.json
git commit -m "bump to version vx.y.z"
git tag -a vx.y.z -m "bump to version vx.y.z"
git push origin main
git push origin vx.y.z
```

To re-release an existing tag (e.g. after a quick fix on the same version):

```bash
git tag -af vx.y.z -m "bump to version vx.y.z"
git push origin vx.y.z --force
```

### CI trigger

GitHub Actions triggers on the tag, builds macOS (DMG) and Windows (installer) artifacts, and publishes a GitHub release automatically.

> [!IMPORTANT]
> Forcing a re-release with `--force` (script) or `git push --force` (manual) will **not** trigger an auto-update in the app. If you want users to receive the update automatically, release a new version number instead.

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
