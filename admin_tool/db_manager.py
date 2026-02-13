import sqlite3
import json
from pathlib import Path
import sys

# Добавляем корневую папку проекта в путь
sys.path.insert(0, str(Path(__file__).parent.parent))

from shared.xml_parser import ConfigurationParser


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
                comment TEXT
            )
        ''')
        
        # Таблица форм
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS forms (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                object_id INTEGER NOT NULL,
                form_name TEXT NOT NULL,
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
                picture TEXT,
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
                properties_json TEXT,
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
        
        # Таблица атрибутов объектов (стандартные + кастомные)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS attributes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                object_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                attribute_type TEXT,
                title TEXT,
                is_standard INTEGER DEFAULT 0,
                standard_type TEXT,
                FOREIGN KEY (object_id) REFERENCES metadata_objects(id)
            )
        ''')
        
        # Таблица колонок табличных частей
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS tabular_section_columns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                object_id INTEGER NOT NULL,
                tabular_section_name TEXT NOT NULL,
                column_name TEXT NOT NULL,
                column_type TEXT,
                title TEXT,
                FOREIGN KEY (object_id) REFERENCES metadata_objects(id)
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
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_tabular_cols_object 
            ON tabular_section_columns(object_id)
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
        """Вставляет данные конфигурации в БД"""
        cursor = self.conn.cursor()
        
        total_objects = len(data['objects'])
        
        for idx, obj in enumerate(data['objects']):
            # Вставляем объект
            cursor.execute('''
                INSERT INTO metadata_objects (uuid, object_type, name, synonym, comment)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                obj['uuid'],
                obj['type'],
                obj['name'],
                obj['properties'].get('synonym', ''),
                obj['properties'].get('comment', '')
            ))
            
            object_id = cursor.lastrowid
            
            # Вставляем модули объекта (без form_id)
            for module in obj['modules']:
                cursor.execute('''
                    INSERT INTO modules (object_id, form_id, module_type, code)
                    VALUES (?, NULL, ?, ?)
                ''', (object_id, module['type'], module['code']))
                
                # Добавляем в полнотекстовый индекс
                module_id = cursor.lastrowid
                cursor.execute('''
                    INSERT INTO code_search (rowid, object_name, module_type, code)
                    VALUES (?, ?, ?, ?)
                ''', (module_id, obj['name'], module['type'], module['code']))
            
            # Вставляем стандартные атрибуты
            for attr in obj['properties'].get('standard_attributes', []):
                self._insert_attribute(cursor, object_id, attr)
            
            # Вставляем кастомные атрибуты
            for attr in obj['properties'].get('custom_attributes', []):
                self._insert_attribute(cursor, object_id, attr)
            
            # Вставляем формы
            for form in obj.get('forms', []):
                self._insert_form(cursor, object_id, obj['name'], form)
            
            # Отчет о прогрессе
            if progress_callback and (idx % 10 == 0 or idx == total_objects - 1):
                progress = 20 + int((idx / total_objects) * 80)
                progress_callback(progress, 100, f"Загружено {idx + 1}/{total_objects} объектов")
        
        self.conn.commit()
    
    def _insert_form(self, cursor, object_id, object_name, form):
        """Вставляет данные формы в БД"""
        # Вставляем форму
        cursor.execute('''
            INSERT INTO forms (object_id, form_name, uuid, properties_json)
            VALUES (?, ?, ?, ?)
        ''', (
            object_id,
            form['name'],
            form['uuid'],
            json.dumps(form['properties'], ensure_ascii=False) if form['properties'] else None
        ))
        
        form_id = cursor.lastrowid
        
        # Вставляем реквизиты
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
                attr['query_text']
            ))
        
        # Вставляем команды
        for cmd in form.get('commands', []):
            cursor.execute('''
                INSERT INTO form_commands (
                    form_id, name, title, action, shortcut, picture, representation
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                form_id,
                cmd['name'],
                cmd['title'],
                cmd['action'],
                cmd['shortcut'],
                cmd['picture'],
                cmd['representation']
            ))
        
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
            
            cursor.execute('''
                INSERT INTO form_items (
                    form_id, parent_id, name, item_type, 
                    data_path, title, properties_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                form_id,
                parent_db_id,
                item['name'],
                item['type'],
                item['data_path'],
                item['title'],
                json.dumps(item['properties'], ensure_ascii=False) if item['properties'] else None
            ))
            
            item_db_id = cursor.lastrowid
            item_id_map[item['id']] = item_db_id
            
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
    
    def _insert_attribute(self, cursor, object_id, attr):
        """Вставляет атрибут объекта в БД"""
        cursor.execute('''
            INSERT INTO attributes (object_id, name, attribute_type, title, is_standard, standard_type)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            object_id,
            attr['name'],
            attr.get('type', ''),
            attr.get('title', ''),
            1 if attr.get('is_standard') else 0,
            attr.get('standard_type')
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
    
    db.close()
    print(f"\nБаза создана: {db_path}")