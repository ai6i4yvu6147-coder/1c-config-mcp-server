def _resolve_config_object(cursor, object_name):
    """
    Resolve ConfigObject by exact then partial name/synonym.
    Returns dict with status: found | not_found | ambiguous.
    """
    cursor.execute('''
        SELECT id, name, object_type, uuid, synonym, comment, object_belonging, extended_configuration_object
        FROM metadata_objects
        WHERE (name = ? OR synonym = ?) AND object_kind = 'ConfigObject'
        LIMIT 1
    ''', (object_name, object_name))
    obj_row = cursor.fetchone()
    if obj_row:
        return {'status': 'found', 'row': obj_row}

    cursor.execute('''
        SELECT id, name, object_type, uuid, synonym, comment, object_belonging, extended_configuration_object
        FROM metadata_objects
        WHERE (name LIKE ? OR IFNULL(synonym, '') LIKE ?) AND object_kind = 'ConfigObject'
        ORDER BY name
    ''', (f'%{object_name}%', f'%{object_name}%'))
    candidates = cursor.fetchall()
    if not candidates:
        return {'status': 'not_found'}
    if len(candidates) > 1:
        return {
            'status': 'ambiguous',
            'requested_name': object_name,
            'candidates': [
                {'name': r['name'], 'type': r['object_type'], 'synonym': r['synonym'] or ''}
                for r in candidates
            ],
        }
    return {'status': 'found', 'row': candidates[0]}


_REFERENCING_SLOTS_SQL = '''
    SELECT mts.ordinal,
           mo_src.object_type AS src_type,
           mo_src.name AS src_name,
           mo_src.synonym AS src_synonym,
           'attribute' AS via,
           a.name AS field_name,
           a.section AS attribute_section,
           NULL AS tabular_section_name,
           NULL AS form_name,
           NULL AS form_attribute_name
    FROM metadata_type_slots mts
    JOIN metadata_objects mo_src ON mts.src_object_id = mo_src.id
    JOIN attributes a ON mts.source_row_id = a.id
    WHERE mts.object_id = ? AND mts.source_table = 'attributes'

    UNION ALL

    SELECT mts.ordinal,
           mo_src.object_type,
           mo_src.name,
           mo_src.synonym,
           'tabular_section_column',
           tsc.column_name,
           NULL,
           ts.name,
           NULL,
           NULL
    FROM metadata_type_slots mts
    JOIN metadata_objects mo_src ON mts.src_object_id = mo_src.id
    JOIN tabular_section_columns tsc ON mts.source_row_id = tsc.id
    JOIN tabular_sections ts ON tsc.tabular_section_id = ts.id
    WHERE mts.object_id = ? AND mts.source_table = 'tabular_section_columns'

    UNION ALL

    SELECT mts.ordinal,
           mo_src.object_type,
           mo_src.name,
           mo_src.synonym,
           'form_attribute',
           fa.name,
           NULL,
           NULL,
           f.form_name,
           NULL
    FROM metadata_type_slots mts
    JOIN metadata_objects mo_src ON mts.src_object_id = mo_src.id
    JOIN form_attributes fa ON mts.source_row_id = fa.id
    JOIN forms f ON fa.form_id = f.id
    WHERE mts.object_id = ? AND mts.source_table = 'form_attributes'

    UNION ALL

    SELECT mts.ordinal,
           mo_src.object_type,
           mo_src.name,
           mo_src.synonym,
           'form_attribute_column',
           fac.name,
           NULL,
           NULL,
           f.form_name,
           fa.name
    FROM metadata_type_slots mts
    JOIN metadata_objects mo_src ON mts.src_object_id = mo_src.id
    JOIN form_attribute_columns fac ON mts.source_row_id = fac.id
    JOIN form_attributes fa ON fac.form_attribute_id = fa.id
    JOIN forms f ON fa.form_id = f.id
    WHERE mts.object_id = ? AND mts.source_table = 'form_attribute_columns'
'''


def _fetch_all_referencing_slots(cursor, target_object_id):
    """Return list of referencer dicts from metadata_type_slots (no limit)."""
    params = (target_object_id, target_object_id, target_object_id, target_object_id)
    cursor.execute(
        f'''
        SELECT * FROM ({_REFERENCING_SLOTS_SQL})
        ORDER BY src_type, src_name, via, field_name, ordinal
        ''',
        params,
    )
    referencers = []
    for row in cursor.fetchall():
        referencers.append({
            'src_object': {
                'type': row['src_type'],
                'name': row['src_name'],
                'synonym': row['src_synonym'] or '',
            },
            'via': row['via'],
            'field_name': row['field_name'],
            'attribute_section': row['attribute_section'],
            'tabular_section_name': row['tabular_section_name'],
            'form_name': row['form_name'],
            'form_attribute_name': row['form_attribute_name'],
            'ordinal': row['ordinal'],
        })
    return referencers


