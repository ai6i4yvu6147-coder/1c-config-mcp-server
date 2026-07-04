"""Admin Hub Phase 3: headless index rebuild operations."""

from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from admin_tool.db_manager import DatabaseManager, format_build_error
from shared.db_build_state import (
    MARKER_SUFFIX,
    TMP_SUFFIX,
    is_building,
    is_stale_building,
    reconcile_building_markers,
)
from shared.index_status import build_index_status, read_db_user_version
from shared.indexer_version import INDEXER_VERSION
from shared.operations_log import log_operation_result
from shared.project_manager import ProjectManager
from shared.runtime_paths import get_paths
from shared.source_path import get_effective_config_xml, source_exists

PathLike = str | Path


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _empty_rebuild_result(operation: str, target_id: Optional[str] = None) -> Dict[str, Any]:
    return {
        "success": False,
        "operation": operation,
        "operationRunId": str(uuid.uuid4()),
        "targetId": target_id,
        "result": "failed",
        "completedAt": _utc_now_iso(),
        "durationMs": 0,
        "warnings": [],
        "errors": [],
    }


def _resolve_rebuild_target(
    data_dir: Path,
    db: dict,
) -> Tuple[Optional[Path], Optional[str], List[str]]:
    """Return (db_path, config_xml, errors)."""
    errors: List[str] = []
    db_path = data_dir / db["db_file"]

    if not source_exists(db):
        errors.append("sourcePath not found or Configuration.xml not resolvable")
        return db_path, None, errors

    config_xml = get_effective_config_xml(db)
    if not config_xml or not Path(config_xml).is_file():
        errors.append("Configuration.xml not found for database source")
        return db_path, None, errors

    return db_path, config_xml, errors


def run_rebuild_index(
    db_id: str,
    explicit_root: Optional[PathLike] = None,
) -> Dict[str, Any]:
    paths = get_paths(explicit_root)
    pm = ProjectManager(str(paths.config), str(paths.data_dir))

    operation_run_id = str(uuid.uuid4())
    result = _empty_rebuild_result("rebuild-index", db_id)
    result["operationRunId"] = operation_run_id

    found = pm.find_database_by_id(db_id)
    if found is None:
        result["errors"].append(f"infobaseId not found: {db_id}")
        log_operation_result(paths.operations_log, result)
        return result

    _project, db = found
    db_path, config_xml, resolve_errors = _resolve_rebuild_target(paths.data_dir, db)
    if resolve_errors:
        result["errors"].extend(resolve_errors)
        log_operation_result(paths.operations_log, result)
        return result

    if is_building(db_path) and not is_stale_building(db_path):
        result["errors"].append(f"rebuild already in progress for infobaseId {db_id}")
        result["result"] = "busy"
        log_operation_result(paths.operations_log, result)
        return result

    result["dbFile"] = db.get("db_file")
    started = time.perf_counter()

    try:
        ok = DatabaseManager.build_from_xml_atomic(db_path, config_xml)
        if not ok:
            result["errors"].append("build_from_xml_atomic returned false")
            log_operation_result(paths.operations_log, result)
            return result
    except Exception as exc:
        result["errors"].append(format_build_error(exc))
        log_operation_result(paths.operations_log, result)
        return result
    finally:
        result["durationMs"] = int((time.perf_counter() - started) * 1000)
        result["completedAt"] = _utc_now_iso()

    user_version = read_db_user_version(db_path)
    result["success"] = True
    result["result"] = "success"
    result["userVersion"] = user_version
    result["expectedVersion"] = INDEXER_VERSION
    log_operation_result(paths.operations_log, result)
    return result


