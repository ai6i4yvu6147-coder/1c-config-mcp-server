import os
import sqlite3
import json
import re
import time
from pathlib import Path
import sys

# Добавляем корневую папку проекта в путь
sys.path.insert(0, str(Path(__file__).parent.parent))

from shared.xml_parser import ConfigurationParser
from shared.indexer_version import INDEXER_VERSION
from shared.db_build_state import mark_building, clear_building, tmp_db_path
from shared.metadata_type_resolver import MetadataTypeResolver

_SQLITE_SIDECAR_SUFFIXES = ('-wal', '-shm')


def _sqlite_sidecar_paths(db_path):
    p = Path(db_path)
    return [p.parent / (p.name + suffix) for suffix in _SQLITE_SIDECAR_SUFFIXES]


def _remove_sqlite_sidecars(db_path):
    for sidecar in _sqlite_sidecar_paths(db_path):
        sidecar.unlink(missing_ok=True)


def _unlink_with_retry(path, retries=10, delay=0.05):
    """Удаление файла с повторами (Windows может держать handle после close SQLite)."""
    p = Path(path)
    if not p.exists():
        return
    last_err = None
    for attempt in range(retries):
        try:
            p.unlink()
            return
        except OSError as exc:
            last_err = exc
            retryable = (
                getattr(exc, 'winerror', None) in (32, 5)
                or exc.errno in (16, 26)
            )
            if not retryable:
                raise
            if attempt + 1 < retries:
                time.sleep(delay)
    raise last_err


def _remove_db_file(db_path):
    """Удалить .db и sidecar-файлы SQLite (-wal, -shm)."""
    _remove_sqlite_sidecars(db_path)
    _unlink_with_retry(db_path)


def _replace_file_with_retry(src, dst, retries=10, delay=0.05):
    """os.replace с повторами: на Windows файл может освобождаться с задержкой."""
    last_err = None
    for attempt in range(retries):
        try:
            os.replace(src, dst)
            return
        except OSError as exc:
            last_err = exc
            retryable = (
                getattr(exc, 'winerror', None) in (32, 5)
                or exc.errno in (16, 26)
            )
            if not retryable:
                raise
            if attempt + 1 < retries:
                time.sleep(delay)
    raise last_err


def format_build_error(exc):
    """Вернуть исходную ошибку сборки, если WinError 32 при очистке .tmp маскирует её."""
    root = exc.__cause__
    if root is None and exc.__context__ is not None and exc.__context__ is not exc:
        root = exc.__context__
    if root is not None and root is not exc:
        cleanup_hint = str(exc)
        if 'WinError 32' in cleanup_hint or 'WinError 5' in cleanup_hint:
            return (
                f'{root}\n\n'
                f'Дополнительно при освобождении временного файла: {cleanup_hint}'
            )
        return f'{root}\n\nПри очистке: {cleanup_hint}'
    return str(exc)


def _strip_bsl_comment_line(line):
    """Снимает префикс // с строки документирующего комментария BSL."""
    stripped = line.strip()
    if stripped.startswith('//'):
        text = stripped[2:]
        if text.startswith(' '):
            text = text[1:]
        return text
    return stripped


