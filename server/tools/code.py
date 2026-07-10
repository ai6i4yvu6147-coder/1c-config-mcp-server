from .formatting import _validate_module_form_command_args

# Максимум модулей для поиска в одной базе (лимит по модулям; внутри каждого — до max_results вхождений)
MAX_MODULES_SEARCH_CODE = 100


class CodeMixin:
    """Code search and retrieval: search_code, get_module_code, get_module_procedures, get_procedure_code."""

    def search_code(self, query, project_filter=None, extension_filter=None, max_results=10,
                    object_name=None, module_type=None):
        """
        Поиск по коду во всех активных проектах.
        max_results — лимит вхождений на один модуль; из каждого модуля возвращается до max_results сниппетов.

        Args:
            query: Поисковый запрос
            project_filter: Фильтр по проекту (опционально)
            extension_filter: Фильтр по расширению/базе (опционально)
            max_results: Максимум совпадений на один модуль (из каждого модуля до max_results сниппетов)
            object_name: Фильтр по имени объекта (опционально, можно частичное)
            module_type: Фильтр по типу модуля (опционально): Module, ManagerModule, ObjectModule, FormModule, CommandModule

        Returns:
            Dict grouped by projects; каждый элемент содержит object_name, object_type, module_type, snippet,
            procedure_display, form_name (для FormModule), command_name (для CommandModule команды объекта)
        """
        self._require_project_filter(project_filter)
        databases = self._get_active_databases(project_filter)
        self._require_project_exists(project_filter, databases)

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
                # Прямой LIKE поиск; лимит по числу модулей
                sql = '''
                    SELECT
                        m.id as module_id,
                        o.name as object_name,
                        m.module_type,
                        m.code,
                        o.object_type,
                        f.form_name,
                        oc.name as command_name
                    FROM modules m
                    JOIN metadata_objects o ON m.object_id = o.id
                    LEFT JOIN forms f ON m.form_id = f.id
                    LEFT JOIN object_commands oc ON m.command_id = oc.id
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
                params.append(MAX_MODULES_SEARCH_CODE)
                cursor.execute(sql, params)
            else:
                # FTS5 полнотекстовый поиск; лимит по числу модулей
                cursor.execute('''
                    SELECT
                        m.id as module_id,
                        o.name as object_name,
                        m.module_type,
                        m.code,
                        o.object_type,
                        f.form_name,
                        oc.name as command_name
                    FROM code_search cs
                    JOIN modules m ON cs.rowid = m.id
                    JOIN metadata_objects o ON m.object_id = o.id
                    LEFT JOIN forms f ON m.form_id = f.id
                    LEFT JOIN object_commands oc ON m.command_id = oc.id
                    WHERE code_search MATCH ?
                    LIMIT ?
                ''', (query, MAX_MODULES_SEARCH_CODE))

            rows = cursor.fetchall()
            module_ids = [r['module_id'] for r in rows] if rows else []
            procedures_by_module = {}
            if module_ids:
                placeholders = ','.join('?' * len(module_ids))
                cursor.execute(
                    f'SELECT module_id, name, proc_type, start_line, end_line FROM module_procedures WHERE module_id IN ({placeholders}) ORDER BY module_id, start_line',
                    module_ids
                )
                for pr in cursor.fetchall():
                    mid = pr['module_id']
                    if mid not in procedures_by_module:
                        procedures_by_module[mid] = []
                    procedures_by_module[mid].append(pr)

            db_results = []
            for row in rows:
                code = row['code']
                module_id = row['module_id']
                procedures = procedures_by_module.get(module_id, [])
                query_lower = query.lower()
                code_lower = code.lower()

                def procedure_at_line(line_no):
                    """Процедура/функция, охватывающая строку line_no (1-based), или None."""
                    best = None
                    for p in procedures:
                        if p['start_line'] <= line_no:
                            if p['end_line'] is None or p['end_line'] >= line_no:
                                if best is None or p['start_line'] > best['start_line']:
                                    best = p
                    return best

                pos = 0
                count_in_module = 0
                while count_in_module < max_results:
                    pos = code_lower.find(query_lower, pos)
                    if pos == -1:
                        break
                    count_in_module += 1
                    line_no = code[:pos].count('\n') + 1
                    proc = procedure_at_line(line_no)
                    if proc:
                        procedure_display = f"{proc['proc_type']}: {proc['name']}"
                    else:
                        procedure_display = '<тело модуля>'

                    start = max(0, pos - 200)
                    end = min(len(code), pos + len(query) + 200)
                    line_start = code.rfind('\n', 0, start)
                    line_start = (line_start + 1) if line_start != -1 else 0
                    line_end = code.find('\n', end)
                    line_end = (line_end + 1) if line_end != -1 else len(code)
                    snippet = "..." + code[line_start:line_end] + "..."

                    db_results.append({
                        'object_name': row['object_name'],
                        'object_type': row['object_type'],
                        'module_type': row['module_type'],
                        'snippet': snippet,
                        'procedure_display': procedure_display,
                        'form_name': row['form_name'] if row['form_name'] is not None else None,
                        'command_name': row['command_name'] if row['command_name'] is not None else None,
                    })
                    pos += 1

            if db_results:
                project_key = f"{db_info['project_name']}"
                if project_key not in results:
                    results[project_key] = {}
                db_key = f"{db_info['db_name']} ({db_info['db_type']})"
                if db_key not in results[project_key]:
                    results[project_key][db_key] = []
                results[project_key][db_key].extend(db_results)

            # Поиск по тексту запроса DynamicList в EAV
            fq_sql = '''
                SELECT
                    o.name as object_name,
                    o.object_type,
                    f.form_name,
                    fa.name as attribute_name,
                    fep.value_text as query_text
                FROM form_entity_properties fep
                JOIN form_attributes fa ON fep.entity_id = fa.id AND fep.entity_kind = 'attribute'
                JOIN forms f ON fa.form_id = f.id
                JOIN metadata_objects o ON f.object_id = o.id
                WHERE fep.property_name = 'QueryText' AND fep.value_text LIKE ?
            '''
            fq_params = [f'%{query}%']
            if object_name:
                fq_sql += ' AND o.name LIKE ?'
                fq_params.append(f'%{object_name}%')
            cursor.execute(fq_sql, fq_params)

            for row in cursor.fetchall():
                text = row['query_text'] or ''
                pos = text.lower().find(query.lower())
                if pos == -1:
                    continue
                start = max(0, pos - 80)
                end = min(len(text), pos + len(query) + 80)
                snippet = "..." + text[start:end] + "..."
                entry = {
                    'match_kind': 'form_query',
                    'object_name': row['object_name'],
                    'object_type': row['object_type'],
                    'form_name': row['form_name'],
                    'attribute_name': row['attribute_name'],
                    'snippet': snippet,
                    'hint': f'get_form_attribute(object_name="{row["object_name"]}", form_name="{row["form_name"]}", attribute_name="{row["attribute_name"]}")',
                }
                project_key = f"{db_info['project_name']}"
                if project_key not in results:
                    results[project_key] = {}
                db_key = f"{db_info['db_name']} ({db_info['db_type']})"
                if db_key not in results[project_key]:
                    results[project_key][db_key] = []
                results[project_key][db_key].append(entry)

        if not results:
            return {"_empty": True, "diagnostics": {"project_filter": project_filter, "num_databases": len(databases)}}
        return results

    def get_module_code(self, object_name, module_type='Module', form_name=None, command_name=None,
                        project_filter=None, extension_filter=None):
        """
        Получить код модуля

        Args:
            object_name: Имя объекта
            module_type: Тип модуля (Module, ManagerModule, ObjectModule, FormModule, CommandModule)
            form_name: Имя формы (обязательно для FormModule)
            command_name: Имя команды объекта (для CommandModule команды объекта; для общей команды не указывать)
            project_filter: Фильтр по проекту
            extension_filter: Фильтр по расширению/базе

        Returns:
            Dict with code from each matching database
        """
        self._require_project_filter(project_filter)
        _validate_module_form_command_args(module_type, form_name, command_name)
        if module_type == 'FormModule' and not (form_name or '').strip():
            raise ValueError("form_name is required when module_type is 'FormModule'")

        databases = self._get_active_databases(project_filter)
        self._require_project_exists(project_filter, databases)

        if extension_filter:
            databases = [db for db in databases if db['db_name'].lower() == extension_filter.lower()]

        results = {}
        cn = (command_name or '').strip() if command_name is not None else ''

        if module_type == 'FormModule':
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
        elif module_type == 'CommandModule':
            for db_info in databases:
                conn = self._get_connection(db_info['db_path'])
                cursor = conn.cursor()
                if cn:
                    cursor.execute('''
                        SELECT m.code
                        FROM modules m
                        JOIN metadata_objects o ON m.object_id = o.id
                        JOIN object_commands oc ON m.command_id = oc.id
                        WHERE o.name = ? AND oc.name = ? AND m.module_type = 'CommandModule'
                        LIMIT 1
                    ''', (object_name, cn))
                else:
                    cursor.execute('''
                        SELECT m.code
                        FROM modules m
                        JOIN metadata_objects o ON m.object_id = o.id
                        WHERE o.name = ? AND m.module_type = 'CommandModule'
                          AND m.form_id IS NULL AND m.command_id IS NULL
                        LIMIT 1
                    ''', (object_name,))
                row = cursor.fetchone()
                if row:
                    project_key = f"{db_info['project_name']}"
                    if project_key not in results:
                        results[project_key] = {}
                    db_key = f"{db_info['db_name']} ({db_info['db_type']})"
                    results[project_key][db_key] = row['code']
        else:
            for db_info in databases:
                conn = self._get_connection(db_info['db_path'])
                cursor = conn.cursor()

                cursor.execute('''
                    SELECT m.code
                    FROM modules m
                    JOIN metadata_objects o ON m.object_id = o.id
                    WHERE o.name = ? AND m.module_type = ? AND m.form_id IS NULL AND m.command_id IS NULL
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

    def get_module_procedures(self, object_name, module_type='Module', form_name=None, command_name=None,
                              project_filter=None, extension_filter=None):
        """
        Получить список процедур и функций модуля (из таблицы module_procedures).

        Args:
            object_name: Имя объекта
            module_type: Тип модуля (Module, ManagerModule, ObjectModule, FormModule, CommandModule)
            form_name: Имя формы (обязательно для FormModule)
            command_name: Имя команды объекта (для CommandModule команды объекта)
            project_filter: Фильтр по проекту
            extension_filter: Фильтр по расширению/базе

        Returns:
            Dict with procedures from each matching database
        """
        self._require_project_filter(project_filter)
        _validate_module_form_command_args(module_type, form_name, command_name)
        if module_type == 'FormModule' and not (form_name or '').strip():
            raise ValueError("form_name is required when module_type is 'FormModule'")

        databases = self._get_active_databases(project_filter)
        self._require_project_exists(project_filter, databases)
        if extension_filter:
            databases = [db for db in databases if db['db_name'].lower() == extension_filter.lower()]

        results = {}
        cn = (command_name or '').strip() if command_name is not None else ''

        def row_to_procedure(row):
            exp = ' Экспорт' if row['is_export'] else ''
            return {
                'type': row['proc_type'],
                'name': row['name'],
                'params': row['params'] or '(без параметров)',
                'export': bool(row['is_export']),
                'line': row['start_line'],
                'signature': f"{row['proc_type']} {row['name']}({row['params']}){exp}",
                'comment': row['comment'] or '',
                'execution_context': row['execution_context'],
                'extension_call_type': row['extension_call_type'],
                'used_in_scheduled_job': bool(row['used_in_scheduled_job']),
            }

        proc_columns = '''
                    SELECT p.name, p.proc_type, p.start_line, p.end_line, p.params, p.is_export,
                           p.execution_context, p.extension_call_type, p.comment,
                           p.used_in_scheduled_job
        '''

        if module_type == 'FormModule':
            for db_info in databases:
                conn = self._get_connection(db_info['db_path'])
                cursor = conn.cursor()
                cursor.execute(f'''
                    {proc_columns}
                    FROM module_procedures p
                    JOIN modules m ON p.module_id = m.id
                    JOIN forms f ON m.form_id = f.id
                    JOIN metadata_objects o ON f.object_id = o.id
                    WHERE o.name = ? AND f.form_name = ? AND m.module_type = 'FormModule'
                    ORDER BY p.start_line
                ''', (object_name, form_name))
                rows = cursor.fetchall()
                if not rows:
                    continue
                procedures = [row_to_procedure(row) for row in rows]
                project_key = db_info['project_name']
                if project_key not in results:
                    results[project_key] = {}
                results[project_key][f"{db_info['db_name']} ({db_info['db_type']})"] = procedures
        elif module_type == 'CommandModule':
            for db_info in databases:
                conn = self._get_connection(db_info['db_path'])
                cursor = conn.cursor()
                if cn:
                    cursor.execute(f'''
                        {proc_columns}
                        FROM module_procedures p
                        JOIN modules m ON p.module_id = m.id
                        JOIN metadata_objects o ON m.object_id = o.id
                        JOIN object_commands oc ON m.command_id = oc.id
                        WHERE o.name = ? AND oc.name = ? AND m.module_type = 'CommandModule'
                        ORDER BY p.start_line
                    ''', (object_name, cn))
                else:
                    cursor.execute(f'''
                        {proc_columns}
                        FROM module_procedures p
                        JOIN modules m ON p.module_id = m.id
                        JOIN metadata_objects o ON m.object_id = o.id
                        WHERE o.name = ? AND m.module_type = 'CommandModule'
                          AND m.form_id IS NULL AND m.command_id IS NULL
                        ORDER BY p.start_line
                    ''', (object_name,))
                rows = cursor.fetchall()
                if not rows:
                    continue
                procedures = [row_to_procedure(row) for row in rows]
                project_key = db_info['project_name']
                if project_key not in results:
                    results[project_key] = {}
                results[project_key][f"{db_info['db_name']} ({db_info['db_type']})"] = procedures
        else:
            for db_info in databases:
                conn = self._get_connection(db_info['db_path'])
                cursor = conn.cursor()
                cursor.execute(f'''
                    {proc_columns}
                    FROM module_procedures p
                    JOIN modules m ON p.module_id = m.id
                    JOIN metadata_objects o ON m.object_id = o.id
                    WHERE o.name = ? AND m.module_type = ? AND m.form_id IS NULL AND m.command_id IS NULL
                    ORDER BY p.start_line
                ''', (object_name, module_type))
                rows = cursor.fetchall()
                if not rows:
                    continue
                procedures = [row_to_procedure(row) for row in rows]
                project_key = db_info['project_name']
                if project_key not in results:
                    results[project_key] = {}
                results[project_key][f"{db_info['db_name']} ({db_info['db_type']})"] = procedures

        return results

    def get_procedure_code(self, object_name, procedure_name, module_type='Module', form_name=None, command_name=None,
                           project_filter=None, extension_filter=None):
        """
        Получить код конкретной процедуры (по start_line/end_line из module_procedures, срез modules.code).

        Args:
            object_name: Имя объекта
            procedure_name: Имя процедуры/функции
            module_type: Тип модуля (Module, ManagerModule, ObjectModule, FormModule, CommandModule)
            form_name: Имя формы (обязательно для FormModule)
            command_name: Имя команды объекта (для CommandModule команды объекта)
            project_filter: Фильтр по проекту
            extension_filter: Фильтр по расширению/базе

        Returns:
            Dict with procedure code from each matching database
        """
        _validate_module_form_command_args(module_type, form_name, command_name)
        if module_type == 'FormModule' and not (form_name or '').strip():
            raise ValueError("form_name is required when module_type is 'FormModule'")

        self._require_project_filter(project_filter)
        databases = self._get_active_databases(project_filter)
        self._require_project_exists(project_filter, databases)
        if extension_filter:
            databases = [db for db in databases if db['db_name'].lower() == extension_filter.lower()]

        results = {}
        cn = (command_name or '').strip() if command_name is not None else ''

        if module_type == 'FormModule':
            for db_info in databases:
                conn = self._get_connection(db_info['db_path'])
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT p.start_line, p.end_line, m.code
                    FROM module_procedures p
                    JOIN modules m ON p.module_id = m.id
                    JOIN forms f ON m.form_id = f.id
                    JOIN metadata_objects o ON f.object_id = o.id
                    WHERE o.name = ? AND f.form_name = ? AND m.module_type = 'FormModule' AND p.name = ?
                    LIMIT 1
                ''', (object_name, form_name, procedure_name))
                row = cursor.fetchone()
                if not row or not row['code']:
                    continue
                lines = row['code'].split('\n')
                start_line = row['start_line']
                end_line = row['end_line']
                if end_line is None:
                    end_line = len(lines)
                procedure_code = '\n'.join(lines[start_line - 1:end_line])
                if procedure_code:
                    project_key = db_info['project_name']
                    if project_key not in results:
                        results[project_key] = {}
                    results[project_key][f"{db_info['db_name']} ({db_info['db_type']})"] = procedure_code
        elif module_type == 'CommandModule':
            for db_info in databases:
                conn = self._get_connection(db_info['db_path'])
                cursor = conn.cursor()
                if cn:
                    cursor.execute('''
                        SELECT p.start_line, p.end_line, m.code
                        FROM module_procedures p
                        JOIN modules m ON p.module_id = m.id
                        JOIN metadata_objects o ON m.object_id = o.id
                        JOIN object_commands oc ON m.command_id = oc.id
                        WHERE o.name = ? AND oc.name = ? AND m.module_type = 'CommandModule' AND p.name = ?
                        LIMIT 1
                    ''', (object_name, cn, procedure_name))
                else:
                    cursor.execute('''
                        SELECT p.start_line, p.end_line, m.code
                        FROM module_procedures p
                        JOIN modules m ON p.module_id = m.id
                        JOIN metadata_objects o ON m.object_id = o.id
                        WHERE o.name = ? AND m.module_type = 'CommandModule'
                          AND m.form_id IS NULL AND m.command_id IS NULL AND p.name = ?
                        LIMIT 1
                    ''', (object_name, procedure_name))
                row = cursor.fetchone()
                if not row or not row['code']:
                    continue
                lines = row['code'].split('\n')
                start_line = row['start_line']
                end_line = row['end_line']
                if end_line is None:
                    end_line = len(lines)
                procedure_code = '\n'.join(lines[start_line - 1:end_line])
                if procedure_code:
                    project_key = db_info['project_name']
                    if project_key not in results:
                        results[project_key] = {}
                    results[project_key][f"{db_info['db_name']} ({db_info['db_type']})"] = procedure_code
        else:
            for db_info in databases:
                conn = self._get_connection(db_info['db_path'])
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT p.start_line, p.end_line, m.code
                    FROM module_procedures p
                    JOIN modules m ON p.module_id = m.id
                    JOIN metadata_objects o ON m.object_id = o.id
                    WHERE o.name = ? AND m.module_type = ? AND m.form_id IS NULL AND m.command_id IS NULL AND p.name = ?
                    LIMIT 1
                ''', (object_name, module_type, procedure_name))
                row = cursor.fetchone()
                if not row or not row['code']:
                    continue
                lines = row['code'].split('\n')
                start_line = row['start_line']
                end_line = row['end_line']
                if end_line is None:
                    end_line = len(lines)
                procedure_code = '\n'.join(lines[start_line - 1:end_line])
                if procedure_code:
                    project_key = db_info['project_name']
                    if project_key not in results:
                        results[project_key] = {}
                    results[project_key][f"{db_info['db_name']} ({db_info['db_type']})"] = procedure_code

        return results
