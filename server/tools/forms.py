import json

from .formatting import _load_resolved_types_map, _resolve_command_source


class FormsMixin:
    """Form structure and element search: find_form, find_form_element, get_form_structure, search_form_properties."""

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
        self._require_project_exists(project_filter, databases)

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
        self._require_project_exists(project_filter, databases)

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
        self._require_project_exists(project_filter, databases)

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

            form_id = form_row['id']

            # Получаем реквизиты
            cursor.execute('''
                SELECT id, name, title, is_main, query_text
                FROM form_attributes
                WHERE form_id = ?
                ORDER BY id
            ''', (form_id,))

            attr_rows = cursor.fetchall()
            attr_ids = [row['id'] for row in attr_rows]
            attr_types_map = _load_resolved_types_map(cursor, 'form_attributes', attr_ids)

            columns_by_attr = {}
            if attr_ids:
                placeholders = ','.join('?' * len(attr_ids))
                cursor.execute(f'''
                    SELECT id, form_attribute_id, name, title, table_context
                    FROM form_attribute_columns
                    WHERE form_attribute_id IN ({placeholders})
                    ORDER BY id
                ''', attr_ids)
                col_rows = cursor.fetchall()
                col_ids = [r['id'] for r in col_rows]
                col_types_map = _load_resolved_types_map(cursor, 'form_attribute_columns', col_ids)
                for col_row in col_rows:
                    col = {
                        'name': col_row['name'],
                        'title': col_row['title'],
                        'types': col_types_map.get(col_row['id'], []),
                    }
                    if col_row['table_context']:
                        col['table'] = col_row['table_context']
                    columns_by_attr.setdefault(col_row['form_attribute_id'], []).append(col)

            attributes = []
            for row in attr_rows:
                attr = {
                    'name': row['name'],
                    'title': row['title'],
                    'is_main': bool(row['is_main']),
                    'types': attr_types_map.get(row['id'], []),
                }
                cols = columns_by_attr.get(row['id'])
                if cols:
                    attr['columns'] = cols
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

            # Получаем элементы UI (visible, enabled), строим дерево и порядок вывода с глубиной
            cursor.execute('''
                SELECT id, parent_id, name, item_type, data_path, title, visible, enabled, command_name
                FROM form_items
                WHERE form_id = ?
                ORDER BY id
            ''', (form_id,))
            rows = cursor.fetchall()
            items_by_id = {}
            for row in rows:
                raw_cmd = row['command_name']
                cmd_name = raw_cmd.strip() if raw_cmd and str(raw_cmd).strip() else None
                item = {
                    'id': row['id'],
                    'parent_id': row['parent_id'],
                    'name': row['name'],
                    'type': row['item_type'],
                    'data_path': row['data_path'],
                    'title': row['title'],
                    'visible': row['visible'] if row['visible'] is not None else None,
                    'enabled': row['enabled'] if row['enabled'] is not None else None,
                    'command_name': cmd_name,
                    'children': [],
                }
                items_by_id[row['id']] = item
            for item in items_by_id.values():
                if item['parent_id'] is not None and item['parent_id'] in items_by_id:
                    items_by_id[item['parent_id']]['children'].append(item)
            roots = sorted([i for i in items_by_id.values() if i['parent_id'] is None], key=lambda x: x['id'])
            items_ordered = []
            def walk(n, depth):
                cn = n.get('command_name')
                out = {
                    'name': n['name'],
                    'type': n['type'],
                    'data_path': n['data_path'],
                    'title': n['title'],
                    'visible': n['visible'],
                    'enabled': n['enabled'],
                    'depth': depth,
                    'command_name': cn,
                    'command_source': _resolve_command_source(cn),
                }
                items_ordered.append(out)
                for ch in sorted(n['children'], key=lambda x: x['id']):
                    walk(ch, depth + 1)
            for r in roots:
                walk(r, 0)
            items = items_ordered

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
        self._require_project_exists(project_filter, databases)

        if extension_filter:
            databases = [db for db in databases if db['db_name'].lower() == extension_filter.lower()]

        results = {}
        want_val = None
        if property_value is not None:
            pv = str(property_value).strip().lower()
            if pv in ('true', '1', 'да', 'yes'):
                want_val = 1
            elif pv in ('false', '0', 'нет', 'no'):
                want_val = 0
            else:
                want_val = 1 if pv else 0  # fallback

        base_sql = '''
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
        '''
        if property_name == 'Visible':
            sql_with_filter = base_sql + (' WHERE fi.visible = ?' if want_val is not None else ' WHERE fi.visible IS NOT NULL')
        else:
            sql_with_filter = base_sql + (' WHERE fi.enabled = ?' if want_val is not None else ' WHERE fi.enabled IS NOT NULL')

        for db_info in databases:
            conn = self._get_connection(db_info['db_path'])
            cursor = conn.cursor()
            if want_val is not None:
                cursor.execute(sql_with_filter, (want_val,))
            else:
                cursor.execute(sql_with_filter)

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
