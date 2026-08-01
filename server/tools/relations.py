from .formatting import _table_exists


def _candidate_list(rows):
    return [
        {'name': r['name'], 'type': r['object_type'], 'synonym': r['synonym'] or ''}
        for r in rows
    ]


def _resolve_config_object(cursor, object_name, object_type=None):
    """
    Resolve ConfigObject by exact then partial name/synonym.
    Returns dict with status: found | not_found | ambiguous.

    object_type сужает поиск до одного вида метаданных (`Document`, `CommonModule`, …)
    и существует именно ради разрешения неоднозначности: без него у агента, получившего
    `ambiguous` на точном имени, нет способа выбрать кандидата — имя у всех одно и то же.

    Точное совпадение тоже бывает неоднозначным: в ЕРП «Планета» 1 181 имя (5.3%
    каталога) принадлежит двум и более видам объектов — `Взаиморасчеты` — это разом
    Document, CommonModule, AccumulationRegister, Report и Role. Раньше здесь стоял
    `LIMIT 1` без `ORDER BY`, поэтому брался объект, который SQLite отдал первым:
    выбор произволен, мог меняться между пересборками, и ошибки при этом не было —
    ответ выглядел валидным. Ветка частичного совпадения неоднозначность отдавала
    корректно; теперь обе ветки живут по одному контракту.
    """
    type_clause = ' AND object_type = ?' if object_type else ''
    type_params = (object_type,) if object_type else ()

    cursor.execute(f'''
        SELECT id, name, object_type, uuid, synonym, comment, object_belonging, extended_configuration_object
        FROM metadata_objects
        WHERE (name = ? OR synonym = ?) AND object_kind = 'ConfigObject'{type_clause}
        ORDER BY object_type, name
    ''', (object_name, object_name, *type_params))
    exact = cursor.fetchall()
    if exact:
        # Совпадение по имени сильнее совпадения по синониму: если имя назвали точно,
        # объект с таким синонимом не делает запрос неоднозначным. Неоднозначность
        # объявляется только среди равных по силе кандидатов.
        by_name = [r for r in exact if r['name'] == object_name]
        tier = by_name or exact
        if len(tier) == 1:
            return {'status': 'found', 'row': tier[0]}
        return {
            'status': 'ambiguous',
            'requested_name': object_name,
            'match_kind': 'exact',
            'candidates': _candidate_list(tier),
        }

    cursor.execute(f'''
        SELECT id, name, object_type, uuid, synonym, comment, object_belonging, extended_configuration_object
        FROM metadata_objects
        WHERE (name LIKE ? OR IFNULL(synonym, '') LIKE ?) AND object_kind = 'ConfigObject'{type_clause}
        ORDER BY name
    ''', (f'%{object_name}%', f'%{object_name}%', *type_params))
    candidates = cursor.fetchall()
    if not candidates:
        return {'status': 'not_found'}
    if len(candidates) > 1:
        return {
            'status': 'ambiguous',
            'requested_name': object_name,
            'match_kind': 'partial',
            'candidates': _candidate_list(candidates),
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


def _fetch_referencing_role_grants(cursor, parent_object_qname):
    """Return referencer dicts from role_grants (phase 4).

    Единственная законная причина промолчать — база собрана до фазы 4 и таблицы
    `role_grants` в ней нет. Раньше здесь стоял `except Exception: return []`, который
    глушил заодно и любую настоящую ошибку запроса, превращая её в «ссылок нет».
    """
    if not _table_exists(cursor, 'role_grants'):
        return []
    cursor.execute('''
        SELECT mo.object_type AS src_type,
               mo.name AS src_name,
               mo.synonym AS src_synonym,
               rg.right_name,
               rg.granted,
               rg.source_db_name
        FROM role_grants rg
        JOIN metadata_objects mo ON rg.role_object_id = mo.id
        WHERE rg.parent_object_qname = ? AND rg.granted = 1
        ORDER BY src_type, src_name, rg.right_name
    ''', (parent_object_qname,))

    referencers = []
    for row in cursor.fetchall():
        referencers.append({
            'src_object': {
                'type': row['src_type'],
                'name': row['src_name'],
                'synonym': row['src_synonym'] or '',
            },
            'via': 'role_grant',
            'right_name': row['right_name'],
            'granted': bool(row['granted']),
            'source_db_name': row['source_db_name'],
            'source_name': parent_object_qname,
            'source_detail': row['right_name'],
        })
    return referencers


_SLOT_VIAS = frozenset({
    'attribute', 'tabular_section_column', 'form_attribute', 'form_attribute_column',
})


def _fetch_referencing_combined(cursor, target_object_id, parent_object_qname, max_results, relation_kinds=None):
    """UNION slots + relations + role_grants; total_count before limit."""
    if relation_kinds:
        include_slots = any(k in _SLOT_VIAS for k in relation_kinds)
        rel_kinds = [k for k in relation_kinds if k != 'role_grant' and k not in _SLOT_VIAS]
        include_relations = bool(rel_kinds)
        include_role_grants = 'role_grant' in relation_kinds
    else:
        include_slots = True
        include_relations = True
        include_role_grants = True
        rel_kinds = None

    slots = _fetch_all_referencing_slots(cursor, target_object_id) if include_slots else []
    relations = []
    if include_relations:
        kinds_filter = rel_kinds if relation_kinds else None
        relations = _fetch_referencing_relations(cursor, target_object_id, kinds_filter)

    role_grants = []
    if include_role_grants and parent_object_qname:
        role_grants = _fetch_referencing_role_grants(cursor, parent_object_qname)

    combined = slots + relations + role_grants
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
        max_results=100, relation_kinds=None, object_type=None,
    ):
        """
        Обратный поиск: кто ссылается на объект через metadata_type_slots,
        metadata_relations (подсистемы и др.) и role_grants (роли).

        Args:
            object_name: Имя или синоним целевого объекта (частичное совпадение)
            project_filter: Фильтр по проекту (обязательно)
            extension_filter: Фильтр по расширению/базе (опционально)
            max_results: Максимум записей на базу (по умолчанию 100)
            relation_kinds: Фильтр видов связей (subsystem_member, role_grant, …)
            object_type: Вид метаданных цели — для разрешения неоднозначности имени

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

            resolved = _resolve_config_object(cursor, object_name, object_type)
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
                    'match_kind': resolved.get('match_kind'),
                    'candidates': resolved['candidates'],
                }
                continue

            obj_row = resolved['row']
            parent_object_qname = f"{obj_row['object_type']}.{obj_row['name']}"
            total_count, referencers = _fetch_referencing_combined(
                cursor, obj_row['id'], parent_object_qname, max_results, relation_kinds,
            )
            for ref in referencers:
                if ref.get('via') == 'role_grant':
                    ref['db_name'] = db_info['db_name']
                    ref.pop('source_db_name', None)

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
