# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**cass_logger_dev** is a desktop application for interfacing with the Cass Logger, a hardware data logger for suspension/IMU telemetry. The project has two layers:

1. **CLI package** (`src/`) — standalone Python package for serial communication with the device; independently installable
2. **GUI application** (`gui/`) — PyWebView + React desktop app that wraps the CLI

## Commands

### GUI Development

```bash
# Terminal 1 — React dev server (hot reload on http://localhost:5173)
cd gui/frontend && npm run dev

# Terminal 2 — PyWebView in dev mode (loads from localhost:5173)
DEV=1 python gui/app.py
```

### GUI Production

```bash
# Build React frontend
cd gui/frontend && npm run build

# Run with bundled frontend
python gui/app.py
```

### Frontend Type Checking / Linting

```bash
cd gui/frontend && npm run build  # tsc + vite build; catches type errors
```

### Packaging (PyInstaller)

```bash
pyinstaller --name CassLogger --windowed \
  --add-data "gui/frontend/dist:gui/frontend/dist" \
  --add-data "src:src" \
  gui/app.py
```

## Architecture

### Python–JavaScript Bridge

PyWebView provides a direct Python ↔ JS bridge — there is **no HTTP server**. The frontend calls `window.pywebview.api.method_name()`, and Python returns results synchronously or via task polling. Never introduce an HTTP server or CORS handling.

### Key Files

| File | Role |
|------|------|
| `gui/app.py` | Entry point; creates PyWebView window, switches between dev/prod URL |
| `gui/api/main_api.py` | ~30 methods exposed to the JS bridge |
| `gui/api/_result.py` | `ok(data)` / `err(msg)` helpers — all API methods return `{"ok": bool, "data": ..., "error": ...}` |
| `gui/services/cass_service.py` | Singleton wrapping `CassCommands`; manages connection state, health polling, caching |
| `gui/frontend/src/types.ts` | TypeScript interfaces + `PyApi` declaration of the bridge API |
| `gui/frontend/src/App.tsx` | Tab navigation, status header, 5-second poll loop, auto-reconnect logic |
| `src/cass_commands.py` | Core serial protocol, file ops, binary/FIT data parsing |
| `src/firmware_structs.py` | NumPy dtype definitions for firmware variants (`std`, `i2c_1`, `i2c_2`) |

### Data Flow for Long-Running Operations

File downloads run on background threads. The API method starts the thread and returns a `task_id` immediately; the frontend polls `get_task_status(task_id)` every ~1 second. Task state is stored in `self._tasks[task_id]` with a `threading.Lock()`.

### Adding New Device Controls

1. Implement in `CassService` or call `self._svc.cass` directly in `main_api.py`
2. Return `ok(value)` or `err(message)` from `MainApi`
3. Add declaration to `PyApi` interface in `gui/frontend/src/types.ts`
4. Call via `window.pywebview.api.method_name()` from React

### Adding Long-Running Operations

1. Spawn a daemon thread in the `MainApi` method
2. Track progress/result in `self._tasks[task_id]`
3. Return `task_id` immediately; let frontend poll `get_task_status()`

## Code Style

- **Indentation**: tabs throughout `gui/` (Python and TypeScript)
- **Python**: type hints on all new function signatures in `gui/`
- **TypeScript**: strict mode enabled; React hooks pattern

## Important Constraints

- `src/` is a standalone CLI package — the GUI imports it but never modifies it
- Only one device connection at a time (`CassService` is a singleton)
- Serial ports are opened lazily per command and closed after each operation (macOS/Windows compatibility)
- `manuallyDisconnectedRef` in `App.tsx` prevents auto-reconnect after an explicit disconnect
