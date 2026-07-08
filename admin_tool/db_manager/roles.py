class RoleInsertionMixin:
    """Materialize role_settings, role_grants, role_access_restrictions, role_restriction_templates."""

    def _insert_index_metadata(self, cursor, data):
        """Persist build-time metadata for MCP merge and active_databases."""
        source_db_name = data.get('name') or ''
        extension_purpose = data.get('extension_purpose') or ''
        rows = [
            ('config_name', source_db_name),
            ('source_db_name', source_db_name),
            ('extension_purpose', extension_purpose),
        ]
        for key, value in rows:
            cursor.execute(
                'INSERT OR REPLACE INTO index_metadata (key, value) VALUES (?, ?)',
                (key, value),
            )

    def _insert_role_data(self, cursor, role_object_id, obj, source_db_name):
        """Insert parsed role payload for one Role metadata object."""
        settings = obj.get('role_settings')
        if settings is not None:
            cursor.execute('''
                INSERT INTO role_settings (
                    role_object_id, set_for_new_objects, set_for_attributes_by_default,
                    independent_rights_of_child_objects, source_db_name
                )
                VALUES (?, ?, ?, ?, ?)
            ''', (
                role_object_id,
                1 if settings.get('set_for_new_objects') else 0 if settings.get('set_for_new_objects') is False else None,
                1 if settings.get('set_for_attributes_by_default') else 0 if settings.get('set_for_attributes_by_default') is False else None,
                1 if settings.get('independent_rights_of_child_objects') else 0 if settings.get('independent_rights_of_child_objects') is False else None,
                source_db_name,
            ))

        grant_id_by_key = {}
        for grant in obj.get('role_grants') or []:
            granted = grant.get('granted')
            cursor.execute('''
                INSERT INTO role_grants (
                    role_object_id, target_qname, target_kind, parent_object_qname,
                    right_name, granted, source_db_name
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                role_object_id,
                grant['target_qname'],
                grant['target_kind'],
                grant['parent_object_qname'],
                grant['right_name'],
                1 if granted else 0 if granted is False else None,
                source_db_name,
            ))
            if granted:
                grant_id_by_key[(grant['target_qname'], grant['right_name'])] = cursor.lastrowid

        for restr in obj.get('role_access_restrictions') or []:
            key = (restr['target_qname'], restr['right_name'])
            grant_id = grant_id_by_key.get(key)
            if grant_id is None:
                continue
            cursor.execute('''
                INSERT INTO role_access_restrictions (
                    grant_id, field_scope, restriction_text, source_db_name
                )
                VALUES (?, ?, ?, ?)
            ''', (
                grant_id,
                restr.get('field_scope'),
                restr.get('restriction_text') or '',
                source_db_name,
            ))

        for tmpl in obj.get('role_restriction_templates') or []:
            cursor.execute('''
                INSERT INTO role_restriction_templates (
                    role_object_id, template_name, condition_text, source_db_name
                )
                VALUES (?, ?, ?, ?)
            ''', (
                role_object_id,
                tmpl['template_name'],
                tmpl.get('condition_text') or '',
                source_db_name,
            ))
