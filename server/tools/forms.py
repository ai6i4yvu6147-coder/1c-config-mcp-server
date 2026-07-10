import json

from shared.form_eav import (
    field_index_from_eav,
    filter_field_eav,
    get_eav_value,
    load_entity_eav,
)
from shared.form_overview_profiles import (
    attribute_overview_hints,
    is_dynamic_list,
    is_value_table,
    overview_paths_for_item,
)

from .formatting import _load_resolved_types_map
from .form_helpers import (
    _build_item_tree,
    _eav_display_props,
    _resolve_form,
)


class FormsMixin:
    """Form structure and element search: find_form, find_form_element, get_form_structure, get_form_attribute, get_form_item, search_form_properties."""

    def find_form(self, object_name=None, form_name=None, project_filter=None, extension_filter=None):
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
                conditions.append('''EXISTS (
                    SELECT 1 FROM form_entity_properties fep
                    WHERE fep.entity_kind = 'item' AND fep.entity_id = fi.id
                      AND fep.property_path = 'DataPath' AND fep.value_text LIKE ?
                )''')
                params.append(f'%{data_path}%')

            query = '''
                SELECT DISTINCT
                    o.name as object_name,
                    o.object_type,
                    o.object_belonging,
                    o.extended_configuration_object,
                    f.form_name,
                    fi.id as item_id,
                    fi.name as element_name,
                    fi.item_type
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
            rows = cursor.fetchall()
            if not rows:
                continue

            item_ids = [r['item_id'] for r in rows]
            eav_by_item = load_entity_eav(cursor, 'item', item_ids)

            db_results = []
            for row in rows:
                eav = eav_by_item.get(row['item_id'], [])
                paths = overview_paths_for_item(row['item_type'])
                overview = _eav_display_props(eav, paths)
                item = {
                    'object_name': row['object_name'],
                    'object_type': row['object_type'],
                    'form_name': row['form_name'],
                    'element_name': row['element_name'],
                    'element_type': row['item_type'],
                    'overview_properties': overview,
                    'data_path': overview.get('DataPath'),
                    'title': overview.get('Title'),
                    'visible': overview.get('Visible'),
                    'enabled': overview.get('Enabled'),
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
        self._require_project_filter(project_filter)
        databases = self._get_active_databases(project_filter)
        self._require_project_exists(project_filter, databases)

        if extension_filter:
            databases = [db for db in databases if db['db_name'].lower() == extension_filter.lower()]

        results = {}

        for db_info in databases:
            conn = self._get_connection(db_info['db_path'])
            cursor = conn.cursor()

            form_row = _resolve_form(cursor, object_name, form_name)
            if not form_row:
                continue

            form_id = form_row['id']

            cursor.execute('''
                SELECT id, name, title, is_main
                FROM form_attributes
                WHERE form_id = ?
                ORDER BY id
            ''', (form_id,))

            attr_rows = cursor.fetchall()
            attr_ids = [row['id'] for row in attr_rows]
            attr_types_map = _load_resolved_types_map(cursor, 'form_attributes', attr_ids)
            attr_eav_map = load_entity_eav(cursor, 'attribute', attr_ids)

            columns_count_by_attr = {}
            if attr_ids:
                placeholders = ','.join('?' * len(attr_ids))
                cursor.execute(f'''
                    SELECT form_attribute_id, COUNT(*) as cnt
                    FROM form_attribute_columns
                    WHERE form_attribute_id IN ({placeholders})
                    GROUP BY form_attribute_id
                ''', attr_ids)
                for row in cursor.fetchall():
                    columns_count_by_attr[row['form_attribute_id']] = row['cnt']

            attributes = []
            for row in attr_rows:
                types = attr_types_map.get(row['id'], [])
                eav = attr_eav_map.get(row['id'], [])
                col_count = columns_count_by_attr.get(row['id'], 0)
                if is_dynamic_list(types) and not col_count:
                    col_count = len(field_index_from_eav(eav))
                attr = {
                    'name': row['name'],
                    'title': row['title'],
                    'is_main': bool(row['is_main']),
                    'types': types,
                    'hints': attribute_overview_hints(types, eav, col_count),
                }
                attributes.append(attr)

            cursor.execute('''
                SELECT name, title, action, shortcut, representation
                FROM form_commands
                WHERE form_id = ?
            ''', (form_id,))
            commands = [dict(row) for row in cursor.fetchall()]

            cursor.execute('''
                SELECT event_name, handler, call_type
                FROM form_events
                WHERE form_id = ?
            ''', (form_id,))
            events = [dict(row) for row in cursor.fetchall()]

            cursor.execute('''
                SELECT id, parent_id, name, item_type
                FROM form_items
                WHERE form_id = ?
                ORDER BY id
            ''', (form_id,))
            item_rows = cursor.fetchall()
            item_ids = [r['id'] for r in item_rows]
            item_eav_map = load_entity_eav(cursor, 'item', item_ids)
            items = _build_item_tree(item_rows, item_eav_map)

            form_structure = {
                'uuid': form_row['uuid'],
                'form_kind': form_row['form_kind'],
                'properties': json.loads(form_row['properties_json']) if form_row['properties_json'] else {},
                'events': events,
                'attributes': attributes,
                'commands': commands,
                'items': items,
                'attribute_names': [a['name'] for a in attributes],
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

    def get_form_attribute(self, object_name, form_name, attribute_name, project_filter=None,
                           extension_filter=None, column_name=None):
        self._require_project_filter(project_filter)
        databases = self._get_active_databases(project_filter)
        self._require_project_exists(project_filter, databases)

        if extension_filter:
            databases = [db for db in databases if db['db_name'].lower() == extension_filter.lower()]

        results = {}

        for db_info in databases:
            conn = self._get_connection(db_info['db_path'])
            cursor = conn.cursor()

            form_row = _resolve_form(cursor, object_name, form_name)
            if not form_row:
                continue

            cursor.execute('''
                SELECT id, name, title, is_main
                FROM form_attributes
                WHERE form_id = ? AND name = ?
                LIMIT 1
            ''', (form_row['id'], attribute_name))
            attr_row = cursor.fetchone()
            if not attr_row:
                continue

            attr_id = attr_row['id']
            types = _load_resolved_types_map(cursor, 'form_attributes', [attr_id]).get(attr_id, [])
            eav = load_entity_eav(cursor, 'attribute', [attr_id]).get(attr_id, [])

            if column_name:
                detail = self._attribute_column_detail(cursor, attr_id, types, eav, column_name)
                if detail is None:
                    continue
                payload = detail
            else:
                payload = {
                    'name': attr_row['name'],
                    'title': attr_row['title'],
                    'is_main': bool(attr_row['is_main']),
                    'types': types,
                    'properties': [
                        {
                            'path': r['property_path'],
                            'ordinal': r.get('ordinal', 0),
                            'value': r['value_text'],
                            'value_type': r.get('value_type'),
                        }
                        for r in eav
                    ],
                    'columns': self._attribute_column_index(cursor, attr_id, types, eav),
                }

            project_key = db_info['project_name']
            results.setdefault(project_key, {})
            db_key = f"{db_info['db_name']} ({db_info['db_type']})"
            results[project_key][db_key] = payload

        return results

    def _attribute_column_index(self, cursor, attr_id, types, eav):
        if is_value_table(types):
            cursor.execute('''
                SELECT id, name, title, table_context
                FROM form_attribute_columns
                WHERE form_attribute_id = ?
                ORDER BY id
            ''', (attr_id,))
            rows = cursor.fetchall()
            col_ids = [r['id'] for r in rows]
            col_types = _load_resolved_types_map(cursor, 'form_attribute_columns', col_ids)
            index = []
            for row in rows:
                entry = {
                    'name': row['name'],
                    'title': row['title'],
                    'types': col_types.get(row['id'], []),
                }
                if row['table_context']:
                    entry['table'] = row['table_context']
                index.append(entry)
            return index
        if is_dynamic_list(types):
            return [
                {
                    'name': f['key'],
                    'dataPath': f.get('dataPath', ''),
                    'field': f.get('field', ''),
                }
                for f in field_index_from_eav(eav)
            ]
        return []

    def _attribute_column_detail(self, cursor, attr_id, types, eav, column_name):
        if is_value_table(types):
            cursor.execute('''
                SELECT id, name, title, table_context
                FROM form_attribute_columns
                WHERE form_attribute_id = ? AND name = ?
                LIMIT 1
            ''', (attr_id, column_name))
            col_row = cursor.fetchone()
            if not col_row:
                return None
            col_eav = load_entity_eav(cursor, 'attribute_column', [col_row['id']]).get(col_row['id'], [])
            col_types = _load_resolved_types_map(cursor, 'form_attribute_columns', [col_row['id']]).get(col_row['id'], [])
            cursor.execute('''
                SELECT mo.name, mo.synonym
                FROM fo_form_usage fo
                JOIN metadata_objects mo ON fo.functional_option_id = mo.id
                JOIN form_attributes fa ON fa.id = ?
                WHERE fo.element_type = 'FormAttributeColumn'
                  AND fo.form_id = fa.form_id
                  AND fo.parent_element_name = fa.name
                  AND fo.element_name = ?
                ORDER BY mo.name
            ''', (attr_id, column_name))
            fo = [{'name': r['name'], 'synonym': r['synonym'] or ''} for r in cursor.fetchall()]
            return {
                'name': col_row['name'],
                'title': col_row['title'],
                'table': col_row['table_context'],
                'types': col_types,
                'properties': [
                    {'path': r['property_path'], 'ordinal': r.get('ordinal', 0), 'value': r['value_text']}
                    for r in col_eav
                ],
                'functional_options': fo,
            }
        if is_dynamic_list(types):
            field_rows = filter_field_eav(eav, column_name)
            if not field_rows:
                return None
            return {
                'column_name': column_name,
                'properties': [
                    {'path': r['property_path'], 'ordinal': r.get('ordinal', 0), 'value': r['value_text']}
                    for r in field_rows
                ],
            }
        return None

    def get_form_item(self, object_name, form_name, element_name, project_filter=None,
                      extension_filter=None, column_name=None):
        self._require_project_filter(project_filter)
        databases = self._get_active_databases(project_filter)
        self._require_project_exists(project_filter, databases)

        if extension_filter:
            databases = [db for db in databases if db['db_name'].lower() == extension_filter.lower()]

        results = {}

        for db_info in databases:
            conn = self._get_connection(db_info['db_path'])
            cursor = conn.cursor()

            form_row = _resolve_form(cursor, object_name, form_name)
            if not form_row:
                continue

            if column_name:
                payload = self._form_item_column_detail(cursor, form_row['id'], element_name, column_name)
            else:
                payload = self._form_item_detail(cursor, form_row['id'], element_name)

            if payload is None:
                continue

            project_key = db_info['project_name']
            results.setdefault(project_key, {})
            db_key = f"{db_info['db_name']} ({db_info['db_type']})"
            results[project_key][db_key] = payload

        return results

    def _form_item_detail(self, cursor, form_id, element_name):
        cursor.execute('''
            SELECT id, name, item_type
            FROM form_items
            WHERE form_id = ? AND name = ?
            LIMIT 1
        ''', (form_id, element_name))
        row = cursor.fetchone()
        if not row:
            return None

        eav = load_entity_eav(cursor, 'item', [row['id']]).get(row['id'], [])
        paths = overview_paths_for_item(row['item_type'])
        cursor.execute('''
            SELECT event_name, handler
            FROM form_item_events
            WHERE item_id = ?
        ''', (row['id'],))
        events = [dict(r) for r in cursor.fetchall()]

        cursor.execute('''
            SELECT id, name, item_type
            FROM form_items
            WHERE form_id = ? AND parent_id = ?
            ORDER BY id
        ''', (form_id, row['id']))
        children = cursor.fetchall()
        child_ids = [c['id'] for c in children]
        child_eav = load_entity_eav(cursor, 'item', child_ids)

        columns = []
        for child in children:
            ce = child_eav.get(child['id'], [])
            cpaths = overview_paths_for_item(child['item_type'])
            cover = _eav_display_props(ce, cpaths)
            columns.append({
                'name': child['name'],
                'item_type': child['item_type'],
                'dataPath': cover.get('DataPath', ''),
                'title': cover.get('Title', ''),
            })

        return {
            'name': row['name'],
            'item_type': row['item_type'],
            'properties': [
                {'path': r['property_path'], 'ordinal': r.get('ordinal', 0), 'value': r['value_text'],
                 'value_type': r.get('value_type')}
                for r in eav
            ],
            'overview_properties': _eav_display_props(eav, paths),
            'events': events,
            'columns': columns,
        }

    def _form_item_column_detail(self, cursor, form_id, parent_name, column_name):
        cursor.execute('''
            SELECT id FROM form_items
            WHERE form_id = ? AND name = ?
            LIMIT 1
        ''', (form_id, parent_name))
        parent = cursor.fetchone()
        if not parent:
            return None

        cursor.execute('''
            SELECT id, name, item_type
            FROM form_items
            WHERE form_id = ? AND parent_id = ? AND name = ?
            LIMIT 1
        ''', (form_id, parent['id'], column_name))
        child = cursor.fetchone()
        if not child:
            return None

        eav = load_entity_eav(cursor, 'item', [child['id']]).get(child['id'], [])
        paths = overview_paths_for_item(child['item_type'])
        cursor.execute('''
            SELECT event_name, handler
            FROM form_item_events
            WHERE item_id = ?
        ''', (child['id'],))
        events = [dict(r) for r in cursor.fetchall()]

        return {
            'name': child['name'],
            'item_type': child['item_type'],
            'parent_name': parent_name,
            'properties': [
                {'path': r['property_path'], 'ordinal': r.get('ordinal', 0), 'value': r['value_text'],
                 'value_type': r.get('value_type')}
                for r in eav
            ],
            'overview_properties': _eav_display_props(eav, paths),
            'events': events,
        }

    def search_form_properties(self, property_name, property_value=None, project_filter=None, extension_filter=None):
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
                want_val = 'true'
            elif pv in ('false', '0', 'нет', 'no'):
                want_val = 'false'
            else:
                want_val = 'true' if pv else 'false'

        for db_info in databases:
            conn = self._get_connection(db_info['db_path'])
            cursor = conn.cursor()

            sql = '''
                SELECT
                    o.name as object_name,
                    o.object_type,
                    f.form_name,
                    fi.id as item_id,
                    fi.name as element_name,
                    fi.item_type,
                    fep.value_text as property_value
                FROM form_entity_properties fep
                JOIN form_items fi ON fep.entity_id = fi.id AND fep.entity_kind = 'item'
                JOIN forms f ON fi.form_id = f.id
                JOIN metadata_objects o ON f.object_id = o.id
                WHERE fep.property_path = ?
            '''
            params = [property_name]
            if want_val is not None:
                sql += ' AND LOWER(fep.value_text) = ?'
                params.append(want_val)
            cursor.execute(sql, params)

            rows = cursor.fetchall()
            if not rows:
                continue

            item_ids = [r['item_id'] for r in rows]
            item_eav = load_entity_eav(cursor, 'item', item_ids)

            db_results = []
            for row in rows:
                eav = item_eav.get(row['item_id'], [])
                db_results.append({
                    'object_name': row['object_name'],
                    'object_type': row['object_type'],
                    'form_name': row['form_name'],
                    'element_name': row['element_name'],
                    'element_type': row['item_type'],
                    'data_path': get_eav_value(eav, 'DataPath'),
                    'property_name': property_name,
                    'property_value': row['property_value'],
                })

            if db_results:
                project_key = f"{db_info['project_name']}"
                if project_key not in results:
                    results[project_key] = {}

                db_key = f"{db_info['db_name']} ({db_info['db_type']})"
                results[project_key][db_key] = db_results

        return results
