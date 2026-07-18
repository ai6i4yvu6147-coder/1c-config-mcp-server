"""get_dcs_schema: the DCS (DataCompositionSchema) document getter (Срез 2).

Symmetry with forms: get_form_structure is to a form what get_dcs_schema is to a schema --
one extractable document per schema, backed by the dcs_schema table (blob + shape hints),
built via the library read side (onec_metadata_schema.dcs). Cross-object search over the
dataset query text stays in search_code (Срез 1, module_type='DcsQuery').
See docs/dcs-schema-indexing.md.
"""

import json

from .relations import _resolve_config_object

_SHAPE_KEYS = (
    'has_query', 'dataset_count', 'field_count', 'parameter_count',
    'calculated_count', 'total_count', 'has_grouping', 'filter_item_count',
)


def _table_exists(cursor, name):
    row = cursor.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name = ?", (name,)
    ).fetchone()
    return row is not None


def _row_summary(row):
    summary = {'template_name': row['template_name']}
    for key in _SHAPE_KEYS:
        value = row[key]
        summary[key] = bool(value) if key in ('has_query', 'has_grouping') else value
    return summary


class DcsMixin:
    """DataCompositionSchema retrieval (read side)."""

    def get_dcs_schema(self, object_name, project_filter=None, template=None,
                       extension_filter=None):
        """Semantic DCS schema(s) owned by an object.

        Args:
            object_name: имя объекта-владельца (частичное совпадение).
            project_filter: проект (обязателен).
            template: имя шаблона (частичное). Без него — обзор всех схем объекта
                (shape-hints); полный документ отдаётся, когда цель одна.
            extension_filter: точное имя базы (опционально).

        Returns:
            Dict {проект: {база: {object, type, schemas: [...]}}}. Каждая схема — shape-hints
            (has_query/dataset_count/…); полный разобранный документ (schema) прикладывается,
            когда запрошена ровно одна схема (или у объекта она единственная).
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
            if not _table_exists(cursor, 'dcs_schema'):
                continue  # DB built before Срез 2 -> nothing to serve here

            resolved = _resolve_config_object(cursor, object_name)
            if resolved['status'] == 'not_found':
                continue

            project_key = db_info['project_name']
            db_key = f"{db_info['db_name']} ({db_info['db_type']})"
            if resolved['status'] == 'ambiguous':
                results.setdefault(project_key, {})[db_key] = {
                    'ambiguous': True,
                    'requested_name': resolved['requested_name'],
                    'candidates': resolved['candidates'],
                }
                continue

            obj_row = resolved['row']
            params = [obj_row['id']]
            sql = 'SELECT * FROM dcs_schema WHERE object_id = ?'
            if template:
                sql += ' AND template_name LIKE ?'
                params.append(f'%{template}%')
            sql += ' ORDER BY template_name'
            rows = cursor.execute(sql, params).fetchall()

            schemas = [_row_summary(r) for r in rows]
            if len(rows) == 1:  # single target -> attach the full extractable document
                schemas[0]['schema'] = json.loads(rows[0]['schema_json'])

            results.setdefault(project_key, {})[db_key] = {
                'object': obj_row['name'],
                'type': obj_row['object_type'],
                'schemas': schemas,
            }
        return results
