"""Tests for UTF-8 JSON CLI I/O (protocol v1.0.3)."""

import io
import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from shared.cli_json import read_json_file, write_json_stdout

PROJECT_ID = "a1b2c3d4-e5f6-4789-a012-3456789abcde"
INFOBASE_ID = "2d90d4c4-4f2c-4c57-8d28-83c0c60db117"
CYRILLIC_NAME = "Тестовый проект"


@pytest.fixture
def portable_root_cyrillic(tmp_path):
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
                "name": CYRILLIC_NAME,
                "active": True,
                "databases": [
                    {
                        "id": INFOBASE_ID,
                        "name": "Основная",
                        "type": "base",
                        "db_file": "main.db",
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


def _run_cli_bytes(root: Path, *cli_args: str) -> tuple[int, bytes, bytes]:
    repo_root = Path(__file__).resolve().parent.parent
    proc = subprocess.run(
        [sys.executable, "-m", "admin_tool.cli", "--root", str(root), *cli_args],
        capture_output=True,
        cwd=str(repo_root),
        check=False,
    )
    return proc.returncode, proc.stdout, proc.stderr


def _assert_utf8_json_stdout(raw: bytes, expected_name: str | None = None) -> dict:
    assert not raw.startswith(b"\xef\xbb\xbf")
    text = raw.decode("utf-8")
    assert "\ufffd" not in text
    data = json.loads(text)
    if expected_name is not None:
        assert data["projects"][0]["name"] == expected_name
    return data


def test_write_json_stdout_cyrillic():
    buf = io.BytesIO()

    class FakeStdout:
        pass

    fake = FakeStdout()
    fake.buffer = buf
    with patch("sys.stdout", fake):
        write_json_stdout({"name": CYRILLIC_NAME})
    raw = buf.getvalue()
    assert not raw.startswith(b"\xef\xbb\xbf")
    text = raw.decode("utf-8").strip()
    assert json.loads(text)["name"] == CYRILLIC_NAME


def test_read_json_file_rejects_bom(tmp_path):
    path = tmp_path / "fragment.json"
    path.write_bytes(b"\xef\xbb\xbf{}")
    with pytest.raises(ValueError, match="BOM"):
        read_json_file(path)


def test_read_json_file_utf8(tmp_path):
    path = tmp_path / "fragment.json"
    path.write_text('{"ok": true}', encoding="utf-8")
    assert read_json_file(path) == {"ok": True}


def test_status_json_stdout_utf8_cyrillic(portable_root_cyrillic):
    code, stdout, stderr = _run_cli_bytes(portable_root_cyrillic, "status", "--json")
    assert code == 0, stderr.decode("utf-8", errors="replace")
    _assert_utf8_json_stdout(stdout, CYRILLIC_NAME)


def test_inventory_json_stdout_utf8(portable_root_cyrillic):
    code, stdout, stderr = _run_cli_bytes(portable_root_cyrillic, "inventory", "--json")
    assert code == 0, stderr.decode("utf-8", errors="replace")
    raw_text = stdout.decode("utf-8")
    assert "\ufffd" not in raw_text
    assert not stdout.startswith(b"\xef\xbb\xbf")


def test_apply_registry_invalid_uuid_stdout_utf8(portable_root_cyrillic, tmp_path):
    fragment_path = tmp_path / "bad.json"
    fragment_path.write_text(
        json.dumps(
            {
                "schemaVersion": 1,
                "moduleId": "1c-config-mcp",
                "moduleType": "config-mcp",
                "registryFragment": {
                    "projects": [{"projectId": "not-uuid", "name": "X", "databases": []}]
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    code, stdout, stderr = _run_cli_bytes(
        portable_root_cyrillic,
        "apply-registry",
        "--input",
        str(fragment_path),
        "--json",
    )
    assert code == 1
    data = _assert_utf8_json_stdout(stdout)
    assert data["success"] is False


def test_apply_registry_rejects_bom_input(portable_root_cyrillic, tmp_path):
    fragment_path = tmp_path / "bom.json"
    fragment_path.write_bytes(b"\xef\xbb\xbf{}")
    code, stdout, stderr = _run_cli_bytes(
        portable_root_cyrillic,
        "apply-registry",
        "--input",
        str(fragment_path),
        "--json",
    )
    assert code == 1
    assert stderr  # error message on stderr
