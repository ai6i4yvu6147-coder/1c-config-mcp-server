"""Tests for Admin Hub protocol (Phase 1 read-only)."""

import json
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from shared.hub_protocol import run_export_registry, run_inventory, run_status

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


@pytest.fixture
def portable_root(tmp_path):
    root = tmp_path / "portable"
    root.mkdir()
    (root / "databases").mkdir()
    (root / "Server").mkdir()
    (root / "Admin").mkdir()
    (root / "Tools").mkdir()
    (root / "Server" / "1c-config-server.exe").write_bytes(b"")
    (root / "Admin" / "1C-Config-Admin.exe").write_bytes(b"")
    (root / "Tools" / "1c-config-cli.exe").write_bytes(b"")

    (root / "module.manifest.json").write_text(
        json.dumps(MANIFEST, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    projects = {
        "schemaVersion": 1,
        "projects": [
            {
                "id": "project-1",
                "name": "Test Project",
                "active": True,
                "databases": [
                    {
                        "id": "db-1",
                        "name": "Main",
                        "type": "base",
                        "db_file": "main.db",
                        "source_xml": "D:/missing/Configuration.xml",
                    }
                ],
            }
        ],
    }
    (root / "projects.json").write_text(
        json.dumps(projects, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return root


def _create_db(path: Path, user_version: int):
    conn = sqlite3.connect(path)
    conn.execute(f"PRAGMA user_version = {user_version}")
    conn.commit()
    conn.close()


def test_inventory_absolute_paths(portable_root):
    result = run_inventory(portable_root)
    assert result["moduleId"] == "1c-config-mcp"
    assert result["schemaVersion"] == 1
    assert Path(result["rootPath"]).is_absolute()
    assert Path(result["configPath"]).is_absolute()
    assert result["statusSupport"] is True
    assert result["cliPath"].endswith("1c-config-cli.exe")


def test_status_warnings_outdated_db(portable_root):
    db_path = portable_root / "databases" / "main.db"
    _create_db(db_path, 9)

    result = run_status(portable_root)
    assert result["moduleId"] == "1c-config-mcp"
    assert result["readiness"] in ("ready", "degraded", "busy")
    assert result["status"] in ("ok", "warning", "error")
    assert result["details"]["configReadable"] is True
    assert any("outdated" in w.lower() for w in result["warnings"])
    assert result["projects"][0]["databases"][0]["isOutdated"] is True


def test_status_build_lock(portable_root):
    db_path = portable_root / "databases" / "main.db"
    _create_db(db_path, 10)
    marker = portable_root / "databases" / "main.db.building"
    marker.write_text('{"pid": 999999, "started_at": "2026-01-01T00:00:00Z"}', encoding="utf-8")

    result = run_status(portable_root)
    assert len(result["locks"]) >= 1
    assert result["locks"][0]["type"] == "build-marker"
    assert result["locks"][0]["targetId"] == "db-1"


def test_export_registry_fragment(portable_root):
    db_path = portable_root / "databases" / "main.db"
    _create_db(db_path, 10)

    result = run_export_registry(portable_root)
    assert result["schemaVersion"] == 1
    assert result["moduleType"] == "config-mcp"
    projects = result["registryFragment"]["projects"]
    assert projects[0]["projectId"] == "project-1"
    db = projects[0]["databases"][0]
    assert db["infobaseId"] == "db-1"
    assert "sourcePath" in db
    assert "sourceKind" in db
    assert "sourceXml" not in db
    assert "indexStatus" in db
    assert db["indexStatus"]["expectedVersion"] >= 10
    assert "db_file" not in db
    assert "dbFile" not in db


def test_cli_status_json(portable_root):
    repo_root = Path(__file__).resolve().parent.parent
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "admin_tool.cli",
            "--root",
            str(portable_root),
            "status",
            "--json",
        ],
        capture_output=True,
        text=True,
        cwd=str(repo_root),
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    data = json.loads(proc.stdout)
    assert data["moduleId"] == "1c-config-mcp"
