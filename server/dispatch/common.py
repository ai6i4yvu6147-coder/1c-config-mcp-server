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
