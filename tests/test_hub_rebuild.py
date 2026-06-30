"""Tests for Admin Hub Phase 3 rebuild CLI."""

from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from shared.hub_protocol import run_status
from shared.hub_rebuild import run_rebuild_all, run_rebuild_index, run_reconcile_markers
from shared.indexer_version import INDEXER_VERSION

PROJECT_ID = "a1b2c3d4-e5f6-4789-a012-3456789abcde"
INFOBASE_ID = "2d90d4c4-4f2c-4c57-8d28-83c0c60db117"

MANIFEST = {
    "schemaVersion": 1,
    "moduleType": "config-mcp",
    "moduleName": "1C Config MCP",
    "moduleId": "1c-config-mcp",
    "moduleVersion": "1.0.0",
    "mode": "standalone",
    "runtime": {
        "kind": "python-exe",
        "entryExe": "Server/1c-config-server.exe",
        "adminExe": "Admin/1C-Config-Admin.exe",
        "cliExe": "Tools/1c-config-cli.exe",
    },
    "paths": {
        "root": ".",
        "config": "projects.json",
        "dataDir": "databases",
        "logsDir": "logs",
        "operationsLog": "logs/operations.log",
    },
}

REPO_ROOT = Path(__file__).resolve().parent.parent


def _write_portable(root: Path, projects: dict) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "databases").mkdir(exist_ok=True)
    for sub in ("Server", "Admin", "Tools"):
        (root / sub).mkdir(exist_ok=True)
        if sub == "Server":
            (root / sub / "1c-config-server.exe").write_bytes(b"")
        elif sub == "Admin":
            (root / sub / "1C-Config-Admin.exe").write_bytes(b"")
        else:
            (root / sub / "1c-config-cli.exe").write_bytes(b"")
    (root / "module.manifest.json").write_text(
        json.dumps(MANIFEST, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (root / "projects.json").write_text(
        json.dumps(projects, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return root


def _minimal_projects(source_xml: str, db_id: str = INFOBASE_ID) -> dict:
    return {
        "schemaVersion": 1,
        "projects": [
            {
                "id": PROJECT_ID,
                "name": "Test Project",
                "active": True,
                "databases": [
                    {
                        "id": db_id,
                        "name": "Main",
                        "type": "base",
                        "db_file": "main.db",
                        "source_xml": source_xml,
                    }
                ],
            }
        ],
    }


def _create_db(path: Path, user_version: int) -> None:
    conn = sqlite3.connect(path)
    conn.execute(f"PRAGMA user_version = {user_version}")
    conn.commit()
    conn.close()


def _run_cli(root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "admin_tool.cli", "--root", str(root), *args],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        check=False,
    )


@pytest.fixture
def portable_with_source(tmp_path):
    source_dir = tmp_path / "export" / "Основная конфигурация"
    source_dir.mkdir(parents=True)
    config_xml = source_dir / "Configuration.xml"
    config_xml.write_text(
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<MetaDataObject xmlns="http://v8.1c.ru/8.3/MDClasses">'
        "<Configuration><Properties><Name>Test</Name></Properties>"
        "<ChildObjects></ChildObjects></Configuration>"
        "</MetaDataObject>",
        encoding="utf-8",
    )
    root = tmp_path / "portable"
    _write_portable(root, _minimal_projects(str(config_xml)))
    return root, config_xml


def test_rebuild_index_unknown_id(tmp_path):
    root = _write_portable(
        tmp_path / "portable",
        _minimal_projects("D:/missing/Configuration.xml"),
    )
    result = run_rebuild_index("unknown-id", root)
    assert result["success"] is False
    assert any("not found" in e for e in result["errors"])

    proc = _run_cli(root, "rebuild-index", "--db-id", "unknown-id", "--json")
    assert proc.returncode == 1
    data = json.loads(proc.stdout)
    assert data["success"] is False


@patch("shared.hub_rebuild.DatabaseManager.build_from_xml_atomic", return_value=True)
def test_rebuild_index_success(mock_build, portable_with_source):
    root, config_xml = portable_with_source
    result = run_rebuild_index(INFOBASE_ID, root)
    assert result["success"] is True
    assert result["result"] == "success"
    assert result["targetId"] == INFOBASE_ID
    assert result["durationMs"] >= 0
    mock_build.assert_called_once()
    args = mock_build.call_args[0]
    assert args[0].name == "main.db"
    assert args[1] == str(config_xml)


@patch(
    "shared.hub_rebuild.DatabaseManager.build_from_xml_atomic",
    side_effect=ValueError("parse failed"),
)
def test_rebuild_index_runtime_error(mock_build, portable_with_source):
    root, _ = portable_with_source
    result = run_rebuild_index(INFOBASE_ID, root)
    assert result["success"] is False
    assert any("parse failed" in e for e in result["errors"])


def test_rebuild_index_busy(portable_with_source):
    root, _ = portable_with_source
    db_path = root / "databases" / "main.db"
    marker = root / "databases" / "main.db.building"
    marker.write_text(
        json.dumps({"pid": 999999, "started_at": "2026-01-01T00:00:00Z"}),
        encoding="utf-8",
    )
    (root / "databases" / "main.db.tmp").write_bytes(b"")
    result = run_rebuild_index(INFOBASE_ID, root)
    assert result["success"] is False
    assert result["result"] == "busy"
    proc = _run_cli(root, "rebuild-index", "--db-id", INFOBASE_ID, "--json")
    assert proc.returncode == 3


@patch("shared.hub_rebuild.DatabaseManager.build_from_xml_atomic", return_value=True)
def test_rebuild_all_mixed(mock_build, portable_with_source, tmp_path):
    root, config_xml = portable_with_source
    projects = _minimal_projects(str(config_xml), db_id=INFOBASE_ID)
    projects["projects"][0]["databases"].append(
        {
            "id": "db-2",
            "name": "NoSource",
            "type": "extension",
            "db_file": "ext.db",
            "source_xml": str(tmp_path / "missing" / "Configuration.xml"),
        }
    )
    (root / "projects.json").write_text(json.dumps(projects), encoding="utf-8")

    result = run_rebuild_all(root)
    assert result["success"] is True
    assert result["summary"]["succeeded"] == 1
    assert result["summary"]["skipped"] == 1


def test_reconcile_markers_removes_stale(portable_with_source):
    root, _ = portable_with_source
    marker = root / "databases" / "main.db.building"
    marker.write_text('{"pid": 999999}', encoding="utf-8")
    orphan_tmp = root / "databases" / "orphan.db.tmp"
    orphan_tmp.write_bytes(b"x")

    result = run_reconcile_markers(root)
    assert result["success"] is True
    assert not marker.exists()
    assert not orphan_tmp.exists()
    assert str(marker.resolve()) in result["removedMarkers"]


def test_status_index_readiness_missing(portable_with_source):
    root, _ = portable_with_source
    result = run_status(root)
    db = result["projects"][0]["databases"][0]
    assert db["indexReadiness"] == "missing"
    assert db["sourcePathExists"] is True
    assert db["dbExists"] is False


def test_status_index_readiness_current(portable_with_source):
    root, _ = portable_with_source
    _create_db(root / "databases" / "main.db", INDEXER_VERSION)
    result = run_status(root)
    db = result["projects"][0]["databases"][0]
    assert db["indexReadiness"] == "current"


@patch("shared.hub_rebuild.DatabaseManager.build_from_xml_atomic", return_value=True)
def test_cli_trigger_rebuild_on_apply(mock_build, portable_with_source, tmp_path):
    from shared.hub_protocol import run_apply_registry
    from shared.hub_rebuild import run_triggered_rebuilds

    root, config_xml = portable_with_source
    new_source = tmp_path / "export2" / "Основная конфигурация"
    new_source.mkdir(parents=True)
    new_xml = new_source / "Configuration.xml"
    new_xml.write_text(config_xml.read_text(encoding="utf-8"), encoding="utf-8")

    fragment = {
        "schemaVersion": 1,
        "moduleId": "1c-config-mcp",
        "registryFragment": {
            "projects": [
                {
                    "projectId": PROJECT_ID,
                    "name": "Test Project",
                    "active": True,
                    "databases": [
                        {
                            "infobaseId": INFOBASE_ID,
                            "name": "Main",
                            "type": "base",
                            "sourcePath": str(new_source),
                            "sourceKind": "directory",
                        }
                    ],
                }
            ],
        },
    }
    fragment_path = tmp_path / "fragment.json"
    fragment_path.write_text(json.dumps(fragment), encoding="utf-8")

    payload = run_apply_registry(fragment_path, root)
    assert payload["success"] is True
    follow_ups = payload["postApplyActions"]["followUpOperations"]
    assert follow_ups

    triggered = run_triggered_rebuilds(follow_ups, explicit_root=root)
    assert triggered[0]["success"] is True
    mock_build.assert_called()
