from typing import Any


def to_js_obj(data: Any) -> Any:
    """Convert dictionaries and lists for Worker binding calls."""
    from js import Object
    from pyodide.ffi import to_js

    return to_js(data, dict_converter=Object.fromEntries)


def to_js_bytes(data: bytes) -> Any:
    from pyodide.ffi import to_js

    return to_js(data)


def to_python(value):
    return value.to_py() if hasattr(value, "to_py") else value
