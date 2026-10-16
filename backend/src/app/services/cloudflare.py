from typing import Any

from pyodide.ffi import to_js
from js import Object


def to_js_obj(data: dict) -> Any:
    """Convert a dict to a plain JavaScript object (needed for binding calls)."""
    return to_js(data, dict_converter=Object.fromEntries)


def to_js_bytes(data: bytes) -> Any:
    return to_js(data)
