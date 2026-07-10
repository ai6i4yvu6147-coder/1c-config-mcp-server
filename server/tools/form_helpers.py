"""Shared helpers for form MCP tools (EAV, tree, overview)."""

from __future__ import annotations

from shared.form_eav import eav_rows_for_display, get_eav_value, load_entity_eav
from shared.form_overview_profiles import (
    attribute_overview_hints,
    is_column_container,
    is_dynamic_list,
    is_value_table,
    overview_paths_for_item,
)
from shared.metadata_type_resolver import format_types_for_text

from .formatting import _load_resolved_types_map, _resolve_command_source


def _eav_display_props(eav_rows, property_paths):
    """Overview property dict from EAV rows."""
    return eav_rows_for_display(eav_rows, property_paths)


def _build_item_tree(rows, eav_by_item_id):
    """Build ordered item list with depth; mark hidden column children."""
    items_by_id = {}
    for row in rows:
        items_by_id[row['id']] = {
            'id': row['id'],
            'parent_id': row['parent_id'],
            'name': row['name'],
            'type': row['item_type'],
            'eav': eav_by_item_id.get(row['id'], []),
            'children': [],
        }
    for item in items_by_id.values():
        pid = item['parent_id']
        if pid is not None and pid in items_by_id:
            items_by_id[pid]['children'].append(item)

    def has_column_container_ancestor(item_id):
        current = items_by_id.get(item_id)
        while current and current['parent_id'] is not None:
            parent = items_by_id.get(current['parent_id'])
            if parent and is_column_container(parent['type']):
                return True
            current = parent
        return False

    roots = sorted([i for i in items_by_id.values() if i['parent_id'] is None], key=lambda x: x['id'])
    ordered = []

    def walk(node, depth):
        if has_column_container_ancestor(node['id']):
            return
        paths = overview_paths_for_item(node['type'])
        props = _eav_display_props(node['eav'], paths)
        cmd_name = props.get('CommandName')
        out = {
            'name': node['name'],
            'type': node['type'],
            'depth': depth,
            'overview_properties': props,
            'command_name': cmd_name,
            'command_source': _resolve_command_source(cmd_name),
            'child_count': len(node['children']) if is_column_container(node['type']) else 0,
        }
        ordered.append(out)
        for ch in sorted(node['children'], key=lambda x: x['id']):
            walk(ch, depth + 1)

    for r in roots:
        walk(r, 0)
    return ordered


def _format_overview_props(props, attribute_names=None):
    """Format overview properties for text output."""
    parts = []
    attribute_names = attribute_names or set()
    for key, val in props.items():
        if key == 'CommandName':
            continue
        if key == 'DataPath' and val in attribute_names:
            parts.append(f'{key}={val} (→ attribute {val})')
        else:
            parts.append(f'{key}={val}')
    return ' '.join(parts)


def _attribute_hints(attr, types, eav_rows, column_count):
    return attribute_overview_hints(types, eav_rows, column_count)


def _resolve_form(cursor, object_name, form_name):
    cursor.execute('''
        SELECT f.id, f.uuid, f.form_kind, f.properties_json,
               o.object_belonging, o.extended_configuration_object
        FROM forms f
        JOIN metadata_objects o ON f.object_id = o.id
        WHERE o.name = ? AND f.form_name = ?
        LIMIT 1
    ''', (object_name, form_name))
    return cursor.fetchone()
