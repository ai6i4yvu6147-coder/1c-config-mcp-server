from __future__ import annotations

import sqlite3
from pathlib import Path

from shared.tool_calls_log import (
    ToolCallLogger,
    build_args_summary,
    extract_correlation,
    inject_correlation_properties,
    read_tool_calls,
    tool_calls_db_path,
)


class _FakeTool:
    def __init__(self, input_schema: dict) -> None:
        self.inputSchema = input_schema


def _read_rows(db_path: Path) -> list[sqlite3.Row]:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        return list(conn.execute("SELECT * FROM tool_calls ORDER BY id"))
    finally:
        conn.close()


def test_tool_calls_db_path_under_logs_dir(tmp_path: Path) -> None:
    assert tool_calls_db_path(tmp_path / "logs") == tmp_path / "logs" / "tool-calls.db"


def test_extract_correlation_reads_quartet_from_input() -> None:
    corr = extract_correlation(
        {
            "task_id": 1024,
            "session_id": "01J8ULID",
            "agent": "cursor",
            "model": "claude-opus-4-8",
            "project_filter": "ТГ",
        }
    )
    assert corr == {
        "task_id": "1024",
        "session_id": "01J8ULID",
        "agent": "cursor",
        "model": "claude-opus-4-8",
    }


def test_extract_correlation_absent_is_none() -> None:
    assert extract_correlation({"project_filter": "ТГ"}) == {
        "task_id": None,
        "session_id": None,
        "agent": None,
        "model": None,
    }


def test_build_args_summary_folds_scope_and_drops_quartet() -> None:
    summary = build_args_summary(
        {
            "task_id": "1024",
            "session_id": "01J8ULID",
            "agent": "x",
            "model": "y",
            "project_filter": "ТГ",
            "query": "Провести",
        }
    )
    assert summary is not None
    assert '"project_filter":"ТГ"' in summary
    assert '"query":"Провести"' in summary
    assert "task_id" not in summary


def test_build_args_summary_redacts_password() -> None:
    summary = build_args_summary({"password": "hunter2"})
    assert summary == '{"password":"***"}'


def test_build_args_summary_caps_length() -> None:
    summary = build_args_summary({"query": "x" * 5000}, max_chars=100)
    assert summary is not None
    assert len(summary) == 100
    assert summary.endswith("…")


def test_build_args_summary_empty_is_none() -> None:
    assert build_args_summary({"task_id": "1"}) is None


def test_inject_correlation_properties_adds_quartet() -> None:
    tool = _FakeTool(
        {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}
    )
    inject_correlation_properties([tool])
    props = tool.inputSchema["properties"]
    assert set(props) == {"query", "task_id", "session_id", "agent", "model"}
    assert tool.inputSchema["required"] == ["query"]


def test_logger_writes_success_row(tmp_path: Path) -> None:
    db_path = tmp_path / "logs" / "tool-calls.db"
    logger = ToolCallLogger(db_path)
    logger.log(
        tool="search_code",
        started_at="2026-07-16T07:00:00Z",
        started_mono=0.0,
        args={"task_id": "t1", "agent": "cursor", "model": "opus", "project_filter": "ТГ"},
        success=True,
        result_bytes=512,
    )

    row = _read_rows(db_path)[0]
    assert row["tool"] == "search_code"
    assert row["task_id"] == "t1"
    assert row["agent"] == "cursor"
    assert row["model"] == "opus"
    assert row["success"] == 1
    assert row["error_code"] is None
    assert row["result_bytes"] == 512
    assert '"project_filter":"ТГ"' in row["args_summary"]
    assert row["pid"] is not None


def test_logger_writes_error_row(tmp_path: Path) -> None:
    db_path = tmp_path / "logs" / "tool-calls.db"
    logger = ToolCallLogger(db_path)
    logger.log(
        tool="get_module_code",
        started_at="2026-07-16T07:01:00Z",
        started_mono=0.0,
        args={"project_filter": "ТГ"},
        success=False,
        error_code="ValueError",
    )

    row = _read_rows(db_path)[0]
    assert row["success"] == 0
    assert row["error_code"] == "ValueError"
    assert row["task_id"] is None


