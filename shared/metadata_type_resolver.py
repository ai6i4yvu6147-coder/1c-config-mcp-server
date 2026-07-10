"""Resolve parsed type slots to metadata_objects ids and insert metadata_type_slots."""

import sqlite3

REF_SUFFIX_TO_OBJECT_TYPE = {
    'CatalogRef': 'Catalog',
    'DocumentRef': 'Document',
    'EnumRef': 'Enum',
    'InformationRegisterRef': 'InformationRegister',
    'AccumulationRegisterRef': 'AccumulationRegister',
    'AccountingRegisterRef': 'AccountingRegister',
    'CalculationRegisterRef': 'CalculationRegister',
    'ChartOfAccountsRef': 'ChartOfAccounts',
    'ChartOfCharacteristicTypesRef': 'ChartOfCharacteristicTypes',
    'ExchangePlanRef': 'ExchangePlan',
    'BusinessProcessRef': 'BusinessProcess',
    'TaskRef': 'Task',
    'ReportRef': 'Report',
    'DataProcessorRef': 'DataProcessor',
    'ChartOfCalculationTypesRef': 'ChartOfCalculationTypes',
}

XS_TYPE_TO_BASE = {
    'xs:boolean': 'Boolean',
    'xs:string': 'String',
    'xs:dateTime': 'Date',
    'xs:date': 'Date',
    'xs:decimal': 'Number',
    'xs:long': 'Number',
    'xs:int': 'Number',
    'xs:double': 'Number',
    'xs:float': 'Number',
}

CFG_FORM_WRAPPER_TO_BASE = {
    'DynamicList': 'DynamicList',
}

# Form.xml object wrappers → metadata object_type for FK resolve
FORM_OBJECT_SUFFIX_TO_TYPE = {
    'DocumentObject': 'Document',
    'CatalogObject': 'Catalog',
    'EnumObject': 'Enum',
}


def parse_cfg_type_string(type_str):
    """Parse cfg:/xs:/v8: type string into slot dict fields."""
    type_str = (type_str or '').strip()
    if not type_str:
        return {'kind': 'unknown', 'raw': type_str}

    if type_str.startswith('cfg:'):
        body = type_str[4:]
        if '.' in body:
            suffix, name = body.split('.', 1)
            if suffix in REF_SUFFIX_TO_OBJECT_TYPE:
                return {
                    'kind': 'object_ref',
                    'raw': type_str,
                    'ref_suffix': suffix,
                    'ref_name': name,
                }
            if suffix in FORM_OBJECT_SUFFIX_TO_TYPE:
                return {
                    'kind': 'object_ref',
                    'raw': type_str,
                    'ref_suffix': suffix,
                    'ref_name': name,
                    'object_type_hint': FORM_OBJECT_SUFFIX_TO_TYPE[suffix],
                }
            wrapper_base = CFG_FORM_WRAPPER_TO_BASE.get(suffix)
            if wrapper_base:
                return {'kind': 'primitive', 'raw': type_str, 'base_type': wrapper_base}
            if suffix == 'DefinedType':
                return {'kind': 'unknown', 'raw': type_str, 'ref_suffix': suffix, 'ref_name': name}
            return {'kind': 'unknown', 'raw': type_str, 'ref_suffix': suffix, 'ref_name': name}
        wrapper_base = CFG_FORM_WRAPPER_TO_BASE.get(body)
        if wrapper_base:
            return {'kind': 'primitive', 'raw': type_str, 'base_type': wrapper_base}
        # cfg:DocumentRef without object name, AnyIBRef, etc.
        return {'kind': 'unknown', 'raw': type_str, 'ref_suffix': body, 'ref_name': None}

    if type_str.startswith('xs:'):
        base = XS_TYPE_TO_BASE.get(type_str)
        if base:
            return {'kind': 'primitive', 'raw': type_str, 'xs_type': type_str, 'base_type': base}
        return {'kind': 'unknown', 'raw': type_str, 'xs_type': type_str}

    # v8: and any other platform namespace alias (dcsset:, mxl:, chart:, adcsp:, …). A bare
    # "prefix:Name" (no dot — not an Object.Name reference) is a concrete platform built-in
    # type (ValueListType, SettingsComposer, SpreadsheetDocument, Color, Font, …) — surface
    # it by name instead of silently dropping it as unresolved (P-3).
    if ':' in type_str:
        _, body = type_str.split(':', 1)
        if body and '.' not in body:
            return {'kind': 'primitive', 'raw': type_str, 'base_type': body}

    return {'kind': 'unknown', 'raw': type_str}