def _parse_module_procedures(code):
    """
    Парсит код модуля 1С, возвращает список процедур/функций для таблицы module_procedures.
    Каждый элемент: name, proc_type, start_line, end_line, params, is_export, comment,
    execution_context, extension_call_type.
    start_line — первая строка для среза (включая //-комментарии и &-директивы над процедурой); 1-based.
    comment — многострочный текст документирующих //-строк над процедурой (без префикса //).
    execution_context и extension_call_type определяются по &-строкам в префиксе.
    Поддерживаются многострочные объявления (закрывающая скобка ) и Экспорт на следующих строках).
    """
    lines = code.split('\n')
    pattern = re.compile(
        r'^\s*(Процедура|Функция)\s+([А-Яа-яA-Za-z0-9_]+)\s*\((.*?)\)\s*(Экспорт)?\s*$',
        re.IGNORECASE
    )
    # Начало объявления без требования закрывающей ) на той же строке (для многострочных сигнатур)
    start_only_pattern = re.compile(
        r'^\s*(Процедура|Функция)\s+([А-Яа-яA-Za-z0-9_]+)\s*\(',
        re.IGNORECASE
    )
    directive_pattern = re.compile(
        r'^\s*&(НаКлиентеНаСервереБезКонтекста|НаСервереБезКонтекста|НаКлиенте|НаСервере|'
        r'AtClientAtServerNoContext|AtServerNoContext|AtClient|AtServer)\s*$',
        re.IGNORECASE
    )
    # Аннотации расширений: с параметром &Перед("ИмяПроцедуры") или без (форма модуля)
    extension_patterns = [
        (re.compile(r'^\s*&ИзменениеИКонтроль\s*(\([^)]*\))?\s*$', re.IGNORECASE), 'ChangeAndControl'),
        (re.compile(r'^\s*&Вместо\s*(\([^)]*\))?\s*$', re.IGNORECASE), 'Instead'),
        (re.compile(r'^\s*&После\s*(\([^)]*\))?\s*$', re.IGNORECASE), 'After'),
        (re.compile(r'^\s*&Перед\s*(\([^)]*\))?\s*$', re.IGNORECASE), 'Before'),
    ]
    end_pattern = re.compile(r'^\s*(КонецФункции|КонецПроцедуры|EndFunction|EndProcedure)\s*$', re.IGNORECASE)

    def directive_to_context(line):
        """Возвращает директиву как есть (без нормализации)."""
        if not line:
            return None
        stripped = line.strip()
        m = re.match(r'^&([А-Яа-яA-Za-z]+)', stripped)
        if m and directive_pattern.match(stripped):
            return m.group(1)
        return None

    def line_to_extension_call_type(stripped):
        for pat, value in extension_patterns:
            if pat.match(stripped):
                return value
        return None

    def collect_procedure_prefix_above(proc_line_index):
        """Собирает //-комментарии и &-директивы непосредственно над объявлением процедуры."""
        indices = []
        j = proc_line_index - 1
        while j >= 0:
            stripped = lines[j].strip()
            if stripped.startswith('//'):
                indices.append(j)
                j -= 1
            elif stripped.startswith('&') and len(stripped) > 1:
                indices.append(j)
                j -= 1
            elif stripped == '':
                break
            else:
                break
        indices.reverse()
        comment_indices = [idx for idx in indices if lines[idx].strip().startswith('//')]
        directive_indices = [idx for idx in indices if lines[idx].strip().startswith('&')]
        return comment_indices, directive_indices, indices

    def prefix_info(proc_line_index, default_start_line):
        comment_indices, directive_indices, all_indices = collect_procedure_prefix_above(proc_line_index)
        execution_context = None
        extension_call_type = None
        for idx in reversed(directive_indices):
            stripped = lines[idx].strip()
            if execution_context is None:
                execution_context = directive_to_context(stripped)
            if extension_call_type is None:
                extension_call_type = line_to_extension_call_type(stripped)
        start_line = (all_indices[0] + 1) if all_indices else default_start_line
        comment = (
            '\n'.join(_strip_bsl_comment_line(lines[idx]) for idx in comment_indices)
            if comment_indices else ''
        )
        return start_line, comment, execution_context, extension_call_type

    result = []
    i = 0
    while i < len(lines):
        match = pattern.match(lines[i])
        if match:
            line_num = i + 1
            proc_type = match.group(1)
            name = match.group(2)
            params = (match.group(3) or '').strip() or '(без параметров)'
            is_export = bool(match.group(4))
            start_line, comment, execution_context, extension_call_type = prefix_info(i, line_num)
            end_line = None
            for j in range(i + 1, len(lines)):
                if end_pattern.match(lines[j]):
                    end_line = j + 1
                    break
            result.append({
                'name': name,
                'proc_type': proc_type,
                'start_line': start_line,
                'end_line': end_line,
                'params': params,
                'is_export': 1 if is_export else 0,
                'comment': comment,
                'execution_context': execution_context,
                'extension_call_type': extension_call_type,
            })
            if end_line is not None:
                i = end_line
            else:
                i = len(lines)
        else:
            start_match = start_only_pattern.match(lines[i])
            if start_match and ')' not in lines[i]:
                # Многострочное объявление: читаем до строки с )
                proc_type = start_match.group(1)
                name = start_match.group(2)
                j = i + 1
                while j < len(lines) and ')' not in lines[j]:
                    j += 1
                if j >= len(lines):
                    i += 1
                    continue
                closing_line = lines[j]
                is_export = bool(re.search(r'\bЭкспорт\b', closing_line, re.IGNORECASE))
                params = '(многострочные)'
                start_line, comment, execution_context, extension_call_type = prefix_info(i, i + 1)
                end_line = None
                for k in range(j + 1, len(lines)):
                    if end_pattern.match(lines[k]):
                        end_line = k + 1
                        break
                result.append({
                    'name': name,
                    'proc_type': proc_type,
                    'start_line': start_line,
                    'end_line': end_line,
                    'params': params,
                    'is_export': 1 if is_export else 0,
                    'comment': comment,
                    'execution_context': execution_context,
                    'extension_call_type': extension_call_type,
                })
                if end_line is not None:
                    i = end_line
                else:
                    i = len(lines)
            else:
                i += 1
    return result


