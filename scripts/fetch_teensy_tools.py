"""Download the tool-teensy package from the PlatformIO registry for the current platform."""

import json
import platform
import ssl
import sys
import tarfile
import tempfile
import urllib.request
from pathlib import Path

REGISTRY_URL = "https://api.registry.platformio.org/v3/packages/platformio/tool/tool-teensy"
DEST = Path(__file__).resolve().parent.parent / "bin" / "tool-teensy"

SYSTEM_MAP = {
    "darwin":  "darwin_x86_64",   # covers both arm64 and x86_64
    "windows": "windows_arm64",   # covers all Windows variants
}

def main() -> None:
    system = platform.system().lower()
    pio_system = SYSTEM_MAP.get(system)
    if pio_system is None:
        print(f"Unsupported platform: {system}")
        sys.exit(1)

    print(f"Fetching tool-teensy metadata for {pio_system}…")
    ctx = ssl.create_default_context()
    with urllib.request.urlopen(REGISTRY_URL, context=ctx, timeout=15) as resp:
        meta = json.loads(resp.read())

    version = meta["version"]["name"]
    files = meta["version"]["files"]
    entry = next(f for f in files if pio_system in f["system"])
    url = entry["download_url"]

    print(f"Downloading tool-teensy {version} from {url}")
    with tempfile.NamedTemporaryFile(suffix=".tar.gz", delete=False) as tmp:
        with urllib.request.urlopen(url, context=ctx, timeout=60) as resp:
            tmp.write(resp.read())
        tmp_path = Path(tmp.name)

    DEST.mkdir(parents=True, exist_ok=True)
    print(f"Extracting to {DEST}")
    with tarfile.open(tmp_path) as tar:
        tar.extractall(DEST, filter="data")
    tmp_path.unlink()

    # Ensure binaries are executable
    for name in ("teensy_loader_cli", "teensy_reboot", "teensy_loader_cli_bin"):
        p = DEST / name
        if p.exists():
            p.chmod(p.stat().st_mode | 0o111)

    print("Done.")

if __name__ == "__main__":
    main()
