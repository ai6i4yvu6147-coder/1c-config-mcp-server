import sqlite3
import json
import re
from pathlib import Path
import sys

# Добавляем корневую папку проекта в путь
sys.path.insert(0, str(Path(__file__).parent.parent))

from shared.xml_parser import ConfigurationParser


def _parse_module_procedures(code):
    """
    Парсит код модуля 1С, возвращает список процедур/функций для таблицы module_procedures.
    Каждый элемент: name, proc_type, start_line, end_line, params, is_export, execution_context, extension_call_type.
    start_line — первая строка для среза (включая все &-директивы над процедурой); 1-based.
    execution_context и extension_call_type определяются по всем подряд идущим &-строкам над процедурой.
    """
    lines = code.split('\n')
    pattern = re.compile(
        r'^\s*(Процедура|Функция)\s+([А-Яа-яA-Za-z0-9_]+)\s*\((.*?)\)\s*(Экспорт)?\s*$',
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

    def collect_annotation_lines_above(lines, proc_line_index):
        """Собирает индексы всех подряд идущих &-строк непосредственно над процедурой (снизу вверх)."""
        indices = []
        j = proc_line_index - 1
        while j >= 0:
            stripped = lines[j].strip()
            if stripped.startswith('&') and len(stripped) > 1:
                indices.append(j)
                j -= 1
            else:
                break
        indices.reverse()
        return indices

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
            ann_indices = collect_annotation_lines_above(lines, i)
            execution_context = None
            extension_call_type = None
            for idx in reversed(ann_indices):
                stripped = lines[idx].strip()
                if execution_context is None:
                    execution_context = directive_to_context(stripped)
                if extension_call_type is None:
                    extension_call_type = line_to_extension_call_type(stripped)
            start_line = (ann_indices[0] + 1) if ann_indices else line_num
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
    
    def connect(self):
        """Подключение к базе данных"""
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute('PRAGMA journal_mode=WAL')
        return self.conn
    
    def close(self):
        """Закрытие подключения"""
        if self.conn:
            self.conn.close()
    
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
                extended_configuration_object TEXT
            )
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
                type TEXT,
                title TEXT,
                is_main INTEGER DEFAULT 0,
                columns_json TEXT,
                query_text TEXT,
                FOREIGN KEY (form_id) REFERENCES forms(id)
            )
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
        
        # Таблица модулей (добавляем form_id)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS modules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                object_id INTEGER NOT NULL,
                form_id INTEGER,
                module_type TEXT NOT NULL,
                code TEXT NOT NULL,
                FOREIGN KEY (object_id) REFERENCES metadata_objects(id),
                FOREIGN KEY (form_id) REFERENCES forms(id)
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
                FOREIGN KEY (module_id) REFERENCES modules(id)
            )
        ''')
        
        # Таблица атрибутов объектов (стандартные + кастомные + измерения/ресурсы регистров)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS attributes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                object_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                attribute_type TEXT,
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
                column_type TEXT,
                title TEXT,
                comment TEXT,
                FOREIGN KEY (tabular_section_id) REFERENCES tabular_sections(id)
            )
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

        # Таблица функциональных опций (свойства ФО; Content хранится в fo_content_ref)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS functional_options (
                object_id INTEGER NOT NULL PRIMARY KEY,
                location_constant TEXT,
                privileged_get_mode INTEGER,
                FOREIGN KEY (object_id) REFERENCES metadata_objects(id)
            )
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
        
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_tabular_sections_object ON tabular_sections(object_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_tabular_section_columns_ts ON tabular_section_columns(tabular_section_id)')

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_enum_values_object
            ON enum_values(object_id)
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

        # Проход 1: объекты без форм (чтобы ФО были в БД до вставки fo_form_usage и fo_content_ref)
        for idx, obj in enumerate(data['objects']):
            cursor.execute('''
                INSERT INTO metadata_objects (uuid, object_type, name, synonym, comment, object_belonging, extended_configuration_object)
                VALUES (?, ?, ?, ?, ?, ?, ?)
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

            for module in obj['modules']:
                cursor.execute('''
                    INSERT INTO modules (object_id, form_id, module_type, code)
                    VALUES (?, NULL, ?, ?)
                ''', (object_id, module['type'], module['code']))
                module_id = cursor.lastrowid
                cursor.execute('''
                    INSERT INTO code_search (rowid, object_name, module_type, code)
                    VALUES (?, ?, ?, ?)
                ''', (module_id, obj['name'], module['type'], module['code']))
                procs = _parse_module_procedures(module['code'])
                if procs:
                    cursor.executemany('''
                        INSERT INTO module_procedures (module_id, name, proc_type, start_line, end_line, params, is_export, execution_context, extension_call_type)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', [(module_id, p['name'], p['proc_type'], p['start_line'], p['end_line'],
                           p['params'], p['is_export'], p['execution_context'], p['extension_call_type']) for p in procs])

            for attr in obj['properties'].get('standard_attributes', []):
                self._insert_attribute(cursor, object_id, attr)
            for attr in obj['properties'].get('custom_attributes', []):
                self._insert_attribute(cursor, object_id, attr)
            for dim in obj.get('dimensions', []):
                self._insert_attribute(cursor, object_id, dim, section='Dimension')
            for res in obj.get('resources', []):
                self._insert_attribute(cursor, object_id, res, section='Resource')
            for ts in obj.get('tabular_sections', []):
                self._insert_tabular_section(cursor, object_id, ts)
            enum_values = obj.get('enum_values', [])
            if enum_values:
                self._insert_enum_values(cursor, object_id, enum_values)

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

        # Справочник (object_type, name) -> id для разрешения Content
        cursor.execute('SELECT id, object_type, name FROM metadata_objects')
        type_name_to_id = {}
        for row in cursor.fetchall():
            type_name_to_id[(row['object_type'], row['name'])] = row['id']

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

        # Проход 2: формы и fo_form_usage
        for idx, obj in enumerate(data['objects']):
            cursor.execute('SELECT id FROM metadata_objects WHERE name = ? AND object_type = ?', (obj['name'], obj['type']))
            row = cursor.fetchone()
            if not row:
                continue
            object_id = row[0]
            for form in obj.get('forms', []):
                self._insert_form(cursor, object_id, obj['name'], form, fo_resolver)

            if progress_callback and (idx % 10 == 0 or idx == total_objects - 1):
                progress = 60 + int((idx / total_objects) * 40)
                progress_callback(progress, 100, f"Формы {idx + 1}/{total_objects}")

        self.conn.commit()
        cursor.execute('PRAGMA synchronous=NORMAL')
    
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

    def _insert_form(self, cursor, object_id, object_name, form, fo_resolver=None):
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
                    form_id, name, type, title, is_main, columns_json, query_text
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                form_id,
                attr['name'],
                attr['type'],
                attr['title'],
                1 if attr['is_main'] else 0,
                json.dumps(attr['columns'], ensure_ascii=False) if attr['columns'] else None,
                attr.get('query_text')
            ))
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
                    data_path, title, visible, enabled
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                form_id,
                parent_db_id,
                item['name'],
                item['type'],
                item['data_path'],
                item['title'],
                visible,
                enabled
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
                INSERT INTO modules (object_id, form_id, module_type, code)
                VALUES (?, ?, ?, ?)
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
                    INSERT INTO module_procedures (module_id, name, proc_type, start_line, end_line, params, is_export, execution_context, extension_call_type)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', [(module_id, p['name'], p['proc_type'], p['start_line'], p['end_line'],
                       p['params'], p['is_export'], p['execution_context'], p['extension_call_type']) for p in procs])
    
    def _insert_attribute(self, cursor, object_id, attr, section='Attribute'):
        """Вставляет атрибут объекта в БД"""
        cursor.execute('''
            INSERT INTO attributes (object_id, name, attribute_type, title, comment, is_standard, standard_type, section)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            object_id,
            attr['name'],
            attr.get('type', ''),
            attr.get('title', ''),
            attr.get('comment', ''),
            1 if attr.get('is_standard') else 0,
            attr.get('standard_type'),
            section,
        ))

    def _insert_tabular_section(self, cursor, object_id, ts):
        """Вставляет табличную часть с колонками в БД (tabular_sections + tabular_section_columns)."""
        cursor.execute('''
            INSERT INTO tabular_sections (object_id, name, title, comment)
            VALUES (?, ?, ?, ?)
        ''', (object_id, ts['name'], ts.get('title', ''), ts.get('comment', '')))
        ts_id = cursor.lastrowid
        for column in ts['columns']:
            cursor.execute('''
                INSERT INTO tabular_section_columns (tabular_section_id, column_name, column_type, title, comment)
                VALUES (?, ?, ?, ?, ?)
            ''', (ts_id, column['name'], column.get('type', ''), column.get('title', ''), column.get('comment', '')))

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

    db.close()
    print(f"\nБаза создана: {db_path}")