def normalize_descriptor_storage(base_type, q1, q2, q3):
    """Канонический ключ TypeDescriptor для кэша, SELECT и INSERT (без NULL в квалификаторах)."""
    base_type = (base_type or '').strip()

    def norm(value):
        if value is None:
            return ''
        return str(value)

    q1, q2, q3 = norm(q1), norm(q2), norm(q3)
    if base_type == 'Number' and q2 == '':
        q2 = '0'
    return base_type, q1, q2, q3


def format_type_descriptor_name(base_type, q1, q2, q3):
    """Human-readable synthetic name for TypeDescriptor row."""
    base_type, q1, q2, q3 = normalize_descriptor_storage(base_type, q1, q2, q3)
    if base_type == 'Number':
        digits = q1 if q1 else ''
        frac = q2 if q2 else '0'
        return f'Number({digits},{frac})'
    if base_type == 'String':
        if q1:
            return f'String({q1})'
        return 'String'
    if base_type == 'Date':
        if q1:
            return f'Date({q1})'
        return 'Date'
    if base_type == 'Boolean':
        return 'Boolean'
    return base_type or 'Unknown'


def qualifiers_to_storage(base_type, qualifiers):
    """Map qualifier dict to (q1, q2, q3) for metadata_objects."""
    if not qualifiers:
        return None, None, None
    if base_type == 'Number':
        return (
            qualifiers.get('digits'),
            qualifiers.get('fraction'),
            qualifiers.get('allowed_sign'),
        )
    if base_type == 'String':
        return (
            qualifiers.get('length'),
            qualifiers.get('allowed_length'),
            None,
        )
    if base_type == 'Date':
        return (qualifiers.get('date_fractions'), None, None)
    return None, None, None


def format_primitive_qualifiers(base_type, q1, q2, q3):
    """Build qualifiers dict for MCP response."""
    def present(value):
        return value is not None and value != ''

    if base_type == 'Number':
        out = {}
        if present(q1):
            out['digits'] = q1
        if present(q2):
            out['fraction'] = q2
        if present(q3):
            out['allowed_sign'] = q3
        return out
    if base_type == 'String':
        out = {}
        if present(q1):
            out['length'] = q1
        if present(q2):
            out['allowed_length'] = q2
        return out
    if base_type == 'Date' and present(q1):
        return {'date_fractions': q1}
    return {}


def slot_to_mcp_type(slot_row):
    """Convert joined metadata_type_slots + metadata_objects row to MCP types element."""
    if slot_row['object_kind'] == 'TypeDescriptor':
        quals = format_primitive_qualifiers(
            slot_row['base_type'],
            slot_row['qualifier_1'],
            slot_row['qualifier_2'],
            slot_row['qualifier_3'],
        )
        item = {'kind': 'primitive', 'base_type': slot_row['base_type']}
        if quals:
            item['qualifiers'] = quals
        return item
    return {
        'kind': 'object',
        'object_type': slot_row['object_type'],
        'name': slot_row['name'],
        'synonym': slot_row['synonym'] or '',
    }


def format_types_for_text(types):
    """Compact text for MCP text responses.

    P-3: a real 1C attribute always has at least one type; an empty list here means
    the parser/resolver couldn't map the declared type (e.g. cfg:DefinedType.X, or a
    genuinely empty <Type/>), not that the attribute is untyped. Say so explicitly
    instead of leaving a blank the agent might misread as "no type".
    """
    if not types:
        return '(тип не определён)'
    parts = []
    for t in types:
        if t.get('kind') == 'object':
            parts.append(f"{t.get('object_type')}.{t.get('name')}")
        elif t.get('kind') == 'primitive':
            bt = t.get('base_type', '')
            quals = t.get('qualifiers') or {}
            if bt == 'Number' and 'digits' in quals:
                frac = quals.get('fraction', 0)
                parts.append(f"Number({quals['digits']},{frac})")
            elif bt == 'String' and 'length' in quals:
                parts.append(f"String({quals['length']})")
            else:
                parts.append(bt)
        else:
            parts.append(str(t))
    return ' | '.join(parts)


