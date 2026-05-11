"""PyWebView entry point for the Cass Logger GUI."""

import os
import sys
from pathlib import Path

# Add repo root so both `src/` and `gui/` are importable as packages.
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
	sys.path.insert(0, str(ROOT))

# When frozen by PyInstaller, data files are unpacked into sys._MEIPASS.
BUNDLE_DIR = Path(getattr(sys, "_MEIPASS", ROOT))

# cass_commands.py in the parent package uses `from src.firmware_structs import …`
# (a legacy import path). Shim `src` → `cass_logger_dev` so it resolves correctly
# both in dev and in the PyInstaller bundle.
import cass_logger_dev
import cass_logger_dev.firmware_structs
sys.modules.setdefault("src", cass_logger_dev)
sys.modules.setdefault("src.firmware_structs", cass_logger_dev.firmware_structs)

import webview

from gui.api.main_api import MainApi
from gui.services.cass_service import CassService
from gui.services.update_service import UpdateService


def main() -> None:
	service = CassService()
	UpdateService().start_check()
	api = MainApi(service)

	dev_mode = os.environ.get("DEV", "").lower() in ("1", "true", "yes")

	if dev_mode:
		# Vite dev server — hot reload available
		url = "http://localhost:5173"
	else:
		dist = BUNDLE_DIR / "gui" / "frontend" / "dist" / "index.html"
		url = dist.as_uri()

	webview.create_window(
		"Cass Logger",
		url,
		js_api=api,
		width=1200,
		height=800,
		min_size=(900, 600),
	)
	webview.start(debug=dev_mode)


if __name__ == "__main__":
	main()
