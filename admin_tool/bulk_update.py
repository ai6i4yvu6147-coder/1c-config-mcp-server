"""Массовое обновление индексов (backlog `gui-bulk-update`).

Здесь только отбор целей и оркестрация прогона — без Tk, чтобы логику можно было
покрыть тестами. GUI (`admin_tool/gui_v2.py`) поверх этого рисует прогресс и лог.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, List, Optional

from admin_tool.db_manager import DatabaseManager, format_build_error
from shared.db_build_state import is_building, is_stale_building
from shared.indexer_version import INDEXER_VERSION
from shared.source_path import get_effective_config_xml, source_exists

#: Обновлять только базы, чья версия формата индекса не равна текущей (плюс отсутствующие файлы).
SCOPE_OUTDATED = 'outdated'
#: Обновлять все базы в области видимости.
SCOPE_ALL = 'all'


@dataclass
class BulkTarget:
    """Одна база в плане массового обновления.

    `skip_reason is None` — база будет пересобрана; иначе причина пропуска показывается
    в плане и в итоговой сводке (молча базы не выпадают)."""

    project_id: str
    project_name: str
    db_id: str
    db_name: str
    db_file: str
    db_path: Path
    config_xml: Optional[str]
    db_version: Optional[int]
    skip_reason: Optional[str] = None

    @property
    def label(self) -> str:
        return f"{self.project_name} / {self.db_name}"

    @property
    def is_actionable(self) -> bool:
        return self.skip_reason is None


@dataclass
class BulkResult:
    """Итог прогона: по одной записи на попытку сборки плюс агрегаты."""

    succeeded: int = 0
    failed: int = 0
    stopped_early: bool = False
    failures: List[tuple] = field(default_factory=list)  # (label, текст ошибки)


def _up_to_date_label(version: Optional[int]) -> str:
    return f"актуальна (v{version})"


def collect_bulk_targets(
    pm,
    db_dir,
    project_id: Optional[str] = None,
    scope: str = SCOPE_OUTDATED,
) -> List[BulkTarget]:
    """План массового обновления: все базы области с отметкой «пересобрать / пропустить».

    Args:
        pm: `ProjectManager`.
        db_dir: каталог с файлами `.db`.
        project_id: ограничить одним проектом; `None` — все проекты.
        scope: `SCOPE_OUTDATED` (по умолчанию) или `SCOPE_ALL`.

    Возвращает цели в порядке обхода проектов, включая пропускаемые.
    """
    db_dir = Path(db_dir)
    projects = pm.get_all_projects()
    if project_id is not None:
        projects = [p for p in projects if p['id'] == project_id]

    targets: List[BulkTarget] = []
    for project in projects:
        for db in project.get('databases', []):
            db_path = db_dir / db['db_file']
            version = DatabaseManager.read_db_version(db_path)
            config_xml = get_effective_config_xml(db) if source_exists(db) else None

            target = BulkTarget(
                project_id=project['id'],
                project_name=project['name'],
                db_id=db['id'],
                db_name=db['name'],
                db_file=db['db_file'],
                db_path=db_path,
                config_xml=config_xml,
                db_version=version,
            )

            if version is not None and version > INDEXER_VERSION:
                # Пересборка старым админ-инструментом понизила бы формат индекса —
                # это всегда явное решение пользователя, не побочный эффект массовой операции.
                target.skip_reason = f"новее ПО (v{version} > v{INDEXER_VERSION}) — обновите админ-инструмент"
            elif scope == SCOPE_OUTDATED and version == INDEXER_VERSION:
                target.skip_reason = _up_to_date_label(version)
            elif config_xml is None:
                target.skip_reason = "источник не найден — обновите базу вручную и укажите XML"
            elif is_building(db_path) and not is_stale_building(db_path):
                target.skip_reason = "сборка уже идёт"

            targets.append(target)

    return targets


def run_bulk_update(
    targets: List[BulkTarget],
    on_db_start: Optional[Callable[[int, int, BulkTarget], None]] = None,
    on_progress: Optional[Callable[[BulkTarget, int, int, str, bool], None]] = None,
    on_db_finish: Optional[Callable[[BulkTarget, bool, Optional[str]], None]] = None,
    should_stop: Optional[Callable[[], bool]] = None,
) -> BulkResult:
    """Последовательно пересобирает базы из плана.

    Ошибка одной базы не прерывает прогон: она попадает в `BulkResult.failures`, и
    обход продолжается — иначе долгий батч пришлось бы запускать заново с начала.
    `should_stop` проверяется между базами (сборка одной базы не прерывается —
    кооперативная отмена внутри сборки это отдельная задача `gui-cancel-build`).
    """
    actionable = [t for t in targets if t.is_actionable]
    result = BulkResult()

    for index, target in enumerate(actionable, start=1):
        if should_stop is not None and should_stop():
            result.stopped_early = True
            break

        if on_db_start:
            on_db_start(index, len(actionable), target)

        def progress_callback(current, total, message, replace_last=False, _t=target):
            if on_progress:
                on_progress(_t, current, total, message, replace_last)

        try:
            DatabaseManager.build_from_xml_atomic(
                target.db_path, target.config_xml, progress_callback=progress_callback
            )
            result.succeeded += 1
            if on_db_finish:
                on_db_finish(target, True, None)
        except Exception as exc:  # noqa: BLE001 — сводка по всем базам важнее падения на первой
            error_text = format_build_error(exc)
            result.failed += 1
            result.failures.append((target.label, error_text))
            if on_db_finish:
                on_db_finish(target, False, error_text)

    return result
