"""Source path semantics for config-mcp (Admin Hub protocol v1.0.2)."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, Optional

SOURCE_KIND_DIRECTORY = "directory"
SOURCE_KIND_ARCHIVE = "archive"


def resolve_configuration_xml(source_path: Path, source_kind: str) -> Optional[Path]:
    """Resolve Configuration.xml path from sourcePath + sourceKind."""
    if source_kind == SOURCE_KIND_ARCHIVE:
        return None

    if source_kind != SOURCE_KIND_DIRECTORY:
        return None

    path = Path(source_path)
    primary = path / "Configuration.xml"
    if primary.is_file():
        return primary

    fallback = path / "Ext" / "Configuration.xml"
    if fallback.is_file():
        return fallback

    return None


def normalize_db_record(db: dict) -> dict:
    """Return db view with source_path/source_kind filled from legacy source_xml if needed."""
    out = deepcopy(db)
    source_path = out.get("source_path")
    source_kind = out.get("source_kind")
    source_xml = out.get("source_xml")

    if source_path and source_kind:
        return out

    if source_xml:
        xml_path = Path(source_xml)
        out.setdefault("source_path", str(xml_path.parent))
        out.setdefault("source_kind", SOURCE_KIND_DIRECTORY)

    return out


def get_effective_config_xml(db: dict) -> Optional[str]:
    """Path to Configuration.xml for indexing, from canonical or legacy fields."""
    normalized = normalize_db_record(db)
    source_path = normalized.get("source_path")
    source_kind = normalized.get("source_kind")

    if source_path and source_kind:
        resolved = resolve_configuration_xml(Path(source_path), source_kind)
        if resolved is not None:
            return str(resolved)
        if source_kind == SOURCE_KIND_DIRECTORY and normalized.get("source_xml"):
            return normalized.get("source_xml")
        return None

    source_xml = normalized.get("source_xml")
    return source_xml if source_xml else None


def source_exists(db: dict) -> bool:
    """True if source directory/archive path or resolved Configuration.xml exists."""
    normalized = normalize_db_record(db)
    source_path = normalized.get("source_path")
    source_kind = normalized.get("source_kind")

    if source_path and source_kind == SOURCE_KIND_DIRECTORY:
        path = Path(source_path)
        if path.is_dir():
            resolved = resolve_configuration_xml(path, source_kind)
            if resolved is not None:
                return True
        effective = get_effective_config_xml(normalized)
        return bool(effective and Path(effective).is_file())

    if source_path and source_kind == SOURCE_KIND_ARCHIVE:
        return Path(source_path).is_file()

    source_xml = normalized.get("source_xml")
    return bool(source_xml and Path(source_xml).is_file())


def hub_source_fields(db: dict) -> Dict[str, Any]:
    """Export-oriented sourcePath/sourceKind for Hub protocol."""
    normalized = normalize_db_record(db)
    source_path = normalized.get("source_path")
    source_kind = normalized.get("source_kind")

    if source_path and source_kind:
        return {"sourcePath": source_path, "sourceKind": source_kind}

    source_xml = normalized.get("source_xml")
    if source_xml:
        return {
            "sourcePath": str(Path(source_xml).parent),
            "sourceKind": SOURCE_KIND_DIRECTORY,
        }

    return {"sourcePath": None, "sourceKind": None}


def apply_source_to_local(
    source_path: str,
    source_kind: str,
) -> tuple[Optional[str], Optional[str], Optional[str], Optional[str]]:
    """
    Map Hub source fields to local storage.

    Returns (source_path, source_kind, source_xml, warning).
    warning is set when path cannot be resolved or archive is unsupported.
    """
    if source_kind == SOURCE_KIND_ARCHIVE:
        return None, None, None, "archive not supported in Phase 2"

    if source_kind != SOURCE_KIND_DIRECTORY:
        return None, None, None, f"unknown sourceKind: {source_kind}"

    path = Path(source_path)
    resolved = resolve_configuration_xml(path, source_kind)
    source_xml = str(resolved) if resolved is not None else None

    warning = None
    if not path.is_dir():
        warning = f"sourcePath directory not found: {source_path}"
    elif resolved is None:
        warning = f"Configuration.xml not found under: {source_path}"

    return source_path, source_kind, source_xml, warning