def run_rebuild_all(explicit_root: Optional[PathLike] = None) -> Dict[str, Any]:
    paths = get_paths(explicit_root)
    pm = ProjectManager(str(paths.config), str(paths.data_dir))

    operation_run_id = str(uuid.uuid4())
    started = time.perf_counter()
    results: List[Dict[str, Any]] = []
    warnings: List[str] = []
    any_failed = False

    for project in pm.get_all_projects():
        for db in project.get("databases", []):
            db_id = db.get("id", "")
            entry: Dict[str, Any] = {
                "targetId": db_id,
                "name": db.get("name"),
                "dbFile": db.get("db_file"),
            }

            if not source_exists(db):
                entry["result"] = "skipped"
                entry["success"] = True
                warnings.append(f"Database '{db.get('name')}': sourcePath not found, skipped")
                results.append(entry)
                continue

            sub = run_rebuild_index(db_id, explicit_root=explicit_root)
            entry["success"] = sub.get("success", False)
            entry["result"] = sub.get("result", "failed")
            entry["durationMs"] = sub.get("durationMs", 0)
            entry["userVersion"] = sub.get("userVersion")
            if sub.get("errors"):
                entry["errors"] = sub["errors"]
                any_failed = True
            results.append(entry)

    duration_ms = int((time.perf_counter() - started) * 1000)
    succeeded = sum(1 for r in results if r.get("result") == "success")
    skipped = sum(1 for r in results if r.get("result") == "skipped")
    failed = sum(1 for r in results if r.get("result") not in ("success", "skipped"))

    payload = {
        "success": not any_failed,
        "operation": "rebuild-all",
        "operationRunId": operation_run_id,
        "completedAt": _utc_now_iso(),
        "durationMs": duration_ms,
        "summary": {
            "total": len(results),
            "succeeded": succeeded,
            "skipped": skipped,
            "failed": failed,
        },
        "results": results,
        "warnings": warnings,
        "errors": [] if not any_failed else [f"{failed} database(s) failed to rebuild"],
    }
    log_operation_result(paths.operations_log, payload)
    return payload


def _list_marker_paths(data_dir: Path) -> List[str]:
    if not data_dir.is_dir():
        return []
    return sorted(str(p.resolve()) for p in data_dir.glob(f"*{MARKER_SUFFIX}"))


def _list_tmp_paths(data_dir: Path) -> List[str]:
    if not data_dir.is_dir():
        return []
    return sorted(str(p.resolve()) for p in data_dir.glob(f"*{TMP_SUFFIX}"))


def run_reconcile_markers(explicit_root: Optional[PathLike] = None) -> Dict[str, Any]:
    paths = get_paths(explicit_root)
    data_dir = paths.data_dir

    markers_before = set(_list_marker_paths(data_dir))
    tmp_before = set(_list_tmp_paths(data_dir))

    reconcile_building_markers(data_dir)

    markers_after = set(_list_marker_paths(data_dir))
    tmp_after = set(_list_tmp_paths(data_dir))

    removed_markers = sorted(markers_before - markers_after)
    removed_tmp = sorted(tmp_before - tmp_after)

    return {
        "success": True,
        "operation": "reconcile-markers",
        "operationRunId": str(uuid.uuid4()),
        "completedAt": _utc_now_iso(),
        "removedMarkers": removed_markers,
        "removedTmp": removed_tmp,
        "remainingMarkers": _list_marker_paths(data_dir),
        "remainingTmp": _list_tmp_paths(data_dir),
        "warnings": [],
        "errors": [],
    }


def run_triggered_rebuilds(
    follow_ups: List[Dict[str, Any]],
    explicit_root: Optional[PathLike] = None,
) -> List[Dict[str, Any]]:
    """Execute rebuild-index for each followUpOperation entry."""
    triggered: List[Dict[str, Any]] = []
    for op in follow_ups:
        if op.get("command") != "rebuild-index":
            continue
        args = op.get("args") or {}
        db_id = args.get("db-id") or args.get("db_id")
        if not db_id:
            triggered.append(
                {
                    "success": False,
                    "operation": "rebuild-index",
                    "errors": ["followUpOperations entry missing db-id"],
                    "followUp": op,
                }
            )
            continue
        sub = run_rebuild_index(str(db_id), explicit_root=explicit_root)
        sub["followUp"] = op
        triggered.append(sub)
    return triggered