def test_logger_task_id_sticky_fallback(tmp_path: Path) -> None:
    # A long tool-heavy session can drop task_id on some calls; the logger
    # should carry forward the last non-empty value it saw in this process
    # instead of leaving the row uncorrelated.
    db_path = tmp_path / "logs" / "tool-calls.db"
    logger = ToolCallLogger(db_path)
    logger.log(
        tool="search_code",
        started_at="2026-07-16T07:00:00Z",
        started_mono=0.0,
        args={"task_id": "42", "project_filter": "ТГ"},
        success=True,
    )
    logger.log(
        tool="get_module_code",
        started_at="2026-07-16T07:00:01Z",
        started_mono=0.0,
        args={"project_filter": "ТГ"},  # task_id omitted
        success=True,
    )
    logger.log(
        tool="search_code",
        started_at="2026-07-16T07:00:02Z",
        started_mono=0.0,
        args={"task_id": "43", "project_filter": "ТГ"},  # explicit switch overrides sticky
        success=True,
    )
    logger.log(
        tool="get_module_code",
        started_at="2026-07-16T07:00:03Z",
        started_mono=0.0,
        args={"project_filter": "ТГ"},  # task_id omitted again, follows the new sticky value
        success=True,
    )

    rows = _read_rows(db_path)
    assert [r["task_id"] for r in rows] == ["42", "42", "43", "43"]


def test_logger_session_id_sticky_fallback(tmp_path: Path) -> None:
    db_path = tmp_path / "logs" / "tool-calls.db"
    logger = ToolCallLogger(db_path)
    logger.log(
        tool="search_code",
        started_at="2026-07-16T07:00:00Z",
        started_mono=0.0,
        args={"session_id": "01J8AAA", "project_filter": "ТГ"},
        success=True,
    )
    logger.log(
        tool="get_module_code",
        started_at="2026-07-16T07:00:01Z",
        started_mono=0.0,
        args={"project_filter": "ТГ"},  # session_id omitted
        success=True,
    )

    rows = _read_rows(db_path)
    assert [r["session_id"] for r in rows] == ["01J8AAA", "01J8AAA"]


def test_logger_set_context_seeds_quartet_up_front(tmp_path: Path) -> None:
    db_path = tmp_path / "logs" / "tool-calls.db"
    logger = ToolCallLogger(db_path)
    context = logger.set_context(
        task_id="900", session_id="01J8SEED", agent="cursor", model="claude-opus-4-8"
    )
    assert context == {
        "task_id": "900",
        "session_id": "01J8SEED",
        "agent": "cursor",
        "model": "claude-opus-4-8",
    }

    logger.log(
        tool="search_code",
        started_at="2026-07-16T07:00:00Z",
        started_mono=0.0,
        args={"project_filter": "ТГ"},
        success=True,
    )

    row = _read_rows(db_path)[0]
    assert row["task_id"] == "900"
    assert row["session_id"] == "01J8SEED"
    assert row["agent"] == "cursor"
    assert row["model"] == "claude-opus-4-8"


def test_logger_set_context_omits_untouched_fields(tmp_path: Path) -> None:
    db_path = tmp_path / "logs" / "tool-calls.db"
    logger = ToolCallLogger(db_path)
    logger.set_context(task_id="900")
    context = logger.set_context(agent="cursor")  # session_id/model untouched
    assert context == {
        "task_id": "900",
        "session_id": None,
        "agent": "cursor",
        "model": None,
    }


def test_migrates_pre_v1_0_8_store_missing_session_id_column(tmp_path: Path) -> None:
    # A v1.0.7-era store predates the session_id column; the logger must add
    # it in place instead of erroring on the first post-upgrade write.
    db_path = tmp_path / "logs" / "tool-calls.db"
    db_path.parent.mkdir(parents=True)
    conn = sqlite3.connect(str(db_path))
    try:
        conn.executescript(
            """
            CREATE TABLE tool_calls (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              ts_utc TEXT NOT NULL,
              tool TEXT NOT NULL,
              task_id TEXT,
              agent TEXT,
              model TEXT,
              elapsed_ms INTEGER,
              result_bytes INTEGER,
              success INTEGER,
              error_code TEXT,
              args_summary TEXT,
              pid INTEGER
            );
            """
        )
        conn.commit()
    finally:
        conn.close()

    logger = ToolCallLogger(db_path)
    logger.log(
        tool="search_code",
        started_at="2026-07-16T07:00:00Z",
        started_mono=0.0,
        args={"session_id": "01J8UPG", "project_filter": "ТГ"},
        success=True,
    )

    row = _read_rows(db_path)[0]
    assert row["session_id"] == "01J8UPG"


