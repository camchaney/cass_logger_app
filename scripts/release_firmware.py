"""Build firmware and upload it to R2.

The firmware version is read automatically from the FW_VERSION define in main.cpp.

Usage:
    python scripts/release_firmware.py
    python scripts/release_firmware.py --changelog "Fixed IMU drift"
    python scripts/release_firmware.py --dry-run

Requires:
    pip install boto3

Environment variables:
    R2_ACCESS_KEY_ID      — R2 API token (Access Key ID)
    R2_SECRET_ACCESS_KEY  — R2 API token (Secret Access Key)
"""

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

# ── Config ─────────────────────────────────────────────────────────────────────

# Firmware project is assumed to sit next to cass_logger_dev/
FIRMWARE_DIR = Path(__file__).resolve().parent.parent.parent / "cassLogger"
HEX_PATH     = FIRMWARE_DIR / ".pio" / "build" / "teensy41" / "firmware.hex"
PIO          = Path.home() / ".platformio" / "penv" / "bin" / "pio"

BUCKET      = "cass-logger-firmware"
R2_ENDPOINT = "https://3dcf54c93bec8bb69b6170a316c1c6a8.r2.cloudflarestorage.com/cass-logger-firmware"
PUBLIC_BASE = "https://pub-a45f689de46443639322741c26449513.r2.dev/cass-logger-firmware"

# ── Helpers ────────────────────────────────────────────────────────────────────

def read_fw_version() -> str:
	main_cpp = FIRMWARE_DIR / "src" / "main.cpp"
	match = re.search(r'#define FW_VERSION\s+"([^"]+)"', main_cpp.read_text())
	if not match:
		print(f"Could not find FW_VERSION in {main_cpp}")
		sys.exit(1)
	return match.group(1)

def sha256(path: Path) -> str:
	return hashlib.sha256(path.read_bytes()).hexdigest()

def require_env(name: str) -> str:
	val = os.environ.get(name)
	if not val:
		print(f"Error: environment variable {name} is not set.")
		sys.exit(1)
	return val

# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
	parser = argparse.ArgumentParser(description="Build and upload firmware to R2")
	parser.add_argument("--changelog", default="", help="Short release notes shown in the app")
	parser.add_argument("--dry-run", action="store_true", help="Build only, skip upload")
	args = parser.parse_args()

	if not FIRMWARE_DIR.is_dir():
		print(f"Firmware directory not found: {FIRMWARE_DIR}")
		sys.exit(1)

	version = read_fw_version()

	# ── Build ──────────────────────────────────────────────────────────────────
	print(f"Building firmware v{version}…")
	result = subprocess.run([str(PIO), "run"], cwd=FIRMWARE_DIR)
	if result.returncode != 0:
		print("Build failed.")
		sys.exit(1)

	if not HEX_PATH.exists():
		print(f"Hex file not found after build: {HEX_PATH}")
		sys.exit(1)

	checksum = sha256(HEX_PATH)
	print(f"  {HEX_PATH.name}  {HEX_PATH.stat().st_size // 1024} KB  sha256={checksum[:16]}…")

	if args.dry_run:
		print("\nDry run — skipping upload.")
		return

	if PUBLIC_BASE == "https://YOUR_PUBLIC_URL":
		print("Error: set PUBLIC_BASE in this script before uploading.")
		sys.exit(1)

	# ── Upload to R2 ───────────────────────────────────────────────────────────
	try:
		import boto3
	except ImportError:
		print("boto3 not installed. Run: pip install boto3")
		sys.exit(1)

	s3 = boto3.client(
		"s3",
		endpoint_url=R2_ENDPOINT,
		aws_access_key_id=require_env("r2_accessKey"),
		aws_secret_access_key=require_env("r2_secretKey"),
		region_name="auto",
	)

	hex_key = f"firmware/{version}/firmware.hex"
	print(f"Uploading {hex_key}…")
	s3.upload_file(
		str(HEX_PATH), BUCKET, hex_key,
		ExtraArgs={"ContentType": "application/octet-stream"},
	)

	# ── Write and upload manifest ──────────────────────────────────────────────
	manifest = {
		"latest_version": version,
		"changelog": args.changelog,
		"variants": {
			"std": {
				"url": f"{PUBLIC_BASE}/{hex_key}",
				"sha256": checksum,
			}
		},
	}
	manifest_json = json.dumps(manifest, indent=2)
	print("Uploading firmware/manifest.json…")
	s3.put_object(
		Bucket=BUCKET,
		Key="firmware/manifest.json",
		Body=manifest_json.encode(),
		ContentType="application/json",
	)

	print(f"\nDone. Firmware v{version} is live.")
	print(manifest_json)

if __name__ == "__main__":
	main()
