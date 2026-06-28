"""Tests for apply-registry (Admin Hub Phase 2)."""

import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from shared.hub_protocol import run_apply_registry, run_export_registry
from shared.registry_apply import apply_registry_fragment, run_apply_registry_from_data
from shared.project_manager import ProjectManager
from shared.registry_ids import is_uuid_v4, validate_hub_id
from shared.source_path import (
    get_effective_config_xml,
    hub_source_fields,
    normalize_db_record,
    resolve_configuration_xml,
    source_exists,
)

PROJECT_ID = "a1b2c3d4-e5f6-4789-a012-3456789abcde"
INFOBASE_ID = "2d90d4c4-4f2c-4c57-8d28-83c0c60db117"
CLIENT_ID = "3e81e5d5-5f3d-4d68-9e39-94d1d71ec228"


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

    manifest = {
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
    (root / "module.manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    projects = {
        "schemaVersion": 1,
        "projects": [
            {
                "id": PROJECT_ID,
                "name": "Existing",
                "active": True,
                "databases": [
                    {
                        "id": INFOBASE_ID,
                        "name": "Main",
                        "type": "base",
                        "db_file": "main.db",
                        "source_path": "D:/old-export",
                        "source_kind": "directory",
                        "source_xml": "D:/old-export/Configuration.xml",
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


def _pm(root: Path) -> ProjectManager:
    return ProjectManager(str(root / "projects.json"), str(root / "databases"))


def _fragment_wrapper(projects_payload, **extra):
    data = {
        "schemaVersion": 1,
        "moduleId": "1c-config-mcp",
        "moduleType": "config-mcp",
        "registryFragment": {"projects": projects_payload, **extra},
    }
    return data


def test_uuid_v4_validation():
    assert is_uuid_v4("2d90d4c4-4f2c-4c57-8d28-83c0c60db117")
    assert not is_uuid_v4("project-1")
    assert validate_hub_id("projectId", "bad-id") is not None


def test_resolve_configuration_xml(tmp_path):
    export_dir = tmp_path / "export"
    export_dir.mkdir()
    (export_dir / "Configuration.xml").write_text("<root/>", encoding="utf-8")
    resolved = resolve_configuration_xml(export_dir, "directory")
    assert resolved == export_dir / "Configuration.xml"


def test_resolve_configuration_xml_ext_fallback(tmp_path):
    export_dir = tmp_path / "export"
    ext_dir = export_dir / "Ext"
    ext_dir.mkdir(parents=True)
    (ext_dir / "Configuration.xml").write_text("<root/>", encoding="utf-8")
    resolved = resolve_configuration_xml(export_dir, "directory")
    assert resolved == ext_dir / "Configuration.xml"


def test_normalize_legacy_source_xml():
    db = {"source_xml": "D:/export/Configuration.xml"}
    normalized = normalize_db_record(db)
    assert Path(normalized["source_path"]) == Path("D:/export")
    assert normalized["source_kind"] == "directory"


def test_hub_source_fields_legacy():
    db = {"source_xml": "D:/export/Configuration.xml"}
    fields = hub_source_fields(db)
    assert Path(fields["sourcePath"]) == Path("D:/export")
    assert fields["sourceKind"] == "directory"


def test_apply_upsert_new_project_and_infobase(portable_root, tmp_path):
    export_dir = tmp_path / "new-export"
    export_dir.mkdir()
    (export_dir / "Configuration.xml").write_text("<root/>", encoding="utf-8")

    new_project_id = "b2c3d4e5-f6a7-4890-b123-456789abcdef"
    new_infobase_id = "c3d4e5f6-a7b8-4901-a234-567890abcdef"

    payload = _fragment_wrapper(
        [
            {
                "projectId": new_project_id,
                "name": "New Project",
                "active": True,
                "databases": [
                    {
                        "infobaseId": new_infobase_id,
                        "name": "New Base",
                        "type": "base",
                        "sourcePath": str(export_dir),
                        "sourceKind": "directory",
                    }
                ],
            }
        ]
    )

    result = run_apply_registry_from_data(payload, portable_root)
    assert result["success"] is True
    assert result["changes"]["created"] == 2

    pm = _pm(portable_root)
    project = pm.get_project(new_project_id)
    assert project is not None
    db = project["databases"][0]
    assert db["db_file"].endswith(".db")
    assert db["source_path"] == str(export_dir)
    assert db["source_kind"] == "directory"
    assert Path(db["source_xml"]).name == "Configuration.xml"


def test_apply_update_preserves_db_file(portable_root, tmp_path):
    export_dir = tmp_path / "updated-export"
    export_dir.mkdir()
    (export_dir / "Configuration.xml").write_text("<root/>", encoding="utf-8")

    payload = _fragment_wrapper(
        [
            {
                "projectId": PROJECT_ID,
                "name": "Renamed",
                "active": True,
                "databases": [
                    {
                        "infobaseId": INFOBASE_ID,
                        "name": "Renamed Base",
                        "type": "base",
                        "sourcePath": str(export_dir),
                        "sourceKind": "directory",
                    }
                ],
            }
        ]
    )

    result = run_apply_registry_from_data(payload, portable_root)
    assert result["success"] is True
    assert result["changes"]["updated"] >= 1

    pm = _pm(portable_root)
    db = pm.get_project(PROJECT_ID)["databases"][0]
    assert db["db_file"] == "main.db"
    assert db["name"] == "Renamed Base"
    assert db["source_path"] == str(export_dir)


def test_apply_invalid_uuid_no_disk_change(portable_root):
    before = (portable_root / "projects.json").read_text(encoding="utf-8")
    payload = _fragment_wrapper(
        [
            {
                "projectId": "not-a-uuid",
                "name": "Bad",
                "databases": [],
            }
        ]
    )
    result = run_apply_registry_from_data(payload, portable_root)
    assert result["success"] is False
    assert any("UUID" in e for e in result["errors"])
    after = (portable_root / "projects.json").read_text(encoding="utf-8")
    assert before == after


def test_apply_wrong_module_id(portable_root):
    payload = {
        "schemaVersion": 1,
        "moduleId": "wrong-module",
        "moduleType": "config-mcp",
        "registryFragment": {"projects": []},
    }
    result = run_apply_registry_from_data(payload, portable_root)
    assert result["success"] is False
    assert any("moduleId" in e for e in result["errors"])


def test_apply_archive_skipped(portable_root):
    payload = _fragment_wrapper(
        [
            {
                "projectId": PROJECT_ID,
                "name": "Existing",
                "databases": [
                    {
                        "infobaseId": INFOBASE_ID,
                        "name": "Main",
                        "sourcePath": "D:/archive.zip",
                        "sourceKind": "archive",
                    }
                ],
            }
        ]
    )
    result = run_apply_registry_from_data(payload, portable_root)
    assert result["success"] is True
    assert result["changes"]["skipped"] == 1
    assert any("archive" in w.lower() for w in result["warnings"])


def test_apply_removed_infobase(portable_root):
    payload = _fragment_wrapper([], removedIds={"infobaseIds": [INFOBASE_ID]})
    result = run_apply_registry_from_data(payload, portable_root)
    assert result["success"] is True
    assert result["changes"]["removed"] == 1
    pm = _pm(portable_root)
    assert pm.get_project(PROJECT_ID)["databases"] == []


def test_apply_source_path_change_follow_up(portable_root, tmp_path):
    export_dir = tmp_path / "follow-up-export"
    export_dir.mkdir()
    (export_dir / "Configuration.xml").write_text("<root/>", encoding="utf-8")

    payload = _fragment_wrapper(
        [
            {
                "projectId": PROJECT_ID,
                "name": "Existing",
                "databases": [
                    {
                        "infobaseId": INFOBASE_ID,
                        "name": "Main",
                        "sourcePath": str(export_dir),
                        "sourceKind": "directory",
                    }
                ],
            }
        ]
    )
    result = run_apply_registry_from_data(payload, portable_root)
    follow_ups = result["postApplyActions"]["followUpOperations"]
    assert any(f["command"] == "rebuild-index" for f in follow_ups)
    assert any(f["args"]["db-id"] == INFOBASE_ID for f in follow_ups)


def test_apply_atomic_write_failure(portable_root, tmp_path):
    export_dir = tmp_path / "atomic-export"
    export_dir.mkdir()
    (export_dir / "Configuration.xml").write_text("<root/>", encoding="utf-8")

    payload = _fragment_wrapper(
        [
            {
                "projectId": PROJECT_ID,
                "name": "Existing",
                "databases": [
                    {
                        "infobaseId": INFOBASE_ID,
                        "name": "Main",
                        "sourcePath": str(export_dir),
                        "sourceKind": "directory",
                    }
                ],
            }
        ]
    )

    pm = _pm(portable_root)
    before = (portable_root / "projects.json").read_text(encoding="utf-8")

    with patch.object(ProjectManager, "save_projects_atomic", side_effect=OSError("disk full")):
        with pytest.raises(OSError):
            apply_registry_fragment(payload, pm)

    after = (portable_root / "projects.json").read_text(encoding="utf-8")
    assert before == after


def test_export_legacy_source_path(portable_root):
    result = run_export_registry(portable_root)
    db = result["registryFragment"]["projects"][0]["databases"][0]
    assert "sourcePath" in db
    assert "sourceKind" in db
    assert db["sourceKind"] == "directory"
    assert "sourceXml" not in db


def test_cli_apply_registry(portable_root, tmp_path):
    export_dir = tmp_path / "cli-export"
    export_dir.mkdir()
    (export_dir / "Configuration.xml").write_text("<root/>", encoding="utf-8")

    fragment_path = tmp_path / "fragment.json"
    fragment_path.write_text(
        json.dumps(
            _fragment_wrapper(
                [
                    {
                        "projectId": PROJECT_ID,
                        "name": "CLI Updated",
                        "databases": [
                            {
                                "infobaseId": INFOBASE_ID,
                                "name": "Main",
                                "sourcePath": str(export_dir),
                                "sourceKind": "directory",
                            }
                        ],
                    }
                ]
            ),
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    repo_root = Path(__file__).resolve().parent.parent
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "admin_tool.cli",
            "--root",
            str(portable_root),
            "apply-registry",
            "--input",
            str(fragment_path),
            "--json",
        ],
        capture_output=True,
        text=True,
        cwd=str(repo_root),
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    data = json.loads(proc.stdout)
    assert data["success"] is True


def test_source_exists_directory(tmp_path):
    export_dir = tmp_path / "exists-export"
    export_dir.mkdir()
    (export_dir / "Configuration.xml").write_text("<root/>", encoding="utf-8")
    db = {
        "source_path": str(export_dir),
        "source_kind": "directory",
    }
    assert source_exists(db) is True
    assert get_effective_config_xml(db) is not None