def _fetch_referencing_relations(cursor, target_object_id, relation_kinds=None):
    """Return list of referencer dicts from metadata_relations (no limit)."""
    sql = '''
        SELECT mr.relation_kind,
               mo_src.object_type AS src_type,
               mo_src.name AS src_name,
               mo_src.synonym AS src_synonym,
               mr.source_name,
               mr.source_detail
        FROM metadata_relations mr
        JOIN metadata_objects mo_src ON mr.src_object_id = mo_src.id
        WHERE mr.dst_object_id = ?
    '''
    params = [target_object_id]
    if relation_kinds:
        placeholders = ','.join('?' * len(relation_kinds))
        sql += f' AND mr.relation_kind IN ({placeholders})'
        params.extend(relation_kinds)
    sql += ' ORDER BY src_type, src_name, relation_kind, source_name'
    cursor.execute(sql, params)
    referencers = []
    for row in cursor.fetchall():
        referencers.append({
            'src_object': {
                'type': row['src_type'],
                'name': row['src_name'],
                'synonym': row['src_synonym'] or '',
            },
            'via': row['relation_kind'],
            'source_name': row['source_name'],
            'source_detail': row['source_detail'],
        })
    return referencers


def _referencer_sort_key(ref):
    src = ref['src_object']
    via = ref.get('via', '')
    detail = (
        ref.get('field_name')
        or ref.get('source_name')
        or ''
    )
    return (src['type'], src['name'], via, detail, ref.get('ordinal', 0))


def _fetch_referencing_combined(cursor, target_object_id, max_results, relation_kinds=None):
    """UNION slots + relations; total_count before limit, sorted combined list."""
    slots = _fetch_all_referencing_slots(cursor, target_object_id)
    relations = _fetch_referencing_relations(cursor, target_object_id, relation_kinds)
    combined = slots + relations
    combined.sort(key=_referencer_sort_key)
    total_count = len(combined)
    return total_count, combined[:max_results]


def _fetch_referencing_slots(cursor, target_object_id, max_results):
    """Return (total_count, list of referencer dicts) for slots pointing at target_object_id."""
    slots = _fetch_all_referencing_slots(cursor, target_object_id)
    total_count = len(slots)
    return total_count, slots[:max_results]


class RelationsMixin:
    """Reverse dependency lookup (find_referencing_objects) over type slots + metadata_relations."""

    def find_referencing_objects(
        self, object_name, project_filter=None, extension_filter=None,
        max_results=100, relation_kinds=None,
    ):
        """
        Обратный поиск: кто ссылается на объект через metadata_type_slots
        и metadata_relations (подсистемы и др.).

        Args:
            object_name: Имя или синоним целевого объекта (частичное совпадение)
            project_filter: Фильтр по проекту (обязательно)
            extension_filter: Фильтр по расширению/базе (опционально)
            max_results: Максимум записей на базу (по умолчанию 100)
            relation_kinds: Фильтр relation_kind в metadata_relations (опционально)

        Returns:
            Dict сгруппированный по проектам/базам
        """
        self._require_project_filter(project_filter)
        databases = self._get_active_databases(project_filter)
        self._require_project_exists(project_filter, databases)
        if extension_filter:
            databases = [db for db in databases if db['db_name'].lower() == extension_filter.lower()]

        if max_results is None or max_results < 1:
            max_results = 100

        results = {}

        for db_info in databases:
            conn = self._get_connection(db_info['db_path'])
            cursor = conn.cursor()

            resolved = _resolve_config_object(cursor, object_name)
            project_key = db_info['project_name']
            db_key = f"{db_info['db_name']} ({db_info['db_type']})"

            if resolved['status'] == 'not_found':
                continue
            if resolved['status'] == 'ambiguous':
                if project_key not in results:
                    results[project_key] = {}
                results[project_key][db_key] = {
                    'ambiguous': True,
                    'requested_name': resolved['requested_name'],
                    'candidates': resolved['candidates'],
                }
                continue

            obj_row = resolved['row']
            total_count, referencers = _fetch_referencing_combined(
                cursor, obj_row['id'], max_results, relation_kinds,
            )

            if project_key not in results:
                results[project_key] = {}
            results[project_key][db_key] = {
                'target': {
                    'name': obj_row['name'],
                    'type': obj_row['object_type'],
                    'synonym': obj_row['synonym'] or '',
                },
                'referencers': referencers,
                'total_count': total_count,
                'returned_count': len(referencers),
                'is_truncated': total_count > len(referencers),
            }

        return results
