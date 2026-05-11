"""Singleton wrapper around CassCommands that manages connection state."""

import threading
import time
from typing import Optional

import serial

from cass_logger_dev.cass_commands import CassCommands


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
					inst._fw_ver: Optional[str] = None
					inst._device_id: Optional[str] = None
					inst._op_lock = threading.Lock()
					cls._instance = inst
		return cls._instance

	# ── Connection ──────────────────────────────────────────────────────────────

	def connect(self) -> tuple[bool, str]:
		"""Auto-detect device and establish serial connection.

		Retries once with a short pause — firmware sometimes isn't ready to respond
		immediately after USB enumeration.
		"""
		with self._op_lock:
			last_err = ""
			for attempt in range(2):
				try:
					cass = CassCommands()
					_ = cass.ser_data	# triggers _establish_serial
					self._cass = cass
					self._connected = True
					self._cache_device_info()
					return True, "Connected"
				except Exception as e:
					last_err = _friendly(e)
					if attempt == 0:
						time.sleep(0.5)
			self._cass = None
			self._connected = False
			return False, last_err

	def connect_manual(self, data_port: str, command_port: str) -> tuple[bool, str]:
		"""Connect using explicitly specified serial ports."""
		with self._op_lock:
			last_err = ""
			for attempt in range(2):
				try:
					cass = CassCommands()
					ok = cass.set_manual_serial_ports(data_port, command_port)
					if not ok:
						return False, f"Could not open ports {data_port} / {command_port}"
					_ = cass.ser_data
					self._cass = cass
					self._connected = True
					self._cache_device_info()
					return True, f"Connected via {data_port} / {command_port}"
				except Exception as e:
					last_err = _friendly(e)
					if attempt == 0:
						time.sleep(0.5)
			self._cass = None
			self._connected = False
			return False, last_err

	def disconnect(self) -> None:
		with self._op_lock:
			if self._cass is not None:
				try:
					self._cass._close_serial()
				except Exception:
					pass
				self._cass = None
			self._connected = False
			self._fw_ver = None
			self._device_id = None

	def check_alive(self) -> bool:
		"""Probe the serial port to confirm the USB device is still present.

		CassCommands closes the port after each command, so the port is normally
		closed between operations. When closed, we do a quick open+close to verify
		the device node still exists — open() raises OSError if the device is gone.
		When the port is already open (mid-command), in_waiting is enough.
		"""
		if not self._connected or self._cass is None:
			return False
		try:
			ser = self._cass._ser_data
			if ser is None:
				self.disconnect()
				return False
			if ser.is_open:
				_ = ser.in_waiting
			else:
				ser.open()
				ser.close()
			return True
		except (OSError, serial.SerialException):
			self.disconnect()
			return False
		except Exception:
			self.disconnect()
			return False

	@property
	def is_connected(self) -> bool:
		return self._connected

	@property
	def fw_ver(self) -> Optional[str]:
		return self._fw_ver

	@property
	def device_id(self) -> Optional[str]:
		return self._device_id

	@property
	def cass(self) -> CassCommands:
		if not self._connected or self._cass is None:
			raise RuntimeError(
				"Device not connected — plug in the logger and click Connect."
			)
		return self._cass

	# ── Private ─────────────────────────────────────────────────────────────────

	def _cache_device_info(self) -> None:
		"""Read and cache fw_ver and device_id immediately after connecting."""
		try:
			self._fw_ver = self._cass.get_fw_ver()
			self._device_id = self._cass.get_device_ID()
		except Exception:
			self._fw_ver = None
			self._device_id = None


def _friendly(e: Exception) -> str:
	msg = str(e)
	if "No logger detected" in msg:
		return "No device found — make sure the logger is plugged in and powered on."
	if "Timeout" in type(e).__name__ or "timeout" in msg.lower():
		return "Device not responding — try unplugging and replugging the logger."
	if "Permission" in msg:
		return "Permission denied on serial port — close any other apps using the port."
	return msg
