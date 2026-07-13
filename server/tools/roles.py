from server.role_db import fetch_role_layer, fetch_role_row, read_index_metadata
from server.role_merge import (
    filter_grants,
    filter_restrictions,
    filter_used_templates,
    grant_stats,
    merge_grants,
    merge_restrictions,
    merge_role_settings,
    merge_templates,
    restriction_preview,
    should_use_summary_mode,
    sort_layers_for_merge,
)

DEFAULT_MAX_RESULTS = 200


def _config_to_registry_map(layer_payloads):
    return {
        layer['source_db_name']: layer['db_name']
        for layer in layer_payloads
        if layer.get('source_db_name') and layer.get('db_name')
    }


def _agent_db_name(config_name, layer_map, fallback=None):
    if config_name and config_name in layer_map:
        return layer_map[config_name]
    return fallback or config_name


def _with_agent_db_name(item, layer_map, fallback_db_name=None):
    out = {k: v for k, v in item.items() if k != 'source_db_name'}
    config_name = item.get('source_db_name')
    db_name = _agent_db_name(config_name, layer_map, fallback_db_name)
    if db_name:
        out['db_name'] = db_name
    return out


def _restriction_templates_out(templates, include_restriction_text, layer_map, fallback_db):
    out = []
    for t in templates:
        item = _with_agent_db_name(
            {'template_name': t['template_name'], 'source_db_name': t.get('source_db_name')},
            layer_map, fallback_db,
        )
        preview = restriction_preview(t.get('condition_text'), include_restriction_text)
        if preview is not None:
            if include_restriction_text == 'full':
                item['condition_text'] = preview
            else:
                item['condition_text_preview'] = preview
        out.append(item)
    return out


def _role_dict(row, db_info):
    item = {
        'role_name': row['name'],
        'role_qualified_name': f"Role.{row['name']}",
        'uuid': row['uuid'],
        'synonym': row['synonym'] or '',
        'source_layer': 'main' if db_info.get('db_type') == 'base' else 'extension',
        'extension_name': None if db_info.get('db_type') == 'base' else db_info.get('db_name'),
    }
    if row['object_belonging']:
        item['object_belonging'] = row['object_belonging']
    if row['extended_configuration_object']:
        item['extended_configuration_object_uuid'] = row['extended_configuration_object']
    return item


def _query_roles_for_object_rows(cursor, parent_qname, right_name=None, rls=None):
    sql = '''
        SELECT DISTINCT mo.id AS role_object_id, mo.name AS role_name, mo.uuid,
               rg.right_name, rg.granted
        FROM role_grants rg
        JOIN metadata_objects mo ON rg.role_object_id = mo.id
        WHERE rg.parent_object_qname = ? AND rg.granted = 1
    '''
    params = [parent_qname]
    if right_name:
        sql += ' AND rg.right_name = ?'
        params.append(right_name)
    sql += ' ORDER BY mo.name, rg.right_name'

    cursor.execute(sql, params)
    all_rows = cursor.fetchall()

    if rls is not None:
        cursor.execute('''
            SELECT DISTINCT rg.role_object_id
            FROM role_access_restrictions rar
            JOIN role_grants rg ON rar.grant_id = rg.id
            WHERE rg.parent_object_qname = ?
        ''', (parent_qname,))
        role_ids_with_rls = {r[0] for r in cursor.fetchall()}
        if rls is True:
            all_rows = [r for r in all_rows if r['role_object_id'] in role_ids_with_rls]
        else:
            all_rows = [r for r in all_rows if r['role_object_id'] not in role_ids_with_rls]

    return all_rows


