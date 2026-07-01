"""SQLite index version and build-state helpers (shared, no server/tools dependency)."""

from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from shared.db_build_state import is_building, is_stale_building, read_building_info
from shared.indexer_version import INDEXER_VERSION

PathLike = str | Path


def read_db_user_version(db_path: PathLike) -> Optional[int]:
    """PRAGMA user_version; None if file missing."""
    p = Path(db_path)
    if not p.is_file():
        return None
    uri = p.resolve().as_uri() + "?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    try:
        row = conn.execute("PRAGMA user_version").fetchone()
        return int(row[0]) if row is not None else 0
    finally:
        conn.close()


def is_index_outdated(db_path: PathLike) -> bool:
    ver = read_db_user_version(db_path)
    if ver is None or ver == 0:
        return True
    return ver < INDEXER_VERSION


def read_db_last_updated_at(db_path: PathLike) -> Optional[str]:
    """mtime .db as ISO-8601 UTC (…Z); None if file missing."""
    p = Path(db_path)
    if not p.is_file():
        return None
    ts = os.path.getmtime(p)
    dt = datetime.fromtimestamp(ts, tz=timezone.utc)
    return dt.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def format_last_updated_local(iso_z: Optional[str]) -> str:
    """DD.MM.YYYY HH:MM in local TZ; empty string if None."""
    if not iso_z:
        return ""
    dt = datetime.fromisoformat(iso_z.replace("Z", "+00:00"))
    return dt.astimezone().strftime("%d.%m.%Y %H:%M")


def build_index_status(db_path: PathLike) -> Dict[str, Any]:
    user_version = read_db_user_version(db_path)
    building = is_building(db_path)
    return {
        "userVersion": user_version,
        "expectedVersion": INDEXER_VERSION,
        "isOutdated": is_index_outdated(db_path),
        "isBuilding": building,
        "lastUpdatedAt": read_db_last_updated_at(db_path),
    }


def compute_index_readiness(
    db_path: PathLike,
    *,
    source_path_exists: bool,
) -> str:
    """
    Hub-facing readiness label for a database index.

    Returns one of: missing, building, outdated, current.
    """
    p = Path(db_path)
    idx = build_index_status(p)

    if idx["isBuilding"] and not is_stale_building(p):
        return "building"

    ver = idx["userVersion"]
    db_missing = ver is None or ver == 0 or not p.is_file()

    if source_path_exists and db_missing:
        return "missing"

    if idx["isOutdated"]:
        return "outdated"

    return "current"


def collect_locks_for_db(db_path: PathLike, target_id: str) -> list:
    """Lock entries for status output (addendum §6.3 / §10.2)."""
    p = Path(db_path)
    if not is_building(p):
        return []

    marker = p.parent / (p.name + ".building")
    info = read_building_info(p) or {}
    stale = is_stale_building(p)
    return [
        {
            "type": "build-marker",
            "targetId": target_id,
            "path": str(marker.resolve()),
            "startedAt": info.get("started_at"),
            "pid": info.get("pid"),
            "stale": stale,
            "reason": "rebuild-index",
        }
    ]
