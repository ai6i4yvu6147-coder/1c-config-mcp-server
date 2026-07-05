from mcp.types import TextContent


async def handle_find_referencing_objects(tools, arguments: dict) -> list[TextContent]:
    object_name = arguments["object_name"]
    project_filter = arguments.get("project_filter")
    extension_filter = arguments.get("extension_filter")
    max_results = arguments.get("max_results", 100)
    relation_kinds = arguments.get("relation_kinds")

    results = tools.find_referencing_objects(
        object_name, project_filter, extension_filter, max_results, relation_kinds
    )

    if not results:
        return [TextContent(type="text", text=f"Объект '{object_name}' не найден или на него нет ссылок")]

    response = f"Обратные ссылки на '{object_name}':\n\n"

    for project_name, project_data in results.items():
        response += f"Проект: {project_name}\n"
        for db_name, payload in project_data.items():
            response += f"  {db_name}:\n"

            if payload.get('ambiguous'):
                response += f"    Неоднозначность: уточните object_name.\n"
                response += f"    Запрошено: {payload['requested_name']}\n"
                response += "    Кандидаты:\n"
                for c in payload['candidates']:
                    syn = f" ({c['synonym']})" if c.get('synonym') else ""
                    response += f"      - {c['type']}.{c['name']}{syn}\n"
                response += "\n"
                continue

            target = payload['target']
            syn = f" ({target['synonym']})" if target.get('synonym') else ""
            response += f"    Цель: {target['type']}.{target['name']}{syn}\n"
            total = payload.get('total_count', 0)
            returned = payload.get('returned_count', 0)
            response += f"    total_count: {total}, returned_count: {returned}"
            if payload.get('is_truncated'):
                response += ", is_truncated: true — увеличьте max_results"
            response += "\n"

            if not payload.get('referencers'):
                response += "    (нет обратных ссылок)\n\n"
                continue

            response += "    Referencers:\n"
            for ref in payload['referencers']:
                src = ref['src_object']
                src_syn = f" ({src['synonym']})" if src.get('synonym') else ""
                line = f"      • {src['type']}.{src['name']}{src_syn} [via: {ref['via']}]"
                via = ref['via']
                if via == 'attribute':
                    section = ref.get('attribute_section') or 'Attribute'
                    line += f" — {section}.{ref['field_name']}"
                elif via == 'tabular_section_column':
                    line += f" — TabularSection.{ref['tabular_section_name']}.{ref['field_name']}"
                elif via == 'form_attribute':
                    line += f" — Form.{ref['form_name']}.{ref['field_name']}"
                elif via == 'form_attribute_column':
                    line += f" — Form.{ref['form_name']}.{ref['form_attribute_name']}.{ref['field_name']}"
                elif via == 'subsystem_member':
                    detail = ref.get('source_detail') or 'Content'
                    line += f" — {detail}: {ref.get('source_name', '')}"
                if ref.get('ordinal', 0) > 0:
                    line += f" (ordinal={ref['ordinal']})"
                response += line + "\n"
            response += "\n"

    return [TextContent(type="text", text=response)]