class RolesMixin:
    """Role search and rights tools (phase 4)."""

    def find_role(self, name, project_filter=None, extension_filter=None):
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
                SELECT id, name, uuid, synonym, object_belonging, extended_configuration_object
                FROM metadata_objects
                WHERE object_type = 'Role' AND object_kind = 'ConfigObject'
                  AND (name LIKE ? OR IFNULL(synonym, '') LIKE ?)
                ORDER BY name
            ''', (f'%{name}%', f'%{name}%'))

            rows = cursor.fetchall()
            if not rows:
                continue

            project_key = db_info['project_name']
            results.setdefault(project_key, {})
            db_key = f"{db_info['db_name']} ({db_info['db_type']})"
            results[project_key][db_key] = [_role_dict(row, db_info) for row in rows]

        return results

    def list_roles(self, project_filter=None, extension_filter=None, limit=200):
        self._require_project_filter(project_filter)
        databases = self._get_active_databases(project_filter)
        self._require_project_exists(project_filter, databases)
        if extension_filter:
            databases = [db for db in databases if db['db_name'].lower() == extension_filter.lower()]

        if limit is None or limit < 1:
            limit = 200

        results = {}
        for db_info in databases:
            conn = self._get_connection(db_info['db_path'])
            cursor = conn.cursor()

            total = cursor.execute(
                "SELECT COUNT(*) FROM metadata_objects WHERE object_type = 'Role' AND object_kind = 'ConfigObject'"
            ).fetchone()[0]

            cursor.execute('''
                SELECT name, uuid, synonym, object_belonging, extended_configuration_object
                FROM metadata_objects
                WHERE object_type = 'Role' AND object_kind = 'ConfigObject'
                ORDER BY name
                LIMIT ?
            ''', (limit,))
            rows = cursor.fetchall()

            project_key = db_info['project_name']
            results.setdefault(project_key, {})
            db_key = f"{db_info['db_name']} ({db_info['db_type']})"
            roles = []
            for row in rows:
                roles.append({
                    'role_qualified_name': f"Role.{row['name']}",
                    'role_name': row['name'],
                    'uuid': row['uuid'],
                    'synonym': row['synonym'] or '',
                })
            results[project_key][db_key] = {
                'roles': roles,
                'total_count': total,
                'is_truncated': total > len(roles),
            }

        return results

    def get_role_rights(
        self,
        role_name,
        project_filter=None,
        extension_filter=None,
        merge=True,
        object_name=None,
        rights=None,
        rls=None,
        depth='object',
        include_restriction_text=False,
        max_results=DEFAULT_MAX_RESULTS,
        response_mode=None,
    ):
        self._require_project_filter(project_filter)
        databases = self._get_active_databases(project_filter)
        self._require_project_exists(project_filter, databases)

        if max_results is None or max_results < 1:
            max_results = DEFAULT_MAX_RESULTS

        if merge and extension_filter:
            extension_filter = None

        if not merge and not extension_filter and len(databases) > 1:
            databases = [db for db in databases if db.get('db_type') == 'base'] or databases[:1]

        layer_payloads = []
        role_row = None
        for db_info in databases:
            if not merge and extension_filter and db_info['db_name'].lower() != extension_filter.lower():
                continue
            conn = self._get_connection(db_info['db_path'])
            cursor = conn.cursor()
            meta = read_index_metadata(cursor)
            row = fetch_role_row(cursor, role_name)
            if row is None:
                continue
            if role_row is None:
                role_row = row
            layer_payloads.append({
                'db_type': db_info.get('db_type'),
                'db_name': db_info.get('db_name'),
                'extension_purpose': meta.get('extension_purpose') or '',
                'source_db_name': meta.get('source_db_name') or db_info.get('db_name'),
                **fetch_role_layer(cursor, row['id']),
            })

        if role_row is None:
            return {'error': 'not_found', 'role_name': role_name}

        if merge:
            layer_payloads = sort_layers_for_merge(layer_payloads)

        layer_map = _config_to_registry_map(layer_payloads)
        fallback_db = layer_payloads[0]['db_name'] if len(layer_payloads) == 1 else None

        settings = merge_role_settings(layer_payloads) if merge else (
            layer_payloads[0]['role_settings'] if layer_payloads else None
        )
        if settings and settings.get('source_db_name'):
            settings = _with_agent_db_name(settings, layer_map, fallback_db)

        all_grants = merge_grants(layer_payloads) if merge else (layer_payloads[0]['grants'] if layer_payloads else [])
        all_restrictions = merge_restrictions(layer_payloads) if merge else (
            layer_payloads[0]['access_restrictions'] if layer_payloads else []
        )
        all_templates = merge_templates(layer_payloads) if merge else (
            layer_payloads[0]['restriction_templates'] if layer_payloads else []
        )

        grants = filter_grants(all_grants, object_name=object_name, rights=rights, depth=depth)
        restrictions = filter_restrictions(all_restrictions, rls=rls, object_name=object_name)
        used_templates = filter_used_templates(all_templates, restrictions)

        total_grant_count = len(grants)
        use_summary = should_use_summary_mode(
            role_name, total_grant_count, object_name, response_mode, max_results
        )

        extension_delta_grants = []
        if merge and use_summary:
            main_sources = {
                layer['source_db_name'] for layer in layer_payloads if layer.get('db_type') == 'base'
            }
            extension_delta_grants = [
                g for g in all_grants
                if g.get('source_db_name') not in main_sources
            ]
            extension_delta_grants = filter_grants(
                extension_delta_grants, object_name=object_name, rights=rights, depth=depth
            )[:max_results]
            extension_delta_grants = [
                _with_agent_db_name(g, layer_map) for g in extension_delta_grants
            ]

        payload = {
            'role': {
                'name': role_row['name'],
                'qualified_name': f"Role.{role_row['name']}",
                'uuid': role_row['uuid'],
                'synonym': role_row['synonym'] or '',
            },
            'settings': settings,
            'merge': bool(merge),
            'layers': [layer['db_name'] for layer in layer_payloads],
            'restriction_templates': _restriction_templates_out(
                used_templates, include_restriction_text, layer_map, fallback_db
            ),
        }

        if role_row['object_belonging']:
            payload['role']['object_belonging'] = role_row['object_belonging']
        if role_row['extended_configuration_object']:
            payload['role']['extended_configuration_object_uuid'] = role_row['extended_configuration_object']

        restr_out = []
        for restr in restrictions[:max_results]:
            item = _with_agent_db_name({
                'object': restr['target_qname'],
                'right': restr['right_name'],
                'field_scope': restr.get('field_scope'),
                'source_db_name': restr.get('source_db_name'),
            }, layer_map, fallback_db)
            preview = restriction_preview(
                restr.get('restriction_text'), include_restriction_text
            )
            if preview is not None:
                if include_restriction_text == 'full':
                    item['restriction_text'] = preview
                else:
                    item['restriction_text_preview'] = preview
            restr_out.append(item)

        payload['access_restrictions'] = restr_out
        payload['access_restrictions_total_count'] = len(restrictions)
        payload['access_restrictions_is_truncated'] = len(restrictions) > max_results

        if use_summary:
            payload['response_mode'] = 'summary'
            payload['role_profile'] = 'admin_full' if role_name == 'ПолныеПрава' else None
            payload['grant_stats'] = grant_stats(all_grants if depth == 'all' else filter_grants(all_grants, depth='object'))
            payload['grants'] = []
            payload['extension_delta_grants'] = extension_delta_grants
            payload['is_truncated'] = True
            payload['total_count'] = total_grant_count
            payload['hint'] = (
                'Admin role; use object_name filter or response_mode=full for enumeration.'
                if role_name == 'ПолныеПрава'
                else 'Large role; use object_name filter or response_mode=full for enumeration.'
            )
        else:
            payload['response_mode'] = 'full'
            payload['grants'] = [
                _with_agent_db_name(g, layer_map, fallback_db) for g in grants[:max_results]
            ]
            payload['is_truncated'] = total_grant_count > max_results
            payload['total_count'] = total_grant_count

        return payload

    def find_roles_for_object(
        self,
        object_name,
        project_filter=None,
        extension_filter=None,
        merge=False,
        right_name=None,
        rls=None,
        max_results=DEFAULT_MAX_RESULTS,
    ):
        self._require_project_filter(project_filter)
        databases = self._get_active_databases(project_filter)
        self._require_project_exists(project_filter, databases)

        if max_results is None or max_results < 1:
            max_results = DEFAULT_MAX_RESULTS

        from .relations import _resolve_config_object

        if merge and extension_filter:
            merge = False

        if merge:
            return self._find_roles_for_object_merged(
                object_name, databases, right_name, rls, max_results, _resolve_config_object,
            )

        if extension_filter:
            databases = [db for db in databases if db['db_name'].lower() == extension_filter.lower()]

        results = {}
        for db_info in databases:
            conn = self._get_connection(db_info['db_path'])
            cursor = conn.cursor()

            resolved = _resolve_config_object(cursor, object_name)
            project_key = db_info['project_name']
            results.setdefault(project_key, {})

            if resolved['status'] == 'not_found':
                results[project_key][f"{db_info['db_name']} ({db_info['db_type']})"] = {
                    'error': 'not_found',
                }
                continue
            if resolved['status'] == 'ambiguous':
                results[project_key][f"{db_info['db_name']} ({db_info['db_type']})"] = {
                    'ambiguous': True,
                    'candidates': resolved['candidates'],
                }
                continue

            row = resolved['row']
            parent_qname = f"{row['object_type']}.{row['name']}"
            all_rows = _query_roles_for_object_rows(cursor, parent_qname, right_name, rls)

            roles = []
            for r in all_rows[:max_results]:
                roles.append({
                    'role_qualified_name': f"Role.{r['role_name']}",
                    'role_name': r['role_name'],
                    'uuid': r['uuid'],
                    'right_name': r['right_name'],
                })

            has_polnye_prava = cursor.execute(
                "SELECT 1 FROM metadata_objects WHERE object_type='Role' AND name='ПолныеПрава' LIMIT 1"
            ).fetchone()

            db_payload = {
                'target': {'type': row['object_type'], 'name': row['name']},
                'roles': roles,
                'total_count': len(all_rows),
                'is_truncated': len(all_rows) > max_results,
            }
            if has_polnye_prava:
                db_payload['admin_roles_note'] = (
                    'Role.ПолныеПрава grants broad access by policy; not enumerated per object.'
                )
            results[project_key][f"{db_info['db_name']} ({db_info['db_type']})"] = db_payload

        return results

    def _find_roles_for_object_merged(
        self, object_name, databases, right_name, rls, max_results, resolve_fn,
    ):
        layer_payloads = []
        target = None
        has_polnye_prava = False
        project_key = None

        for db_info in databases:
            conn = self._get_connection(db_info['db_path'])
            cursor = conn.cursor()
            meta = read_index_metadata(cursor)
            project_key = db_info['project_name']

            resolved = resolve_fn(cursor, object_name)
            if resolved['status'] != 'found':
                continue

            row = resolved['row']
            if target is None:
                target = {'type': row['object_type'], 'name': row['name']}

            parent_qname = f"{row['object_type']}.{row['name']}"
            rows = _query_roles_for_object_rows(cursor, parent_qname, right_name, rls)

            if cursor.execute(
                "SELECT 1 FROM metadata_objects WHERE object_type='Role' AND name='ПолныеПрава' LIMIT 1"
            ).fetchone():
                has_polnye_prava = True

            layer_payloads.append({
                'db_type': db_info.get('db_type'),
                'db_name': db_info.get('db_name'),
                'extension_purpose': meta.get('extension_purpose') or '',
                'source_db_name': meta.get('source_db_name') or db_info.get('db_name'),
                'rows': rows,
            })

        if target is None:
            return {project_key or '': {'error': 'not_found', 'object_name': object_name}}

        merged = {}
        for layer in sort_layers_for_merge(layer_payloads):
            purpose = layer.get('extension_purpose') or None
            if layer.get('db_type') == 'base':
                purpose = None
            for r in layer.get('rows') or []:
                key = (r['role_name'], r['right_name'])
                merged[key] = {
                    'role_qualified_name': f"Role.{r['role_name']}",
                    'role_name': r['role_name'],
                    'uuid': r['uuid'],
                    'right_name': r['right_name'],
                    'db_name': layer['db_name'],
                    'extension_purpose': purpose,
                }

        all_roles = list(merged.values())
        all_roles.sort(key=lambda item: (item['role_name'], item['right_name']))

        payload = {
            'merge': True,
            'target': target,
            'roles': all_roles[:max_results],
            'total_count': len(all_roles),
            'is_truncated': len(all_roles) > max_results,
        }
        if has_polnye_prava:
            payload['admin_roles_note'] = (
                'Role.ПолныеПрава grants broad access by policy; not enumerated per object.'
            )

        return {project_key: payload}