class MetadataTypeResolver:
    """Resolves parser type slots during DB build."""

    def __init__(self):
        self._descriptor_cache = {}

    def get_or_create_type_descriptor(self, cursor, base_type, q1, q2, q3):
        base_type, q1, q2, q3 = normalize_descriptor_storage(base_type, q1, q2, q3)
        key = (base_type, q1, q2, q3)
        if key in self._descriptor_cache:
            return self._descriptor_cache[key]

        cursor.execute('''
            SELECT id FROM metadata_objects
            WHERE object_kind = 'TypeDescriptor'
              AND base_type = ?
              AND qualifier_1 = ?
              AND qualifier_2 = ?
              AND qualifier_3 = ?
        ''', (base_type, q1, q2, q3))
        row = cursor.fetchone()
        if row:
            obj_id = row[0]
        else:
            name = format_type_descriptor_name(base_type, q1, q2, q3)
            try:
                cursor.execute('''
                    INSERT INTO metadata_objects (
                        uuid, object_type, name, synonym, comment,
                        object_kind, is_primitive, base_type,
                        qualifier_1, qualifier_2, qualifier_3
                    )
                    VALUES ('', 'TypeDescriptor', ?, '', NULL,
                            'TypeDescriptor', 1, ?, ?, ?, ?)
                ''', (name, base_type, q1, q2, q3))
                obj_id = cursor.lastrowid
            except sqlite3.IntegrityError:
                cursor.execute('''
                    SELECT id FROM metadata_objects
                    WHERE object_kind = 'TypeDescriptor'
                      AND base_type = ?
                      AND qualifier_1 = ?
                      AND qualifier_2 = ?
                      AND qualifier_3 = ?
                ''', (base_type, q1, q2, q3))
                row = cursor.fetchone()
                if row is None:
                    raise
                obj_id = row[0]

        self._descriptor_cache[key] = obj_id
        return obj_id

    def resolve_object_ref(self, ref_suffix, ref_name, type_name_to_id):
        if not ref_name:
            return None
        object_type = REF_SUFFIX_TO_OBJECT_TYPE.get(ref_suffix)
        if not object_type:
            return None
        return type_name_to_id.get((object_type, ref_name))

    def resolve_slot_object_id(self, cursor, slot, type_name_to_id):
        kind = slot.get('kind')
        if kind == 'object_ref':
            hint = slot.get('object_type_hint')
            ref_name = slot.get('ref_name')
            if hint and ref_name:
                resolved = type_name_to_id.get((hint, ref_name))
                if resolved is not None:
                    return resolved
            return self.resolve_object_ref(
                slot.get('ref_suffix'),
                ref_name,
                type_name_to_id,
            )
        if kind == 'primitive':
            base_type = slot.get('base_type')
            q1, q2, q3 = qualifiers_to_storage(base_type, slot.get('qualifiers'))
            return self.get_or_create_type_descriptor(cursor, base_type, q1, q2, q3)
        return None

    def insert_slots(self, cursor, pending_list, type_name_to_id):
        """Insert metadata_type_slots from pending entries collected during object import."""
        rows = []
        for entry in pending_list:
            source_table = entry['source_table']
            source_row_id = entry['source_row_id']
            src_object_id = entry['src_object_id']
            for ordinal, slot in enumerate(entry.get('type_slots') or []):
                object_id = self.resolve_slot_object_id(cursor, slot, type_name_to_id)
                if object_id is None:
                    continue
                rows.append((
                    source_table,
                    source_row_id,
                    src_object_id,
                    object_id,
                    ordinal,
                ))
        if rows:
            cursor.executemany('''
                INSERT INTO metadata_type_slots (
                    source_table, source_row_id, src_object_id, object_id, ordinal
                )
                VALUES (?, ?, ?, ?, ?)
            ''', rows)
