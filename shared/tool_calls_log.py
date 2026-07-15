"""Per-server SQLite journal of MCP tool invocations.

Shared, uniform implementation across the 1C MCP cluster (Admin Hub protocol
v1.0.7 addendum §3). One row per tool call, written at the central ``call_tool``
dispatch after the handler completes. Failure-isolated: a journal write MUST NOT
break, materially slow, or change the tool result.

Cluster-wide columns are the correlation token ``task_id`` plus the self-reported
caller identity ``agent`` / ``model``. Server-specific scope (``database_id``,
project/extension filters, help version, …) is NOT a column — it is captured
inside the masked, length-capped ``args_summary``.
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from shared.security import mask_secrets

PathLike = str | Path

_LOCK = threading.Lock()

# Reserved cluster-wide correlation params (protocol v1.0.7 §2). Optional
# everywhere; their absence preserves current behavior.
CORRELATION_KEYS = ("task_id", "agent", "model")

# Args whose values must never reach the journal, even masked.
_REDACT_KEYS = frozenset({"password"})
_REDACTED = "***"

# Recommended 2–4 KB cap on the serialized args summary (protocol v1.0.7 §3.3).
ARGS_SUMMARY_MAX_CHARS = 2048

# Shared input-schema fragment so every tool advertises the trio uniformly
# (protocol v1.0.7 §2). Optional — never added to a tool's ``required``.
CORRELATION_INPUT_PROPERTIES: dict[str, dict[str, str]] = {
    "task_id": {
        "type": "string",
        "description": (
            "Optional global task number for cross-tool correlation. "
            "Journaling only — does not affect tool behavior, results, or errors."
        ),
    },
    "agent": {
        "type": "string",
        "description": "Optional self-reported caller/agent label (journaling only).",
    },
    "model": {
        "type": "string",
        "description": (
            "Optional self-reported model id, e.g. claude-opus-4-8 (journaling only)."
        ),
    },
}

_SCHEMA = """
CREATE TABLE IF NOT EXISTS tool_calls (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  ts_utc       TEXT    NOT NULL,
  tool         TEXT    NOT NULL,
  task_id      TEXT,
  agent        TEXT,
  model        TEXT,
  elapsed_ms   INTEGER,
  result_bytes INTEGER,
  success      INTEGER,
  error_code   TEXT,
  args_summary TEXT,
  pid          INTEGER
);
CREATE INDEX IF NOT EXISTS idx_tool_calls_task ON tool_calls(task_id);
CREATE INDEX IF NOT EXISTS idx_tool_calls_ts   ON tool_calls(ts_utc);
"""

_INSERT = (
    "INSERT INTO tool_calls "
    "(ts_utc, tool, task_id, agent, model, elapsed_ms, result_bytes, "
    "success, error_code, args_summary, pid) "
    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
)


def utc_now_iso() -> str:
    """ISO-8601 Z timestamp at second resolution (call start)."""
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def tool_calls_db_path(logs_dir: PathLike) -> Path:
    """Default journal store: ``<logsDir>/tool-calls.db`` (protocol v1.0.7 §3.1)."""
    return Path(logs_dir) / "tool-calls.db"


def inject_correlation_properties(tools: Iterable[Any]) -> list[Any]:
    """Advertise the optional task_id/agent/model trio on every tool schema.

    Mutates each tool's ``inputSchema.properties`` in place (idempotent) and
    never touches ``required``. Returns the tools as a list for convenience.
    """
    result = list(tools)
    for tool in result:
        schema = getattr(tool, "inputSchema", None)
        if not isinstance(schema, dict):
            continue
        props = schema.setdefault("properties", {})
        for key, spec in CORRELATION_INPUT_PROPERTIES.items():
            props.setdefault(key, dict(spec))
    return result


def extract_correlation(args: dict[str, Any]) -> dict[str, str | None]:
    """Read the correlation trio from tool arguments as opaque strings."""
    out: dict[str, str | None] = {}
    for key in CORRELATION_KEYS:
        value = args.get(key)
        out[key] = str(value) if value not in (None, "") else None
    return out


def build_args_summary(
    args: dict[str, Any], *, max_chars: int = ARGS_SUMMARY_MAX_CHARS
) -> str | None:
    """Masked, length-capped JSON of tool args (minus the correlation trio).

    Server-specific scope (``database_id``, filters, version, …) lives here.
    Known secret-bearing keys are redacted, then the whole string passes
    ``mask_secrets``.
    """
    scoped = {
        key: (_REDACTED if key in _REDACT_KEYS else value)
        for key, value in args.items()
        if key not in CORRELATION_KEYS
    }
    if not scoped:
        return None
    try:
        raw = json.dumps(
            scoped, ensure_ascii=False, separators=(",", ":"), default=str
        )
    except (TypeError, ValueError):
        raw = str(scoped)
    masked = mask_secrets(raw)
    if len(masked) > max_chars:
        masked = masked[: max_chars - 1] + "…"
    return masked


class ToolCallLogger:
    """Writes one ``tool_calls`` row per invocation. Failure-isolated."""

    def __init__(self, db_path: PathLike) -> None:
        self._db_path = Path(db_path)

    def log(
        self,
        *,
        tool: str,
        started_at: str,
        started_mono: float,
        args: dict[str, Any] | None = None,
        success: bool,
        error_code: str | None = None,
        result_bytes: int | None = None,
    ) -> None:
        elapsed_ms = int((time.monotonic() - started_mono) * 1000)
        args = args or {}
        correlation = extract_correlation(args)
        record = (
            started_at,
            tool,
            correlation["task_id"],
            correlation["agent"],
            correlation["model"],
            elapsed_ms,
            result_bytes,
            1 if success else 0,
            error_code,
            build_args_summary(args),
            os.getpid(),
        )
        self._write(record)

    def _write(self, record: tuple[Any, ...]) -> None:
        try:
            with _LOCK:
                self._db_path.parent.mkdir(parents=True, exist_ok=True)
                conn = sqlite3.connect(str(self._db_path), timeout=1.0)
                try:
                    conn.executescript(_SCHEMA)
                    conn.execute(_INSERT, record)
                    conn.commit()
                finally:
                    conn.close()
        except (OSError, sqlite3.Error):
            return
