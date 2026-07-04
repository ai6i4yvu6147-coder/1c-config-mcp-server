"""Apply-registry merge logic for config-mcp (Admin Hub protocol v1.0.2)."""

from __future__ import annotations

import copy
import re
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from shared.operations_log import log_operation_result
from shared.project_manager import ProjectManager
from shared.registry_ids import validate_hub_id
from shared.runtime_paths import get_paths
from shared.source_path import (
    SOURCE_KIND_ARCHIVE,
    SOURCE_KIND_DIRECTORY,
    apply_source_to_local,
)

PathLike = str | Path

EXPECTED_MODULE_ID = "1c-config-mcp"
EXPECTED_MODULE_TYPE = "config-mcp"
EXPECTED_SCHEMA_VERSION = 1


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _empty_result() -> Dict[str, Any]:
    return {
        "success": False,
        "appliedAt": _utc_now_iso(),
        "changes": {"created": 0, "updated": 0, "removed": 0, "skipped": 0},
        "warnings": [],
        "errors": [],
        "postApplyActions": {
            "restartRequired": False,
            "reloadRequired": False,
            "followUpOperations": [],
        },
    }


def _extract_fragment(input_data: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]], List[str]]:
    errors: List[str] = []
    if "registryFragment" in input_data:
        fragment = input_data["registryFragment"]
        if not isinstance(fragment, dict):
            errors.append("registryFragment must be an object")
            return None, errors
        return fragment, errors

    if "projects" in input_data:
        return input_data, errors

    errors.append("input must contain registryFragment or projects")
    return None, errors


