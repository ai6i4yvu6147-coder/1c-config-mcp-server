"""Append-only operations log (Admin Hub protocol v1 §11)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

PathLike = str | Path


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _apply_message(result: Dict[str, Any]) -> str:
    if result.get("success"):
        changes = result.get("changes") or {}
        return (
            f"created={changes.get('created', 0)} "
            f"updated={changes.get('updated', 0)} "
            f"removed={changes.get('removed', 0)} "
            f"skipped={changes.get('skipped', 0)}"
        )
    errors = result.get("errors") or []
    if errors:
        return str(errors[0])
    return "apply-registry failed"


def _rebuild_message(result: Dict[str, Any]) -> str:
    op_result = result.get("result", "failed")
    if op_result == "success":
        return "Index rebuilt"
    if op_result == "busy":
        return "rebuild already in progress"
    if op_result == "skipped":
        return "sourcePath not found, skipped"
    errors = result.get("errors") or []
    if errors:
        return str(errors[0])
    return f"{result.get('operation', 'rebuild')} {op_result}"


def _rebuild_all_message(result: Dict[str, Any]) -> str:
    summary = result.get("summary") or {}
    return (
        f"total={summary.get('total', 0)} "
        f"succeeded={summary.get('succeeded', 0)} "
        f"skipped={summary.get('skipped', 0)} "
        f"failed={summary.get('failed', 0)}"
    )


def record_from_operation_result(result: Dict[str, Any]) -> Dict[str, Any]:
    """Build a protocol v1 §11.1 log record from a CLI operation result."""
    operation = result.get("operation") or "apply-registry"

    if operation == "apply-registry":
        op_result = "success" if result.get("success") else "failed"
        message = _apply_message(result)
        timestamp = result.get("appliedAt") or _utc_now_iso()
        duration_ms = result.get("durationMs", 0)
        target_id = None
    elif operation == "rebuild-all":
        op_result = "success" if result.get("success") else "failed"
        message = _rebuild_all_message(result)
        timestamp = result.get("completedAt") or _utc_now_iso()
        duration_ms = result.get("durationMs", 0)
        target_id = None
    else:
        op_result = result.get("result") or ("success" if result.get("success") else "failed")
        message = _rebuild_message(result)
        timestamp = result.get("completedAt") or _utc_now_iso()
        duration_ms = result.get("durationMs", 0)
        target_id = result.get("targetId")

    record: Dict[str, Any] = {
        "timestamp": timestamp,
        "operation": operation,
        "operationRunId": result.get("operationRunId") or "",
        "result": op_result,
        "message": message,
        "durationMs": duration_ms,
    }
    if target_id:
        record["targetId"] = target_id
    return record


def append_operation_record(log_path: PathLike, record: Dict[str, Any]) -> None:
    """Append one JSONL line to the operations log (creates parent dirs)."""
    path = Path(log_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record, ensure_ascii=False, separators=(",", ":"))
    with path.open("a", encoding="utf-8", newline="\n") as fh:
        fh.write(line)
        fh.write("\n")


def log_operation_result(log_path: PathLike, result: Dict[str, Any]) -> None:
    """Append an audit record derived from a control-plane operation result."""
    append_operation_record(log_path, record_from_operation_result(result))
