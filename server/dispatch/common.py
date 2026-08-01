from mcp.types import TextContent

from shared.index_status import format_last_updated_local


def _form_item_command_suffix(item: dict) -> str:
    """Суффикс строки элемента формы для CommandName (текстовый вывод MCP)."""
    cn = item.get('command_name')
    if not cn or not str(cn).strip():
        return ''
    src = item.get('command_source')
    s = str(cn).strip()
    if src == 'Form':
        tail = s[len('Form.Command.'):] if s.startswith('Form.Command.') else s
        return f' [команда формы: {tail}]'
    if src == 'Object':
        return f' [команда объекта: {s}]'
    if src == 'Common':
        tail = s[len('CommonCommand.'):] if s.startswith('CommonCommand.') else s
        return f' [общая команда: {tail}]'
    return ''


def _ambiguous_block(payload: dict, indent: str = "    ") -> str:
    """Рендер неоднозначности разрешения объекта — общий для всех tool'ов, которые
    резолвят объект по имени.

    Подсказка именно про object_type, а не «уточните object_name»: при точном совпадении
    имя у всех кандидатов одно и то же, и уточнять в нём нечего — выбор делается видом.
    """
    lines = [f"{indent}Неоднозначность: имя принадлежит нескольким видам объектов.\n"]
    if payload.get('requested_name'):
        lines.append(f"{indent}Запрошено: {payload['requested_name']}\n")
    lines.append(f"{indent}Кандидаты:\n")
    for c in payload.get('candidates') or []:
        syn = f" ({c['synonym']})" if c.get('synonym') else ""
        lines.append(f"{indent}  - {c['type']}.{c['name']}{syn}\n")
    if payload.get('match_kind') == 'partial':
        lines.append(f"{indent}→ уточните object_name или задайте object_type.\n")
    else:
        first = (payload.get('candidates') or [{}])[0].get('type', 'Document')
        lines.append(f"{indent}→ повторите вызов с object_type, например object_type={first!r}.\n")
    lines.append("\n")
    return "".join(lines)


async def handle_active_databases(tools, arguments: dict) -> list[TextContent]:
    results = tools.list_active_databases()
    lines = []
    for proj in results.get("projects", []):
        lines.append(f"Проект: {proj['name']}")
        for db in proj.get("databases", []):
            if db.get("is_updating"):
                suffix = " [!] обновляется"
            elif db.get("is_outdated"):
                suffix = " [!] устарела"
            else:
                suffix = ""
            updated = format_last_updated_local(db.get("last_updated_at"))
            updated_part = f", обновлена {updated}" if updated else ""
            lines.append(f"  — {db['name']} ({db['type']}){updated_part}{suffix}")
        lines.append("")
    return [TextContent(type="text", text="Активные проекты и базы:\n\n" + "\n".join(lines) if lines else "Нет активных проектов.")]
