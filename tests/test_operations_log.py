"""Tests for append-only operations log (Admin Hub protocol v1 §11)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from shared.hub_rebuild import run_rebuild_index
from shared.operations_log import (
    append_operation_record,
    log_operation_result,
    record_from_operation_result,
)
from shared.registry_apply import run_apply_registry_from_data

PROJECT_ID = "a1b2c3d4-e5f6-4789-a012-3456789abcde"
INFOBASE_ID = "2d90d4c4-4f2c-4c57-8d28-83c0c60db117"
CLIENT_ID = "3e81e5d5-5f3d-4d68-9e39-94d1d71ec228"


def _read_jsonl(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def test_record_from_rebuild_index_success():
    record = record_from_operation_result(
        {
            "success": True,
            "operation": "rebuild-index",
            "operationRunId": "run-1",
            "targetId": INFOBASE_ID,
            "result": "success",
            "completedAt": "2026-06-28T10:00:00Z",
            "durationMs": 4200,
        }
    )
    assert record["operation"] == "rebuild-index"
    assert record["targetId"] == INFOBASE_ID
    assert record["result"] == "success"
    assert record["message"] == "Index rebuilt"
    assert record["durationMs"] == 4200


def test_record_from_apply_registry_failed():
    record = record_from_operation_result(
        {
            "success": False,
            "appliedAt": "2026-06-28T10:00:00Z",
            "operationRunId": "run-2",
            "durationMs": 12,
            "errors": ["infobaseId must be UUID v4"],
            "changes": {"created": 0, "updated": 0, "removed": 0, "skipped": 0},
        }
    )
    assert record["operation"] == "apply-registry"
    assert "targetId" not in record
    assert record["result"] == "failed"
    assert "UUID" in record["message"]


def test_append_operation_record_creates_log_dir(tmp_path):
    log_path = tmp_path / "logs" / "operations.log"
    append_operation_record(
        log_path,
        {
            "timestamp": "2026-06-28T10:00:00Z",
            "operation": "rebuild-index",
            "operationRunId": "run-3",
            "result": "success",
            "message": "Index rebuilt",
            "durationMs": 1,
            "targetId": INFOBASE_ID,
        },
    )
    entries = _read_jsonl(log_path)
    assert len(entries) == 1
    assert entries[0]["operation"] == "rebuild-index"


@pytest.fixture
def portable_root(tmp_path):
    root = tmp_path / "portable"
    root.mkdir()
    (root / "databases").mkdir()
    (root / "logs").mkdir()
    manifest = {
        "schemaVersion": 1,
        "moduleType": "config-mcp",
        "moduleId": "1c-config-mcp",
        "paths": {
            "config": "projects.json",
            "dataDir": "databases",
            "logsDir": "logs",
            "operationsLog": "logs/operations.log",
        },
    }
    (root / "module.manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (root / "projects.json").write_text(
        json.dumps({"schemaVersion": 1, "projects": []}),
        encoding="utf-8",
    )
    return root


def test_apply_registry_appends_log_on_success(portable_root):
    payload = {
        "schemaVersion": 1,
        "moduleId": "1c-config-mcp",
        "registryFragment": {
            "projects": [
                {
                    "projectId": PROJECT_ID,
                    "clientId": CLIENT_ID,
                    "name": "New",
                    "active": True,
                    "databases": [
                        {
                            "infobaseId": INFOBASE_ID,
                            "name": "Main",
                            "type": "base",
                            "sourcePath": "D:/export",
                            "sourceKind": "directory",
                        }
                    ],
                }
            ]
        },
    }
    result = run_apply_registry_from_data(payload, explicit_root=portable_root)
    assert result["success"]

    log_path = portable_root / "logs" / "operations.log"
    entries = _read_jsonl(log_path)
    assert len(entries) == 1
    assert entries[0]["operation"] == "apply-registry"
    assert entries[0]["result"] == "success"
    assert entries[0]["operationRunId"] == result["operationRunId"]
    assert "created=" in entries[0]["message"]


def test_apply_registry_appends_log_on_validation_error(portable_root):
    payload = {
        "registryFragment": {
            "projects": [
                {
                    "projectId": "not-a-uuid",
                    "databases": [],
                }
            ]
        }
    }
    result = run_apply_registry_from_data(payload, explicit_root=portable_root)
    assert not result["success"]

    entries = _read_jsonl(portable_root / "logs" / "operations.log")
    assert len(entries) == 1
    assert entries[0]["result"] == "failed"


def test_rebuild_index_appends_log_on_unknown_id(portable_root):
    result = run_rebuild_index("00000000-0000-4000-8000-000000000001", explicit_root=portable_root)
    assert not result["success"]

    entries = _read_jsonl(portable_root / "logs" / "operations.log")
    assert len(entries) == 1
    assert entries[0]["operation"] == "rebuild-index"
    assert entries[0]["result"] == "failed"


def test_log_operation_result_appends_multiple_lines(tmp_path):
    log_path = tmp_path / "operations.log"
    log_operation_result(
        log_path,
        {
            "success": True,
            "operation": "rebuild-index",
            "operationRunId": "a",
            "targetId": INFOBASE_ID,
            "result": "success",
            "completedAt": "2026-06-28T10:00:00Z",
            "durationMs": 5,
        },
    )
    log_operation_result(
        log_path,
        {
            "success": True,
            "appliedAt": "2026-06-28T10:01:00Z",
            "operationRunId": "b",
            "durationMs": 3,
            "changes": {"created": 0, "updated": 1, "removed": 0, "skipped": 0},
        },
    )
    entries = _read_jsonl(log_path)
    assert len(entries) == 2
    assert entries[0]["operation"] == "rebuild-index"
    assert entries[1]["operation"] == "apply-registry"
