import sqlite3
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
        
        # Таблица модулей
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS modules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                object_id INTEGER NOT NULL,
                module_type TEXT NOT NULL,
                code TEXT NOT NULL,
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
            
            # Вставляем модули
            for module in obj['modules']:
                cursor.execute('''
                    INSERT INTO modules (object_id, module_type, code)
                    VALUES (?, ?, ?)
                ''', (object_id, module['type'], module['code']))
                
                # Добавляем в полнотекстовый индекс
                module_id = cursor.lastrowid
                cursor.execute('''
                    INSERT INTO code_search (rowid, object_name, module_type, code)
                    VALUES (?, ?, ?, ?)
                ''', (module_id, obj['name'], module['type'], module['code']))
            
            # Отчет о прогрессе
            if progress_callback and (idx % 10 == 0 or idx == total_objects - 1):
                progress = 20 + int((idx / total_objects) * 80)
                progress_callback(progress, 100, f"Загружено {idx + 1}/{total_objects} объектов")
        
        self.conn.commit()
    
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
    print("\nПо типам:")
    for obj_type, count in stats['by_type'].items():
        print(f"  {obj_type}: {count}")
    
    db.close()
    print(f"\nБаза создана: {db_path}")