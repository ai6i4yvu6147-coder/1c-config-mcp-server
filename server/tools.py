import sqlite3
import json
from pathlib import Path


class ConfigurationTools:
    """Инструменты для работы с конфигурацией 1С"""
    
    def __init__(self, db_path):
        self.db_path = Path(db_path)
        self.conn = None
    
    def connect(self):
        """Подключение к БД"""
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
    
    def close(self):
        """Закрытие соединения"""
        if self.conn:
            self.conn.close()
    
    def search_code(self, query, max_results=10):
        """
        Полнотекстовый поиск по коду
        
        Args:
            query: Строка поиска
            max_results: Максимум результатов
        
        Returns:
            list: Список найденных фрагментов кода
        """
        cursor = self.conn.cursor()
        
        # Поиск через FTS5
        cursor.execute('''
            SELECT 
                m.id,
                o.name as object_name,
                m.module_type,
                m.code
            FROM modules m
            JOIN metadata_objects o ON m.object_id = o.id
            WHERE m.id IN (
                SELECT rowid FROM code_search WHERE code_search MATCH ?
            )
            LIMIT ?
        ''', (query, max_results))
        
        results = []
        for row in cursor.fetchall():
            # Находим контекст вокруг найденного текста
            code = row['code']
            query_lower = query.lower()
            code_lower = code.lower()
            
            # Простой поиск позиции
            pos = code_lower.find(query_lower)
            if pos == -1:
                # Поиск первого слова из запроса
                words = query_lower.split()
                if words:
                    pos = code_lower.find(words[0])
            
            if pos != -1:
                # Вырезаем контекст вокруг найденного
                start = max(0, pos - 50)
                end = min(len(code), pos + len(query) + 50)
                snippet = code[start:end].strip()
                if start > 0:
                    snippet = "..." + snippet
                if end < len(code):
                    snippet = snippet + "..."
            else:
                snippet = code[:100] + "..."
            
            results.append({
                'object': row['object_name'],
                'module': row['module_type'],
                'snippet': snippet
            })
        
        return results
    
    def find_object(self, name):
        """
        Поиск объекта метаданных по имени
        
        Args:
            name: Имя объекта
        
        Returns:
            dict: Информация об объекте
        """
        cursor = self.conn.cursor()
        
        cursor.execute('''
            SELECT 
                id, uuid, object_type, name, synonym, comment
            FROM metadata_objects
            WHERE name LIKE ?
            LIMIT 1
        ''', (f'%{name}%',))
        
        row = cursor.fetchone()
        if not row:
            return None
        
        # Получаем модули объекта
        cursor.execute('''
            SELECT module_type, LENGTH(code) as code_length
            FROM modules
            WHERE object_id = ?
        ''', (row['id'],))
        
        modules = []
        for mod_row in cursor.fetchall():
            modules.append({
                'type': mod_row['module_type'],
                'lines': mod_row['code_length'] // 50  # примерное количество строк
            })
        
        return {
            'name': row['name'],
            'type': row['object_type'],
            'uuid': row['uuid'],
            'synonym': row['synonym'],
            'modules': modules
        }
    
    def list_objects(self, object_type=None, limit=50):
        """
        Список объектов метаданных
        
        Args:
            object_type: Тип объекта (Catalog, Document и т.д.) или None для всех
            limit: Максимум результатов
        
        Returns:
            list: Список объектов
        """
        cursor = self.conn.cursor()
        
        if object_type:
            cursor.execute('''
                SELECT name, object_type, synonym
                FROM metadata_objects
                WHERE object_type = ?
                ORDER BY name
                LIMIT ?
            ''', (object_type, limit))
        else:
            cursor.execute('''
                SELECT name, object_type, synonym
                FROM metadata_objects
                ORDER BY object_type, name
                LIMIT ?
            ''', (limit,))
        
        results = []
        for row in cursor.fetchall():
            results.append({
                'name': row['name'],
                'type': row['object_type'],
                'synonym': row['synonym']
            })
        
        return results
    
    def get_module_code(self, object_name, module_type='Module'):
        """
        Получить код модуля объекта
        
        Args:
            object_name: Имя объекта
            module_type: Тип модуля
        
        Returns:
            str: Код модуля
        """
        cursor = self.conn.cursor()
        
        cursor.execute('''
            SELECT m.code
            FROM modules m
            JOIN metadata_objects o ON m.object_id = o.id
            WHERE o.name = ? AND m.module_type = ?
            LIMIT 1
        ''', (object_name, module_type))
        
        row = cursor.fetchone()
        return row['code'] if row else None
    
    def get_module_procedures(self, object_name, module_type='Module'):
        """
        Получить список процедур и функций модуля (только сигнатуры)
        
        Args:
            object_name: Имя объекта
            module_type: Тип модуля
        
        Returns:
            list: Список процедур/функций
        """
        import re
        
        code = self.get_module_code(object_name, module_type)
        if not code:
            return None
        
        # Регулярное выражение для поиска процедур и функций
        # Ищем: Функция/Процедура ИмяПроцедуры(параметры) [Экспорт]
        pattern = r'^\s*(Функция|Процедура)\s+(\w+)\s*\(([^)]*)\)(\s+Экспорт)?'
        
        procedures = []
        for line_num, line in enumerate(code.split('\n'), 1):
            match = re.match(pattern, line, re.IGNORECASE)
            if match:
                proc_type = match.group(1)  # Функция или Процедура
                proc_name = match.group(2)  # Имя
                params = match.group(3).strip()  # Параметры
                is_export = bool(match.group(4))  # Экспорт?
                
                procedures.append({
                    'type': proc_type,
                    'name': proc_name,
                    'params': params if params else '(без параметров)',
                    'export': is_export,
                    'line': line_num,
                    'signature': line.strip()
                })
        
        return procedures

    def get_procedure_code(self, object_name, procedure_name, module_type='Module'):
        """
        Получить код конкретной процедуры или функции
        
        Args:
            object_name: Имя объекта
            procedure_name: Имя процедуры/функции
            module_type: Тип модуля
        
        Returns:
            str: Код процедуры
        """
        import re
        
        code = self.get_module_code(object_name, module_type)
        if not code:
            return None
        
        lines = code.split('\n')
        
        # Ищем начало процедуры
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
            return None
        
        # Ищем конец процедуры
        end_line = None
        indent_level = 0
        
        for i in range(start_line + 1, len(lines)):
            line = lines[i].strip()
            
            # Считаем вложенность (вложенные процедуры/функции)
            if re.match(r'^(Функция|Процедура)\s+', line, re.IGNORECASE):
                indent_level += 1
            elif line in end_keywords or re.match(r'^(КонецФункции|КонецПроцедуры)', line, re.IGNORECASE):
                if indent_level == 0:
                    end_line = i
                    break
                else:
                    indent_level -= 1
        
        if end_line is None:
            return None
        
        # Извлекаем код процедуры
        procedure_code = '\n'.join(lines[start_line:end_line + 1])
        
        return procedure_code