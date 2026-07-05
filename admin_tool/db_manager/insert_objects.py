import time

from .bsl import _parse_module_procedures
from shared.metadata_type_resolver import MetadataTypeResolver


class ObjectInsertionMixin:
    """Phase 1 insertion: objects, modules, attributes, tabular sections, enums, BP route data."""

    def _insert_configuration(self, data, progress_callback=None):
        """Вставляет данные конфигурации в БД. Два прохода: сначала все объекты и ФО, затем формы и fo_usage."""
        cursor = self.conn.cursor()
        cursor.execute('PRAGMA synchronous=OFF')
        cursor.execute('PRAGMA cache_size=-256000')
        cursor.execute('PRAGMA temp_store=MEMORY')
        total_objects = len(data['objects'])
        pending_type_slots = []

        t_phase1_start = time.perf_counter()

        # Проход 1: объекты без форм (чтобы ФО были в БД до вставки fo_form_usage и fo_content_ref)
        for idx, obj in enumerate(data['objects']):
            cursor.execute('''
                INSERT INTO metadata_objects (
                    uuid, object_type, name, synonym, comment,
                    object_belonging, extended_configuration_object, object_kind
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, 'ConfigObject')
            ''', (
                obj['uuid'],
                obj['type'],
                obj['name'],
                obj['properties'].get('synonym', ''),
                obj['properties'].get('comment', ''),
                obj['properties'].get('object_belonging'),
                obj['properties'].get('extended_configuration_object')
            ))
            object_id = cursor.lastrowid

            if obj['type'] == 'FunctionalOption':
                loc = obj['properties'].get('location')
                priv = obj['properties'].get('privileged_get_mode')
                cursor.execute('''
                    INSERT INTO functional_options (object_id, location_constant, privileged_get_mode)
                    VALUES (?, ?, ?)
                ''', (object_id, loc, 1 if priv else 0))

            if obj['type'] == 'ScheduledJob':
                p = obj['properties']
                use_val = p.get('use')
                predefined_val = p.get('predefined')
                cursor.execute('''
                    INSERT INTO scheduled_jobs (
                        object_id, method_name, description, key, use, predefined,
                        restart_count_on_failure, restart_interval_on_failure
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    object_id,
                    p.get('method_name'),
                    p.get('description'),
                    p.get('key'),
                    1 if use_val else 0 if use_val is not None else None,
                    1 if predefined_val else 0 if predefined_val is not None else None,
                    p.get('restart_count_on_failure'),
                    p.get('restart_interval_on_failure'),
                ))

            for module in obj['modules']:
                cursor.execute('''
                    INSERT INTO modules (object_id, form_id, command_id, module_type, code)
                    VALUES (?, NULL, NULL, ?, ?)
                ''', (object_id, module['type'], module['code']))
                module_id = cursor.lastrowid
                cursor.execute('''
                    INSERT INTO code_search (rowid, object_name, module_type, code)
                    VALUES (?, ?, ?, ?)
                ''', (module_id, obj['name'], module['type'], module['code']))
                procs = _parse_module_procedures(module['code'])
                if procs:
                    cursor.executemany('''
                        INSERT INTO module_procedures (module_id, name, proc_type, start_line, end_line, params, is_export, execution_context, extension_call_type, comment)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', [(module_id, p['name'], p['proc_type'], p['start_line'], p['end_line'],
                           p['params'], p['is_export'], p['execution_context'], p['extension_call_type'], p['comment']) for p in procs])

            # Команды объекта (не CommonCommand) + модули CommandModule
            if obj['type'] != 'CommonCommand':
                for cmd in obj.get('commands', []):
                    cursor.execute('''
                        INSERT INTO object_commands (
                            object_id, name, synonym, uuid, object_belonging, extended_configuration_object
                        )
                        VALUES (?, ?, ?, ?, ?, ?)
                    ''', (
                        object_id,
                        cmd['name'],
                        cmd.get('synonym') or '',
                        cmd.get('uuid') or '',
                        cmd.get('object_belonging'),
                        cmd.get('extended_configuration_object'),
                    ))
                    command_id = cursor.lastrowid
                    module_code = cmd.get('module_code')
                    if module_code:
                        cursor.execute('''
                            INSERT INTO modules (object_id, form_id, command_id, module_type, code)
                            VALUES (?, NULL, ?, 'CommandModule', ?)
                        ''', (object_id, command_id, module_code))
                        module_id = cursor.lastrowid
                        code_search_name = f"{obj['name']}.{cmd['name']}"
                        cursor.execute('''
                            INSERT INTO code_search (rowid, object_name, module_type, code)
                            VALUES (?, ?, ?, ?)
                        ''', (module_id, code_search_name, 'CommandModule', module_code))
                        procs = _parse_module_procedures(module_code)
                        if procs:
                            cursor.executemany('''
                                INSERT INTO module_procedures (module_id, name, proc_type, start_line, end_line, params, is_export, execution_context, extension_call_type, comment)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            ''', [(module_id, p['name'], p['proc_type'], p['start_line'], p['end_line'],
                                   p['params'], p['is_export'], p['execution_context'], p['extension_call_type'], p['comment']) for p in procs])

            for attr in obj['properties'].get('standard_attributes', []):
                self._insert_attribute(cursor, object_id, attr, pending_type_slots=pending_type_slots)
            for attr in obj['properties'].get('custom_attributes', []):
                self._insert_attribute(cursor, object_id, attr, pending_type_slots=pending_type_slots)
            if obj['type'] not in ('ScheduledJob', 'Subsystem'):
                for dim in obj.get('dimensions', []):
                    self._insert_attribute(cursor, object_id, dim, section='Dimension', pending_type_slots=pending_type_slots)
                for res in obj.get('resources', []):
                    self._insert_attribute(cursor, object_id, res, section='Resource', pending_type_slots=pending_type_slots)
                for attr in obj.get('attributes', []):
                    self._insert_attribute(cursor, object_id, attr, section='Attribute', pending_type_slots=pending_type_slots)
                for ts in obj.get('tabular_sections', []):
                    self._insert_tabular_section(cursor, object_id, ts, pending_type_slots=pending_type_slots)
                enum_values = obj.get('enum_values', [])
                if enum_values:
                    self._insert_enum_values(cursor, object_id, enum_values)
                if obj['type'] == 'BusinessProcess':
                    self._insert_bp_route_data(
                        cursor, object_id,
                        obj.get('route_points', []),
                        obj.get('route_transitions', []),
                    )

            if progress_callback and (idx % 10 == 0 or idx == total_objects - 1):
                progress = 20 + int((idx / total_objects) * 40)
                progress_callback(progress, 100, f"Объекты {idx + 1}/{total_objects}")

        if progress_callback:
            progress_callback(60, 100, f"Объекты ({total_objects}) — {time.perf_counter() - t_phase1_start:.1f} c")

        t_relations_start = time.perf_counter()

        # Справочник ФО для разрешения UUID / "FunctionalOption.Имя" -> id
        cursor.execute('SELECT id, name, uuid FROM metadata_objects WHERE object_type = ?', ('FunctionalOption',))
        fo_resolver = {}
        for row in cursor.fetchall():
            fid, name, uuid_val = row[0], row[1], row[2] or ''
            fo_resolver[uuid_val] = fid
            fo_resolver[name] = fid
            fo_resolver['FunctionalOption.' + name] = fid

        # Справочник (object_type, name) -> id для разрешения Content и типов
        cursor.execute('''
            SELECT id, object_type, name FROM metadata_objects
            WHERE object_kind = 'ConfigObject'
        ''')
        type_name_to_id = {}
        for row in cursor.fetchall():
            type_name_to_id[(row['object_type'], row['name'])] = row['id']

        type_resolver = MetadataTypeResolver()
        if pending_type_slots:
            type_resolver.insert_slots(cursor, pending_type_slots, type_name_to_id)

        self._link_subsystem_relations(cursor, data['objects'], type_name_to_id)

        # Заполняем fo_content_ref из Content каждой ФО
        for obj in data['objects']:
            if obj['type'] != 'FunctionalOption':
                continue
            content_refs = obj['properties'].get('content_refs') or []
            cursor.execute('SELECT id FROM metadata_objects WHERE name = ? AND object_type = ?', (obj['name'], obj['type']))
            fo_row = cursor.fetchone()
            if not fo_row:
                continue
            fo_id = fo_row['id']
            for ref_str in content_refs:
                parsed = self._parse_content_ref(ref_str)
                if not parsed:
                    continue
                obj_type, obj_name, ref_type, ts_name, elem_name = parsed
                meta_id = type_name_to_id.get((obj_type, obj_name))
                if meta_id is None:
                    continue
                cursor.execute('''
                    INSERT INTO fo_content_ref (functional_option_id, metadata_object_id, content_ref_type, tabular_section_name, element_name)
                    VALUES (?, ?, ?, ?, ?)
                ''', (fo_id, meta_id, ref_type, ts_name, elem_name))

        self._link_scheduled_job_procedures(cursor)

        if progress_callback:
            progress_callback(65, 100, f"Связи (типы, подсистемы, ФО, регл. задания) — {time.perf_counter() - t_relations_start:.1f} c")

        t_phase2_start = time.perf_counter()

        # Проход 2: формы и fo_form_usage
        pending_form_type_slots = []
        for idx, obj in enumerate(data['objects']):
            cursor.execute('SELECT id FROM metadata_objects WHERE name = ? AND object_type = ?', (obj['name'], obj['type']))
            row = cursor.fetchone()
            if not row:
                continue
            object_id = row[0]
            for form in obj.get('forms', []):
                self._insert_form(
                    cursor, object_id, obj['name'], form, fo_resolver,
                    pending_type_slots=pending_form_type_slots,
                )

            if progress_callback and (idx % 10 == 0 or idx == total_objects - 1):
                progress = 60 + int((idx / total_objects) * 40)
                progress_callback(progress, 100, f"Формы {idx + 1}/{total_objects}")

        if progress_callback:
            progress_callback(95, 100, f"Формы — {time.perf_counter() - t_phase2_start:.1f} c")

        if pending_form_type_slots:
            type_resolver.insert_slots(cursor, pending_form_type_slots, type_name_to_id)

        self.conn.commit()
        cursor.execute('PRAGMA synchronous=NORMAL')

    def _insert_attribute(self, cursor, object_id, attr, section='Attribute', pending_type_slots=None):
        """Вставляет атрибут объекта в БД"""
        cursor.execute('''
            INSERT INTO attributes (object_id, name, title, comment, is_standard, standard_type, section)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            object_id,
            attr['name'],
            attr.get('title', ''),
            attr.get('comment', ''),
            1 if attr.get('is_standard') else 0,
            attr.get('standard_type'),
            section,
        ))
        if pending_type_slots is not None:
            type_slots = attr.get('type_slots')
            if type_slots:
                pending_type_slots.append({
                    'source_table': 'attributes',
                    'source_row_id': cursor.lastrowid,
                    'src_object_id': object_id,
                    'type_slots': type_slots,
                })

    def _insert_tabular_section(self, cursor, object_id, ts, pending_type_slots=None):
        """Вставляет табличную часть с колонками в БД (tabular_sections + tabular_section_columns)."""
        cursor.execute('''
            INSERT INTO tabular_sections (object_id, name, title, comment)
            VALUES (?, ?, ?, ?)
        ''', (object_id, ts['name'], ts.get('title', ''), ts.get('comment', '')))
        ts_id = cursor.lastrowid
        for column in ts['columns']:
            cursor.execute('''
                INSERT INTO tabular_section_columns (tabular_section_id, column_name, title, comment)
                VALUES (?, ?, ?, ?)
            ''', (ts_id, column['name'], column.get('title', ''), column.get('comment', '')))
            if pending_type_slots is not None:
                type_slots = column.get('type_slots')
                if type_slots:
                    pending_type_slots.append({
                        'source_table': 'tabular_section_columns',
                        'source_row_id': cursor.lastrowid,
                        'src_object_id': object_id,
                        'type_slots': type_slots,
                    })

    def _insert_enum_values(self, cursor, object_id, enum_values):
        """Вставляет значения перечисления в БД"""
        for ev in enum_values:
            cursor.execute('''
                INSERT INTO enum_values (object_id, name, enum_order, title, comment, object_belonging, extended_configuration_object)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                object_id,
                ev['name'],
                ev.get('order'),
                ev.get('title', ''),
                ev.get('comment', ''),
                ev.get('object_belonging'),
                ev.get('extended_configuration_object'),
            ))

    def _insert_bp_route_data(self, cursor, object_id, route_points, route_transitions):
        """Вставляет точки маршрута и переходы бизнес-процесса."""
        for point in route_points:
            cursor.execute('''
                INSERT INTO bp_route_points (
                    object_id, name, point_type, title, uuid, tab_order, true_port, false_port
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                object_id,
                point['name'],
                point['type'],
                point.get('title', ''),
                point.get('uuid', ''),
                point.get('tab_order'),
                point.get('true_port'),
                point.get('false_port'),
            ))
        for transition in route_transitions:
            cursor.execute('''
                INSERT INTO bp_route_transitions (
                    object_id, from_point, to_point, from_port, title
                )
                VALUES (?, ?, ?, ?, ?)
            ''', (
                object_id,
                transition['from'],
                transition['to'],
                transition.get('from_port'),
                transition.get('title', ''),
            ))
