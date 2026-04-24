# Cass Logger GUI

Desktop app wrapping the `cass_logger_dev` CLI package via PyWebView + React.

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

## Architecture

```
gui/
├── app.py            # Entry point — creates PyWebView window, loads frontend
├── api/
│   ├── main_api.py   # Flat API class exposed to JS via window.pywebview.api.*
│   └── _result.py    # ok() / err() result helpers
├── services/
│   └── cass_service.py  # Singleton wrapper around CassCommands
└── frontend/            # React + Vite TypeScript app
    └── src/
        ├── App.tsx
        ├── types.ts     # PyWebView API type declarations
        └── components/
            ├── DevicePanel.tsx
            ├── FilesPanel.tsx
            ├── DataPanel.tsx
            └── ConfigPanel.tsx
```

`src/` (the CLI package) is never modified — the GUI imports it as a read-only dependency.
