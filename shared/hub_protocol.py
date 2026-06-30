"""Admin Hub protocol v1.0.3 operations for config-mcp."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from shared.cli_json import read_json_file
from shared.db_build_state import is_stale_building
from shared.index_status import build_index_status, collect_locks_for_db, compute_index_readiness
from shared.indexer_version import INDEXER_VERSION
from shared.project_manager import ProjectManager
from shared.registry_apply import run_apply_registry_from_data
from shared.runtime_paths import get_paths
from shared.source_path import hub_source_fields, source_exists

PathLike = str | Path


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _abs_str(path: Path) -> str:
    return str(path.resolve())


def run_inventory(explicit_root: Optional[PathLike] = None) -> Dict[str, Any]:
    paths = get_paths(explicit_root)
    manifest_exists = paths.manifest_path.is_file()

    return {
        "moduleId": paths.module_id,
        "moduleType": paths.module_type,
        "moduleVersion": paths.module_version,
        "schemaVersion": 1,
        "mode": paths.mode,
        "rootPath": _abs_str(paths.root),
        "manifestPath": _abs_str(paths.manifest_path) if manifest_exists else None,
        "configPath": _abs_str(paths.config),
        "runtimePath": _abs_str(paths.runtime_exe),
        "adminPath": _abs_str(paths.admin_exe) if paths.admin_exe.is_file() else None,
        "cliPath": _abs_str(paths.cli_exe) if paths.cli_exe.is_file() else None,
        "dataPaths": [_abs_str(paths.data_dir)],
        "statusSupport": True,
        "syncSupport": True,
        "cliSupport": True,
    }


def run_status(explicit_root: Optional[PathLike] = None) -> Dict[str, Any]:
    paths = get_paths(explicit_root)
    pm = ProjectManager(str(paths.config), str(paths.data_dir))

    config_readable = paths.config.is_file()
    try:
        if config_readable:
            pm.get_all_projects()
    except Exception:
        config_readable = False

    runtime_exists = paths.runtime_exe.is_file()
    admin_exists = paths.admin_exe.is_file()
    cli_exists = paths.cli_exe.is_file()
    data_reachable = paths.data_dir.is_dir()

    warnings: List[str] = []
    errors: List[str] = []
    locks: List[Dict[str, Any]] = []
    projects_out: List[Dict[str, Any]] = []

    outdated_count = 0
    active_locks = 0

    if not paths.manifest_path.is_file():
        warnings.append("module.manifest.json not found; using default paths")

    if not config_readable:
        errors.append(f"Config not readable: {paths.config}")

    for project in pm.get_all_projects():
        databases_out = []
        for db in project.get("databases", []):
            db_path = paths.data_dir / db["db_file"]
            db_id = db.get("id", "")
            src = hub_source_fields(db)
            src_exists = source_exists(db)
            idx = build_index_status(db_path)

            if idx["isOutdated"]:
                outdated_count += 1
                warnings.append(
                    f"Database '{db.get('name')}': index outdated "
                    f"(v{idx['userVersion']} < v{INDEXER_VERSION})"
                )
            if src.get("sourcePath") and not src_exists:
                warnings.append(f"Database '{db.get('name')}': sourcePath not found")
            if idx["isBuilding"] and not is_stale_building(db_path):
                active_locks += 1

            for lock in collect_locks_for_db(db_path, db_id):
                locks.append(lock)

            databases_out.append(
                {
                    "infobaseId": db_id,
                    "name": db.get("name"),
                    "type": db.get("type"),
                    "dbFile": db.get("db_file"),
                    "dbExists": db_path.is_file(),
                    "sourcePath": src.get("sourcePath"),
                    "sourceKind": src.get("sourceKind"),
                    "sourcePathExists": src_exists,
                    "userVersion": idx["userVersion"],
                    "isOutdated": idx["isOutdated"],
                    "isBuilding": idx["isBuilding"],
                    "indexReadiness": compute_index_readiness(
                        db_path, source_path_exists=src_exists
                    ),
                }
            )

        projects_out.append(
            {
                "projectId": project.get("id"),
                "name": project.get("name"),
                "active": project.get("active", False),
                "databases": databases_out,
            }
        )

    stale_locks = any(l.get("stale") for l in locks)

    if errors:
        readiness = "misconfigured"
        status = "error"
    elif active_locks > 0:
        readiness = "busy"
        status = "ok"
    elif stale_locks:
        readiness = "degraded"
        status = "warning"
    elif warnings:
        readiness = "ready"
        status = "warning"
    else:
        readiness = "ready"
        status = "ok"

    summary_parts = [
        f"{len(projects_out)} project(s)",
        f"{sum(len(p['databases']) for p in projects_out)} database(s)",
        f"{active_locks} active lock(s)",
    ]

    registry_schema = None
    if paths.manifest and paths.config.is_file():
        try:
            data = json.loads(paths.config.read_text(encoding="utf-8"))
            registry_schema = data.get("schemaVersion")
        except Exception:
            pass

    return {
        "moduleId": paths.module_id,
        "status": status,
        "readiness": readiness,
        "timestamp": _utc_now_iso(),
        "summary": ", ".join(summary_parts),
        "details": {
            "configReadable": config_readable,
            "configSchemaVersion": registry_schema,
            "runtimeExists": runtime_exists,
            "adminExists": admin_exists,
            "cliExists": cli_exists,
            "dataStoreReachable": data_reachable,
            "indexerVersion": INDEXER_VERSION,
        },
        "projects": projects_out,
        "warnings": warnings,
        "errors": errors,
        "locks": locks,
    }


def run_export_registry(explicit_root: Optional[PathLike] = None) -> Dict[str, Any]:
    paths = get_paths(explicit_root)
    pm = ProjectManager(str(paths.config), str(paths.data_dir))

    fragment_projects = []
    for project in pm.get_all_projects():
        databases = []
        for db in project.get("databases", []):
            db_path = paths.data_dir / db["db_file"]
            idx = build_index_status(db_path)
            src = hub_source_fields(db)
            entry = {
                "infobaseId": db.get("id"),
                "name": db.get("name"),
                "type": db.get("type"),
                "sourcePath": src.get("sourcePath"),
                "sourceKind": src.get("sourceKind"),
                "platformVersion": db.get("platform_version"),
                "indexStatus": idx,
            }
            databases.append(entry)

        fragment_projects.append(
            {
                "projectId": project.get("id"),
                "clientId": project.get("clientId"),
                "name": project.get("name"),
                "active": project.get("active", False),
                "databases": databases,
            }
        )

    return {
        "schemaVersion": 1,
        "moduleId": paths.module_id,
        "moduleType": paths.module_type,
        "exportedAt": _utc_now_iso(),
        "registryFragment": {
            "projects": fragment_projects,
        },
    }


def run_apply_registry(
    input_path: PathLike,
    explicit_root: Optional[PathLike] = None,
    apply_mode: str = "patch",
) -> Dict[str, Any]:
    path = Path(input_path)
    data = read_json_file(path)
    return run_apply_registry_from_data(data, explicit_root=explicit_root, apply_mode=apply_mode)
