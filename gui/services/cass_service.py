"""Singleton wrapper around CassCommands that manages connection state."""

import threading
from typing import Optional

from src.cass_commands import CassCommands


class CassService:
	"""Singleton holding a single CassCommands instance."""

	_instance: Optional["CassService"] = None
	_init_lock = threading.Lock()

	def __new__(cls) -> "CassService":
		if cls._instance is None:
			with cls._init_lock:
				if cls._instance is None:
					inst = super().__new__(cls)
					inst._cass: Optional[CassCommands] = None
					inst._connected = False
					inst._op_lock = threading.Lock()
					cls._instance = inst
		return cls._instance

	# ── Connection ──────────────────────────────────────────────────────────────

	def connect(self) -> tuple[bool, str]:
		"""Auto-detect device and establish serial connection."""
		with self._op_lock:
			try:
				cass = CassCommands()
				_ = cass.ser_data	# triggers _establish_serial
				self._cass = cass
				self._connected = True
				return True, "Connected"
			except Exception as e:
				self._cass = None
				self._connected = False
				return False, _friendly(e)

	def connect_manual(self, data_port: str, command_port: str) -> tuple[bool, str]:
		"""Connect using explicitly specified serial ports."""
		with self._op_lock:
			try:
				cass = CassCommands()
				ok = cass.set_manual_serial_ports(data_port, command_port)
				if not ok:
					return False, f"Could not open ports {data_port} / {command_port}"
				_ = cass.ser_data
				self._cass = cass
				self._connected = True
				return True, f"Connected via {data_port} / {command_port}"
			except Exception as e:
				self._cass = None
				self._connected = False
				return False, _friendly(e)

	def disconnect(self) -> None:
		with self._op_lock:
			if self._cass is not None:
				try:
					self._cass._close_serial()
				except Exception:
					pass
				self._cass = None
			self._connected = False

	@property
	def is_connected(self) -> bool:
		return self._connected

	@property
	def cass(self) -> CassCommands:
		if not self._connected or self._cass is None:
			raise RuntimeError(
				"Device not connected — plug in the logger and click Connect."
			)
		return self._cass


def _friendly(e: Exception) -> str:
	msg = str(e)
	if "No logger detected" in msg:
		return "No device found — make sure the logger is plugged in and powered on."
	if "Timeout" in type(e).__name__ or "timeout" in msg.lower():
		return "Device not responding — try unplugging and replugging the logger."
	if "Permission" in msg:
		return "Permission denied on serial port — close any other apps using the port."
	return msg
