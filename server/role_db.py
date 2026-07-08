"""Read role layer payloads and index metadata from SQLite."""

def read_index_metadata(cursor):
    try:
        rows = cursor.execute('SELECT key, value FROM index_metadata').fetchall()
    except Exception:
        return {}
    return {row[0]: row[1] for row in rows}


def fetch_role_row(cursor, role_name):
    cursor.execute('''
        SELECT id, name, uuid, synonym, object_belonging, extended_configuration_object
        FROM metadata_objects
        WHERE object_type = 'Role' AND name = ? AND object_kind = 'ConfigObject'
        LIMIT 1
    ''', (role_name,))
    return cursor.fetchone()


def fetch_role_layer(cursor, role_object_id):
    """Return grants, access_restrictions, role_settings, restriction_templates for one role in one db."""
    cursor.execute('''
        SELECT set_for_new_objects, set_for_attributes_by_default,
               independent_rights_of_child_objects, source_db_name
        FROM role_settings WHERE role_object_id = ?
    ''', (role_object_id,))
    settings_row = cursor.fetchone()
    role_settings = None
    if settings_row:
        role_settings = {
            'set_for_new_objects': bool(settings_row[0]) if settings_row[0] is not None else None,
            'set_for_attributes_by_default': bool(settings_row[1]) if settings_row[1] is not None else None,
            'independent_rights_of_child_objects': bool(settings_row[2]) if settings_row[2] is not None else None,
        }

    cursor.execute('''
        SELECT target_qname, target_kind, parent_object_qname, right_name, granted, source_db_name
        FROM role_grants WHERE role_object_id = ?
        ORDER BY target_qname, right_name
    ''', (role_object_id,))
    grants = []
    for row in cursor.fetchall():
        grants.append({
            'target_qname': row[0],
            'target_kind': row[1],
            'parent_object_qname': row[2],
            'right_name': row[3],
            'granted': bool(row[4]) if row[4] is not None else None,
            'source_db_name': row[5],
        })

    cursor.execute('''
        SELECT rar.field_scope, rar.restriction_text, rar.source_db_name,
               rg.target_qname, rg.right_name
        FROM role_access_restrictions rar
        JOIN role_grants rg ON rar.grant_id = rg.id
        WHERE rg.role_object_id = ?
        ORDER BY rg.target_qname, rg.right_name, rar.field_scope
    ''', (role_object_id,))
    access_restrictions = []
    for row in cursor.fetchall():
        access_restrictions.append({
            'target_qname': row[3],
            'right_name': row[4],
            'field_scope': row[0],
            'restriction_text': row[1] or '',
            'source_db_name': row[2],
        })

    cursor.execute('''
        SELECT template_name, condition_text, source_db_name
        FROM role_restriction_templates
        WHERE role_object_id = ?
        ORDER BY template_name
    ''', (role_object_id,))
    restriction_templates = [
        {
            'template_name': row[0],
            'condition_text': row[1] or '',
            'source_db_name': row[2],
        }
        for row in cursor.fetchall()
    ]

    return {
        'role_settings': role_settings,
        'grants': grants,
        'access_restrictions': access_restrictions,
        'restriction_templates': restriction_templates,
    }
