import sqlite3
import time
from pathlib import Path

from shared.xml_parser import ConfigurationParser
from shared.indexer_version import INDEXER_VERSION
from shared.db_build_state import mark_building, clear_building, tmp_db_path

from .file_ops import _remove_db_file, _remove_sqlite_sidecars, _replace_file_with_retry

_STAGE_LABELS = {
    'properties': 'Метаданные (свойства/реквизиты)',
    'modules': 'Модули (BSL)',
    'forms': 'Формы',
    'sections': 'Табличные части/регистры/перечисления',
    'flowchart': 'Маршруты БП (Flowchart)',
    'commands': 'Команды объектов',
    'subsystems': 'Подсистемы',
}


class DatabaseManagerCore:
    """Connection lifecycle, atomic build orchestration, and statistics."""

    def __init__(self, db_path):
        """
        Args:
            db_path: Путь к файлу базы данных
        """
        self.db_path = Path(db_path)
        self.conn = None

    def connect(self, journal_mode='WAL'):
        """Подключение к базе данных"""
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row
        if journal_mode:
            self.conn.execute(f'PRAGMA journal_mode={journal_mode}')
        return self.conn

    def close(self):
        """Закрытие подключения"""
        if self.conn:
            try:
                self.conn.execute('PRAGMA wal_checkpoint(TRUNCATE)')
            except sqlite3.Error:
                pass
            self.conn.close()
            self.conn = None
            _remove_sqlite_sidecars(self.db_path)

    @staticmethod
    def read_db_version(db_path):
        """
        Читает PRAGMA user_version из файла БД (только чтение).
        Returns:
            None если файла нет; иначе int (0 — база без записанной версии).
        """
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

    @staticmethod
    def build_from_xml_atomic(db_path, config_xml_path, progress_callback=None):
        """
        Сборка в .db.tmp с маркером .building и атомарной подменой foo.db.
        При ошибке старая база (если была) не трогается.
        """
        from . import DatabaseManager  # deferred: DatabaseManager composes this mixin in __init__.py

        db_path = Path(db_path)
        tmp_path = tmp_db_path(db_path)
        mark_building(db_path)
        db_manager = None
        succeeded = False
        try:
            _remove_db_file(tmp_path)
            db_manager = DatabaseManager(tmp_path)
            # DELETE вместо WAL: один файл, надёжнее os.replace на Windows.
            db_manager.connect(journal_mode='DELETE')
            db_manager.create_database(config_xml_path, progress_callback)
            db_manager.close()
            db_manager = None
            _replace_file_with_retry(tmp_path, db_path)
            succeeded = True
            return True
        finally:
            if db_manager is not None:
                try:
                    db_manager.close()
                except sqlite3.Error:
                    pass
            clear_building(db_path)
            if not succeeded:
                try:
                    _remove_db_file(tmp_path)
                except OSError:
                    pass

    def create_database(self, config_xml_path, progress_callback=None):
        """
        Создает базу данных из XML конфигурации

        Args:
            config_xml_path: Путь к Configuration.xml
            progress_callback: Функция для отчета о прогрессе (current, total, message)
        """
        t_start = time.perf_counter()

        # Парсим конфигурацию
        if progress_callback:
            progress_callback(0, 100, "Парсинг Configuration.xml...")

        t0 = time.perf_counter()
        parser = ConfigurationParser(config_xml_path)
        data = parser.parse()

        # Создаем структуру БД
        if progress_callback:
            progress_callback(10, 100, f"XML parse — {time.perf_counter() - t0:.1f} c — создание структуры БД...")
            for stage_name, seconds in sorted(parser.stage_seconds.items(), key=lambda kv: -kv[1]):
                label = _STAGE_LABELS.get(stage_name, stage_name)
                progress_callback(10, 100, f"    - {label}: {seconds:.1f} c")

        t0 = time.perf_counter()
        self._create_schema()

        # Заполняем данными
        if progress_callback:
            progress_callback(20, 100, f"Структура БД — {time.perf_counter() - t0:.1f} c — загрузка объектов...")

        self._insert_configuration(data, progress_callback)

        cursor = self.conn.cursor()
        cursor.execute(f'PRAGMA user_version = {INDEXER_VERSION}')
        self.conn.commit()

        if progress_callback:
            progress_callback(100, 100, f"Готово! Всего: {time.perf_counter() - t_start:.1f} c")

        return True

    def get_statistics(self):
        """Возвращает статистику по БД"""
        cursor = self.conn.cursor()

        stats = {}

        # Общее количество объектов
        cursor.execute('SELECT COUNT(*) FROM metadata_objects')
        stats['total_objects'] = cursor.fetchone()[0]

        # По типам
        cursor.execute('''
            SELECT object_type, COUNT(*) as count
            FROM metadata_objects
            GROUP BY object_type
            ORDER BY count DESC
        ''')
        stats['by_type'] = {row['object_type']: row['count'] for row in cursor.fetchall()}

        # Количество модулей
        cursor.execute('SELECT COUNT(*) FROM modules')
        stats['total_modules'] = cursor.fetchone()[0]

        # Количество атрибутов
        cursor.execute('SELECT COUNT(*) FROM attributes')
        stats['total_attributes'] = cursor.fetchone()[0]

        # Количество стандартных атрибутов
        cursor.execute('SELECT COUNT(*) FROM attributes WHERE is_standard = 1')
        stats['total_standard_attributes'] = cursor.fetchone()[0]

        # Количество кастомных атрибутов
        cursor.execute('SELECT COUNT(*) FROM attributes WHERE is_standard = 0')
        stats['total_custom_attributes'] = cursor.fetchone()[0]

        # Количество измерений регистров
        cursor.execute("SELECT COUNT(*) FROM attributes WHERE section = 'Dimension'")
        stats['total_dimensions'] = cursor.fetchone()[0]

        # Количество ресурсов регистров
        cursor.execute("SELECT COUNT(*) FROM attributes WHERE section = 'Resource'")
        stats['total_resources'] = cursor.fetchone()[0]

        # Количество колонок табличных частей
        cursor.execute('SELECT COUNT(*) FROM tabular_section_columns')
        stats['total_tabular_section_columns'] = cursor.fetchone()[0]

        # Количество значений перечислений
        cursor.execute('SELECT COUNT(*) FROM enum_values')
        stats['total_enum_values'] = cursor.fetchone()[0]

        # Функциональные опции (базы пересоздаются при изменении схемы)
        cursor.execute('SELECT COUNT(*) FROM functional_options')
        stats['total_functional_options'] = cursor.fetchone()[0]
        cursor.execute('SELECT COUNT(*) FROM fo_form_usage')
        stats['total_fo_form_usage'] = cursor.fetchone()[0]
        cursor.execute('SELECT COUNT(*) FROM fo_content_ref')
        stats['total_fo_content_ref'] = cursor.fetchone()[0]

        cursor.execute('SELECT COUNT(*) FROM scheduled_jobs')
        stats['total_scheduled_jobs'] = cursor.fetchone()[0]

        return stats
