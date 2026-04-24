"""Helpers for consistent API return shapes."""

from typing import Any


def ok(data: Any = None) -> dict:
	return {"ok": True, "data": data, "error": None}


def err(message: str) -> dict:
	return {"ok": False, "data": None, "error": message}
