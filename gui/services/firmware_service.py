"""Service for downloading and flashing firmware to the Cass Logger device."""

import hashlib
import json
import platform
import ssl
import subprocess
import sys
import threading
import urllib.request
import uuid
from pathlib import Path
from typing import Optional

import certifi
import platformdirs

from gui.__version__ import VERSION as APP_VERSION

# ── Configuration ──────────────────────────────────────────────────────────────

# Public R2 URL for the firmware manifest. Replace with your actual bucket URL.
FIRMWARE_MANIFEST_URL = "https://pub-a45f689de46443639322741c26449513.r2.dev/cass-logger-firmware/firmware/manifest.json"

_APP_NAME = "CassLogger"
_CACHE_DIR = Path(platformdirs.user_cache_dir(_APP_NAME))
_DATA_DIR = Path(platformdirs.user_data_dir(_APP_NAME, roaming=False))

# In dev: repo root (3 levels up from gui/services/firmware_service.py)
# In packaged app: sys._MEIPASS
_ROOT = Path(__file__).resolve().parent.parent.parent
_BUNDLE_DIR = Path(getattr(sys, "_MEIPASS", _ROOT))


def _tool(name: str) -> Path:
	suffix = ".exe" if platform.system() == "Windows" else ""
	full = name + suffix
	# Prefer bundled copy (works in packaged app and after fetch_teensy_tools.py)
	bundled = _BUNDLE_DIR / "bin" / "tool-teensy" / full
	if bundled.exists():
		return bundled
	# Fall back to Homebrew (dev machine)
	for prefix in (Path("/opt/homebrew/bin"), Path("/usr/local/bin")):
		p = prefix / full
		if p.exists():
			return p
	return bundled  # return missing path so caller reports a clear error


def _parse_ver(v: str) -> tuple[int, ...]:
	try:
		return tuple(int(x) for x in v.strip().split("."))
	except ValueError:
		return (0,)


# ── Service ────────────────────────────────────────────────────────────────────

