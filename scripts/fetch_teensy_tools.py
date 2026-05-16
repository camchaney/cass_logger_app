"""Download the tool-teensy package from the PlatformIO registry.

On macOS, downloads both arm64 and x86_64 builds and merges teensy_loader_cli
into a universal binary with `lipo`, so a single app bundle runs on both Intel
and Apple Silicon machines.  If the CI workflow has already placed a universal
binary at the destination, this script skips the download entirely.
"""

import json
import platform
import shutil
import ssl
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
from pathlib import Path

REGISTRY_URL = "https://api.registry.platformio.org/v3/packages/platformio/tool/tool-teensy"
DEST = Path(__file__).resolve().parent.parent / "bin" / "tool-teensy"

# PlatformIO system identifiers for each arch we care about
DARWIN_SLICES = ["darwin_x86_64", "darwin_arm64"]
WINDOWS_SYSTEM = "windows_arm64"   # covers all Windows variants


def _is_universal(path: Path) -> bool:
    """Return True if path is a Mach-O universal (fat) binary."""
    result = subprocess.run(["file", str(path)], capture_output=True, text=True)
    return "universal binary" in result.stdout


def _fetch_meta(ctx: ssl.SSLContext) -> dict:
    with urllib.request.urlopen(REGISTRY_URL, context=ctx, timeout=15) as resp:
        return json.loads(resp.read())


def _download_tar(url: str, ctx: ssl.SSLContext) -> Path:
    with tempfile.NamedTemporaryFile(suffix=".tar.gz", delete=False) as tmp:
        with urllib.request.urlopen(url, context=ctx, timeout=60) as resp:
            tmp.write(resp.read())
    return Path(tmp.name)


def _extract_binary(tar_path: Path, binary_name: str, dest_path: Path) -> bool:
    """Extract a single named binary from a tar.gz into dest_path. Returns True on success."""
    with tarfile.open(tar_path) as tar:
        for member in tar.getmembers():
            if member.name.endswith(binary_name) and member.isfile():
                member.name = dest_path.name
                tar.extract(member, dest_path.parent, filter="data")
                dest_path.chmod(dest_path.stat().st_mode | 0o111)
                return True
    return False


def _lipo_universal(slices: list[Path], output: Path) -> None:
    """Merge arch-specific binaries into a universal (fat) binary using lipo."""
    subprocess.run(
        ["lipo", "-create", "-output", str(output)] + [str(s) for s in slices],
        check=True,
    )
    output.chmod(output.stat().st_mode | 0o111)


def _homebrew_copy(dest: Path) -> bool:
    """Copy teensy_loader_cli from Homebrew if available. Returns True on success."""
    for candidate in (
        Path("/opt/homebrew/bin/teensy_loader_cli"),
        Path("/usr/local/bin/teensy_loader_cli"),
    ):
        if candidate.exists():
            if dest.exists():
                dest.unlink()
            shutil.copy2(candidate, dest)
            dest.chmod(dest.stat().st_mode | 0o111)
            print(f"Copied teensy_loader_cli from {candidate}")
            return True
    return False


def main() -> None:
    system = platform.system().lower()
    ctx = ssl.create_default_context()

    print("Fetching tool-teensy metadata…")
    meta = _fetch_meta(ctx)
    version = meta["version"]["name"]
    files = meta["version"]["files"]
    print(f"Latest tool-teensy: {version}")

    DEST.mkdir(parents=True, exist_ok=True)

    if system == "darwin":
        loader = DEST / "teensy_loader_cli"

        # If CI already produced a universal binary, don't overwrite it.
        if loader.exists() and _is_universal(loader):
            print(f"  ✓ Universal binary already present at {loader} — skipping download.")
            print("Done.")
            return

        # Download arm64 and x86_64 separately, then lipo them into a universal binary.
        # This ensures the bundled app works on both Intel and Apple Silicon Macs.
        slice_paths: list[Path] = []

        for pio_system in DARWIN_SLICES:
            entries = [f for f in files if pio_system in f.get("system", "")]
            if not entries:
                print(f"  No PlatformIO package for {pio_system}, skipping.")
                continue

            url = entries[0]["download_url"]
            print(f"  Downloading {pio_system}…")
            tar_path = _download_tar(url, ctx)

            slice_bin = DEST / f"teensy_loader_cli_{pio_system}"
            if _extract_binary(tar_path, "teensy_loader_cli", slice_bin):
                slice_paths.append(slice_bin)
                print(f"  Extracted teensy_loader_cli ({pio_system})")
            else:
                print(f"  teensy_loader_cli not found in {pio_system} package.")

            tar_path.unlink()

        if len(slice_paths) == 2:
            print("  Creating universal binary with lipo…")
            _lipo_universal(slice_paths, loader)
            print(f"  ✓ Universal binary at {loader}")
            for s in slice_paths:
                s.unlink()
        elif len(slice_paths) == 1:
            # Only one arch available from PlatformIO — use it directly
            slice_paths[0].rename(loader)
            arch = "arm64" if "arm64" in slice_paths[0].name else "x86_64"
            print(f"  ✓ Single-arch binary ({arch}) at {loader}")
        else:
            # PlatformIO package has no loader binary — fall back to Homebrew
            if not _homebrew_copy(loader):
                print("Warning: teensy_loader_cli not found in PlatformIO packages or Homebrew.")
                print("  Install it: brew install teensy_loader_cli")

    elif system == "windows":
        entries = [f for f in files if WINDOWS_SYSTEM in f.get("system", "")]
        if not entries:
            print(f"No PlatformIO package found for {WINDOWS_SYSTEM}")
            sys.exit(1)

        url = entries[0]["download_url"]
        print(f"Downloading {WINDOWS_SYSTEM}…")
        tar_path = _download_tar(url, ctx)

        print(f"Extracting to {DEST}")
        with tarfile.open(tar_path) as tar:
            tar.extractall(DEST, filter="data")
        tar_path.unlink()

    else:
        print(f"Unsupported platform: {system}")
        sys.exit(1)

    # Mark all known binaries executable (belt-and-suspenders for Windows .exe paths)
    for name in ("teensy_loader_cli", "teensy_reboot", "teensy_loader_cli_bin",
                 "teensy_loader_cli.exe", "teensy_reboot.exe"):
        p = DEST / name
        if p.exists():
            p.chmod(p.stat().st_mode | 0o111)

    print("Done.")


if __name__ == "__main__":
    main()
