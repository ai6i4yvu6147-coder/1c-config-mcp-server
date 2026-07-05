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
