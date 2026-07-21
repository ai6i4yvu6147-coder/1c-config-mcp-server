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
        self._last_task_id: str | None = None

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
        task_id = self._resolve_task_id(correlation["task_id"])
        record = (
            started_at,
            tool,
            task_id,
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

    def _resolve_task_id(self, task_id: str | None) -> str | None:
        """Sticky per-process fallback for the correlation ``task_id``.

        ``task_id`` is self-reported by the calling agent on every call (protocol
        v1.0.7 §2); over a long tool-heavy session it's easy to drop it on some
        calls. The last non-empty value seen by this logger (one instance per
        server process/session) carries forward to calls that omit it. An
        explicit ``task_id`` always overrides and re-seeds it.
        """
        with _LOCK:
            if task_id:
                self._last_task_id = task_id
                return task_id
            return self._last_task_id

    def _write(self, record: tuple[Any, ...]) -> None:
        try:
            with _LOCK:
                self._db_path.parent.mkdir(parents=True, exist_ok=True)
                conn = sqlite3.connect(str(self._db_path), timeout=2.0)
                try:
                    conn.execute("PRAGMA journal_mode=WAL")
                    conn.execute("PRAGMA busy_timeout=2000")
                    conn.executescript(_SCHEMA)
                    conn.execute(_INSERT, record)
                    conn.commit()
                finally:
                    conn.close()
        except (OSError, sqlite3.Error):
            return


# Column order returned by the reader; also the ``rows[]`` object keys (camelCase)
# consumed by the Hub «журнал по задаче» viewer (protocol v1.0.7 §3.4).
_READ_COLUMNS = (
    "id",
    "ts_utc",
    "tool",
    "task_id",
    "agent",
    "model",
    "elapsed_ms",
    "result_bytes",
    "success",
    "error_code",
    "args_summary",
    "pid",
)

# Newest-first default page size and hard cap for a single read.
READ_DEFAULT_LIMIT = 200
READ_MAX_LIMIT = 5000


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "tsUtc": row["ts_utc"],
        "tool": row["tool"],
        "taskId": row["task_id"],
        "agent": row["agent"],
        "model": row["model"],
        "elapsedMs": row["elapsed_ms"],
        "resultBytes": row["result_bytes"],
        "success": None if row["success"] is None else bool(row["success"]),
        "errorCode": row["error_code"],
        "argsSummary": row["args_summary"],
        "pid": row["pid"],
    }


def read_tool_calls(
    db_path: PathLike,
    *,
    task_id: str | None = None,
    tool: str | None = None,
    since: str | None = None,
    until: str | None = None,
    only_errors: bool = False,
    limit: int = READ_DEFAULT_LIMIT,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """Read journal rows newest-first as camelCase dicts. Failure-isolated.

    Absent store (Sub never called), a missing ``tool_calls`` table, or any
    sqlite/OS error yields ``[]`` — never raises. ``since``/``until`` compare
    lexicographically against the ISO-8601 Z ``ts_utc`` (correct for that form).
    """
    path = Path(db_path)
    if not path.is_file():
        return []

    clauses: list[str] = []
    params: list[Any] = []
    if task_id:
        clauses.append("task_id = ?")
        params.append(task_id)
    if tool:
        clauses.append("tool = ?")
        params.append(tool)
    if since:
        clauses.append("ts_utc >= ?")
        params.append(since)
    if until:
        clauses.append("ts_utc <= ?")
        params.append(until)
    if only_errors:
        clauses.append("success = 0")

    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    capped_limit = max(1, min(int(limit), READ_MAX_LIMIT))
    safe_offset = max(0, int(offset))
    sql = (
        f"SELECT {', '.join(_READ_COLUMNS)} FROM tool_calls"
        f"{where} ORDER BY id DESC LIMIT ? OFFSET ?"
    )
    params.extend([capped_limit, safe_offset])

    try:
        conn = sqlite3.connect(str(path), timeout=2.0)
        try:
            conn.execute("PRAGMA busy_timeout=2000")
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(sql, params)
            return [_row_to_dict(r) for r in cursor.fetchall()]
        finally:
            conn.close()
    except (OSError, sqlite3.Error):
        return []