class FirmwareService:
	"""Singleton that manages firmware manifest fetching, downloading, and flashing."""

	_instance: Optional["FirmwareService"] = None
	_init_lock = threading.Lock()

	def __new__(cls) -> "FirmwareService":
		if cls._instance is None:
			with cls._init_lock:
				if cls._instance is None:
					inst = super().__new__(cls)
					inst._lock = threading.Lock()
					inst._state = "unknown"  # unknown | ready | error
					inst._latest_version: Optional[str] = None
					inst._changelog: Optional[str] = None
					inst._variants: dict = {}  # variant -> {url, sha256}
					inst._error: Optional[str] = None
					inst._checking = False
					inst._downloads: dict[str, dict] = {}
					inst._flashes: dict[str, dict] = {}
					_CACHE_DIR.mkdir(parents=True, exist_ok=True)
					_DATA_DIR.mkdir(parents=True, exist_ok=True)
					cls._instance = inst
		return cls._instance

	# ── Manifest ───────────────────────────────────────────────────────────────

	def start_check(self) -> None:
		"""Kick off a non-blocking manifest fetch. Idempotent."""
		with self._lock:
			if self._checking or self._state != "unknown":
				return
			self._checking = True
		threading.Thread(target=self._run_check, daemon=True).start()

	def get_state(self) -> dict:
		with self._lock:
			return {
				"state": self._state,
				"latest_version": self._latest_version,
				"changelog": self._changelog,
				"available_variants": list(self._variants.keys()),
				"installed_version": self._load_prefs().get("installed_version"),
				"error": self._error,
			}

	def _run_check(self) -> None:
		try:
			manifest = _fetch_manifest()
			self._save_manifest_cache(manifest)
		except Exception:
			manifest = self._load_manifest_cache()

		with self._lock:
			self._checking = False
			if manifest is None:
				self._state = "error"
				self._error = "Could not reach firmware update server."
				return
			self._latest_version = manifest.get("latest_version")
			self._changelog = manifest.get("changelog")
			self._variants = manifest.get("variants", {})
			self._state = "ready"

	# ── Download ───────────────────────────────────────────────────────────────

	def start_download(self, variant: str) -> str:
		"""Download the .hex for the given variant. Returns a task_id to poll."""
		task_id = str(uuid.uuid4())
		task: dict = {
			"status": "running",
			"progress": 0.0,
			"downloaded_bytes": 0,
			"total_bytes": 0,
			"hex_path": None,
			"error": None,
		}
		with self._lock:
			self._downloads[task_id] = task
			entry = self._variants.get(variant)

		if not entry:
			task.update({"status": "error", "error": f"No firmware available for variant '{variant}'"})
			return task_id

		url: str = entry["url"]
		expected_sha256: Optional[str] = entry.get("sha256")
		threading.Thread(
			target=self._run_download,
			args=(task_id, url, expected_sha256, variant),
			daemon=True,
		).start()
		return task_id

	def get_download_status(self, task_id: str) -> Optional[dict]:
		with self._lock:
			task = self._downloads.get(task_id)
		return dict(task) if task is not None else None

	def _run_download(
		self, task_id: str, url: str, expected_sha256: Optional[str], variant: str
	) -> None:
		task = self._downloads[task_id]
		dest = _CACHE_DIR / f"firmware_{variant}.hex"
		try:
			ctx = ssl.create_default_context(cafile=certifi.where())
			req = urllib.request.Request(url, headers={"User-Agent": "CassLogger"})
			with urllib.request.urlopen(req, timeout=30, context=ctx) as response:
				total = int(response.headers.get("Content-Length", 0))
				task["total_bytes"] = total
				sha = hashlib.sha256()
				downloaded = 0
				with open(dest, "wb") as f:
					while True:
						chunk = response.read(65536)
						if not chunk:
							break
						f.write(chunk)
						sha.update(chunk)
						downloaded += len(chunk)
						task["downloaded_bytes"] = downloaded
						task["progress"] = downloaded / total if total else 0.0

			if expected_sha256:
				if sha.hexdigest() != expected_sha256.lower():
					dest.unlink(missing_ok=True)
					task.update({
						"status": "error",
						"error": "SHA-256 mismatch — file may be corrupted. Please retry.",
					})
					return

			task.update({"status": "done", "progress": 1.0, "hex_path": str(dest)})
		except Exception as e:
			task.update({"status": "error", "error": str(e)})

	# ── Flash ──────────────────────────────────────────────────────────────────

	def start_flash(self, download_task_id: str, variant: str) -> str:
		"""Run teensy_reboot + teensy_loader_cli using the completed download. Returns a flash_task_id."""
		flash_id = str(uuid.uuid4())
		flash_task: dict = {
			"status": "running",
			"stage": "rebooting",  # rebooting | flashing | done | error
			"output": "",
			"error": None,
		}
		with self._lock:
			self._flashes[flash_id] = flash_task
			dl_task = self._downloads.get(download_task_id)

		if not dl_task or dl_task.get("status") != "done" or not dl_task.get("hex_path"):
			flash_task.update({"status": "error", "error": "Download not complete."})
			return flash_id

		hex_path = dl_task["hex_path"]
		threading.Thread(
			target=self._run_flash,
			args=(flash_id, hex_path, variant),
			daemon=True,
		).start()
		return flash_id

	def get_flash_status(self, flash_id: str) -> Optional[dict]:
		with self._lock:
			task = self._flashes.get(flash_id)
		return dict(task) if task is not None else None

	def _run_flash(self, flash_id: str, hex_path: str, variant: str) -> None:
		task = self._flashes[flash_id]
		reboot_bin = _tool("teensy_reboot")
		loader_bin = _tool("teensy_loader_cli")

		for b in (reboot_bin, loader_bin):
			if b.exists() and platform.system() != "Windows":
				b.chmod(b.stat().st_mode | 0o111)

		if not loader_bin.exists():
			task.update({
				"status": "error",
				"error": f"teensy_loader_cli not found. Run: brew install teensy_loader_cli",
			})
			return

		# Step 1: trigger bootloader via teensy_reboot (stage stays "rebooting")
		task["output"] = "Rebooting device into bootloader…"
		if reboot_bin.exists():
			try:
				subprocess.run([str(reboot_bin)], timeout=10, capture_output=True)
			except Exception:
				pass
		else:
			task["output"] = "Press the PROGRAM button on your device to begin flashing."

		# Step 2: flash — -w waits for the bootloader to appear
		task["stage"] = "flashing"
		try:
			proc = subprocess.Popen(
				[str(loader_bin), "--mcu=TEENSY41", "-w", hex_path],
				stdout=subprocess.PIPE,
				stderr=subprocess.STDOUT,
				text=True,
			)
			lines: list[str] = []
			assert proc.stdout is not None
			for line in proc.stdout:
				line = line.rstrip()
				if line:
					lines.append(line)
					task["output"] = "\n".join(lines[-8:])
			proc.wait(timeout=120)

			if proc.returncode == 0:
				task.update({"status": "done", "stage": "done"})
				self._save_installed_version(variant)
			else:
				task.update({
					"status": "error",
					"error": f"teensy_loader_cli exited with code {proc.returncode}.\n{task['output']}",
				})
		except subprocess.TimeoutExpired:
			task.update({"status": "error", "error": "Flash timed out. Is the device plugged in?"})
		except Exception as e:
			task.update({"status": "error", "error": str(e)})

	# ── Persistence ────────────────────────────────────────────────────────────

	def _prefs_path(self) -> Path:
		return _DATA_DIR / "firmware_prefs.json"

	def _manifest_cache_path(self) -> Path:
		return _CACHE_DIR / "firmware_manifest_cache.json"

	def _load_prefs(self) -> dict:
		try:
			return json.loads(self._prefs_path().read_text())
		except Exception:
			return {}

	def _save_installed_version(self, variant: str) -> None:
		with self._lock:
			version = self._latest_version
		prefs = self._load_prefs()
		prefs["installed_version"] = version
		prefs["installed_variant"] = variant
		try:
			self._prefs_path().write_text(json.dumps(prefs, indent=2))
		except Exception:
			pass

	def _load_manifest_cache(self) -> Optional[dict]:
		try:
			return json.loads(self._manifest_cache_path().read_text())
		except Exception:
			return None

	def _save_manifest_cache(self, manifest: dict) -> None:
		try:
			self._manifest_cache_path().write_text(json.dumps(manifest, indent=2))
		except Exception:
			pass


def _fetch_manifest() -> dict:
	ctx = ssl.create_default_context(cafile=certifi.where())
	req = urllib.request.Request(FIRMWARE_MANIFEST_URL, headers={"User-Agent": "CassLogger"})
	with urllib.request.urlopen(req, timeout=10, context=ctx) as resp:
		return json.loads(resp.read())