def _validate_envelope(input_data: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    schema_version = input_data.get("schemaVersion")
    if schema_version is not None and schema_version != EXPECTED_SCHEMA_VERSION:
        errors.append(f"unsupported schemaVersion: {schema_version}")

    module_id = input_data.get("moduleId")
    if module_id is not None and module_id != EXPECTED_MODULE_ID:
        errors.append(f"moduleId mismatch: expected {EXPECTED_MODULE_ID}, got {module_id!r}")

    module_type = input_data.get("moduleType")
    if module_type is not None and module_type != EXPECTED_MODULE_TYPE:
        errors.append(f"moduleType mismatch: expected {EXPECTED_MODULE_TYPE}, got {module_type!r}")

    return errors


def _sanitize_db_file_name(name: str) -> str:
    cleaned = re.sub(r"[^\w\-]+", "_", name.strip(), flags=re.UNICODE)
    cleaned = cleaned.strip("_") or "database"
    return cleaned[:64]


def _generate_db_file(name: str, infobase_id: str, existing: Set[str]) -> str:
    base = _sanitize_db_file_name(name)
    suffix = infobase_id.replace("-", "")[:8]
    candidate = f"{base}_{suffix}.db"
    if candidate not in existing:
        return candidate
    n = 2
    while True:
        candidate = f"{base}_{suffix}_{n}.db"
        if candidate not in existing:
            return candidate
        n += 1


def _collect_db_files(projects: List[Dict[str, Any]]) -> Set[str]:
    files: Set[str] = set()
    for project in projects:
        for db in project.get("databases", []):
            db_file = db.get("db_file")
            if db_file:
                files.add(db_file)
    return files


def _source_changed(old_db: Dict[str, Any], new_source_path: Optional[str], new_source_kind: Optional[str]) -> bool:
    old_path = old_db.get("source_path")
    old_kind = old_db.get("source_kind")
    if old_path != new_source_path or old_kind != new_source_kind:
        return True
    if not old_path and not old_kind:
        old_xml = old_db.get("source_xml")
        if new_source_path and new_source_kind == SOURCE_KIND_DIRECTORY:
            return old_xml is not None
    return False


def _follow_up_rebuild(infobase_id: str) -> Dict[str, Any]:
    return {
        "moduleId": EXPECTED_MODULE_ID,
        "command": "rebuild-index",
        "args": {"db-id": infobase_id},
        "reason": "sourcePath changed after apply-registry",
        "blocking": False,
    }


def apply_registry_fragment(
    input_data: Dict[str, Any],
    pm: ProjectManager,
    apply_mode: str = "patch",
) -> Dict[str, Any]:
    """
    Merge Hub registry fragment into in-memory projects and persist atomically on success.

    Returns apply result dict per protocol v1.0.1 §9.2.
    """
    result = _empty_result()
    changes = result["changes"]
    warnings: List[str] = result["warnings"]
    errors: List[str] = result["errors"]
    follow_ups: List[Dict[str, Any]] = result["postApplyActions"]["followUpOperations"]

    envelope_errors = _validate_envelope(input_data)
    if envelope_errors:
        errors.extend(envelope_errors)
        return result

    fragment, parse_errors = _extract_fragment(input_data)
    if parse_errors:
        errors.extend(parse_errors)
        return result
    assert fragment is not None

    projects_in = fragment.get("projects")
    if projects_in is None:
        errors.append("registryFragment.projects is required")
        return result
    if not isinstance(projects_in, list):
        errors.append("registryFragment.projects must be an array")
        return result

    removed_ids = fragment.get("removedIds") or {}
    if not isinstance(removed_ids, dict):
        errors.append("removedIds must be an object")
        return result

    for project in projects_in:
        project_id = project.get("projectId")
        err = validate_hub_id("projectId", project_id)
        if err:
            errors.append(err)
            continue

        client_id = project.get("clientId")
        if client_id is not None:
            err = validate_hub_id("clientId", client_id)
            if err:
                errors.append(err)
                continue

        for db in project.get("databases", []):
            infobase_id = db.get("infobaseId")
            err = validate_hub_id("infobaseId", infobase_id)
            if err:
                errors.append(err)
                continue

            source_kind = db.get("sourceKind")
            if source_kind is not None and source_kind not in (SOURCE_KIND_DIRECTORY, SOURCE_KIND_ARCHIVE):
                errors.append(f"unknown sourceKind for infobaseId {infobase_id}: {source_kind!r}")

    if errors:
        return result

    working = copy.deepcopy(pm.projects)
    projects_list: List[Dict[str, Any]] = working.setdefault("projects", [])
    db_files = _collect_db_files(projects_list)

    project_index = {p["id"]: p for p in projects_list}
    fragment_project_ids: Set[str] = set()
    fragment_infobase_ids: Set[str] = set()

    for hub_project in projects_in:
        project_id = hub_project["projectId"]
        fragment_project_ids.add(project_id)

        existing_project = project_index.get(project_id)
        project_created = existing_project is None

        if project_created:
            existing_project = {
                "id": project_id,
                "name": hub_project.get("name") or "Unnamed",
                "active": bool(hub_project.get("active", False)),
                "databases": [],
            }
            if hub_project.get("clientId"):
                existing_project["clientId"] = hub_project["clientId"]
            projects_list.append(existing_project)
            project_index[project_id] = existing_project
            changes["created"] += 1
        else:
            project_updated = False
            if hub_project.get("name") is not None and existing_project.get("name") != hub_project["name"]:
                existing_project["name"] = hub_project["name"]
                project_updated = True
            if "active" in hub_project and existing_project.get("active") != hub_project["active"]:
                existing_project["active"] = bool(hub_project["active"])
                project_updated = True
            if hub_project.get("clientId") is not None and existing_project.get("clientId") != hub_project["clientId"]:
                existing_project["clientId"] = hub_project["clientId"]
                project_updated = True
            if project_updated:
                changes["updated"] += 1

        db_index = {d["id"]: d for d in existing_project.get("databases", [])}

        for hub_db in hub_project.get("databases", []):
            infobase_id = hub_db["infobaseId"]
            fragment_infobase_ids.add(infobase_id)

            source_path_in = hub_db.get("sourcePath")
            source_kind_in = hub_db.get("sourceKind")

            if source_kind_in == SOURCE_KIND_ARCHIVE:
                changes["skipped"] += 1
                warnings.append(
                    f"infobaseId {infobase_id}: archive not supported in Phase 2"
                )
                continue

            local_source_path: Optional[str] = None
            local_source_kind: Optional[str] = None
            local_source_xml: Optional[str] = None

            if source_path_in is not None or source_kind_in is not None:
                if source_kind_in is None:
                    errors.append(f"infobaseId {infobase_id}: sourceKind is required when sourcePath is set")
                    continue
                if source_path_in is None:
                    errors.append(f"infobaseId {infobase_id}: sourcePath is required when sourceKind is set")
                    continue

                local_source_path, local_source_kind, local_source_xml, src_warning = apply_source_to_local(
                    source_path_in, source_kind_in
                )
                if src_warning:
                    warnings.append(f"infobaseId {infobase_id}: {src_warning}")

                if source_kind_in == SOURCE_KIND_DIRECTORY and local_source_xml is None:
                    changes["skipped"] += 1
                    continue

            existing_db = db_index.get(infobase_id)
            db_created = existing_db is None

            if db_created:
                db_name = hub_db.get("name") or "Unnamed"
                db_type = hub_db.get("type") or "base"
                db_file = _generate_db_file(db_name, infobase_id, db_files)
                db_files.add(db_file)

                new_db: Dict[str, Any] = {
                    "id": infobase_id,
                    "name": db_name,
                    "type": db_type,
                    "db_file": db_file,
                }
                if local_source_path is not None:
                    new_db["source_path"] = local_source_path
                    new_db["source_kind"] = local_source_kind
                if local_source_xml is not None:
                    new_db["source_xml"] = local_source_xml
                if hub_db.get("platformVersion") is not None:
                    new_db["platform_version"] = hub_db["platformVersion"]

                existing_project.setdefault("databases", []).append(new_db)
                db_index[infobase_id] = new_db
                changes["created"] += 1
                if local_source_path and local_source_kind:
                    follow_ups.append(_follow_up_rebuild(infobase_id))
                continue

            db_updated = False
            if hub_db.get("name") is not None and existing_db.get("name") != hub_db["name"]:
                existing_db["name"] = hub_db["name"]
                db_updated = True
            if hub_db.get("type") is not None and existing_db.get("type") != hub_db["type"]:
                existing_db["type"] = hub_db["type"]
                db_updated = True
            if hub_db.get("platformVersion") is not None and existing_db.get("platform_version") != hub_db["platformVersion"]:
                existing_db["platform_version"] = hub_db["platformVersion"]
                db_updated = True

            source_changed = False
            if local_source_path is not None and local_source_kind is not None:
                source_changed = _source_changed(existing_db, local_source_path, local_source_kind)
                existing_db["source_path"] = local_source_path
                existing_db["source_kind"] = local_source_kind
                if local_source_xml is not None:
                    existing_db["source_xml"] = local_source_xml
                elif "source_xml" in existing_db and local_source_xml is None:
                    pass
                db_updated = True

            if db_updated:
                changes["updated"] += 1
            if source_changed:
                follow_ups.append(_follow_up_rebuild(infobase_id))

    if errors:
        result["success"] = False
        return result

    removed_project_ids = removed_ids.get("projectIds") or []
    removed_infobase_ids = removed_ids.get("infobaseIds") or []

    for pid in removed_project_ids:
        err = validate_hub_id("removedIds.projectIds", pid)
        if err:
            errors.append(err)
    for iid in removed_infobase_ids:
        err = validate_hub_id("removedIds.infobaseIds", iid)
        if err:
            errors.append(err)

    if errors:
        return result

    for pid in removed_project_ids:
        before = len(projects_list)
        projects_list[:] = [p for p in projects_list if p.get("id") != pid]
        if len(projects_list) < before:
            changes["removed"] += 1
            project_index.pop(pid, None)

    for iid in removed_infobase_ids:
        for project in projects_list:
            before = len(project.get("databases", []))
            project["databases"] = [d for d in project.get("databases", []) if d.get("id") != iid]
            if len(project["databases"]) < before:
                changes["removed"] += 1

    if apply_mode == "snapshot":
        for project in list(projects_list):
            pid = project.get("id")
            if pid not in fragment_project_ids:
                projects_list.remove(project)
                changes["removed"] += 1
                continue
            for db in list(project.get("databases", [])):
                if db.get("id") not in fragment_infobase_ids:
                    project["databases"].remove(db)
                    changes["removed"] += 1

    original = copy.deepcopy(pm.projects)
    pm.projects = working
    try:
        pm.save_projects_atomic()
    except Exception:
        pm.projects = original
        raise

    result["success"] = True
    result["postApplyActions"]["reloadRequired"] = True
    return result


def run_apply_registry_from_data(
    input_data: Dict[str, Any],
    explicit_root: Optional[PathLike] = None,
    apply_mode: str = "patch",
) -> Dict[str, Any]:
    paths = get_paths(explicit_root)
    pm = ProjectManager(str(paths.config), str(paths.data_dir))
    operation_run_id = str(uuid.uuid4())
    started = time.perf_counter()
    result = apply_registry_fragment(input_data, pm, apply_mode=apply_mode)
    result["operationRunId"] = operation_run_id
    result["durationMs"] = int((time.perf_counter() - started) * 1000)
    log_operation_result(paths.operations_log, result)
    return result
