import sqlite3
from pathlib import Path
import sys

# Добавляем корневую папку проекта в путь
sys.path.insert(0, str(Path(__file__).parent.parent))

from shared.project_manager import ProjectManager


class ConfigurationTools:
    """Инструменты для работы с конфигурациями 1С через несколько проектов"""
    
    def __init__(self, projects_file=None, databases_dir=None):
        """
        Args:
            projects_file: Путь к projects.json (если None - автоопределение)
            databases_dir: Путь к папке databases (если None - автоопределение)
        """
        # Автоопределение путей если не указаны
        if projects_file is None or databases_dir is None:
            if getattr(sys, 'frozen', False):
                # Portable: exe в подпапке, поднимаемся на уровень выше
                app_path = Path(sys.executable).parent
                root = app_path.parent
            else:
                # Разработка: текущая папка - это корень
                root = Path.cwd()
            
            if projects_file is None:
                projects_file = root / "projects.json"
            if databases_dir is None:
                databases_dir = root / "databases"
        
        self.pm = ProjectManager(str(projects_file), str(databases_dir))
        self.connections = {}
    
    def _get_active_databases(self, project_filter=None):
        """
        Получить список активных БД с фильтрацией
        
        Args:
            project_filter: Имя проекта для фильтрации или None для всех
        
        Returns:
            List of database info dicts
        """
        all_dbs = self.pm.get_active_databases()
        
        if project_filter:
            all_dbs = [db for db in all_dbs if db['project_name'].lower() == project_filter.lower()]
        
        return all_dbs
    
    def _get_connection(self, db_path):
        """Получить подключение к БД (с кэшированием)"""
        if db_path not in self.connections:
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            self.connections[db_path] = conn
        
        return self.connections[db_path]
    
    def close_all(self):
        """Закрыть все подключения"""
        for conn in self.connections.values():
            conn.close()
        self.connections.clear()
    
    def search_code(self, query, project_filter=None, extension_filter=None, max_results=10):
        """
        Поиск по коду во всех активных проектах
        
        Args:
            query: Поисковый запрос
            project_filter: Фильтр по проекту (опционально)
            extension_filter: Фильтр по расширению/базе (опционально)
            max_results: Максимум результатов на базу
        
        Returns:
            Dict grouped by projects
        """
        databases = self._get_active_databases(project_filter)
        
        if extension_filter:
            databases = [db for db in databases if db['db_name'].lower() == extension_filter.lower()]
        
        results = {}
        
        for db_info in databases:
            conn = self._get_connection(db_info['db_path'])
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT 
                    o.name as object_name,
                    m.module_type,
                    m.code,
                    o.object_type
                FROM code_search cs
                JOIN modules m ON cs.rowid = m.id
                JOIN metadata_objects o ON m.object_id = o.id
                WHERE code_search MATCH ?
                LIMIT ?
            ''', (query, max_results))
            
            db_results = []
            for row in cursor.fetchall():
                # Находим позицию совпадения для snippet
                code = row['code']
                query_lower = query.lower()
                code_lower = code.lower()
                
                pos = code_lower.find(query_lower)
                if pos == -1:
                    snippet = code[:100]
                else:
                    start = max(0, pos - 30)
                    end = min(len(code), pos + len(query) + 30)
                    snippet = "..." + code[start:end] + "..."
                
                db_results.append({
                    'object_name': row['object_name'],
                    'object_type': row['object_type'],
                    'module_type': row['module_type'],
                    'snippet': snippet
                })
            
            if db_results:
                project_key = f"{db_info['project_name']}"
                if project_key not in results:
                    results[project_key] = {}
                
                db_key = f"{db_info['db_name']} ({db_info['db_type']})"
                results[project_key][db_key] = db_results
        
        return results
    
    def find_object(self, name, project_filter=None, extension_filter=None):
        """
        Поиск объекта метаданных по имени
        
        Args:
            name: Имя объекта (можно частичное)
            project_filter: Фильтр по проекту
            extension_filter: Фильтр по расширению/базе
        
        Returns:
            Dict grouped by projects
        """
        databases = self._get_active_databases(project_filter)
        
        if extension_filter:
            databases = [db for db in databases if db['db_name'].lower() == extension_filter.lower()]
        
        results = {}
        
        for db_info in databases:
            conn = self._get_connection(db_info['db_path'])
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT 
                    o.name,
                    o.object_type,
                    o.uuid,
                    o.synonym,
                    GROUP_CONCAT(m.module_type) as modules
                FROM metadata_objects o
                LEFT JOIN modules m ON o.id = m.object_id
                WHERE o.name LIKE ?
                GROUP BY o.id
            ''', (f'%{name}%',))
            
            db_results = []
            for row in cursor.fetchall():
                modules = row['modules'].split(',') if row['modules'] else []
                
                db_results.append({
                    'name': row['name'],
                    'type': row['object_type'],
                    'uuid': row['uuid'],
                    'synonym': row['synonym'],
                    'modules': modules
                })
            
            if db_results:
                project_key = f"{db_info['project_name']}"
                if project_key not in results:
                    results[project_key] = {}
                
                db_key = f"{db_info['db_name']} ({db_info['db_type']})"
                results[project_key][db_key] = db_results
        
        return results
    
    def list_objects(self, object_type=None, project_filter=None, extension_filter=None, limit=50):
        """
        Список объектов метаданных
        
        Args:
            object_type: Тип объекта (опционально)
            project_filter: Фильтр по проекту
            extension_filter: Фильтр по расширению/базе
            limit: Максимум объектов на базу
        
        Returns:
            Dict grouped by projects and types
        """
        databases = self._get_active_databases(project_filter)
        
        if extension_filter:
            databases = [db for db in databases if db['db_name'].lower() == extension_filter.lower()]
        
        results = {}
        
        for db_info in databases:
            conn = self._get_connection(db_info['db_path'])
            cursor = conn.cursor()
            
            if object_type:
                cursor.execute('''
                    SELECT name, object_type
                    FROM metadata_objects
                    WHERE object_type = ?
                    ORDER BY name
                    LIMIT ?
                ''', (object_type, limit))
            else:
                cursor.execute('''
                    SELECT name, object_type
                    FROM metadata_objects
                    ORDER BY object_type, name
                    LIMIT ?
                ''', (limit,))
            
            # Группируем по типам
            by_type = {}
            for row in cursor.fetchall():
                obj_type = row['object_type']
                if obj_type not in by_type:
                    by_type[obj_type] = []
                by_type[obj_type].append(row['name'])
            
            if by_type:
                project_key = f"{db_info['project_name']}"
                if project_key not in results:
                    results[project_key] = {}
                
                db_key = f"{db_info['db_name']} ({db_info['db_type']})"
                results[project_key][db_key] = by_type
        
        return results
    
    def get_module_code(self, object_name, module_type='Module', project_filter=None, extension_filter=None):
        """
        Получить код модуля
        
        Args:
            object_name: Имя объекта
            module_type: Тип модуля
            project_filter: Фильтр по проекту
            extension_filter: Фильтр по расширению/базе
        
        Returns:
            Dict with code from each matching database
        """
        databases = self._get_active_databases(project_filter)
        
        if extension_filter:
            databases = [db for db in databases if db['db_name'].lower() == extension_filter.lower()]
        
        results = {}
        
        for db_info in databases:
            conn = self._get_connection(db_info['db_path'])
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT m.code
                FROM modules m
                JOIN metadata_objects o ON m.object_id = o.id
                WHERE o.name = ? AND m.module_type = ?
                LIMIT 1
            ''', (object_name, module_type))
            
            row = cursor.fetchone()
            if row:
                project_key = f"{db_info['project_name']}"
                if project_key not in results:
                    results[project_key] = {}
                
                db_key = f"{db_info['db_name']} ({db_info['db_type']})"
                results[project_key][db_key] = row['code']
        
        return results
    
    def get_module_procedures(self, object_name, module_type='Module', project_filter=None, extension_filter=None):
        """
        Получить список процедур и функций модуля
        
        Args:
            object_name: Имя объекта
            module_type: Тип модуля
            project_filter: Фильтр по проекту
            extension_filter: Фильтр по расширению/базе
        
        Returns:
            Dict with procedures from each matching database
        """
        import re
        
        databases = self._get_active_databases(project_filter)
        
        if extension_filter:
            databases = [db for db in databases if db['db_name'].lower() == extension_filter.lower()]
        
        results = {}
        
        for db_info in databases:
            conn = self._get_connection(db_info['db_path'])
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT m.code
                FROM modules m
                JOIN metadata_objects o ON m.object_id = o.id
                WHERE o.name = ? AND m.module_type = ?
                LIMIT 1
            ''', (object_name, module_type))
            
            row = cursor.fetchone()
            if not row:
                continue
            
            code = row['code']
            
            # Парсинг процедур и функций
            pattern = r'^\s*(Функция|Процедура)\s+(\w+)\s*\(([^)]*)\)(\s+Экспорт)?'
            
            procedures = []
            for line_num, line in enumerate(code.split('\n'), 1):
                match = re.match(pattern, line, re.IGNORECASE)
                if match:
                    proc_type = match.group(1)
                    proc_name = match.group(2)
                    params = match.group(3).strip()
                    is_export = bool(match.group(4))
                    
                    procedures.append({
                        'type': proc_type,
                        'name': proc_name,
                        'params': params if params else '(без параметров)',
                        'export': is_export,
                        'line': line_num,
                        'signature': line.strip()
                    })
            
            if procedures:
                project_key = f"{db_info['project_name']}"
                if project_key not in results:
                    results[project_key] = {}
                
                db_key = f"{db_info['db_name']} ({db_info['db_type']})"
                results[project_key][db_key] = procedures
        
        return results
    
    def get_procedure_code(self, object_name, procedure_name, module_type='Module', project_filter=None, extension_filter=None):
        """
        Получить код конкретной процедуры
        
        Args:
            object_name: Имя объекта
            procedure_name: Имя процедуры/функции
            module_type: Тип модуля
            project_filter: Фильтр по проекту
            extension_filter: Фильтр по расширению/базе
        
        Returns:
            Dict with procedure code from each matching database
        """
        import re
        
        databases = self._get_active_databases(project_filter)
        
        if extension_filter:
            databases = [db for db in databases if db['db_name'].lower() == extension_filter.lower()]
        
        results = {}
        
        for db_info in databases:
            conn = self._get_connection(db_info['db_path'])
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT m.code
                FROM modules m
                JOIN metadata_objects o ON m.object_id = o.id
                WHERE o.name = ? AND m.module_type = ?
                LIMIT 1
            ''', (object_name, module_type))
            
            row = cursor.fetchone()
            if not row:
                continue
            
            code = row['code']
            lines = code.split('\n')
            
            # Поиск процедуры
            start_pattern = rf'^\s*(Функция|Процедура)\s+{re.escape(procedure_name)}\s*\('
            end_keywords = ['КонецФункции', 'КонецПроцедуры']
            
            start_line = None
            proc_type = None
            
            for i, line in enumerate(lines):
                if re.match(start_pattern, line, re.IGNORECASE):
                    start_line = i
                    proc_type = re.match(r'^\s*(Функция|Процедура)', line, re.IGNORECASE).group(1)
                    break
            
            if start_line is None:
                continue
            
            # Поиск конца
            end_line = None
            indent_level = 0
            
            for i in range(start_line + 1, len(lines)):
                line = lines[i].strip()
                
                if re.match(r'^(Функция|Процедура)\s+', line, re.IGNORECASE):
                    indent_level += 1
                elif line in end_keywords or re.match(r'^(КонецФункции|КонецПроцедуры)', line, re.IGNORECASE):
                    if indent_level == 0:
                        end_line = i
                        break
                    else:
                        indent_level -= 1
            
            if end_line is not None:
                procedure_code = '\n'.join(lines[start_line:end_line + 1])
                
                project_key = f"{db_info['project_name']}"
                if project_key not in results:
                    results[project_key] = {}
                
                db_key = f"{db_info['db_name']} ({db_info['db_type']})"
                results[project_key][db_key] = procedure_code
        
        return results