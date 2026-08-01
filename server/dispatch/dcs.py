from mcp.types import TextContent

from .common import _ambiguous_block


def _format_shape(schema: dict) -> str:
    bits = [
        f"наборов: {schema.get('dataset_count', 0)}",
        f"полей: {schema.get('field_count', 0)}",
        f"параметров: {schema.get('parameter_count', 0)}",
    ]
    if schema.get('calculated_count'):
        bits.append(f"вычисляемых: {schema['calculated_count']}")
    if schema.get('total_count'):
        bits.append(f"итогов: {schema['total_count']}")
    if schema.get('filter_item_count'):
        bits.append(f"отборов: {schema['filter_item_count']}")
    if schema.get('has_grouping'):
        bits.append("группировки: да")
    bits.append("запрос: да" if schema.get('has_query') else "запрос: нет (правило отбора/выборки)")
    return ", ".join(bits)


def _format_document(doc: dict) -> str:
    """Full extractable document: datasets (name/query/fields), params, calc/total, variants."""
    lines = []
    for ds in doc.get('datasets', []):
        qlen = len(ds['query']) if ds.get('query') else 0
        head = f"    набор {ds.get('name') or '?'} ({ds.get('kind') or '?'}), полей: {len(ds.get('fields') or [])}"
        head += f", запрос: {qlen} симв." if qlen else ", без запроса"
        lines.append(head)
        for f in ds.get('fields', []):
            role = f.get('role')
            role_txt = f" [{', '.join(sorted(role))}]" if role else ""
            title = f" — {f['title']}" if f.get('title') else ""
            lines.append(f"      • {f.get('data_path')}{title}{role_txt}")
    if doc.get('parameters'):
        lines.append("    параметры: " + ", ".join(
            p.get('name') or '?' for p in doc['parameters']))
    if doc.get('calculated_fields'):
        lines.append("    вычисляемые: " + ", ".join(
            c.get('data_path') or '?' for c in doc['calculated_fields']))
    if doc.get('total_fields'):
        lines.append("    итоги: " + ", ".join(
            t.get('data_path') or '?' for t in doc['total_fields']))
    for v in doc.get('settings_variants', []):
        lines.append(
            f"    вариант {v.get('name') or '?'}: выборка {v.get('selection_count', 0)}, "
            f"отборы {v.get('filter_count', 0)}, порядок {v.get('order_count', 0)}"
            + (", с группировками" if v.get('has_grouping') else ""))
    return "\n".join(lines)


async def handle_get_dcs_schema(tools, arguments: dict) -> list[TextContent]:
    object_name = arguments["object_name"]
    project_filter = arguments.get("project_filter")
    template = arguments.get("template")
    extension_filter = arguments.get("extension_filter")

    results = tools.get_dcs_schema(object_name, project_filter, template, extension_filter,
                                   arguments.get("object_type"))

    if not results:
        return [TextContent(
            type="text",
            text=f"Схемы компоновки данных для объекта '{object_name}' не найдены.",
        )]

    response = f"Схемы компоновки данных (СКД) объекта '{object_name}':\n\n"
    for project_name, project_data in results.items():
        response += f"Проект: {project_name}\n"
        for db_name, payload in project_data.items():
            response += f"  {db_name}:\n"
            if payload.get('ambiguous'):
                response += _ambiguous_block(payload)
                continue
            schemas = payload.get('schemas', [])
            if not schemas:
                response += "    (нет схем СКД у объекта)\n"
                continue
            response += f"  {payload['type']}.{payload['object']} — схем: {len(schemas)}\n"
            for schema in schemas:
                response += f"    • {schema['template_name']}: {_format_shape(schema)}\n"
                if 'schema' in schema:
                    response += _format_document(schema['schema']) + "\n"
            if len(schemas) > 1:
                response += "    Уточните template, чтобы получить полный документ одной схемы.\n"
        response += "\n"

    return [TextContent(type="text", text=response.rstrip() + "\n")]
