import sqlite3
from pathlib import Path
import sys

# Добавляем корневую папку проекта в путь
sys.path.insert(0, str(Path(__file__).parent.parent))

from shared.project_manager import ProjectManager


def _directive_to_context(line, directive_pattern):
    """
    По строке директивы компиляции 1С возвращает контекст выполнения: Client, Server, ClientOrServer.
    Используются только 4 директивы модулей форм: &НаКлиенте, &НаСервере, &НаСервереБезКонтекста, &НаКлиентеНаСервереБезКонтекста
    (и их английские аналоги AtClient, AtServer, AtServerNoContext, AtClientAtServerNoContext).
    """
    if not line or not directive_pattern.match(line):
        return None
    # Длинные варианты проверяем первыми
    if "AtClientAtServerNoContext" in line or "НаКлиентеНаСервереБезКонтекста" in line:
        return "ClientOrServer"
    if "AtClient" in line or "НаКлиенте" in line:
        return "Client"
    return "Server"


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

    def _require_project_filter(self, project_filter):
        """Требует указания project_filter. Вызвать в начале tools, где фильтр обязателен."""
        if not project_filter or not str(project_filter).strip():
            raise ValueError(
                "project_filter is required. Use list_active_databases to get the list of projects and databases."
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
            })
        return {'projects': list(by_project.values())}

    def search_code(self, query, project_filter=None, extension_filter=None, max_results=10,
                    object_name=None, module_type=None):
        """
        Поиск по коду во всех активных проектах

        Args:
            query: Поисковый запрос
            project_filter: Фильтр по проекту (опционально)
            extension_filter: Фильтр по расширению/базе (опционально)
            max_results: Максимум результатов на базу
            object_name: Фильтр по имени объекта (опционально, можно частичное)
            module_type: Фильтр по типу модуля (опционально): Module, ManagerModule, ObjectModule, FormModule

        Returns:
            Dict grouped by projects
        """
        self._require_project_filter(project_filter)
        databases = self._get_active_databases(project_filter)

        if extension_filter:
            databases = [db for db in databases if db['db_name'].lower() == extension_filter.lower()]

        # Автоматическое определение метода поиска
        # FTS5 не поддерживает спецсимволы в запросах
        special_chars = '.()[]"\''
        use_exact_search = any(char in query for char in special_chars) or bool(object_name) or bool(module_type)

        results = {}

        for db_info in databases:
            conn = self._get_connection(db_info['db_path'])
            cursor = conn.cursor()

            if use_exact_search:
                # Прямой LIKE поиск
                sql = '''
                    SELECT
                        o.name as object_name,
                        m.module_type,
                        m.code,
                        o.object_type
                    FROM modules m
                    JOIN metadata_objects o ON m.object_id = o.id
                    WHERE m.code LIKE ?
                '''
                params = [f'%{query}%']
                if object_name:
                    sql += ' AND o.name LIKE ?'
                    params.append(f'%{object_name}%')
                if module_type:
                    sql += ' AND m.module_type = ?'
                    params.append(module_type)
                sql += ' LIMIT ?'
                params.append(max_results)
                cursor.execute(sql, params)
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
        self._require_project_filter(project_filter)
        databases = self._get_active_databases(project_filter)
        
        if extension_filter:
            databases = [db for db in databases if db['db_name'].lower() == extension_filter.lower()]
        
        results = {}
        
        for db_info in databases:
            conn = self._get_connection(db_info['db_path'])
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT
                    o.id,
                    o.name,
                    o.object_type,
                    o.uuid,
                    o.synonym,
                    o.object_belonging,
                    o.extended_configuration_object,
                    GROUP_CONCAT(DISTINCT m.module_type) as modules
                FROM metadata_objects o
                LEFT JOIN modules m ON o.id = m.object_id AND m.form_id IS NULL
                WHERE o.name LIKE ?
                GROUP BY o.id
            ''', (f'%{name}%',))

            db_results = []
            for row in cursor.fetchall():
                modules = row['modules'].split(',') if row['modules'] else []

                # Получаем список форм объекта
                cursor2 = conn.cursor()
                cursor2.execute('''
                    SELECT form_name FROM forms WHERE object_id = ? ORDER BY form_name
                ''', (row['id'],))
                forms = [r['form_name'] for r in cursor2.fetchall()]

                item = {
                    'name': row['name'],
                    'type': row['object_type'],
                    'uuid': row['uuid'],
                    'synonym': row['synonym'],
                    'modules': modules,
                    'forms': forms,
                }
                if db_info.get('db_type') == 'extension' and row['object_belonging']:
                    item['object_belonging'] = row['object_belonging']
                    if row['extended_configuration_object']:
                        item['extended_configuration_object'] = row['extended_configuration_object']
                db_results.append(item)
            
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
        self._require_project_filter(project_filter)
        databases = self._get_active_databases(project_filter)
        
        if extension_filter:
            databases = [db for db in databases if db['db_name'].lower() == extension_filter.lower()]
        
        results = {}
        
        for db_info in databases:
            conn = self._get_connection(db_info['db_path'])
            cursor = conn.cursor()
            
            if object_type:
                cursor.execute('''
                    SELECT name, object_type, object_belonging, extended_configuration_object
                    FROM metadata_objects
                    WHERE object_type = ?
                    ORDER BY name
                    LIMIT ?
                ''', (object_type, limit))
            else:
                cursor.execute('''
                    SELECT name, object_type, object_belonging, extended_configuration_object
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
                entry = {'name': row['name']}
                if db_info.get('db_type') == 'extension' and row['object_belonging']:
                    entry['object_belonging'] = row['object_belonging']
                    if row['extended_configuration_object']:
                        entry['extended_configuration_object'] = row['extended_configuration_object']
                by_type[obj_type].append(entry)
            
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
        self._require_project_filter(project_filter)
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
        
        self._require_project_filter(project_filter)
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
        # Директивы компиляции модулей форм 1С (4 штуки): см. документацию по управляемым формам.
        # ПослеЗаписиНаСервере — не директива, а типовое имя метода формы; BeforeServer — не директива.
        directive_pattern = re.compile(
            r'^\s*&(НаКлиентеНаСервереБезКонтекста|НаСервереБезКонтекста|НаКлиенте|НаСервере|'
            r'AtClientAtServerNoContext|AtServerNoContext|AtClient|AtServer)\s*$',
            re.IGNORECASE
        )
        
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
                lines = code.split('\n')
                for line_num, line in enumerate(lines, 1):
                    match = re.match(pattern, line, re.IGNORECASE)
                    if match:
                        prev_line = lines[line_num - 2] if line_num >= 2 else ''
                        execution_context = _directive_to_context(prev_line.strip(), directive_pattern)
                        procedures.append({
                            'type': match.group(1),
                            'name': match.group(2),
                            'params': match.group(3).strip() if match.group(3) else '(без параметров)',
                            'export': bool(match.group(4)),
                            'line': line_num,
                            'signature': line.strip(),
                            'execution_context': execution_context,
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
                lines = code.split('\n')
                for line_num, line in enumerate(lines, 1):
                    match = re.match(pattern, line, re.IGNORECASE)
                    if match:
                        prev_line = lines[line_num - 2] if line_num >= 2 else ''
                        execution_context = _directive_to_context(prev_line.strip(), directive_pattern)
                        procedures.append({
                            'type': match.group(1),
                            'name': match.group(2),
                            'params': match.group(3).strip() if match.group(3) else '(без параметров)',
                            'export': bool(match.group(4)),
                            'line': line_num,
                            'signature': line.strip(),
                            'execution_context': execution_context,
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
        
        self._require_project_filter(project_filter)
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
            
            # Включить строку директивы компиляции 1С (4 директивы модулей форм), если она над процедурой
            directive_pattern = re.compile(
                r'^\s*&(НаКлиентеНаСервереБезКонтекста|НаСервереБезКонтекста|НаКлиенте|НаСервере|'
                r'AtClientAtServerNoContext|AtServerNoContext|AtClient|AtServer)\s*$',
                re.IGNORECASE
            )
            if start_line > 0 and directive_pattern.match(lines[start_line - 1].strip()):
                start_line = start_line - 1
            
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
        self._require_project_filter(project_filter)
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
                    o.object_belonging,
                    o.extended_configuration_object,
                    f.form_name,
                    f.uuid,
                    f.form_kind,
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
                item = {
                    'object_name': row['object_name'],
                    'object_type': row['object_type'],
                    'form_name': row['form_name'],
                    'uuid': row['uuid'],
                    'form_kind': row['form_kind'],
                    'properties': properties,
                    'attributes_count': row['attributes_count'],
                    'commands_count': row['commands_count'],
                    'items_count': row['items_count']
                }
                if db_info.get('db_type') == 'extension' and row['object_belonging']:
                    item['object_belonging'] = row['object_belonging']
                    if row['extended_configuration_object']:
                        item['extended_configuration_object'] = row['extended_configuration_object']
                db_results.append(item)
            
            if db_results:
                project_key = f"{db_info['project_name']}"
                if project_key not in results:
                    results[project_key] = {}
                
                db_key = f"{db_info['db_name']} ({db_info['db_type']})"
                results[project_key][db_key] = db_results
        
        return results
    
    def find_form_element(self, element_name=None, data_path=None, object_name=None, project_filter=None, extension_filter=None):
        """
        Найти формы, содержащие элемент по имени элемента или по связи с данными (ПутьКДанным / data_path).

        Args:
            element_name: Имя элемента формы (можно частичное). Необязательно, если задан data_path.
            data_path: Путь к данным (реквизит формы) — поиск по полю DataPath/ПутьКДанным. Необязательно, если задан element_name.
            object_name: Имя объекта для фильтрации (опционально, можно частичное)
            project_filter: Фильтр по проекту
            extension_filter: Фильтр по расширению/базе

        Returns:
            Dict grouped by projects
        """
        if not element_name and not data_path:
            raise ValueError("Укажите element_name и/или data_path")
        self._require_project_filter(project_filter)
        databases = self._get_active_databases(project_filter)

        if extension_filter:
            databases = [db for db in databases if db['db_name'].lower() == extension_filter.lower()]

        results = {}

        for db_info in databases:
            conn = self._get_connection(db_info['db_path'])
            cursor = conn.cursor()

            conditions = []
            params = []
            if element_name:
                conditions.append('fi.name LIKE ?')
                params.append(f'%{element_name}%')
            if data_path:
                conditions.append('fi.data_path LIKE ?')
                params.append(f'%{data_path}%')

            query = '''
                SELECT DISTINCT
                    o.name as object_name,
                    o.object_type,
                    o.object_belonging,
                    o.extended_configuration_object,
                    f.form_name,
                    fi.name as element_name,
                    fi.item_type,
                    fi.data_path,
                    fi.title,
                    fi.visible,
                    fi.enabled
                FROM form_items fi
                JOIN forms f ON fi.form_id = f.id
                JOIN metadata_objects o ON f.object_id = o.id
                WHERE ('''
            query += ' OR '.join(conditions)
            query += ')'

            if object_name:
                query += ' AND o.name LIKE ?'
                params.append(f'%{object_name}%')

            query += ' ORDER BY o.name, f.form_name'

            cursor.execute(query, params)
            
            db_results = []
            for row in cursor.fetchall():
                item = {
                    'object_name': row['object_name'],
                    'object_type': row['object_type'],
                    'form_name': row['form_name'],
                    'element_name': row['element_name'],
                    'element_type': row['item_type'],
                    'data_path': row['data_path'],
                    'title': row['title'],
                    'visible': row['visible'] if row['visible'] is not None else None,
                    'enabled': row['enabled'] if row['enabled'] is not None else None,
                }
                if db_info.get('db_type') == 'extension' and row['object_belonging']:
                    item['object_belonging'] = row['object_belonging']
                    if row['extended_configuration_object']:
                        item['extended_configuration_object'] = row['extended_configuration_object']
                db_results.append(item)
            
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
        self._require_project_filter(project_filter)
        databases = self._get_active_databases(project_filter)
        
        if extension_filter:
            databases = [db for db in databases if db['db_name'].lower() == extension_filter.lower()]
        
        results = {}
        
        for db_info in databases:
            conn = self._get_connection(db_info['db_path'])
            cursor = conn.cursor()
            
            # Получаем форму (form_kind, object_belonging для extension)
            cursor.execute('''
                SELECT f.id, f.uuid, f.form_kind, f.properties_json,
                       o.object_belonging, o.extended_configuration_object
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
            
            # Получаем команды (без picture)
            cursor.execute('''
                SELECT name, title, action, shortcut, representation
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
            
            # Получаем элементы UI (visible, enabled вместо properties_json)
            cursor.execute('''
                SELECT id, parent_id, name, item_type, data_path, title, visible, enabled
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
                    'title': row['title'],
                    'visible': row['visible'] if row['visible'] is not None else None,
                    'enabled': row['enabled'] if row['enabled'] is not None else None,
                }
                items.append(item)
            
            # Собираем результат
            form_structure = {
                'uuid': form_row['uuid'],
                'form_kind': form_row['form_kind'],
                'properties': json.loads(form_row['properties_json']) if form_row['properties_json'] else {},
                'events': events,
                'attributes': attributes,
                'commands': commands,
                'items': items
            }
            if db_info.get('db_type') == 'extension' and form_row['object_belonging']:
                form_structure['object_belonging'] = form_row['object_belonging']
                if form_row['extended_configuration_object']:
                    form_structure['extended_configuration_object'] = form_row['extended_configuration_object']
            
            project_key = f"{db_info['project_name']}"
            if project_key not in results:
                results[project_key] = {}
            
            db_key = f"{db_info['db_name']} ({db_info['db_type']})"
            results[project_key][db_key] = form_structure
        
        return results
    
    def search_form_properties(self, property_name, property_value=None, project_filter=None, extension_filter=None):
        """
        Поиск форм по свойствам элементов. Поддерживаются только свойства Visible и Enabled.

        Args:
            property_name: Имя свойства — только "Visible" или "Enabled"
            property_value: Значение (опционально): "true"/"false" или 1/0
            project_filter: Фильтр по проекту (обязателен)
            extension_filter: Фильтр по расширению/базе

        Returns:
            Dict с найденными элементами
        """
        if property_name not in ('Visible', 'Enabled'):
            raise ValueError("Поддерживаются только свойства Visible и Enabled. Укажите property_name 'Visible' или 'Enabled'.")
        self._require_project_filter(project_filter)
        databases = self._get_active_databases(project_filter)
        
        if extension_filter:
            databases = [db for db in databases if db['db_name'].lower() == extension_filter.lower()]
        
        results = {}
        col = 'visible' if property_name == 'Visible' else 'enabled'
        want_val = None
        if property_value is not None:
            pv = str(property_value).strip().lower()
            if pv in ('true', '1', 'да', 'yes'):
                want_val = 1
            elif pv in ('false', '0', 'нет', 'no'):
                want_val = 0
            else:
                want_val = 1 if pv else 0  # fallback

        for db_info in databases:
            conn = self._get_connection(db_info['db_path'])
            cursor = conn.cursor()
            if want_val is not None:
                cursor.execute('''
                    SELECT 
                        o.name as object_name,
                        o.object_type,
                        f.form_name,
                        fi.name as element_name,
                        fi.item_type,
                        fi.data_path,
                        fi.visible,
                        fi.enabled
                    FROM form_items fi
                    JOIN forms f ON fi.form_id = f.id
                    JOIN metadata_objects o ON f.object_id = o.id
                    WHERE fi.%s = ?
                ''' % col, (want_val,))
            else:
                cursor.execute('''
                    SELECT 
                        o.name as object_name,
                        o.object_type,
                        f.form_name,
                        fi.name as element_name,
                        fi.item_type,
                        fi.data_path,
                        fi.visible,
                        fi.enabled
                    FROM form_items fi
                    JOIN forms f ON fi.form_id = f.id
                    JOIN metadata_objects o ON f.object_id = o.id
                    WHERE fi.%s IS NOT NULL
                ''' % col)
            
            db_results = []
            for row in cursor.fetchall():
                val = row['visible'] if property_name == 'Visible' else row['enabled']
                db_results.append({
                    'object_name': row['object_name'],
                    'object_type': row['object_type'],
                    'form_name': row['form_name'],
                    'element_name': row['element_name'],
                    'element_type': row['item_type'],
                    'data_path': row['data_path'],
                    'property_name': property_name,
                    'property_value': val,
                })

            if db_results:
                project_key = f"{db_info['project_name']}"
                if project_key not in results:
                    results[project_key] = {}

                db_key = f"{db_info['db_name']} ({db_info['db_type']})"
                results[project_key][db_key] = db_results

        return results

    def get_object_structure(self, object_name, project_filter=None, extension_filter=None):
        """
        Получить полную структуру метаданных объекта 1С:
        реквизиты, табличные части, измерения/ресурсы регистров, значения перечислений.

        Args:
            object_name: Имя объекта (частичное совпадение)
            project_filter: Фильтр по проекту (опционально)
            extension_filter: Фильтр по расширению/базе (опционально)

        Returns:
            Dict сгруппированный по проектам/базам
        """
        self._require_project_filter(project_filter)
        databases = self._get_active_databases(project_filter)
        if extension_filter:
            databases = [db for db in databases if db['db_name'].lower() == extension_filter.lower()]

        results = {}

        for db_info in databases:
            conn = self._get_connection(db_info['db_path'])
            cursor = conn.cursor()

            cursor.execute('''
                SELECT id, name, object_type, uuid, synonym, comment, object_belonging, extended_configuration_object
                FROM metadata_objects
                WHERE name LIKE ?
                LIMIT 1
            ''', (f'%{object_name}%',))

            obj_row = cursor.fetchone()
            if not obj_row:
                continue

            object_id = obj_row['id']

            # Реквизиты, измерения, ресурсы
            cursor.execute('''
                SELECT name, attribute_type, title, is_standard, standard_type, section
                FROM attributes
                WHERE object_id = ?
                ORDER BY section, is_standard DESC, name
            ''', (object_id,))

            attributes_by_section = {}
            for row in cursor.fetchall():
                section = row['section'] or 'Attribute'
                if section not in attributes_by_section:
                    attributes_by_section[section] = []
                attributes_by_section[section].append({
                    'name': row['name'],
                    'type': row['attribute_type'],
                    'title': row['title'],
                    'is_standard': bool(row['is_standard']),
                    'standard_type': row['standard_type'],
                })

            # Табличные части с колонками
            cursor.execute('''
                SELECT tabular_section_name, tabular_section_title,
                       column_name, column_type, title
                FROM tabular_section_columns
                WHERE object_id = ?
                ORDER BY tabular_section_name, column_name
            ''', (object_id,))

            tabular_sections = {}
            for row in cursor.fetchall():
                ts_name = row['tabular_section_name']
                if ts_name not in tabular_sections:
                    tabular_sections[ts_name] = {
                        'name': ts_name,
                        'title': row['tabular_section_title'],
                        'columns': [],
                    }
                tabular_sections[ts_name]['columns'].append({
                    'name': row['column_name'],
                    'type': row['column_type'],
                    'title': row['title'],
                })

            # Значения перечислений (для extension — object_belonging)
            cursor.execute('''
                SELECT name, enum_order, title, object_belonging, extended_configuration_object
                FROM enum_values
                WHERE object_id = ?
                ORDER BY enum_order, name
            ''', (object_id,))

            enum_values = []
            for row in cursor.fetchall():
                ev = {'name': row['name'], 'enum_order': row['enum_order'], 'title': row['title']}
                if db_info.get('db_type') == 'extension' and row['object_belonging']:
                    ev['object_belonging'] = row['object_belonging']
                    if row['extended_configuration_object']:
                        ev['extended_configuration_object'] = row['extended_configuration_object']
                enum_values.append(ev)

            # Модули (краткий список)
            cursor.execute('''
                SELECT module_type FROM modules
                WHERE object_id = ? AND form_id IS NULL
            ''', (object_id,))
            modules = [row['module_type'] for row in cursor.fetchall()]

            # Формы (краткий список)
            cursor.execute('''
                SELECT form_name FROM forms
                WHERE object_id = ?
            ''', (object_id,))
            forms = [row['form_name'] for row in cursor.fetchall()]

            structure = {
                'name': obj_row['name'],
                'type': obj_row['object_type'],
                'uuid': obj_row['uuid'],
                'synonym': obj_row['synonym'],
                'comment': obj_row['comment'],
                'attributes': attributes_by_section.get('Attribute', []),
                'dimensions': attributes_by_section.get('Dimension', []),
                'resources': attributes_by_section.get('Resource', []),
                'tabular_sections': list(tabular_sections.values()),
                'enum_values': enum_values,
                'modules': modules,
                'forms': forms,
            }
            if db_info.get('db_type') == 'extension' and obj_row['object_belonging']:
                structure['object_belonging'] = obj_row['object_belonging']
                if obj_row['extended_configuration_object']:
                    structure['extended_configuration_object'] = obj_row['extended_configuration_object']

            project_key = db_info['project_name']
            if project_key not in results:
                results[project_key] = {}

            db_key = f"{db_info['db_name']} ({db_info['db_type']})"
            results[project_key][db_key] = structure

        return results

    def find_attribute(self, attribute_name, project_filter=None, extension_filter=None, max_results=20):
        """
        Поиск реквизита по имени во всех объектах метаданных.

        Args:
            attribute_name: Имя реквизита (частичное совпадение)
            project_filter: Фильтр по проекту (опционально)
            extension_filter: Фильтр по расширению/базе (опционально)
            max_results: Максимум результатов на базу (по умолчанию 20)

        Returns:
            Dict сгруппированный по проектам/базам
        """
        self._require_project_filter(project_filter)
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
                    o.object_belonging,
                    o.extended_configuration_object,
                    a.name as attr_name,
                    a.attribute_type,
                    a.title,
                    a.is_standard,
                    a.section
                FROM attributes a
                JOIN metadata_objects o ON a.object_id = o.id
                WHERE a.name LIKE ?
                ORDER BY o.object_type, o.name, a.section, a.name
                LIMIT ?
            ''', (f'%{attribute_name}%', max_results))

            db_results = []
            for row in cursor.fetchall():
                item = {
                    'object_name': row['object_name'],
                    'object_type': row['object_type'],
                    'attribute_name': row['attr_name'],
                    'attribute_type': row['attribute_type'],
                    'title': row['title'],
                    'is_standard': bool(row['is_standard']),
                    'section': row['section'],
                }
                if db_info.get('db_type') == 'extension' and row['object_belonging']:
                    item['object_belonging'] = row['object_belonging']
                    if row['extended_configuration_object']:
                        item['extended_configuration_object'] = row['extended_configuration_object']
                db_results.append(item)

            if db_results:
                project_key = db_info['project_name']
                if project_key not in results:
                    results[project_key] = {}
                db_key = f"{db_info['db_name']} ({db_info['db_type']})"
                results[project_key][db_key] = db_results

        return results