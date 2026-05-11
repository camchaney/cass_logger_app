# Teensy Flash Tools

Place platform-specific Teensy flash tool binaries here before building the app.

## Required binaries

| File | macOS arm64 | Windows |
|------|-------------|---------|
| `teensy_loader_cli` / `teensy_loader_cli.exe` | ✓ | ✓ |
| `teensy_reboot` / `teensy_reboot.exe` | ✓ | ✓ |

## Getting the binaries

### Option A — Extract from your PlatformIO installation

PlatformIO bundles both tools. After installing the Teensy platform in PlatformIO, find them at:

- **macOS**: `~/.platformio/packages/tool-teensy/teensy_loader_cli` and `teensy_reboot`
- **Windows**: `%USERPROFILE%\.platformio\packages\tool-teensy\teensy_loader_cli.exe` and `teensy_reboot.exe`

Copy the appropriate binaries into this `bin/` directory.

### Option B — Build from source

- `teensy_loader_cli`: https://github.com/PaulStoffregen/teensy_loader_cli
- `teensy_reboot`: included in the Teensy tools repo or available via `brew install teensy_loader_cli` on macOS

## CI/CD

The GitHub Actions release workflow should download or cache these binaries before running PyInstaller.
The `CassLogger.spec` file will silently skip bundling if the binaries are absent, so builds without
them will still succeed — firmware flashing just won't work in those builds.
