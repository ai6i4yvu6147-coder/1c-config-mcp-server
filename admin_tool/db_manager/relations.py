from shared.metadata_type_resolver import parse_event_source_string


class RelationsMixin:
    """metadata_relations materialization (subsystems) and scheduled-job procedure linking."""

    def _link_subsystem_relations(self, cursor, objects, type_name_to_id):
        """Материализует subsystem_member в metadata_relations из Content и ChildObjects подсистем."""
        subsystem_ids = {}
        for obj in objects:
            if obj['type'] != 'Subsystem':
                continue
            cursor.execute(
                'SELECT id FROM metadata_objects WHERE name = ? AND object_type = ?',
                (obj['name'], 'Subsystem'),
            )
            row = cursor.fetchone()
            if row:
                subsystem_ids[obj['name']] = row['id']

        for obj in objects:
            if obj['type'] != 'Subsystem':
                continue
            src_id = subsystem_ids.get(obj['name'])
            if src_id is None:
                continue

            for ref_str in obj.get('content_refs') or []:
                if '.' not in ref_str:
                    continue
                obj_type, obj_name = ref_str.split('.', 1)
                dst_id = type_name_to_id.get((obj_type, obj_name))
                if dst_id is None:
                    continue
                cursor.execute('''
                    INSERT INTO metadata_relations (
                        src_object_id, dst_object_id, relation_kind, source_name, source_detail
                    )
                    VALUES (?, ?, 'subsystem_member', ?, 'Content')
                ''', (src_id, dst_id, ref_str))

            parent_qname = obj['name']
            for child_name in obj.get('child_subsystem_names') or []:
                child_qname = f'{parent_qname}.{child_name}'
                dst_id = subsystem_ids.get(child_qname)
                if dst_id is None:
                    continue
                cursor.execute('''
                    INSERT INTO metadata_relations (
                        src_object_id, dst_object_id, relation_kind, source_name, source_detail
                    )
                    VALUES (?, ?, 'subsystem_member', ?, 'ChildSubsystem')
                ''', (src_id, dst_id, child_name))

    def _link_event_subscription_relations(self, cursor, objects, type_name_to_id):
        """Материализует event_subscription в metadata_relations из Source подписок.

        Разворачиваются только конкретные источники (`cfg:DocumentObject.РеализацияТоваров`):
        у них есть один объект-адресат, поэтому обратный поиск по документу находит подписку.
        Источники-вид-целиком (`cfg:DocumentObject` — «все документы») намеренно НЕ
        разворачиваются: это дало бы декартово произведение (325 подписок × тысячи объектов);
        они лежат строкой в event_subscriptions.source_kinds и видны в get_object_structure.
        В source_name кладём событие, в source_detail — обработчик: обратный поиск тогда
        отвечает не только «кто», но и «на что и чем».
        """
        rows = []
        for obj in objects:
            if obj['type'] != 'EventSubscription':
                continue
            src_id = type_name_to_id.get(('EventSubscription', obj['name']))
            if src_id is None:
                continue
            properties = obj['properties']
            event = properties.get('event') or ''
            handler = properties.get('handler') or ''
            seen = set()
            for source in properties.get('sources') or []:
                parsed = parse_event_source_string(source.get('raw'))
                if parsed['kind'] != 'object_ref' or not parsed['object_type']:
                    continue
                dst_id = type_name_to_id.get((parsed['object_type'], parsed['ref_name']))
                # dst_id is None — источник ссылается на неиндексируемый вид (журналы
                # документов, последовательности): связь пропускаем, подписка не теряется.
                if dst_id is None or dst_id in seen:
                    continue
                seen.add(dst_id)
                rows.append((src_id, dst_id, event, handler))
        if rows:
            cursor.executemany('''
                INSERT INTO metadata_relations (
                    src_object_id, dst_object_id, relation_kind, source_name, source_detail
                )
                VALUES (?, ?, 'event_subscription', ?, ?)
            ''', rows)

    def _link_event_subscription_procedures(self, cursor):
        """Проставляет used_in_event_subscription процедурам общих модулей из Handler подписок."""
        cursor.execute('''
            UPDATE module_procedures SET used_in_event_subscription = 1
            WHERE id IN (
                SELECT p.id
                FROM event_subscriptions es
                JOIN metadata_objects o
                  ON o.object_type = 'CommonModule' AND o.name = es.handler_module
                JOIN modules m
                  ON m.object_id = o.id AND m.module_type = 'Module'
                 AND m.form_id IS NULL AND m.command_id IS NULL
                JOIN module_procedures p
                  ON p.module_id = m.id AND p.name = es.handler_procedure
                WHERE es.handler_module IS NOT NULL
            )
        ''')

    def _link_scheduled_job_procedures(self, cursor):
        """Проставляет used_in_scheduled_job для процедур общих модулей из MethodName регл. заданий."""
        cursor.execute('SELECT method_name FROM scheduled_jobs WHERE method_name IS NOT NULL')
        for row in cursor.fetchall():
            method_name = (row['method_name'] or '').strip()
            if not method_name:
                continue
            parts = method_name.split('.')
            if len(parts) != 3 or parts[0] != 'CommonModule':
                continue
            module_name, procedure_name = parts[1], parts[2]
            cursor.execute('''
                SELECT p.id
                FROM module_procedures p
                JOIN modules m ON p.module_id = m.id
                JOIN metadata_objects o ON m.object_id = o.id
                WHERE o.object_type = 'CommonModule' AND o.name = ?
                  AND m.module_type = 'Module'
                  AND m.form_id IS NULL AND m.command_id IS NULL
                  AND p.name = ?
            ''', (module_name, procedure_name))
            proc_row = cursor.fetchone()
            if proc_row:
                cursor.execute(
                    'UPDATE module_procedures SET used_in_scheduled_job = 1 WHERE id = ?',
                    (proc_row['id'],),
                )
