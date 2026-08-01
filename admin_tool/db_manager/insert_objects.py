import json
import time

from .bsl import _parse_module_procedures
from shared.metadata_type_resolver import MetadataTypeResolver

#: Виды объектов, которые после вставки нужны ещё раз — на этапе связей (подсистемы: Content и
#: дочерние подсистемы; подписки: источники; ФО: Content). Только их и удерживаем до конца
#: сборки; у всех остальных после вставки не остаётся ни одной ссылки. Тяжёлые поля
#: (модули/формы/реквизиты) к этому моменту уже освобождены и у этих трёх видов тоже.
RELATION_SOURCE_TYPES = ('Subsystem', 'EventSubscription', 'FunctionalOption')


class _InsertState:
    """Отложенное и накопленное за потоковый проход по объектам (см. `_insert_configuration`)."""

    def __init__(self, source_db_name):
        self.source_db_name = source_db_name
        #: Слоты типов реквизитов/ТЧ/объектов — разрешаются после прохода, когда известны все id.
        self.pending_type_slots = []
        #: То же для слотов реквизитов форм (отдельный список: порядок строк
        #: metadata_type_slots — сначала объектные слоты, потом формные, как и раньше).
        self.pending_form_type_slots = []
        #: fo_form_usage: (fo_ref, owner_object_id, form_id, element_type, element_name,
        #: parent_element_name) — ссылку на ФО можно разрешить только когда вставлены все ФО.
        self.pending_fo_usage = []
        #: (object_type, name) -> id. Раньше строился SELECT-ом после первого прохода.
        self.type_name_to_id = {}
        #: uuid / имя / 'FunctionalOption.Имя' -> id функциональной опции.
        self.fo_resolver = {}
        #: Объекты видов RELATION_SOURCE_TYPES — нужны на этапе связей.
        self.relation_objects = []


