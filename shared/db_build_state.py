"""Маркер сборки SQLite-базы: координация admin_tool и MCP во время пересоздания индекса."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Union

PathLike = Union[str, Path]

MARKER_SUFFIX = '.building'
TMP_SUFFIX = '.tmp'


def building_marker_path(db_path: PathLike) -> Path:
    """Путь к sidecar-файлу маркера: foo.db → foo.db.building."""
    p = Path(db_path)
    return p.parent / (p.name + MARKER_SUFFIX)


def tmp_db_path(db_path: PathLike) -> Path:
    """Путь к временному файлу сборки: foo.db → foo.db.tmp."""
    p = Path(db_path)
    return p.parent / (p.name + TMP_SUFFIX)


def is_building(db_path: PathLike) -> bool:
    """True, если для базы активен маркер сборки."""
    return building_marker_path(db_path).exists()


def read_building_info(db_path: PathLike) -> Optional[Dict[str, Any]]:
    """Метаданные маркера или None, если маркера нет."""
    marker = building_marker_path(db_path)
    if not marker.exists():
        return None
    try:
        return json.loads(marker.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError):
        return {}


def mark_building(db_path: PathLike) -> None:
    """Создать маркер «идёт сборка» перед началом create_database."""
    marker = building_marker_path(db_path)
    payload = {
        'db_path': str(Path(db_path).resolve()),
        'started_at': datetime.now(timezone.utc).isoformat(),
        'pid': os.getpid(),
    }
    marker.write_text(json.dumps(payload, ensure_ascii=False), encoding='utf-8')


def clear_building(db_path: PathLike) -> None:
    """Удалить маркер сборки (успех, ошибка или ручной сброс)."""
    marker = building_marker_path(db_path)
    if marker.exists():
        marker.unlink()


def _pid_alive(pid: Any) -> bool:
    if pid is None:
        return False
    try:
        os.kill(int(pid), 0)
    except (OSError, ValueError, TypeError):
        return False
    return True


def is_stale_building(db_path: PathLike) -> bool:
    """Маркер есть, но процесс-сборщик не жив и нет незавершённого .tmp."""
    if not is_building(db_path):
        return False
    info = read_building_info(db_path)
    if info and _pid_alive(info.get('pid')):
        return False
    return not tmp_db_path(db_path).exists()


def reconcile_building_markers(databases_dir: PathLike) -> None:
    """
    При старте admin tool: убрать зависшие маркеры (процесс мёртв, .tmp нет)
    и удалить осиротевшие .db.tmp (не трогать .tmp активной сборки).
    """
    root = Path(databases_dir)
    if not root.is_dir():
        return

    protected_tmp = set()
    for marker in root.glob('*.db' + MARKER_SUFFIX):
        db_name = marker.name[: -len(MARKER_SUFFIX)]
        db_path = root / db_name
        info = None
        try:
            info = json.loads(marker.read_text(encoding='utf-8'))
        except (OSError, json.JSONDecodeError):
            pass
        tmp = tmp_db_path(db_path)
        pid_alive = info and _pid_alive(info.get('pid'))
        if pid_alive and tmp.exists():
            protected_tmp.add(tmp.resolve())
        tmp_exists = tmp.exists()
        if not pid_alive and not tmp_exists:
            marker.unlink(missing_ok=True)

    for tmp in root.glob('*.db' + TMP_SUFFIX):
        if tmp.resolve() in protected_tmp:
            continue
        tmp.unlink(missing_ok=True)
        for suffix in ('-wal', '-shm'):
            sidecar = tmp.parent / (tmp.name + suffix)
            sidecar.unlink(missing_ok=True)
