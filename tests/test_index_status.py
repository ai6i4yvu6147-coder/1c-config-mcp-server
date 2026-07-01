"""Tests for shared/index_status.py."""

import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from shared.index_status import (
    build_index_status,
    format_last_updated_local,
    read_db_last_updated_at,
)
from shared.indexer_version import INDEXER_VERSION


def test_read_db_last_updated_at_missing():
    assert read_db_last_updated_at("/nonexistent/path.db") is None


def test_read_db_last_updated_at_from_mtime(tmp_path):
    db_path = tmp_path / "main.db"
    db_path.write_bytes(b"sqlite")
    fixed_ts = datetime(2026, 6, 15, 12, 30, 45, tzinfo=timezone.utc).timestamp()
    os.utime(db_path, (fixed_ts, fixed_ts))

    assert read_db_last_updated_at(db_path) == "2026-06-15T12:30:45Z"


def test_build_index_status_includes_last_updated_at(tmp_path):
    db_path = tmp_path / "main.db"
    conn = sqlite3.connect(db_path)
    conn.execute(f"PRAGMA user_version = {INDEXER_VERSION}")
    conn.commit()
    conn.close()
    fixed_ts = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc).timestamp()
    os.utime(db_path, (fixed_ts, fixed_ts))

    status = build_index_status(db_path)
    assert status["lastUpdatedAt"] == "2026-01-01T00:00:00Z"
    assert status["expectedVersion"] == INDEXER_VERSION


def test_format_last_updated_local_empty():
    assert format_last_updated_local(None) == ""
    assert format_last_updated_local("") == ""


def test_format_last_updated_local_converts_tz():
    iso = "2026-06-15T12:30:45Z"
    formatted = format_last_updated_local(iso)
    assert len(formatted) == 16  # DD.MM.YYYY HH:MM
    assert formatted[2] == "." and formatted[5] == "."