class ObjectInsertionMixin:
    """Streaming insertion: objects with their forms, then relations and deferred resolution."""

    def _insert_configuration(self, data, progress_callback=None, after_objects=None):
        """Вставляет конфигурацию в БД одним потоковым проходом по объектам.

        `data['objects']` — список **или генератор** (`ConfigurationParser.parse_streaming`).
        Каждый объект вставляется целиком, вместе со своими формами, и тут же отпускается:
        пик памяти перестаёт зависеть от размера конфигурации (`parser-streaming-pipeline`,
        остаток P-4 из audit-2026-08). Прежде вставка шла двумя проходами по полностью
        разобранному дереву — сначала все объекты, затем все формы.

        Что мешало сделать так раньше и как обойдено: формам нужны справочники, полные только
        после обхода **всех** объектов — id функциональных опций (`fo_form_usage`) и
        (object_type, name) → id (слоты типов). Оба теперь копятся в памяти по ходу вставки
        (раньше их брал SELECT после первого прохода), а то, что требует их полноты,
        откладывается до конца: слоты типов (как и раньше) и `fo_form_usage`
        (`pending_fo_usage`). Порядок строк в обеих таблицах сохраняется — отложенное
        разрешение идёт по тому же списку, в котором формы вставлялись.

        `after_objects` — callable без аргументов, вызывается сразу после обхода объектов:
        сборка выводит им разбивку времени парсинга, которая при потоковом разборе известна
        только когда поток вычерпан.
        """
        cursor = self.conn.cursor()
        cursor.execute('PRAGMA synchronous=OFF')
        cursor.execute('PRAGMA cache_size=-256000')
        cursor.execute('PRAGMA temp_store=MEMORY')

        objects = data['objects']
        expected_total = data.get('expected_object_count')
        if expected_total is None:
            expected_total = len(objects) if isinstance(objects, (list, tuple)) else 0
        state = _InsertState(data.get('name') or '')

        t_objects_start = time.perf_counter()

        total_objects = 0
        for idx, obj in enumerate(objects):
            total_objects = idx + 1
            self._insert_object(cursor, obj, state)

            if progress_callback and idx % 10 == 0:
                progress = 20 + int((idx / expected_total) * 70) if expected_total else 20
                progress_callback(
                    min(progress, 90), 100,
                    f"Объекты и формы {idx + 1}/{expected_total or '?'}", replace_last=True,
                )

        if progress_callback:
            progress_callback(
                90, 100,
                f"Объекты и формы ({total_objects}) — {time.perf_counter() - t_objects_start:.1f} c",
            )

        if after_objects is not None:
            after_objects()

        self._finalize_configuration(cursor, state, data, progress_callback)

    def _insert_object(self, cursor, obj, state):
        """Вставляет один объект целиком: сам объект, его модули/реквизиты/секции/команды и формы.

        Всё, что уже записано, тут же освобождается (`obj[...] = None`) — для потокового входа
        это лишь ускоряет освобождение, для списочного (dev-скрипты) остаётся единственным
        способом не держать всё дерево до конца сборки."""
        pending_type_slots = state.pending_type_slots

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

        # Справочник (object_type, name) -> id: раньше SELECT после первого прохода, теперь
        # копится здесь. Дубли имён внутри вида перетирают друг друга в том же порядке, что и
        # при чтении строк по возрастанию id, — карта получается та же.
        state.type_name_to_id[(obj['type'], obj['name'])] = object_id

        if obj['type'] == 'FunctionalOption':
            loc = obj['properties'].get('location')
            priv = obj['properties'].get('privileged_get_mode')
            cursor.execute('''
                INSERT INTO functional_options (object_id, location_constant, privileged_get_mode)
                VALUES (?, ?, ?)
            ''', (object_id, loc, 1 if priv else 0))
            uuid_val = obj['uuid'] or ''
            state.fo_resolver[uuid_val] = object_id
            state.fo_resolver[obj['name']] = object_id
            state.fo_resolver['FunctionalOption.' + obj['name']] = object_id

        if obj['type'] == 'EventSubscription':
            p = obj['properties']
            handler = (p.get('handler') or '').strip()
            # Handler — всегда CommonModule.<Модуль>.<Процедура> (проверено на корпусе:
            # 1110 подписок, других префиксов нет). Разбираем заранее, чтобы не парсить
            # строку в каждом запросе — по handler_module идёт пометка процедур.
            parts = handler.split('.')
            handler_module = parts[1] if len(parts) == 3 and parts[0] == 'CommonModule' else None
            handler_procedure = parts[2] if len(parts) == 3 and parts[0] == 'CommonModule' else None
            kind_wide = [
                s['raw'] for s in (p.get('sources') or [])
                if s.get('is_type_set') and '.' not in s.get('raw', '')
            ]
            cursor.execute('''
                INSERT INTO event_subscriptions (
                    object_id, event, handler, handler_module, handler_procedure, source_kinds
                )
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                object_id,
                p.get('event'),
                handler or None,
                handler_module,
                handler_procedure,
                ', '.join(kind_wide) or None,
            ))

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

        if obj['type'] == 'Role':
            self._insert_role_data(cursor, object_id, obj, state.source_db_name)
            obj['role_grants'] = None
            obj['role_access_restrictions'] = None
            obj['role_restriction_templates'] = None

        # Тип, объявленный на самом объекте: состав DefinedType и тип значения Constant.
        if obj['type'] in ('DefinedType', 'Constant'):
            type_slots = obj.get('type_slots') or []
            if type_slots:
                pending_type_slots.append({
                    'source_table': 'metadata_objects',
                    'source_row_id': object_id,
                    'src_object_id': object_id,
                    'type_slots': type_slots,
                })

        for module in obj['modules']:
            cursor.execute('''
                INSERT INTO modules (object_id, form_id, command_id, module_type, code)
                VALUES (?, NULL, NULL, ?, ?)
            ''', (object_id, module['type'], module['code']))
            module_id = cursor.lastrowid
            cursor.execute('''
                INSERT INTO code_search (rowid, code)
                VALUES (?, ?)
            ''', (module_id, module['code']))
            procs = _parse_module_procedures(module['code'])
            if procs:
                cursor.executemany('''
                    INSERT INTO module_procedures (module_id, name, proc_type, start_line, end_line, params, is_export, execution_context, extension_call_type, comment)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', [(module_id, p['name'], p['proc_type'], p['start_line'], p['end_line'],
                       p['params'], p['is_export'], p['execution_context'], p['extension_call_type'], p['comment']) for p in procs])
        # P-4 (audit-2026-08): module code is the single biggest chunk of a parsed object
        # (904 MB across modules on the ERP corpus) — drop it the moment it's inserted.
        obj['modules'] = None

        # Срез 1 (dcs-schema-indexing): текст запроса набора СКД -> code_search (FTS).
        # code_search — внешнее содержимое над modules, поэтому кладём запрос строкой
        # modules с module_type='DcsQuery' (владелец — объект шаблона). Схемы без
        # <query> (правила отбора каталогов) не дают строки — деградация без ошибки.
        self._insert_dcs_schemas(cursor, object_id, obj)
        self._insert_spreadsheet_templates(cursor, object_id, obj)

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
                    cursor.execute('''
                        INSERT INTO code_search (rowid, code)
                        VALUES (?, ?)
                    ''', (module_id, module_code))
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
        if obj['type'] not in ('ScheduledJob', 'Subsystem', 'DefinedType'):
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
                obj['route_points'] = None
                obj['route_transitions'] = None
            obj['tabular_sections'] = None
            obj['dimensions'] = None
            obj['resources'] = None
            obj['attributes'] = None
            obj['enum_values'] = None
        obj['commands'] = None
        obj['dcs_schemas'] = None
        obj['spreadsheet_templates'] = None
        if 'type_slots' in obj:
            obj['type_slots'] = None

        # Формы того же объекта — сразу здесь, а не вторым проходом: id объекта уже известен
        # (раньше его искали SELECT-ом по имени и виду), ссылки на ФО и слоты типов отложены.
        for form in obj.get('forms') or []:
            self._insert_form(
                cursor, object_id, form,
                pending_type_slots=state.pending_form_type_slots,
                pending_fo_usage=state.pending_fo_usage,
            )
        # P-4 (audit-2026-08): form item/attribute/command trees are the second-biggest chunk
        # of a parsed object (349k form_items + 137k form_attributes + 61k form_commands +
        # 1.9M form_entity_properties rows on the ERP corpus) — release once inserted.
        obj['forms'] = None

        if obj['type'] in RELATION_SOURCE_TYPES:
            state.relation_objects.append(obj)

    def _finalize_configuration(self, cursor, state, data, progress_callback=None):
        """Хвост сборки: связи и всё отложенное, чему нужны полные справочники объектов."""
        t_relations_start = time.perf_counter()

        type_name_to_id = state.type_name_to_id
        type_resolver = MetadataTypeResolver()
        if state.pending_type_slots:
            type_resolver.insert_slots(cursor, state.pending_type_slots, type_name_to_id)
            state.pending_type_slots = []

        # fo_form_usage: ссылки на ФО, накопленные при вставке форм (порядок сохранён).
        for (fo_ref, owner_object_id, form_id, element_type,
             element_name, parent_element_name) in state.pending_fo_usage:
            fo_id = self._resolve_fo_id(fo_ref, state.fo_resolver)
            if fo_id is not None:
                self._insert_fo_form_usage(
                    cursor, fo_id, owner_object_id, form_id,
                    element_type, element_name, parent_element_name,
                )
        state.pending_fo_usage = []

        self._link_subsystem_relations(cursor, state.relation_objects, type_name_to_id)
        self._link_event_subscription_relations(cursor, state.relation_objects, type_name_to_id)

        # Заполняем fo_content_ref из Content каждой ФО
        for obj in state.relation_objects:
            if obj['type'] != 'FunctionalOption':
                continue
            content_refs = obj['properties'].get('content_refs') or []
            fo_id = type_name_to_id.get(('FunctionalOption', obj['name']))
            if fo_id is None:
                continue
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
        self._link_event_subscription_procedures(cursor)

        if state.pending_form_type_slots:
            type_resolver.insert_slots(cursor, state.pending_form_type_slots, type_name_to_id)
            state.pending_form_type_slots = []

        if progress_callback:
            progress_callback(
                95, 100,
                f"Связи (типы, подсистемы, ФО, регл. задания, подписки) — "
                f"{time.perf_counter() - t_relations_start:.1f} c",
            )

        self._insert_index_metadata(cursor, data)

        self.conn.commit()

        # Без sqlite_stat1 планировщик работает на дефолтных эвристиках и на базе в
        # несколько ГБ выбирает SCAN там, где индекс дешевле. На ЕРП (3.3 ГБ) ANALYZE
        # занимает 1.8 c — это последний шаг сборки, дальше база только читается.
        t_analyze = time.perf_counter()
        cursor.execute('ANALYZE')
        self.conn.commit()
        if progress_callback:
            progress_callback(98, 100, f"ANALYZE — {time.perf_counter() - t_analyze:.1f} c")

    def _insert_dcs_schemas(self, cursor, object_id, obj):
        """DCS templates of an object (dcs-schema-indexing):

        - Срез 1: each dataset query text -> code_search (FTS) as a 'DcsQuery' module row
          (external content over modules). Query-less schemas add no row (graceful
          degradation).
        - Срез 2: one extractable document per schema -> dcs_schema (schema_json blob +
          denormalised shape hints for cheap listing / query-vs-rule distinction).

        See docs/dcs-schema-indexing.md."""
        for dcs in obj.get('dcs_schemas', []):
            template_name = dcs.get('template_name', '')

            # Срез 1
            for query_text in dcs.get('query_texts', []):
                if not (query_text and query_text.strip()):
                    continue
                cursor.execute('''
                    INSERT INTO modules (object_id, form_id, command_id, module_type, code)
                    VALUES (?, NULL, NULL, 'DcsQuery', ?)
                ''', (object_id, query_text))
                module_id = cursor.lastrowid
                cursor.execute('''
                    INSERT INTO code_search (rowid, code)
                    VALUES (?, ?)
                ''', (module_id, query_text))

            # Срез 2
            shape = dcs.get('shape') or {}
            cursor.execute('''
                INSERT INTO dcs_schema (
                    object_id, template_name, has_query, dataset_count, field_count,
                    parameter_count, calculated_count, total_count, has_grouping,
                    filter_item_count, schema_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                object_id,
                template_name,
                1 if shape.get('has_query') else 0,
                shape.get('dataset_count', 0),
                shape.get('field_count', 0),
                shape.get('parameter_count', 0),
                shape.get('calculated_count', 0),
                shape.get('total_count', 0),
                1 if shape.get('has_grouping') else 0,
                shape.get('filter_item_count', 0),
                json.dumps(dcs.get('schema') or {}, ensure_ascii=False),
            ))

    def _insert_spreadsheet_templates(self, cursor, object_id, obj):
        """MXL macets of an object (mxl-macet-indexing), Срез 1: the macet's visible text
        (cell text + whole-cell parameters + named-area names) -> code_search (FTS) as an
        'MxlText' module row (external content over modules). Text-less macets add no row
        (graceful degradation). See docs/mxl-macet-indexing.md."""
        for macet in obj.get('spreadsheet_templates', []):
            text = macet.get('text')
            if not (text and text.strip()):
                continue
            cursor.execute('''
                INSERT INTO modules (object_id, form_id, command_id, module_type, code)
                VALUES (?, NULL, NULL, 'MxlText', ?)
            ''', (object_id, text))
            module_id = cursor.lastrowid
            cursor.execute('''
                INSERT INTO code_search (rowid, code)
                VALUES (?, ?)
            ''', (module_id, text))

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
