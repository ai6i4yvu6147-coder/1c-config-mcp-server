"""Helpers for reading form_entity_properties (EAV) in indexer and MCP."""

from __future__ import annotations

from collections import defaultdict
from typing import Any


def group_eav_rows(rows) -> dict[int, list[dict[str, Any]]]:
    """Group EAV rows by entity_id."""
    by_id: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_id[row['entity_id']].append(dict(row))
    return by_id


def eav_prop_map(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """Map property_path -> list of rows (supports repeated paths via ordinal)."""
    result: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        result[row['property_path']].append(row)
    for path in result:
        result[path].sort(key=lambda r: r.get('ordinal', 0))
    return result


def get_eav_value(rows: list[dict[str, Any]], property_path: str, ordinal: int = 0) -> str | None:
    """First value at property_path and ordinal."""
    for row in rows:
        if row['property_path'] == property_path and row.get('ordinal', 0) == ordinal:
            return row.get('value_text')
    return None


def get_eav_values(rows: list[dict[str, Any]], property_path: str) -> list[str]:
    """All values at property_path sorted by ordinal."""
    matches = [r for r in rows if r['property_path'] == property_path]
    matches.sort(key=lambda r: r.get('ordinal', 0))
    return [r['value_text'] for r in matches if r.get('value_text') is not None]


def load_entity_eav(cursor, entity_kind: str, entity_ids: list[int]) -> dict[int, list[dict[str, Any]]]:
    """Batch-load EAV rows for entity ids."""
    if not entity_ids:
        return {}
    placeholders = ','.join('?' * len(entity_ids))
    cursor.execute(f'''
        SELECT entity_id, property_path, property_name, ordinal, value_text, value_type
        FROM form_entity_properties
        WHERE entity_kind = ? AND entity_id IN ({placeholders})
        ORDER BY entity_id, property_path, ordinal
    ''', [entity_kind, *entity_ids])
    return group_eav_rows(cursor.fetchall())


def count_field_siblings(rows: list[dict[str, Any]]) -> int:
    """Count DynamicList Settings.Field ordinals from EAV (max ordinal at Field.dataPath + 1)."""
    ordinals = [r.get('ordinal', 0) for r in rows if r['property_path'] in ('Settings.Field.dataPath', 'Settings.Field.field')]
    return max(ordinals) + 1 if ordinals else 0


def query_text_length(rows: list[dict[str, Any]]) -> int | None:
    """Char count for QueryText from attribute EAV."""
    for path in ('Settings.QueryText', 'QueryText'):
        val = get_eav_value(rows, path)
        if val:
            return len(val)
    return None


def field_index_from_eav(rows: list[dict[str, Any]]) -> list[dict[str, str]]:
    """Build DynamicList field index from parent attribute EAV."""
    by_ordinal: dict[int, dict[str, str]] = defaultdict(dict)
    for row in rows:
        path = row['property_path']
        if not path.startswith('Settings.Field.'):
            continue
        ord = row.get('ordinal', 0)
        leaf = path.rsplit('.', 1)[-1]
        if row.get('value_text'):
            by_ordinal[ord][leaf] = row['value_text']
    fields = []
    for ord in sorted(by_ordinal.keys()):
        entry = by_ordinal[ord]
        key = entry.get('dataPath') or entry.get('field') or f'field_{ord}'
        fields.append({
            'ordinal': ord,
            'dataPath': entry.get('dataPath', ''),
            'field': entry.get('field', ''),
            'key': key,
        })
    return fields


def filter_field_eav(rows: list[dict[str, Any]], column_name: str) -> list[dict[str, Any]]:
    """Slice EAV rows for one DynamicList field by dataPath or field text."""
    fields = field_index_from_eav(rows)
    target_ord = None
    for f in fields:
        if f['key'] == column_name or f.get('dataPath') == column_name or f.get('field') == column_name:
            target_ord = f['ordinal']
            break
    if target_ord is None:
        return []
    prefix = 'Settings.Field.'
    return [r for r in rows if r['property_path'].startswith(prefix) and r.get('ordinal', 0) == target_ord]


def eav_rows_for_display(rows: list[dict[str, Any]], property_paths: list[str]) -> dict[str, str]:
    """Pick first ordinal value per property_path for overview."""
    result = {}
    for path in property_paths:
        val = get_eav_value(rows, path)
        if val is not None:
            result[path] = val
    return result
