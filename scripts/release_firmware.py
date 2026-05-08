"""Build all firmware variants and upload them to R2.

Usage:
    python scripts/release_firmware.py 0.09
    python scripts/release_firmware.py 0.09 --changelog "Fixed IMU drift"
    python scripts/release_firmware.py 0.09 --dry-run

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
import subprocess
import sys
from pathlib import Path

# ── Config ─────────────────────────────────────────────────────────────────────

# Firmware project is assumed to sit next to cass_logger_dev/
FIRMWARE_DIR = Path(__file__).resolve().parent.parent.parent / "cassLogger"

BUCKET       = "cass-logger-firmware"
R2_ENDPOINT  = "https://3dcf54c93bec8bb69b6170a316c1c6a8.r2.cloudflarestorage.com"
PUBLIC_BASE  = "https://YOUR_PUBLIC_URL"   # ← replace with R2 public URL or Worker URL

VARIANTS = ["std", "i2c_1", "i2c_2"]

# ── Helpers ────────────────────────────────────────────────────────────────────

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
	parser.add_argument("version", help="Firmware version string, e.g. 0.09")
	parser.add_argument("--changelog", default="", help="Short release notes shown in the app")
	parser.add_argument("--dry-run", action="store_true", help="Build only, skip upload")
	args = parser.parse_args()

	if not FIRMWARE_DIR.is_dir():
		print(f"Firmware directory not found: {FIRMWARE_DIR}")
		sys.exit(1)

	# ── Build all environments ─────────────────────────────────────────────────
	print(f"Building firmware v{args.version} ({', '.join(VARIANTS)})…")
	result = subprocess.run(["pio", "run"], cwd=FIRMWARE_DIR)
	if result.returncode != 0:
		print("Build failed.")
		sys.exit(1)

	# ── Collect and verify hex files ───────────────────────────────────────────
	hex_files: dict[str, Path] = {}
	for variant in VARIANTS:
		p = FIRMWARE_DIR / ".pio" / "build" / variant / "firmware.hex"
		if not p.exists():
			print(f"Missing build output: {p}")
			sys.exit(1)
		hex_files[variant] = p
		print(f"  {variant}: {p.stat().st_size // 1024} KB  sha256={sha256(p)[:16]}…")

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
		aws_access_key_id=require_env("R2_ACCESS_KEY_ID"),
		aws_secret_access_key=require_env("R2_SECRET_ACCESS_KEY"),
		region_name="auto",
	)

	variants_meta: dict = {}
	for variant, hex_path in hex_files.items():
		key = f"firmware/{args.version}/{variant}.hex"
		print(f"Uploading {key}…")
		s3.upload_file(
			str(hex_path), BUCKET, key,
			ExtraArgs={"ContentType": "application/octet-stream"},
		)
		variants_meta[variant] = {
			"url": f"{PUBLIC_BASE}/{key}",
			"sha256": sha256(hex_path),
		}

	# ── Write and upload manifest ──────────────────────────────────────────────
	manifest = {
		"latest_version": args.version,
		"changelog": args.changelog,
		"variants": variants_meta,
	}
	manifest_json = json.dumps(manifest, indent=2)
	print("Uploading firmware/manifest.json…")
	s3.put_object(
		Bucket=BUCKET,
		Key="firmware/manifest.json",
		Body=manifest_json.encode(),
		ContentType="application/json",
	)

	print(f"\nDone. Firmware v{args.version} is live.")
	print(manifest_json)


if __name__ == "__main__":
	main()