def test_logger_task_id_none_when_never_seen(tmp_path: Path) -> None:
    db_path = tmp_path / "logs" / "tool-calls.db"
    logger = ToolCallLogger(db_path)
    logger.log(
        tool="search_code",
        started_at="2026-07-16T07:00:00Z",
        started_mono=0.0,
        args={"project_filter": "ТГ"},
        success=True,
    )
    assert _read_rows(db_path)[0]["task_id"] is None


def test_logger_swallows_write_errors(tmp_path: Path) -> None:
    db_path = tmp_path / "logs" / "tool-calls.db"
    db_path.parent.mkdir(parents=True)
    db_path.mkdir()  # occupy the db path with a directory so sqlite open fails
    logger = ToolCallLogger(db_path)
    logger.log(
        tool="search_code",
        started_at="2026-07-16T07:00:00Z",
        started_mono=0.0,
        args={"project_filter": "ТГ"},
        success=True,
    )  # must not raise


def _seed(db_path: Path) -> ToolCallLogger:
    logger = ToolCallLogger(db_path)
    logger.log(
        tool="search_code",
        started_at="2026-07-16T07:00:00Z",
        started_mono=0.0,
        args={"task_id": "T-1", "project_filter": "ТГ"},
        success=True,
        result_bytes=100,
    )
    logger.log(
        tool="get_module_code",
        started_at="2026-07-16T07:05:00Z",
        started_mono=0.0,
        args={"task_id": "T-2"},
        success=False,
        error_code="ValueError",
    )
    logger.log(
        tool="search_code",
        started_at="2026-07-16T07:10:00Z",
        started_mono=0.0,
        args={"task_id": "T-1"},
        success=True,
    )
    return logger


def test_read_missing_db_returns_empty(tmp_path: Path) -> None:
    assert read_tool_calls(tmp_path / "logs" / "tool-calls.db") == []


def test_read_returns_newest_first_camelcase(tmp_path: Path) -> None:
    db_path = tmp_path / "logs" / "tool-calls.db"
    _seed(db_path)
    rows = read_tool_calls(db_path)
    assert [r["tool"] for r in rows] == ["search_code", "get_module_code", "search_code"]
    top = rows[0]
    assert top["tsUtc"] == "2026-07-16T07:10:00Z"
    assert top["taskId"] == "T-1"
    assert top["success"] is True
    assert set(top) == {
        "id", "tsUtc", "tool", "taskId", "sessionId", "agent", "model",
        "elapsedMs", "resultBytes", "success", "errorCode", "argsSummary", "pid",
    }


def test_read_filter_by_task_id(tmp_path: Path) -> None:
    db_path = tmp_path / "logs" / "tool-calls.db"
    _seed(db_path)
    rows = read_tool_calls(db_path, task_id="T-1")
    assert len(rows) == 2
    assert {r["taskId"] for r in rows} == {"T-1"}


def test_read_filter_by_session_id(tmp_path: Path) -> None:
    db_path = tmp_path / "logs" / "tool-calls.db"
    logger = ToolCallLogger(db_path)
    logger.log(
        tool="search_code", started_at="2026-07-16T07:00:00Z", started_mono=0.0,
        args={"session_id": "S-1"}, success=True,
    )
    logger.log(
        tool="search_code", started_at="2026-07-16T07:01:00Z", started_mono=0.0,
        args={"session_id": "S-2"}, success=True,
    )
    rows = read_tool_calls(db_path, session_id="S-1")
    assert len(rows) == 1
    assert rows[0]["sessionId"] == "S-1"


def test_read_filter_by_tool_and_only_errors(tmp_path: Path) -> None:
    db_path = tmp_path / "logs" / "tool-calls.db"
    _seed(db_path)
    assert len(read_tool_calls(db_path, tool="search_code")) == 2
    errors = read_tool_calls(db_path, only_errors=True)
    assert len(errors) == 1
    assert errors[0]["success"] is False
    assert errors[0]["errorCode"] == "ValueError"


def test_read_time_window_and_limit_offset(tmp_path: Path) -> None:
    db_path = tmp_path / "logs" / "tool-calls.db"
    _seed(db_path)
    windowed = read_tool_calls(db_path, since="2026-07-16T07:05:00Z", until="2026-07-16T07:05:00Z")
    assert [r["tool"] for r in windowed] == ["get_module_code"]
    assert len(read_tool_calls(db_path, limit=1)) == 1
    assert read_tool_calls(db_path, limit=1, offset=1)[0]["tool"] == "get_module_code"