class DatabaseManager:
    """Управление SQLite базой данных конфигурации"""
    
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
        # Парсим конфигурацию
        if progress_callback:
            progress_callback(0, 100, "Парсинг Configuration.xml...")
        
        parser = ConfigurationParser(config_xml_path)
        data = parser.parse()
        
        # Создаем структуру БД
        if progress_callback:
            progress_callback(10, 100, "Создание структуры БД...")
        
        self._create_schema()
        
        # Заполняем данными
        if progress_callback:
            progress_callback(20, 100, "Загрузка объектов...")
        
        self._insert_configuration(data, progress_callback)

        cursor = self.conn.cursor()
        cursor.execute(f'PRAGMA user_version = {INDEXER_VERSION}')
        self.conn.commit()
        
        if progress_callback:
            progress_callback(100, 100, "Готово!")
        
        return True
    
    def _create_schema(self):
        """Создает структуру таблиц"""
        cursor = self.conn.cursor()
        
        # Таблица объектов метаданных
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS metadata_objects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                uuid TEXT,
                object_type TEXT NOT NULL,
                name TEXT NOT NULL,
                synonym TEXT,
                comment TEXT,
                object_belonging TEXT,
                extended_configuration_object TEXT,
                object_kind TEXT NOT NULL DEFAULT 'ConfigObject',
                is_primitive INTEGER NOT NULL DEFAULT 0,
                base_type TEXT,
                qualifier_1 TEXT,
                qualifier_2 TEXT,
                qualifier_3 TEXT
            )
        ''')
        cursor.execute('''
            CREATE UNIQUE INDEX IF NOT EXISTS uq_metadata_objects_type_descriptor
            ON metadata_objects(object_kind, base_type, qualifier_1, qualifier_2, qualifier_3)
            WHERE object_kind = 'TypeDescriptor'
        ''')
        
        # Таблица форм
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS forms (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                object_id INTEGER NOT NULL,
                form_name TEXT NOT NULL,
                form_kind TEXT,
                uuid TEXT,
                properties_json TEXT,
                FOREIGN KEY (object_id) REFERENCES metadata_objects(id)
            )
        ''')
        
        # Таблица реквизитов форм
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS form_attributes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                form_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                title TEXT,
                is_main INTEGER DEFAULT 0,
                query_text TEXT,
                FOREIGN KEY (form_id) REFERENCES forms(id)
            )
        ''')

        # Колонки реквизитов форм (ValueTable / AdditionalColumns)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS form_attribute_columns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                form_attribute_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                title TEXT,
                table_context TEXT,
                FOREIGN KEY (form_attribute_id) REFERENCES form_attributes(id)
            )
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS ix_fac_form_attribute
            ON form_attribute_columns(form_attribute_id)
        ''')
        
        # Таблица команд форм
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS form_commands (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                form_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                title TEXT,
                action TEXT,
                shortcut TEXT,
                representation TEXT,
                FOREIGN KEY (form_id) REFERENCES forms(id)
            )
        ''')
        
        # Таблица событий формы
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS form_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                form_id INTEGER NOT NULL,
                event_name TEXT NOT NULL,
                handler TEXT NOT NULL,
                call_type TEXT,
                FOREIGN KEY (form_id) REFERENCES forms(id)
            )
        ''')
        
        # Таблица элементов UI
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS form_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                form_id INTEGER NOT NULL,
                parent_id INTEGER,
                name TEXT NOT NULL,
                item_type TEXT NOT NULL,
                data_path TEXT,
                title TEXT,
                visible INTEGER,
                enabled INTEGER,
                command_name TEXT,
                FOREIGN KEY (form_id) REFERENCES forms(id),
                FOREIGN KEY (parent_id) REFERENCES form_items(id)
            )
        ''')
        
        # Таблица событий элементов
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS form_item_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                item_id INTEGER NOT NULL,
                event_name TEXT NOT NULL,
                handler TEXT NOT NULL,
                FOREIGN KEY (item_id) REFERENCES form_items(id)
            )
        ''')
        
        # Таблица условного оформления
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS form_conditional_appearance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                form_id INTEGER NOT NULL,
                xml_data TEXT NOT NULL,
                FOREIGN KEY (form_id) REFERENCES forms(id)
            )
        ''')
        
        # Команды объекта метаданных (ChildObjects/Command в XML объекта)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS object_commands (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                object_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                synonym TEXT,
                uuid TEXT,
                object_belonging TEXT,
                extended_configuration_object TEXT,
                FOREIGN KEY (object_id) REFERENCES metadata_objects(id)
            )
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_object_commands_object_name
            ON object_commands(object_id, name)
        ''')

        # Таблица модулей (form_id для FormModule; command_id для CommandModule команды объекта)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS modules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                object_id INTEGER NOT NULL,
                form_id INTEGER,
                command_id INTEGER,
                module_type TEXT NOT NULL,
                code TEXT NOT NULL,
                FOREIGN KEY (object_id) REFERENCES metadata_objects(id),
                FOREIGN KEY (form_id) REFERENCES forms(id),
                FOREIGN KEY (command_id) REFERENCES object_commands(id)
            )
        ''')
        
        # Таблица процедур/функций модулей (индекс, код хранится в modules.code по start_line/end_line)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS module_procedures (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                module_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                proc_type TEXT NOT NULL,
                start_line INTEGER NOT NULL,
                end_line INTEGER,
                params TEXT,
                is_export INTEGER DEFAULT 0,
                execution_context TEXT,
                extension_call_type TEXT,
                comment TEXT,
                used_in_scheduled_job INTEGER DEFAULT 0,
                FOREIGN KEY (module_id) REFERENCES modules(id)
            )
        ''')
        
        # Таблица атрибутов объектов (стандартные + кастомные + измерения/ресурсы регистров)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS attributes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                object_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                title TEXT,
                comment TEXT,
                is_standard INTEGER DEFAULT 0,
                standard_type TEXT,
                section TEXT NOT NULL DEFAULT 'Attribute',
                FOREIGN KEY (object_id) REFERENCES metadata_objects(id)
            )
        ''')

        # Таблица табличных частей (нормализованная)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS tabular_sections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                object_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                title TEXT,
                comment TEXT,
                FOREIGN KEY (object_id) REFERENCES metadata_objects(id)
            )
        ''')
        
        # Таблица колонок табличных частей
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS tabular_section_columns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tabular_section_id INTEGER NOT NULL,
                column_name TEXT NOT NULL,
                title TEXT,
                comment TEXT,
                FOREIGN KEY (tabular_section_id) REFERENCES tabular_sections(id)
            )
        ''')

        # Нормализованные типы реквизитов и колонок ТЧ
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS metadata_type_slots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_table TEXT NOT NULL,
                source_row_id INTEGER NOT NULL,
                src_object_id INTEGER NOT NULL,
                object_id INTEGER NOT NULL,
                ordinal INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY (object_id) REFERENCES metadata_objects(id),
                FOREIGN KEY (src_object_id) REFERENCES metadata_objects(id)
            )
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS ix_mts_object ON metadata_type_slots(object_id)
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS ix_mts_src_object ON metadata_type_slots(src_object_id)
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS ix_mts_source ON metadata_type_slots(source_table, source_row_id)
        ''')

        # Таблица значений перечислений
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS enum_values (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                object_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                enum_order INTEGER,
                title TEXT,
                comment TEXT,
                object_belonging TEXT,
                extended_configuration_object TEXT,
                FOREIGN KEY (object_id) REFERENCES metadata_objects(id)
            )
        ''')

        # Точки маршрута бизнес-процессов (Flowchart.xml)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS bp_route_points (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                object_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                point_type TEXT NOT NULL,
                title TEXT,
                uuid TEXT,
                tab_order INTEGER,
                true_port INTEGER,
                false_port INTEGER,
                FOREIGN KEY (object_id) REFERENCES metadata_objects(id)
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS bp_route_transitions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                object_id INTEGER NOT NULL,
                from_point TEXT NOT NULL,
                to_point TEXT NOT NULL,
                from_port INTEGER,
                title TEXT,
                FOREIGN KEY (object_id) REFERENCES metadata_objects(id)
            )
        ''')

        # Таблица функциональных опций (свойства ФО; Content хранится в fo_content_ref)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS functional_options (
                object_id INTEGER NOT NULL PRIMARY KEY,
                location_constant TEXT,
                privileged_get_mode INTEGER,
                FOREIGN KEY (object_id) REFERENCES metadata_objects(id)
            )
        ''')

        # Регламентные задания (свойства из ScheduledJob.xml)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS scheduled_jobs (
                object_id INTEGER NOT NULL PRIMARY KEY,
                method_name TEXT,
                description TEXT,
                key TEXT,
                use INTEGER,
                predefined INTEGER,
                restart_count_on_failure INTEGER,
                restart_interval_on_failure INTEGER,
                FOREIGN KEY (object_id) REFERENCES metadata_objects(id)
            )
        ''')

        # Структурные связи метаданных (подсистемы, роли, подписки — не типы полей)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS metadata_relations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                src_object_id INTEGER NOT NULL,
                dst_object_id INTEGER NOT NULL,
                relation_kind TEXT NOT NULL,
                source_name TEXT,
                source_detail TEXT,
                FOREIGN KEY (src_object_id) REFERENCES metadata_objects(id),
                FOREIGN KEY (dst_object_id) REFERENCES metadata_objects(id)
            )
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS ix_mrel_src ON metadata_relations(src_object_id)
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS ix_mrel_dst ON metadata_relations(dst_object_id)
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS ix_mrel_kind ON metadata_relations(relation_kind)
        ''')

        # Привязка ФО к объектам метаданных (Content ФО: документ/реквизит/колонка ТЧ/ресурс)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS fo_content_ref (
                functional_option_id INTEGER NOT NULL,
                metadata_object_id INTEGER NOT NULL,
                content_ref_type TEXT NOT NULL,
                tabular_section_name TEXT,
                element_name TEXT,
                FOREIGN KEY (functional_option_id) REFERENCES metadata_objects(id),
                FOREIGN KEY (metadata_object_id) REFERENCES metadata_objects(id)
            )
        ''')

        # Привязка ФО к элементам форм (реквизит/команда/элемент формы зависит от ФО)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS fo_form_usage (
                functional_option_id INTEGER NOT NULL,
                owner_object_id INTEGER NOT NULL,
                form_id INTEGER,
                element_type TEXT NOT NULL,
                element_name TEXT,
                FOREIGN KEY (functional_option_id) REFERENCES metadata_objects(id),
                FOREIGN KEY (owner_object_id) REFERENCES metadata_objects(id),
                FOREIGN KEY (form_id) REFERENCES forms(id)
            )
        ''')
        
        # Индексы для быстрого поиска
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_objects_name 
            ON metadata_objects(name)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_objects_type 
            ON metadata_objects(object_type)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_forms_name 
            ON forms(form_name)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_form_items_name 
            ON form_items(name)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_form_items_type 
            ON form_items(item_type)
        ''')
        
        # Индексы для атрибутов
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_attributes_object 
            ON attributes(object_id)
        ''')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_attributes_name ON attributes(name)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_form_items_data_path ON form_items(data_path)')
        
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_tabular_sections_object ON tabular_sections(object_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_tabular_section_columns_ts ON tabular_section_columns(tabular_section_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_tabular_section_columns_name ON tabular_section_columns(column_name)')

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_enum_values_object
            ON enum_values(object_id)
        ''')

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_bp_route_points_object
            ON bp_route_points(object_id)
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_bp_route_transitions_object
            ON bp_route_transitions(object_id)
        ''')

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_fo_content_ref_fo
            ON fo_content_ref(functional_option_id)
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_fo_content_ref_object
            ON fo_content_ref(metadata_object_id)
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_fo_form_usage_fo
            ON fo_form_usage(functional_option_id)
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_fo_form_usage_owner_form
            ON fo_form_usage(owner_object_id, form_id, element_type, element_name)
        ''')

        cursor.execute('CREATE INDEX IF NOT EXISTS idx_modules_object ON modules(object_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_forms_object ON forms(object_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_form_events_form ON form_events(form_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_form_item_events_item ON form_item_events(item_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_module_procedures_module ON module_procedures(module_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_module_procedures_name ON module_procedures(name)')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_scheduled_jobs_method_name
            ON scheduled_jobs(method_name)
        ''')

        # Таблица для полнотекстового поиска по коду (FTS5)
        cursor.execute('''
            CREATE VIRTUAL TABLE IF NOT EXISTS code_search 
            USING fts5(
                object_name,
                module_type,
                code,
                content='modules',
                content_rowid='id'
            )
        ''')
        
        self.conn.commit()
    
    def _insert_configuration(self, data, progress_callback=None):
        """Вставляет данные конфигурации в БД. Два прохода: сначала все объекты и ФО, затем формы и fo_usage."""
        cursor = self.conn.cursor()
        cursor.execute('PRAGMA synchronous=OFF')
        cursor.execute('PRAGMA cache_size=-256000')
        cursor.execute('PRAGMA temp_store=MEMORY')
        total_objects = len(data['objects'])
        pending_type_slots = []

        # Проход 1: объекты без форм (чтобы ФО были в БД до вставки fo_form_usage и fo_content_ref)
        for idx, obj in enumerate(data['objects']):
            cursor.execute('''
                INSERT INTO metadata_objects (
                    uuid, object_type, name, synonym, comment,
                    object_belonging, extended_configuration_object, object_kind
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, 'ConfigObject')
            ''', (
                obj['uuid'],
                obj['type'],
                obj['name'],
                obj['properties'].get('synonym', ''),
                obj['properties'].get('comment', ''),
                obj['properties'].get('object_belonging'),
                obj['properties'].get('extended_configuration_object')
            ))
            object_id = cursor.lastrowid

            if obj['type'] == 'FunctionalOption':
                loc = obj['properties'].get('location')
                priv = obj['properties'].get('privileged_get_mode')
                cursor.execute('''
                    INSERT INTO functional_options (object_id, location_constant, privileged_get_mode)
                    VALUES (?, ?, ?)
                ''', (object_id, loc, 1 if priv else 0))

            if obj['type'] == 'ScheduledJob':
                p = obj['properties']
                use_val = p.get('use')
                predefined_val = p.get('predefined')
                cursor.execute('''
                    INSERT INTO scheduled_jobs (
                        object_id, method_name, description, key, use, predefined,
                        restart_count_on_failure, restart_interval_on_failure
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    object_id,
                    p.get('method_name'),
                    p.get('description'),
                    p.get('key'),
                    1 if use_val else 0 if use_val is not None else None,
                    1 if predefined_val else 0 if predefined_val is not None else None,
                    p.get('restart_count_on_failure'),
                    p.get('restart_interval_on_failure'),
                ))

            for module in obj['modules']:
                cursor.execute('''
                    INSERT INTO modules (object_id, form_id, command_id, module_type, code)
                    VALUES (?, NULL, NULL, ?, ?)
                ''', (object_id, module['type'], module['code']))
                module_id = cursor.lastrowid
                cursor.execute('''
                    INSERT INTO code_search (rowid, object_name, module_type, code)
                    VALUES (?, ?, ?, ?)
                ''', (module_id, obj['name'], module['type'], module['code']))
                procs = _parse_module_procedures(module['code'])
                if procs:
                    cursor.executemany('''
                        INSERT INTO module_procedures (module_id, name, proc_type, start_line, end_line, params, is_export, execution_context, extension_call_type, comment)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', [(module_id, p['name'], p['proc_type'], p['start_line'], p['end_line'],
                           p['params'], p['is_export'], p['execution_context'], p['extension_call_type'], p['comment']) for p in procs])

            # Команды объекта (не CommonCommand) + модули CommandModule
            if obj['type'] != 'CommonCommand':
                for cmd in obj.get('commands', []):
                    cursor.execute('''
                        INSERT INTO object_commands (
                            object_id, name, synonym, uuid, object_belonging, extended_configuration_object
                        )
                        VALUES (?, ?, ?, ?, ?, ?)
                    ''', (
                        object_id,
                        cmd['name'],
                        cmd.get('synonym') or '',
                        cmd.get('uuid') or '',
                        cmd.get('object_belonging'),
                        cmd.get('extended_configuration_object'),
                    ))
                    command_id = cursor.lastrowid
                    module_code = cmd.get('module_code')
                    if module_code:
                        cursor.execute('''
                            INSERT INTO modules (object_id, form_id, command_id, module_type, code)
                            VALUES (?, NULL, ?, 'CommandModule', ?)
                        ''', (object_id, command_id, module_code))
                        module_id = cursor.lastrowid
                        code_search_name = f"{obj['name']}.{cmd['name']}"
                        cursor.execute('''
                            INSERT INTO code_search (rowid, object_name, module_type, code)
                            VALUES (?, ?, ?, ?)
                        ''', (module_id, code_search_name, 'CommandModule', module_code))
                        procs = _parse_module_procedures(module_code)
                        if procs:
                            cursor.executemany('''
                                INSERT INTO module_procedures (module_id, name, proc_type, start_line, end_line, params, is_export, execution_context, extension_call_type, comment)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            ''', [(module_id, p['name'], p['proc_type'], p['start_line'], p['end_line'],
                                   p['params'], p['is_export'], p['execution_context'], p['extension_call_type'], p['comment']) for p in procs])

            for attr in obj['properties'].get('standard_attributes', []):
                self._insert_attribute(cursor, object_id, attr, pending_type_slots=pending_type_slots)
            for attr in obj['properties'].get('custom_attributes', []):
                self._insert_attribute(cursor, object_id, attr, pending_type_slots=pending_type_slots)
            if obj['type'] not in ('ScheduledJob', 'Subsystem'):
                for dim in obj.get('dimensions', []):
                    self._insert_attribute(cursor, object_id, dim, section='Dimension', pending_type_slots=pending_type_slots)
                for res in obj.get('resources', []):
                    self._insert_attribute(cursor, object_id, res, section='Resource', pending_type_slots=pending_type_slots)
                for attr in obj.get('attributes', []):
                    self._insert_attribute(cursor, object_id, attr, section='Attribute', pending_type_slots=pending_type_slots)
                for ts in obj.get('tabular_sections', []):
                    self._insert_tabular_section(cursor, object_id, ts, pending_type_slots=pending_type_slots)
                enum_values = obj.get('enum_values', [])
                if enum_values:
                    self._insert_enum_values(cursor, object_id, enum_values)
                if obj['type'] == 'BusinessProcess':
                    self._insert_bp_route_data(
                        cursor, object_id,
                        obj.get('route_points', []),
                        obj.get('route_transitions', []),
                    )

            if progress_callback and (idx % 10 == 0 or idx == total_objects - 1):
                progress = 20 + int((idx / total_objects) * 40)
                progress_callback(progress, 100, f"Объекты {idx + 1}/{total_objects}")

        # Справочник ФО для разрешения UUID / "FunctionalOption.Имя" -> id
        cursor.execute('SELECT id, name, uuid FROM metadata_objects WHERE object_type = ?', ('FunctionalOption',))
        fo_resolver = {}
        for row in cursor.fetchall():
            fid, name, uuid_val = row[0], row[1], row[2] or ''
            fo_resolver[uuid_val] = fid
            fo_resolver[name] = fid
            fo_resolver['FunctionalOption.' + name] = fid

        # Справочник (object_type, name) -> id для разрешения Content и типов
        cursor.execute('''
            SELECT id, object_type, name FROM metadata_objects
            WHERE object_kind = 'ConfigObject'
        ''')
        type_name_to_id = {}
        for row in cursor.fetchall():
            type_name_to_id[(row['object_type'], row['name'])] = row['id']

        type_resolver = MetadataTypeResolver()
        if pending_type_slots:
            type_resolver.insert_slots(cursor, pending_type_slots, type_name_to_id)

        self._link_subsystem_relations(cursor, data['objects'], type_name_to_id)

        # Заполняем fo_content_ref из Content каждой ФО
        for obj in data['objects']:
            if obj['type'] != 'FunctionalOption':
                continue
            content_refs = obj['properties'].get('content_refs') or []
            cursor.execute('SELECT id FROM metadata_objects WHERE name = ? AND object_type = ?', (obj['name'], obj['type']))
            fo_row = cursor.fetchone()
            if not fo_row:
                continue
            fo_id = fo_row['id']
            for ref_str in content_refs:
                parsed = self._parse_content_ref(ref_str)
                if not parsed:
                    continue
                obj_type, obj_name, ref_type, ts_name, elem_name = parsed
                meta_id = type_name_to_id.get((obj_type, obj_name))
                if meta_id is None:
                    continue
                cursor.execute('''
                    INSERT INTO fo_content_ref (functional_option_id, metadata_object_id, content_ref_type, tabular_section_name, element_name)
                    VALUES (?, ?, ?, ?, ?)
                ''', (fo_id, meta_id, ref_type, ts_name, elem_name))

        self._link_scheduled_job_procedures(cursor)

        # Проход 2: формы и fo_form_usage
        pending_form_type_slots = []
        for idx, obj in enumerate(data['objects']):
            cursor.execute('SELECT id FROM metadata_objects WHERE name = ? AND object_type = ?', (obj['name'], obj['type']))
            row = cursor.fetchone()
            if not row:
                continue
            object_id = row[0]
            for form in obj.get('forms', []):
                self._insert_form(
                    cursor, object_id, obj['name'], form, fo_resolver,
                    pending_type_slots=pending_form_type_slots,
                )

            if progress_callback and (idx % 10 == 0 or idx == total_objects - 1):
                progress = 60 + int((idx / total_objects) * 40)
                progress_callback(progress, 100, f"Формы {idx + 1}/{total_objects}")

        if pending_form_type_slots:
            type_resolver.insert_slots(cursor, pending_form_type_slots, type_name_to_id)

        self.conn.commit()
        cursor.execute('PRAGMA synchronous=NORMAL')

    def _link_subsystem_relations(self, cursor, objects, type_name_to_id):
        """Материализует subsystem_member в metadata_relations из Content и ChildObjects подсистем."""
        subsystem_ids = {}
        for obj in objects:
            if obj['type'] != 'Subsystem':
                continue
            cursor.execute(
                'SELECT id FROM metadata_objects WHERE name = ? AND object_type = ?',
                (obj['name'], 'Subsystem'),
            )
            row = cursor.fetchone()
            if row:
                subsystem_ids[obj['name']] = row['id']

        for obj in objects:
            if obj['type'] != 'Subsystem':
                continue
            src_id = subsystem_ids.get(obj['name'])
            if src_id is None:
                continue

            for ref_str in obj.get('content_refs') or []:
                if '.' not in ref_str:
                    continue
                obj_type, obj_name = ref_str.split('.', 1)
                dst_id = type_name_to_id.get((obj_type, obj_name))
                if dst_id is None:
                    continue
                cursor.execute('''
                    INSERT INTO metadata_relations (
                        src_object_id, dst_object_id, relation_kind, source_name, source_detail
                    )
                    VALUES (?, ?, 'subsystem_member', ?, 'Content')
                ''', (src_id, dst_id, ref_str))

            parent_qname = obj['name']
            for child_name in obj.get('child_subsystem_names') or []:
                child_qname = f'{parent_qname}.{child_name}'
                dst_id = subsystem_ids.get(child_qname)
                if dst_id is None:
                    continue
                cursor.execute('''
                    INSERT INTO metadata_relations (
                        src_object_id, dst_object_id, relation_kind, source_name, source_detail
                    )
                    VALUES (?, ?, 'subsystem_member', ?, 'ChildSubsystem')
                ''', (src_id, dst_id, child_name))
    
    def _link_scheduled_job_procedures(self, cursor):
        """Проставляет used_in_scheduled_job для процедур общих модулей из MethodName регл. заданий."""
        cursor.execute('SELECT method_name FROM scheduled_jobs WHERE method_name IS NOT NULL')
        for row in cursor.fetchall():
            method_name = (row['method_name'] or '').strip()
            if not method_name:
                continue
            parts = method_name.split('.')
            if len(parts) != 3 or parts[0] != 'CommonModule':
                continue
            module_name, procedure_name = parts[1], parts[2]
            cursor.execute('''
                SELECT p.id
                FROM module_procedures p
                JOIN modules m ON p.module_id = m.id
                JOIN metadata_objects o ON m.object_id = o.id
                WHERE o.object_type = 'CommonModule' AND o.name = ?
                  AND m.module_type = 'Module'
                  AND m.form_id IS NULL AND m.command_id IS NULL
                  AND p.name = ?
            ''', (module_name, procedure_name))
            proc_row = cursor.fetchone()
            if proc_row:
                cursor.execute(
                    'UPDATE module_procedures SET used_in_scheduled_job = 1 WHERE id = ?',
                    (proc_row['id'],),
                )

    def _parse_content_ref(self, ref_str):
        """Парсит строку Content ФО (например Document.Имя, Document.Имя.Attribute.Рекв,
        Document.Имя.TabularSection.ТЧ.Attribute.Кол, InformationRegister.Имя.Resource.Ресурс).
        Возвращает (object_type, object_name, content_ref_type, tabular_section_name, element_name)
        или None при неверном формате."""
        if not ref_str or not isinstance(ref_str, str):
            return None
        s = ref_str.strip()
        parts = s.split('.')
        if len(parts) < 2:
            return None
        object_type = parts[0]
        object_name = parts[1]
        if len(parts) == 2:
            return (object_type, object_name, 'Object', None, None)
        if len(parts) == 4:
            # Type.Name.Attribute|Resource|Dimension.ElementName
            ref_type = parts[2]
            if ref_type in ('Attribute', 'Resource', 'Dimension'):
                return (object_type, object_name, ref_type, None, parts[3])
            return None
        if len(parts) == 6 and parts[2] == 'TabularSection' and parts[4] == 'Attribute':
            return (object_type, object_name, 'TabularSectionColumn', parts[3], parts[5])
        return None

    def _resolve_fo_id(self, fo_ref, fo_resolver):
        """Разрешает ссылку на ФО (UUID или FunctionalOption.Имя) в id. Возвращает id или None."""
        if not fo_ref or not fo_resolver:
            return None
        s = fo_ref.strip()
        return fo_resolver.get(s)

    def _insert_form(self, cursor, object_id, object_name, form, fo_resolver=None, pending_type_slots=None):
        """Вставляет данные формы в БД. fo_resolver: dict (uuid/имя/FunctionalOption.Имя -> id) для fo_form_usage."""
        fo_resolver = fo_resolver or {}
        cursor.execute('''
            INSERT INTO forms (object_id, form_name, form_kind, uuid, properties_json)
            VALUES (?, ?, ?, ?, ?)
        ''', (
            object_id,
            form['name'],
            form.get('form_kind'),
            form['uuid'],
            json.dumps(form['properties'], ensure_ascii=False) if form['properties'] else None
        ))
        form_id = cursor.lastrowid

        for attr in form.get('attributes', []):
            cursor.execute('''
                INSERT INTO form_attributes (
                    form_id, name, title, is_main, query_text
                )
                VALUES (?, ?, ?, ?, ?)
            ''', (
                form_id,
                attr['name'],
                attr['title'],
                1 if attr['is_main'] else 0,
                attr.get('query_text')
            ))
            attr_id = cursor.lastrowid
            if pending_type_slots is not None:
                type_slots = attr.get('type_slots')
                if type_slots:
                    pending_type_slots.append({
                        'source_table': 'form_attributes',
                        'source_row_id': attr_id,
                        'src_object_id': object_id,
                        'type_slots': type_slots,
                    })
            for col in attr.get('columns') or []:
                cursor.execute('''
                    INSERT INTO form_attribute_columns (
                        form_attribute_id, name, title, table_context
                    )
                    VALUES (?, ?, ?, ?)
                ''', (
                    attr_id,
                    col['name'],
                    col.get('title', ''),
                    col.get('table'),
                ))
                col_id = cursor.lastrowid
                if pending_type_slots is not None:
                    col_slots = col.get('type_slots')
                    if col_slots:
                        pending_type_slots.append({
                            'source_table': 'form_attribute_columns',
                            'source_row_id': col_id,
                            'src_object_id': object_id,
                            'type_slots': col_slots,
                        })
            for fo_ref in attr.get('functional_options', []):
                fo_id = self._resolve_fo_id(fo_ref, fo_resolver)
                if fo_id is not None:
                    cursor.execute('''
                        INSERT INTO fo_form_usage (functional_option_id, owner_object_id, form_id, element_type, element_name)
                        VALUES (?, ?, ?, ?, ?)
                    ''', (fo_id, object_id, form_id, 'FormAttribute', attr['name']))

        for cmd in form.get('commands', []):
            cursor.execute('''
                INSERT INTO form_commands (
                    form_id, name, title, action, shortcut, representation
                )
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                form_id,
                cmd['name'],
                cmd['title'],
                cmd['action'],
                cmd.get('shortcut'),
                cmd.get('representation')
            ))
            for fo_ref in cmd.get('functional_options', []):
                fo_id = self._resolve_fo_id(fo_ref, fo_resolver)
                if fo_id is not None:
                    cursor.execute('''
                        INSERT INTO fo_form_usage (functional_option_id, owner_object_id, form_id, element_type, element_name)
                        VALUES (?, ?, ?, ?, ?)
                    ''', (fo_id, object_id, form_id, 'FormCommand', cmd['name']))
        
        # Вставляем события формы
        for event in form.get('events', []):
            cursor.execute('''
                INSERT INTO form_events (form_id, event_name, handler, call_type)
                VALUES (?, ?, ?, ?)
            ''', (
                form_id,
                event['name'],
                event['handler'],
                event['call_type']
            ))
        
        # Вставляем элементы UI
        item_id_map = {}  # Маппинг item['id'] -> db_id
        
        for item in form.get('items', []):
            # Определяем parent_id из БД
            parent_db_id = None
            if item['parent_id']:
                parent_db_id = item_id_map.get(item['parent_id'])
            
            visible = item.get('visible')
            enabled = item.get('enabled')
            if visible is not None:
                visible = 1 if visible else 0
            if enabled is not None:
                enabled = 1 if enabled else 0
            cursor.execute('''
                INSERT INTO form_items (
                    form_id, parent_id, name, item_type,
                    data_path, title, visible, enabled, command_name
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                form_id,
                parent_db_id,
                item['name'],
                item['type'],
                item['data_path'],
                item['title'],
                visible,
                enabled,
                item.get('command_name') or None,
            ))
            
            item_db_id = cursor.lastrowid
            item_id_map[item['id']] = item_db_id
            for fo_ref in item.get('functional_options', []):
                fo_id = self._resolve_fo_id(fo_ref, fo_resolver)
                if fo_id is not None:
                    cursor.execute('''
                        INSERT INTO fo_form_usage (functional_option_id, owner_object_id, form_id, element_type, element_name)
                        VALUES (?, ?, ?, ?, ?)
                    ''', (fo_id, object_id, form_id, 'FormItem', item['name']))

            # Вставляем события элемента
            for event in item.get('events', []):
                cursor.execute('''
                    INSERT INTO form_item_events (item_id, event_name, handler)
                    VALUES (?, ?, ?)
                ''', (
                    item_db_id,
                    event['name'],
                    event['handler']
                ))
        
        # Вставляем условное оформление
        if form.get('conditional_appearance'):
            cursor.execute('''
                INSERT INTO form_conditional_appearance (form_id, xml_data)
                VALUES (?, ?)
            ''', (
                form_id,
                form['conditional_appearance']
            ))
        
        # Вставляем модуль формы
        if form.get('module'):
            cursor.execute('''
                INSERT INTO modules (object_id, form_id, command_id, module_type, code)
                VALUES (?, ?, NULL, ?, ?)
            ''', (
                object_id,
                form_id,
                'FormModule',
                form['module']
            ))
            
            # Добавляем в полнотекстовый индекс
            module_id = cursor.lastrowid
            cursor.execute('''
                INSERT INTO code_search (rowid, object_name, module_type, code)
                VALUES (?, ?, ?, ?)
            ''', (
                module_id,
                f"{object_name}.{form['name']}",
                'FormModule',
                form['module']
            ))
            procs = _parse_module_procedures(form['module'])
            if procs:
                cursor.executemany('''
                    INSERT INTO module_procedures (module_id, name, proc_type, start_line, end_line, params, is_export, execution_context, extension_call_type, comment)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', [(module_id, p['name'], p['proc_type'], p['start_line'], p['end_line'],
                       p['params'], p['is_export'], p['execution_context'], p['extension_call_type'], p['comment']) for p in procs])
    
    def _insert_attribute(self, cursor, object_id, attr, section='Attribute', pending_type_slots=None):
        """Вставляет атрибут объекта в БД"""
        cursor.execute('''
            INSERT INTO attributes (object_id, name, title, comment, is_standard, standard_type, section)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            object_id,
            attr['name'],
            attr.get('title', ''),
            attr.get('comment', ''),
            1 if attr.get('is_standard') else 0,
            attr.get('standard_type'),
            section,
        ))
        if pending_type_slots is not None:
            type_slots = attr.get('type_slots')
            if type_slots:
                pending_type_slots.append({
                    'source_table': 'attributes',
                    'source_row_id': cursor.lastrowid,
                    'src_object_id': object_id,
                    'type_slots': type_slots,
                })

    def _insert_tabular_section(self, cursor, object_id, ts, pending_type_slots=None):
        """Вставляет табличную часть с колонками в БД (tabular_sections + tabular_section_columns)."""
        cursor.execute('''
            INSERT INTO tabular_sections (object_id, name, title, comment)
            VALUES (?, ?, ?, ?)
        ''', (object_id, ts['name'], ts.get('title', ''), ts.get('comment', '')))
        ts_id = cursor.lastrowid
        for column in ts['columns']:
            cursor.execute('''
                INSERT INTO tabular_section_columns (tabular_section_id, column_name, title, comment)
                VALUES (?, ?, ?, ?)
            ''', (ts_id, column['name'], column.get('title', ''), column.get('comment', '')))
            if pending_type_slots is not None:
                type_slots = column.get('type_slots')
                if type_slots:
                    pending_type_slots.append({
                        'source_table': 'tabular_section_columns',
                        'source_row_id': cursor.lastrowid,
                        'src_object_id': object_id,
                        'type_slots': type_slots,
                    })

    def _insert_enum_values(self, cursor, object_id, enum_values):
        """Вставляет значения перечисления в БД"""
        for ev in enum_values:
            cursor.execute('''
                INSERT INTO enum_values (object_id, name, enum_order, title, comment, object_belonging, extended_configuration_object)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                object_id,
                ev['name'],
                ev.get('order'),
                ev.get('title', ''),
                ev.get('comment', ''),
                ev.get('object_belonging'),
                ev.get('extended_configuration_object'),
            ))

    def _insert_bp_route_data(self, cursor, object_id, route_points, route_transitions):
        """Вставляет точки маршрута и переходы бизнес-процесса."""
        for point in route_points:
            cursor.execute('''
                INSERT INTO bp_route_points (
                    object_id, name, point_type, title, uuid, tab_order, true_port, false_port
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                object_id,
                point['name'],
                point['type'],
                point.get('title', ''),
                point.get('uuid', ''),
                point.get('tab_order'),
                point.get('true_port'),
                point.get('false_port'),
            ))
        for transition in route_transitions:
            cursor.execute('''
                INSERT INTO bp_route_transitions (
                    object_id, from_point, to_point, from_port, title
                )
                VALUES (?, ?, ?, ?, ?)
            ''', (
                object_id,
                transition['from'],
                transition['to'],
                transition.get('from_port'),
                transition.get('title', ''),
            ))
    
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


def test_database_creation(config_xml_path, db_path):
    """Тестовая функция создания БД"""
    
    def progress(current, total, message):
        print(f"[{current}/{total}] {message}")
    
    db = DatabaseManager(db_path)
    db.connect()
    
    print("Создание базы данных...")
    db.create_database(config_xml_path, progress)
    
    print("\nСтатистика:")
    stats = db.get_statistics()
    print(f"  Всего объектов: {stats['total_objects']}")
    print(f"  Всего модулей: {stats['total_modules']}")
    print(f"  Всего атрибутов: {stats['total_attributes']}")
    print(f"    - Стандартных: {stats['total_standard_attributes']}")
    print(f"    - Кастомных: {stats['total_custom_attributes']}")
    print("\nПо типам:")
    for obj_type, count in stats['by_type'].items():
        print(f"  {obj_type}: {count}")
    if stats.get('total_functional_options', 0) or stats.get('total_fo_content_ref', 0) or stats.get('total_fo_form_usage', 0):
        print(f"\n  ФО: {stats.get('total_functional_options', 0)}, content_ref: {stats.get('total_fo_content_ref', 0)}, form_usage: {stats.get('total_fo_form_usage', 0)}")
    if stats.get('total_scheduled_jobs', 0):
        print(f"\n  Регл. задания: {stats.get('total_scheduled_jobs', 0)}")

    db.close()
    print(f"\nБаза создана: {db_path}")