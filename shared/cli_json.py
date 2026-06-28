"""UTF-8 JSON I/O for Admin Hub CLI (protocol v1.0.3)."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

_UTF8_BOM = b"\xef\xbb\xbf"


def write_json_stdout(payload: object, *, indent: int | None = 2) -> None:
    """Write machine-readable JSON to stdout as UTF-8 without BOM."""
    data = json.dumps(payload, ensure_ascii=False, indent=indent)
    sys.stdout.buffer.write(data.encode("utf-8"))
    sys.stdout.buffer.write(b"\n")
    sys.stdout.buffer.flush()


def read_json_file(path: Path) -> Any:
    """Read JSON from file; UTF-8 only, BOM rejected."""
    raw = path.read_bytes()
    if raw.startswith(_UTF8_BOM):
        raise ValueError("UTF-8 BOM is not allowed in JSON input")
    text = raw.decode("utf-8")
    return json.loads(text)
