from typing import Optional

from shared.metadata_type_resolver import slot_to_mcp_type


def _load_resolved_types_map(cursor, source_table, source_row_ids):
    """Batch-load resolved types for attribute/column rows."""
    if not source_row_ids:
        return {}
    placeholders = ','.join('?' * len(source_row_ids))
    cursor.execute(f'''
        SELECT mts.source_row_id, mts.ordinal,
               mo.object_kind, mo.object_type, mo.name, mo.synonym,
               mo.base_type, mo.qualifier_1, mo.qualifier_2, mo.qualifier_3
        FROM metadata_type_slots mts
        JOIN metadata_objects mo ON mts.object_id = mo.id
        WHERE mts.source_table = ? AND mts.source_row_id IN ({placeholders})
        ORDER BY mts.source_row_id, mts.ordinal
    ''', [source_table, *source_row_ids])
    result = {}
    for row in cursor.fetchall():
        rid = row['source_row_id']
        result.setdefault(rid, []).append(slot_to_mcp_type(row))
    return result


def _resolve_command_source(command_name: Optional[str]) -> Optional[str]:
    """По сырому CommandName из Form.xml: Form | Object | Common | None."""
    if not command_name or not str(command_name).strip():
        return None
    s = str(command_name).strip()
    if s.startswith('Form.Command.'):
        return 'Form'
    if s.startswith('CommonCommand.'):
        return 'Common'
    if '.Command.' in s:
        return 'Object'
    return None


def _format_route_point_label(name, point_type):
    """Метка точки маршрута с типом для adjacency."""
    if point_type in ('Split', 'Join'):
        return f'[{point_type}] {name}'
    return name


def _transition_branch_label(transition, condition_ports):
    """Подпись ветки перехода: title линии или Да/Нет по порту Condition."""
    title = (transition.get('title') or '').strip()
    if title:
        return title
    from_port = transition.get('from_port')
    if from_port is None or not condition_ports:
        return ''
    true_port, false_port = condition_ports
    if true_port is not None and from_port == true_port:
        return 'Да'
    if false_port is not None and from_port == false_port:
        return 'Нет'
    return ''


def format_business_process_route_text(route_points, route_transitions):
    """Текстовое представление маршрута БП: индекс по типам + adjacency list."""
    if not route_points and not route_transitions:
        return ''

    lines = []
    point_types = {}
    for point in route_points:
        pt = point.get('type') or 'Unknown'
        point_types.setdefault(pt, []).append(point)

    type_parts = []
    for pt in sorted(point_types.keys(), key=lambda t: (t != 'Start', t != 'Activity', t)):
        items = point_types[pt]
        if pt == 'Activity':
            names = []
            for p in items:
                label = p['name']
                syn = (p.get('synonym') or '').strip()
                if syn:
                    label = f'{label} («{syn}»)'
                names.append(label)
            type_parts.append(f'Activity ({len(items)}): {", ".join(names)}')
        elif len(items) == 1:
            p = items[0]
            syn = (p.get('synonym') or '').strip()
            label = f'{pt}: {p["name"]}'
            if syn and pt not in ('Start', 'Completion', 'Split', 'Join'):
                label += f' («{syn}»)'
            type_parts.append(label)
        else:
            names = ', '.join(p['name'] for p in items)
            type_parts.append(f'{pt} ({len(items)}): {names}')

    lines.append(f'  Точки маршрута ({len(route_points)}): {" | ".join(type_parts)}')
    lines.append('')

    if route_transitions:
        condition_ports = {}
        point_type_by_name = {p['name']: p.get('type') for p in route_points}
        for point in route_points:
            if point.get('type') == 'Condition':
                condition_ports[point['name']] = (point.get('true_port'), point.get('false_port'))

        adjacency = {}
        for tr in route_transitions:
            adjacency.setdefault(tr['from'], []).append(tr)

        lines.append(f'  Переходы ({len(route_transitions)}):')
        for from_name in sorted(adjacency.keys()):
            from_type = point_type_by_name.get(from_name, '')
            from_label = _format_route_point_label(from_name, from_type)
            lines.append(f'    {from_label}:')
            for tr in adjacency[from_name]:
                to_name = tr['to']
                to_type = point_type_by_name.get(to_name, '')
                to_label = _format_route_point_label(to_name, to_type)
                branch = _transition_branch_label(tr, condition_ports.get(from_name))
                if branch:
                    lines.append(f'      → [{branch}] {to_label}')
                else:
                    lines.append(f'      → {to_label}')
        lines.append('')

    return '\n'.join(lines)


def _validate_module_form_command_args(module_type: str, form_name, command_name):
    """form_name только для FormModule; command_name только для CommandModule; взаимоисключение."""
    fn = (form_name or '').strip() if form_name else ''
    cn = (command_name or '').strip() if command_name is not None else ''
    if fn and cn:
        raise ValueError('form_name and command_name are mutually exclusive')
    if cn and module_type != 'CommandModule':
        raise ValueError("command_name can only be used with module_type='CommandModule'")
    if fn and module_type != 'FormModule':
        raise ValueError("form_name can only be used with module_type='FormModule'")
