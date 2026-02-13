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
        
        # Автоматическое определение метода поиска
        # FTS5 не поддерживает спецсимволы в запросах
        special_chars = '.()[]"\''
        use_exact_search = any(char in query for char in special_chars)
        
        results = {}
        
        for db_info in databases:
            conn = self._get_connection(db_info['db_path'])
            cursor = conn.cursor()
            
            if use_exact_search:
                # Прямой LIKE поиск для запросов со спецсимволами
                cursor.execute('''
                    SELECT 
                        o.name as object_name,
                        m.module_type,
                        m.code,
                        o.object_type
                    FROM modules m
                    JOIN metadata_objects o ON m.object_id = o.id
                    WHERE m.code LIKE ?
                    LIMIT ?
                ''', (f'%{query}%', max_results))
            else:
                # FTS5 полнотекстовый поиск (быстрее, но не работает со спецсимволами)
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
    
    def get_module_code(self, object_name, module_type='Module', form_name=None, project_filter=None, extension_filter=None):
        """
        Получить код модуля
        
        Args:
            object_name: Имя объекта
            module_type: Тип модуля (Module, ManagerModule, ObjectModule, FormModule)
            form_name: Имя формы (обязательно для FormModule)
            project_filter: Фильтр по проекту
            extension_filter: Фильтр по расширению/базе
        
        Returns:
            Dict with code from each matching database
        """
        # Валидация параметров
        if module_type == 'FormModule' and not form_name:
            raise ValueError("form_name is required when module_type is 'FormModule'")
        
        if form_name and module_type != 'FormModule':
            raise ValueError("form_name can only be used with module_type='FormModule'")
        
        databases = self._get_active_databases(project_filter)
        
        if extension_filter:
            databases = [db for db in databases if db['db_name'].lower() == extension_filter.lower()]
        
        results = {}
        
        if module_type == 'FormModule':
            # Модуль формы
            for db_info in databases:
                conn = self._get_connection(db_info['db_path'])
                cursor = conn.cursor()
                
                cursor.execute('''
                    SELECT m.code
                    FROM modules m
                    JOIN forms f ON m.form_id = f.id
                    JOIN metadata_objects o ON f.object_id = o.id
                    WHERE o.name = ? AND f.form_name = ? AND m.module_type = 'FormModule'
                    LIMIT 1
                ''', (object_name, form_name))
                
                row = cursor.fetchone()
                if row:
                    project_key = f"{db_info['project_name']}"
                    if project_key not in results:
                        results[project_key] = {}
                    
                    db_key = f"{db_info['db_name']} ({db_info['db_type']})"
                    results[project_key][db_key] = row['code']
        else:
            # Модуль объекта
            for db_info in databases:
                conn = self._get_connection(db_info['db_path'])
                cursor = conn.cursor()
                
                cursor.execute('''
                    SELECT m.code
                    FROM modules m
                    JOIN metadata_objects o ON m.object_id = o.id
                    WHERE o.name = ? AND m.module_type = ? AND m.form_id IS NULL
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
    
    def get_module_procedures(self, object_name, module_type='Module', form_name=None, project_filter=None, extension_filter=None):
        """
        Получить список процедур и функций модуля
        
        Args:
            object_name: Имя объекта
            module_type: Тип модуля (Module, ManagerModule, ObjectModule, FormModule)
            form_name: Имя формы (обязательно для FormModule)
            project_filter: Фильтр по проекту
            extension_filter: Фильтр по расширению/базе
        
        Returns:
            Dict with procedures from each matching database
        """
        import re
        
        # Валидация параметров
        if module_type == 'FormModule' and not form_name:
            raise ValueError("form_name is required when module_type is 'FormModule'")
        
        if form_name and module_type != 'FormModule':
            raise ValueError("form_name can only be used with module_type='FormModule'")
        
        databases = self._get_active_databases(project_filter)
        
        if extension_filter:
            databases = [db for db in databases if db['db_name'].lower() == extension_filter.lower()]
        
        results = {}
        pattern = r'^\s*(Процедура|Функция)\s+([А-Яа-яA-Za-z0-9_]+)\s*\((.*?)\)\s*(Экспорт)?\s*$'
        
        if module_type == 'FormModule':
            # Модуль формы
            for db_info in databases:
                conn = self._get_connection(db_info['db_path'])
                cursor = conn.cursor()
                
                cursor.execute('''
                    SELECT m.code
                    FROM modules m
                    JOIN forms f ON m.form_id = f.id
                    JOIN metadata_objects o ON f.object_id = o.id
                    WHERE o.name = ? AND f.form_name = ? AND m.module_type = 'FormModule'
                    LIMIT 1
                ''', (object_name, form_name))
                
                row = cursor.fetchone()
                if not row:
                    continue
                
                code = row['code']
                
                # Парсинг процедур и функций
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
        else:
            # Модуль объекта
            for db_info in databases:
                conn = self._get_connection(db_info['db_path'])
                cursor = conn.cursor()
                
                cursor.execute('''
                    SELECT m.code
                    FROM modules m
                    JOIN metadata_objects o ON m.object_id = o.id
                    WHERE o.name = ? AND m.module_type = ? AND m.form_id IS NULL
                    LIMIT 1
                ''', (object_name, module_type))
                
                row = cursor.fetchone()
                if not row:
                    continue
                
                code = row['code']
                
                # Парсинг процедур и функций
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
    
    def get_procedure_code(self, object_name, procedure_name, module_type='Module', form_name=None, project_filter=None, extension_filter=None):
        """
        Получить код конкретной процедуры
        
        Args:
            object_name: Имя объекта
            procedure_name: Имя процедуры/функции
            module_type: Тип модуля (Module, ManagerModule, ObjectModule, FormModule)
            form_name: Имя формы (обязательно для FormModule)
            project_filter: Фильтр по проекту
            extension_filter: Фильтр по расширению/базе
        
        Returns:
            Dict with procedure code from each matching database
        """
        import re
        
        # Валидация параметров
        if module_type == 'FormModule' and not form_name:
            raise ValueError("form_name is required when module_type is 'FormModule'")
        
        if form_name and module_type != 'FormModule':
            raise ValueError("form_name can only be used with module_type='FormModule'")
        
        databases = self._get_active_databases(project_filter)
        
        if extension_filter:
            databases = [db for db in databases if db['db_name'].lower() == extension_filter.lower()]
        
        results = {}
        
        # Общая логика поиска процедуры
        def extract_procedure(code, proc_name):
            lines = code.split('\n')
            
            # Паттерны для поиска (русский и английский)
            start_pattern = rf'^\s*(Функция|Процедура|Function|Procedure)\s+{re.escape(proc_name)}\s*\('
            end_pattern = r'^\s*(КонецФункции|КонецПроцедуры|EndFunction|EndProcedure)\s*$'
            
            start_line = None
            
            # Ищем начало процедуры
            for i, line in enumerate(lines):
                if re.match(start_pattern, line, re.IGNORECASE):
                    start_line = i
                    break
            
            if start_line is None:
                return None
            
            # Ищем конец процедуры (первое вхождение КонецПроцедуры/КонецФункции)
            end_line = None
            for i in range(start_line + 1, len(lines)):
                if re.match(end_pattern, lines[i], re.IGNORECASE):
                    end_line = i
                    break
            
            if end_line is not None:
                return '\n'.join(lines[start_line:end_line + 1])
            
            return None
        
        if module_type == 'FormModule':
            # Модуль формы
            for db_info in databases:
                conn = self._get_connection(db_info['db_path'])
                cursor = conn.cursor()
                
                cursor.execute('''
                    SELECT m.code
                    FROM modules m
                    JOIN forms f ON m.form_id = f.id
                    JOIN metadata_objects o ON f.object_id = o.id
                    WHERE o.name = ? AND f.form_name = ? AND m.module_type = 'FormModule'
                    LIMIT 1
                ''', (object_name, form_name))
                
                row = cursor.fetchone()
                if not row:
                    continue
                
                procedure_code = extract_procedure(row['code'], procedure_name)
                
                if procedure_code:
                    project_key = f"{db_info['project_name']}"
                    if project_key not in results:
                        results[project_key] = {}
                    
                    db_key = f"{db_info['db_name']} ({db_info['db_type']})"
                    results[project_key][db_key] = procedure_code
        else:
            # Модуль объекта
            for db_info in databases:
                conn = self._get_connection(db_info['db_path'])
                cursor = conn.cursor()
                
                cursor.execute('''
                    SELECT m.code
                    FROM modules m
                    JOIN metadata_objects o ON m.object_id = o.id
                    WHERE o.name = ? AND m.module_type = ? AND m.form_id IS NULL
                    LIMIT 1
                ''', (object_name, module_type))
                
                row = cursor.fetchone()
                if not row:
                    continue
                
                procedure_code = extract_procedure(row['code'], procedure_name)
                
                if procedure_code:
                    project_key = f"{db_info['project_name']}"
                    if project_key not in results:
                        results[project_key] = {}
                    
                    db_key = f"{db_info['db_name']} ({db_info['db_type']})"
                    results[project_key][db_key] = procedure_code
        
        return results
    
    def find_form(self, object_name=None, form_name=None, project_filter=None, extension_filter=None):
        """
        Поиск форм по имени объекта и/или имени формы
        
        Args:
            object_name: Имя объекта (опционально, можно частичное)
            form_name: Имя формы (опционально, можно частичное)
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
            
            query = '''
                SELECT 
                    o.name as object_name,
                    o.object_type,
                    f.form_name,
                    f.uuid,
                    f.properties_json,
                    (SELECT COUNT(*) FROM form_attributes WHERE form_id = f.id) as attributes_count,
                    (SELECT COUNT(*) FROM form_commands WHERE form_id = f.id) as commands_count,
                    (SELECT COUNT(*) FROM form_items WHERE form_id = f.id) as items_count
                FROM forms f
                JOIN metadata_objects o ON f.object_id = o.id
                WHERE 1=1
            '''
            params = []
            
            if object_name:
                query += ' AND o.name LIKE ?'
                params.append(f'%{object_name}%')
            
            if form_name:
                query += ' AND f.form_name LIKE ?'
                params.append(f'%{form_name}%')
            
            cursor.execute(query, params)
            
            db_results = []
            for row in cursor.fetchall():
                import json
                properties = json.loads(row['properties_json']) if row['properties_json'] else {}
                
                db_results.append({
                    'object_name': row['object_name'],
                    'object_type': row['object_type'],
                    'form_name': row['form_name'],
                    'uuid': row['uuid'],
                    'properties': properties,
                    'attributes_count': row['attributes_count'],
                    'commands_count': row['commands_count'],
                    'items_count': row['items_count']
                })
            
            if db_results:
                project_key = f"{db_info['project_name']}"
                if project_key not in results:
                    results[project_key] = {}
                
                db_key = f"{db_info['db_name']} ({db_info['db_type']})"
                results[project_key][db_key] = db_results
        
        return results
    
    def find_form_element(self, element_name, project_filter=None, extension_filter=None):
        """
        Найти все формы, содержащие элемент с указанным именем
        
        Args:
            element_name: Имя элемента (можно частичное)
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
                SELECT DISTINCT
                    o.name as object_name,
                    o.object_type,
                    f.form_name,
                    fi.name as element_name,
                    fi.item_type,
                    fi.data_path,
                    fi.title,
                    fi.properties_json
                FROM form_items fi
                JOIN forms f ON fi.form_id = f.id
                JOIN metadata_objects o ON f.object_id = o.id
                WHERE fi.name LIKE ?
                ORDER BY o.name, f.form_name
            ''', (f'%{element_name}%',))
            
            db_results = []
            for row in cursor.fetchall():
                import json
                properties = json.loads(row['properties_json']) if row['properties_json'] else {}
                
                db_results.append({
                    'object_name': row['object_name'],
                    'object_type': row['object_type'],
                    'form_name': row['form_name'],
                    'element_name': row['element_name'],
                    'element_type': row['item_type'],
                    'data_path': row['data_path'],
                    'title': row['title'],
                    'properties': properties
                })
            
            if db_results:
                project_key = f"{db_info['project_name']}"
                if project_key not in results:
                    results[project_key] = {}
                
                db_key = f"{db_info['db_name']} ({db_info['db_type']})"
                results[project_key][db_key] = db_results
        
        return results
    
    def get_form_structure(self, object_name, form_name, project_filter=None, extension_filter=None):
        """
        Получить полную структуру формы
        
        Args:
            object_name: Имя объекта
            form_name: Имя формы
            project_filter: Фильтр по проекту
            extension_filter: Фильтр по расширению/базе
        
        Returns:
            Dict с полной структурой формы
        """
        databases = self._get_active_databases(project_filter)
        
        if extension_filter:
            databases = [db for db in databases if db['db_name'].lower() == extension_filter.lower()]
        
        results = {}
        
        for db_info in databases:
            conn = self._get_connection(db_info['db_path'])
            cursor = conn.cursor()
            
            # Получаем форму
            cursor.execute('''
                SELECT f.id, f.uuid, f.properties_json
                FROM forms f
                JOIN metadata_objects o ON f.object_id = o.id
                WHERE o.name = ? AND f.form_name = ?
                LIMIT 1
            ''', (object_name, form_name))
            
            form_row = cursor.fetchone()
            if not form_row:
                continue
            
            import json
            form_id = form_row['id']
            
            # Получаем реквизиты
            cursor.execute('''
                SELECT name, type, title, is_main, columns_json, query_text
                FROM form_attributes
                WHERE form_id = ?
            ''', (form_id,))
            
            attributes = []
            for row in cursor.fetchall():
                attr = {
                    'name': row['name'],
                    'type': row['type'],
                    'title': row['title'],
                    'is_main': bool(row['is_main'])
                }
                if row['columns_json']:
                    attr['columns'] = json.loads(row['columns_json'])
                if row['query_text']:
                    attr['query_text'] = row['query_text']
                attributes.append(attr)
            
            # Получаем команды
            cursor.execute('''
                SELECT name, title, action, shortcut, picture, representation
                FROM form_commands
                WHERE form_id = ?
            ''', (form_id,))
            
            commands = [dict(row) for row in cursor.fetchall()]
            
            # Получаем события формы
            cursor.execute('''
                SELECT event_name, handler, call_type
                FROM form_events
                WHERE form_id = ?
            ''', (form_id,))
            
            events = [dict(row) for row in cursor.fetchall()]
            
            # Получаем элементы UI
            cursor.execute('''
                SELECT id, parent_id, name, item_type, data_path, title, properties_json
                FROM form_items
                WHERE form_id = ?
                ORDER BY id
            ''', (form_id,))
            
            items = []
            for row in cursor.fetchall():
                item = {
                    'name': row['name'],
                    'type': row['item_type'],
                    'data_path': row['data_path'],
                    'title': row['title']
                }
                if row['properties_json']:
                    item['properties'] = json.loads(row['properties_json'])
                items.append(item)
            
            # Собираем результат
            form_structure = {
                'uuid': form_row['uuid'],
                'properties': json.loads(form_row['properties_json']) if form_row['properties_json'] else {},
                'events': events,
                'attributes': attributes,
                'commands': commands,
                'items': items
            }
            
            project_key = f"{db_info['project_name']}"
            if project_key not in results:
                results[project_key] = {}
            
            db_key = f"{db_info['db_name']} ({db_info['db_type']})"
            results[project_key][db_key] = form_structure
        
        return results
    
    def search_form_properties(self, property_name, property_value=None, project_filter=None, extension_filter=None):
        """
        Поиск форм по свойствам элементов
        
        Args:
            property_name: Имя свойства (например, "Visible")
            property_value: Значение свойства (опционально, например "false")
            project_filter: Фильтр по проекту
            extension_filter: Фильтр по расширению/базе
        
        Returns:
            Dict с найденными элементами
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
                    o.object_type,
                    f.form_name,
                    fi.name as element_name,
                    fi.item_type,
                    fi.data_path,
                    fi.properties_json
                FROM form_items fi
                JOIN forms f ON fi.form_id = f.id
                JOIN metadata_objects o ON f.object_id = o.id
                WHERE fi.properties_json IS NOT NULL
            ''')
            
            import json
            db_results = []
            
            for row in cursor.fetchall():
                try:
                    properties = json.loads(row['properties_json'])
                    
                    # Проверяем наличие свойства
                    if property_name in properties:
                        # Если указано значение - проверяем его
                        if property_value is None or str(properties[property_name]).lower() == property_value.lower():
                            db_results.append({
                                'object_name': row['object_name'],
                                'object_type': row['object_type'],
                                'form_name': row['form_name'],
                                'element_name': row['element_name'],
                                'element_type': row['item_type'],
                                'data_path': row['data_path'],
                                'property_name': property_name,
                                'property_value': properties[property_name],
                                'all_properties': properties
                            })
                except:
                    continue
            
            if db_results:
                project_key = f"{db_info['project_name']}"
                if project_key not in results:
                    results[project_key] = {}
                
                db_key = f"{db_info['db_name']} ({db_info['db_type']})"
                results[project_key][db_key] = db_results
        
        return results