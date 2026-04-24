# Product Requirements Document — Cass Logger GUI

## Overview

This document describes the addition of a graphical user interface to the existing [`cass_logger_dev`](https://github.com/mcharlesmorrison/cass_logger_dev) repository. The goal is to wrap the existing Python package in a cross-platform desktop app so that non-technical users can access every capability of the Cass Logger without touching a terminal, writing code, or editing config files.

The GUI is being added **inside the existing repo**, not in a separate one. The existing CLI package (`src/`) must remain unmodified, independently installable, and fully usable on its own. The GUI lives in parallel directories so the two layers are clearly separated.

The app must run natively on **macOS and Windows** as a standalone distributable (double-click to open).

---

## Goals

- Expose 100% of `CassCommands` functionality through a clean, approachable UI
- Require zero technical knowledge from the end user
- Ship as a packaged standalone executable for macOS and Windows
- Keep the existing CLI package (`src/cass_commands.py`) completely unmodified and independently usable
- Maintain a clear separation between CLI code and GUI code so contributors can work on either without confusion
- Keep the GUI architecture simple — no HTTP server, no extra processes, no dependencies the project doesn't actually need
- Architect the codebase so that cloud integrations (MongoDB, R2) can be added later without structural rework

---

## Non-Goals (for now)

- Publishing to the Mac App Store or Microsoft Store
- User authentication / accounts
- Cloud sync or database integration (MongoDB / R2) — architecture must anticipate this, but no implementation yet
- Mobile support
- A hosted/web version of the app

---

## Tech Stack

| Layer | Technology | Rationale |
|---|---|---|
| Desktop shell + Python↔JS bridge | **PyWebView** | Native OS window with a built-in JS API bridge — no HTTP server needed |
| Frontend | **React + Vite** (TypeScript) | Fast dev experience, component-driven UI |
| Packaging | **PyInstaller** | Bundles Python runtime + React build into a single distributable |
| Underlying package | **`cass_logger_dev`** (this repo's `src/`) | Imported directly; already installable via `pyproject.toml` |

### Why no HTTP server / no FastAPI

This is a purely local app. PyWebView already provides a direct Python↔JavaScript bridge, which eliminates an entire layer of complexity — no port management, no JSON route plumbing, no second process to launch and tear down, no CORS, no web server in the PyInstaller bundle.

If a future cloud sync feature requires HTTP, the cloud module will own its own client; the local app does not need to be HTTP-shaped to support that.

---

## Repository Structure

The existing repo layout is preserved. The GUI is added under a dedicated top-level `gui/` directory so the separation between CLI and GUI is immediately obvious.

```
cass_logger_dev/
├── src/                         # CLI package — UNCHANGED, independently usable
├── examples/                    # CLI usage examples — UNCHANGED
├── gui/                         # NEW — all GUI code lives here
│   ├── app.py                   # PyWebView entry point
│   ├── api/                     # Python-side methods exposed to the frontend
│   ├── services/                # Singleton wrapper(s) around CassCommands
│   ├── frontend/                # React + Vite app
│   ├── requirements.txt         # GUI-only Python deps
│   ├── build/                   # PyInstaller artifacts (gitignored)
│   ├── dist/                    # Output executables (gitignored)
│   └── README.md                # GUI-specific setup and build instructions
├── requirements.txt             # CLI requirements — UNCHANGED
├── pyproject.toml               # Existing package config — UNCHANGED
├── README.md                    # Top-level README — add a section pointing to gui/
├── PRD.md                       # This file
└── LICENSE
```

### Key separation principles

- **Nothing in `src/` imports anything from `gui/`.** The CLI package must remain standalone.
- **`gui/` imports from `src/` freely** (via the existing `cass_logger_dev` package).
- **GUI dependencies are isolated** in `gui/requirements.txt` and `gui/frontend/package.json` — they are not added to the root `requirements.txt`.
- **GUI build artifacts** (`gui/build/`, `gui/dist/`, `gui/frontend/node_modules/`, `gui/frontend/dist/`) must be added to `.gitignore`.

---

## Modes of Operation

### Standalone (only mode)
Launching the GUI opens a native PyWebView window. In production this becomes a single double-clickable executable.

### Frontend dev workflow
During React development, the Vite dev server should be usable while still running through PyWebView (so the JS bridge works). This enables hot reload for frontend iteration.

### CLI (unchanged)
Existing CLI usage via `src/cass_commands.py` and the example scripts in `examples/` continues to work exactly as before. Users who prefer the CLI never need to install GUI dependencies.

---

## Features

All features map directly to methods in `CassCommands`. The UI should group them into logical sections.

### 1. Device Connection

- On launch, the app should automatically attempt to detect and connect to a Cass Logger
- Display clear connection status (connected / not connected / error) at all times in the UI
- **Manual port override:** if auto-detection fails, provide a UI to list available ports and let the user pick the data port and command port manually (wraps `get_serial_ports()`, `set_manual_serial_ports()`, `list_available_ports()`)
- **Windows diagnostics:** surface the output of `diagnose_windows_ports()` in a help/diagnostic panel for Windows users who can't connect
- Show the detected firmware version and device ID once connected

### 2. File Management

- **List files:** display all files on the SD card in a table with name and size (`list_files()`, `list_file_sizes()`)
- **Download all:** one-click download of all files to a user-chosen local folder; show a progress indicator (`download_all()`)
- **Delete all:** delete all files from the SD card with a confirmation dialog (`delete_all_files(prompt_user=True)`)

### 3. Data Processing & Visualization

- **Load & parse file:** user selects a local `.bin` file; app parses it with `process_data_file()` and displays a preview table of the resulting DataFrame
- **Firmware version selector:** allow the user to specify `fw_ver` (`std`, `i2c_1`, `i2c_2`) when parsing — default to `std`
- **Plot suspension data:** two-panel time-series chart of fork (`a0`) and shock (`b0`) potentiometer data, with configurable gain constants (`FORK_GAIN`, `SHOCK_GAIN`)
- **Plot IMU data:** three-panel time-series chart of internal IMU axes (`gx`, `gy`, `gz`)
- **Parse FIT file:** user selects a `.fit` file; app shows session and record DataFrames in tabs (`process_fit_file()`)
- **Export to CSV:** allow exporting any parsed DataFrame to a local CSV file

### 4. Device Configuration

- **Set RTC time:** one-click sync of device clock to current UTC (`set_RTC_time()`)
- **Get RTC time:** display current device RTC time (`get_RTC_time()`)
- **Get / Set device ID:** display current device ID, allow editing and writing to EEPROM (`get_device_ID()`, `put_device_ID()`)
- **Get / Set RTC install timestamp:** display and optionally update the RTC battery install date (`get_rtc_install_timestamp()`, `put_rtc_install_timestamp()`)
- **Get firmware version:** display firmware version string (`get_fw_ver()`)

### 5. Metadata

- **Find and parse metadata:** given a local directory, search for `metadata.txt` and display firmware version and device ID (`find_and_parse_metadata()`)

---

## Future: Cloud Integration (MongoDB + R2)

> **Do not implement now.** The architecture should make this a clean addition.

- A reserved stub module under `gui/api/` will hold placeholder cloud methods
- Ride data (parsed DataFrames from `.bin` files) will eventually be uploaded to **Cloudflare R2** object storage
- Session metadata (device ID, firmware version, timestamps, ride duration, etc.) will be written to **MongoDB**
- The singleton service pattern in `gui/services/` makes it easy to add a cloud service alongside the existing one later
- The cloud module will own its own HTTP client — this does not require turning the local app into an HTTP server
- No credentials, config schemas, or upload logic should be written until this work begins

---

## API Surface (Conceptual)

The frontend interacts with Python via a JS bridge. The exposed surface should be organized into namespaces matching the feature groups above:

- **Device:** status, port listing, connect/disconnect, RTC get/set, device ID get/set, firmware version, RTC install timestamp get/set
- **Files:** list with sizes, download all, delete all
- **Data:** parse `.bin`, parse `.fit`, export to CSV
- **Cloud:** reserved stub for future MongoDB + R2 work

Expected error conditions (no device connected, file not found, parse failure, etc.) should be returned as structured results with human-readable messages — not raised as exceptions that surface raw Python tracebacks in the UI.

---

## UX Principles

- **Status always visible:** device connection state should be in a persistent header/sidebar — never hidden
- **Errors are human-readable:** no stack traces shown to users; translate serial/OS errors into plain English (e.g. "No device found — make sure the logger is plugged in and powered on")
- **Confirmation for destructive actions:** any delete or overwrite operation must require explicit user confirmation
- **Progress feedback:** file downloads and long operations must show a progress bar or spinner; the UI must never appear frozen
- **Sensible defaults:** firmware version defaults to `std`; download directory defaults to the user's Downloads folder

---

## Threading Considerations

PyWebView's JS bridge calls run on the main thread by default, which means long-running serial operations (downloads, large file reads) would block the UI if called directly. The implementation must run these operations on a background thread and provide a way for the frontend to observe progress (e.g. polling a status method). The exact mechanism is left to implementation.

---

## Packaging & Distribution

- **macOS:** PyInstaller `.app` bundle, distributable as a `.dmg`
- **Windows:** PyInstaller `.exe`, distributable as an installer (NSIS or similar) or a standalone `.exe`
- The React app must be built before running PyInstaller; the resulting build artifacts are included in the bundle
- Target a single-file or single-folder distributable — users should not need to install Python, Node, or any dependencies
- All build outputs go under `gui/dist/` — never mixed with CLI artifacts

---

## Code Style

- Python: **tabs** for indentation (not spaces) — applies to all GUI code; CLI code in `src/` retains its current style
- TypeScript/React: **tabs** for indentation
- Python type hints on all new function signatures in `gui/`
- The `CassCommands` instance lives as a singleton — never instantiate it inside an API method

---

## Out of Scope

- Any modification to `src/cass_commands.py` or `src/firmware_structs.py` — treat the CLI package as a read-only dependency from the GUI's perspective
- Direct SD card access without a connected device
- Multi-device support (one connected logger at a time)
- Real-time streaming / live data plotting (can be revisited later)
- HTTP server / REST API — explicitly out of scope; revisit only if a concrete need appears
