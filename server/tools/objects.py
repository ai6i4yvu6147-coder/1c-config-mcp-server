from .formatting import _load_resolved_types_map
from .relations import _resolve_config_object


class ObjectsMixin:
    """Object search/discovery: find_object, list_objects, get_object_structure, find_attribute, get_functional_options."""

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
        self._require_project_exists(project_filter, databases)

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
                LEFT JOIN modules m ON o.id = m.object_id AND m.form_id IS NULL AND m.command_id IS NULL
                WHERE (o.name LIKE ? OR IFNULL(o.synonym, '') LIKE ?)
                  AND o.object_kind = 'ConfigObject'
                GROUP BY o.id
            ''', (f'%{name}%', f'%{name}%'))

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
        self._require_project_exists(project_filter, databases)

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
                    WHERE object_type = ? AND object_kind = 'ConfigObject'
                    ORDER BY name
                    LIMIT ?
                ''', (object_type, limit))
                rows = cursor.fetchall()
                cursor.execute(
                    "SELECT COUNT(*) FROM metadata_objects WHERE object_type = ? AND object_kind = 'ConfigObject'",
                    (object_type,),
                )
                total_count = cursor.fetchone()[0]
            else:
                cursor.execute('''
                    SELECT DISTINCT object_type FROM metadata_objects
                    WHERE object_kind = 'ConfigObject'
                    ORDER BY object_type
                ''')
                types_rows = cursor.fetchall()
                rows = []
                total_count = 0
                for tr in types_rows:
                    ot = tr['object_type']
                    cursor.execute('''
                        SELECT name, object_type, object_belonging, extended_configuration_object
                        FROM metadata_objects
                        WHERE object_type = ? AND object_kind = 'ConfigObject'
                        ORDER BY name
                        LIMIT ?
                    ''', (ot, limit))
                    chunk = cursor.fetchall()
                    cursor.execute(
                        "SELECT COUNT(*) FROM metadata_objects WHERE object_type = ? AND object_kind = 'ConfigObject'",
                        (ot,),
                    )
                    cnt = cursor.fetchone()[0]
                    total_count += cnt
                    rows.extend(chunk)
            returned_count = len(rows)
            is_truncated = returned_count < total_count

            by_type = {}
            for row in rows:
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
                results[project_key][db_key] = {
                    'by_type': by_type,
                    'total_count': total_count,
                    'returned_count': returned_count,
                    'is_truncated': is_truncated,
                }

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
        self._require_project_exists(project_filter, databases)
        if extension_filter:
            databases = [db for db in databases if db['db_name'].lower() == extension_filter.lower()]

        results = {}

        for db_info in databases:
            conn = self._get_connection(db_info['db_path'])
            cursor = conn.cursor()

            resolved = _resolve_config_object(cursor, object_name)
            if resolved['status'] == 'not_found':
                continue
            if resolved['status'] == 'ambiguous':
                project_key = db_info['project_name']
                if project_key not in results:
                    results[project_key] = {}
                db_key = f"{db_info['db_name']} ({db_info['db_type']})"
                results[project_key][db_key] = {
                    'ambiguous': True,
                    'requested_name': resolved['requested_name'],
                    'candidates': resolved['candidates'],
                }
                continue
            obj_row = resolved['row']

            object_id = obj_row['id']
            obj_type = obj_row['object_type']

            if obj_type == 'FunctionalOption':
                # Функциональная опция: данные из functional_options; Content из fo_content_ref; использования на формах из fo_form_usage
                cursor.execute('''
                    SELECT location_constant, privileged_get_mode
                    FROM functional_options WHERE object_id = ?
                ''', (object_id,))
                fo_row = cursor.fetchone()
                location_constant = privileged_get_mode = None
                if fo_row:
                    location_constant = fo_row['location_constant']
                    privileged_get_mode = bool(fo_row['privileged_get_mode']) if fo_row['privileged_get_mode'] is not None else None
                cursor.execute('''
                    SELECT mo.object_type, mo.name, r.content_ref_type, r.tabular_section_name, r.element_name
                    FROM fo_content_ref r
                    JOIN metadata_objects mo ON r.metadata_object_id = mo.id
                    WHERE r.functional_option_id = ?
                    ORDER BY mo.object_type, mo.name, r.content_ref_type, r.tabular_section_name, r.element_name
                ''', (object_id,))
                content_refs = []
                for row in cursor.fetchall():
                    ot, on = row['object_type'], row['name']
                    rt, ts, en = row['content_ref_type'], row['tabular_section_name'], row['element_name']
                    if rt == 'Object':
                        content_refs.append(f"{ot}.{on}")
                    elif rt in ('Attribute', 'Resource', 'Dimension'):
                        content_refs.append(f"{ot}.{on}.{rt}.{en or ''}")
                    elif rt == 'TabularSectionColumn':
                        content_refs.append(f"{ot}.{on}.TabularSection.{ts or ''}.Attribute.{en or ''}")
                    else:
                        content_refs.append(f"{ot}.{on}")
                cursor.execute('''
                    SELECT o.name AS owner_name, f.form_name, fo.element_type, fo.element_name
                    FROM fo_form_usage fo
                    JOIN metadata_objects o ON fo.owner_object_id = o.id
                    LEFT JOIN forms f ON fo.form_id = f.id
                    WHERE fo.functional_option_id = ?
                    ORDER BY o.name, f.form_name, fo.element_type, fo.element_name
                ''', (object_id,))
                used_in = []
                for row in cursor.fetchall():
                    used_in.append({
                        'owner_object': row['owner_name'],
                        'form_name': row['form_name'],
                        'element_type': row['element_type'],
                        'element_name': row['element_name'],
                    })
                structure = {
                    'name': obj_row['name'],
                    'type': obj_type,
                    'uuid': obj_row['uuid'],
                    'synonym': obj_row['synonym'],
                    'comment': obj_row['comment'],
                    'location_constant': location_constant,
                    'content_refs': content_refs,
                    'privileged_get_mode': privileged_get_mode,
                    'used_in': used_in,
                    'modules': [],
                    'commands': [],
                    'forms': [],
                }
            elif obj_type == 'ScheduledJob':
                cursor.execute('''
                    SELECT method_name, description, key, use, predefined,
                           restart_count_on_failure, restart_interval_on_failure
                    FROM scheduled_jobs WHERE object_id = ?
                ''', (object_id,))
                sj_row = cursor.fetchone()
                structure = {
                    'name': obj_row['name'],
                    'type': obj_type,
                    'uuid': obj_row['uuid'],
                    'synonym': obj_row['synonym'],
                    'comment': obj_row['comment'],
                    'method_name': sj_row['method_name'] if sj_row else None,
                    'description': sj_row['description'] if sj_row else None,
                    'key': sj_row['key'] if sj_row else None,
                    'use': bool(sj_row['use']) if sj_row and sj_row['use'] is not None else None,
                    'predefined': bool(sj_row['predefined']) if sj_row and sj_row['predefined'] is not None else None,
                    'restart_count_on_failure': sj_row['restart_count_on_failure'] if sj_row else None,
                    'restart_interval_on_failure': sj_row['restart_interval_on_failure'] if sj_row else None,
                    'modules': [],
                    'commands': [],
                    'forms': [],
                }
            else:
                # Реквизиты, измерения, ресурсы
                cursor.execute('''
                    SELECT id, name, title, comment, is_standard, standard_type, section
                    FROM attributes
                    WHERE object_id = ?
                    ORDER BY section, is_standard DESC, name
                ''', (object_id,))

                attr_rows = cursor.fetchall()
                attr_ids = [r['id'] for r in attr_rows]
                attr_types_map = _load_resolved_types_map(cursor, 'attributes', attr_ids)

                attributes_by_section = {}
                for row in attr_rows:
                    section = row['section'] or 'Attribute'
                    if section not in attributes_by_section:
                        attributes_by_section[section] = []
                    attributes_by_section[section].append({
                        'name': row['name'],
                        'types': attr_types_map.get(row['id'], []),
                        'title': row['title'],
                        'comment': row['comment'] or '',
                        'is_standard': bool(row['is_standard']),
                        'standard_type': row['standard_type'],
                    })

                # Табличные части с колонками (JOIN с tabular_sections)
                cursor.execute('''
                    SELECT ts.name AS tabular_section_name, ts.title AS tabular_section_title,
                           ts.comment AS tabular_section_comment,
                           tsc.id AS column_id, tsc.column_name, tsc.title, tsc.comment
                    FROM tabular_section_columns tsc
                    JOIN tabular_sections ts ON tsc.tabular_section_id = ts.id
                    WHERE ts.object_id = ?
                    ORDER BY ts.name, tsc.column_name
                ''', (object_id,))

                col_rows = cursor.fetchall()
                col_ids = [r['column_id'] for r in col_rows]
                col_types_map = _load_resolved_types_map(cursor, 'tabular_section_columns', col_ids)

                tabular_sections = {}
                for row in col_rows:
                    ts_name = row['tabular_section_name']
                    if ts_name not in tabular_sections:
                        tabular_sections[ts_name] = {
                            'name': ts_name,
                            'title': row['tabular_section_title'],
                            'comment': row['tabular_section_comment'] or '',
                            'columns': [],
                        }
                    tabular_sections[ts_name]['columns'].append({
                        'name': row['column_name'],
                        'types': col_types_map.get(row['column_id'], []),
                        'title': row['title'],
                        'comment': row['comment'] or '',
                    })

                # Значения перечислений (для extension — object_belonging)
                cursor.execute('''
                    SELECT name, enum_order, title, comment, object_belonging, extended_configuration_object
                    FROM enum_values
                    WHERE object_id = ?
                    ORDER BY enum_order, name
                ''', (object_id,))

                enum_values = []
                for row in cursor.fetchall():
                    ev = {'name': row['name'], 'enum_order': row['enum_order'], 'title': row['title'], 'comment': row['comment'] or ''}
                    if db_info.get('db_type') == 'extension' and row['object_belonging']:
                        ev['object_belonging'] = row['object_belonging']
                        if row['extended_configuration_object']:
                            ev['extended_configuration_object'] = row['extended_configuration_object']
                    enum_values.append(ev)

                # Модули объекта (без модулей команд — они в commands / object_commands)
                cursor.execute('''
                    SELECT module_type FROM modules
                    WHERE object_id = ? AND form_id IS NULL AND command_id IS NULL
                ''', (object_id,))
                modules = [row['module_type'] for row in cursor.fetchall()]

                # Команды объекта (не CommonCommand — у общих команд нет строк в object_commands)
                cursor.execute('''
                    SELECT oc.name, oc.synonym,
                           EXISTS(SELECT 1 FROM modules m2 WHERE m2.command_id = oc.id) AS has_module
                    FROM object_commands oc
                    WHERE oc.object_id = ?
                    ORDER BY oc.name
                ''', (object_id,))
                object_commands = [
                    {
                        'name': row['name'],
                        'synonym': row['synonym'] or '',
                        'has_module': bool(row['has_module']),
                    }
                    for row in cursor.fetchall()
                ]

                # Формы (краткий список)
                cursor.execute('''
                    SELECT form_name FROM forms
                    WHERE object_id = ?
                ''', (object_id,))
                forms = [row['form_name'] for row in cursor.fetchall()]

                route_points = []
                route_transitions = []
                if obj_type == 'BusinessProcess':
                    cursor.execute('''
                        SELECT name, point_type, title, uuid, tab_order, true_port, false_port
                        FROM bp_route_points
                        WHERE object_id = ?
                        ORDER BY tab_order, name
                    ''', (object_id,))
                    for row in cursor.fetchall():
                        route_points.append({
                            'name': row['name'],
                            'type': row['point_type'],
                            'synonym': row['title'] or '',
                            'uuid': row['uuid'] or '',
                            'tab_order': row['tab_order'],
                            'true_port': row['true_port'],
                            'false_port': row['false_port'],
                        })
                    cursor.execute('''
                        SELECT from_point, to_point, from_port, title
                        FROM bp_route_transitions
                        WHERE object_id = ?
                        ORDER BY from_point, to_point
                    ''', (object_id,))
                    for row in cursor.fetchall():
                        route_transitions.append({
                            'from': row['from_point'],
                            'to': row['to_point'],
                            'from_port': row['from_port'],
                            'title': row['title'] or '',
                        })

                structure = {
                    'name': obj_row['name'],
                    'type': obj_type,
                    'uuid': obj_row['uuid'],
                    'synonym': obj_row['synonym'],
                    'comment': obj_row['comment'],
                    'attributes': attributes_by_section.get('Attribute', []),
                    'dimensions': attributes_by_section.get('Dimension', []),
                    'resources': attributes_by_section.get('Resource', []),
                    'tabular_sections': list(tabular_sections.values()),
                    'enum_values': enum_values,
                    'modules': modules,
                    'commands': object_commands,
                    'forms': forms,
                }
                if obj_type == 'BusinessProcess':
                    structure['route_points'] = route_points
                    structure['route_transitions'] = route_transitions
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

    def get_functional_options(self, object_name, project_filter=None, extension_filter=None,
                               form_name=None, element_type=None, element_name=None,
                               attribute_name=None):
        """
        Единый инструмент: возвращает функциональные опции для объекта метаданных или для элемента формы.
        Вызывать при вопросах: почему объект/документ недоступен; почему поле/кнопка на форме не отображается.

        — Только object_name: в каких ФО задействован этот объект (документ, справочник и т.д.) — из fo_content_ref.
        — object_name + form_name + element_type + element_name: от каких ФО зависит этот элемент формы — из fo_form_usage.

        Args:
            object_name: Имя объекта (обязательно).
            project_filter: Фильтр по проекту (обязательно).
            extension_filter: Фильтр по расширению/базе (опционально).
            form_name: Имя формы (опционально; для запроса по элементу формы).
            element_type: FormAttribute | FormCommand | FormItem | FormAttributeColumn (опционально).
            element_name: Имя реквизита/команды/элемента/колонки (опционально).
            attribute_name: Имя реквизита-родителя (обязательно для FormAttributeColumn).

        Returns:
            Dict по проектам/базам. Для объекта: список {name, synonym, content_ref_type, tabular_section_name, element_name}.
            Для элемента формы: список {name, synonym}.
        """
        self._require_project_filter(project_filter)
        databases = self._get_active_databases(project_filter)
        self._require_project_exists(project_filter, databases)
        if extension_filter:
            databases = [db for db in databases if db['db_name'].lower() == extension_filter.lower()]

        query_form_element = bool(form_name and element_type and element_name)
        if element_type == 'FormAttributeColumn' and not attribute_name:
            raise ValueError("Для element_type='FormAttributeColumn' укажите attribute_name")

        results = {}
        for db_info in databases:
            conn = self._get_connection(db_info['db_path'])
            cursor = conn.cursor()

            if query_form_element:
                cursor.execute('''
                    SELECT o.id AS owner_id, f.id AS form_id
                    FROM forms f
                    JOIN metadata_objects o ON f.object_id = o.id
                    WHERE o.name = ? AND f.form_name = ?
                    LIMIT 1
                ''', (object_name, form_name))
                row = cursor.fetchone()
                if not row:
                    continue
                owner_id, form_id = row['owner_id'], row['form_id']
                if element_type == 'FormAttributeColumn':
                    cursor.execute('''
                        SELECT mo.name, mo.synonym
                        FROM fo_form_usage fo
                        JOIN metadata_objects mo ON fo.functional_option_id = mo.id
                        WHERE fo.owner_object_id = ? AND fo.form_id = ?
                          AND fo.element_type = ? AND fo.element_name = ?
                          AND fo.parent_element_name = ?
                        ORDER BY mo.name
                    ''', (owner_id, form_id, element_type, element_name, attribute_name))
                else:
                    cursor.execute('''
                        SELECT mo.name, mo.synonym
                        FROM fo_form_usage fo
                        JOIN metadata_objects mo ON fo.functional_option_id = mo.id
                        WHERE fo.owner_object_id = ? AND fo.form_id = ? AND fo.element_type = ? AND fo.element_name = ?
                        ORDER BY mo.name
                    ''', (owner_id, form_id, element_type, element_name))
                options = [{'name': r['name'], 'synonym': r['synonym'] or ''} for r in cursor.fetchall()]
            else:
                cursor.execute('SELECT id FROM metadata_objects WHERE name = ? LIMIT 1', (object_name,))
                row = cursor.fetchone()
                if not row:
                    continue
                meta_id = row['id']
                cursor.execute('''
                    SELECT mo.name, mo.synonym, r.content_ref_type, r.tabular_section_name, r.element_name
                    FROM fo_content_ref r
                    JOIN metadata_objects mo ON r.functional_option_id = mo.id
                    WHERE r.metadata_object_id = ?
                    ORDER BY mo.name, r.content_ref_type, r.tabular_section_name, r.element_name
                ''', (meta_id,))
                options = []
                for r in cursor.fetchall():
                    opt = {'name': r['name'], 'synonym': r['synonym'] or ''}
                    if r['content_ref_type']:
                        opt['content_ref_type'] = r['content_ref_type']
                    if r['tabular_section_name']:
                        opt['tabular_section_name'] = r['tabular_section_name']
                    if r['element_name']:
                        opt['element_name'] = r['element_name']
                    options.append(opt)

            project_key = db_info['project_name']
            if project_key not in results:
                results[project_key] = {}
            db_key = f"{db_info['db_name']} ({db_info['db_type']})"
            results[project_key][db_key] = options
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
        self._require_project_exists(project_filter, databases)
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
                    a.id as attr_id,
                    a.name as attr_name,
                    a.title,
                    a.is_standard,
                    a.section
                FROM attributes a
                JOIN metadata_objects o ON a.object_id = o.id
                WHERE a.name LIKE ? AND o.object_kind = 'ConfigObject'
                ORDER BY o.object_type, o.name, a.section, a.name
                LIMIT ?
            ''', (f'%{attribute_name}%', max_results))

            attr_rows = cursor.fetchall()
            attr_ids = [r['attr_id'] for r in attr_rows]
            attr_types_map = _load_resolved_types_map(cursor, 'attributes', attr_ids)

            db_results = []
            for row in attr_rows:
                item = {
                    'object_name': row['object_name'],
                    'object_type': row['object_type'],
                    'attribute_name': row['attr_name'],
                    'types': attr_types_map.get(row['attr_id'], []),
                    'title': row['title'],
                    'is_standard': bool(row['is_standard']),
                    'section': row['section'],
                }
                if db_info.get('db_type') == 'extension' and row['object_belonging']:
                    item['object_belonging'] = row['object_belonging']
                    if row['extended_configuration_object']:
                        item['extended_configuration_object'] = row['extended_configuration_object']
                db_results.append(item)

            remaining = max_results - len(db_results)
            if remaining > 0:
                cursor.execute('''
                    SELECT
                        o.name as object_name,
                        o.object_type,
                        o.object_belonging,
                        o.extended_configuration_object,
                        ts.name as tabular_section_name,
                        tsc.id as column_id,
                        tsc.column_name as attr_name,
                        tsc.title
                    FROM tabular_section_columns tsc
                    JOIN tabular_sections ts ON tsc.tabular_section_id = ts.id
                    JOIN metadata_objects o ON ts.object_id = o.id
                    WHERE tsc.column_name LIKE ? AND o.object_kind = 'ConfigObject'
                    ORDER BY o.object_type, o.name, ts.name, tsc.column_name
                    LIMIT ?
                ''', (f'%{attribute_name}%', remaining))
                col_rows = cursor.fetchall()
                col_ids = [r['column_id'] for r in col_rows]
                col_types_map = _load_resolved_types_map(cursor, 'tabular_section_columns', col_ids)
                for row in col_rows:
                    item = {
                        'object_name': row['object_name'],
                        'object_type': row['object_type'],
                        'attribute_name': row['attr_name'],
                        'types': col_types_map.get(row['column_id'], []),
                        'title': row['title'],
                        'is_standard': False,
                        'section': 'TabularSectionColumn',
                        'tabular_section_name': row['tabular_section_name'],
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
