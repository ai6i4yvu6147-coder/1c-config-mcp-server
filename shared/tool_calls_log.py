"""Per-server SQLite journal of MCP tool invocations.

Shared, uniform implementation across the 1C MCP cluster (Admin Hub protocol
v1.0.7 addendum §3, v1.0.8 addendum §1-2). One row per tool call, written at the
central ``call_tool`` dispatch after the handler completes. Failure-isolated: a
journal write MUST NOT break, materially slow, or change the tool result.

Cluster-wide columns are the correlation quartet: ``task_id`` / ``session_id``
plus the self-reported caller identity ``agent`` / ``model``. Server-specific
scope (``database_id``, project/extension filters, help version, …) is NOT a
column — it is captured inside the masked, length-capped ``args_summary``.

Each field is a per-process sticky value (see ``ToolCallLogger._resolve``): the
last non-empty value seen carries forward to calls that omit it. The
``set_context`` tool (exposed by the server, not this module) deterministically
seeds all four via ``ToolCallLogger.set_context`` instead of relying on whichever
ordinary call happens to carry them first.
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

# Reserved cluster-wide correlation params (protocol v1.0.7 §2 trio + v1.0.8 §1
# session_id). Optional everywhere; their absence preserves prior behavior.
CORRELATION_KEYS = ("task_id", "session_id", "agent", "model")

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
    "session_id": {
        "type": "string",
        "description": (
            "Optional per-chat iteration id minted by the Hub's work_on_task "
            "(protocol v1.0.8 §1). Journaling only — does not affect tool behavior, "
            "results, or errors."
        ),
    },
}

_SCHEMA = """
CREATE TABLE IF NOT EXISTS tool_calls (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  ts_utc       TEXT    NOT NULL,
  tool         TEXT    NOT NULL,
  task_id      TEXT,
  session_id   TEXT,
  agent        TEXT,
  model        TEXT,
  elapsed_ms   INTEGER,
  result_bytes INTEGER,
  success      INTEGER,
  error_code   TEXT,
  args_summary TEXT,
  pid          INTEGER
);
CREATE INDEX IF NOT EXISTS idx_tool_calls_task    ON tool_calls(task_id);
CREATE INDEX IF NOT EXISTS idx_tool_calls_session ON tool_calls(session_id);
CREATE INDEX IF NOT EXISTS idx_tool_calls_ts      ON tool_calls(ts_utc);
"""

# Upgrades a v1.0.7-era store in place (protocol v1.0.8 §2). Harmless no-op on
# a fresh store (column already exists via _SCHEMA) or a store that already
# has the column — sqlite3 raises "duplicate column name" either way.
_MIGRATE_SESSION_ID = "ALTER TABLE tool_calls ADD COLUMN session_id TEXT"

_INSERT = (
    "INSERT INTO tool_calls "
    "(ts_utc, tool, task_id, session_id, agent, model, elapsed_ms, result_bytes, "
    "success, error_code, args_summary, pid) "
    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
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
        self._sticky: dict[str, str | None] = {key: None for key in CORRELATION_KEYS}

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
        resolved = self._resolve(correlation)
        record = (
            started_at,
            tool,
            resolved["task_id"],
            resolved["session_id"],
            resolved["agent"],
            resolved["model"],
            elapsed_ms,
            result_bytes,
            1 if success else 0,
            error_code,
            build_args_summary(args),
            os.getpid(),
        )
        self._write(record)

    def set_context(
        self,
        *,
        task_id: str | None = None,
        session_id: str | None = None,
        agent: str | None = None,
        model: str | None = None,
    ) -> dict[str, str | None]:
        """Explicitly (re)seed the sticky quartet for this process (``set_context`` tool).

        Unlike the passive per-call carry-forward in :meth:`_resolve` — which only
        ever updates when *some* call happens to carry a value — this is the
        deterministic entry point: the agent calls it once per chat and every
        field it supplies takes effect immediately, before any other tool runs.
        Fields omitted here are left untouched (not cleared). Returns the full
        resulting sticky state for the tool's response payload.
        """
        with _LOCK:
            for key, value in (
                ("task_id", task_id),
                ("session_id", session_id),
                ("agent", agent),
                ("model", model),
            ):
                if value:
                    self._sticky[key] = value
            return dict(self._sticky)

    def _resolve(self, correlation: dict[str, str | None]) -> dict[str, str | None]:
        """Sticky per-process fallback for the correlation quartet.

        Each of ``task_id``/``session_id``/``agent``/``model`` is self-reported by
        the calling agent (protocol v1.0.7 §2 / v1.0.8 §1); over a long tool-heavy
        session it's easy to drop one on some calls. The last non-empty value seen
        by this logger (one instance per server process/session) carries forward
        to calls that omit it. An explicit value always overrides and re-seeds it.
        ``set_context`` is the deterministic way to seed all four up front instead
        of relying on whichever call happens to carry them first.
        """
        with _LOCK:
            resolved: dict[str, str | None] = {}
            for key in CORRELATION_KEYS:
                value = correlation.get(key)
                if value:
                    self._sticky[key] = value
                resolved[key] = value if value else self._sticky[key]
            return resolved

    def _write(self, record: tuple[Any, ...]) -> None:
        try:
            with _LOCK:
                self._db_path.parent.mkdir(parents=True, exist_ok=True)
                conn = sqlite3.connect(str(self._db_path), timeout=2.0)
                try:
                    conn.execute("PRAGMA journal_mode=WAL")
                    conn.execute("PRAGMA busy_timeout=2000")
                    # Migrate an existing v1.0.7-era table (no session_id column) BEFORE
                    # the schema script, which otherwise fails on
                    # `CREATE INDEX ... (session_id)` against a table missing it.
                    # Harmless no-op on a fresh store (no table yet) or an
                    # already-migrated one (column already exists) — both raise
                    # OperationalError, swallowed the same way.
                    try:
                        conn.execute(_MIGRATE_SESSION_ID)
                    except sqlite3.OperationalError:
                        pass
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
    "session_id",
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
        "sessionId": row["session_id"],
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
    session_id: str | None = None,
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
    if session_id:
        clauses.append("session_id = ?")
        params.append(session_id)
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
