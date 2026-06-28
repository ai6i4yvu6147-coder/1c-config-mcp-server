"""Portable module root and path resolution (Admin Hub protocol)."""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Union

from shared.module_version import MODULE_VERSION

PathLike = Union[str, Path]

MANIFEST_FILENAME = "module.manifest.json"
ENV_MODULE_ROOT = "CONFIG_MCP_ROOT"

DEFAULT_PATHS = {
    "config": "projects.json",
    "dataDir": "databases",
    "logsDir": "logs",
    "operationsLog": "logs/operations.log",
}

DEFAULT_RUNTIME = {
    "entryExe": "Server/1c-config-server.exe",
    "adminExe": "Admin/1C-Config-Admin.exe",
    "cliExe": "Tools/1c-config-cli.exe",
}


@dataclass(frozen=True)
class ModulePaths:
    root: Path
    manifest_path: Path
    config: Path
    data_dir: Path
    logs_dir: Path
    operations_log: Path
    runtime_exe: Path
    admin_exe: Path
    cli_exe: Path
    mode: str
    module_id: str
    module_type: str
    module_version: str
    manifest: Optional[Dict[str, Any]]


def resolve_module_root(explicit_root: Optional[PathLike] = None) -> Path:
    """
    Module root resolution order:
    1. explicit_root (CLI --root)
    2. CONFIG_MCP_ROOT env
    3. frozen: exe.parent.parent (Portable/Subdir/exe)
    4. development: cwd
    """
    if explicit_root is not None:
        return Path(explicit_root).resolve()

    env_root = os.environ.get(ENV_MODULE_ROOT)
    if env_root:
        return Path(env_root).resolve()

    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent.parent

    return Path.cwd().resolve()


def load_manifest(root: PathLike) -> Optional[Dict[str, Any]]:
    path = Path(root).resolve() / MANIFEST_FILENAME
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _resolve_path(root: Path, rel_or_abs: str) -> Path:
    p = Path(rel_or_abs)
    if p.is_absolute():
        return p.resolve()
    return (root / p).resolve()


def get_paths(explicit_root: Optional[PathLike] = None) -> ModulePaths:
    root = resolve_module_root(explicit_root)
    manifest = load_manifest(root)

    paths_cfg = dict(DEFAULT_PATHS)
    runtime_cfg = dict(DEFAULT_RUNTIME)
    mode = "standalone"
    module_id = "1c-config-mcp"
    module_type = "config-mcp"
    module_version = MODULE_VERSION

    if manifest:
        paths_cfg.update(manifest.get("paths") or {})
        runtime_cfg.update(manifest.get("runtime") or {})
        mode = manifest.get("mode") or mode
        module_id = manifest.get("moduleId") or module_id
        module_type = manifest.get("moduleType") or module_type
        module_version = manifest.get("moduleVersion") or module_version

    manifest_path = root / MANIFEST_FILENAME

    return ModulePaths(
        root=root,
        manifest_path=manifest_path.resolve(),
        config=_resolve_path(root, paths_cfg["config"]),
        data_dir=_resolve_path(root, paths_cfg["dataDir"]),
        logs_dir=_resolve_path(root, paths_cfg["logsDir"]),
        operations_log=_resolve_path(root, paths_cfg["operationsLog"]),
        runtime_exe=_resolve_path(root, runtime_cfg["entryExe"]),
        admin_exe=_resolve_path(root, runtime_cfg["adminExe"]),
        cli_exe=_resolve_path(root, runtime_cfg["cliExe"]),
        mode=mode,
        module_id=module_id,
        module_type=module_type,
        module_version=module_version,
        manifest=manifest,
    )
