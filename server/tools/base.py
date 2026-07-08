import os
import sqlite3
from pathlib import Path
from typing import Optional

from shared.project_manager import ProjectManager
from shared.indexer_version import INDEXER_VERSION
from shared.index_status import read_db_last_updated_at
from shared.db_build_state import is_building as _is_db_updating
from server.role_db import read_index_metadata


def _read_db_user_version(db_path: str) -> Optional[int]:
    """PRAGMA user_version из файла .db (только чтение). None — файла нет."""
    p = Path(db_path)
    if not p.exists():
        return None
    uri = p.resolve().as_uri() + '?mode=ro'
    conn = sqlite3.connect(uri, uri=True)
    try:
        row = conn.execute('PRAGMA user_version').fetchone()
        return int(row[0]) if row is not None else 0
    finally:
        conn.close()


def _is_db_outdated(db_path: str) -> bool:
    """True если базы нет, user_version == 0 или меньше ожидаемого INDEXER_VERSION."""
    ver = _read_db_user_version(db_path)
    if ver is None:
        return True
    if ver == 0:
        return True
    return ver < INDEXER_VERSION


def _read_db_extension_purpose(db_path: str) -> str:
    """Read extension_purpose from index_metadata (empty for base configs)."""
    p = Path(db_path)
    if not p.exists():
        return ''
    uri = p.resolve().as_uri() + '?mode=ro'
    conn = sqlite3.connect(uri, uri=True)
    try:
        meta = read_index_metadata(conn.cursor())
        return meta.get('extension_purpose') or ''
    except sqlite3.Error:
        return ''
    finally:
        conn.close()


class BaseTools:
    """Connection lifecycle, active-database resolution, and project-filter validation."""

    def __init__(self, projects_file=None, databases_dir=None):
        """
        Args:
            projects_file: Путь к projects.json (если None - автоопределение)
            databases_dir: Путь к папке databases (если None - автоопределение)
        """
        # Автоопределение путей если не указаны
        if projects_file is None or databases_dir is None:
            from shared.runtime_paths import get_paths
            paths = get_paths()
            if projects_file is None:
                projects_file = paths.config
            if databases_dir is None:
                databases_dir = paths.data_dir

        self.pm = ProjectManager(str(projects_file), str(databases_dir))
        self.connections = {}
        self._connection_mtime = {}

    def _get_active_databases(self, project_filter=None, include_outdated: bool = False):
        """
        Получить список активных БД с фильтрацией

        Args:
            project_filter: Имя проекта для фильтрации или None для всех
            include_outdated: Включать ли устаревшие базы (user_version < INDEXER_VERSION).

        Returns:
            List of database info dicts
        """
        all_dbs = self.pm.get_active_databases()

        if project_filter:
            all_dbs = [db for db in all_dbs if db['project_name'].lower() == project_filter.lower()]

        # По умолчанию НЕ используем устаревшие и обновляющиеся базы.
        if not include_outdated:
            all_dbs = [
                db for db in all_dbs
                if not _is_db_outdated(db['db_path']) and not _is_db_updating(db['db_path'])
            ]

        return all_dbs

    def _get_connection(self, db_path):
        """Получить подключение к БД (только чтение, с кэшированием). При изменении mtime — пересоздание."""
        p = Path(db_path)
        if not p.exists():
            raise FileNotFoundError(f"Database file not found: {db_path}")
        try:
            current_mtime = os.path.getmtime(db_path)
        except OSError:
            current_mtime = 0
        if db_path in self.connections:
            if self._connection_mtime.get(db_path) != current_mtime:
                self.connections[db_path].close()
                del self.connections[db_path]
                del self._connection_mtime[db_path]
        if db_path not in self.connections:
            uri = p.resolve().as_uri() + '?mode=ro'
            conn = sqlite3.connect(uri, uri=True)
            conn.row_factory = sqlite3.Row
            self.connections[db_path] = conn
            self._connection_mtime[db_path] = current_mtime
        return self.connections[db_path]

    def close_all(self):
        """Закрыть все подключения"""
        for conn in self.connections.values():
            conn.close()
        self.connections.clear()
        self._connection_mtime.clear()

    def _require_project_filter(self, project_filter):
        """Требует указания project_filter. Вызвать в начале tools, где фильтр обязателен."""
        if not project_filter or not str(project_filter).strip():
            raise ValueError(
                "project_filter is required. Use active_databases to get the list of projects and databases."
            )

    def _get_active_project_names(self):
        """Список имён активных проектов (для сообщений об ошибках)."""
        return sorted(set(db['project_name'] for db in self.pm.get_active_databases()))

    def _require_project_exists(self, project_filter, databases):
        """Если передан project_filter, но список баз пуст — явная ошибка с подсказкой доступных проектов."""
        if project_filter and not databases:
            names = self._get_active_project_names()
            available = ", ".join(names) if names else "нет"
            raise ValueError(
                f'Проект с именем "{project_filter}" не найден. '
                f'Доступные проекты: {available}. Используйте active_databases для полного списка.'
            )

    def list_active_databases(self):
        """
        Возвращает список активных проектов и их баз (для выбора project_filter и extension_filter).
        """
        all_dbs = self.pm.get_active_databases()
        by_project = {}
        for db in all_dbs:
            pname = db['project_name']
            if pname not in by_project:
                by_project[pname] = {'name': pname, 'databases': []}
            by_project[pname]['databases'].append({
                'name': db['db_name'],
                'type': db['db_type'],
                'is_outdated': _is_db_outdated(db['db_path']),
                'is_updating': _is_db_updating(db['db_path']),
                'last_updated_at': read_db_last_updated_at(db['db_path']),
                'extension_purpose': _read_db_extension_purpose(db['db_path']),
            })
        return {'projects': list(by_project.values())}
